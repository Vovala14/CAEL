"""More story reasoning: pronouns, pairs, time order, induction, 2-D positions, compass relations, motivations.

All authored algorithms over the stated premises, except the motivation table, which
is counted from the bAbI task 20 training split (see train_motivations). Each solver
raises Unparsed when the premises are not in its form, so the Reasoner can try the next.
"""
from collections import Counter, defaultdict
import json
import re

from .reasoning_logic import Unparsed, sentences

MOTION = r'(?:moved|went|journeyed|travelled|traveled|walked|ran|headed|went back|journeyed back|travelled back|moved back)'
PRONOUN_SINGLE = r'\b(?:he|she)\b'
TIME_ORDER = {'yesterday': 0, 'this morning': 1, 'this afternoon': 2, 'this evening': 3}


# ---------------------------------------------------------------- rewriting for the event engine

def rewrite(context):
    """'A and B went to X. Then they moved to Y. Afterwards he ...' -> one person per simple sentence.

    Returns (rewritten context, index map from rewritten sentence to original premise number).
    """
    out, origin = [], []
    last_people = []
    for index, statement in enumerate(sentences(context), 1):
        text = statement.strip()
        lowered = text.lower()
        pair = re.match(r'([A-Z][a-z]+)\s+and\s+([A-Z][a-z]+)\s+(.*)', text)
        lead = re.match(r'(?i)^(?:then|afterwards|after that|following that|later|next)\s*,?\s*', text)
        body = text[lead.end():] if lead else text
        if pair:
            people = [pair.group(1), pair.group(2)]
            for person in people:
                out.append(f'{person} {pair.group(3)}')
                origin.append(index)
            last_people = people
            continue
        they = re.match(r'(?i)they\s+(.*)', body)
        if they and last_people:
            for person in last_people:
                out.append(f'{person} {they.group(1)}')
                origin.append(index)
            continue
        single = re.match(r'(?i)(he|she)\s+(.*)', body)
        if single and last_people:
            out.append(f'{last_people[-1]} {single.group(2)}')
            origin.append(index)
            continue
        subject = re.match(r'([A-Z][a-z]+)\b', body)
        if subject and subject.group(1).lower() not in ('the', 'a', 'an', 'this', 'yesterday', 'then'):
            last_people = [subject.group(1)]
        out.append(body if lead else text)
        origin.append(index)
    changed = len(out) != len(sentences(context)) or any(re.search(r'(?i)\b(?:and|they|he|she)\b', s) for s in sentences(context))
    return ('. '.join(out) + '.') if changed else None, origin


# ---------------------------------------------------------------- time order (bAbI 14)

def time_query(context, question):
    q = question.lower().strip(' ?.')
    match = re.fullmatch(r'where was (\w+) before the (\w+)', q)
    if not match:
        raise Unparsed('not a before-question')
    person, place = match.groups()
    events = []
    for index, statement in enumerate(sentences(context), 1):
        s = statement.lower()
        when = next((t for t in TIME_ORDER if t in s), None)
        who = re.search(r'\b(\w+)\s+' + MOTION + r'\s+to\s+the\s+(\w+)', s.replace(when or '##', '').strip())
        if when is None or not who:
            continue
        events.append((TIME_ORDER[when], who.group(1), who.group(2), index))
    mine = sorted(e for e in events if e[1] == person)
    if not mine:
        raise Unparsed('no timed events for that person')
    places = [e[2] for e in mine]
    if place not in places:
        return dict(answer='unknown', support=[])
    at = len(places) - 1 - places[::-1].index(place)     # before the most recent visit
    if at == 0:
        return dict(answer='unknown', support=[mine[0][3]])
    return dict(answer=places[at - 1], support=[mine[at - 1][3], mine[at][3]])


# ---------------------------------------------------------------- induction (bAbI 16)

def induction_query(context, question):
    q = question.lower().strip(' ?.')
    match = re.fullmatch(r'what colou?r is (\w+)', q)
    if not match:
        raise Unparsed('not a colour question')
    target = match.group(1)
    kind, colour, kind_at, colour_at = {}, {}, {}, {}
    for index, statement in enumerate(sentences(context), 1):
        s = statement.lower().strip()
        is_a = re.fullmatch(r'(\w+) is an? (\w+)', s)
        is_colour = re.fullmatch(r'(\w+) is (\w+)', s)
        if is_a:
            kind[is_a.group(1)], kind_at[is_a.group(1)] = is_a.group(2), index
        elif is_colour:
            colour[is_colour.group(1)], colour_at[is_colour.group(1)] = is_colour.group(2), index
    if target in colour:
        return dict(answer=colour[target], support=[colour_at[target]])
    if target not in kind:
        raise Unparsed('no kind known for that individual')
    # The most recently stated colour of another member of the same kind (best of four rules
    # compared on the training split: research/reasoning_042).
    same = [(colour_at[n], n) for n, k in kind.items() if k == kind[target] and n != target and n in colour]
    if not same:
        return dict(answer='unknown', support=[kind_at[target]])
    _, example = max(same)
    return dict(answer=colour[example], support=[kind_at[target], kind_at[example], colour_at[example]], inferred=True)


# ---------------------------------------------------------------- 2-D positions (bAbI 17)

DIRECTION = {'to the left of': (-1, 0), 'to the right of': (1, 0), 'above': (0, 1), 'below': (0, -1)}


