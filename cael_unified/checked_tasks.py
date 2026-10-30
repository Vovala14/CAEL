"""Whole-task readers with checked symbolic execution and explicit coverage.

No task IDs, solution corpus, learned weights, network, eval or native generated
code. Unsupported clauses stay unsupported instead of becoming a partial answer.
"""
import ast
from datetime import date, timedelta
import re


class Unclear(ValueError):
    pass


NUMBERS = dict(zip('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split(),range(21)))
ORDINALS = 'first second third fourth fifth sixth seventh eighth'.split()
MONTHS = {name:i+1 for i,name in enumerate('january february march april may june july august september october november december'.split())}
MONTHS.update({name[:3]:value for name,value in list(MONTHS.items())})
# Authored ordinary culinary/object vocabulary, not a learned classifier. Unknown
# nouns and category distinctions require clarification, not guessed exclusion.
VOCAB = {
    'fruit': 'kiwi plum mango apricot pear cherry grape melon peach apple banana orange raspberry blueberry strawberry lemon lime papaya pineapple nectarine grapefruit',
    'vegetable': 'cucumber zucchini carrot onion potato cauliflower celery cabbage garlic leek broccoli spinach lettuce radish turnip',
    'instrument': 'oboe cello violin viola xylophone marimba harp guitar piano flute trumpet trombone clarinet accordion drum saxophone bassoon tuba ukulele',
    'animal': 'cat dog rabbit horse cow goat sheep pig hamster parrot chicken duck goose fish turtle mouse lizard',
    'other': 'pebble stone book notebook pen pencil spoon fork plate cup bowl sock shoe hat coin button vase pot chair table lamp box bag crate',
}
NOUNS = {word:category for category,words in VOCAB.items() for word in words.split()}
CATEGORIES = {'fruits':'fruit','fruit':'fruit','vegetables':'vegetable','vegetable':'vegetable',
    'instruments':'instrument','musical instruments':'instrument','animals':'animal','animal':'animal'}


def interested(text):
    if not isinstance(text,str):return False
    return bool(re.match(r'(?is)^\s*(?:evaluate (?:the truth value of |the Boolean expression )?|'
        r'what is the truth value of |(?:not\s+|true\b|false\b|\(\s*(?:not|true|false)\b)|'
        r'(?:sort|alphabetize|put) (?:these|the following)|items\s*:|objects\s*:|participants\s*:|'
        r'(?:on|in|at) [^\n:]{1,100}:|there (?:are|stand) [^\n:]{1,100}:|'
        r'(?:I have|\w+ has|the \w+ (?:contains|holds))\b|today is\b)',text))


def _number(text):
    text=text.casefold()
    if text in NUMBERS:return NUMBERS[text]
    if re.fullmatch(r'\d{1,6}',text):return int(text)
    raise Unclear('Use an explicit bounded nonnegative whole-number count.')


def _boolean(text):
    declared=bool(re.match(r'(?i)^(?:evaluate (?:the truth value of|the Boolean expression)|what is the truth value of)\b',text))
    text=re.sub(r'(?i)^(?:evaluate (?:the truth value of |the Boolean expression )?|what is the truth value of )','',text).strip()
    text=re.sub(r'(?i)\s+is\s*$', '',text.rstrip(' ?.'))
    if not re.fullmatch(r'(?i)[()\s]*(?:(?:true|false|not|and|or)\b[()\s]*)+',text):
        if declared:raise Unclear('The Boolean request contains an unsupported operand or clause; it cannot be omitted.')
        return None
    expression=re.sub(r'(?i)\btrue\b','True',text)
    expression=re.sub(r'(?i)\bfalse\b','False',expression)
    expression=re.sub(r'(?i)\b(?:and|or|not)\b',lambda m:m[0].lower(),expression)
    try:tree=ast.parse(expression.strip(),mode='eval')
    except (SyntaxError,RecursionError):raise Unclear('The Boolean expression is incomplete or has unmatched syntax.')
    if sum(1 for _ in ast.walk(tree))>160:raise Unclear('The Boolean expression exceeds the checked size limit.')
    def value(node):
        if isinstance(node,ast.Constant) and type(node.value) is bool:return node.value
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.Not):return not value(node.operand)
        if isinstance(node,ast.BoolOp) and isinstance(node.op,(ast.And,ast.Or)):
            values=[value(n) for n in node.values]
            return all(values) if isinstance(node.op,ast.And) else any(values)
        raise Unclear('Only Boolean literals, parentheses, not, and, or are supported here.')
    return value(tree.body),'boolean',dict(expression=expression,complete_expression=True)


def _words(text):
    m=re.fullmatch(r'(?is)(?:(?:sort|alphabetize) (?:these|the following) (?:words|tokens)(?: alphabetically| in alphabetical order)?|put (?:these|the following) (?:words|tokens) in alphabetical order)\s*:\s*(?:list\s*:\s*)?(.+)',text)
    if not m:return None
    payload=m[1].strip().rstrip('.')
    words=re.split(r'[\s,]+',payload)
    if not 1<=len(words)<=150 or any(not re.fullmatch(r"[A-Za-z]+(?:['-][A-Za-z]+)*",w) for w in words):
        raise Unclear('Give only the complete word list; extra clauses or unsupported tokens cannot be discarded.')
    ordered=sorted(words,key=str.casefold)
    return ' '.join(ordered),'words',dict(input_words=words,output_words=ordered,preserved_multiplicity=True)


def _singular(word):
    if word in NOUNS:return word
    if word.endswith('ies') and word[:-3]+'y' in NOUNS:return word[:-3]+'y'
    if word.endswith('es') and word[:-2] in NOUNS:return word[:-2]
    if word.endswith('s') and word[:-1] in NOUNS:return word[:-1]
    return word


def _plain_singular(word):
    word=word.strip().casefold()
    if word.endswith('ies') and len(word)>4:return word[:-3]+'y'
    if re.search(r'(?:ches|shes|sses|xes)$',word):return word[:-2]
    if word.endswith('s') and not word.endswith('ss'):return word[:-1]
    return word


def _count(text):
    m=re.fullmatch(r'(?is)(I|[A-Z][a-z]+|the \w+) (?:have|has|contains|holds) (.+?)\.\s*How many (.+?) (?:do I have|does ([A-Z][a-z]+) have|are there|are in the \w+)\??',text)
    if not m:return None
    owner,inventory,asked,query_owner=m.groups()
    if query_owner and query_owner.casefold()!=owner.casefold():raise Unclear('The question asks about a different owner from the supplied inventory.')
    asked=asked.strip().casefold()
    category=CATEGORIES.get(asked)
    wanted=_singular(asked) if _singular(asked) in NOUNS else None
    parts=re.split(r'\s*,\s*(?:and\s+)?(?:then\s+)?|\s+and\s+(?:then\s+)?|\s+then\s+',inventory)
    if not 1<=len(parts)<=80:raise Unclear('Use a bounded explicit inventory.')
    clause=r'(?i)(a|an|\d{1,6}|'+ '|'.join(NUMBERS) +r')\s+([a-z]+(?:[ -][a-z]+)*)'
    # This reader owns only static inventories. A clause that is not a plain
    # "<count> <noun>" (receive/give/lose/buy events, bare numbers, rates) is a
    # quantity-change task for the event reasoner, not an unsupported inventory.
    if not all(re.fullmatch(clause,part.strip()) for part in parts):return None
    if any(re.search(r'\b(?:of|with|except|without|but|each|per|gave|lost|not)\b',re.fullmatch(clause,part.strip())[2]) for part in parts):
        raise Unclear('Container, event, exclusion or rate clauses need their full quantitative relations.')
    if category is None and wanted is None and asked not in ('items','objects','things'):
        # An unlisted noun is still countable when the inventory names exactly
        # that noun; only category membership needs the explicit vocabulary.
        literal=_plain_singular(asked)
        nouns={_plain_singular(re.fullmatch(clause,part.strip())[2].casefold()) for part in parts}
        if nouns!={literal}:raise Unclear('That category or attribute is outside the explicit counting vocabulary.')
        total=sum(1 if re.fullmatch(clause,part.strip())[1].lower() in ('a','an') else _number(re.fullmatch(clause,part.strip())[1]) for part in parts)
        return total,'number',dict(owner=owner,category=literal,entries=[part.strip() for part in parts],all_clauses_consumed=True,literal_noun=True)
    entries=[]
    for part in parts:
        match=re.fullmatch(clause,part.strip())
        count=1 if match[1].lower() in ('a','an') else _number(match[1])
        noun=match[2].casefold()
        if re.search(r'\b(?:of|with|except|without|but|each|per|gave|lost|not)\b',noun):
            raise Unclear('Container, event, exclusion or rate clauses need their full quantitative relations.')
        key=_singular(noun.split()[-1])
        if (category is not None or wanted is not None) and key not in NOUNS:raise Unclear('I cannot classify '+noun+' from the explicit vocabulary; specify its category.')
        if (category is not None or wanted is not None) and any(w not in {'red','green','yellow','blue','small','large','ripe','fresh'} for w in noun.split()[:-1]):
            raise Unclear('A noun modifier may change its category; specify whether it belongs in the requested count.')
        entries.append(dict(text=part,count=count,noun=noun,unit=key,category=NOUNS.get(key,'unspecified')))
    total=sum(e['count'] for e in entries if (e['category']==category if category is not None else e['unit']==wanted if wanted is not None else True))
    return total,'number',dict(owner=owner,category=category or wanted or 'all items',entries=entries,all_clauses_consumed=True)


def _date(text):
    m=re.fullmatch(r'(?is)Today is (.+?)\.\s*(?:What is the date|What date is(?: it)?)(?:\s+on)?\s+(.+?)\??',text)
    if not m:return None
    raw,offset=m.groups()
    raw=re.sub(r'(?i)(\d)(?:st|nd|rd|th)\b',r'\1',raw).replace(',','')
    p=re.fullmatch(r'(?i)([a-z]+)\s+(\d{1,2})\s+(\d{4})',raw)
    q=re.fullmatch(r'(?i)(\d{1,2})\s+([a-z]+)\s+(\d{4})',raw)
    iso=re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})',raw)
    try:
        if p:base=date(int(p[3]),MONTHS[p[1].lower()],int(p[2]))
        elif q:base=date(int(q[3]),MONTHS[q[2].lower()],int(q[1]))
        elif iso:base=date(*map(int,iso.groups()))
        else:raise Unclear('Use an explicit, unambiguous calendar date and year.')
    except (ValueError,KeyError):raise Unclear('The supplied calendar date is not valid.')
    offset=re.sub(r'(?i)\s+in MM/DD/YYYY$','',offset).strip().lower()
    offset=re.sub(r'(?i)^(?:the date )?','',offset)
    if offset in ('tomorrow','yesterday','today'):days={'tomorrow':1,'yesterday':-1,'today':0}[offset]
    else:
        r=re.fullmatch(r'(\d{1,5}|'+ '|'.join(NUMBERS)+r') (days?|weeks?|hours?) (earlier|later|ago|from today|before today|after today)',offset)
        if not r:raise Unclear('Give one explicit day/week offset; a missing time or relation cannot be inferred.')
        amount=_number(r[1]);unit=r[2].rstrip('s')
        if unit=='hour' and amount%24:raise Unclear('A partial-day offset requires a starting time.')
        days=amount*(7 if unit=='week' else 1) if unit!='hour' else amount//24
        if r[3] in ('earlier','ago','before today'):days=-days
    try:answer=base+timedelta(days=days)
    except (OverflowError,ValueError):raise Unclear('That offset is outside the supported calendar range.')
    return answer.strftime('%m/%d/%Y'),'date',dict(anchor=base.isoformat(),offset_days=days,result=answer.isoformat())


