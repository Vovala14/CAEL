"""Conservative MC adapters to existing bounded symbolic/helper engines.

Only complete, explicit computations/premises are eligible. No benchmark IDs,
answer memories, learned weights, external models or network calls. Abstract
alphanumeric identifiers are bound injectively to alphabetic parser symbols.
Unsupported input or non-unique answer matches fall through unchanged.
"""
from fractions import Fraction
import re

from .helper import calculate
from .reasoning import Reasoner
from .reasoning_logic import Unparsed, sentences
from .reasoning_order import ordering
from .symbolic_choice import reply as state_or_proof
from .verify import check_arithmetic, Unchecked

ATOM = r'[A-Za-z][A-Za-z0-9_]*'
NUMERIC = re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:/[+-]?\d+)?')
TRUTH = {'true':'true', 'yes':'true', 'false':'false', 'no':'false',
         'unknown':'unknown', 'undetermined':'unknown', 'not enough information':'unknown',
         'inconsistent':'conflicting', 'conflicting':'conflicting', 'both true and false':'conflicting'}


def key(value):
    return value.strip().rstrip(' .?!').casefold()


def chosen(options, value, family, proof):
    matches=[i for i,option in enumerate(options) if key(option)==key(value)]
    if len(matches)!=1:
        return None
    index=matches[0]
    return dict(route='chat/choice-helper-'+family, choice=index,
        response=f'{"ABCD"[index]}. {options[index]}', sources=[], reasoning=proof,
        details='Matched exactly one option to the existing bounded '+family+
                ' engine. Fully parsed explicit input; no internet or neural model.')


def arithmetic(context, options):
    text=context.strip()
    if '\n' in text or len(text)>350:
        return None
    text=re.sub(r'(?i)^(?:using|with) (?:standard|ordinary|exact) arithmetic,\s*','',text)
    text=re.sub(r'(?i)\.\s*(?:what is the (?:result|answer|value)|give the result)\?\s*$','',text)
    text=re.sub(r'(?i)^evaluate\s+','Calculate ',text).rstrip(' .?')
    result=calculate(text)
    if not result or result.get('route')!='helper/arithmetic' or not result.get('exact'):
        return None
    # Exact full numeric options only; never match a number inside a proposition.
    if not all(NUMERIC.fullmatch(option.strip()) for option in options):
        return None
    try:
        verified=check_arithmetic(text,result)
        if verified['status']!='verified':
            return None
        value=Fraction(result['response'].rsplit(' = ',1)[1])
        matches=[i for i,option in enumerate(options) if Fraction(option.strip())==value]
    except (ValueError, ZeroDivisionError, Unchecked):
        return None
    if len(matches)!=1:
        return None
    index=matches[0]
    return dict(route='chat/choice-helper-arithmetic', choice=index,
        response=f'{"ABCD"[index]}. {options[index]}', sources=[],
        verification=verified, reasoning=dict(family='arithmetic',derivation=result['response'],internet_used=False),
        details=result['response']+'\n'+verified['check']+'\nExact rational option matching; no language-score override without a unique checked result.')


def alphabet(index):
    value=''
    while True:
        value=chr(ord('a')+index%26)+value
        index=index//26-1
        if index<0:
            return value


def bind(context, options):
    """Alpha-rename identifiers, keeping every atom distinct and reversible."""
    all_text=context+'\n'+'\n'.join(options)
    tokens=set(re.findall(ATOM,all_text.casefold()))
    prefix='opaque'
    while any(word.startswith(prefix) for word in tokens):
        prefix='z'+prefix
    names=sorted(word for word in tokens if re.search(r'[0-9_]',word))
    mapping={name:prefix+alphabet(i)+'q' for i,name in enumerate(names)}
    def replace(text):
        return re.sub(ATOM,lambda m:mapping.get(m[0].casefold(),m[0]),text)
    return replace(context),[replace(option) for option in options],mapping


