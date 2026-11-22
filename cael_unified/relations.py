"""General relation reader and solver (0.4.4 work after release, 2026-11-22). Non-neural.

The earlier puzzle readers each matched one way of saying things. This one reads any sentence by its parts:
- **Things:** the people or things named in a list ("jobs called wash, paint and seal", "Ann, Ben and Cara") or by
  capitalised names.
- **Mentions:** every place a thing is mentioned in a sentence.
- **Relation words:** what lies between two mentions decides the fact. "before", "ahead of", "precedes" and
  "followed by" give an order; "immediately", "right", "directly" and "just" make it adjacent; "next to" and "beside"
  are adjacency either way; "two places after" is a distance; "not", "never" and "can't" negate. One mention with
  "first", "last", "second", "the middle" or "either end" gives a place.
- **Kinds of scene:** a line or schedule (positions 1..n), a ring ("round table", "circle"), or matching people to
  things ("each has a different pet: a cat, a dog and a fish").

Every arrangement is tried. The question is answered from the arrangements that satisfy every fact:
- "could" and "can" ask whether one exists;
- "must" and "have to" ask whether all do;
- which / who / where / what order / how many ways are read off from all of them.
A sentence that has relation words but can't be read stops the reader, so it never answers from part of the facts.
A later sentence with "actually", "instead" or "I meant" replaces the earlier facts about the same things.
"""
import re
from itertools import permutations

ROUTE = 'chat/relations'
ORD = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5, 'sixth': 6, 'seventh': 7, '1st': 1, '2nd': 2, '3rd': 3,
       '4th': 4, '5th': 5, '6th': 6, '7th': 7}
ORDWORD = {1: 'first', 2: 'second', 3: 'third', 4: 'fourth', 5: 'fifth', 6: 'sixth', 7: 'seventh'}
NUMW = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6}
FUNCTION = {'is', 'are', 'was', 'were', 'be', 'then', 'that', 'this', 'it', 'they', 'he', 'she', 'we', 'i', 'you', 'not', 'so',
            'but', 'if', 'when', 'one', 'each', 'all', 'both', 'some', 'any', 'there', 'here', 'also', 'only', 'just', 'very',
            'must', 'can', 'could', 'should', 'will', 'would', 'has', 'have', 'had', 'do', 'does', 'did', 'first', 'last',
            'second', 'third', 'before', 'after', 'who', 'what', 'which', 'where', 'how', 'my', 'our', 'their', 'his', 'her',
            'me', 'us', 'them', 'him', 'in', 'on', 'at', 'to', 'of', 'for', 'with', 'by', 'from', 'up', 'out', 'more', 'less',
            'time', 'times', 'order', 'way', 'ways', 'day', 'days', 'people', 'person', 'things', 'thing', 'other', 'another',
            'same', 'different', 'yes', 'no', 'now', 'today', 'tomorrow', 'yesterday', 'once', 'twice', 'never', 'always'}
FUNCTION |= set(NUMW) | {'seven', 'eight', 'nine', 'ten'}
STOP_CAPS = {'If', 'The', 'A', 'An', 'Who', 'Where', 'What', 'Which', 'When', 'Is', 'Are', 'Does', 'Did', 'Can', 'Could', 'In', 'On',
             'At', 'They', 'He', 'She', 'It', 'I', 'We', 'You', 'My', 'Our', 'Their', 'There', 'Nobody', 'No', 'Yes', 'Then', 'So',
             'And', 'But', 'Each', 'Every', 'All', 'Both', 'Neither', 'Either', 'From', 'Must', 'Should', 'Would', 'Will', 'Do',
             'Has', 'Have', 'How', 'Why', 'Actually', 'Sorry', 'Also', 'Now', 'Suppose', 'Assume', 'Assuming', 'Given', 'For',
             'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'This', 'That', 'These', 'Those', 'Please', 'Okay', 'OK', 'Ok',
             'Hi', 'Hello', 'Thanks', 'Starting', 'Moving', 'Going', 'Counting', 'Wait', 'Oh', 'Well', 'To', 'Of', 'With', 'After', 'Before', 'Not', 'Only', 'Just', 'Is',
             'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday', 'January', 'February', 'March',
             'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December', 'Mr', 'Mrs', 'Ms', 'Dr'}

NEG = re.compile(r"(?i)\b(?:not|never|cannot|can't|mustn't|isn't|wasn't|aren't|doesn't|don't|didn't|won't|shouldn't|no)\b|n't\b")
FOLLOWED = re.compile(r'(?i)\b(?:(?:is|are|was|be|gets?|got)\s+)?(followed|preceded|succeeded)\s+(?:immediately\s+|directly\s+|right\s+|straight\s+|just\s+)?by\b')
ADJ_WORD = re.compile(r'(?i)\b(?:immediately|directly|right|straight|just|the\s+(?:very\s+)?(?:next|one|job|step|slot|task|spot|place)|next)\s+'
                      r'(?:(?:\w+\s+)?(?:after|before|behind|in front of|ahead of|following|preceding)\b)|\bthe\s+(?:very\s+)?next\s+\w+\s+after\b|\bnext\s+after\b')
