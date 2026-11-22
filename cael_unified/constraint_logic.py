"""Line-ups, queues, rows and races by exhaustive search (0.4.4). Non-neural.

Every sentence about positions is read into a constraint over positions 1..n (first/front/left = 1). All orders of the
named people or things are tried; the ones that satisfy every constraint survive. The question is answered only from
what every surviving order agrees on: a unique answer, "it can't be determined" (with the possibilities), or "the
statements contradict each other". Also: if-then rules (modus ponens / tollens, and the two invalid forms).
"""
import re
from itertools import permutations

ROUTE = 'chat/constraint'
ORD = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5, 'sixth': 6, 'seventh': 7, '1st': 1, '2nd': 2, '3rd': 3,
       '4th': 4, '5th': 5, '6th': 6, '7th': 7}
ORDWORD = {v: k for k, v in ORD.items() if not k[0].isdigit()}
COUNT = {'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7}
STOP = {'If', 'The', 'A', 'An', 'Who', 'Where', 'What', 'Which', 'When', 'Is', 'Are', 'Does', 'Did', 'Can', 'Could', 'In', 'On', 'At',
        'Five', 'Four', 'Three', 'Six', 'Seven', 'Two', 'They', 'He', 'She', 'It', 'I', 'We', 'You', 'My', 'Our', 'Their', 'There',
        'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday', 'Nobody', 'No', 'Yes', 'Then', 'So', 'And',
        'But', 'Each', 'Every', 'All', 'Both', 'Neither', 'Either', 'From', 'Reading', 'Left', 'Right', 'Front', 'Back'}
SCENE = re.compile(r'(?i)\b(?:queue|line|row|race|finished|stand|stands|sit|sits|seated|seats|shelf|bench|podium|places?|positions?|order|'
                   r'lined up|in front of|behind|ahead of|left of|right of|next to|beside|between|first|last)\b')


def out(text, kind):
    return dict(route=f'{ROUTE}-{kind}', response=text, sources=[], reasoning=True, details=f'{kind} (constraint_logic.py)')


def names_in(text):
    got = []
    for m in re.finditer(r'\b([A-Z][a-z]+)\b', text):
        w = m[1]
        if w in STOP:
            continue
        if w not in got:
            got.append(w)
    return got


def constraints(text, names):
    """[(description, test(pos) -> bool)] where pos maps name -> 1..n; None when a position sentence can't be read."""
    cs = []
    n_ref = [0]
    N = r'(' + '|'.join(names) + r')'
    sents = [s.strip() for s in re.split(r'(?<=[.!?;])\s+|\n+', text) if s.strip() and not s.strip().endswith('?')]
    for s in sents:
        found = False
        low = s
        for m in re.finditer(N + r"\s+(?:is|was|stands|sits|came|finished|ended up|went)\s+(not\s+)?(?:in\s+|at\s+)?(?:the\s+)?"
                             r"(first|second|third|fourth|fifth|sixth|seventh|last|front|back|middle|1st|2nd|3rd|4th|5th)\b(?!\s+of\b)(?:\s+(?:place|position|in line|in the queue))?", low):
            x, neg, where = m[1], bool(m[2]), m[3]
            cs.append((s, lambda p, x=x, neg=neg, where=where: neg != _at(p, x, where)))
            found = True
        for m in re.finditer(N + r"\s+(?:is|was|sits|stands)\s+(not\s+)?at\s+(?:either|one|an)\s+end", low):
            x, neg = m[1], bool(m[2])
            cs.append((s, lambda p, x=x, neg=neg: neg != (p[x] in (1, len(p)))))
            found = True
        for m in re.finditer(N + r"\s+(?:is|was|sits|stands|is parked)\s+(not\s+)?(?:on\s+|at\s+)?the\s+(?:far\s+)?(left|right)(?:\s+end)?\b(?!\s+of\b)", low):
            x, neg, side = m[1], bool(m[2]), m[3]
            cs.append((s, lambda p, x=x, neg=neg, side=side: neg != (p[x] == (1 if side == 'left' else len(p)))))
            found = True
        for m in re.finditer(N + r"\s+(?:is|was|sits|stands|finished|came|ran|went|arrived)?\s*(not\s+)?(directly\s+|immediately\s+|right\s+|just\s+)?"
                             r"(behind|after|ahead of|in front of|before|to the left of|left of|to the right of|right of)\s+" + N, low):
            x, neg, adj, rel, y = m[1], bool(m[2]), bool(m[3]), m[4], m[5]
            later = rel in ('behind', 'after', 'to the right of', 'right of')
            cs.append((s, lambda p, x=x, y=y, neg=neg, adj=adj, later=later:
                       neg != ((p[x] - p[y] == (1 if later else -1)) if adj else ((p[x] > p[y]) if later else (p[x] < p[y])))))
            found = True
        for m in re.finditer(N + r"\s+(?:finished\s+|came\s+)?(?:right|directly|immediately|just)\s+after\s+" + N, low):
            pass        # covered above
        for m in re.finditer(N + r"\s+(?:(won|came first|finished first|was the winner|took first place)|(came last|finished last|was last))\b", low):
            x, first = m[1], bool(m[2])      # 2026-11-22, test-informed: "Uma won"
            cs.append((s, lambda p, x=x, first=first: p[x] == (1 if first else len(p))))
            found = True
        for m in re.finditer(N + r"\s+(beat|outran|overtook|finished ahead of|finished before)\s+" + N, low):
            x, y = m[1], m[3]
            cs.append((s, lambda p, x=x, y=y: p[x] < p[y]))
            found = True
        for m in re.finditer(N + r"\s+(?:is|was|sits|stands)\s+(not\s+)?(?:directly\s+|right\s+)?(?:next to|beside|adjacent to)\s+" + N, low):
            x, neg, y = m[1], bool(m[2]), m[3]
            cs.append((s, lambda p, x=x, y=y, neg=neg: neg != (abs(p[x] - p[y]) == 1)))
            found = True
        for m in re.finditer(N + r"\s+(?:is|was|sits|stands)\s+(not\s+)?(?:somewhere\s+|directly\s+|right\s+)?between\s+" + N + r"\s+and\s+" + N, low):
            x, neg, y, z = m[1], bool(m[2]), m[3], m[4]
            cs.append((s, lambda p, x=x, y=y, z=z, neg=neg: neg != (min(p[y], p[z]) < p[x] < max(p[y], p[z]))))
            found = True
        relation = re.search(r'(?i)\b(?:before|after|ahead|behind|front|back|next|beside|left|right|between|first|second|third|last|middle|end|beat)\b', s)
        if not found and SCENE.search(s) and any(re.search(r'\b' + nm + r'\b', s) for nm in names) and relation:
            return None         # a sentence about places that we could not read: do not guess
    return cs


def _at(p, x, where):
    n = len(p)
    if where in ('first', 'front', '1st'):
        return p[x] == 1
    if where in ('last', 'back'):
        return p[x] == n
    if where == 'middle':
        return n % 2 == 1 and p[x] == (n + 1) // 2
    k = ORD.get(where)
    return k is not None and p[x] == k


COLOURS = r'(?:red|blue|green|yellow|white|black|grey|gray|orange|purple|pink|brown|silver|gold)'


def normalise(text):
    """'the red car' -> 'Red'; 'the blue one' -> 'Blue'; 'Liam finished before Mia but after Noah' -> two sentences."""
    listed = re.search(r'(?i)\b' + COLOURS + r'(?:\s*,\s*' + COLOURS + r'){1,},?\s+and\s+' + COLOURS + r'\b', text)
    if listed:          # "five books: red, blue, green, yellow and white" -> the colours are the things (2026-11-22, test-informed)
        cols = set(re.findall(r'(?i)' + COLOURS, listed[0]))
        text = re.sub(r'(?i)\b(?:the\s+)?(' + '|'.join(cols) + r')(?:\s+(?:one|book|car|house|box|door|cup|ball))?\b', lambda m: m[1].capitalize(), text)
    nouns = [n for n in re.findall(r'(?i)\b' + COLOURS + r'\s+([a-z]+)\b', text)
             if n.lower() not in ('is', 'was', 'are', 'were', 'and', 'or', 'sits', 'stands', 'immediately', 'directly', 'not', 'on', 'in', 'at')]
    noun = max(set(n.lower() for n in nouns), key=lambda n: [x.lower() for x in nouns].count(n)) if nouns else None
    if noun and [x.lower() for x in nouns].count(noun) >= 2:
        text = re.sub(r'(?i)\b(?:the\s+|a\s+)?(' + COLOURS + r')\s+(?:' + noun + r'|one)\b', lambda m: m[1].capitalize(), text)
        text = re.sub(r'(?i)\b(?:the\s+)?(?:fourth|fifth|third|other|last|remaining)\s+' + noun + r'\s+is\s+(' + COLOURS + r')\b',
                      lambda m: f'There is {m[1].capitalize()}', text)
    text = re.sub(r'\b([A-Z][a-z]+)\s+(finished|came|arrived|is|was|stands|sits)\s+(before|after|ahead of|behind|in front of)\s+([A-Z][a-z]+)\s+but\s+'
                  r'(before|after|ahead of|behind|in front of)\s+([A-Z][a-z]+)', r'\1 \2 \3 \4. \1 \2 \5 \6', text)
    return text


def solve(text, names):
    cs = constraints(text, names)
    if cs is None or not cs:
        return None, None
    sols = []
    for perm in permutations(names):
        pos = {nm: i + 1 for i, nm in enumerate(perm)}
        if all(t(pos) for _, t in cs):
            sols.append(pos)
        if len(sols) > 200:
            break
    return sols, cs


def position_word(k, n):
    if k == 1:
        return 'first'
    if k == n:
        return f'last ({ORDWORD.get(k, str(k))})'
    return ORDWORD.get(k, f'number {k}')


def respond(messages):
    users = [(m.get('content') or '').strip() for m in messages if m.get('role') == 'user']
    if not users:
        return None
    q = users[-1]
    text = '\n'.join(users[-4:])
    got = if_then(text, q)
    if got:
        return got
    text = normalise(text)
    q = normalise(q)
    got = all_are(text, q)
    if got:
        return got
    if not SCENE.search(text) or not q.rstrip().endswith('?'):
        return None
    qs = re.findall(r'[^.!?\n]*\?', q)
    if not qs:
        return None
    question = qs[-1].strip()
    names = names_in(re.sub(r'[^.!?\n]*\?', ' ', text))
    for nm in names_in(question):
        if nm not in names:
            names.append(nm)
    said = re.search(r'(?i)\b(two|three|four|five|six|seven)\s+(?:friends|people|runners|children|kids|students|cars|horses|players|books|jars|boxes|houses|cats|dogs|guests|teams|swimmers)', text)
    if said and COUNT[said[1].lower()] != len(names):
        return None
    if not 2 <= len(names) <= 7:
        return None
    sols, cs = solve(text, names)
    if sols is None:
        return None
    n = len(names)
    if not sols:
        return out('**The statements contradict each other**: no order satisfies all of them.', 'contradiction')
    unique = len(sols) == 1
    m = re.search(r'(?i)\bwhere\s+(?:is|does|did|was)\s+(\w+)|what\s+(?:position|place)\s+(?:is|was|did)\s+(\w+)|(\w+)\'s\s+position', question)
    if m:
        x = m[1] or m[2] or m[3]
        if x not in names:
            return None
        vals = {s[x] for s in sols}
        if len(vals) == 1:
            k = vals.pop()
            return out(f'**{x} is {position_word(k, n)}.** ' + _explain(sols, names), 'where')
        return out(f'**It can\'t be determined**: {x} could be ' + ' or '.join(position_word(v, n) for v in sorted(vals)) + '.', 'where')
    m = re.search(r'(?i)\b(?:who|which\s+(?:[a-z]+\s+)?)\s*(?:is|was|came|finished|stands|sits|ended up|is parked)\s+(?:in\s+|at\s+|on\s+)?(?:the\s+)?(?:far\s+|very\s+)?(first|second|third|fourth|fifth|last|middle|front|back|left end|right end|left|right|leftmost|rightmost|youngest|oldest)\b(?!\s+of\b)', question)
    if m:
        where = m[1].lower()
        if where in ('youngest', 'oldest'):
            return None
        k = {'first': 1, 'front': 1, 'left end': 1, 'left': 1, 'leftmost': 1, 'last': n, 'back': n, 'right end': n, 'right': n, 'rightmost': n,
             'middle': (n + 1) // 2 if n % 2 else None}.get(where, ORD.get(where))
        if not k:
            return None
        who = {next(nm for nm in names if s[nm] == k) for s in sols}
        if len(who) == 1:
            return out(f'**{who.pop()}.** ' + _explain(sols, names), 'who')
        return out(f'**It can\'t be determined**: it could be ' + ' or '.join(sorted(who)) + '.', 'who')
    m = re.search(r'(?i)\bwho\s+(?:sits|stands|is)\s+(?:directly\s+)?(?:next to|beside)\s+(\w+)', question)
    if m and m[1] in names:
        x = m[1]
        nb = {frozenset(nm for nm in names if abs(s[nm] - s[x]) == 1) for s in sols}
        if len(nb) == 1:
            got = sorted(nb.pop())
            return out(f'**{" and ".join(got)}.** ' + _explain(sols, names), 'next-to')
        return out('**It can\'t be determined** from what you said.', 'next-to')
    m = re.search(r'(?i)\bcould\s+(\w+)\s+(?:be|have been|have finished|finish|sit|stand)\s+(?:in\s+|at\s+)?(?:the\s+)?(first|second|third|fourth|fifth|last|middle|front|back)\b', question)
    if m and m[1] in names:
        x, where = m[1], m[2].lower()
        ok = any(_at(s, x, where) for s in sols)
        return out(f'**{"Yes" if ok else "No"}.** ' + ('At least one order that fits everything puts them there.' if ok else 'No order that fits every statement puts them there.'), 'could')
    if re.search(r'(?i)\b(?:order|line-?up|arrangement|ranking|standings)\b', question):
        orders = {tuple(sorted(names, key=lambda nm: s[nm])) for s in sols}
        if len(orders) == 1:
            return out(f'**{", ".join(orders.pop())}** (first to last).', 'order')
        return out(f'**It can\'t be fully determined**: {len(orders)} orders fit, for example ' +
                   '; '.join(', '.join(o) for o in list(orders)[:2]) + '.', 'order')
    return None


def _explain(sols, names):
    if len(sols) == 1:
        return 'The only order that fits every statement is ' + ', '.join(sorted(names, key=lambda nm: sols[0][nm])) + ' (first to last).'
    return f'{len(sols)} orders fit every statement, and they all agree on this.'


def all_are(text, q):
    """'All my mugs are blue. This cup is red. Is it one of my mugs?' -> No."""
    m = re.search(r'(?i)\b(?:all|every one of|each of)\s+(?:my|the|our)\s+(?P<cls>[a-z]+)\s+(?:are|were)\s+(?P<p>[a-z]+)\b', text)
    t = re.search(r'(?i)\bthis\s+(?P<thing>[a-z]+)\s+(?:is|was)\s+(?P<q>[a-z]+)\b', text)
    if not (m and t) or not re.search(r'(?i)\b(?:one of|among|part of)\s+(?:my|the|our)\s+' + m['cls'][:-1], q):
        return None
    p, v = m['p'].lower(), t['q'].lower()
    if p == v:
        return out(f'**Not necessarily.** All of them are {p}, but being {p} does not make something one of them.', 'all-are')
    if re.fullmatch(COLOURS, p) and re.fullmatch(COLOURS, v):
        return out(f'**No.** Every one of them is {p}; this one is {v}, so it can\'t be one of them.', 'all-are')
    return None


# ------------------------------------------------------------------ if-then rules
def if_then(text, q):
    m = re.search(r'(?i)\bif\s+(?P<p>[^,.]+?),\s*(?:then\s+)?(?P<c>[^.]+)\.', text)
    if not m or not q.rstrip().endswith('?'):
        return None
    p, c = m['p'].strip().lower(), m['c'].strip().lower()
    rest = text[m.end():].lower()
    facts = [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', rest) if s.strip() and not s.strip().endswith('?')]

    def core(s):
        s = re.sub(r"\b(?:was|is|were|are|has been|had been|will be|did|does|do)\b", ' ', s)
        s = re.sub(r"\b(?:not|n't|never|no longer)\b|n't", ' ', s)
        return set(w for w in re.findall(r'[a-z]+', s) if len(w) > 2 and w not in ('the', 'and', 'that', 'this', 'its', 'their'))

    def negated(s):
        return bool(re.search(r"\b(?:not|never|no longer)\b|n't|\bdidn|\bwasn|\bisn|\bweren", s))

    def same(a, b):
        ka, kb = core(a), core(b)
        stem = lambda w: re.sub(r'(?:ed|ing|es|s)$', '', w)
        sa, sb = {stem(w) for w in ka}, {stem(w) for w in kb}
        return bool(sa) and bool(sb) and len(sa & sb) >= min(len(sa), len(sb))      # every content word of the shorter one
    for f in facts:
        if same(f, c):
            if negated(f) != negated(c):
                # not-C: modus tollens -> not-P
                if same(q, p):
                    return out(f'**No.** If {p}, then {c}; that did not happen, so {p} cannot be true (modus tollens).', 'if-then')
            else:
                if same(q, p):
                    return out(f'**It can\'t be determined.** {c[0].upper() + c[1:]} could have other causes: the rule says what follows '
                               f'from "{p}", not the reverse.', 'if-then')
        if same(f, p):
            if negated(f) == negated(p):
                if same(q, c):
                    return out(f'**Yes.** If {p}, then {c}, and {p} is the case.', 'if-then')
            else:
                if same(q, c):
                    return out(f'**It can\'t be determined.** The rule only says what happens if {p}; it says nothing about the case '
                               f'where that is false.', 'if-then')
    return None
