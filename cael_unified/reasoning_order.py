"""Bounded integer constraints over one explicit, tie-free ordering.

Checks all permutations, distinguishes possibility from necessity, and requires
complete surface clauses. No learned weights, network calls or benchmark data.
"""
from functools import lru_cache
from itertools import permutations
import re
from .reasoning_logic import Unparsed, sentences

ORDINAL = dict(zip('first second third fourth fifth sixth seventh eighth'.split(), range(8)))
LIST = r'(?:items|people|objects|participants|runners|books|cars|order)\s*:'


def clean(text):
    return re.sub(r'^(?:the|a|an)\s+', '', text.lower().strip(' .'))


def explicit_order(text):
    text = re.sub(r'(?i)^\s*(?:facts|premises|given|suppose|scenario|context)\s*:\s*', '', text)
    return bool(re.match(r'(?i)^\s*'+LIST, text))


def ordinal(text, n):
    """Parse a complete position phrase, never a keyword in an arbitrary clause."""
    text = re.sub(r'^the\s+', '', text.strip())
    if text in ('leftmost', 'oldest', 'most expensive', 'first'):return 0
    if text in ('rightmost', 'newest', 'youngest', 'least expensive', 'cheapest', 'last'):return n-1
    m = re.fullmatch(r'('+ '|'.join(ORDINAL) +r')(?: (?:from (?:the )?(left|right)|(?:to )?(oldest|newest|youngest|most expensive|least expensive|cheapest|last)))?', text)
    if not m:raise Unparsed('Unrecognized ordinal position')
    index = ORDINAL[m[1]]
    if index >= n:raise Unparsed('Position is outside the listed order')
    reverse = (m[2] or m[3]) in ('right', 'newest', 'youngest', 'least expensive', 'cheapest', 'last')
    return n-1-index if reverse else index


def condition(statement, names):
    """Compile an entire statement to an integer predicate tuple."""
    lower = statement.lower().strip(' .')
    entity = r'(?:the )?('+'|'.join(re.escape(name) for name in sorted(names,key=len,reverse=True))+r')'
    m = re.fullmatch(entity+r' (?:is |comes |finished )?(not )?(.+)', lower)
    if not m:raise Unparsed('Unsupported ordering subject or clause')
    a, negative, tail = m.groups()
    neg = 'not_' if negative else ''
    relation = re.fullmatch(r'(immediately |directly )?(before|after|left of|right of|above|below|older than|younger than|newer than|more expensive than|less expensive than|cheaper than) '+entity, tail)
    if relation:
        immediate, word, b = relation.groups()
        if word in ('after','right of','below','younger than','newer than','less expensive than','cheaper than'):a,b = b,a
        return (neg+('immediately_before' if immediate else 'before'),a,b)
    adjacent = re.fullmatch(r'(?:next to|adjacent to) '+entity, tail)
    if adjacent:return (neg+'adjacent',a,adjacent[1])
    between = re.fullmatch(r'between '+entity+r' and '+entity, tail)
    if between:return (neg+'between',a,between[1],between[2])
    return (neg+'at',a,ordinal(tail,len(names)))


def axes(text):
    """Do not turn an age ranking into a price or spatial inference."""
    cues = {
        'horizontal':r'left of|right of|leftmost|rightmost|from (?:the )?(?:left|right)',
        'vertical':r'above|below',
        'age':r'older than|younger than|newer than|oldest|youngest|newest',
        'price':r'more expensive|less expensive|most expensive|least expensive|cheaper than|cheapest',
    }
    return {axis for axis,pattern in cues.items() if re.search(r'\b(?:'+pattern+r')\b',text.lower())}


def dimensions(text, names):
    pattern = r'(?<!\w)(?:'+'|'.join(re.escape(n) for n in sorted(names,key=len,reverse=True))+r')(?!\w)'
    return axes(re.sub(pattern,'item',text,flags=re.I))


def holds(constraint, positions):
    op,a,*rest = constraint
    negative = op.startswith('not_')
    if negative:op = op[4:]
    x = positions[a]
    b = rest[0]
    if op == 'at':value = x == b
    elif op == 'before':value = x < positions[b]
    elif op == 'immediately_before':value = x+1 == positions[b]
    elif op == 'adjacent':value = abs(x-positions[b]) == 1
    elif op == 'between':value = min(positions[b],positions[rest[1]]) < x < max(positions[b],positions[rest[1]])
    else:raise Unparsed('Unsupported ordering predicate')
    return not value if negative else value


@lru_cache(maxsize=16)
def solve_order(context):
    if len(context)>40000 or len(sentences(context))>400:raise Unparsed('Keep the scenario within 400 premises and 40,000 characters')
    parts = sentences(context)
    if not parts or ':' not in parts[0]:raise Unparsed('An ordering puzzle needs an explicit item list')
    items = re.sub(r'\s+and\s+', ',', parts[0].split(':',1)[1],flags=re.I)
    names = tuple(clean(item) for item in items.split(',') if clean(item))
    if len(set(names)) != len(names) or not 2 <= len(names) <= 8:raise Unparsed('Use 2 to 8 distinct items')
    if any(not re.fullmatch(r'[\w]+(?:[ -][\w]+)*',name) for name in names):raise Unparsed('Unsupported item name')
    constraints = tuple(condition(part,names) for part in parts[1:])
    if len(dimensions(' '.join(parts[1:]),names))>1:
        raise Unparsed('Use one ordering dimension; age, price and spatial orders are separate')
    solutions = []
    for order in permutations(names):
        positions = {name:i for i,name in enumerate(order)}
        if all(holds(c,positions) for c in constraints):solutions.append(order)
    return names,tuple(solutions)