BEFORE = re.compile(r'(?i)\b(?:before|earlier\s+than|ahead\s+of|in\s+front\s+of|precedes?|preceded|preceding|prior\s+to|sooner\s+than|'
                    r'(?:to\s+the\s+)?left\s+of|on\s+the\s+left\s+of|beat|beats|outran|outrun|overtook|until|then)\b')
AFTER = re.compile(r'(?i)\b(?:after|later\s+than|behind|follows?|followed|following|(?:to\s+the\s+)?right\s+of|on\s+the\s+right\s+of|'
                   r'lost\s+to|once|later)\b')
NEXT_TO = re.compile(r'(?i)\b(?:next\s+to|beside|besides|adjacent\s+to|adjacent|alongside|neighbou?rs?|neighbou?ring|together|side\s+by\s+side)\b')
OPPOSITE = re.compile(r'(?i)\b(?:opposite|across\s+from|directly\s+across|facing)\b')
DIST = re.compile(r'(?i)\b(\d|one|two|three|four|five)\s+(?:places?|spots?|positions?|seats?|slots?|jobs?|steps?|tasks?|spaces?|people|cars?|'
                  r'houses?|days?|rooms?|doors?|turns?)\s+(before|after|ahead\s+of|behind|in\s+front\s+of|apart\s+from|away\s+from|apart|from)\b')
CLOCKWISE = re.compile(r'(?i)\b(?:(\d|one|two|three)\s+(?:seats?|places?|stools?|chairs?|spots?|steps?)\s+)?'
                       r'(immediately\s+|directly\s+|right\s+|just\s+|next\s+|one\s+(?:seat|place|stool)\s+)?'
                       r'(counter-?clockwise|anti-?clockwise|clockwise)\s+(?:from|of|after|to)\b')
SAME = re.compile(r'(?i)\b(?:the\s+same\s+as|equals?)\b')
POS_FIRST = re.compile(r'(?i)\b(?:first|start(?:s|ing)?|begins?|beginning|opens?|opening|front|leftmost|far\s+left|earliest|kicks?\s+off|won|win|wins|winner)\b')
POS_LAST = re.compile(r'(?i)\b(?:last|final|finally|back|rightmost|far\s+right|latest|closes?|closing)\b|\b(?:at|is)\s+the\s+(?:very\s+)?end\b')
POS_ENDS = re.compile(r'(?i)\b(?:either|one\s+of\s+the|an|one|the\s+two)\s+ends?\b|\bat\s+the\s+ends\b')
POS_MIDDLE = re.compile(r'(?i)\b(?:in\s+the\s+)?(?:middle|centre|center)\b')
POS_ORD = re.compile(r'(?i)\b(second|third|fourth|fifth|sixth|seventh|2nd|3rd|4th|5th|6th|7th)\b|\b(?:number|position|place|slot|spot|seat)\s+(\d)\b')
RELWORD = re.compile(r'(?i)\b(?:before|after|ahead|behind|front|follow\w*|preced\w*|next|beside|adjacent|left|right|between|first|second|'
                     r'third|fourth|fifth|last|middle|end|ends|opposite|across|earlier|later|beat|start\w*|begin\w*|immediately|directly)\b')
CORRECT = re.compile(r"(?i)\b(?:actually|instead|correction|sorry|i\s+meant|scratch\s+that|change\s+of\s+plans?|update|i\s+was\s+wrong|"
                     r"rather|i\s+got\s+that\s+wrong|my\s+mistake|not\s+quite)\b")
RING = re.compile(r'(?i)\b(?:round|circular)\s+table\b|\b(?:in|form|forms|formed|forming|around)\s+a\s+(?:circle|ring)\b|\bclockwise\b|\baround\s+(?:a|the)\s+(?:\w+\s+)?table\b|\bcircle\b')
MATCHING = re.compile(r'(?i)\b(?:each|every\s+one|everyone|one\s+each|different|exactly\s+one|one\s+of)\b')


def out(text, kind):
    return dict(route=f'{ROUTE}-{kind}', response=text, sources=[], reasoning=True, details=f'{kind} (relations.py)')


# ------------------------------------------------------------------ things
_W = r"[A-Za-z][\w'-]*"
_NOTW = r"(?!(?:and|or|nor|is|are|was|were|be|must|has|have|had|can|could|each|all|both|will|would|should|in|on|at|to|of|for|with|then|but|"
_NOTW += r"so|that|which|who|go|goes|come|comes|happen|happens|sit|sits|stand|stands|need|needs|finished|ran|play|plays|own|owns)\b)"
ITEM = r"(?:(?:the|a|an)\s+)?" + _W + r"(?:\s+" + _NOTW + _W + r")?"
LIST3 = re.compile(r'(?<![\w-])(' + ITEM + r'(?:\s*,\s*' + ITEM + r')+\s*,?\s+(?:and|or)\s+' + ITEM + r')(?![\w-])')
LIST2 = re.compile(r'(?i)(?:called|named|:|are|were|namely|-)\s+(' + ITEM + r'\s+(?:and|or)\s+' + ITEM + r')(?![\w-])')
LISTC = re.compile(r'(?i):\s*(' + ITEM + r'(?:\s*,\s*' + ITEM + r'){2,})\s*(?=[.;\n]|$)')


