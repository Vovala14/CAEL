"""Conservative primitive semantics for single-state integer stream programs.

This is an authored specification reader. It creates a new expression graph;
it contains no complete Python algorithm bodies or task-name solution table.
Ambiguous or unsupported clauses produce a clarification, not guessed code.
"""
import keyword
import re

from .state_search import Program, S, X, ZERO, ONE, node, OutsideDomain


class Unclear(ValueError):
    pass


def predicates(text):
    """Interpret selection adjectives and integer comparison relations."""
    found=[]
    for word, op, number in [('positive','>',0),('negative','<',0),('nonnegative','>=',0),
                              ('nonpositive','<=',0),('nonzero','!=',0),('even','%',2),('odd','odd',2)]:
        if re.search(r'\b'+word+r'\b',text):
            if op in {'%','odd'}:
                found.append(node('==' if op=='%' else '!=',node('%',X,node('const',2)),ZERO))
            else:found.append(node(op,X,node('const',number)))
    for m in re.finditer(r'\b(greater than|above|less than|below|at least|at most|divisible by)\s+(-?\d{1,3})\b',text):
        number=int(m[2])
        if abs(number)>100:raise Unclear('Comparison constants must be within ±100.')
        if m[1]=='divisible by':
            if not 1<=number<=10:raise Unclear('Divisors must be between 1 and 10.')
            found.append(node('==',node('%',X,node('const',number)),ZERO))
        else:
            op={'greater than':'>','above':'>','less than':'<','below':'<','at least':'>=','at most':'<='}[m[1]]
            found.append(node(op,X,node('const',number)))
    if not found:return None
    if len(found)>3:raise Unclear('Please simplify the selection condition.')
    if re.search(r'\band\b',text) and re.search(r'\bor\b',text):
        raise Unclear('Specify how AND and OR are grouped, or give contrasting examples.')
    result=found[0]
    connector='or' if re.search(r'\bor\b',text) else 'and'
    for other in found[1:]:result=node(connector,result,other)
    return result