def position_query(context, question):
    q = question.lower().strip(' ?.')
    ask = re.fullmatch(r'is the (.+?) (to the left of|to the right of|above|below) the (.+)', q)
    if not ask:
        raise Unparsed('not a position question')
    edges = []
    for index, statement in enumerate(sentences(context), 1):
        m = re.fullmatch(r'the (.+?) is (to the left of|to the right of|above|below) the (.+)', statement.lower().strip(' .'))
        if m:
            edges.append((m.group(1), DIRECTION[m.group(2)], m.group(3), index))
    if not edges:
        raise Unparsed('no position premises')
    # Place shapes by propagating offsets from one anchor.
    position = {edges[0][2]: (0, 0)}
    for _ in range(len(edges) + 1):
        for a, (dx, dy), b, _ in edges:
            if b in position and a not in position:
                position[a] = (position[b][0] + dx, position[b][1] + dy)
            elif a in position and b not in position:
                position[b] = (position[a][0] - dx, position[a][1] - dy)
    a, relation, b = ask.group(1), ask.group(2), ask.group(3)
    if a not in position or b not in position:
        return dict(answer='unknown', support=[e[3] for e in edges])
    dx, dy = position[a][0] - position[b][0], position[a][1] - position[b][1]
    holds = {'to the left of': dx < 0, 'to the right of': dx > 0, 'above': dy > 0, 'below': dy < 0}[relation]
    return dict(answer='yes' if holds else 'no', support=[e[3] for e in edges])


# ---------------------------------------------------------------- compass relations (bAbI 4)

OPPOSITE = {'north': 'south', 'south': 'north', 'east': 'west', 'west': 'east'}


def compass_query(context, question):
    q = question.lower().strip(' ?.')
    facts = []
    for index, statement in enumerate(sentences(context), 1):
        m = re.fullmatch(r'the (\w+) is (north|south|east|west) of the (\w+)', statement.lower().strip(' .'))
        if m:
            facts.append((m.group(1), m.group(2), m.group(3), index))
    if not facts:
        raise Unparsed('no compass premises')
    of = re.fullmatch(r'what is (north|south|east|west) of the (\w+)', q)
    inverse = re.fullmatch(r'what is the (\w+) (north|south|east|west) of', q)
    for a, direction, b, index in facts:
        if of and ((direction == of.group(1) and b == of.group(2))):
            return dict(answer=a, support=[index])
        if of and (OPPOSITE[direction] == of.group(1) and a == of.group(2)):
            return dict(answer=b, support=[index])
        if inverse and (a == inverse.group(1) and direction == inverse.group(2)):
            return dict(answer=b, support=[index])
        if inverse and (b == inverse.group(1) and OPPOSITE[direction] == inverse.group(2)):
            return dict(answer=a, support=[index])
    if of or inverse:
        return dict(answer='unknown', support=[f[3] for f in facts])
    raise Unparsed('not a compass question')


# ---------------------------------------------------------------- motivations (bAbI 20)

def train_motivations(rows):
    """Count motivation -> place and motivation -> object from training stories (bAbI 20 train split)."""
    places, objects = defaultdict(Counter), defaultdict(Counter)
    for row in rows:
        state, located = {}, {}
        for _, text in row['context']:
            s = text.lower().strip(' .')
            feel = re.fullmatch(r'(\w+) is (\w+)', s)
            move = re.fullmatch(r'(\w+) ' + MOTION + r' to the (\w+)', s)
            grab = re.fullmatch(r'(\w+) (?:grabbed|got|took|picked up) the (\w+) there', s)
            if feel:
                state[feel.group(1)] = feel.group(2)
            elif move and move.group(1) in state:
                places[state[move.group(1)]][move.group(2)] += 1
            elif grab and grab.group(1) in state:
                objects[state[grab.group(1)]][grab.group(2)] += 1
    return dict(places={k: dict(v) for k, v in places.items()}, objects={k: dict(v) for k, v in objects.items()})


def motivation_query(context, question, table):
    q = question.lower().strip(' ?.')
    feelings, at = {}, {}
    moves = defaultdict(list)
    grabs = defaultdict(list)
    for index, statement in enumerate(sentences(context), 1):
        s = statement.lower().strip(' .')
        feel = re.fullmatch(r'(\w+) is (\w+)', s)
        move = re.fullmatch(r'(\w+) ' + MOTION + r' to the (\w+)', s)
        grab = re.fullmatch(r'(\w+) (?:grabbed|got|took|picked up) the (\w+) there', s)
        if feel and table and feel.group(2) in table['places']:
            feelings[feel.group(1)], at[feel.group(1)] = feel.group(2), index
        elif move:
            moves[move.group(1)].append((move.group(2), index))
        elif grab:
            grabs[grab.group(1)].append((grab.group(2), index))
    where = re.fullmatch(r'where will (\w+) go', q)
    why_go = re.fullmatch(r'why did (\w+) go to the (\w+)', q)
    why_get = re.fullmatch(r'why did (\w+) (?:get|grab|take|pick up) the (\w+)', q)
    if not (where or why_go or why_get):
        raise Unparsed('not a motivation question')
    person = (where or why_go or why_get).group(1)
    if person not in feelings:
        return dict(answer='unknown', support=[])
    feeling = feelings[person]
    if where:
        likely = table['places'].get(feeling, {})
        return dict(answer=max(likely, key=likely.get), support=[at[person]], inferred=True) if likely else dict(answer='unknown', support=[at[person]])
    return dict(answer=feeling, support=[at[person]])


def load_table(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