def classification(context, options, reasoner):
    # The quote delimits the full proposition; remainder is a validated answer
    # instruction, not silently ignored prose or a guessed question boundary.
    match=re.fullmatch(r'''(?is)(.+?)(?:\n|\.\s+)(?:(?:under|using) open[- ]world (?:logic|assumptions),?\s*)?(?:is|classify)\s+(['"])(.+?)\2\s+(?:as\s+)?true,\s*false,\s*or\s*(?:unknown|undetermined)\?\s*(?:No fact implies its converse\.)?''',context)
    if not match:
        return None
    premises,proposition=match[1],match[3]
    result=reasoner.solve(premises,proposition)
    if result.get('inferred') or result.get('family') not in ('logic','logic-cases'):
        return None
    answer=result['answer']
    matches=[i for i,option in enumerate(options) if TRUTH.get(key(option))==answer]
    if len(matches)!=1:
        return None
    return matches[0],dict(result,internet_used=False)


def relative_order(context, options):
    """Bind a complete set of strict precedence premises to the existing CSP.

    No assumption about an unseen item is made: every answer option must be a
    listed premise entity. Cycles, ties and incomplete orders remain unproved.
    """
    parts=sentences(context)
    if len(parts)<2:
        return None
    question=parts[-1].strip(' ?.')
    match=re.fullmatch(r'(?i)(?:which|what) (?:item|object|entry) (?:comes|is) (first|last)',question)
    if match is None:
        return None
    names=[]; constraints=[]
    for premise in parts[:-1]:
        relation=re.fullmatch(rf'(?i)({ATOM}) (?:comes |is )?(before|after) ({ATOM})',premise)
        if not relation or relation[1].casefold()==relation[3].casefold():
            return None
        first,last=relation[1].casefold(),relation[3].casefold()
        names.extend((first,last))
        constraints.append(f'{first} is {relation[2].lower()} {last}')
    names=list(dict.fromkeys(names))
    if not 2<=len(names)<=8 or len(constraints)>28 or any(key(option) not in names for option in options):
        return None
    result=ordering('Items: '+', '.join(names)+'. '+'. '.join(constraints), 'Which item is '+match[1].lower()+'?')
    if result['answer'] in ('unknown','conflicting'):
        return None
    return result


def reply(context, options, reasoner=None):
    if not isinstance(context,str) or not 0<len(context)<=12000 or not 2<=len(options)<=4:
        return None
    if not all(isinstance(option,str) and 0<len(option)<=500 for option in options):
        return None
    answer=arithmetic(context,options)
    if answer:
        return answer
    # Empty/unrecognized option vocabularies do not justify open-world answers.
    if not re.search(r'(?i)\b(?:is|every|all|went|moved|holds?|has|gives?|hands?|before|after)\b',context):
        return None
    normalized,choices,mapping=bind(context,options)
    reasoner=reasoner or Reasoner()
    if not reasoner.model:
        return None
    try:
        classified=classification(normalized,choices,reasoner)
        if classified:
            index,proof=classified
            return dict(route='chat/choice-helper-logic',choice=index,
                response=f'{"ABCD"[index]}. {options[index]}',sources=[],reasoning=proof,
                details='Existing open-world proof/case engines classified the complete quoted proposition. No absent fact was treated as false.',
                symbol_bindings=mapping)
        ordered=relative_order(normalized,choices)
        if ordered:
            result=chosen(choices,ordered['answer'],'ordering',dict(ordered,family='ordering',internet_used=False))
            if result:
                result.update(response=f'{"ABCD"[result["choice"]]}. {options[result["choice"]]}',symbol_bindings=mapping)
                return result
        # Chronology annotations state the semantics already used by WorldCA;
        # unknown headers/premises are never deleted to force a parse.
        state=re.sub(r'(?i)^(?:Events are listed from earliest to latest\.|Events in chronological order:|Chronological events:)\s*','',normalized)
        if state==normalized and not mapping:
            return None  # Existing natural-name bridge runs next, unchanged.
        result=state_or_proof(state,choices,reasoner)
        if result:
            result.update(route='chat/choice-helper-'+result['reasoning']['family'],
                response=f'{"ABCD"[result["choice"]]}. {options[result["choice"]]}',symbol_bindings=mapping)
            return result
    except Unparsed:
        return None
    return None