def _items(span, text=''):
    parts = re.split(r'\s*,\s*(?:and\s+|or\s+)?|\s+and\s+|\s+or\s+', span.strip())
    got = []
    parts = [re.sub(r'(?i)^(?:the|a|an)\s+', '', p.strip()) for p in parts]
    for i, p in enumerate(parts):       # a two-word item is kept only when the text says it again
        w = p.split()
        if len(w) == 2 and len(re.findall(r'(?i)(?<![\w-])' + re.escape(p) + r'(?![\w-])', text)) < 2:
            parts[i] = w[0] if i == len(parts) - 1 else w[1]
    caps = [p for p in parts if p[:1].isupper()]
    if 2 <= len(caps) < len(parts) and not parts[0][:1].isupper():
        parts = caps        # "three friends, Raj, Sue and Tom" -> the names
    for p in parts:
        if not p or p.lower() in FUNCTION or p.isdigit() or len(p) < 2 and not p.isupper():
            return None
        got.append(p)
    return got if len(set(x.lower() for x in got)) == len(got) else None


def lists_in(text):
    found = []
    for rx in (LIST3, LISTC, LIST2):
        for m in rx.finditer(text):
            it = _items(m[1], text)
            if it and not any(set(x.lower() for x in it) <= set(y.lower() for y in f) for f in found):
                found.append(it)
    out_ = []
    for f in found:         # drop lists contained in a longer one
        low = set(x.lower() for x in f)
        if not any(low < set(y.lower() for y in g) for g in found):
            if not any(low == set(y.lower() for y in g) for g in out_):
                out_.append(f)
    return out_


def caps_names(text):
    got = []
    for m in re.finditer(r"\b([A-Z][a-z]+)\b", text):
        w = m[1]
        if w in STOP_CAPS or w.lower() in FUNCTION:
            continue
        if w not in got:
            got.append(w)
    return got


def mention_re(e):
    return re.compile(r"(?i)(?<![\w-])" + re.escape(e) + r"(?:'s|s|es|ing|ed)?(?![\w-])")


def mentions(clause, ents):
    """[(start, end, entity)] in order, without overlaps."""
    got = []
    for e in ents:
        for m in mention_re(e).finditer(clause):
            got.append((m.start(), m.end(), e))
    got.sort(key=lambda t: (t[0], -(t[1] - t[0])))
    keep, last = [], -1
    for s, e_, ent in got:
        if s >= last:
            keep.append((s, e_, ent))
            last = e_
    return keep


# ------------------------------------------------------------------ facts
def clauses(text):
    sents = [s.strip() for s in re.split(r'(?<=[.!?;])\s+|\n+', text) if s.strip()]
    out_ = []
    for s in sents:
        for piece in re.split(r'(?i),?\s+\bbut\b\s+|,\s*and\s+(?=\w+\s+(?:\w+\s+)?(?:is|was|must|has|have|can|comes?|goes?|sits?|stands?|'
                              r'happens?|finished|came|should|needs?|will|isn|doesn))|;\s*|,\s*while\s+|,\s*whereas\s+|,\s*so\s+|\s+-\s+|\s+—\s+', s):
            if piece and piece.strip():
                out_.append(piece.strip())
    return out_


class Unread(Exception):
    pass


def _dist(word):
    return int(word) if word.isdigit() else NUMW.get(word.lower())


def pair_fact(x, mid, y, after_text=''):
    """A fact over positions relating mention x (first in the sentence) and y, from the words between them."""
    neg = bool(NEG.search(mid))
    fol = FOLLOWED.search(mid)
    if fol:
        adj = bool(re.search(r'(?i)\b(?:immediately|directly|right|straight|just)\b', mid))
        before = fol[1].lower() in ('followed', 'succeeded')
        return ('order', x, y, before, adj, neg)
    cw = CLOCKWISE.search(mid)
    if cw:
        k = _dist(cw[1]) if cw[1] else (1 if cw[2] else None)
        if k is None:
            raise Unread
        return ('gap', x, y, -k if re.match(r'(?i)(?:counter|anti)', cw[3]) else k, neg)
    d = DIST.search(mid)
    if d:
        k = _dist(d[1])
        rel = d[2].lower()
        if rel in ('apart from', 'away from', 'apart', 'from'):
            return ('dist', x, y, k, neg)
        before = rel in ('before', 'ahead of', 'in front of')
        return ('gap', x, y, k if not before else -k, neg)
    if OPPOSITE.search(mid):
        return ('opposite', x, y, neg)
    adj = bool(ADJ_WORD.search(mid))
    b, a = BEFORE.search(mid), AFTER.search(mid)
    if b or a:
        before = b.start() < a.start() if b and a else bool(b)
        side = bool(re.search(r"(?i)\b(?:left|right)\s+of\b|\bon\s+\w+(?:'s)?\s+(?:left|right)\b", mid))
        return ('order', x, y, before, adj, neg, side)
    if NEXT_TO.search(mid):
        return ('adj', x, y, neg)
    if re.search(r'(?i)\bunless\b', mid):
        raise Unread
    return None


