"""Swarm memory: many small CAEL agents share what they read, with no central database and no voting.

Each agent reads part of a story, a document or a conversation and sends what it found as claims: "the lamp's colour
is red, at step 3 of part 2, I read it". This module answers three questions about those claims.

1. Who is who (referent binding). Agents name things as they saw them: "Dr. Sam Lee", "Sam", "Lee". Names are joined
   by fixed rules: an agent's explicit "these are the same" link always joins. A short name joins the one longer name
   it is part of, but only when exactly one longer name fits and no agent said the two are different. When two longer
   names fit, the short one stays apart and the view reports it as ambiguous. Pronouns are not allowed on the wire:
   an agent resolves "she" itself before it sends a claim.

2. What is true when agents disagree (consensus). There are no votes, so a hundred copies of one mistake do not beat
   one correct reading. The rules, in order:
     - An agent's own correction replaces its earlier claim. A correction has the same position and a higher clock.
     - Evidence kind decides next: something stated beats something derived, which beats something retrieved from a
       search, which beats a default.
     - Then position in the shared timeline: a later reading beats an earlier one, because the world changed.
     - Changes ("gains 2") apply on top of the latest absolute value before them, whichever agent saw which part.
     - Two different values at the same rank and the same position are a conflict. The view reports both sides with
       their agents. It never picks one.
   Rules ("every cat is black") from one agent apply to facts from another ("Felix is a cat"). A derived value never
   overrides a stated one. When they disagree, the view reports it as a rule exception.

3. Shared state without a central store (merging). A state is three grow-only sets: claims, links and rules. Merging
   two states is set union, so merging is commutative, associative and idempotent. Agents can gossip in any order,
   any number of times, and all of them reach the same view. The view is computed from the sets on reading, so
   arrival order never matters. summary() drops only claims that can never matter again: an agent's superseded
   claims, lower-kind claims under a stated one, and changes made before a later stated value. A tree of nodes can
   therefore merge and summarise level by level, and the root gives exactly the view of merging every claim flat.

No model is involved: this is plain sets, sorting and fractions.
"""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import cached_property
from fractions import Fraction
import hashlib
import re

RANK = {'confirmed': 5, 'trusted': 4, 'stated': 3, 'derived': 2, 'retrieved': 1, 'doubted': 1, 'default': 0}
TOP = max(RANK.values())
OPS = ('set', 'add', 'subtract')
TITLES = {'dr', 'mr', 'mrs', 'ms', 'miss', 'prof', 'sir', 'dame', 'the', 'a', 'an', 'my', 'our', 'your'}
PRONOUNS = {'he', 'she', 'it', 'they', 'him', 'her', 'them', 'his', 'hers', 'its', 'their', 'this', 'that', 'i', 'you',
            'we', 'me', 'us'}
MAX_RULE_ROUNDS = 64
DESCRIPTION_WORDS = {'in', 'with', 'of', 'on', 'at', 'from', 'who', 'that', 'wearing', 'the', 'a', 'an'}


def norm(name):
    """The key a name is filed under: 'Dr. Sam Lee' -> 'sam lee'."""
    words = re.findall(r"[a-z0-9]+(?:'[a-z]+)?", str(name).casefold())
    while words and words[0] in TITLES:
        words = words[1:]
    return ' '.join(words)


def norm_attr(attribute):
    """'Apples' and 'apple' are one attribute ('glasses', 'status' and 'gas' stay as they are)."""
    words = re.findall(r'[a-z0-9]+', str(attribute).casefold())
    if words and len(words[-1]) > 3 and words[-1].endswith('s') and not re.search(r'(?:ss|us|is)$', words[-1]):
        words[-1] = words[-1][:-3] + 'y' if words[-1].endswith('ies') else words[-1][:-1]
    return ' '.join(words)


@dataclass(frozen=True)
class Claim:
    entity: str
    attribute: str
    value: str
    agent: str
    clock: int = 0                 # the agent's own counter: a higher clock at the same position is its correction
    kind: str = 'stated'           # stated / derived / retrieved / default
    at: tuple = ()                 # position in the shared timeline, e.g. (part, step); () is timeless (earliest)
    op: str = 'set'                # set, or a change: add / subtract
    evidence: str = ''             # the words it came from, for the explanation

    def __post_init__(self):
        if self.kind not in RANK:
            raise ValueError('unknown evidence kind: ' + str(self.kind))
        if self.op not in OPS:
            raise ValueError('unknown operation: ' + str(self.op))
        if self.op != 'set' and self.kind != 'stated':
            raise ValueError('only a stated claim can be a change')
        if not norm(self.entity) or norm(self.entity) in PRONOUNS:
            raise ValueError('an agent resolves pronouns before it sends a claim: ' + repr(self.entity))
        if not norm_attr(self.attribute):
            raise ValueError('a claim needs an attribute')
        if not all(isinstance(x, int) for x in self.at):
            raise ValueError('a position is a tuple of whole numbers')

    @property
    def key(self):
        return norm(self.entity), norm_attr(self.attribute)

    @cached_property
    def id(self):
        raw ='\x1f'.join(map(str, (self.key, self.value, self.agent, self.clock, self.kind, self.at, self.op)))
        return hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]


@dataclass(frozen=True)
class Link:
    a: str
    b: str
    relation: str                  # same / distinct
    agent: str
    clock: int = 0                 # an agent's later link about the same description is its correction

    def __post_init__(self):
        if self.relation not in ('same', 'distinct', 'retract'):
            raise ValueError('a link is same, distinct or retract')
        if norm(self.a) in PRONOUNS or norm(self.b) in PRONOUNS or not norm(self.a) or not norm(self.b):
            raise ValueError('a link names two things, not pronouns')

    @property
    def pair(self):
        return tuple(sorted((norm(self.a), norm(self.b))))


@dataclass(frozen=True)
class Rule:
    """Whatever has if_attribute == if_value also has then_attribute == then_value ("every cat is black")."""
    if_attribute: str
    if_value: str
    then_attribute: str
    then_value: str
    agent: str

    @property
    def parts(self):
        return (norm_attr(self.if_attribute), value_key(self.if_value), norm_attr(self.then_attribute), value_key(self.then_value))


def value_key(value):
    """Values compare by meaning: '3', '3.0' and '6/2' are one number; 'The Kitchen' and 'kitchen' are one place."""
    text = str(value).strip()
    try:
        return str(Fraction(text))
    except (ValueError, ZeroDivisionError):
        return norm(text) or text.casefold()


@dataclass
class Cell:
    status: str                    # known / conflict / unknown
    value: object = None
    support: tuple = ()            # agents whose claims give the value
    sides: dict = field(default_factory=dict)     # value -> agents, for a conflict
    derived: tuple = ()            # rules and facts behind a derived value
    note: str = ''


class State:
    """What one node knows. Merging is set union; nothing is ever edited in place except by adding."""

    def __init__(self, claims=(), links=(), rules=()):
        self.claims = set(claims)
        self.links = set(links)
        self.rules = set(rules)

    def add(self, *items):
        for item in items:
            {Claim: self.claims, Link: self.links, Rule: self.rules}[type(item)].add(item)
        return self

    def merge(self, other):
        self.claims |= other.claims
        self.links |= other.links
        self.rules |= other.rules
        return self

    def copy(self):
        return State(self.claims, self.links, self.rules)

    def __len__(self):
        return len(self.claims) + len(self.links) + len(self.rules)

    def __eq__(self, other):
        return isinstance(other, State) and (self.claims, self.links, self.rules) == (other.claims, other.links, other.rules)

    def summary(self):
        """A smaller state with the same view, now and after any later merge (see the module notes). A claim is dropped
        only when the claims beside it rule it out, and more claims never bring it back, so summarising in any order
        or grouping gives the same set as summarising everything at once."""
        kept = set()
        for group in live(self.claims, by=lambda c: c.key).values():
            values = [c for c in group if c.op == 'set']
            top = max((RANK[c.kind] for c in values), default=None)
            # A cell's base is chosen among its highest-ranked values, and that rank only rises as claims arrive. A
            # change is placed after the latest of them; that point only moves later once nothing can outrank them.
            last = max((c.at for c in values if RANK[c.kind] == TOP), default=None)
            for c in group:
                if c.op == 'set' and RANK[c.kind] < top:
                    continue                    # a higher-ranked value for this name always outranks it
                if c.op != 'set' and last is not None and c.at <= last:
                    continue                    # a change made before a later top-ranked value never applies again
                kept.add(c)
        return State(kept, self.links, self.rules)

    def view(self):
        return View(self)


def live(claims, by):
    """Each agent's latest word per position: a correction (higher clock, same position, kind and operation) replaces
    the earlier claim. Returns {by(claim): [claims]}."""
    latest = {}
    for c in claims:
        slot = (by(c), c.agent, c.kind, c.op, c.at)
        if slot not in latest or (c.clock, c.id) > (latest[slot].clock, latest[slot].id):
            latest[slot] = c
    groups = defaultdict(list)
    for slot, c in latest.items():
        groups[slot[0]].append(c)
    return groups


def live_links(links):
    """Each agent's latest word about each description: "The driver was Sam", then "Actually the driver was Tom" (or "the
    driver was not Sam") from the same agent, keeps only the correction. Withdrawn links bind nothing, so every
    conclusion that rested on them is recomputed without them."""
    latest = {}
    for link in links:
        key = (link.agent, norm(link.a))
        if key not in latest or (link.clock, link.relation, link.pair) > (latest[key].clock, latest[key].relation, latest[key].pair):
            latest[key] = link
    return set(latest.values())


class Binding:
    """Which names are one thing. Computed from the whole set every time, so it does not depend on arrival order."""

    def __init__(self, names, links):
        links = live_links(links)
        self.parent = {n: n for n in names}
        self.notes = []
        for link in links:
            for n in link.pair:
                self.parent.setdefault(n, n)
        distinct = defaultdict(set)
        for link in sorted(links, key=lambda l: (l.pair, l.relation, l.agent)):
            if link.relation == 'distinct':
                a, b = link.pair
                distinct[a].add(b)
                distinct[b].add(a)
        self.members = {n: {n} for n in self.parent}
        for link in sorted(links, key=lambda l: (l.pair, l.agent)):
            if link.relation == 'same':
                a, b = link.pair
                if self.clash(a, b, distinct):
                    self.notes.append(f'binding conflict: {link.agent} says {a!r} and {b!r} are the same, another agent says they differ')
                self.union(a, b)
        keys = sorted(self.parent)
        longer = defaultdict(list)
        for k in keys:
            words = k.split()
            if len(words) > 1 and not DESCRIPTION_WORDS & set(words):
                for w in {words[0], words[-1]}:
                    longer[w].append(k)
        for k in keys:
            if len(k.split()) != 1 or k not in longer:
                continue
            fits = sorted({self.find(x) for x in longer[k]} - {self.find(k)})
            if len(fits) > 1:
                self.notes.append(f'ambiguous: {k!r} could be ' + ' or '.join(repr(self.name(f)) for f in fits))
            elif len(fits) == 1:
                if self.clash(k, fits[0], distinct):
                    self.notes.append(f'kept apart: {k!r} and {self.name(fits[0])!r} (an agent said they differ)')
                else:
                    self.union(k, fits[0])

    def find(self, n):
        while self.parent[n] != n:
            self.parent[n] = self.parent[self.parent[n]]
            n = self.parent[n]
        return n

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            ra, rb = sorted((ra, rb))
            self.parent[rb] = ra
            self.members[ra] |= self.members.pop(rb)

    def clash(self, a, b, distinct):
        ma, mb = self.members[self.find(a)], self.members[self.find(b)]
        return any(distinct[x] & mb for x in ma)

    def name(self, n):
        """The fullest name in n's group: 'sam lee' rather than 'sam'."""
        return max(self.members[self.find(n)], key=lambda m: (len(m.split()), len(m), [-ord(ch) for ch in m]))


