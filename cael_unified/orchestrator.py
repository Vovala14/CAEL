"""Let CAEL's engines work together on one multi-part request.

Every engine (arithmetic, quantities, reasoning, facts, code, translation, pictures...) answers a whole message
or passes. A request such as "What is the population of France? Then divide it by 4" needs two of them, with
the second using the first one's result. This module does that with three parts:

* Planner: splits a request into steps at explicit sequencing words ("then", "after that", numbered lines),
  but only when every step reads as its own request, so a story like "Mary went home, then John left" is
  never split.
* Board: a shared record of each step's result, kept as a typed value (number, code, short answer, text)
  plus the engine route that produced it.
* Resolver: before a step runs, words that point back ("it", "that", "the result", "step 2") are replaced
  with the value they refer to; spoken operations ("multiply it by 3") become arithmetic the helper reads.
  "Run it on 10" executes the function an earlier step wrote.

Each step then goes through the ordinary routing, so every engine is reused unchanged. The reply shows each
step, and the details list which engine answered each one and what was substituted.
"""
import ast
import json
from dataclasses import dataclass, field
import re

VERBS = (r'(?:what|whats|what\'s|who|where|when|which|how|why|is|are|does|do|can|could|write|create|make|generate|build|code|'
         r'calculate|compute|work out|solve|convert|translate|draw|paint|show|tell|give|list|explain|define|describe|find|'
         r'look up|search|add|subtract|multiply|divide|double|halve|square|take|use|run|test|call|apply|check|fix|sort|'
         r'reverse|count|summari[sz]e|say|recommend|suggest|plan|compare|now|help|correct|rewrite|change|put|spell|conjugate|triple|increase|decrease|'
         r'should)')
STEP_SPLIT = re.compile(r'(?i)(?:[,;.?!]\s*|\s+)(?:and\s+)?(?:then|after that|afterwards|next|finally|and finally|once (?:that\'s|that is) done)\s*,?\s+'
                        r'|(?:\n\s*)+(?:\d+[.)]\s*|step \d+\s*[:.]\s*|-\s+)?|(?<=[?!])\s+(?=' + VERBS + r'\b)'
                        r'|(?<=[?!.])\s+(?:also|and also|plus)\s*,?\s+(?=' + VERBS + r'\b)')
NUMBERING = re.compile(r'(?i)^\s*(?:\d+[.)]|step \d+\s*[:.])\s*')
# A step that asks about the step before it: "explain the rule", "why?", "show your working".
EXPLAIN = re.compile(r'(?i)^(?:and\s+|please\s+|now\s+)?(?:explain(?:\s+(?:why|how|the rule|the rules|that|it|this|your reasoning|the reasoning|the steps|the answer))?'
                     r'|why(?:\s+is that)?|how come|show (?:me )?(?:your|the) (?:working|steps|reasoning)|what (?:is|was) the rule)\s*[?.!]*$')
REFERENCE = re.compile(r'(?i)\b(?:the (?:result|answer|number|value|output|total|function|code|word|phrase|name|city|place)'
                       r'(?: (?:from|of) (?:step|part) (\d+))?|that (?:number|result|answer|value|word|phrase|function|name)|'
                       r'(?:step|part) (\d+)|this|that|it)\b')
NUMBER = re.compile(r'-?\d[\d,]*(?:\.\d+)?(?:/\d+)?')


@dataclass
class Entry:
    step: int
    request: str
    route: str
    response: str
    kind: str                # number | code | short | text
    value: object = None
    notes: list = field(default_factory=list)
    verification: dict = field(default_factory=dict)
    status: str = 'ok'       # ok | uncertain | failed | skipped
    dependencies: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    resolved_request: str = ''
    tool: dict = field(default_factory=dict)