def proposition(question, names):
    """Return (quantifier, predicate); a plain assertion query is open-world."""
    for pattern,quantifier in (
        (r'(?:can|could) (.+?) be (.+)', 'possible'),
        (r'is it possible (?:that|for) (.+?)(?: to be| is) (.+)', 'possible'),
        (r'must (.+?) be (.+)', 'necessary'),
        (r'does (.+?) have to be (.+)', 'necessary'),
        (r'is (.+?) (.+)', 'entailed'),
        (r'prove:\s*(.+?) is (.+)', 'entailed'),
    ):
        m = re.fullmatch(pattern,question)
        if m:return quantifier,condition(m[1]+' is '+m[2],names)
    raise Unparsed('Ask for a position, relation, possibility or necessity')


def ordering(context, question):
    names,solutions = solve_order(context)
    # Examine parsed clue/query tails only, so item names such as "Oldest Oak"
    # cannot create a ranking dimension by themselves.
    clue_axes = dimensions(' '.join(sentences(context)[1:]),names)
    question_axes = dimensions(question,names)
    if question_axes and question_axes != clue_axes:
        raise Unparsed('The question uses an ordering dimension not established by the clues')
    result = dict(support=list(range(1,len(sentences(context))+1)),depth=len(names),
                  valid_orders=len(solutions),assumptions='One linear order of distinct listed items; no ties.')
    if not solutions:return dict(result,answer='conflicting',order_explanation='No order satisfies all the stated clues.')
    q = question.lower().strip(' ?.!.')
    if q in ('what is the order','give the order','what is the complete order'):
        answer = ', '.join(solutions[0]) if len(solutions)==1 else 'unknown'
        result.update(answer=answer,examples=[list(s) for s in solutions[:2]])
    elif re.match(r'^(?:which|who|what)\b',q):
        tail = re.sub(r'^(?:which|who|what)(?: one| item| object| person)? (?:is |finished |comes )?', '', q)
        if re.fullmatch(r'(?:in )?(?:the )?(?:middle|centre|center)(?: one)?',tail):
            if len(names)%2 == 0:raise Unparsed('An even order has two middle positions')
            index = len(names)//2
        else:index = ordinal(tail,len(names))
        possible = {order[index] for order in solutions}
        result['answer'] = next(iter(possible)) if len(possible)==1 else 'unknown'
        first = solutions[0]
        other = next((s for s in solutions if s[index]!=first[index]),None)
        result['examples'] = [list(first)]+([list(other)] if other else [])
    else:
        quantifier,predicate = proposition(q,names)
        witness = counter = None
        for order in solutions:
            if holds(predicate,{name:i for i,name in enumerate(order)}):
                if witness is None:witness = order
            elif counter is None:counter = order
        if quantifier == 'possible':
            answer = 'true' if witness else 'false'
            verdict = 'Yes, at least one valid order allows that.' if witness else 'No valid order allows that.'
        elif quantifier == 'necessary':
            answer = 'true' if counter is None else 'false'
            verdict = 'Yes, that holds in every valid order.' if counter is None else 'No, it is not required; a valid order makes it false.'
        else:
            answer = 'true' if counter is None else 'false' if witness is None else 'unknown'
            verdict = {'true':'Yes, that holds in every valid order.',
                       'false':'No, every valid order makes that false.',
                       'unknown':'The clues allow both outcomes, so that is not determined.'}[answer]
        result.update(answer=answer,quantifier=quantifier,verdict_text=verdict,
                      witness=list(witness) if witness else None,counterexample=list(counter) if counter else None)
    count = len(solutions)
    result['order_explanation'] = f'Checked all {count} valid order'+('s' if count!=1 else '')+'. '+result['assumptions']
    return result


def evidence_text(result):
    lines = [result['order_explanation']]
    if result.get('witness'):lines.append('Example allowing it: '+' → '.join(result['witness'])+'.')
    if result.get('counterexample'):lines.append('Example making it false: '+' → '.join(result['counterexample'])+'.')
    for order in result.get('examples',[]):lines.append('Valid order: '+' → '.join(order)+'.')
    return '\n'.join(lines)


def chat_scope(text, messages):
    """Only explicit ordering tasks and contiguous ordering follow-ups get priority."""
    if explicit_order(text):return True
    from .reasoning_chat import context_from_history
    context,_ = context_from_history(messages)
    if not explicit_order(context):return False
    if re.match(r'(?i)^\s*(?:add|also|update|forget|clear|reset)\b',text):return True
    from .reasoning_chat import WHY
    if WHY.fullmatch(text):return True
    try:ordering(context,text)
    except Unparsed:return False
    return True