class View:
    """The swarm's agreed picture: {entity: {attribute: Cell}} plus notes on binding and rules."""

    def __init__(self, state, binding=None):
        # A shard's view uses the binding of the whole swarm (Shards.binding), computed from the shared name directory
        self.binding = binding or Binding({c.key[0] for c in state.claims}, state.links)
        self.notes = list(self.binding.notes)
        self.surface = {}
        for c in sorted(state.claims, key=lambda c: (c.key[0], c.entity)):
            self.surface.setdefault(c.key[0], c.entity)
        cells = live(state.claims, by=lambda c: (self.binding.name(c.key[0]), c.key[1]))
        self.cells = {}
        for (entity, attribute), claims in sorted(cells.items()):
            self.cells.setdefault(entity, {})[attribute] = resolve(claims)
        self.apply_rules(state.rules)

    def apply_rules(self, rules):
        """Derived values are rebuilt from the stated ones every round until nothing changes. A value derived in an earlier
        round is withdrawn when its premise no longer holds (for example when a premise became a conflict), so an
        explanation never rests on a conclusion that is no longer accepted."""
        rules = sorted(rules, key=lambda r: (r.parts, r.agent))
        if not rules:
            return
        base = {e: dict(cells) for e, cells in self.cells.items()}
        derived, notes = {}, []
        for _ in range(MAX_RULE_ROUNDS):
            cells = {e: dict(base.get(e, {}), **derived.get(e, {})) for e in set(base) | set(derived)}
            found = defaultdict(set)            # (entity, attribute) -> {(value, rule agent, if attribute, if value)}
            for rule in rules:
                if_a, if_v, then_a, then_v = rule.parts
                for entity, attributes in cells.items():
                    cell = attributes.get(if_a)
                    if cell and cell.status == 'known' and value_key(cell.value) == if_v:
                        found[entity, then_a].add((then_v, rule.agent, if_a, if_v))
            new, notes = {}, []
            for (entity, attribute), got in sorted(found.items()):
                values = sorted({g[0] for g in got})
                why = tuple(sorted(f'{g[1]}: every {g[2]} {g[3]} has {attribute} {g[0]}' for g in got))
                old = base.get(entity, {}).get(attribute)
                if old is not None and old.status != 'unknown':
                    if old.status == 'known' and [value_key(old.value)] != values:
                        notes.append(f'{self.display(entity)} {attribute}: rule exception: stated {old.value!r}, rules give '
                                     + ' or '.join(values))
                    continue                     # a stated value is never overridden by a derived one
                if len(values) > 1:
                    cell = Cell('conflict', sides={v: tuple(sorted(g[1] for g in got if g[0] == v)) for v in values},
                                derived=why, note='rules disagree')
                else:
                    cell = Cell('known', values[0], tuple(sorted({g[1] for g in got})), derived=why, note='derived')
                new.setdefault(entity, {})[attribute] = cell
            same = {e: {a: (c.status, c.value, c.derived) for a, c in v.items()} for e, v in new.items()} == \
                   {e: {a: (c.status, c.value, c.derived) for a, c in v.items()} for e, v in derived.items()}
            derived = new
            if same:
                break
        else:
            notes.append('rules stopped after the round limit')
        for entity, attributes in derived.items():
            self.cells.setdefault(entity, {}).update(attributes)
        self.notes += [n for n in notes if n not in self.notes]

    def display(self, entity):
        return self.surface.get(entity, entity)

    def get(self, entity, attribute):
        entity = self.binding.name(norm(entity)) if norm(entity) in self.binding.parent else norm(entity)
        return self.cells.get(entity, {}).get(norm_attr(attribute), Cell('unknown', note='nobody said'))

    def table(self):
        """Plain values for comparing views: {entity: {attribute: (status, value or sides)}}."""
        return table_of(self.cells)


def resolve(claims):
    """One cell's value from its live claims, by the consensus rules in the module notes."""
    absolute = [c for c in claims if c.op == 'set']
    if not absolute:
        return Cell('unknown', note='only changes are known, not a starting value')
    top = max(RANK[c.kind] for c in absolute)
    absolute = [c for c in absolute if RANK[c.kind] == top]
    last = max(c.at for c in absolute)
    base = [c for c in absolute if c.at == last]
    values, shown = defaultdict(set), {}
    for c in sorted(base, key=lambda c: c.id):
        values[value_key(c.value)].add(c.agent)
        shown.setdefault(value_key(c.value), c.value)
    if len(values) > 1:
        return Cell('conflict', sides={shown[v]: tuple(sorted(a)) for v, a in sorted(values.items())},
                    note='same rank and position, different values')
    (value, agents), = values.items()
    support = set(agents)
    changes = sorted({(c.at, c.op, value_key(c.value)): c for c in claims if c.op != 'set' and c.at > last}.items())
    if changes:
        try:
            number = Fraction(value)
        except (ValueError, ZeroDivisionError):
            return Cell('unknown', note='a change was reported to a value that is not a number')
        for (at, op, amount), c in changes:
            number = number + Fraction(amount) if op == 'add' else number - Fraction(amount)
            support.add(c.agent)
        value = str(number)
    shown = next(c.value for c in sorted(base, key=lambda c: c.id)) if not changes else value
    return Cell('known', shown, tuple(sorted(support)))


def merged(states):
    out = State()
    for s in states:
        out.merge(s)
    return out


def tree(states, fanout=8):
    """Merge and summarise level by level, like a swarm of swarms. Returns the root and the largest node size seen."""
    level = [s.summary() for s in states]
    largest = max((len(s) for s in level), default=0)
    while len(level) > 1:
        level = [merged(level[i:i + fanout]).summary() for i in range(0, len(level), fanout)]
        largest = max(largest, max(len(s) for s in level))
    return (level[0] if level else State()), largest


def item_id(item):
    if isinstance(item, Claim):
        return item.id
    return hashlib.sha1(repr(item).encode('utf-8')).hexdigest()[:16]


def bucket(item, buckets):
    return int(item_id(item)[:4], 16) % buckets


def index(state, buckets=256):
    """{bucket: {item id: item}} for a state's items."""
    out = defaultdict(dict)
    for item in (*state.claims, *state.links, *state.rules):
        out[bucket(item, buckets)][item_id(item)] = item
    return out


def digest(indexed):
    """A short fingerprint per bucket. Two nodes compare fingerprints first and look closer only where they differ."""
    return {b: hashlib.sha1(''.join(sorted(ids)).encode()).hexdigest()[:16] for b, ids in indexed.items()}


def exchange(theirs, mine, their_digest=None, my_digest=None):
    """One pull, in three steps: compare bucket fingerprints, send the ids of the differing buckets, then send the items
    whose ids the puller lacks. Returns (the items, how many ids were sent)."""
    their_digest = their_digest or digest(theirs)
    my_digest = my_digest or digest(mine)
    out, ids = State(), 0
    for b, h in their_digest.items():
        if my_digest.get(b) != h:
            ids += len(theirs[b])
            have = mine.get(b, {})
            for i, item in theirs[b].items():
                if i not in have:
                    out.add(item)
    return out, ids


def gossip(states, rng, rounds=64, delta=True):
    """Every node pulls from one random peer each round, with no coordinator. With delta the peer sends only the items
    the puller lacks (see exchange); otherwise its whole summary. Returns (the rounds until every node holds the same
    summary, or None if that did not happen within the limit, and the traffic as {'items', 'ids'}). Changes the states
    in place."""
    target = merged(states).summary()        # every summary of the same claims is the same set (see summary())
    states[:] = [s.summary() for s in states]
    traffic = {'items': 0, 'ids': 0}
    for r in range(1, rounds + 1):
        if delta:
            indexed = [index(s) for s in states]
            digests = [digest(x) for x in indexed]
        pulls = []
        for i in range(len(states)):
            j = rng.randrange(len(states))
            if delta:
                got, ids = exchange(indexed[j], indexed[i], digests[j], digests[i])
                traffic['ids'] += ids
            else:
                got = states[j].copy()
            traffic['items'] += len(got)
            pulls.append(got)
        for i, got in enumerate(pulls):
            before = len(states[i])
            states[i].merge(got)
            if len(states[i]) != before:
                states[i] = states[i].summary()
        if all(s == target for s in states):
            return r, traffic
    return None, traffic


class Shards:
    """Claims split over many nodes by the name they were filed under, so no node holds the whole world.

    Every node keeps a small shared directory: the names in use, the links and the rules. That is enough to work out
    who is who (Binding) anywhere. To answer about one entity, a node collects the claims filed under that entity's
    names from the nodes that hold them, and nothing else. Rules look only at one entity's own attributes, so an
    entity's view built this way equals its view from merging everything."""

    def __init__(self, count):
        self.shards = [defaultdict(set) for _ in range(count)]      # per node: name key -> claims filed under it
        self.names, self.links, self.rules = set(), set(), set()
        self._binding = None

    def home(self, key):
        return int(hashlib.sha1(key.encode('utf-8')).hexdigest()[:8], 16) % len(self.shards)

    def add(self, state):
        for c in state.claims:
            self.shards[self.home(c.key[0])][c.key[0]].add(c)
            self.names.add(c.key[0])
        self.links |= state.links
        self.rules |= state.rules
        self._binding = None
        return self

    def summarise(self):
        """Summarise each name on its own node (a summary never looks past one name, see State.summary)."""
        for shard in self.shards:
            for key, claims in shard.items():
                shard[key] = State(claims).summary().claims

    @property
    def binding(self):
        if self._binding is None:
            self._binding = Binding(self.names, self.links)
        return self._binding

    def directory_size(self):
        return len(self.names) + len(self.links) + len(self.rules)

    def sizes(self):
        return [sum(len(c) for c in shard.values()) for shard in self.shards]

    def entity(self, name):
        """(the entity's {attribute: Cell}, how many nodes were asked). Empty when nobody named it."""
        key, b = norm(name), self.binding
        if key not in b.parent:
            return {}, 0
        members = b.members[b.find(key)]
        homes = {self.home(m) for m in members}
        claims = [c for m in members for c in self.shards[self.home(m)].get(m, ())]
        view = View(State(claims, self.links, self.rules), binding=b)
        return view.cells.get(b.name(key), {}), len(homes)

    def table(self):
        """The whole picture, built one entity at a time, in the same form as View.table()."""
        b, out = self.binding, {}
        for root in sorted({b.find(n) for n in self.names}):
            cells, _ = self.entity(root)
            if cells:
                out.update(table_of({b.name(root): cells}))
        return out


def table_of(cells):
    out = {}
    for entity, attributes in cells.items():
        for attribute, cell in attributes.items():
            shown = cell.value if cell.status == 'known' else dict(cell.sides) if cell.status == 'conflict' else None
            out.setdefault(entity, {})[attribute] = (cell.status, shown)
    return out


LEAD = re.compile(r"(?i)^\s*(?:(?:actually|now|so|well|oh|ok|okay|update|correction|sorry|wait|but|and|also|then|later|"
                  r"in fact|it turns out|turns out|i found out|i know(?: for (?:sure|a fact|certain))?|i checked(?: and)?|"
                  r"we know|for the record|i (?:can )?confirm|we (?:can )?confirm|confirmed|i(?:'ve| have) confirmed|"
                  r"i(?:'m| am) sure|i(?:'m| am) certain)\b(?:\s+that\b)?[,:!\s-]*)+")
NOT_A_SUBJECT = {'said', 'says', 'told', 'thinks', 'thought', 'saw', 'heard', 'believes', 'claims', 'and', 'but', 'that', 'if',
                 'when', 'because', 'reported', 'reports', 'i', 'you', 'we', 'they', 'he', 'she'}
TIME_WORD = r"(?:noon|midday|midnight|\d{1,2}(?::\d\d)?\s*(?:am|pm)|\d{1,2}:\d\d|\d{1,2}(?:\s*o'clock)?(?=\s*$))"
SEEN_AT = re.compile(r"(?i)(?:\s+(?:at|around|about|by|just after|just before|shortly after)\s+(" + TIME_WORD + r")\s*$|"
                     r"^\s*(?:at|around|about|by|just after|just before)\s+(" + TIME_WORD + r")\s*,?\s+)")
DESCRIBED = [re.compile(r"^\s*(?:[Tt]he|[Aa]n?)\s+([a-z][\w'-]*(?:\s+[\w'-]+){0,6}?)\s+(?:was|is)\s+(?:actually\s+|really\s+|definitely\s+)?"
                        r"([A-Z][a-z'-]+(?:\s+[A-Z][a-z'-]+)?)\s*$"),
             re.compile(r"^\s*([A-Z][a-z'-]+(?:\s+[A-Z][a-z'-]+)?)\s+(?:was|is)\s+(?:actually\s+|really\s+|definitely\s+)?(?:the|an?)\s+"
                        r"([a-z][\w'-]*(?:\s+[\w'-]+){0,6}?)\s*$")]