class Board:
    def __init__(self):
        self.entries = []

    def add(self, entry):
        self.entries.append(entry)

    def get(self, step=None, kinds=None):
        """The latest entry (or the given step's) whose value has one of the wanted kinds."""
        pool = [e for e in self.entries if step is None or e.step == step]
        for entry in reversed(pool):
            if entry.value is not None and (kinds is None or entry.kind in kinds):
                return entry
        return None

    def dependency(self, step=None):
        if step is not None:
            entry=next((e for e in self.entries if e.step==step),None)
        else:
            # An explanation adds no new result, but failures are barriers:
            # never search past one for an older convenient answer.
            entry=next((e for e in reversed(self.entries) if e.route!='chat/plan-explain'),None)
        if entry is None:
            raise ResolutionError(f'Step {step} has not produced a result.' if step else 'There is no earlier result to use.',step)
        if entry.status!='ok' or (entry.value is None and entry.kind!='literal'):
            raise ResolutionError(f'Step {entry.step} gave no single usable result.',entry.step)
        return entry


class ResolutionError(ValueError):
    def __init__(self,message,step=None):
        super().__init__(message)
        self.step=step


def protected_spans(text):
    """Quotes/backticks are data. Apostrophes inside words are not quote starts."""
    spans=[];i=0
    while i<len(text):
        char=text[i]
        if char not in '\"\'`' or (char=="'" and i and text[i-1].isalnum()):
            i+=1;continue
        end=i+1
        while end<len(text):
            if text[end]=='\\':end+=2;continue
            if text[end]==char:
                spans.append((i,end+1));i=end+1;break
            end+=1
        else:i+=1
    return spans


def unprotected(text,match,spans):
    return not any(left<match.end() and match.start()<right for left,right in spans)


def plan(text):
    """The steps of a multi-part request, or None when it is a single request."""
    if len(text) > 1500 or '```' in text:
        return None
    request = re.compile(r'(?i)(?:please\s+|and\s+|also\s+)?' + VERBS + r'\b')
    spans=protected_spans(text)
    cuts=[m for m in STEP_SPLIT.finditer(text) if unprotected(text,m,spans)
          and ('\n' not in m[0] or (not re.match(r'[A-Za-z_]\w*\s*\(',text[m.end():])
               and (request.match(text[m.end():]) or EXPLAIN.match(text[m.end():]))))]
    parts=[];start=0
    for cut in cuts:
        parts.append(text[start:cut.start()]);start=cut.end()
    parts.append(text[start:])
    parts = [NUMBERING.sub('', p.strip(' ,;')) for p in parts if p and p.strip(' ,;.')]
    parts = [p for p in parts if p.strip(' ,;.')]
    if len(parts) < 2 or len(parts) > 6:
        return None
    # The first part may set the scene ("I have 3 apples ..."); every later part must be a request of its own.
    if not all(request.match(p) or EXPLAIN.match(p) for p in parts[1:]):
        return None
    points_back = any(REFERENCE.search(p) or EXPLAIN.match(p) for p in parts[1:])
    if not request.match(parts[0]) and not points_back:
        return None
    if not points_back and not re.search(r'(?i)\b(?:then|after that|next|finally|also|plus)\b|\n', text):
        return None
    return parts


def normalise(step):
    """Everyday phrasings of a step that the engines read better as a plain question."""
    text = re.sub(r'(?i)^(?:and\s+|also\s+|now\s+|please\s+)+', '', step.strip())
    # "tell me if the result is a prime number" -> "is the result a prime number?"
    text = re.sub(r'(?i)^(?:can you\s+|could you\s+)?(?:tell me|check)\s+(?:if|whether)\s+(.+?)\s+(is|are)\s+(.+?)\s*[?.!]*$', r'\2 \1 \3?', text)
    text = re.sub(r'(?i)^(?:can you\s+|could you\s+)?tell me\s+(?=(?:how|what|who|when|where|which|why|whether|if)\b)', '', text)
    text = re.sub(r'(?i)^(?:can you\s+|could you\s+)?tell me the (\w+(?: \w+)?) of (.+?)\s*[?.!]*$', r'what is the \1 of \2?', text)
    text = re.sub(r'(?i)^say\s+(.+?)\s+in\s+([A-Z][a-z]+)\s*[?.!]*$', r'how do you say \1 in \2?', text)
    # Splitting at "? Then" drops the question mark some engines read ("..., is Tom an animal?").
    if not re.search(r'[?.!"\')]$', text) and re.search(r'(?i)^(?:is|are|does|do|did|can|could|would|should)\b|,\s*(?:is|are|does|do|can)\b', text):
        text += '?'
    return text


