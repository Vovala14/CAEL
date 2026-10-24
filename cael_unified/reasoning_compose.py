"""Multi-step reasoning on top of the single-question solvers in reasoning.py.

The solvers each answer one plain question with one family of rules (events, logic, ordering...). Many real
questions need two of them in a row. This layer breaks such a question into smaller ones, asks them in
order, and feeds each answer into the next:

* "Where is the person who has the ball?" -> "Who has the ball?" (Daniel) -> "Where is Daniel?"
* "Who is in the kitchen?" -> "Where is Mary?", "Where is John?" ... for each person, keeping the matches
* "If John goes to the garden, where is John?" -> add the premise to a copy of the facts, then ask
* "Where is Mary? Who has the ball?" -> answer each question against the same facts
* "Mary went to the kitchen, then John went to the garden." -> two events, not one

Every step is recorded in a chain that the reply shows, so the reasoning stays checkable.
"""
import re

from .reasoning_logic import Unparsed

ROLE = r'(?:person|one|man|woman|boy|girl|child|people|animal|someone|somebody)'
POSITION = r'(leftmost|rightmost|oldest|newest|youngest|first|last|cheapest|most expensive|least expensive|second|third|fourth|fifth)'
HOLD = r'(?:has|holds|is holding|is carrying|carries|owns|got|picked up|took|grabbed)'
NOT_PEOPLE = {'The', 'A', 'An', 'If', 'All', 'Every', 'Each', 'Some', 'No', 'Then', 'After', 'Before', 'Afterwards', 'This',
              'That', 'There', 'It', 'He', 'She', 'They', 'Yesterday', 'Today', 'Later', 'Finally', 'Next', 'When', 'Where',
              'Who', 'What', 'Which', 'Is', 'Does', 'Do', 'Can', 'Why', 'How', 'Question', 'Facts', 'Given', 'Suppose'}
PRESENT_TO_PAST = [(r'\bgoes\b', 'went'), (r'\bgo\b', 'went'), (r'\bmoves\b', 'moved'), (r'\bmove\b', 'moved'),
                   (r'\btravels\b', 'travelled'), (r'\bjourneys\b', 'journeyed'), (r'\bruns\b', 'ran'), (r'\bwalks\b', 'walked'),
                   (r'\bpicks up\b', 'picked up'), (r'\bpick up\b', 'picked up'), (r'\bdrops\b', 'dropped'), (r'\bdrop\b', 'dropped'),
                   (r'\bgives\b', 'gave'), (r'\bgive\b', 'gave'), (r'\btakes\b', 'took'), (r'\btake\b', 'took'), (r'\bgets\b', 'got'),
                   (r'\bleaves\b', 'left'), (r'\bputs down\b', 'put down'), (r'\bgrabs\b', 'grabbed'), (r'\bdiscards\b', 'discarded')]


def normalise(context):
    """Split 'Mary went to the kitchen, then John went to the garden' into two premises."""
    return re.sub(r'\s*(?:,\s*(?:and\s+)?then|\s+and\s+then|;\s*then)\s+(?=[A-Z][a-z]+\s+\w)', '. ', context)


def questions(text):
    """(context, [question, ...]) when a scenario ends with two or more questions."""
    parts = re.findall(r'[^.?!\n]+[.?!]?', text)
    asked = []
    while parts and parts[-1].strip().endswith('?'):
        asked.insert(0, parts.pop().strip())
    context = ''.join(parts).strip()
    if len(asked) >= 2 and context:
        return context, asked
    return None


def hypothetical(text):
    """(context, extra premise, question) for '... If John goes to the garden, where is John?'."""
    match = re.search(r'(?is)^(.*?[.!\n])\s*(?:what if|if|suppose(?: that)?|assuming(?: that)?|imagine(?: that)?)\s+(.+?)'
                      r'(?:[,;]\s*(?:then\s+)?|[.?]\s+(?:then\s+)?)((?:where|who|what|is|does|which|how)\b.+?)\s*$', text.strip())
    if not match:
        return None
    premise = match[2].strip(' ,.')
    for pattern, past in PRESENT_TO_PAST:
        premise = re.sub(pattern, past, premise)
    question = re.sub(r'(?i)\bwhere (?:would|will) (\w+) be\b', r'where is \1', match[3])
    question = re.sub(r'(?i)\bwho (?:would|will) have\b', 'who has', question)
    return match[1].strip(), premise, question


def people(context):
    names = []
    for word in re.findall(r'(?:^|[.!?\n]\s*|,\s*then\s+|\band\s+)([A-Z][a-z]+)\b', context):
        if word not in NOT_PEOPLE and word not in names:
            names.append(word)
    return names