NUMBER_WORDS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
                'eleven': 11, 'twelve': 12, 'twenty': 20, 'a': 1, 'an': 1}
COUNT = re.compile(r"(?i)^\s*(?:the\s+)?([a-z][\w'-]*(?:\s+[A-Z][\w'-]*)?)\s+"
                   r"(had|has|have|owned|owns|kept|keeps|started with|starts with|"
                   r"spent|spends|lost|loses|gave away|gives away|used|uses|ate|eats|sold|sells|dropped|drops|broke|gave|gives|"
                   r"found|finds|got|gets|bought|buys|earned|earns|received|receives|won|wins|picked up|picks up|collected|collects|made|makes)"
                   r"\s+(\d+|" + '|'.join(NUMBER_WORDS) + r")\s+(?:more\s+|extra\s+|new\s+)?([a-z]+)\s*$")
TAKES = {'spent', 'spends', 'lost', 'loses', 'gave away', 'gives away', 'used', 'uses', 'ate', 'eats', 'sold', 'sells', 'dropped',
         'drops', 'broke', 'gave', 'gives'}
HOLDS = {'had', 'has', 'have', 'owned', 'owns', 'kept', 'keeps', 'started with', 'starts with'}


def counted(clause):
    # ('put' or 'add' or 'subtract', slots) for "Ben had 10 coins" / "Ben spent 4 coins" / "Ben found 2 coins", or None
    m = COUNT.match(clause)
    if not m or norm(m[1]) in PRONOUNS or set(norm(m[1]).split()) & NOT_A_SUBJECT:
        return None
    verb, amount = m[2].casefold(), m[3].casefold()
    n = str(int(amount) if amount.isdigit() else NUMBER_WORDS[amount])
    noun = m[4]
    if verb in HOLDS:
        return 'put', {'E': m[1], 'A': noun, 'V': n}
    return ('subtract' if verb in TAKES else 'add'), {'E': m[1], 'A': noun, 'D': n}


def minutes(word):
    word = word.casefold().replace(' ', '')
    if word in ('noon', 'midday'):
        return 12 * 60
    if word == 'midnight':
        return 0
    word = word.replace("o'clock", '')
    m = re.fullmatch(r'(\d{1,2})(?::(\d\d))?(am|pm)?', word)
    hour, minute = int(m[1]) % 12 if m[3] else int(m[1]), int(m[2] or 0)
    return (hour + (12 if m[3] == 'pm' else 0)) * 60 + minute


def clock_text(total):
    hour, minute = divmod(total, 60)
    suffix = 'am' if hour < 12 else 'pm'
    return f'{hour % 12 or 12}' + (f':{minute:02d}' if minute else '') + suffix


def described(clause):
    # ('the driver', 'Sam') for "The driver was Sam" or "Sam was the driver", or None
    for i, pattern in enumerate(DESCRIBED):
        m = pattern.match(clause)
        if m:
            name, words = (m[2], m[1]) if i == 0 else (m[1], m[2])
            if (words.casefold() in FAMILY_OF or FAMILY_OF.get(words.casefold().split()[-1]) or re.search(r'\d', words)
                    or norm(name) in PRONOUNS or set(norm(words).split()) & NOT_A_SUBJECT
                    or name.casefold() in FAMILY_OF or re.fullmatch(r'(?i)(?:' + DAYS + r')', name)):
                return None
            return 'the ' + words, name
    return None
TAIL = re.compile(r"(?i)[,\s]+(?:now|again|today|these days|any ?more|at the moment|right now|as well|too|instead)\s*$")
WORE = re.compile(r"(?i)^\s*(?:the\s+)?([a-z][\w'-]*(?:\s+[A-Z][\w'-]*)?)\s+(?:wore|was wearing|had on|carried|drove|was carrying|was driving|had)\s+"
                  r"(?:a|an|the|his|her|their)\s+((?:dark |light )?[a-z]+)\s+([a-z]+)\s*$")
MOVED = re.compile(r"(?i)^\s*(?:the\s+)?([a-z][\w'-]*(?:\s+[\w'-]+){0,5}?)\s+(?:went|moved|travelled|traveled|journeyed|walked|ran|"
                   r"drove|came|went back|headed|returned)\s+(?:back\s+)?(?:to|into)\s+(?:the\s+)?([a-z][\w -]{0,40}?)\s*$")
IS_IN = re.compile(r"(?i)^\s*(?:the\s+)?([a-z][\w'-]*(?:\s+[\w'-]+){0,5}?)\s+(?:is|was|are|were)\s+(?:in|at|on|by|near|next to|beside|outside|inside)\s+(?:the\s+)?([a-z][\w -]{0,40}?)\s*$")
DIFFERENT = re.compile(r"(?i)^\s*([A-Za-z][\w'-]*(?:\s+[A-Z][\w'-]*)?)\s+and\s+([A-Za-z][\w'-]*(?:\s+[A-Z][\w'-]*)?)\s+are\s+(?:two\s+)?"
                       r"(?:different|separate|not the same)(?:\s+(?:people|persons|men|women|things|places|ones|animals|cars|vehicles))?\s*$")
MOVER = re.compile(r"(?i)^\s*(?:i|we|someone|somebody|he|she|they|[A-Z][a-z]+)\s+(?:have\s+|had\s+|just\s+)?(?:moved|put|took|carried|brought|placed|"
                   r"left|hid|stored|dropped|hung|threw|stashed|parked)\s+(?:the\s+|my\s+|our\s+|his\s+|her\s+|their\s+)?([a-z][\w'-]*(?:\s+[\w'-]+){0,3}?)\s+"
                   r"(?:back\s+)?(?:to|into|in|on|onto|under|behind|beside|by|next to|inside|upstairs to|downstairs to|over to)\s+(?:the\s+)?([a-z][\w -]{0,40}?)\s*$")
SEEN_BY = re.compile(r"(?i)^\s*(?:i|we)\s+(?:personally\s+|myself\s+|actually\s+|just\s+|definitely\s+)?(?:saw|spotted|noticed|watched|found)\s+"
                     r"(?:the\s+)?([a-z][\w'-]*(?:\s+[\w'-]+){0,3}?)\s+(?:at|in|on|by|near|next to|beside|outside|inside)\s+(?:the\s+)?([a-z][\w -]{0,40}?)\s*$")
DAYS = r'monday|tuesday|wednesday|thursday|friday|saturday|sunday|today|tomorrow|yesterday'
EVENT_VERBS = r'coming|visiting|arriving|leaving|happening|starting|finishing|due|back|home|flying|landing|open|closing'
WHEN = re.compile(r"(?i)^\s*(?:the\s+|our\s+|my\s+)?([a-z][\w'-]*(?:\s+[a-z][\w'-]*){0,2}?)\s+(?:(?:is|are|was|will be)"
                  r"(?:\s+(?:" + EVENT_VERBS + r"))?|has been moved to|moved to|is moved to|got moved to|was moved to|were moved to|"
                  r"was changed to|got changed to|has been changed to|was pushed to|was put back to|was brought forward to|is now|"
                  r"comes|came|arrives|arrived|leaves|left|starts|started|was delivered|got here|turned up|"
                  r"lands|opens|closes)\s+(?:on\s+|at\s+|for\s+)?((?:next\s+|this\s+)?(?:" + DAYS + r")"
                  r"(?:\s+at\s+\d{1,2}(?::\d\d)?\s*(?:am|pm)?)?|\d{1,2}(?::\d\d)?\s*(?:am|pm)|\d{1,2}:\d\d|(?<=at )\d{1,2}(?:\s*o'clock)?)\s*$")
# Adjectives whose attribute is plain from the word itself: "the van was white" is the van's colour.
FAMILIES = {
    'colour': 'red|blue|green|yellow|white|black|grey|gray|silver|brown|orange|pink|purple|gold|beige|navy|maroon|dark blue|'
              'light blue|dark green|dark red',
    'mood': 'happy|sad|angry|upset|calm|nervous|scared|afraid|worried|relaxed|excited|tired|cheerful|annoyed|anxious|'
            'frightened|furious|content|grumpy|bored',
    'height': 'tall|short',
    'state': 'open|closed|locked|unlocked|on|off|empty|full|broken|working|up|down|online|offline|running|stopped',
}
FAMILY_OF = {w: attribute for attribute, words in FAMILIES.items() for w in words.split('|')}
ADJ = re.compile(r"(?i)^\s*(?:the\s+|a\s+|an\s+|my\s+|our\s+)?([a-z][\w'-]*(?:\s+[\w'-]+){0,5}?)\s+(?:is|was|looked|seemed|appeared|"
                 r"felt|looks|seems|appears|feels)\s+(?:very\s+|really\s+|quite\s+|a bit\s+|rather\s+|definitely\s+)?"
                 r"((?:dark |light )?[a-z]+)\s*$")


def when_attribute(value):
    return 'time' if re.fullmatch(r'(?i)\d{1,2}(?::\d\d)?\s*(?:am|pm)?', value.strip()) else 'day'


def adjective(clause):
    """('van', 'colour', 'white') for "The van was white", or None."""
    m = ADJ.match(clause)
    if not m or norm(m[1]) in PRONOUNS or not norm(m[1]):
        return None
    word = m[2].casefold()
    attribute = FAMILY_OF.get(word)
    return (m[1], attribute, word) if attribute else None


def claims_from_text(agent, text, part=0, clock=0, timeline=True, kind='stated', unread=None, links=None):
    """One agent reads one part of a text with CAEL's event memory and turns what it can establish into claims.
    A change to something this part never set ("Ana gains 2 apples") becomes a change claim, left for the swarm to
    place on top of a value another agent read. "Sam went to the garden" and "Sam is in the garden" set Sam's location;
    "The van was white" sets its colour; "on Monday at 3pm" is a day and a time.

    With timeline, the parts are consecutive (part 1, then part 2) and a later part's reading wins. Without it, the
    parts are separate accounts of the same moment (witnesses, sources): each agent's own later statement replaces
    its earlier one, and two accounts that differ are a conflict. `kind` is the evidence kind of this reader's values
    (trusted or doubted when the user said so); its changes stay stated, and a doubted reader's changes are left out."""
    from . import event_memory, state_language
    memory = event_memory.Memory()
    out, step = [], 0
    for clause in event_memory.clauses(text):
        if event_memory.ignored(clause) or event_memory.question(clause):
            continue
        clause = TAIL.sub('', LEAD.sub('', clause)) or clause      # "Actually my car is blue now" -> "my car is blue"
        seen = None
        if not timeline and not WHEN.match(clause):
            # "Sam was in the kitchen at 3pm": a sighting at a time, so a later sighting elsewhere is no conflict
            t = SEEN_AT.search(clause)
            if t:
                seen = minutes(t[1] or t[2])
                clause = (clause[:t.start()] + ' ' + clause[t.end():]).strip() if t[1] else clause[t.end():].strip()
        apart = DIFFERENT.match(clause)
        if apart and norm(apart[1]) and norm(apart[2]) and not {norm(apart[1]), norm(apart[2])} & PRONOUNS:
            step += 1                       # "Jo and Jordan are different people": never one entity, whatever the names suggest
            if links is not None:
                links.append(Link(apart[1], apart[2], 'distinct', agent, clock + step))
            continue
        negated = re.sub(r"(?i)\b(was|is)\s+not\b|\b(was|is)n't\b", lambda m: m[1] or m[2], clause)
        same = described(clause) or (described(negated) if negated != clause else None)
        if same:
            step += 1
            if links is not None:
                links.append(Link(same[0], same[1], 'distinct' if negated != clause else 'same', agent, clock + step))
            continue
        try:
            parsed = state_language.event(clause, memory.focus, state=memory.state) or event_memory.event(clause)
        except ValueError:
            parsed = None
        when, extra = WHEN.match(clause), None
        if when and norm(when[1]) and norm(when[1]) not in PRONOUNS:
            said = re.sub(r'(?i)\b(' + DAYS + r')\b', lambda d: d[1].capitalize(), ' '.join(when[2].split()))
            day, _, hour = said.partition(' at ')
            parsed = ('assert', {'E': when[1], 'A': when_attribute(day), 'V': day})
            if hour:
                extra = (when[1], 'time', hour)     # "on Monday at 3pm" is a day and a time, not a third kind of day
        if not parsed:
            parsed = counted(clause)
        if not parsed:
            m = MOVED.match(clause) or IS_IN.match(clause)
            if m and norm(m[1]) and norm(m[1]) not in PRONOUNS:
                parsed = ('assert', {'E': m[1], 'A': 'location', 'V': m[2]})
        if not parsed:
            m = SEEN_BY.match(clause)       # "I saw Jo in the lobby": the speaker's own sighting of Jo
            if m and norm(m[1]) and norm(m[1]) not in PRONOUNS:
                parsed = ('assert', {'E': m[1], 'A': 'location', 'V': m[2]})
        if not parsed:
            m = MOVER.match(clause)         # "I moved the radio to the porch": the radio's location, whoever moved it
            if m and norm(m[1]) and norm(m[1]) not in PRONOUNS:
                parsed = ('assert', {'E': m[1], 'A': 'location', 'V': m[2]})
        if not parsed:
            # "The thief wore a blue hat": the colour of the thief's hat
            m = WORE.match(clause)
            if m and norm(m[1]) and norm(m[1]) not in PRONOUNS and m[2].casefold() in FAMILY_OF and FAMILY_OF[m[2].casefold()] == 'colour':
                parsed = ('assert', {'E': f"{m[1]}'s {m[3]}", 'A': 'colour', 'V': m[2].casefold()})
        if not parsed:
            found = adjective(clause)
            if found:
                parsed = ('assert', {'E': found[0], 'A': found[1], 'V': found[2]})
        if not parsed:
            if unread is not None:
                unread.append(clause)       # said, but not understood: the caller decides whether that matters
            continue
        if set(norm(parsed[1].get('E', '')).split()) & NOT_A_SUBJECT:
            if unread is not None:
                unread.append(clause)       # "Sam said the van was white" is reported speech, not a fact about "Sam said the van"
            continue
        step += 1
        at = (part, step) if timeline else ((seen,) if seen is not None else ())
        op, slots = parsed
        target = event_memory.key(slots['E'], slots['A'])
        if op in ('add', 'subtract') and target not in memory.state:
            if kind != 'doubted':
                out.append(Claim(event_memory.clean(slots['E']), slots['A'], str(Fraction(slots['D'])), agent, clock + step,
                                 at=at, op=op, evidence=clause))
            continue
        if op == 'assert':
            op = 'put'                      # a reader records what it is told; agreement is the swarm's job
        memory.apply(op, slots, step, clause)
        value = memory.state.get(target)
        if value is not None and not isinstance(value, dict):
            out.append(Claim(memory.names.get(event_memory.clean(slots['E']).casefold(), slots['E']), slots['A'], str(value),
                             agent, clock + step, kind=kind, at=at, evidence=clause))
        if extra:
            out.append(Claim(event_memory.clean(extra[0]), extra[1], extra[2], agent, clock + step, kind=kind, at=at,
                             evidence=clause))
    return out