# Values -----------------------------------------------------------------------------------------
def number_in(response):
    """The answer number of an engine reply: the result after '=' or the first number in the first sentence."""
    first = response.split('\n', 1)[0]
    after = re.search(r'=\s*\**(' + NUMBER.pattern + r')\**(?:\s+[A-Za-z]+)?\s*[.!]?$', first)
    if after:
        return after[1]
    found = NUMBER.findall(re.sub(r'\[[^\]]*\]|\(\d{4}\)', '', first))
    found = [f for f in found if not re.fullmatch(r'(?:1[5-9]|20)\d\d', f.replace(',', ''))] or found
    return found[0].replace(',', '') if found else None


def short_answer(response):
    """A short answer inside a sentence: 'The capital of Japan is Tokyo.' -> 'Tokyo'."""
    first = response.strip().split('\n', 1)[0]
    match = re.match(r'^(?:the|a|an)?\s*.+?\b(?:is|was|are|were) \**([^.*]+?)\**\.?$', first, re.I)
    if match and len(match[1].split()) <= 5:
        # "Hamlet was written by William Shakespeare." -> the person, not "written by ..."
        return re.sub(r'(?i)^(?:written|painted|directed|composed|invented|discovered|founded|designed|built|created) by\s+', '',
                      match[1].strip(' "'))
    quoted = re.search(r'\*\*(.+?)\*\*', first)
    if quoted and len(quoted[1].split()) <= 6:
        return quoted[1]
    return None


def classify(route, response):
    if route=='chat/reasoning-words':
        first=response.strip().split('\n',1)[0]
        count=re.fullmatch(r'\*\*.+?\*\* has \*\*(\d+)\*\* (?:letters?|vowels?|consonants?)(?:[.:].*)?',first)
        if count:return 'number',count[1]
        reverse=re.fullmatch(r'\*\*.+?\*\* backwards is \*\*(.+?)\*\*\.',first)
        if reverse:return 'short',reverse[1]
    result = re.search(r'` = \*\*(.+?)\*\*', response)          # "`area(6, 7)` = **42**" from a learned rule
    if route == 'chat/rules-use' and result:
        value = result[1]
        return ('number', value) if NUMBER.fullmatch(value) else ('short', value.strip("'\""))
    # Word answers: the first synonym or opposite, the meaning of a phrase, a corrected sentence.
    if route == 'chat/dictionary-synonyms':
        found = re.search(r':\s*([A-Za-z][\w\' -]*?)\s*[,.]', response.split('\n', 1)[0])
        if found:
            return 'short', found[1]
    if route == 'chat/dictionary-antonyms':
        found = re.search(r'\*\*([^*]+)\*\*[^*]*$', response.split('\n', 1)[0])
        if found:
            return 'short', found[1].split(',')[0].strip()
    if route == 'chat/everyday-translate-meaning':
        found = re.search(r'means\s+"([^"]+)"', response)
        if found:
            return 'short', found[1]
    if route.startswith('chat/grammar-'):
        found = re.search(r'(?:Corrected|In the past tense|In the passive|With punctuation)[^*]*\*\*(.+?)\*\*', response)
        if found:
            return 'short', found[1]
    code = re.search(r'```python\n(.*?)```', response, re.S)
    if code and re.search(r'^def \w+\(', code[1], re.M):
        return 'code', code[1]
    # Exact symbolic results come with a decimal ("Area = 9*pi (approximately 28.27433388)"): pass the decimal on.
    # Exact-quantity answers mark their result in bold ("2 to the power of 10 = **1024**", "You get **$1.40** in change").
    bold = re.search(r'\*\*\$?(-?\d[\d,]*(?:\.\d+)?)%?(?:°[CF])?(?:\s[a-z/]+)?\*\*', response.split('\n', 1)[0])
    if route.startswith('helper/quantity-') and bold:
        return 'number', bold[1].replace(',', '')
    approximate = re.search(r'\(approximately\s+(-?\d+(?:\.\d+)?)\)', response.split('\n', 1)[0])
    if route.startswith('helper/') and approximate:
        return 'number', approximate[1]
    if route.startswith(('helper/', 'chat/everyday-figure')) or route in ('chat/web-wikidata-faq',):
        number = number_in(response)
        if number is not None and route.startswith('helper/'):
            return 'number', number
        short = short_answer(response)
        if number is not None and (short is None or NUMBER.search(short)):
            return 'number', number
        if short:
            return 'short', short
    short = short_answer(response)
    if short and not route.startswith(('chat/smalltalk', 'chat/local')):
        number = number_in(short)
        return ('number', number) if number and NUMBER.fullmatch(short.replace(',', '').split()[0]) else ('short', short)
    return 'text', response.strip()