def unary_fact(x, text):
    neg = bool(NEG.search(text))
    if POS_ENDS.search(text):
        return ('ends', x, neg)
    m = POS_ORD.search(text)
    if m:
        k = ORD.get((m[1] or '').lower()) or int(m[2])
        return ('at', x, k, neg)
    if POS_MIDDLE.search(text):
        return ('middle', x, neg)
    if POS_FIRST.search(text) and not re.search(r'(?i)\bfirst\s+(?:of\s+all|time)\b', text):
        return ('at', x, 1, neg)
    if POS_LAST.search(text):
        return ('at', x, -1, neg)
    return None


def read_facts(text, ents):
    """[(fact, entities)] from the statements; raises Unread when a sentence about places can't be read."""
    facts = []
    subject = None
    for c in clauses(text):
        if c.endswith('?'):
            continue
        ms = mentions(c, ents)
        correcting = bool(CORRECT.search(c))
        if not ms:
            continue
        got = []
        # a clause that starts with a relation word continues the last subject: "..., but after Noah"
        if len(ms) == 1 and subject and re.match(r'(?i)(?:and\s+|but\s+|also\s+)?(?:not\s+)?(?:immediately\s+|directly\s+|right\s+|just\s+)?'
                                                 r'(?:before|after|behind|ahead of|in front of|next to|beside)\b', c):
            f = pair_fact(subject, c[:ms[0][0]], ms[0][2])
            if f:
                got.append(f)
        between = re.search(r'(?i)\bbetween\b', c)
        if between and len(ms) >= 3 and not got:
            after_b = [m for m in ms if m[0] > between.start()]
            before_b = [m for m in ms if m[0] < between.start()]
            if len(after_b) >= 2 and before_b:
                neg = bool(NEG.search(c[before_b[-1][1]:between.start()]))
                direct = bool(re.search(r'(?i)\b(?:directly|right|exactly|immediately)\s+between\b', c))
                got.append(('between', before_b[-1][2], after_b[0][2], after_b[1][2], neg, direct))
            elif len(after_b) >= 3:     # "Between A and B sits C"
                got.append(('between', after_b[2][2], after_b[0][2], after_b[1][2], bool(NEG.search(c)), False))
        if not got and len(ms) == 2 and re.search(r'(?i)\b(?:and|&)\b', c[ms[0][1]:ms[1][0]]) and len(c[ms[0][1]:ms[1][0]]) < 8:
            rest = c[ms[1][1]:]
            if NEXT_TO.search(rest) or re.search(r'(?i)\beach\s+other\b', rest):
                got.append(('adj', ms[0][2], ms[1][2], bool(NEG.search(rest))))
            elif POS_ENDS.search(rest) or re.search(r'(?i)\bthe\s+ends\b', rest):
                got += [('ends', ms[0][2], False), ('ends', ms[1][2], False)]
            elif re.search(r'(?i)\bin\s+that\s+order\b', rest):
                got.append(('order', ms[0][2], ms[1][2], True, False, False))
        if not got and len(ms) >= 3 and re.search(r'(?i)\bin\s+that\s+order\b|\bin\s+this\s+order\b', c):
            for (_, _, a), (_, _, b) in zip(ms, ms[1:]):
                got.append(('order', a, b, True, False, False))
        if not got:
            for i, (s, e, x) in enumerate(ms):
                nxt = ms[i + 1] if i + 1 < len(ms) else None
                if nxt:
                    mid = c[e:nxt[0]]
                    f = pair_fact(x, mid, nxt[2])
                    if f:
                        got.append(f)
                        continue
                    if re.search(r'(?i)\b(?:and|or|nor)\b', mid) and len(mid) < 10:
                        continue
                window = c[e:nxt[0]] if nxt else c[e:]
                prefix = c[:s] if i == 0 else ''
                f = unary_fact(x, window) or (unary_fact(x, prefix) if prefix and not RELWORD.search(window) else None)
                if f:
                    if not f[-1] and NEG.search(prefix):
                        f = f[:-1] + (True,)
                    got.append(f)
        if got:
            subject = ms[0][2]
            if correcting:
                touched = {frozenset(f_ents(f)) for f in got}
                facts = [(f, es) for f, es in facts if frozenset(es) not in touched and not (set(es) & set().union(*touched) and len(es) == 1)]
            facts += [(f, f_ents(f)) for f in got]
        elif RELWORD.search(c) and not re.search(r'(?i)\b(?:called|named|each|every|one at a time|once|options?|are)\b', c):
            raise Unread
    return facts


def f_ents(f):
    return [v for v in f[1:] if isinstance(v, str)]