LIMIT = 6                       # readers working at one time, as for the Meesix agents


def read_parts(parts, limit=LIMIT, names=None, timeline=True, kinds=None):
    """Each part is read by its own short-lived agent, at most `limit` at a time. The agents share nothing while they
    read; their claims are merged afterwards. Returns the merged State."""
    names = names or [f'reader{i + 1}' for i in range(len(parts))]
    kinds = kinds or ['stated'] * len(parts)

    def one(item):
        index, text = item
        return State(claims_from_text(names[index], text, part=index, timeline=timeline, kind=kinds[index]))
    with ThreadPoolExecutor(max_workers=max(1, min(limit, len(parts)))) as pool:
        return merged(pool.map(one, enumerate(parts)))


WHAT_IS = re.compile(r"(?i)^\s*what\s+([a-z]+(?: [a-z]+)?)\s+(?:is|are|was|were)\s+(.+?)\s*\??\s*$")
WHERE_IS = re.compile(r"(?i)^\s*where\s+(?:does|do|did)\s+(?:that|this|it|the correction|the retraction)\s+(?:put|leave|place)\s+(.+?)\s*\??\s*$|"
                      r"^\s*where\s+(?:is|was|are|were|did|does|has|have)\s+(.+?)(?:\s+(?:go|gone|went|end up|ended up|head|headed|"
                      r"go to|run to|move to|moved to))?\s*(?:now|at the end|in the end)?\s*\??\s*$")
HOW_SEEM = re.compile(r"(?i)^\s*(?:how\s+(?:did|does|do)\s+(?:the\s+)?(.+?)\s+(?:seem|feel|look|appear)|"
                      r"what\s+mood\s+(?:was|is)\s+(?:the\s+)?(.+?)\s+in)\s*\??\s*$")
YES_NO = re.compile(r"(?i)^\s*(?:is|was|are|were)\s+(?:the\s+|my\s+|our\s+)?(.+?)\s*\??\s*$")
EARLIER = re.compile(r"(?i)\s*\b(?:at first|at the start|at the beginning|in the beginning|originally|to begin with|first of all|initially)\b\s*")
BY_LABEL = r"(?:on|in|after|by|at the end of|during)\s+((?:{t})\s*(?:#?\d{{1,3}}|[A-Z]\b|one|two|three|four|five|six)|(?:the\s+)?(?:first|second|third|fourth|fifth|sixth|last)\s+(?:{t}))"


def asked(question):
    """(entity, attribute) for a question about one value, or None."""
    from . import event_memory, state_language
    m = WHERE_IS.match(question)
    if m and norm(m[1] or m[2]):
        return (m[1] or m[2]), 'location'
    m = HOW_SEEM.match(question)            # "How did Sam seem?", "What mood was Sam in?"
    if m and norm(m[1] or m[2]) and norm(m[1] or m[2]) not in PRONOUNS:
        return m[1] or m[2], 'mood'
    q = event_memory.question(question.strip())
    if q and q.get('past'):
        return None                         # an earlier value: see question_of
    if q and q['kind'] == 'one':
        return q['E'], q['A']
    if q and q['kind'] == 'one_phrase':
        try:
            return state_language.property_phrase(q['phrase'], ())
        except ValueError:
            return None
    m = WHAT_IS.match(question)             # "What colour is the lamp?"
    if m and norm(m[2]):
        return m[2], m[1]
    return None


def yes_no(question):
    """(entity, attribute, expected value) for "Was the van white?", "Is Sam in the kitchen?", "Is the meeting on
    Monday?", or None."""
    m = YES_NO.match(question)
    if not m:
        return None
    body = m[1]
    place = re.fullmatch(r"(?i)(.+?)\s+(?:in|at|inside)\s+(?:the\s+)?([a-z][\w -]{0,40})", body)
    if place and norm(place[1]) and not re.fullmatch(r'(?i)\d.*', place[2]):
        return place[1], 'location', place[2]
    day = re.fullmatch(r"(?i)(.+?)\s+(?:on|at)\s+(.+)", body)
    if day and norm(day[1]) and re.fullmatch(r'(?i)(?:next |this )?(?:' + DAYS + r')|\d{1,2}(?::\d\d)?\s*(?:am|pm)?|\d{1,2}:\d\d', day[2]):
        return day[1], when_attribute(day[2]), day[2]
    words = body.rsplit(' ', 1)
    if len(words) == 2 and words[1].casefold() in FAMILY_OF and norm(words[0]):
        return words[0], FAMILY_OF[words[1].casefold()], words[1]
    return None


def label_key(label):
    """'Witness 2', 'witness two' and 'the second witness' are one label: 'witness 2'."""
    ordinals = {'first': '1', 'second': '2', 'third': '3', 'fourth': '4', 'fifth': '5', 'sixth': '6', 'one': '1', 'two': '2',
                'three': '3', 'four': '4', 'five': '5', 'six': '6'}
    words = [w for w in re.findall(r"[a-z0-9]+", label.casefold()) if w != 'the']
    if len(words) == 2 and words[0] in ordinals and words[0] not in ('one', 'two', 'three', 'four', 'five', 'six'):
        words = [words[1], ordinals[words[0]]]
    return ' '.join(ordinals.get(w, w) for w in words)


CERTAIN = re.compile(r"(?i)\b(?:definitely|certainly|for sure|for certain|still|really|exactly|actually|now)\b")
TRIM_Q = re.compile(r"(?i)\s*,?\s*(?:and\s+)?(?:according to whom|by whom|who (?:saw|said|reported) (?:it|that|this|so)|who says so|and who)\s*(?=\?|$)|"
                    r"\s*,\s*(?:if|assuming|given that|supposing)\b[^?]*(?=\?|$)|\s*,?\s*(?:if|assuming)\s+(?:no|nothing|there (?:were|was) no)\b[^?]*(?=\?|$)")
SEEN_LAST = re.compile(r"(?i)\s*(?:\b(?:when|where)\s+(?:it|they|he|she)\s+(?:was|were)\s+)?\b(?:last|most recently|latest)\s+"
                       r"(?:seen|spotted|sighted|noticed|reported|recorded|checked)\b|\b(?:seen|spotted) last\b\s*")
CONFIRMED_LAST = re.compile(r"(?i)\s*\b(?:last\s+)?(?:confirmed|verified|known for sure|for certain|for sure)(?:\s+by\s+(?:me|you|us|myself))?\b\s*")


def question_of(question, labels=(), timeline=True):
    """What is asked: dict(entity, attribute, expect=None or a value for a yes/no question, upto=None, 'initial' or a
    label key for an earlier value, mode=None, 'seen' or 'confirmed'). None when it is not about one value.

    "Where was the van last seen?" asks for the latest sighting from anyone, whatever its rank; "Where was it last
    confirmed?" asks only for what the user confirmed; "Where is the van?" asks for the best-supported value."""
    mode, certain = None, bool(re.search(r'(?i)\b(?:definitely|certainly|for sure|for certain|surely|guaranteed)\b', question))
    question = re.sub(r'\s+\?', '?', TRIM_Q.sub('', CERTAIN.sub(' ', question))).strip()
    question = re.sub(r'\s{2,}', ' ', question)
    if SEEN_LAST.search(question):
        mode, question = 'seen', re.sub(r'\s+\?', '?', SEEN_LAST.sub(' ', question)).strip()
    elif CONFIRMED_LAST.search(question):
        mode, question = 'confirmed', re.sub(r'\s+\?', '?', CONFIRMED_LAST.sub(' ', question)).strip()
    found = _question_of(question, labels, timeline)
    if found is not None:
        found['mode'] = mode
        found['certain'] = certain
    return found


def _question_of(question, labels=(), timeline=True):
    upto = None
    if timeline:
        if EARLIER.search(question):
            upto, question = 'initial', EARLIER.sub(' ', question).strip()
        else:
            m = re.search(r'(?i)\s*\b' + BY_LABEL.format(t=TIMELINE) + r'\s*(?=\?|$)', question)
            if m and label_key(m[1]) in labels:
                upto, question = label_key(m[1]), (question[:m.start()] + question[m.end():]).strip()
    elif EARLIER.search(question):
        return None                         # separate accounts have no "at first"
    else:
        t = re.search(r'(?i)\s+(?:at|around|by)\s+(' + TIME_WORD + r')\s*(?=\?|$)', question)
        if t:
            upto, question = (minutes(t[1]),), (question[:t.start()] + question[t.end():]).strip()
    question = re.sub(r'\s+\?', '?', question)
    where = asked(question)
    if where:
        return dict(entity=where[0], attribute=where[1], expect=None, upto=upto)
    found = yes_no(question)
    if found:
        return dict(entity=found[0], attribute=found[1], expect=found[2], upto=upto)
    return None


def cell_claims(state, view, entity, attribute):
    b = view.binding
    if norm(entity) not in b.parent:
        return []
    members = b.members[b.find(norm(entity))]
    return [c for c in state.claims if c.key[0] in members and c.key[1] == norm_attr(attribute)]