def decimal(x):
    return f'{x:.6f}'.rstrip('0').rstrip('.')


# Resolving references ---------------------------------------------------------------------------
SPOKEN = [
    (r'^(?:add|plus)\s+(.+?)\s+to\s+(.+)$', '({1}) + ({0})'),
    (r'^add\s+(.+?)\s+and\s+(.+)$', '({0}) + ({1})'),
    (r'^subtract\s+(.+?)\s+from\s+(.+)$', '({1}) - ({0})'),
    (r'^take\s+(.+?)\s+(?:away\s+)?from\s+(.+)$', '({1}) - ({0})'),
    (r'^multiply\s+(.+?)\s+by\s+(.+)$', '({0}) * ({1})'),
    (r'^divide\s+(.+?)\s+by\s+(.+)$', '({0}) / ({1})'),
    (r'^(?:double)\s+(.+)$', '({0}) * 2'),
    (r'^(?:triple)\s+(.+)$', '({0}) * 3'),
    (r'^(?:halve|half of)\s+(.+)$', '({0}) / 2'),
    (r'^square\s+(.+)$', '({0}) * ({0})'),
    (r'^(.+?)\s+squared$', '({0}) * ({0})'),
    (r'^(?:take|what is|find|calculate)?\s*(\d+(?:\.\d+)?)\s*%\s+of\s+(.+)$', '({0} / 100) * ({1})'),
    (r'^increase\s+(.+?)\s+by\s+(-?\d+(?:\.\d+)?)\s*%$', '({0}) * (1 + ({1}) / 100)'),
    (r'^decrease\s+(.+?)\s+by\s+(-?\d+(?:\.\d+)?)\s*%$', '({0}) * (1 - ({1}) / 100)'),
    (r'^(?:what is\s+)?(.+?)\s+(plus|minus|times|divided by|multiplied by)\s+(.+)$', None),
]
OPERATORS = {'plus': '+', 'minus': '-', 'times': '*', 'divided by': '/', 'multiplied by': '*'}


def spoken_arithmetic(text):
    """'multiply 24 by 3' -> '(24) * (3)'; None if the step is not plain arithmetic on numbers."""
    body = re.sub(r'(?i)^(?:now\s+|please\s+|and\s+|then\s+)+', '', text.strip(' ?.!'))
    body = re.sub(r'(?i)^(?:calculate|compute|work out|what is|what\'s)\s+', '', body) if re.search(r'(?i)\b(?:plus|minus|times|divided|multiplied)\b', body) else body
    for pattern, template in SPOKEN:
        match = re.match(pattern, body, re.I)
        if not match:
            continue
        if template is None:
            parts = [match[1], OPERATORS[match[2].lower()], match[3]]
            expression = f'({parts[0]}) {parts[1]} ({parts[2]})'
            operands = [parts[0], parts[2]]
        else:
            operands = list(match.groups())
            expression = template.format(*operands)
        if all(re.fullmatch(r'\s*-?\d[\d,]*(?:\.\d+)?(?:/\d+)?\s*', o or '') for o in operands):
            return expression.replace(',', '')
    return None