def plan(description):
    t=' '.join(description.lower().split()).strip().rstrip('.')
    if len(t)>1200:raise Unclear('Please shorten the specification.')
    # These change order, identity, state model or implementation requirements.
    if re.search(r'\b(?:except|unless|alternat\w*|every other|pairwise|nested|recursive|'
                 r'recursion|without|do not|in[- ]place|sorted|sort|unique|distinct|'
                 r'duplicates?|files?|async|threads?|numpy|pandas|median|average|mean|'
                 r'skip\w*|exclude\w*|remov\w*|drop\w*|discard\w*|dict(?:ionary)?|'
                 r'tuple|strings?|floats?|decimals?|parameters?|arguments?)\b',t):
        raise Unclear('That modifier is outside the single-state planner. Give contrasting input/output examples or simplify the requirements.')
    if not re.search(r'\b(?:numbers?|integers?|list|array|values?|stream)\b',t):return None
    operation=[]
    if re.search(r'\bsum\b|\btotal\b',t):operation.append('+')
    if re.search(r'\bproduct\b',t):operation.append('*')
    if re.search(r'\bcount\b',t):operation.append('count')
    if re.search(r'\bmaximum\b|\blargest\b',t):operation.append('max')
    if re.search(r'\bminimum\b|\bsmallest\b',t):operation.append('min')
    # "longest consecutive ..." specifies a count at each step and a maximum
    # over those states. Other reducers continue to compose independently.
    consecutive=bool(re.search(r'\bconsecutive\b|\bstreak\b',t))
    longest=bool(re.search(r'\blongest\b',t))
    if longest:
        if not consecutive:raise Unclear('Longest by what measure? Specify the per-item update.')
        operation.append('count')
    if len(set(operation))!=1:
        raise Unclear('Specify one accumulator operation: sum, product, count, maximum or minimum.')
    operation=operation[0]
    projection='max' if longest else 'scan' if re.search(r'\brunning\b|\bcumulative\b|\bprefix\b|\bat each step\b',t) else 'last'
    initial_match=re.search(r'\b(?:start(?:ing)? (?:at|with|from)|initial state(?: is| of)?)\s+(-?\d{1,3})\b',t)
    initial=int(initial_match[1]) if initial_match else 1 if operation=='*' else 0
    if abs(initial)>100:raise Unclear('Initial state must be within ±100.')
    if operation in {'max','min'} and initial_match is None:
        raise Unclear('Specify the initial state for a running minimum or maximum, including the empty-input result.')
    # A reset condition belongs to control flow, not to the selection predicate.
    reset=None
    reset_match=re.search(r'\breset(?:ting)?(?: (?:the )?(?:state|total|accumulator))?\s+(?:to\s+(-?\d{1,3})\s+)?(?:on|when(?: (?:a )?(?:value|number) is)?)\s+(zero|negative|positive|even|odd)\b',t)
    if 'reset' in t and reset_match is None:
        raise Unclear('Specify the reset value and condition, for example reset to 0 on zero.')
    selection_text=t
    if reset_match:
        reset_word=reset_match[2]
        reset_pred=node('==',X,ZERO) if reset_word=='zero' else predicates(reset_word)
        reset_value=int(reset_match[1]) if reset_match[1] is not None else initial
        if abs(reset_value)>100:raise Unclear('Reset state must be within ±100.')
        reset=(reset_pred,node('const',reset_value))
        selection_text=t[:reset_match.start()]+t[reset_match.end():]
    eligible=predicates(selection_text)
    if consecutive and eligible is None:
        raise Unclear('Which values continue the consecutive run? Give a sign, parity or comparison condition.')
    if consecutive and operation!='count':
        raise Unclear('Specify whether a non-matching value resets or skips the accumulator.')
    term=X
    transforms=[]
    if re.search(r'\bsquares?\b|\bsquared\b',t):transforms.append(node('*',X,X))
    if re.search(r'\bcubes?\b|\bcubed\b',t):transforms.append(node('*',node('*',X,X),X))
    if re.search(r'\babsolute\b',t):transforms.append(node('abs',X))
    if re.search(r'\bdouble(?:d)?\b',t):transforms.append(node('*',X,node('const',2)))
    scale=re.search(r'\bmultipl(?:y|ied) (?:each (?:number|value) )?by\s+(-?\d{1,3})\b',t)
    if scale:
        factor=int(scale[1])
        if abs(factor)>100:raise Unclear('Scale factor must be within ±100.')
        transforms.append(node('*',X,node('const',factor)))
    if len(transforms)>1:raise Unclear('Specify the order of the transformations or give examples.')
    if transforms:term=transforms[0]
    if operation=='count':
        if transforms:raise Unclear('Does the transformation happen before the count condition? Give examples.')
        term=ONE
    # Selection always describes original input values. Explicit alternatives
    # need a different plan and are refused instead of silently re-ordered.
    if re.search(r'\b(?:after|before|then|until|stop|break|at most \d+ (?:items|values)|last \d+|first \d+)\b',t):
        raise Unclear('That ordering or stopping rule needs contrasting examples; it is not supported by this description planner.')
    update=node('+' if operation=='count' else operation,S,term)
    if eligible is not None:
        update=node('if',eligible,update,node('const',initial) if consecutive else S)
    if reset is not None:
        if consecutive:raise Unclear('Use either a consecutive-run rule or an explicit reset rule, with examples for their interaction.')
        update=node('if',reset[0],reset[1],update)
    return Program(initial,update,projection)


def reply(description):
    try:p=plan(description)
    except Unclear as error:
        return dict(response=str(error),route='chat/code-state-clarify',sources=[],
                    details='The stateful specification has unsupported or ambiguous semantics. No code was emitted.')
    if p is None:return None
    match=re.search(r'\b(?:named|called)\s+`?([a-zA-Z_]\w*)',description,re.I)
    name=match[1] if match else 'process_stream'
    if keyword.iskeyword(name) or name.startswith('_'):
        return dict(response='Choose a public Python function name that is not a reserved word.',route='chat/code-state-clarify',sources=[])
    try:code=p.render(name)
    except OutsideDomain:
        return dict(response='Choose a public Python function name that does not shadow a required built-in.',route='chat/code-state-clarify',sources=[])
    return dict(response=f'```python\n{code}```\n'
                f'I built this from an initial state of `{p.initial}`, per-item update `{p.update.source()}`, '
                f'and `{p.projection}` output. Selection tests refer to the original input value; '
                'a running result includes one state per input item. '
                'Domain: at most 40 integer inputs, each within ±1,000,000; intermediate states within ±1,000,000,000,000. '
                'This is a parsed specification, so please confirm those semantics and test your own inputs.',
                route='chat/code-state-planned',sources=[],
                details='A non-neural primitive specification reader constructed an integer-state expression graph and emitted a new loop. '
                        'No complete function solution was retrieved. This path does not infer behavior from examples or prove natural-language intent.')