def respond_from(state, ask, timeline=True, owned_only=False, trust=None, parts=0, names=(), why=None):
    # why: per label key, the reason a source is doubted when the user did not say so directly
    # ("Witness 2 was wrong about where Sam was, going by what you told me")
    """The reply for one question (see question_of) over a merged State."""
    trust, why = trust or {}, why or {}
    entity, attribute = ask['entity'], ask['attribute']
    view = state.view()
    gone = [l for l in state.links if norm(entity) in l.pair and l.relation == 'same' and l not in live_links(state.links)]
    if owned_only and (norm(entity) not in view.binding.parent or (gone and not cell_claims(state, view, entity, attribute))):
        if not gone:
            return None                     # about something none of the parts named
        l = sorted(gone, key=lambda l: l.clock)[-1]
        withdrew = any(x.relation == 'retract' and x.agent == l.agent and norm(x.a) == norm(l.a) for x in state.links)
        return {'route': 'chat/swarm-unknown', 'sources': [],
                'response': f'Nobody places {entity} now. {l.agent} first said {l.a} was {l.b}, then '
                            f'{"withdrew" if withdrew else "corrected"} it, so nothing that was said about {l.a} applies to {entity} '
                            f'any more, and where {entity} is is unknown.',
                'swarm': {'parts': parts, 'readers': list(names), 'status': 'unknown', 'withdrawn': [l.agent]}}
    lead = ''
    if ask.get('upto'):
        mine = [c for c in cell_claims(state, view, entity, attribute) if c.op == 'set']
        if not mine:
            return None
        if ask['upto'] == 'initial':
            cutoff, lead = min(c.at for c in mine), 'At first: '
        elif isinstance(ask['upto'], tuple):
            cutoff, lead = ask['upto'], f'At {clock_text(ask["upto"][0])}: '
            before = sorted((c for c in mine if c.at and c.at < cutoff), key=lambda c: c.at)
            after = sorted((c for c in mine if c.at and c.at > cutoff), key=lambda c: c.at)
            if before and after and not any(c.at == cutoff for c in mine) and value_key(before[-1].value) != value_key(after[0].value):
                b, a = before[-1], after[0]
                return {'route': 'chat/swarm-unknown', 'sources': [], 'swarm': {'parts': parts, 'readers': list(names), 'status': 'unknown'},
                        'response': f'Not known exactly. At {clock_text(b.at[0])} it was at the **{b.value}** ({b.agent}), and at '
                                    f'{clock_text(a.at[0])} at the **{a.value}** ({a.agent}); nothing places it at {clock_text(cutoff[0])}, '
                                    f'so it could have been at either or in between.'}
        else:
            index = next((i for i, n in enumerate(names) if label_key(n) == ask['upto']), None)
            if index is None:
                return None
            cutoff, lead = (index, 10 ** 9), f'By {names[index]}: '
        state = State({c for c in state.claims if c.at <= cutoff}, state.links, state.rules)
        view = state.view()
    mode_note = ''
    if ask.get('mode') in ('seen', 'confirmed') and not timeline:
        mine = [c for c in cell_claims(state, view, entity, attribute) if c.op == 'set']
        if ask['mode'] == 'confirmed':
            keep = {c for c in mine if c.kind == 'confirmed'}
            if not keep:
                mode_note = ' Nothing about this is confirmed by you; that is the best-supported account.'
        else:
            last = max((c.at for c in mine), default=())
            keep = {c for c in mine if c.at == last}
            if keep and last:
                lead = f'Last seen at {clock_text(last[0])}: '
        if keep:
            other = {c for c in state.claims if c not in mine}
            state = State(other | {Claim(c.entity, c.attribute, c.value, c.agent, c.clock, 'stated', c.at, c.op, c.evidence)
                                   for c in keep}, state.links, state.rules)
            view = state.view()
    cell = view.get(entity, attribute)
    who = 'sources' if not timeline else 'parts'

    def by(agents):
        return ', '.join('what you told me' if a == 'you' else a for a in agents)
    if cell.status == 'known':
        shown = f'**{cell.value}**' + (f' ({by(cell.support)})' if cell.support else '')
        if ask.get('expect') is not None:
            same = value_key(cell.value) == value_key(ask['expect'])
            text = ('**Yes**' if same else '**No**') + f': {cell.value}' + (f' ({by(cell.support)})' if cell.support else '')
        else:
            text = shown
        if not timeline and len(cell.support) > 1:
            text += f'. The {who} agree.'
    elif cell.status == 'conflict':
        text = (f'The {who} disagree, and neither account outranks the other: '
                + '; '.join(f'**{v}** ({by(a)})' for v, a in cell.sides.items())
                + '. I would check with whoever was there rather than pick one.')
    else:
        text = f'The {who} do not settle this: ' + (cell.note or 'nobody said') + '.'
    if not timeline and cell.status != 'unknown':
        text = text.rstrip('.') + '.'
        winners = set(cell.support) | {a for agents in cell.sides.values() for a in agents}
        trusted = [a for a in sorted(winners) if trust.get(label_key(a)) == 'trusted']
        aside = defaultdict(list)                       # value -> agents whose differing account was outranked
        latest = max((c.at for c in cell_claims(state, view, entity, attribute) if c.op == 'set' and c.agent in winners),
                     default=())
        for c in sorted(cell_claims(state, view, entity, attribute), key=lambda c: c.agent):
            if c.op == 'set' and c.agent not in winners and value_key(c.value) != value_key(cell.value or '') \
                    and not (c.at and latest and c.at < latest and RANK[c.kind] >= RANK['stated']) \
                    and not (c.at and latest and c.at > latest and not timeline) \
                    and c.agent not in aside.get(c.value, ()):
                aside[c.value].append(c.agent)
        doubted = [a for agents in aside.values() for a in agents if trust.get(label_key(a)) == 'doubted']
        for value, agents in aside.items():
            text += f' {" and ".join(agents)} said **{value}**.'
        if aside:
            reasons = []
            if 'you' in winners:
                reasons, doubted, trusted = ['it goes against what you told me'], [], []
            if trusted:
                reasons.append(f'by what you told me, {" and ".join(trusted)} {"is" if len(trusted) == 1 else "are"} the more reliable source')
            told = [a for a in doubted if label_key(a) not in why]
            if told:
                reasons.append(f'you said not to rely on {" and ".join(told)}')
            for a in doubted:
                if label_key(a) in why:
                    reasons.append(why[label_key(a)])
            text += ' I set that aside because ' + ', and '.join(reasons) + '.' if reasons else ''
        elif trusted:
            text += f' By what you told me, {" and ".join(trusted)} {"is" if len(trusted) == 1 else "are"} the more reliable source.'
    text += mode_note
    if not timeline and cell.status == 'known' and not ask.get('upto') and not ask.get('mode'):
        mine = [c for c in cell_claims(state, view, entity, attribute) if c.op == 'set' and c.at]
        held = max((c.at for c in mine if c.agent in cell.support and value_key(c.value) == value_key(cell.value)), default=())
        later = sorted((c for c in mine if c.at > held and value_key(c.value) != value_key(cell.value)), key=lambda c: (c.at, c.agent))
        if later:
            # newer evidence of lower rank is shown, never hidden: "last confirmed" and "last seen" can differ
            groups = defaultdict(list)
            for c in later:
                groups[(c.at, c.value)].append(c.agent)
            shown = '; '.join(f'**{v}** at {clock_text(at[0])} ({", ".join(sorted(set(a)))}'
                              + (', seen by separate sources' if len(set(a)) > 1 else '') + ')' for (at, v), a in sorted(groups.items()))
            text += (f' That is as of {clock_text(held[0])}. A later sighting ranks lower: {shown}. '
                     'Ask where it was last seen for the latest sighting on its own.') if held else \
                    f' A later sighting ranks lower: {shown}.'
        else:
            timed = sorted((c for c in mine if RANK[c.kind] >= RANK['stated']), key=lambda c: (c.at, c.agent))
            if len({c.at for c in timed}) > 1:
                last = timed[-1].at
                earlier = [c for c in timed if c.at < last and value_key(c.value) != value_key(cell.value)]
                text += f' That is the latest sighting, at {clock_text(last[0])}.'
                if earlier:
                    text += ' Earlier: ' + '; '.join(f'**{c.value}** at {clock_text(c.at[0])} ({by([c.agent])})' for c in earlier) + '.'
    if cell.status != 'unknown' and norm(entity) in view.binding.parent:
        # the answer came through "the driver was Sam": say which link it rests on
        mine = view.binding.find(norm(entity))
        used = {c.key[0] for c in cell_claims(state, view, entity, attribute) if c.agent in set(cell.support) |
                {a for agents in cell.sides.values() for a in agents}}
        if used and norm(entity) not in used:
            for link in sorted(live_links(state.links), key=lambda l: (l.agent, l.pair)):
                if link.relation == 'same' and view.binding.find(norm(link.a)) == mine and set(link.pair) & used:
                    text += f' This rests on {link.agent}: {link.a} was {link.b}.'
                    break
    notes = [n for n in view.notes if norm(entity) in n or norm_attr(attribute) in n]
    if notes:
        text += ' Note: ' + '; '.join(notes) + '.'
    if lead and text.startswith('The '):
        lead, text = lead.rstrip(': ') + ', ', 't' + text[1:]
    return {'route': 'chat/swarm-' + cell.status, 'response': lead + text, 'sources': [],
            'swarm': {'parts': parts, 'readers': list(names), 'claims': len(state.claims), 'status': cell.status,
                      'support': list(cell.support), 'sides': cell.sides, 'timeline': timeline, 'trust': dict(trust),
                      'upto': ask.get('upto')},
            'details': 'Each part was read by its own reader; their claims were merged by the swarm rules (swarm.py): '
                       'corrections, evidence kind, timeline position, and conflicts reported rather than voted on.'}


def answer(parts, question, limit=LIMIT, names=None, timeline=True, owned_only=False, where=None, kinds=None, trust=None):
    """Read the parts with a swarm of readers and answer one question from their merged view. A dict reply in CAEL's
    usual shape, or None when the question is not about one value (or, with owned_only, about nothing the parts named)."""
    names = names or [f'reader{i + 1}' for i in range(len(parts))]
    ask = (dict(entity=where[0], attribute=where[1], expect=None, upto=None) if where
           else question_of(question, {label_key(n) for n in names}, timeline))
    if ask is None:
        return None
    state = read_parts(parts, limit, names, timeline, kinds)
    return respond_from(state, ask, timeline, owned_only, trust, len(parts), names)


TIMELINE = r'part|chapter|day|step|stage|scene|round|episode|entry|update'
ACCOUNTS = (r'witness|source|report|reporter|account|document|doc|agent|reader|sensor|scout|observer|camera|log|post|message|note|'
            r'neighbou?r|friend|article|website|site|channel|email|letter')
NAME = (r"(?:(?:" + TIMELINE + '|' + ACCOUNTS + r")\s*(?:#?\d{1,3}|[A-Z]\b|one|two|three|four|five|six)"
        r"|(?:the\s+)?(?:first|second|third|fourth|fifth|sixth|last)\s+(?:" + TIMELINE + '|' + ACCOUNTS + r"))")
LABEL = re.compile(r"(?im)(?:^|(?<=[.!?\n]))\s*(?:(?:a\s+)?(?:correction|update|amendment|clarification|addition)\s+(?:to|from|for)\s+)?(" + NAME + r")"
                   r"(?:\s+(?:correction|update|corrects(?:\s+this)?|amends|clarifies|revision|adds|again|now says))?"
                   r"(?:\s*[:\-]|(?=\s+(?:heard|was told|only heard)\b)|\s+(?:says|said|reports|reported|claims|claimed|states|stated|thinks|thought|told me|told us|tells me|writes|wrote)(?:\s+that)?)\s*")
TRUSTED = (r"(?:is|was|seems|'s)\s+(?:very\s+|really\s+|completely\s+|more\s+|the\s+most\s+)?(?:reliable|trustworthy|credible|accurate|"
           r"official|certain|sure|right|an expert|the police|a professional)|saw it (?:directly|first-hand|firsthand|up close|clearly)|"
           r"(?:is|comes|came|was)\s+(?:straight\s+|directly\s+)?from\s+(?:the\s+|its\s+|their\s+)?(?:[a-z]+'s\s+)?(?:own\s+|official\s+)"
           r"(?:website|site|page|records?|account|announcement|notice|timetable|schedule|staff)|is (?:the )?official (?:\w+\s+)?(?:source|record|website)")
DOUBTED = (r"(?:is|was|seems|'s)\s+(?:very\s+|really\s+|often\s+|usually\s+|known to be\s+)?(?:unreliable|untrustworthy|not reliable|"
           r"not trustworthy|not credible|lying|a liar|drunk|confused|biased|unsure|not sure|guessing|wrong|mistaken|half asleep)|"
           r"(?:can't|cannot|can not|shouldn't|should not) be trusted|(?:often |usually |always )?(?:lies|gets things wrong|"
           r"has been wrong before|is often wrong)|(?:wasn't|was not|didn't|did not) (?:see|wear|have) (?:it|clearly|well|"
           r"(?:his|her|their) glasses)")