def resolve(request, board):
    """Replace back-references with the values they point to. Returns (new text, notes, code entry or None)."""
    notes = []
    wants_code = bool(re.match(r'(?i)^(?:run|call|test|apply|execute|use)\b',request)
                      or re.match(r'(?i)^what does (?:it|the function) (?:return|give)\b',request))
    code=None
    text = request
    spans=protected_spans(text)

    def swap(match):
        nonlocal code
        if not unprotected(text,match,spans) or not is_reference(text,match):return match[0]
        step = match[1] or match[2]
        entry = board.dependency(int(step) if step else None)
        if entry.kind=='code' or wants_code and code is None and entry.tool:
            if not wants_code or code is not None and code.step!=entry.step:
                raise ResolutionError('Specify one function to run, or ask to explain its step.',entry.step)
            code=entry
            notes.append(f'uses the function from step {entry.step}')
            return 'the function'
        if wants_code and code is None:
            raise ResolutionError(f'Step {entry.step} did not produce a function to run.',entry.step)
        if numeric_request(text) and (entry.kind=='literal' or not NUMBER.fullmatch(str(entry.value).replace(',',''))):
            raise ResolutionError(f'Step {entry.step} did not produce a single number.',entry.step)
        notes.append(f'"{match[0]}" = {entry.value} (from step {entry.step})')
        value = repr(entry.value) if entry.kind=='literal' or wants_code and entry.kind!='number' else str(entry.value)
        # A whole sentence goes in quotes so the next engine reads it as the text to work on.
        if code is None and not wants_code and len(value.split()) >= 3 and re.search(r'[.!?]$', value):return repr(value)
        return value

    text = REFERENCE.sub(swap, text)
    # "What is the weather there?" after a step that named a place.
    there = re.search(r'(?i)(?<!\bis )(?<!\bare )\bthere(?=\s*[?.!]*$)', text)
    if there and unprotected(text,there,protected_spans(text)):
        place=board.dependency()
        if place.kind!='short' or len(str(place.value).split())>4 or NUMBER.fullmatch(str(place.value)):
            raise ResolutionError(f'Step {place.step} did not identify a single place.',place.step)
        text = text[:there.start()] + f'in {place.value}' + text[there.end():]
        notes.append(f'"there" = {place.value} (from step {place.step})')
    return text, notes, code


def numeric_request(text):
    return bool(re.match(r'(?i)^(?:add|subtract|multiply|divide|double|triple|halve|square|increase|decrease)\b',text))


def is_reference(text, match):
    if match[1] or match[2]:return True
    tail=text[match.end():]
    # "this: hello", "the word banana" and "is it raining" provide their
    # own subject. They are not dependencies on a previous tool result.
    if re.match(r'\s*[:=]',tail):return False
    if match[0].lower() in ('it','this','that'):
        if re.match(r'(?i)\s+(?:like|raining|snowing|sunny|cold|hot|possible)\b',tail):return False
        return wants_value(text,match)
    next_word=re.match(r'\s+([\w]+)',tail)
    if next_word and next_word[1].lower() not in {
        'in','into','to','from','of','by','on','with','using','for','and','is','are','was','were',
        'backwards','backward','squared','plus','minus','times','divided','multiplied','has','have',
    }:return False
    return True


def wants_value(text, match):
    """Is a bare 'it' / 'that' / 'this' a reference to an earlier answer here (and not 'what is it like')?"""
    before = text[:match.start()].lower()
    after = text[match.end():].lower()
    return bool(re.search(r'(?:add|subtract|multiply|divide|double|triple|halve|square|increase|decrease|translate|draw|paint|convert|take|'
                          r'times|plus|minus|by|to|from|of|and|is|with|use|run|call|execute|test|apply|spell|reverse|describe|explain|define|'
                          r'(?:letters|vowels|consonants|words) (?:are )?in)\s*$', before)
                or re.match(r'\s*(?:by|to|from|into|in|squared|times|plus|minus|divided|multiplied|and|\?|$)', after))