def _order(text,options):
    from .reasoning_order import clean,condition,solve_order,ordering,holds
    from .reasoning_logic import Unparsed
    m=re.fullmatch(r'(?is)([^:.\n]{1,140}):\s*([^:.\n]+)\.\s*(.+)',text)
    if not m or not re.match(r'(?i)^(?:items|objects|participants|on |in |at |there (?:are|stand) )',m[1]):return None
    names=[clean(p.strip()) for p in re.split(r',\s*(?:and\s+)?|\s+and\s+',m[2])]
    if not 2<=len(names)<=8 or len(set(names))!=len(names):raise Unclear('Use two to eight distinct explicitly listed objects.')
    declared=re.search(r'(?i)\b('+ '|'.join(NUMBERS)+r'|\d+)\b',m[1])
    if declared and _number(declared[1])!=len(names):raise Unclear('The stated object count and complete item list disagree.')
    parts=[p.strip() for p in re.split(r'[.!?]\s*|\n+',m[3]) if p.strip()]
    query=None
    if parts and re.match(r'(?i)^(?:which|who|what|give|is|can|could|must)\b',parts[-1]):query=parts.pop()
    def normalise(part):
        part=re.sub(r'(?i)\bto the (left|right) of\b',r'\1 of',part)
        part=re.sub(r'(?i)\bstands\b','is',part)
        return part
    context='Items: '+', '.join(names)+'. '+'. '.join(map(normalise,parts))+'.'
    try:
        _,solutions=solve_order(context)
        if not solutions:raise Unclear('No ordering satisfies every supplied clue.')
        if options:
            if query and not re.fullmatch(r'(?i)which (?:of (?:the )?following )?statements? (?:is true|must be true|is forced by the clues)',query):
                raise Unclear('The choice question requires an unsupported ordering quantifier.')
            selected=[]
            for i,option in enumerate(options):
                constraint=condition(normalise(option).strip(' .'),tuple(names))
                if all(holds(constraint,{name:j for j,name in enumerate(order)}) for order in solutions):selected.append(i)
            if len(selected)!=1:raise Unclear('The complete clues do not entail exactly one of these choices.')
            return selected[0],'choice',dict(objects=names,valid_orders=len(solutions),constraints=parts,all_clauses_consumed=True)
        if query is None:raise Unclear('What position, relation or complete order should I determine?')
        query=normalise(query)
        query=re.sub(r'(?i)^(which|what) \w+ is ',r'\1 is ',query)
        result=ordering(context,query+'?')
        if result['answer'] in ('unknown','conflicting'):raise Unclear('The complete clues do not determine a unique answer.')
        return result['answer'],'order',dict(objects=names,valid_orders=len(solutions),constraints=parts,checked=result)
    except Unparsed as error:raise Unclear('An ordering clause is unsupported: '+str(error))