# ------------------------------------------------------------------ checking a line or a ring
def holds(f, p, n, ring):
    kind = f[0]
    if kind == 'order':
        _, x, y, before, adj, neg = f[:6]
        if ring:        # at a round table "left of" means the seat directly to the left
            if len(f) > 6 and f[6]:
                before = not before       # positions go clockwise; "left of Y" is the seat after Y
            d = (p[y] - p[x]) % n
            ok = (d == 1) if before else (d == n - 1)
            if not adj and not (len(f) > 6 and f[6]):
                raise Unread
        else:
            d = p[y] - p[x]
            ok = (d == 1 if adj else d > 0) if before else (d == -1 if adj else d < 0)
        return ok != neg
    if kind == 'noop':
        return True
    if kind == 'gap':
        _, x, y, k, neg = f
        if ring:
            return ((p[x] - p[y]) % n == k % n) != neg
        return (p[x] - p[y] == k) != neg
    if kind == 'dist':
        _, x, y, k, neg = f
        d = abs(p[x] - p[y])
        if ring:
            d = min(d, n - d)
        return (d == k) != neg
    if kind == 'adj':
        _, x, y, neg = f
        d = abs(p[x] - p[y])
        return (d == 1 or ring and d == n - 1) != neg
    if kind == 'opposite':
        _, x, y, neg = f
        if not ring or n % 2:
            raise Unread
        return ((p[x] - p[y]) % n == n // 2) != neg
    if kind == 'between':
        _, x, y, z, neg, direct = f
        if ring:
            raise Unread
        ok = min(p[y], p[z]) < p[x] < max(p[y], p[z]) and (not direct or abs(p[y] - p[z]) == 2)
        return ok != neg
    if ring:
        raise Unread
    if kind == 'at':
        _, x, k, neg = f
        k = n if k == -1 else k
        return (p[x] == k - 1) != neg
    if kind == 'ends':
        _, x, neg = f
        return (p[x] in (0, n - 1)) != neg
    if kind == 'middle':
        _, x, neg = f
        if n % 2 == 0:
            raise Unread
        return (p[x] == n // 2) != neg
    raise Unread


def arrangements(ents, facts, ring, extra=()):
    n = len(ents)
    sols = []
    rest = ents[1:] if ring else ents
    for perm in permutations(rest):
        order = ([ents[0]] + list(perm)) if ring else list(perm)
        p = {e: i for i, e in enumerate(order)}
        if all(holds(f, p, n, ring) for f, _ in facts) and all(holds(f, p, n, ring) for f in extra):
            sols.append(order)
    return sols


# ------------------------------------------------------------------ questions
MAY = re.compile(r'(?i)\b(?:could|can|possible|possibly|might|may|is\s+there\s+(?:a|any)\s+way|allowed|able)\b')
MUST = re.compile(r'(?i)\b(?:must|have\s+to|has\s+to|need\s+to|needs\s+to|necessarily|definitely|always|certainly|for\s+sure|guaranteed|forced)\b')


def strip_q(q):
    q = re.sub(r'(?i)^\s*(?:so|ok(?:ay)?|and|but|then|now|also|wait|hmm)[,\s]+', '', q)
    q = re.sub(r"(?i)\b(?:is\s+it\s+possible\s+(?:that|for)|could|can|must|might|may|does|do|did|is|are|was|will|would|should|"
               r"have\s+to|has\s+to|necessarily|definitely|always|possibly|be|for\s+sure)\b", ' ', q)
    return re.sub(r'\s+', ' ', q).strip(' ?')


def listing(order):
    return ', '.join(order)


def pos_name(k, n):
    return 'last' if k == n and n > 2 else ORDWORD.get(k, f'number {k}')


def ask_line(q, ents, facts, ring):
    """The reply to the question q, or None when the question isn't one this reader answers."""
    n = len(ents)
    hyp = re.match(r'(?i)\s*(?:and\s+|so\s+|but\s+)?(?:what\s+if|if|suppose|assuming|assume|given\s+that|say)\s+(.+?)(?:,\s*|\s+then\s+)(.+)$', q)
    if not hyp:
        tail = re.match(r'(?i)(.+?),?\s+(?:if|assuming|given\s+that|provided)\s+(.+?)\??$', q)
        if tail:
            hyp = (None, tail[2], tail[1])
    extra = []
    if hyp:
        cond = hyp[1]
        if ring and re.search(r'(?i)\b(?:last|remaining|other|empty|free|spare)\s+(?:seat|stool|chair|place|spot)\b', cond) and                 len(mentions(cond, ents)) == 1:
            got = [('noop',)]       # "if Paz has the last stool": nothing new at a ring
        else:
            try:
                got = [f for f, _ in read_facts(cond + '.', ents)]
            except Unread:
                return None
        if not got:
            return None
        extra = [f for f in got if f[0] != 'noop']
        q = hyp[2]
    sols = arrangements(ents, facts, ring, extra)
    if not sols:
        if re.search(r'(?i)\bhow\s+many\b', q):
            return out('**0.** No order fits every rule you gave, so the rules contradict each other.', 'count')
        if extra:
            return out('**That can\'t happen**: with ' + hyp[1].strip() + ', no arrangement fits every rule you gave.', 'impossible-if')
        return out('**The statements contradict each other**: no arrangement satisfies all of them.', 'contradiction')
    low = q.lower()
    qm = mentions(q, ents)
    how_many = re.search(r'(?i)\bhow\s+many\s+(?:different\s+|possible\s+|valid\s+)?(?:orders?|ways|arrangements|sequences|schedules|orderings|'
                         r'line-?ups|possibilities|options|seatings)\b', q)
    if how_many:
        if ring:
            return out(f'**{len(sols)}**, counting seatings that are rotations of each other as the same. They are: ' +
                       '; '.join(listing(s) for s in sols[:6]) + ' (going round the table).', 'count')
        return out(f'**{len(sols)}.** The orders that fit every rule: ' + '; '.join(listing(s) for s in sols[:8]) +
                   ('' if len(sols) <= 8 else '; …') + '.', 'count')
    if re.search(r'(?i)\b(?:what|which|the)\s+(?:\w+\s+)?(?:order|sequence|schedule|line-?up|arrangement|ranking|standings)\b|'
                 r'\bin\s+what\s+order\b|\bwhat\s+order\b|\blist\s+(?:them|the)\b|\bhow\s+(?:are|do|should|were)\s+(?:they|the\s+\w+)\s+'
                 r'(?:ordered|arranged|lined\s+up|seated|scheduled)\b', q) and not qm:
        if len(sols) == 1:
            return out(f'**{listing(sols[0])}**' + (' (going round the table).' if ring else ' (first to last).') +
                       ' It is the only arrangement that fits every rule.', 'order')
        return out(f'**It can\'t be fully determined**: {len(sols)} arrangements fit, for example ' +
                   '; '.join(listing(s) for s in sols[:3]) + '.', 'order-open')
    # neighbours: "who/what comes right after X", "who sits next to X", "who is opposite X"
    if qm and re.search(r'(?i)(?:^|,\s*)\s*(?:who|what|which)\b', q):
        x = qm[-1][2]
        tail = q[:qm[-1][0]]
        if not re.search(r'(?i)\b(?:clockwise|opposite|across|next|beside|after|before|behind|ahead|front|follow\w*|preced\w*|left|right)\b', tail):
            tail = q[:qm[-1][0]] + ' ' + q[qm[-1][1]:]
        rel = None
        if ring and re.search(r'(?i)\b(?:counter-?clockwise|anti-?clockwise)\b', tail):
            rel = 'before'
        elif ring and re.search(r'(?i)\bclockwise\b', tail):
            rel = 'after'
        elif ring and re.search(r'(?i)\bleft\b', tail) and not NEXT_TO.search(tail):
            rel = 'after'
        elif ring and re.search(r'(?i)\bright\b', tail) and not NEXT_TO.search(tail):
            rel = 'before'
        elif OPPOSITE.search(tail):
            rel = 'opp'
        elif NEXT_TO.search(tail):
            rel = 'adj'
        elif re.search(r'(?i)\b(?:after|behind|follows?|following|right\s+of)\b', tail):
            rel = 'after'
        elif re.search(r'(?i)\b(?:before|ahead\s+of|in\s+front\s+of|precedes?|left\s+of)\b', tail):
            rel = 'before'
        if rel and len(qm) == 1:
            vals = set()
            for s in sols:
                i = s.index(x)
                if rel == 'adj':
                    nb = [s[(i + d) % n] for d in (-1, 1) if ring or 0 <= i + d < n]
                    vals.add(' and '.join(sorted(set(nb))))
                elif rel == 'opp':
                    if not ring or n % 2:
                        return None
                    vals.add(s[(i + n // 2) % n])
                else:
                    j = i + (1 if rel == 'after' else -1)
                    if ring:
                        vals.add(s[j % n])
                    elif 0 <= j < n:
                        if re.search(r'(?i)\b(?:immediately|directly|right|straight|just|next)\b', tail) or True:
                            vals.add(s[j])
                    else:
                        vals.add('nothing')
            if len(vals) == 1:
                v = vals.pop()
                return out(f'**{v[0].upper() + v[1:] if v == "nothing" else v}.** ' + why(sols, ring), 'neighbour')
            return out("**It can't be determined**: it could be " + ' or '.join(sorted(vals)) + '. ' + why(sols, ring), 'neighbour-open')
    # which thing is in a place: "which job is first", "who is in the middle", "what is the third task"
    if not ring and re.match(r'(?i)\s*(?:who|what|which)\b', q) and not qm:
        k = None
        m = POS_ORD.search(q)
        if m:
            k = ORD.get((m[1] or '').lower()) or int(m[2])
        elif POS_MIDDLE.search(q):
            k = (n + 1) // 2 if n % 2 else None
        elif POS_FIRST.search(q) or re.search(r'(?i)\b(?:won|win|winner)\b', q):
            k = 1
        elif POS_LAST.search(q) or re.search(r'(?i)\b(?:loser|lost)\b', q):
            k = n
        if k and 1 <= k <= n:
            vals = sorted({s[k - 1] for s in sols})
            if MAY.search(q) and not MUST.search(q):
                if len(vals) == 1:
                    return out(f'**Only {vals[0]}.** ' + why(sols, ring), 'which-could')
                return out(f'**{" or ".join(vals)}.** ' + why(sols, ring), 'which-could')
            if len(vals) == 1:
                return out(f'**{vals[0]}.** ' + why(sols, ring), 'which')
            return out(f"**It can't be determined**: it could be " + ' or '.join(vals) + '. ' + why(sols, ring), 'which-open')
    # where is X
    m = re.search(r'(?i)\b(?:where|what\s+(?:position|place|spot|slot|number|step)|which\s+(?:position|place|spot|slot|step))\b', q)
    if m and len(qm) == 1 and not ring:
        x = qm[0][2]
        ks = sorted({s.index(x) + 1 for s in sols})
        if len(ks) == 1:
            return out(f'**{x} is {pos_name(ks[0], n)}.** ' + why(sols, ring), 'where')
        return out(f"**It can't be determined**: {x} could be " + ' or '.join(pos_name(k, n) for k in ks) + '. ' + why(sols, ring), 'where-open')
    # yes/no about a fact: "could paint be first?", "must A sit next to B?", "is X before Y?"
    if re.match(r'(?i)\s*(?:could|can|must|might|may|does|do|is|are|will|would|should|has|have|did|was|were|is\s+it)\b', q) and qm:
        body = strip_q(q)
        try:
            test = read_facts(body + '.', ents)
        except Unread:
            return None
        if not test:
            return None
        fs = [f for f, _ in test]
        try:
            ok = [s for s in sols if all(holds(f, {e: i for i, e in enumerate(s)}, n, ring) for f in fs)]
        except Unread:
            return None
        some, every = bool(ok), len(ok) == len(sols)
        if MAY.search(q) and not MUST.search(q):
            if some:
                return out(f'**Yes.** For example: {listing(ok[0])}' + (' (round the table)' if ring else '') + ' fits every rule.', 'could')
            return out('**No.** ' + why(sols, ring) + ' None of them has that.', 'could-not')
        if MUST.search(q):
            if every:
                return out('**Yes, it has to.** ' + why(sols, ring) + ' Every one of them has that.', 'must')
            if some:
                return out(f'**No, not necessarily.** It can happen ({listing(ok[0])}) but it doesn\'t have to '
                           f'({listing(next(s for s in sols if s not in ok))}).', 'must-not')
            return out('**No — in fact it can\'t happen.** ' + why(sols, ring), 'must-never')
        if every:
            return out('**Yes.** ' + why(sols, ring), 'is')
        if not some:
            return out('**No.** ' + why(sols, ring), 'is-not')
        return out(f"**It can't be determined** from what you said: it holds in {listing(ok[0])} but not in "
                   f"{listing(next(s for s in sols if s not in ok))}.", 'is-open')
    return None


def why(sols, ring):
    if len(sols) == 1:
        return 'The only arrangement that fits every rule is ' + listing(sols[0]) + (' (going round the table).' if ring else ' (first to last).')
    if len(sols) <= 4:
        return f'The arrangements that fit every rule are ' + '; '.join(listing(s) for s in sols) + '.'
    return f'{len(sols)} arrangements fit every rule.'


# ------------------------------------------------------------------ matching people to things
def read_links(text, groups):
    """[(kind, a, b)] with kind 'same' or 'diff' between things of different groups; raises Unread on relation words."""
    ents = [e for g in groups for e in g]
    gid = {e: i for i, g in enumerate(groups) for e in g}
    links = []
    for c in clauses(text):
        if c.endswith('?'):
            continue
        ms = mentions(c, ents)
        if len(ms) < 2:
            continue
        kinds = {gid[m[2]] for m in ms}
        if len(kinds) < 2:
            continue
        if any(len({m[2] for m in ms if gid[m[2]] == k}) == len(groups[k]) for k in kinds):
            continue        # the sentence that introduces the lists
        if re.search(r'(?i)\b(?:before|after|left|right|next to|beside|taller|older|younger|more|less|than)\b', c):
            raise Unread
        neg = bool(NEG.search(c)) or bool(re.search(r'(?i)\bneither\b|\bnor\b', c))
        either = re.search(r'(?i)\beither\b|\bor\b', c) and not re.search(r'(?i)\bnor\b', c)
        by = {}
        for m in ms:
            by.setdefault(gid[m[2]], []).append(m[2])
        ks = sorted(by)
        if len(ks) != 2:
            raise Unread
        a_list, b_list = by[ks[0]], by[ks[1]]
        if either and not neg and (len(a_list) > 1 or len(b_list) > 1):
            links.append(('oneof', a_list, b_list))
            continue
        for a in a_list:
            for b in b_list:
                links.append(('diff' if neg else 'same', a, b))
    return links


def ask_match(q, groups, links):
    people = groups[0]
    n = len(people)
    gid = {e: i for i, g in enumerate(groups) for e in g}
    sols = []

    def rec(i, assign):
        if i == len(groups):
            sols.append([dict(a) for a in assign])
            return
        for perm in permutations(groups[i]):
            assign.append(dict(zip(people, perm)))
            if ok(assign):
                rec(i + 1, assign)
            assign.pop()

    def owner(assign, e):
        g = gid[e]
        if g == 0:
            return e
        if g >= len(assign):
            return None
        return next(p for p, v in assign[g].items() if v == e)

    def ok(assign):
        for link in links:
            if link[0] == 'oneof':
                _, al, bl = link
                pairs = [(a, b) for a in al for b in bl]
                vals = [(owner(assign, a), owner(assign, b)) for a, b in pairs]
                if any(None in v for v in vals):
                    continue
                if not any(x == y for x, y in vals):
                    return False
                continue
            kind, a, b = link
            oa, ob = owner(assign, a), owner(assign, b)
            if oa is None or ob is None:
                continue
            if (oa == ob) != (kind == 'same'):
                return False
        return True

    rec(1, [{p: p for p in people}])
    if len(sols) > 2000:
        return None
    if not sols:
        return out('**The clues contradict each other**: no way of matching fits all of them.', 'match-contradiction')
    qm = mentions(q, [e for g in groups for e in g])
    if not qm:
        if re.search(r'(?i)\bwho\s+has\s+what\b|\bwhat\s+does\s+each\b|\bmatch\b|\beach\s+(?:person|one)\b', q):
            if len(sols) == 1:
                return out('**' + '; '.join(f'{p}: ' + ', '.join(sols[0][g][p] for g in range(1, len(groups))) for p in people) + '.**', 'match-all')
            return out(f"**It can't be fully determined**: {len(sols)} matchings fit the clues.", 'match-open')
        return None
    x = qm[-1][2]
    g = gid[x]
    if g == 0:
        tgt = None
        for gi in range(1, len(groups)):      # which group the question asks about: the one whose noun appears, else the only one
            if len(groups) == 2:
                tgt = 1
        if tgt is None:
            return None
        vals = sorted({s[tgt][x] for s in sols})
    else:
        def own(s, e):
            return next(p for p, v in s[g].items() if v == e)
        if re.match(r'(?i)\s*who\b', q) or re.search(r'(?i)\bwhich\s+(?:person|one|friend|child|student|of\s+them)\b', q):
            vals = sorted({own(s, x) for s in sols})
        elif len(groups) == 3:
            other = 2 if g == 1 else 1
            vals = sorted({s[other][own(s, x)] for s in sols})
        else:
            return None
    if len(vals) == 1:
        return out(f'**{vals[0]}.** ' + ('It is the only matching that fits every clue.' if len(sols) == 1 else
                                         f'Every matching that fits the clues agrees on this.'), 'match')
    return out("**It can't be determined**: it could be " + ' or '.join(vals) + '.', 'match-open')


# ------------------------------------------------------------------ entry point
def respond(messages):
    users = [(m.get('content') or '').strip() for m in messages if m.get('role') == 'user']
    if not users or not users[-1]:
        return None
    last = users[-1]
    qs = re.findall(r'[^.!?\n]*\?', last)
    if not qs:
        return None
    q = qs[-1].strip()
    text = '\n'.join(users[-5:])
    facts_text = re.sub(r'[^.!?\n]*\?', ' ', text)
    try:
        from .constraint_logic import normalise
        facts_text, q = normalise(facts_text), normalise(q)
    except Exception:
        pass
    lists = lists_in(facts_text)
    ring = bool(RING.search(text))
    # matching: two or three lists of the same size, and "each"/"different"
    same = [l for l in lists if len(l) == len(lists[0])] if lists else []
    if len(same) >= 2 and MATCHING.search(facts_text) and 2 <= len(same[0]) <= 5:
        groups = same[:3]
        caps = [g for g in groups if all(x[0].isupper() for x in g)]
        if caps:
            groups = [caps[0]] + [g for g in groups if g is not caps[0]]
        if len({e.lower() for g in groups for e in g}) != sum(len(g) for g in groups):
            return None
        try:
            links = read_links(facts_text, groups)
        except Unread:
            return None
        if not links:
            return None
        return ask_match(q, groups, links)
    ents = None
    if lists:
        ents = max(lists, key=len)
        if len(lists) > 1 and len(lists[-1]) == len(ents):
            return None
    else:
        caps = caps_names(facts_text)
        ents = [e for e in caps if any((RELWORD.search(c) or CLOCKWISE.search(c)) and mention_re(e).search(c) for c in clauses(facts_text))]
        said = re.search(r'(?i)\b(two|three|four|five|six)\s+(?:\w+\s+)?(?:stools|seats|chairs|people|places|friends|runners|kids|children|guests|players)\b', text)
        if said and NUMW[said[1].lower()] == len(ents) + 1:
            new = [e for e in caps_names(q) if e not in ents]
            if len(new) == 1:
                ents.append(new[0])
    if not ents or not 2 <= len(ents) <= 7:
        return None
    try:
        facts = read_facts(facts_text, ents)
    except Unread:
        return None
    if not facts:
        return None
    try:
        return ask_line(q, ents, facts, ring)
    except Unread:
        return None