def code_outcome(entry, request):
    """Call the function an earlier step wrote, on the arguments the request gives."""
    source=entry.value
    if entry.tool:
        from .codegen.tool_contract import read
        try:artifact=read(entry.tool)
        except ValueError as error:return None,str(error),'failed'
        source=artifact['source'];name=artifact['entrypoint']
    function = re.search(r'^def (\w+)\(', source, re.M)
    if not function:return None,'That step did not provide a supported Python function.','failed'
    if not entry.tool:name = function[1]
    args_text = re.search(r'(?i)\b(?:on|with|for|using|of)\s+(.+?)\s*[?.!]*$', request)
    if not args_text:
        return None, 'Tell me which input to run it on, for example "run it on 10".', 'uncertain'
    try:
        raw=args_text[1]
        if len(raw)>8000:raise ValueError('Argument text too large')
        spans=protected_spans(raw);depth=0;pieces=[];start=0
        for match in re.finditer(r'[\[\]{}()]|\band\b',raw):
            if not unprotected(raw,match,spans):continue
            if match[0] in ('[','{','('):depth+=1
            elif match[0] in (']','}',')'):depth-=1
            elif depth==0:
                pieces.append(raw[start:match.start()]);start=match.end()
        pieces.append(raw[start:]);raw=','.join(pieces)
        tree=ast.parse('_call('+raw+')',mode='eval')
        if sum(1 for _ in ast.walk(tree))>1000:raise ValueError('Argument AST too large')
        args=[ast.literal_eval(a) for a in tree.body.args]
        kwargs={k.arg:ast.literal_eval(k.value) for k in tree.body.keywords}
        if None in kwargs or len(kwargs)!=len(tree.body.keywords):raise ValueError('Ambiguous keyword arguments')
    except (ValueError, SyntaxError, RecursionError, TypeError):
        return None, 'I could not read the inputs as bounded Python literal arguments.', 'uncertain'
    call = f'{name}({", ".join([repr(a) for a in args]+[k+"="+repr(v) for k,v in kwargs.items()])})'
    # No native exec fallback: unsupported operations and exhausted budgets are
    # failures, never invitations to retry the same source without limits.
    from .codegen.python_vm import run_cases
    checked = run_cases(source, [dict(name=name, args=args,kwargs=kwargs)])
    outcome = (checked.get('cases') or [{}])[0]
    if outcome.get('status') == 'value':
        return outcome['value'], f'`{call}` returns `{outcome["value"]!r}` (run by CAEL\'s bounded Python interpreter).', 'ok'
    if outcome.get('status') == 'error':
        return None, f'Running `{name}` raised {outcome["error"]}: {outcome["message"]}', 'failed'
    status=outcome.get('status',checked.get('status','unsupported'))
    return None, f'I could not run `{name}` within the bounded Python interpreter ({status}).', 'failed'


def run_code(entry,request):
    value,response,_=code_outcome(entry,request)
    return value,response


