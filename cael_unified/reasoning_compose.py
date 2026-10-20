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


def solve(solver, context, question, depth=0):
    """Answer a question that may need sub-questions. solver(context, question) answers plain ones.
    Returns the solver's result with a 'chain' of (sub-question, answer) steps, or raises Unparsed."""
    context = normalise(context)
    if depth > 3:
        raise Unparsed('The question nests too deeply')
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
        for person in people(context):
            try:
                answer = solver(context, f'Where is {person}?').get('answer', 'unknown')
            except Unparsed:
                continue
            chain.append((f'Where is {person}?', answer))
            if answer.lower() == place:
                found.append(person)
        if room:
            if not chain:
                raise Unparsed('No people to check')
            answer = ' and '.join(found) if found else 'nobody'
            return dict(answer=answer, support=[], chain=chain, composed=True, asked=q)
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


def settle(solver, context, question, chain):
    result = solver(context, question)
    answer = result.get('answer')
    chain.append((question, answer))
    if answer in (None, 'unknown', 'conflicting', 'nobody', 'nothing'):
        raise Unparsed(f'The premises do not settle "{question}"')
    written = re.search(r'(?i)\b' + re.escape(answer) + r'\b', context)   # "daniel" -> "Daniel", as the premises write it
    if written:
        answer = written[0]
        chain[-1] = (question, answer)
    return answer


def chain_text(chain):
    return '\n'.join(f'{i}. {q} → {a}' for i, (q, a) in enumerate(chain, 1))