TRUST = [
    (re.compile(r"(?i)\b(?:ignore|disregard|leave out|drop|forget|skip)\s+(" + NAME + r")"), 'ignored'),
    (re.compile(r"(?i)\b(?:don't|do not|never|wouldn't|would not)\s+(?:trust|believe|rely on)\s+(" + NAME + r")"), 'doubted'),
    (re.compile(r"(?i)(?:^|[.!?]\s*|\b(?:but|and|also|though)\s+)(" + NAME + r")\s+(?:" + DOUBTED + r")"), 'doubted'),
    (re.compile(r"(?i)(?:^|[.!?]\s*|\b(?:but|and|also|though)\s+)(" + NAME + r")\s+(?:" + TRUSTED + r")"), 'trusted'),
    (re.compile(r"(?i)(?<!n't )(?<!not )\b(?:trust|believe|rely on|go with)\s+(" + NAME + r")"), 'trusted'),
]
WHICH = re.compile(r"(?i)^\s*(?:so\s+)?(?:which|who|what)(?:\s+one)?\s+(?:is|'s|was)\s+(?:right|correct|true|accurate)\b|"
                   r"^\s*(?:what(?:'s| is) the truth|who(?:m)? (?:should|do) i (?:believe|trust)|which (?:one )?(?:should|do) i (?:believe|trust))\b")
WHEN_ASKED = re.compile(r"(?i)^\s*(?:so\s+)?(?:when|what day|what time)\s+(?:is|are|was|will|does|do|did)\s+(?:the\s+|our\s+|my\s+)?(.+?)"
                        r"(?:\s+be)?(?:\s+(?:" + EVENT_VERBS + r"|come|visit|arrive|leave|start|finish|land|open|close))?"
                        r"(?:\s+now)?\s*\??\s*$")
LEAD_PRONOUN = re.compile(r"(?i)(^|(?<=[.!?])\s+)((?:then|later|now|and|but|after that|afterwards)[,\s]+)?(it|this|that)\b"
                          r"(?=\s+(?:is|was|will|has|moved|got|went|came|became|turned))")
SENTENCES = re.compile(r'(?<=[.!?])\s+|\n+')


def trust_of(text):
    """{label key: trusted / doubted / ignored} from what the user said about the sources."""
    out = {}
    for pattern, tier in TRUST:
        for m in pattern.finditer(text):
            out.setdefault(label_key(m[1]), tier)       # the earlier patterns (ignore, don't trust) take precedence
    return out


def trust_sentence(sentence):
    return any(p.search(sentence) for p, _ in TRUST) and not LABEL.match(sentence)


def segments(text):
    """[(label, body)] of one message's labelled parts (one kind only), or [] when it has none."""
    marks = list(LABEL.finditer(text))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        label = ' '.join(m[1].split())
        out.append((label[:1].upper() + label[1:], text[m.end():end].strip()))
    return out


def labelled_parts(text):
    """[(label, text)] for a message of two or more labelled parts of one kind ("Witness 1: ... Witness 2: ..."), the
    question split off, and whether the parts are a timeline. None otherwise."""
    found = gather([text])
    return (found['parts'], found['question'], found['timeline']) if found else None


def gather(turns):
    """The labelled parts across the user's turns, merged by label, the question from the last turn, what the user said
    about trusting them, and whether the parts are a timeline. None when this is not a swarm question.

    The parts may all be in the last message, or spread over earlier messages with the question last ("Witness 1 says
    ...", "Witness 2 says ...", "Where is Sam?"). Sentences about trust ("Witness 2 is unreliable") may come anywhere."""
    last = turns[-1]
    found = [(i, label, body) for i, t in enumerate(turns) for label, body in segments(t)]
    own = [s for t in turns for s in SENTENCES.split(own_part(t))
           if s.strip() and not s.strip().endswith('?') and not trust_sentence(s) and fact_sentence(s)]
    # two sources, or one source and the user's own fact, or one source that corrected itself ("Log A: ..." then
    # "Log A correction: ...")
    if len({label_key(label) for _, label, _ in found}) < (1 if own or len(found) > 1 else 2):
        return None
    kinds = {bool(re.search(r'(?i)\b(?:' + TIMELINE + r')\b', label)) for _, label, _ in found}
    if len(kinds) != 1:
        return None
    if found[-1][0] == len(turns) - 1:
        sentences = [s for s in SENTENCES.split(found[-1][2]) if s.strip()]
    else:
        # the last message holds no part: it is the question, perhaps after something said about the sources
        sentences = [s for s in SENTENCES.split(last) if s.strip()]
        if not sentences or not all(s.strip().endswith('?') or trust_sentence(s) or fact_sentence(s) or retract_sentence(s)
                                    or ACKNOWLEDGE.match(s) for s in sentences):
            return None
    asks = [s.strip() for s in sentences if s.strip().endswith('?')]
    if not asks:
        return None
    question = re.sub(r'(?i)^\s*(?:question|q|so|and|ok|okay)\s*[:\-,]?\s*', '', asks[-1])
    order, bodies, shown = [], {}, {}
    for i, label, body in found:
        if i == len(turns) - 1 and body is found[-1][2]:
            body = body[:body.rfind(asks[-1])].strip() if asks[-1] in body else body
        key = label_key(label)
        if key not in bodies:
            order.append(key)
            bodies[key] = []
            shown[key] = label
        bodies[key].append(' '.join(s for s in SENTENCES.split(body) if s.strip() and not trust_sentence(s)))
    trust = trust_of(' '.join(turns))
    parts = [(shown[k], ' '.join(b for b in bodies[k] if b)) for k in order]
    if not all(t for _, t in parts):
        return None
    # "Post A says the shop opens at 9. Post B says it opens at 10.": a part that opens with "it" is about the one
    # thing the other parts open with
    heads = {m[1].lower() for _, t in parts for m in [re.match(r"(?i)\s*the\s+([a-z]+(?:'s)?(?:\s+[a-z]+)?)\s+(?:is|was|opens|closes|leaves|"
                                                             r"arrives|starts|ends|finishes|lands|departs)\b", t)] if m}
    if len(heads) == 1:
        thing = heads.pop()
        parts = [(n, re.sub(r"^(\s*)(?:it|this)\b", lambda m: m[1] + 'the ' + thing, t, count=1, flags=re.I)) for n, t in parts]
    facts = [s.strip() for t in turns for s in SENTENCES.split(own_part(t))
             if s.strip() and not s.strip().endswith('?') and not trust_sentence(s) and fact_sentence(s)]
    retracted = {}
    for t in turns:
        for s in SENTENCES.split(t):
            r = retract_sentence(s)
            if r:
                retracted[label_key(r[0])] = r[1]
    return dict(parts=parts, question=question, timeline=kinds.pop(), trust=trust, facts=facts, retracted=retracted)


def own_part(text):
    # the user's own words in a message: all of it when it has no labels, else what comes before the first label
    marks = LABEL.search(text)
    return text if not marks else text[:marks.start()]


RETRACT = re.compile(r"(?i)^\s*(" + NAME + r")\s+(?:now\s+)?(?:retracts|withdraws|takes back|retracted|withdrew|took back|no longer stands by|"
                     r"is no longer sure about|has withdrawn|has retracted)\s+(?:the|their|his|her|its|that)?\s*(identification|statement|account|"
                     r"claim|report|sighting|testimony|evidence|answer|id)\b")
ACKNOWLEDGE = re.compile(r"(?i)^\s*(?:so\s+)?(?:we|i|nobody|no one)\s+(?:don't|do not|doesn't|does not|can't|cannot)\s+(?:know|tell|say)\b|"
                         r"^\s*(?:that|this) (?:is|was) (?:all|everything)\b|^\s*(?:nothing|no) (?:else|other)\b")


def retract_sentence(sentence):
    # (label, scope) for "Witness 2 retracts the identification", or None
    m = RETRACT.match(sentence or '')
    if not m:
        return None
    return ' '.join(m[1].split()), ('identification' if m[2].lower() in ('identification', 'id') else 'all')


def fact_sentence(sentence):
    # a sentence of the user's own that a reader can read ("It turns out Sam was in the kitchen")
    unread = []
    return bool(claims_from_text('you', sentence, timeline=False, unread=unread)) and not unread


def subject_of(readings, attribute=None):
    """(entity, attribute) when the accounts are all about one value (of this attribute, when given), or None."""
    agents = defaultdict(set)
    for reading in readings:
        for c in reading:
            if attribute is None or c.key[1] == norm_attr(attribute):
                agents[c.key].add(c.agent)
    shared = [k for k, a in agents.items() if len(a) > 1] or ([k for k in agents] if attribute and len(agents) == 1 else [])
    return shared[0] if len(shared) == 1 else None


SOURCE_WORDS = r'(?:logs?|reports?|sources?|witness(?:es)?|accounts?|sensors?|cameras?|records?|documents?|observers?|scouts?|readers?|messages?|posts?|notes?|neighbou?rs?|friends?|articles?|websites?|emails?|letters?)'
DISAGREE_Q = re.compile(r"(?i)^\s*(?:so\s+)?(?:do|does|are|is)\s+(?:the\s+|both\s+|all\s+)?(?:two\s+)?" + SOURCE_WORDS +
                        r"\s+(?:still\s+)?(?:in\s+)?(?P<verb>disagree|agree|conflict|differ|match|agreement|disagreement)(?:ing)?"
                        r"(?:\s+(?:now|yet|again|still|any more|anymore))?"
                        r"(?:\s+(?:about|on|over|regarding)\s+(?:the\s+)?(?:[a-z]+'s\s+)?(?P<attr>[a-z]+))?(?:\s+(?:now|yet|again))?\s*\?\s*$")
REMAINING_Q = re.compile(r"(?i)^\s*(?:so\s+)?what\s+(?P<attr>[a-z]+)\s+(?:do|does|did)\s+(?:the\s+)?(?:remaining|other|rest of the|rest|kept|"
                         r"remaining two|other two)\s+" + SOURCE_WORDS + r"?\s*(?:give|say|report|show|suggest)\s*\??\s*$")
HEARSAY_Q = re.compile(r"(?i)\bdid\s+(?:either|any|both|all|the|each)\s+(?:of\s+(?:the\s+|them\s*)?)?(?:two\s+)?" + SOURCE_WORDS +
                       r"?\s*(?:say|claim|report|state|tell (?:you|us))\s+(?:that\s+)?(?:they|he|she|it)\s+(?:had\s+)?(?:personally\s+|"
                       r"actually\s+|really\s+|themselves\s+|directly\s+)?(?:saw|see|seen|witnessed|spotted)")
INDEPENDENT_Q = re.compile(r"(?i)\bhow many\s+(?:independent|separate|first-?hand|direct|different)\s+(sightings?|accounts?|reports?|witnesses|sources|"
                           r"observations?)\b")
COPIED = re.compile(r"(?i)\b(?:copied|repeated|forwarded|re-?posted|passed on|relayed|took (?:it|this|that) from|got (?:it|this|that) from|"
                    r"is based on|based (?:it|this) on|quoting|quoted|according to)\b")