# Running a plan ---------------------------------------------------------------------------------
def run(steps, answer_one, messages=()):
    """Run each step through answer_one(text, history) and share results on a board."""
    board = Board()
    history = list(messages[:-1]) if messages else []
    if not 1<=len(steps)<=6:raise ValueError('Use between one and six plan steps')
    for index, request in enumerate(steps, 1):
        target=re.fullmatch(r'(?i)(?:explain|explain why|show (?:the )?(?:reasoning|steps) for) (?:step|part) (\d+)\s*[?.!]*',request.strip())
        if target or EXPLAIN.match(request.strip()):
            previous=next((e for e in board.entries if e.step==int(target[1])),None) if target else (board.entries[-1] if board.entries else None)
            if previous:
                board.add(explain(index,request,previous))
            else:
                board.add(Entry(index,request,'chat/plan-skipped','There is no completed step with that number to explain.','text',None,status='skipped'))
            history += [dict(role='user', content=request), dict(role='assistant', content=board.entries[-1].response)]
            continue
        last = board.entries[-1] if board.entries else None
        step_text = normalise(request)
        # "Make a prompt for a dog image, then make one for a cat": "one"/"another" is another prompt of the same kind.
        if last is not None and last.route.startswith('chat/prompt-'):
            step_text = re.sub(r'(?i)^(make|write|create|generate|give me|do)\s+(?:one|another)(?:\s+(?:one|more))?\b',
                               r'\1 a prompt', step_text)
            if re.fullmatch(r'(?i)(?:make|write|create|generate|give me|do) a prompt\s*[.!?]*', step_text):
                from .promptgen import parse as parse_prompt
                earlier = parse_prompt(last.request)
                if earlier and earlier['brief']:
                    step_text = step_text.rstrip(' .!?') + ' for ' + earlier['brief']
                    if earlier['kind'] == 'image' and not re.search(r'(?i)\b(?:image|picture|photo)\b', earlier['brief']):
                        step_text += ' image'
        try:
            text, notes, code = resolve(step_text, board)
        except ResolutionError as error:
            board.add(Entry(index,request,'chat/plan-skipped','I could not do this step: '+str(error),
                            'text',None,status='skipped',dependencies=[error.step] if error.step else []))
            history += [dict(role='user',content=request),dict(role='assistant',content=board.entries[-1].response)]
            continue
        dependencies=sorted({int(n) for note in notes for n in re.findall(r'\bstep (\d+)\b',note)})
        if code is not None:
            value, response, status = code_outcome(code, text)
            entry = Entry(index, request, 'chat/code-run', response, 'number' if isinstance(value, (int, float)) and not isinstance(value, bool)
                          else 'short' if isinstance(value,str) else 'literal', value, notes,status=status,dependencies=dependencies,
                          resolved_request=text,verification=dict(status='unchecked',check='Bounded execution, not an independent correctness proof.'))
        else:
            arithmetic = spoken_arithmetic(text)
            if arithmetic:
                notes.append(f'read as {arithmetic}')
                text = arithmetic
            try:
                answer = answer_one(text, history)
            except Exception as error:
                entry=Entry(index,request,'chat/plan-error','This step failed; independent steps can still continue.',
                            'text',None,[type(error).__name__],status='failed',dependencies=dependencies,resolved_request=text)
                board.add(entry)
                history += [dict(role='user',content=text),dict(role='assistant',content=entry.response)]
                continue
            if answer:
                from . import verify
                if re.search(r'```python\n.*?^def \w+\(',answer.get('response',''),re.S|re.M):
                    # Do not send source through the legacy native-code checker
                    # here. This plan invokes functions only through the VM.
                    if answer.get('verification',{}).get('status')!='failed':
                        answer=dict(answer,verification=dict(status='unchecked',check='Function kept as source; calls use the bounded Python interpreter.'))
                else:
                    answer = verify.apply(text, answer)   # corrected values feed later steps
            response = (answer or {}).get('response') or 'I could not do this step.'
            route = (answer or {}).get('route', 'none')
            kind, value = classify(route, response)
            status='ok' if answer else 'failed'
            artifact={}
            if 'python_tool' in (answer or {}):
                from .codegen.tool_contract import read
                try:
                    artifact=read(answer['python_tool'])
                    result=answer.get('tool_result')
                    if result is not None:
                        if result.get('status')!='value' or result.get('source_sha256')!=artifact['sha256']:
                            raise ValueError('Tool result/source mismatch')
                        value=result['value']
                        kind='number' if type(value) in (int,float) else 'short' if type(value) is str else 'literal'
                        if kind=='number':value=str(value)
                    else:kind,value='code',artifact['source']
                except (ValueError,TypeError,KeyError):
                    artifact={};status='failed';value=None
            reasoning=(answer or {}).get('reasoning')
            if isinstance(reasoning,list):status='uncertain';value=None
            if isinstance(reasoning,dict):
                conclusion=reasoning.get('answer')
                if conclusion in (None,'unknown','conflicting','maybe'):
                    status='uncertain';value=None
                elif isinstance(conclusion,str) and NUMBER.fullmatch(conclusion):kind,value='number',conclusion
                elif isinstance(conclusion,str):kind,value='short',conclusion
            if re.search(r'(?:^|[/\-])(?:clarify|not-found|unsure|unsupported|undefined|cannot|needs-examples)(?:$|[/\-])',route):
                status='uncertain';value=None
            if (answer or {}).get('verification',{}).get('status')=='failed':status='failed';value=None
            # Several solutions have no single value to pass to a later step.
            several = re.search(r'(?i)^\s*(\w+)\s*=\s*(-?[\d./]+)(?:\s*(?:,|or)\s*\1\s*=\s*-?[\d./]+)+', response.split('\n', 1)[0])
            if kind == 'number' and several:
                kind, value = 'text', None
                route = 'chat/plan-clarify-solutions'
                response += '\nWhich solution should the next step use?'
                notes.append('multiple solutions; no single value selected')
                status='uncertain'
            entry = Entry(index, request, route, response, kind, value, notes, (answer or {}).get('verification', {}),
                          status,dependencies,list((answer or {}).get('sources') or []),text,artifact)
        board.add(entry)
        history += [dict(role='user', content=text), dict(role='assistant', content=entry.response)]
    return board


