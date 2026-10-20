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
from dataclasses import dataclass, field
import math
import re

VERBS = (r'(?:what|whats|what\'s|who|where|when|which|how|why|is|are|does|do|can|could|write|create|make|generate|build|code|'
         r'calculate|compute|work out|solve|convert|translate|draw|paint|show|tell|give|list|explain|define|describe|find|'
         r'look up|search|add|subtract|multiply|divide|double|halve|square|take|use|run|test|call|apply|check|fix|sort|'
         r'reverse|count|summari[sz]e|say|recommend|suggest|plan|compare|now)')
STEP_SPLIT = re.compile(r'(?i)(?:[,;.?!]\s*|\s+)(?:and\s+)?(?:then|after that|afterwards|next|finally|and finally|once (?:that\'s|that is) done)\s*,?\s+'
                        r'|(?:\n\s*)+(?:\d+[.)]\s*|step \d+\s*[:.]\s*|-\s+)?|(?<=[?!])\s+(?=' + VERBS + r'\b)')
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


def plan(text):
    """The steps of a multi-part request, or None when it is a single request."""
    if len(text) > 1500 or '```' in text:
        return None
    parts = [p.strip(' ,;') for p in STEP_SPLIT.split(text) if p and p.strip(' ,;.')]
    if len(parts) < 2 or len(parts) > 6:
        return None
    # The first part may set the scene ("I have 3 apples ..."); every later part must be a request of its own.
    request = re.compile(r'(?i)(?:please\s+|and\s+|also\s+)?' + VERBS + r'\b')
    if not all(request.match(p) for p in parts[1:]):
        return None
    if not request.match(parts[0]) and not any(REFERENCE.search(p) for p in parts[1:]):
        return None
    if not any(REFERENCE.search(p) for p in parts[1:]) and not re.search(r'(?i)\b(?:then|after that|next|finally)\b|\n', text):
        return None
    return parts


# Values -----------------------------------------------------------------------------------------
def number_in(response):
    """The answer number of an engine reply: the result after '=' or the first number in the first sentence."""
    first = response.split('\n', 1)[0]
    after = re.search(r'=\s*(' + NUMBER.pattern + r')\s*$', first)
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
        return match[1].strip(' "')
    quoted = re.search(r'\*\*(.+?)\*\*', first)
    if quoted and len(quoted[1].split()) <= 6:
        return quoted[1]
    return None


def classify(route, response):
    result = re.search(r'` = \*\*(.+?)\*\*', response)          # "`area(6, 7)` = **42**" from a learned rule
    if route == 'chat/rules-use' and result:
        value = result[1]
        return ('number', value) if NUMBER.fullmatch(value) else ('short', value.strip("'\""))
    code = re.search(r'```python\n(.*?)```', response, re.S)
    if code and re.search(r'^def \w+\(', code[1], re.M):
        return 'code', code[1]
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
    wants_code = re.search(r'(?i)\b(?:run|call|test|apply|execute|use)\b.*\b(?:it|that|the function|the code|this)\b'
                           r'|\bwhat does (?:it|the function) (?:return|give)\b', request)
    if wants_code:
        entry = board.get(kinds={'code'})
        if entry:
            return request, [f'uses the function from step {entry.step}'], entry
    text = request

    def swap(match):
        step = match[1] or match[2]
        word = match[0].lower()
        if word in ('this', 'that', 'it') and not wants_value(text, match):
            return match[0]
        entry = board.get(int(step)) if step else board.get(kinds={'number', 'short'})
        if entry is None:
            return match[0]
        notes.append(f'"{match[0]}" = {entry.value} (from step {entry.step})')
        return str(entry.value)

    text = REFERENCE.sub(swap, text)
    return text, notes, None


def wants_value(text, match):
    """Is a bare 'it' / 'that' / 'this' a reference to an earlier answer here (and not 'what is it like')?"""
    before = text[:match.start()].lower()
    after = text[match.end():].lower()
    return bool(re.search(r'(?:add|subtract|multiply|divide|double|triple|halve|square|translate|draw|paint|convert|take|'
                          r'times|plus|minus|by|to|from|of|and|is|with|use|spell|reverse|describe|explain|define)\s*$', before)
                or re.match(r'\s*(?:by|to|from|into|in|squared|times|plus|minus|divided|multiplied|and|\?|$)', after))