def sources_question(question, names, texts, readings):
    # Questions about the accounts themselves: who saw it first-hand, how many independent sightings there are
    hearsay = [n for n, t in zip(names, texts) if REPORTED.search(t) and not SEEN_BY.search(t) and not re.search(r'(?i)\bI (?:saw|watched|spotted)\b', t)]
    # "I copied Witness A's account" marks the part it is in; "Witness 3 copied Witness 1's statement" marks Witness 3,
    # whichever part the sentence happens to sit in
    copies = []
    for n, t in zip(names, texts):
        for s in re.split(r'(?<=[.!?])\s+', t):
            named = re.match(r'(?i)\s*(' + NAME + r')\s+(?:has\s+|had\s+|just\s+)?(?:copied|repeated|forwarded|relayed|re-?posted|passed on)\b', s)
            if named:
                copies.append(' '.join(named[1].split()))
            elif COPIED.search(s) and re.match(r'(?i)\s*(?:i|we|this|it|they|the report|this report)\b', s):
                copies.append(n)
    copies = [n for n in names if label_key(n) in {label_key(c) for c in copies}]
    first_hand = [n for n, t in zip(names, texts) if n not in hearsay and n not in copies]
    if HEARSAY_Q.search(question):
        if first_hand:
            return {'route': 'chat/swarm-sources', 'sources': [], 'response':
                    f'**Yes:** {" and ".join(first_hand)} {"says" if len(first_hand) == 1 else "say"} they saw it themselves.'
                    + (f' {" and ".join(hearsay)} only {"passes" if len(hearsay) == 1 else "pass"} on what someone else said.' if hearsay else '')}
        return {'route': 'chat/swarm-sources', 'sources': [], 'response':
                f'**No.** Neither says they saw it themselves: {" and ".join(hearsay or names)} only '
                f'{"passes" if len(hearsay or names) == 1 else "pass"} on what someone else said.'}
    m = INDEPENDENT_Q.search(question)
    if m:
        n = len(first_hand)
        word = {0: 'None', 1: 'One', 2: 'Two', 3: 'Three', 4: 'Four'}.get(n, str(n))
        why = []
        if first_hand:
            why.append(f'{" and ".join(first_hand)} {"is" if n == 1 else "are"} first-hand')
        if copies:
            why.append(f'{" and ".join(copies)} copied or repeated another account, so {"it is" if len(copies) == 1 else "they are"} not independent')
        if hearsay:
            why.append(f'{" and ".join(hearsay)} only passed on what someone else said')
        return {'route': 'chat/swarm-sources', 'sources': [], 'response': f'**{word}.** ' + '; '.join(why) + '.'}
    return None


def disagreement(state, ask, reply):
    # "Do the logs still disagree about the colour?": yes or no, and say which correction settled it
    view = state.view()
    cell = view.get(ask['entity'], ask['attribute'])
    agree_q = ask['disagree'] in ('agree', 'match', 'agreement')
    corrected = []
    for agent in sorted({c.agent for c in cell_claims(state, view, ask['entity'], ask['attribute'])}):
        mine = sorted((c for c in state.claims if c.agent == agent and c.op == 'set' and view.binding.name(c.key[0]) == view.binding.name(norm(ask['entity']))
                       and c.key[1] == norm_attr(ask['attribute'])), key=lambda c: c.clock)
        if len({value_key(c.value) for c in mine}) > 1:
            corrected.append(f'{agent} corrected its account from **{mine[0].value}** to **{mine[-1].value}**')
    if cell.status == 'conflict':
        sides = '; '.join(f'**{v}** ({", ".join(a)})' for v, a in cell.sides.items())
        return ('**No**, they still disagree: ' if agree_q else '**Yes**, they still disagree: ') + sides + '.'
    if cell.status == 'known':
        lead = '**Yes**, they agree' if agree_q else '**No**, they agree now'
        return f'{lead}: **{cell.value}** ({", ".join(cell.support)}).' + (' ' + '; '.join(corrected) + '.' if corrected else '')
    return reply['response']


REPORTED = re.compile(r"(?i)\b(?:said|says|told (?:me|us|him|her|them)|claimed|claims|heard|reckons|thinks)\b")
WHY = re.compile(r"(?i)^\s*(?:but\s+|and\s+|so\s+|ok\s+|okay\s+)?(?:why\b(?: is that| do you say that| that one| not)?|how do you know|"
                 r"what did (?:each|every|the) (?:\w+ )?(?:say|said)|show (?:me )?(?:the |your )?(?:evidence|working|sources)|"
                 r"explain(?: that| yourself| why)?|what (?:makes|made) you say that|says who)\b"
                 r"(?:\s+(?:then|exactly|again|please|though|so sure|is that|that is))*\s*[?!.]*\s*$")


def solve(turns):
    """Everything the Swarm desk works out for a swarm question: the reply and what it was built from. None when the
    turns are not a swarm question."""
    found = gather(turns)
    if not found:
        return None
    timeline, trust, question = found['timeline'], dict(found['trust']), found['question']
    kept = [(n, t) for n, t in found['parts'] if trust.get(label_key(n)) != 'ignored']
    left_out = [n for n, _ in found['parts'] if trust.get(label_key(n)) == 'ignored']
    names = [n for n, _ in kept]
    texts = [t for _, t in kept]

    linked = [0] * len(names)

    unread = [[] for _ in names]           # per part: the clauses its reader could not read

    def read(kinds):
        links = []
        readings = []
        for i, (n, t, k) in enumerate(zip(names, texts, kinds)):
            before = len(links)
            unread[i] = []
            readings.append(claims_from_text(n, t, i, timeline=timeline, kind=k, links=links, unread=unread[i]))
            linked[i] = len(links) - before
        return readings, links
    told = {label_key(n): trust[label_key(n)] for n in names if trust.get(label_key(n)) in ('trusted', 'doubted')}
    kinds = [told.get(label_key(n), 'stated') for n in names]
    readings, links = read(kinds)
    about_sources = sources_question(question, names, texts, readings)
    if about_sources is not None:
        return dict(reply=about_sources, state=State(), ask=None, timeline=timeline, trust=trust, why={}, names=names,
                    left_out=left_out, unread=unread)
    named = {c.entity for r in readings for c in r}
    if len({norm(e) for e in named}) == 1:
        # "Source 2 says it is on Tuesday": a part's leading "it" is the one thing the other parts named. The reader
        # of that part is told the name, as a reader on its own would ask.
        thing = sorted(named)[0]
        for i, t in enumerate(texts):
            if not readings[i] and LEAD_PRONOUN.search(t):
                texts[i] = LEAD_PRONOUN.sub(lambda m: m[1] + (m[2] or '') + ('the ' + thing if not thing[:1].isupper() else thing), t)
        readings, links = read(kinds)
    retracted = found.get('retracted') or {}
    if retracted:
        # "Witness 2 retracts the identification": its links are withdrawn; "... retracts the statement": all of it
        top = max([l.clock for l in links] + [c.clock for r in readings for c in r] + [0]) + 1000
        for l in list(links):
            if label_key(l.agent) in retracted and l.relation == 'same':
                links.append(Link(l.a, l.b, 'retract', l.agent, top))
        for i, n in enumerate(names):
            if retracted.get(label_key(n)) == 'all':
                readings[i] = []
    readable = [i for i, (r, l) in enumerate(zip(readings, linked)) if r or l]
    hearsay = [names[i] for i in range(len(names)) if i not in readable and REPORTED.search(texts[i])]
    # an account the reader could not read, but which is about the same thing ("As for the bin, ... might ..."), still counts:
    # its sentence is shown as unread, and it can make an answer uncertain
    named_words = {w for r in readings for c in r for w in c.key[0].split()} - DESCRIPTION_WORDS
    about = [i for i in range(len(names)) if i not in readable and any(set(re.findall(r'[a-z0-9]+', u.casefold())) & named_words for u in unread[i])]
    self_corrected = len(names) == 1 and readable and len(readings[0]) > 1    # "Log A: ..." then "Log A correction: ..."
    if len(readable) + len(about) + (1 if found['facts'] else 0) < 2 and not self_corrected and not (left_out and any(readings)) and not (readable and hearsay and
                                                                        len(readable) + len(hearsay) == len(names)):
        return None                         # not two parts with something the readers could establish
    # What the user knows first-hand ("It turns out Sam was in the kitchen") outranks every source. A source that
    # contradicted it is doubted on everything else it said, unless the user said to trust that source.
    facts = [] if timeline else [c for s in found['facts'] for c in claims_from_text('you', s, timeline=False, kind='confirmed')]
    why = {}
    if facts:
        view = State([c for r in readings for c in r] + facts, links).view()
        for fact in facts:
            mine = view.binding.name(fact.key[0])
            for r in readings:
                for c in r:
                    if c.op == 'set' and view.binding.name(c.key[0]) == mine and c.key[1] == fact.key[1] \
                            and value_key(c.value) != value_key(fact.value) and (not c.at or not fact.at or c.at == fact.at) \
                            and told.get(label_key(c.agent)) != 'trusted':
                        why.setdefault(label_key(c.agent), f'{c.agent} got {topic(view.display(mine), fact.key[1])} wrong, '
                                                           f'going by what you told me')
        if why:
            kinds = ['doubted' if label_key(n) in why else k for n, k in zip(names, kinds)]
            readings, links = read(kinds)
            for key in why:
                trust[key] = 'doubted'
    ask = question_of(question, {label_key(n) for n in names}, timeline)
    if ask is None:
        when = WHEN_ASKED.match(question)
        if when and norm(when[1]):
            keys = {c.key[1] for r in readings for c in r if c.key[0] == norm(when[1])}
            ask = dict(entity=when[1], attribute='day' if 'day' in keys or 'time' not in keys else 'time', expect=None, upto=None)
        elif WHICH.match(question):
            where = subject_of(readings)
            ask = dict(entity=where[0], attribute=where[1], expect=None, upto=None) if where else None
        else:
            m = DISAGREE_Q.match(question) or REMAINING_Q.match(question)
            if m:
                where = subject_of(readings, m['attr']) or (subject_of(readings) if not m['attr'] else None)
                if where:
                    ask = dict(entity=where[0], attribute=where[1], expect=None, upto=None,
                               disagree=m['verb'].lower() if 'verb' in m.re.groupindex and m['verb'] else None, certain=False)
        if ask is None:
            return None
    if norm(ask['entity']) in PRONOUNS or not norm(ask['entity']):
        # "Is it definitely still empty?": "it" is the one thing the accounts are about
        things = sorted({c.key[0] for r in readings for c in r} | {n for l in links for n in l.pair})
        attr = norm_attr(ask['attribute'])
        fitting = sorted({c.key[0] for r in readings for c in r if c.key[1] == attr}) or things
        if len(fitting) != 1:
            return None
        ask = dict(ask, entity=fitting[0])
    state = merged(State(r) for r in readings).merge(State(facts, links))
    reply = respond_from(state, ask, timeline, owned_only=True, trust=trust, parts=len(kept), names=names, why=why)
    if reply is None:
        return None
    if ask.get('disagree'):
        reply = dict(reply, response=disagreement(state, ask, reply))
    if ask['attribute'] == 'day' and ask.get('expect') is None:
        # "When is the meeting?": the time too, when any account gave one
        hour = state.view().get(ask['entity'], 'time')
        if hour.status == 'known':
            reply = dict(reply, response=reply['response'] + f' Time: **{hour.value}** ({", ".join(hour.support)}).')
        elif hour.status == 'conflict':
            reply = dict(reply, response=reply['response'] + ' The time differs: ' +
                         '; '.join(f'**{v}** ({", ".join(a)})' for v, a in hour.sides.items()) + '.')
    if left_out:
        reply = dict(reply, response=reply['response'] + ' (Left out, as you asked: ' + ', '.join(left_out) + '.)')
    if hearsay:
        reply = dict(reply, response=reply['response'] + f' {" and ".join(hearsay)} only passed on what someone else said, '
                                                        'so I did not count that as a sighting.')
    # Reader coverage: a sentence no reader understood never reaches the rules. When one is about the thing asked (by
    # any of its names, or through a pronoun in a part about it), say so: it might change the answer.
    view = state.view()
    key = norm(ask['entity'])
    members = view.binding.members[view.binding.find(key)] if key in view.binding.parent else {key}
    words = {w for m in members for w in m.split()} - DESCRIPTION_WORDS
    risky = []
    for i, clauses in enumerate(unread):
        about = any(view.binding.name(c.key[0]) == view.binding.name(key) for c in readings[i]) if key in view.binding.parent else False
        for u in clauses:
            said = set(re.findall(r"[a-z0-9]+", u.casefold()))
            if hearsay and names[i] in hearsay:
                continue
            if said & words or (about and re.match(r"(?i)\s*(?:then\s+|and\s+|later\s+)?(?:he|she|it|they|him|her|them)\b", u)):
                risky.append((names[i], u))
    if risky and ask.get('certain') and reply.get('route') == 'chat/swarm-known':
        # "Is it definitely still empty?" while a sentence about it could not be read: not for certain
        cell = view.get(ask['entity'], ask['attribute'])
        n, u = risky[0]
        reply = dict(reply, route='chat/swarm-uncertain',
                     response=f'**Not for certain.** {", ".join(cell.support)} said **{cell.value}**, but {n} also said "{u}", '
                              'which I could not read as a fact and cannot rule out.')
        risky = []
    if risky:
        shown = '; '.join(f'{n}: "{u}"' for n, u in risky[:3])
        reply = dict(reply, response=reply['response'] + f' I could not read {"this sentence" if len(risky) == 1 else "these sentences"}'
                                                        f', which may change the answer: {shown}.')
    reply = dict(reply, swarm=dict(reply.get('swarm') or {}, unread={n: u for n, u in zip(names, unread) if u}, risky=len(risky)))
    return dict(reply=reply, state=state, ask=ask, timeline=timeline, trust=trust, why=why, names=names, left_out=left_out,
                unread=unread)