def explain(index, request, previous):
    """'Explain the rule' / 'why?' after a step: the reasoning that step's engine gave for its answer."""
    body = previous.response.strip()
    reasons = re.split(r'\n\s*\n', body, maxsplit=1)
    reasoning = reasons[1].strip() if len(reasons) > 1 and re.search(r'(?i)steps:|what i changed|because|rule|\n\d\.|\n- ', reasons[1]) else ''
    if not reasoning and previous.verification.get('status') in ('verified','corrected'):
        reasoning = f'The answer was checked independently ({previous.verification["status"]}).'
    if previous.status!='ok':
        reasoning=f'Step {previous.step} was {previous.status}; it produced no single usable result.\n'+previous.response
    if not reasoning:
        reasoning = ('That step came from ' + previous.route.split('/', 1)[-1].replace('-', ' ') +
                     '; it did not give separate reasoning beyond the answer itself.')
    return Entry(index, request, 'chat/plan-explain', f'Here is the reasoning behind step {previous.step}:\n\n{reasoning}', 'text',
                 reasoning, [f'explains step {previous.step}'],dependencies=[previous.step],sources=list(previous.sources))


def report(board):
    lines, trace, sources = [], [], []
    seen=set()
    for e in board.entries:
        lines.append(f'**{e.step}. {e.request[0].upper() + e.request[1:]}**\n{e.response.strip()}')
        trace.append(f'Step {e.step} [{e.route}; {e.status}] -> {e.kind}' + (f': {e.value}' if e.kind in ('number', 'short') else '')
                     + (f' [check: {e.verification.get("status", "unchecked")}]')
                     + (' (' + '; '.join(e.notes) + ')' if e.notes else ''))
        for source in e.sources:
            key=json.dumps(source,sort_keys=True,default=str)
            if key not in seen:sources.append(source);seen.add(key)
    details = ('Multi-step plan: the request was split into steps, each step was answered by the ordinary CAEL route '
               'for it, and later steps used earlier results through a shared board.\n' + '\n'.join(trace))
    counts={status:sum(e.status==status for e in board.entries) for status in ('ok','uncertain','failed','skipped')}
    state='complete' if counts['ok']==len(board.entries) else 'partial' if counts['ok'] else 'failed'
    def public_value(entry):
        if entry.kind=='code' or entry.value is None:return None
        try:json.dumps(entry.value,allow_nan=False);return entry.value
        except (TypeError,ValueError):return repr(entry.value)
    return dict(route='chat/plan', response='\n\n'.join(lines), sources=sources, details=details,
                plan_status=state,execution_summary=counts,
                plan=[dict(step=e.step, request=e.request, route=e.route, kind=e.kind,
                           value=public_value(e), notes=e.notes,status=e.status,dependencies=e.dependencies,
                           resolved_request=e.resolved_request,sources=e.sources,verification=e.verification,
                           python_tool=e.tool or None) for e in board.entries])