def run_code(entry, request):
    """Call the function an earlier step wrote, on the arguments the request gives."""
    name = re.search(r'^def (\w+)\(', entry.value, re.M)[1]
    args_text = re.search(r'(?i)\b(?:on|with|for|using|of)\s+(.+?)\s*[?.!]*$', request)
    if not args_text:
        return None, 'Tell me which input to run it on, for example "run it on 10".'
    try:
        args = ast.literal_eval('(' + args_text[1].replace(' and ', ', ') + ',)')
    except (ValueError, SyntaxError):
        return None, f'I could not read "{args_text[1]}" as Python values.'
    if any(isinstance(a, int) and not isinstance(a, bool) and abs(a) > 100_000 for a in args) or \
            any(isinstance(a, (str, list, tuple, dict)) and len(a) > 10_000 for a in args):
        return None, 'That input is too large for me to run safely.'
    scope = {'__builtins__': {k: __builtins__[k] if isinstance(__builtins__, dict) else getattr(__builtins__, k)
                              for k in ('len', 'sum', 'min', 'max', 'sorted', 'list', 'dict', 'set', 'tuple', 'str', 'int',
                                        'float', 'abs', 'round', 'range', 'all', 'any', 'zip', 'enumerate', 'reversed', 'bool')},
             'math': math}
    try:
        exec(entry.value.replace('import math\n', ''), scope)
        value = scope[name](*args)
    except Exception as error:
        return None, f'Running `{name}` raised {type(error).__name__}: {error}'
    call = f'{name}({", ".join(map(repr, args))})'
    return value, f'`{call}` returns `{value!r}`.'


# Running a plan ---------------------------------------------------------------------------------
def run(steps, answer_one, messages=()):
    """Run each step through answer_one(text, history) and share results on a board."""
    board = Board()
    history = list(messages[:-1]) if messages else []
    for index, request in enumerate(steps, 1):
        text, notes, code = resolve(request, board)
        if code is not None:
            value, response = run_code(code, request)
            entry = Entry(index, request, 'chat/code-run', response, 'number' if isinstance(value, (int, float)) and not isinstance(value, bool)
                          else 'short', value, notes)
        else:
            arithmetic = spoken_arithmetic(text)
            if arithmetic:
                notes.append(f'read as {arithmetic}')
                text = arithmetic
            answer = answer_one(text, history)
            if answer:
                from . import verify
                answer = verify.apply(text, answer)   # a corrected value is what later steps will use
            response = (answer or {}).get('response') or 'I could not do this step.'
            route = (answer or {}).get('route', 'none')
            kind, value = classify(route, response)
            if kind == 'number' and '/' in str(value):
                top, bottom = str(value).split('/')
                value = decimal(int(top) / int(bottom))
                response = response.rstrip() + f' (about {value})'
            entry = Entry(index, request, route, response, kind, value, notes, (answer or {}).get('verification', {}))
        board.add(entry)
        history += [dict(role='user', content=text), dict(role='assistant', content=entry.response)]
    return board


def report(board):
    lines, trace = [], []
    for e in board.entries:
        lines.append(f'**{e.step}. {e.request[0].upper() + e.request[1:]}**\n{e.response.strip()}')
        trace.append(f'Step {e.step} [{e.route}] -> {e.kind}' + (f': {e.value}' if e.kind in ('number', 'short') else '')
                     + (f' [check: {e.verification.get("status", "unchecked")}]')
                     + (' (' + '; '.join(e.notes) + ')' if e.notes else ''))
    details = ('Multi-step plan: the request was split into steps, each step was answered by the ordinary CAEL route '
               'for it, and later steps used earlier results through a shared board.\n' + '\n'.join(trace))
    return dict(route='chat/plan', response='\n\n'.join(lines), sources=[], details=details,
                plan=[dict(step=e.step, request=e.request, route=e.route, kind=e.kind,
                           value=e.value if isinstance(e.value, (int, float, str)) else None, notes=e.notes,
                           verification=e.verification) for e in board.entries])
