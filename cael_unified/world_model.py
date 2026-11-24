"""A story world model (non-neural): read short narrative statements into a state, then answer questions about it.

Statements become events: people move (went, moved, journeyed, travelled, ran, headed, returned ...), take objects
(got, grabbed, took, picked up ...), put them down (dropped, put down, discarded, left ...) or give them to someone
(gave, handed, passed); pronouns and "then" refer back to the last subject; time words (yesterday, this morning ...)
order events; "X is a Y", "Ys are afraid of Zs", "X is white" are facts; "the A is north of the B" builds a map;
"X is hungry" is a motivation. Questions about places (now, before, either/or), possession, counts, giving, facts,
categories, routes and reasons are answered from that state.

It answers only when it understood the whole story and the question; otherwise it stays silent.
"""
import re
from collections import defaultdict, deque

MOVE = r'(?:went|moved|journeyed|travell?ed|ran|walked|headed|drove|flew|returned|came|got|hurried|rushed|wandered|strolled|cycled|jogged)'
TAKE = r'(?:got|grabbed|took|picked up|picked|collected|fetched|obtained|lifted|snatched)'
DROP = r'(?:dropped|put down|discarded|left|put|placed|set down|threw away|threw|abandoned)'
GIVE = r'(?:gave|handed|passed|offered|delivered|sent)'
TIME_ORDER = {'yesterday': 0, 'this morning': 1, 'this afternoon': 2, 'this evening': 3, 'tonight': 4}
DIRS = {'north': 'n', 'south': 's', 'east': 'e', 'west': 'w'}
OPP = {'north': 'south', 'south': 'north', 'east': 'west', 'west': 'east'}
NUMW = ['none', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten']
PRONOUNS = {'he', 'she', 'they', 'him', 'her', 'them'}
MOTIVE_PLACE = {'hungry': 'kitchen', 'thirsty': 'kitchen', 'tired': 'bedroom', 'bored': 'garden', 'sleepy': 'bedroom'}
MOTIVE_OBJ = {'hungry': 'apple', 'thirsty': 'milk', 'tired': 'pajamas', 'bored': 'football', 'sleepy': 'pajamas'}
ART = r'(?:the |a |an |his |her |their )?'
NAME = r'([A-Za-z][a-z]+)'


def norm(w):
    w = w.strip().lower()
    return re.sub(r'^(?:the|a|an|his|her|their)\s+', '', w)


IRREGULAR = {'mice': 'mouse', 'geese': 'goose', 'sheep': 'sheep', 'wolves': 'wolf', 'people': 'person', 'men': 'man',
             'women': 'woman', 'children': 'child', 'feet': 'foot', 'teeth': 'tooth', 'oxen': 'ox', 'deer': 'deer'}


def singular(w):
    w = norm(w)
    if w in IRREGULAR:
        return IRREGULAR[w]
    if w.endswith('ies'):
        return w[:-3] + 'y'
    if w.endswith('ves'):
        return w[:-3] + 'f'
    if w.endswith('es') and w[:-2].endswith(('s', 'x', 'ch', 'sh')):
        return w[:-2]
    if w.endswith('s') and not w.endswith('ss'):
        return w[:-1]
    return w


class World:
    def __init__(self):
        self.loc = defaultdict(list)        # person -> [(t, place)] ; place may be ('not', p) or ('either', p, q)
        self.holder = {}                    # object -> person or None
        self.obj_loc = defaultdict(list)    # object -> [(t, place)]
        self.carry = defaultdict(list)      # person -> objects, in order
        self.gives = []                     # (t, giver, obj, receiver)
        self.isa = {}                       # name -> kind
        self.fear = {}                      # kind -> feared kind
        self.attr = defaultdict(dict)       # name -> {attribute kind: value}
        self.mood = {}                      # person -> motive
        self.moves = []                     # (t, person, place)
        self.takes = []                     # (t, person, obj)
        self.edges = defaultdict(dict)      # place -> {direction: place}
        self.t = 0
        self.last = []                      # last subject(s)
        self.people = set()

    # ---------------------------------------------------------------- statements
    def subjects(self, s):
        s = s.strip()
        if s.lower() in PRONOUNS:
            return list(self.last)
        parts = re.split(r'\s+and\s+', s)
        names = [p.strip() for p in parts]
        if all(re.fullmatch(r'[A-Z][a-z]+', n) for n in names):
            return [n.lower() for n in names]
        return None

    def person_at(self, p, place, t):
        self.loc[p].append((t, place))
        if isinstance(place, str):
            self.moves.append((t, p, place))
            for o in self.carry[p]:
                self.obj_loc[o].append((t, place))

    def read(self, sent):
        s = sent.strip().rstrip('.!').strip()
        if not s:
            return True
        t = self.t
        m = re.match(r'(?i)^(yesterday|this morning|this afternoon|this evening|tonight),?\s+(.*)$', s)
        if m:
            t = TIME_ORDER[m.group(1).lower()] * 1000 + self.t
            s = m.group(2)
        s = re.sub(r'(?i)^(?:then|after that|afterwards|following that|next|later|finally)\s*,?\s+', '', s)
        m = re.match(r'(?i)^(.*?),?\s+(yesterday|this morning|this afternoon|this evening|tonight)$', s)   # time word at the end
        if m:
            t = TIME_ORDER[m.group(2).lower()] * 1000 + self.t
            s = m.group(1)
        self.t += 1
        # movement
        m = re.match(rf'(?i)^(.+?)\s+{MOVE}(?:\s+back)?\s+(?:to|into|towards?)\s+{ART}(\w+)$', s)
        if m and self.subjects(m.group(1)):
            ps = self.subjects(m.group(1))
            for p in ps:
                self.people.add(p)
                self.person_at(p, norm(m.group(2)), t)
            self.last = ps
            return True
        m = re.match(rf'(?i)^(.+?)\s+is\s+(no longer|not)\s+in\s+{ART}(\w+)$', s)
        if m and self.subjects(m.group(1)):
            for p in self.subjects(m.group(1)):
                self.people.add(p)
                self.loc[p].append((t, ('not', norm(m.group(3)))))
            self.last = self.subjects(m.group(1))
            return True
        m = re.match(rf'(?i)^(.+?)\s+is\s+either\s+in\s+{ART}(\w+)\s+or\s+{ART}(\w+)$', s)
        if m and self.subjects(m.group(1)):
            for p in self.subjects(m.group(1)):
                self.people.add(p)
                self.loc[p].append((t, ('either', norm(m.group(2)), norm(m.group(3)))))
            self.last = self.subjects(m.group(1))
            return True
        m = re.match(rf'(?i)^(.+?)\s+(?:is|are)\s+(?:in|at)\s+{ART}(\w+)$', s)
        if m and self.subjects(m.group(1)) and not re.match(r'(?i)^the\b', m.group(1)):
            for p in self.subjects(m.group(1)):
                self.people.add(p)
                self.person_at(p, norm(m.group(2)), t)
            self.last = self.subjects(m.group(1))
            return True
        # giving
        m = re.match(rf'(?i)^(.+?)\s+{GIVE}\s+{ART}(\w+)\s+to\s+(\w+)$', s) or None
        if m and self.subjects(m.group(1)):
            g, o, r = self.subjects(m.group(1))[0], norm(m.group(2)), self.subjects(m.group(3))
            if r:
                return self.give(t, g, o, r[0])
        m = re.match(rf'(?i)^(.+?)\s+{GIVE}\s+(\w+)\s+{ART}(\w+)$', s)
        if m and self.subjects(m.group(1)) and self.subjects(m.group(2)):
            return self.give(t, self.subjects(m.group(1))[0], norm(m.group(3)), self.subjects(m.group(2))[0])
        # taking and dropping
        m = re.match(rf'(?i)^(.+?)\s+{TAKE}\s+{ART}(\w+)(?:\s+(?:up|there|from\s+.*))?$', s)
        if m and self.subjects(m.group(1)):
            p = self.subjects(m.group(1))[0]
            o = norm(m.group(2))
            self.people.add(p)
            self.holder[o] = p
            if o not in self.carry[p]:
                self.carry[p].append(o)
            here = self.where(p)
            if here:
                self.obj_loc[o].append((t, here))
            self.takes.append((t, p, o))
            self.last = [p]
            return True
        m = re.match(rf'(?i)^(.+?)\s+{DROP}\s+(?:down\s+)?{ART}(\w+)(?:\s+(?:down|there|here|away))?$', s)
        if m and self.subjects(m.group(1)):
            p = self.subjects(m.group(1))[0]
            o = norm(m.group(2))
            self.people.add(p)
            if o in self.carry[p]:
                self.carry[p].remove(o)
            self.holder[o] = None
            here = self.where(p)
            if here:
                self.obj_loc[o].append((t, here))
            self.last = [p]
            return True
        # spatial map
        m = re.match(rf'(?i)^(?:the\s+)?(\w+)\s+is\s+(north|south|east|west)\s+of\s+(?:the\s+)?(\w+)$', s)
        if m:
            a, d, b = norm(m.group(1)), m.group(2).lower(), norm(m.group(3))
            self.edges[b][d] = a
            self.edges[a][OPP[d]] = b
            return True
        # facts
        m = re.match(r'(?i)^(\w+)s?\s+are\s+afraid\s+of\s+(\w+)$', s)
        if m:
            self.fear[singular(m.group(1))] = singular(m.group(2))
            return True
        m = re.match(r'(?i)^(\w+)\s+is\s+afraid\s+of\s+(\w+)$', s)
        if m:
            self.fear[singular(m.group(1))] = singular(m.group(2))
            return True
        m = re.match(r'(?i)^(\w+)\s+is\s+(hungry|thirsty|tired|bored|sleepy)$', s)
        if m:
            p = m.group(1).lower()
            self.mood[p] = m.group(2).lower()
            self.people.add(p)
            self.last = [p]
            return True
        m = re.match(r'(?i)^(\w+)\s+is\s+an?\s+(\w+)$', s)
        if m:
            self.isa[m.group(1).lower()] = singular(m.group(2))
            return True
        m = re.match(r'(?i)^(\w+)\s+is\s+(white|gray|grey|green|yellow|red|blue|black|brown|pink|orange|purple)$', s)
        if m:
            self.attr[m.group(1).lower()]['color'] = m.group(2).lower()
            return True
        return False

    def give(self, t, g, o, r):
        self.people.update((g, r))
        if o in self.carry[g]:
            self.carry[g].remove(o)
        if o not in self.carry[r]:
            self.carry[r].append(o)
        self.holder[o] = r
        self.gives.append((t, g, o, r))
        self.last = [g]
        return True

    # ---------------------------------------------------------------- state queries
    def history(self, p):
        return [x for _, x in sorted(self.loc.get(p, []), key=lambda e: e[0])]

    def where(self, p):
        h = self.history(p)
        return h[-1] if h and isinstance(h[-1], str) else None

    def obj_where(self, o):
        h = self.holder.get(o)
        if h:
            return self.where(h)
        hist = sorted(self.obj_loc.get(o, []), key=lambda e: e[0])
        return hist[-1][1] if hist else None

    def route(self, a, b):
        prev = {a: None}
        q = deque([a])
        while q:
            x = q.popleft()
            if x == b:
                break
            for d, y in self.edges.get(x, {}).items():
                if y not in prev:
                    prev[y] = (x, d)
                    q.append(y)
        if b not in prev:
            return None
        path = []
        while prev[b]:
            x, d = prev[b]
            path.append(d)
            b = x
        return path[::-1]


def answer(world, q):
    """The answer text for question q, or None."""
    s = q.strip().rstrip('?').strip()
    low = s.lower()
    m = re.match(r'(?i)^where\s+(?:is|was)\s+(?:the\s+)?(\w+)\s+before\s+(?:the\s+)?(\w+)$', s)
    if m:
        x, before = norm(m.group(1)), norm(m.group(2))
        hist = [p for p in world.history(x) if isinstance(p, str)] if x in world.people else \
               [p for _, p in sorted(world.obj_loc.get(x, []), key=lambda e: e[0])]
        dedup = [p for i, p in enumerate(hist) if i == 0 or p != hist[i - 1]]
        if before in dedup:
            i = len(dedup) - 1 - dedup[::-1].index(before)
            if i > 0:
                return dedup[i - 1]
        return None
    m = re.match(r'(?i)^where\s+is\s+(?:the\s+)?(\w+)$', s)
    if m:
        x = norm(m.group(1))
        if x in world.people:
            return world.where(x)
        return world.obj_where(x)
    m = re.match(r'(?i)^is\s+(\w+)\s+(?:in|at)\s+(?:the\s+)?(\w+)$', s)
    if m:
        p, place = m.group(1).lower(), norm(m.group(2))
        h = world.history(p)
        if not h:
            return None
        last = h[-1]
        if isinstance(last, str):
            return 'yes' if last == place else 'no'
        if last[0] == 'not':
            return 'no' if last[1] == place else 'maybe'
        if last[0] == 'either':
            return 'maybe' if place in last[1:] else 'no'
    m = re.match(r'(?i)^how many objects is (\w+) carrying$', s)
    if m:
        n = len(world.carry.get(m.group(1).lower(), []))
        return NUMW[n] if n < len(NUMW) else str(n)
    m = re.match(r'(?i)^what is (\w+) (?:carrying|holding)$', s)
    if m:
        c = world.carry.get(m.group(1).lower(), [])
        return ','.join(c) if c else 'nothing'
    m = re.match(r'(?i)^who gave (?:the\s+)?(\w+) to (\w+)$', s)
    if m:
        o, r = norm(m.group(1)), m.group(2).lower()
        hits = [g for _, g, oo, rr in sorted(world.gives) if oo == o and rr == r]
        return hits[-1].capitalize() if hits else None
    m = re.match(r'(?i)^who did (\w+) give (?:the\s+)?(\w+) to$', s)
    if m:
        g, o = m.group(1).lower(), norm(m.group(2))
        hits = [r for _, gg, oo, r in sorted(world.gives) if gg == g and oo == o]
        return hits[-1].capitalize() if hits else None
    m = re.match(r'(?i)^what did (\w+) give to (\w+)$', s)
    if m:
        g, r = m.group(1).lower(), m.group(2).lower()
        hits = [o for _, gg, o, rr in sorted(world.gives) if gg == g and rr == r]
        return hits[-1] if hits else None
    m = re.match(r'(?i)^who (?:received|got) (?:the\s+)?(\w+)$', s)
    if m:
        o = norm(m.group(1))
        hits = [r for _, _, oo, r in sorted(world.gives) if oo == o]
        return hits[-1].capitalize() if hits else None
    m = re.match(r'(?i)^who gave (?:the\s+)?(\w+)$', s)
    if m:
        o = norm(m.group(1))
        hits = [g for _, g, oo, _ in sorted(world.gives) if oo == o]
        return hits[-1].capitalize() if hits else None
    m = re.match(r'(?i)^what (?:is|are) (\w+) afraid of$', s)
    if m:
        x = m.group(1).lower()
        kind = world.isa.get(x, singular(x))
        f = world.fear.get(kind)
        return f
    m = re.match(r'(?i)^what colou?r is (\w+)$', s)
    if m:
        x = m.group(1).lower()
        if 'color' in world.attr.get(x, {}):
            return world.attr[x]['color']
        kind = world.isa.get(x)
        if kind:
            seen = [world.attr[o]['color'] for o, k in world.isa.items() if k == kind and o != x and 'color' in world.attr.get(o, {})]
            return seen[-1] if seen else None
        return None
    m = re.match(r'(?i)^how do you go from (?:the\s+)?(\w+) to (?:the\s+)?(\w+)$', s)
    if m:
        r = world.route(norm(m.group(1)), norm(m.group(2)))
        return ' '.join(r) if r else None
    m = re.match(r'(?i)^what is (?:the\s+)?(\w+) (north|south|east|west) of$', s)
    if m:
        return world.edges.get(norm(m.group(1)), {}).get(OPP[m.group(2).lower()])   # "the kitchen is east of X"
    m = re.match(r'(?i)^what is (north|south|east|west) of (?:the\s+)?(\w+)$', s)
    if m:
        return world.edges.get(norm(m.group(2)), {}).get(m.group(1).lower())
    m = re.match(r'(?i)^why did (\w+) (?:go|went|move|journey|travel|run|head) (?:back )?to (?:the\s+)?(\w+)$', s) or \
        re.match(r'(?i)^why did (\w+) (?:get|grab|take|pick up) (?:the\s+)?(\w+)$', s)
    if m:
        return world.mood.get(m.group(1).lower())
    m = re.match(r'(?i)^where will (\w+) go$', s)
    if m:
        return MOTIVE_PLACE.get(world.mood.get(m.group(1).lower(), ''))
    return None


def split_story(text):
    lines = [l.strip() for l in re.split(r'(?<=[.!?])\s+|\n+', text.strip()) if l.strip()]
    if len(lines) < 2 or not lines[-1].endswith('?'):
        return None, None
    return lines[:-1], lines[-1]


def reply(text, messages=None):
    statements, question = split_story(text)
    if not statements:
        return None
    world = World()
    understood = sum(world.read(s) for s in statements)
    if understood < len(statements) or understood < 1:
        return None
    a = answer(world, question)
    if a is None:
        return None
    return {'response': a[0].upper() + a[1:] if a and not a.islower() else a, 'route': 'chat/world-model', 'confidence': 0.85}