def _solve(solver, context, question, depth=0):
    """Answer a question that may need sub-questions. solver(context, question) answers plain ones.
    Returns the solver's result with a 'chain' of (sub-question, answer) steps, or raises Unparsed."""
    context = normalise(context)
    if depth > 3:
        raise Unparsed('The question nests too deeply')
    from .reasoning_order import explicit_order
    if explicit_order(context):
        # The ordering compiler handles ordinal predicates itself. Replacing
        # "the first" with a single guessed item would lose ambiguity.
        return solver(context,question)
    chain = []
    q = question.strip()

    # "the person who has the ball" -> ask who has it first.
    held = re.search(r'(?i)\b(?:the ' + ROLE + r'|whoever|someone|somebody) (?:who|that) ' + HOLD + r' (?:the )?([a-z]+)\b', q)
    if held:
        sub = f'Who has the {held[1]}?'
        name = settle(solver, context, sub, chain)
        q = q[:held.start()] + name + q[held.end():]

    # "who is in the kitchen" / "the person in the kitchen": ask where everyone is.
    room = re.fullmatch(r'(?i)\s*who (?:is|was) (?:in|at) (?!(?:the )?(?:middle|centre|center|front|back|end|start|left|right)\b)(?:the )?([a-z ]+?)\s*\??\s*', q)
    inside = re.search(r'(?i)\b(?:the ' + ROLE + r'|whoever) (?:who (?:is|was) )?(?:in|at) (?:the )?([a-z]+)\b', q)
    if room or inside:
        place = (room or inside)[1].strip().lower()
        found = []
        unknown = []
        support = set()
        for person in people(context):
            # A failed parse is not evidence of absence. Keep the whole
            # scenario unsupported instead of silently dropping that person.
            result = solver(context, f'Where is {person}?')
            answer = result.get('answer', 'unknown')
            support.update(result.get('support',[]))
            chain.append((f'Where is {person}?', answer))
            if answer == 'conflicting':
                return dict(answer='conflicting',support=sorted(support),chain=chain,composed=True)
            if answer in ('unknown','maybe',None):
                unknown.append(person)
            if isinstance(answer,str) and answer.lower() == place:
                found.append(person)
        if unknown:
            result = dict(answer='unknown',support=sorted(support),chain=chain,composed=True,
                          known_matches=found,unresolved_people=unknown)
            if room and found:
                result['verdict_text'] = (' and '.join(found)+(' are' if len(found)>1 else ' is')+' in the '+place+'. '
                    'The premises do not determine whether the other tracked people are there.')
            return result
        if room:
            if not chain:
                raise Unparsed('No people to check')
            answer = ' and '.join(found) if found else 'nobody'
            result = dict(answer=answer, support=sorted(support), chain=chain, composed=True, asked=q)
            if not found:result['verdict_text']='None of the tracked people is in the '+place+'.'
            return result
        if len(found) != 1:
            return dict(answer='unknown', support=[], chain=chain, composed=True)
        q = q[:inside.start()] + found[0] + q[inside.end():]

    # "the oldest one" inside a larger question -> ask the ordering first.
    position = re.search(r'(?i)\bthe ' + POSITION + r'(?: one| item| object| person| car| house| book)?\b', q)
    if position and not re.fullmatch(r'(?i)\s*(?:which|who|what)(?: one| item| object)? (?:is|was) the .+', q):
        sub = f'Which is the {position[1].lower()}?'
        item = settle(solver, context, sub, chain)
        q = q[:position.start()] + item + q[position.end():]

    if not chain:
        result = solver(context, q)
        return result
    result = dict(solver(context, q))
    chain.append((q, result.get('answer')))
    result['chain'] = chain
    result['composed'] = True
    result['asked'] = q
    return result


class Unsettled(Exception):
    """A parsed sub-question whose answer is missing or contradictory."""
    def __init__(self,result,chain):
        self.result = dict(answer='conflicting' if result.get('answer')=='conflicting' else 'unknown',
                           support=result.get('support',[]),family=result.get('family','state'),
                           chain=list(chain),composed=True,unresolved_step=chain[-1][0])


def solve(solver, context, question, depth=0):
    try:
        return _solve(solver,context,question,depth)
    except Unsettled as error:
        return error.result


def settle(solver, context, question, chain):
    result = solver(context, question)
    answer = result.get('answer')
    chain.append((question, answer))
    if answer in (None, 'unknown', 'conflicting', 'nobody', 'nothing'):
        raise Unsettled(result,chain)
    written = re.search(r'(?i)\b' + re.escape(answer) + r'\b', context)   # "daniel" -> "Daniel", as the premises write it
    if written:
        answer = written[0]
        chain[-1] = (question, answer)
    return answer


def chain_text(chain):
    return '\n'.join(f'{i}. {q} → {a}' for i, (q, a) in enumerate(chain, 1))