def explain(turns):
    """'Why?' after a swarm answer: what each source said about the thing asked, in its own words, and the rule that
    decided between them."""
    if len(turns) < 2 or not WHY.match(turns[-1]):
        return None
    done = solve(turns[:-1])
    if done is None:
        return None
    state, ask, reply = done['state'], done['ask'], done['reply']
    view = state.view()
    entity, attribute = ask['entity'], ask['attribute']
    claims = sorted(cell_claims(state, view, entity, attribute), key=lambda c: (c.agent != 'you', c.at, c.agent, c.clock))
    if not claims:
        return None
    cell = view.get(entity, attribute)
    winners = set(cell.support) | {a for agents in cell.sides.values() for a in agents}
    lines = []
    for c in claims:
        who = 'You told me' if c.agent == 'you' else c.agent
        quote = c.evidence or f'{c.entity} {c.attribute} {c.value}'
        when = f'at {clock_text(c.at[0])}, ' if not done['timeline'] and c.at else ''
        latest = max((x.at for x in claims if x.agent in winners), default=())
        if c.agent in winners:
            used = 'one side of the disagreement' if cell.status == 'conflict' else 'used'
        elif done['why'].get(label_key(c.agent)):
            used = 'set aside: ' + done['why'][label_key(c.agent)]
        elif c.kind == 'doubted':
            used = 'set aside: you said not to rely on it'
        elif done['timeline']:
            used = 'replaced by a later part'
        elif c.at and latest and c.at < latest:
            used = 'an earlier sighting'
        else:
            used = 'outranked'
        lines.append(f'- {who}: "{quote}" ({when}{used})')
    timed = not done['timeline'] and len({c.at for c in claims if c.at}) > 1
    if done['timeline']:
        rule = 'The parts are in order, so a later part replaces an earlier one, and changes add up from the last value.'
    elif timed and cell.status == 'known':
        rule = ('The sightings were at different times, so the latest one says where things stand now; earlier ones '
                'are not wrong, just older.')
    elif cell.status == 'conflict':
        rule = ('The accounts describe the same moment and none outranks the others, so I did not pick one. Two against '
                'one is not proof.')
    else:
        rule = ('What you told me outranks every source, a source you said to trust outranks the rest, and a source you '
                'doubted, or one that got something wrong, counts least. Counting heads is never the rule.')
    live = live_links(state.links)
    mine = view.binding.find(norm(entity)) if norm(entity) in view.binding.parent else None
    for link in sorted(state.links, key=lambda l: (l.agent, l.clock)):
        if not ({view.binding.find(n) for n in link.pair if n in view.binding.parent} & {mine}) and norm(entity) not in link.pair:
            continue
        if link in live and link.relation == 'same':
            lines.append(f'- {link.agent}: "{link.a} was {link.b}" (so they are the same person)')
        elif link not in live:
            lines.append(f'- {link.agent}: "{link.a} was {link.b}" (withdrawn: {link.agent} corrected it later, so nothing rests on it)')
    for n, clauses in zip(done['names'], done.get('unread') or []):
        for u in clauses:
            lines.append(f'- {n}: "{u}" (not read: I could not follow this sentence, so it did not count)')
    for n in done['left_out']:
        lines.append(f'- {n} (left out, as you asked)')
    text = f'Here is what each source said about {topic(view.display(view.binding.name(norm(entity))), attribute)}:\n' \
           + '\n'.join(lines) + '\n' + rule
    return {'route': 'chat/swarm-why', 'response': text, 'sources': [],
            'swarm': dict(reply.get('swarm') or {}, explained=True)}


def chat_reply(messages):
    """The Swarm desk: labelled parts or accounts and one question, in the last message or spread over the user's
    messages. Each part gets its own reader; what the user said about trusting a source sets that reader's evidence
    kind (trusted above stated, doubted below), "ignore Report C" leaves a part out, and what the user knows first-hand
    outranks every source. "Why?" afterwards shows each source's words."""
    if not isinstance(messages, list) or not messages or messages[-1].get('role') != 'user':
        return None
    turns = [str(m.get('content') or '') for m in messages if m.get('role') == 'user'][-12:]
    if sum(map(len, turns)) > 200_000:
        return None
    why = explain(turns)
    if why is not None:
        return why
    done = solve(turns)
    if done is None:
        return noted(turns) or personal(turns) or personal_noted(turns)
    return done['reply']


def describe(entity, attribute, value):
    """'Sam was in the kitchen', 'the van was white', 'the meeting is on Monday', "Ana's apples: 3"."""
    thing = entity if entity[:1].isupper() else 'the ' + entity
    if attribute == 'location':
        return f'{thing} was in the **{value}**'
    if attribute in ('colour', 'mood', 'height', 'state'):
        return f'{thing} was **{value}**'
    if attribute == 'day':
        return f'{thing} is on **{value}**'
    if attribute == 'time':
        return f'{thing} is at **{value}**'
    return f"{thing}'s {attribute}: **{value}**"


def topic(entity, attribute):
    thing = entity if entity[:1].isupper() else 'the ' + entity
    return {'location': f'where {thing} was', 'day': f'the day of {thing}', 'time': f'the time of {thing}'}.get(
        attribute, f"{thing}'s {attribute}")


def noted(turns):
    """A message that is only labelled accounts or parts, with no question yet: say what each reader took from it,
    and whether the accounts so far agree, instead of answering it as small talk. Every sentence of the parts must be
    one the readers understood; otherwise the message is left to the other desks."""
    last = turns[-1]
    here = segments(last)
    if not here or '?' in last or last[:LABEL.search(last).start()].strip():
        return None
    timeline = bool(re.search(r'(?i)\b(?:' + TIMELINE + r')\b', here[0][0]))
    earlier = [(label, body) for t in turns[:-1] for label, body in segments(t)]
    readings = []
    for i, (label, body) in enumerate(here):
        unread = []
        got = claims_from_text(label, body, len(earlier) + i, timeline=timeline, unread=unread)
        if not got or unread:
            return None
        readings.append((label, got))
    said = ' '.join(f'{label}: ' + ', '.join(describe(c.entity, c.attribute, c.value) for c in got) + '.'
                    for label, got in readings)
    clash = ''
    if not timeline:
        everything = [c for t in turns for label, body in segments(t) for c in claims_from_text(label, body, timeline=False)]
        view = State(everything).view()
        split = [topic(view.display(e), a) for e, cells in view.cells.items() for a, cell in cells.items()
                 if cell.status == 'conflict']
        if split:
            clash = ' So far the accounts differ on ' + ', '.join(split) + '.'
    return {'route': 'chat/swarm-noted', 'response': f'Noted. {said}{clash} Add more accounts, or ask your question.',
            'sources': [], 'swarm': {'noted': [label for label, _ in readings], 'timeline': timeline}}


PERSONAL = {'location', 'day', 'time', *FAMILIES}


def personal(turns):
    """No labels: the user's own statements are one reader ('you'). Answers only a question about something the user
    stated, when that value is known ("My car is red. What colour is my car?"), and leaves everything else to the
    other desks. If the user said something about the same thing that the reader could not read ("my car got
    resprayed"), it does not answer from the older statement."""
    last = turns[-1]
    sentences = [s.strip() for s in SENTENCES.split(last) if s.strip()]
    asks = [s for s in sentences if s.endswith('?')]
    if not asks:
        return None
    question = asks[-1]
    ask = question_of(question, (), True)
    when = WHEN_ASKED.match(question) if ask is None else None
    if when and norm(when[1]):
        hour = bool(re.match(r'(?i)\s*what time', question))
        ask = dict(entity=when[1], attribute='time' if hour else 'day', expect=None, upto=None)
    if ask is None:
        m = re.match(r"(?i)^\s*what colou?r (?:is|are|was|were) (it|they|that|this)\s*\?", question)
        if m:
            ask = dict(entity=m[1], attribute='colour', expect=None, upto=None)
    if ask is None or ask.get('upto') or norm_attr(ask['attribute']) not in PERSONAL:
        return None                         # counts and sums stay with the quantity helpers and event memory
    claims, unread, subject = [], [], None
    for i, t in enumerate(turns):
        body = t if i < len(turns) - 1 else ' '.join(s for s in sentences if not s.endswith('?'))
        if subject:
            # "I moved it to the porch": "it" is the thing the last statement was about
            body = re.sub(r"(?i)\b(moved|put|took|carried|brought|placed|left|hid|stored|dropped|hung|threw|stashed|parked)\s+(it|them)\b",
                          lambda m: f'{m[1]} the {subject}', body)
            # "It got moved to Friday": "it" is that thing too
            body = re.sub(r"(?i)(^|(?<=[.!?])\s+)(?:(?:actually|then|later|but|now)[,\s]+)?(it|they)\b(?=\s+(?:got|has|have|was|were|is|are|had)\b)",
                          lambda m: f'{m[1]}the {subject}', body)
        got = claims_from_text('you', body, i, clock=i * 1000, unread=unread)
        if got:
            subject = got[-1].key[0]
        claims += got
    if not claims:
        return None
    view = State(claims).view()
    key = norm(ask['entity'])
    if not key or key in PRONOUNS:
        # "Where are they?", "What colour is it?": the thing told about that has this attribute
        fits = sorted({view.binding.name(c.key[0]) for c in claims if c.key[1] == norm_attr(ask['attribute'])})
        if len(fits) > 1:
            options = [f'your {f}' if any(re.match(r'(?i)\s*(?:my|our)\b', t) for t in turns) else f'the {f}' for f in fits]
            shown = ' and '.join(f'{o} is **{view.get(f, ask["attribute"]).value}**' for o, f in zip(options, fits))
            return {'route': 'chat/swarm-personal-which', 'sources': [], 'swarm': {'readers': ['you'], 'claims': len(claims)},
                    'response': f'You told me about more than one thing: {shown}. Which one do you mean?'}
        if len(fits) != 1:
            return None
        key = fits[0]
        ask = dict(ask, entity=key)
    cell = view.get(ask['entity'], attribute=ask['attribute'])
    if key not in view.binding.parent or cell.status != 'known':
        return None
    names = view.binding.members[view.binding.find(key)]
    words = {w for n in names for w in n.split()}
    if any(words & set(re.findall(r"[a-z0-9]+", u.casefold())) for u in unread):
        return None                         # something else was said about it that the reader could not follow
    if ask.get('expect') is not None:
        same = value_key(cell.value) == value_key(ask['expect'])
        text = ('**Yes**' if same else '**No**') + f', {cell.value}, as you told me.'
    elif ask['attribute'] == 'location':
        text = f'In the **{cell.value}**, as you told me.'
    else:
        text = f'**{cell.value}**, as you told me.'
    return {'route': 'chat/swarm-personal', 'response': text, 'sources': [],
            'swarm': {'readers': ['you'], 'claims': len(claims), 'status': cell.status},
            'details': 'Read from your own messages by one reader (swarm.py); the latest thing you said wins.'}


def personal_noted(turns):
    """A message that only tells where or how one of the user's own things is ("My keys are in the kitchen.", "My car
    is red now."): say it is noted. Every sentence must be read, and each must be about "my" or "our" something."""
    last = turns[-1].strip()
    if '?' in last or len(last) > 300:
        return None
    sentences = [s.strip() for s in SENTENCES.split(last) if s.strip()]
    told = []
    for s in sentences:
        unread = []
        got = claims_from_text('you', s, unread=unread)
        bare = TAIL.sub('', LEAD.sub('', s.rstrip('.!')))
        if unread or len(got) != 1 or got[0].key[1] not in PERSONAL or got[0].key[1] == 'mood'                 or not re.match(r'(?i)(?:my|our)\s', bare):
            return None                     # a person's mood ("My boss is angry") is for the listening desks
        told.append(re.sub(r'(?i)^(?:my|our)\b', 'your', bare))
    if not told:
        return None
    said = '; '.join(told)
    return {'route': 'chat/swarm-personal-noted', 'response': f'Noted: {said}. Ask me any time.', 'sources': [],
            'swarm': {'readers': ['you'], 'claims': len(told)}}