def _normal(value):
    return str(value).casefold().strip(' .`*').replace(',','')


def reply(text):
    if not isinstance(text,str) or not 0<len(text)<=12000 or not interested(text):return None
    if any(mark in text for mark in ('```','"',"'''",'“','”')):return None
    from .task_context import read
    declared=read(text)
    if declared and declared['kind']=='invalid':
        return dict(route='helper/checked-clarify',response=declared['message'],sources=[],context_owned=True)
    body=declared['context'] if declared and declared['kind']=='choice' else text
    options=declared['options'] if declared and declared['kind']=='choice' else None
    # Keep the existing complete groups/sharing contract with its specialist.
    # It owns typed container capacities, whole/fractional semantics and negatives;
    # the inventory counter must not intercept those as unsupported noun lists.
    from .helper_groups import solve as groups_problem
    if groups_problem(body) is not None:
        return None
    try:
        result=_order(body,options)
        if result is None:
            for parser in (_boolean,_words,_count,_date):
                result=parser(body)
                if result is not None:break
        if result is None:return None
        value,kind,evidence=result
        chosen=None
        if options:
            if kind=='choice':chosen=value
            else:
                matches=[i for i,opt in enumerate(options) if _normal(opt)==_normal(value)]
                if len(matches)!=1:raise Unclear('The checked result does not identify exactly one supplied choice.')
                chosen=matches[0]
            response=chr(65+chosen)+'. '+options[chosen]
        else:response=str(value)
        answer=dict(route='helper/checked-'+kind,response=response,sources=[],exact=True,
            helper_reasoning=dict(kind=kind,value=str(value),exact=True,evidence=evidence),
            context_owned=True,details='Checked from the complete supported task with bounded symbolic operations; no learned answer or network call.')
        if chosen is not None:answer['choice']=chosen
        return answer
    except (Unclear,RecursionError) as error:
        return dict(route='helper/checked-clarify',response=str(error),sources=[],context_owned=True,
                    details='No answer was emitted from an incomplete or inconsistent task.')
