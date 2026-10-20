"""An authored bounded constraint solver, evaluated separately from training data."""
from functools import lru_cache
from itertools import permutations
import re
from .reasoning_logic import Unparsed, sentences

ORDINAL = {'first':0,'second':1,'third':2,'fourth':3,'fifth':4,'sixth':5,'seventh':6,'eighth':7}


def clean(text):
    return re.sub(r'^(?:the|a|an)\s+', '', text.lower().strip(' .'))


def condition(statement, names):
    lower = statement.lower().strip(' .')
    found=[]
    for name in sorted(names,key=len,reverse=True):
        match=re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',lower)
        if match:
            found.append((name,match.start()))
    # Avoid short overlapping entity names being treated as extra entities.
    entities = []
    occupied = []
    for name,pos in found:
        if not any(left <= pos < right for left,right in occupied):
            entities.append((name,pos));occupied.append((pos,pos+len(name)))
    entities.sort(key=lambda row:row[1])
    if len(entities) == 2:
        a,b = entities[0][0],entities[1][0]
        between = lower[entities[0][1]+len(a):entities[1][1]].strip()
        forward = ('left of','before','above','older than','more expensive than')
        backward = ('right of','after','below','newer than','less expensive than','cheaper than')
        if any(phrase in between for phrase in forward):
            return ('before',a,b)
        if any(phrase in between for phrase in backward):
            return ('before',b,a)
        raise Unparsed('Unsupported ordering relation')
    if len(entities) != 1:
        raise Unparsed('No unique ordering subject')
    name,pos = entities[0]
    ending = lower[pos+len(name):].strip()
    n = len(names)
    if re.search(r'\b(?:leftmost|oldest|most expensive|first)\b', ending) and not re.search(r'\b(?:second|third|fourth|fifth|sixth|seventh)\b', ending):
        return ('at',name,0)
    if re.search(r'\b(?:rightmost|newest|least expensive|cheapest|last)\b', ending) and not re.search(r'\b(?:second|third|fourth|fifth|sixth|seventh)\b', ending):
        return ('at',name,n-1)
    ordinal = next((value for word,value in ORDINAL.items() if re.search(r'\b'+word+r'\b',ending)), None)
    if ordinal is not None:
        reverse = any(cue in ending for cue in ('from the right','newest','least expensive','cheapest','last'))
        return ('at',name,n-1-ordinal if reverse else ordinal)
    raise Unparsed('Unrecognized ordinal')


@lru_cache(maxsize=64)
def solve_order(context):
    parts = sentences(context)
    if not parts or ':' not in parts[0]:
        raise Unparsed('An ordering puzzle needs an explicit item list')
    items = re.sub(r'\s+and\s+', ',', parts[0].split(':',1)[1],flags=re.I)
    names = tuple(clean(item) for item in items.split(',') if clean(item))
    if len(set(names)) != len(names) or not 2 <= len(names) <= 8:
        raise Unparsed('Use 2 to 8 distinct items')
    constraints = [condition(part,names) for part in parts[1:]]
    solutions = []
    for order in permutations(names):
        positions = {name:i for i,name in enumerate(order)}
        if all(positions[a] < positions[b] if op == 'before' else positions[a] == b for op,a,b in constraints):
            solutions.append(order)
            if len(solutions)>4096:
                raise Unparsed('Too many possible orders; add more ordering clues')
    return names,tuple(solutions)


def ordering(context, question):
    names,solutions = solve_order(context)
    if not solutions:
        return dict(answer='conflicting',support=[],depth=0)
    question = question.lower().strip(' ?.!.')
    if question in ('what is the order','give the order','what is the complete order'):
        return dict(answer=', '.join(solutions[0]) if len(solutions)==1 else 'unknown',support=list(range(1,len(sentences(context))+1)),depth=len(names))
    question = re.sub(r'^(?:which|who|what)(?: one| item| object)? (?:is |finished )?', '', question)
    if re.fullmatch(r'(?:in )?(?:the )?(?:middle|centre|center)(?: one)?', question) and len(names) % 2:
        possible = {order[len(names) // 2] for order in solutions}
        return dict(answer=next(iter(possible)) if len(possible) == 1 else 'unknown', support=list(range(1, len(sentences(context)) + 1)), depth=len(names))
    query = condition(names[0] + ' is ' + question,names)
    if query[0] != 'at':
        raise Unparsed('Ask for an ordinal position')
    index = query[2]
    possible = {order[index] for order in solutions}
    return dict(answer=next(iter(possible)) if len(possible)==1 else 'unknown',support=list(range(1,len(sentences(context))+1)),depth=len(names))
