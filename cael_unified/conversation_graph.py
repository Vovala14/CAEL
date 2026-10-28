"""Bounded symbolic joins over explicitly stated conversation facts.

This extends the existing integer-record memory, without a learned/neural parser.
Only user statements are evidence. Ownership does not imply physical location;
reported, hypothetical and negated claims are never promoted to direct facts.
The graph and its interned strings are local to one request, not shared sessions.
"""
from array import array
import re

MAX_FACTS = 3000
ENTITY = r"[\w][\w '\-]{0,90}?"
ROLES = frozenset(('mentor', 'manager', 'supervisor', 'assistant', 'teacher', 'tutor',
                   'sister', 'brother', 'mother', 'father', 'aunt', 'uncle', 'cousin',
                   'friend', 'partner', 'colleague', 'neighbor', 'neighbour', 'doctor'))
PROPERTIES = frozenset(('colour', 'color', 'code', 'number', 'name', 'size', 'address',
                        'job', 'profession', 'subject', 'specialty', 'speciality'))
UNSUPPORTED = re.compile(r"\b(?:if|unless|would|could|might|maybe|perhaps|imagine|pretend|wish|"
                         r"wishes|wished|hopes?|hypothetical|suppose|plans? to|planning to|"
                         r"wants? to|said|says|claims?|believes?|thinks?|told|not|never)\b|n't\b", re.I)
UPDATE = re.compile(r"\b(?:now|currently|moved|relocated|changed|correction|actually|instead|"
                    r"replaced|transferred|put|placed|gave|handed|passed|picked up|dropped)\b", re.I)
DETAILS = ('Joined explicit user facts from this chat using bounded integer records. '
           'Evidence indices identify the user messages used. Ownership alone is not physical location. '
           'The graph is rebuilt for each request and never carries facts into another session.')


def clean(text):
    text = re.sub(r"\s+", ' ', text.strip().replace('\u2019', "'")).strip(' .,!?:;')
    text = re.sub(r'^(?:the|a|an)\s+', '', text, flags=re.I)
    return text


class Graph:
    def __init__(self, messages):
        self.ids, self.words = {}, []
        self.records = array('i')  # subject, relation, value, message index, explicit-update flag
        self.cells = {}
        self.invalidations = {}
        self.aliases = {}
        self.shown = {}
        self.person = None
        self.people = set()
        self.thing = None
        self.previous_question = None
        self.previous_subject = None
        for index, message in enumerate(messages):
            if message.get('role') != 'user':
                continue
            content = message.get('content', '').replace('\u2019', "'")
            if '?' in content and re.match(r'(?i)^\s*(?:where|who|what|which|and)\b', content):
                parsed = self.query(content)
                if parsed:
                    self.previous_question, self.previous_subject = parsed
                    resolved, _, conflicts = self.resolve(self.previous_subject)
                    if resolved and not conflicts:
                        self.previous_subject = resolved
                continue
            for sentence in re.split(r'(?<=[.!?])\s+|[;\n]+', content):
                if len(self.records) // 5 >= MAX_FACTS:
                    return
                self.read(sentence, index)

    def intern(self, word):
        if word not in self.ids:
            self.ids[word] = len(self.words)
            self.words.append(word)
        return self.ids[word]

    def entity(self, text, remember=False, person=False):
        shown = re.sub(r'\s+', ' ', text.strip()).strip(' .,!?:;')
        text = clean(text)
        low = text.lower()
        low = re.sub(r'\s+(?:now|currently|today|at present)$', '', low)
        if low in ('he', 'him', 'she', 'her', 'they', 'them'):
            return self.person
        if low in ('it', 'that', 'this', 'that one', 'this one'):
            return self.thing
        if low in ('i', 'me', 'myself', 'we', 'us'):
            low, text = 'user', 'You'
            shown = 'You'
        if not low or len(low.split()) > 9 or re.search(r'\b(?:and|or|if|because)\b', low):
            return None
        # A named family/professional role creates a safe alias, not a guess from names.
        named = re.fullmatch(r'((?i:my|our)) (\w+) ([A-Z][\w-]+)', text)
        if named and named[2].lower() in ROLES:
            self.aliases[(named[1] + ' ' + named[2]).lower()] = named[3].lower()
            low, text, person = named[3].lower(), named[3], True
            shown = text
        low = self.aliases.get(low, low)
        self.shown.setdefault(low, shown)
        if remember:
            if person:
                self.person = low
                self.people.add(low)
            elif low != 'user':
                self.thing = low
        return low

    def add(self, subject, relation, value, index, update=False):
        if not subject or not value or len(self.records) // 5 >= MAX_FACTS:
            return
        value = self.entity(value)
        if not value or subject == value:
            return
        key = (self.intern(subject), self.intern(relation))
        row = (key[0], key[1], self.intern(value), index, int(update))
        self.records.extend(row)
        if update:
            self.cells[key] = [row]
        elif row[2] not in [r[2] for r in self.cells.get(key, [])]:
            self.cells.setdefault(key, []).append(row)

    def read(self, text, index):
        text = text.strip(' \t-*')
        if not text or '?' in text:
            return
        # A direct negation retracts that value; it never invents its opposite.
        negative = re.fullmatch(rf"({ENTITY}) (?:is not|is no longer|isn't) (?:in|at|inside|on) ({ENTITY})[.!]?", text, re.I)
        if negative:
            subject, value = self.entity(negative[1]), self.entity(negative[2])
            rows = self.cell(subject, 'location')
            if rows:
                key = (self.ids[subject], self.ids['location'])
                self.cells[key] = [r for r in rows if self.words[r[2]] != value]
                self.invalidations.setdefault(key, []).append(index)
            return
        if UNSUPPORTED.search(text):
            return
        updated = bool(UPDATE.search(text))
        text = re.sub(r'(?i)^(?:correction|update|actually|now)[,:]\s*', '', text)
        text = text.rstrip('.!')
        m = re.fullmatch(rf"(?:my|our) (\w+) is ({ENTITY})", text, re.I)
        if m and m[1].lower() in ROLES:
            self.add('user', m[1].lower(), m[2], index, updated)
            self.entity(m[2], remember=True, person=True)
            return
        # Explicit nested relation: "Tess's mentor is Oren" / "Oren is Tess's mentor".
        m = re.fullmatch(rf"({ENTITY})'s (\w+) is ({ENTITY})", text, re.I)
        if m and m[2].lower() in ROLES | PROPERTIES:
            subject = self.entity(m[1], remember=True, person=m[2].lower() in ROLES)
            self.add(subject, m[2].lower().replace('color', 'colour'), m[3], index, updated)
            return
        m = re.fullmatch(rf"({ENTITY}) is ({ENTITY})'s (\w+)", text, re.I)
        if m and m[3].lower() in ROLES:
            subject = self.entity(m[2], remember=True, person=True)
            self.add(subject, m[3].lower(), m[1], index, updated)
            return
        # Current physical state and changes. A home/workplace is a separate relation.
        m = re.fullmatch(rf"({ENTITY}) (lives?|works?|is based|resides?|moved|relocated) (?:in|at|to) ({ENTITY})(?: now| currently)?", text, re.I)
        if m:
            subject = self.entity(m[1], remember=True, person=True)
            relation = 'work' if m[2].lower().startswith('work') else 'location' if m[2].lower() in ('moved', 'relocated') else 'home'
            self.add(subject, relation, m[3], index, updated)
            return
        m = re.fullmatch(rf"({ENTITY}) (?:is|are) (?:now |currently )?(in|inside|at|on|with) ({ENTITY})(?: now| currently)?", text, re.I)
        if m:
            subject = self.entity(m[1], remember=True)
            self.add(subject, 'location', m[3], index, updated)
            return
        m = re.fullmatch(rf"({ENTITY}) (?:put|placed|moved) ({ENTITY}) (?:in|inside|at|on|into|to) ({ENTITY})", text, re.I)
        if m:
            self.entity(m[1], remember=True, person=True)
            subject = self.entity(m[2], remember=True)
            self.add(subject, 'location', m[3], index, True)
            return
        # Carrying gives a physical link; merely owning something does not.
        m = re.fullmatch(rf"({ENTITY}) (owns?|has|have|carries|carry|holds?|is carrying|is holding|picked up) ({ENTITY})", text, re.I)
        if m:
            person = self.entity(m[1], remember=True, person=True)
            obj = self.entity(m[3], remember=True)
            verb = m[2].lower()
            self.add(obj, 'holder' if verb not in ('owns', 'own') else 'owner', person, index, updated)
            if verb not in ('owns', 'own', 'has', 'have'):
                self.add(obj, 'location', person, index, True)
            return
        # A transfer changes custody explicitly; it does not assert legal ownership.
        m = re.fullmatch(rf"({ENTITY}) (?:gave|handed|passed) ({ENTITY}) to ({ENTITY})", text, re.I)
        if m:
            obj = self.entity(m[2], remember=True)
            recipient = self.entity(m[3], remember=True, person=True)
            self.add(obj, 'holder', recipient, index, True)
            self.add(obj, 'location', recipient, index, True)
            return
        m = re.fullmatch(rf"({ENTITY}) teach(?:es)? ([\w -]+?)(?: at (?:a |an |the )?[\w -]+)?", text, re.I)
        if m:
            self.add(self.entity(m[1], remember=True, person=True), 'subject', m[2], index, updated)
            return
        m = re.fullmatch(rf"({ENTITY}) (?:is|are) ([\w-]+)", text, re.I)
        if m and m[2].lower() in ('red', 'blue', 'green', 'yellow', 'black', 'white', 'orange', 'purple', 'silver', 'grey', 'gray'):
            self.add(self.entity(m[1], remember=True), 'colour', m[2], index, updated)

    def query(self, text):
        text = clean(text)
        text = re.sub(r"(?i)^(where|who|what)'s\b", r'\1 is', text)
        text = re.sub(r"(?i)^(?:(?:and|so|remind me|please|tell me)[, :]*)+", '', text)
        m = re.fullmatch(rf"where (?:does|do) ({ENTITY}) (live|work)", text, re.I)
        if m:
            return ('home' if m[2].lower() == 'live' else 'work', m[1])
        m = re.fullmatch(rf"where (?:is|are) ({ENTITY})(?: now| currently)?", text, re.I)
        if m:
            return ('location', m[1])
        m = re.fullmatch(rf"who (owns|has|holds|is holding|is carrying) ({ENTITY})(?: now)?", text, re.I)
        if m:
            return ('owner' if m[1].lower() == 'owns' else 'holder', m[2])
        m = re.fullmatch(rf"(?:what|who) (?:is|are) ({ENTITY})'s (\w+)", text, re.I)
        if m and m[2].lower() in ROLES | PROPERTIES:
            return (m[2].lower().replace('color', 'colour'), m[1])
        m = re.fullmatch(rf"what (?:colou?r|subject) (?:is|does|do) ({ENTITY})(?: teach)?", text, re.I)
        if m:
            return ('subject' if 'subject' in text.lower() else 'colour', m[1])
        m = re.fullmatch(rf"(?:what about )?((?:his|her|their|my|our) \w+|{ENTITY}'s \w+)", text, re.I)
        if m and self.previous_question in ('home', 'work', 'location', 'colour'):
            return self.previous_question, m[1]
        return None

    def cell(self, subject, relation):
        if subject not in self.ids or relation not in self.ids:
            return []
        return self.cells.get((self.ids[subject], self.ids[relation]), [])

    def resolve(self, text, depth=0):
        """Possessive joins are bounded, cycle checked by depth, and must be unique."""
        if depth > 4:
            return None, [], []
        text = clean(text)
        low = text.lower()
        if low.startswith(('his ', 'her ', 'their ')):
            person = self.previous_subject if self.previous_subject in self.people else self.person
            if not person:
                return None, [], []
            text = person + "'s " + low.split(' ', 1)[1]
        elif low.startswith(('my ', 'our ')) and low in self.aliases:
            return self.aliases[low], [], []
        elif low.startswith(('my ', 'our ')) and low.split(' ', 1)[1] in ROLES:
            text = "user's " + low.split(' ', 1)[1]
        if "'s " not in text:
            return self.entity(text), [], []
        parent, role = text.rsplit("'s ", 1)
        if role.lower() not in ROLES | PROPERTIES:
            return self.entity(text), [], []
        subject, evidence, conflict = self.resolve(parent, depth + 1)
        if not subject or conflict:
            return None, evidence, conflict
        rows = self.cell(subject, role.lower().replace('color', 'colour'))
        if len(rows) != 1:
            return None, evidence, [self.words[r[2]] for r in rows]
        return self.words[rows[0][2]], evidence + [rows[0][3]], []

    def locate(self, subject):
        evidence, visited, last = [], set(), None
        while subject not in visited and len(visited) < 8:
            visited.add(subject)
            rows = self.cell(subject, 'location')
            if len(rows) > 1:
                return None, evidence, [self.words[r[2]] for r in rows]
            if not rows:
                if subject in self.ids and 'location' in self.ids:
                    evidence += self.invalidations.get((self.ids[subject], self.ids['location']), [])
                return last, evidence, []
            last = self.words[rows[0][2]]
            evidence.append(rows[0][3])
            subject = last
        # Cyclic containment is inconsistent evidence, not an arbitrary final place.
        return None, evidence, ['a circular location chain']

    def display(self, value):
        shown = self.shown.get(value, value)
        return re.sub(r'^(The|A|An)\s', lambda m: m[0].lower(), shown)


def reply(messages):
    if not messages or messages[-1].get('role') != 'user':
        return None
    # Cheap gate: do not construct a graph for general prose, advice or tool requests.
    question = messages[-1].get('content', '')
    if not re.match(r"(?i)^\s*(?:where|who|what|and|remind me|please tell me)\b", question):
        return None
    graph = Graph(messages[:-1])
    parsed = graph.query(question)
    if not parsed:
        return None
    relation, reference = parsed
    subject, evidence, conflict = graph.resolve(reference)
    if subject not in graph.ids and not conflict:
        return None
    if relation == 'location' and subject:
        value, more, conflict = graph.locate(subject)
        evidence += more
    else:
        rows = graph.cell(subject, relation) if subject else []
        if not conflict:
            conflict = [graph.words[r[2]] for r in rows] if len(rows) > 1 else []
        value = graph.words[rows[0][2]] if len(rows) == 1 else None
        evidence += [r[3] for r in rows]
    # Existing memory remains responsible for single-hop recall. Claim precedence
    # only for an actual join, safe follow-up, transfer, or newly scoped property.
    joined = "'s " in reference or re.match(r'(?i)(?:his|her|their) ', reference)
    followup = bool(graph.previous_question and not re.match(r'(?i)^(?:where|who|what)\b', clean(question)))
    if not (joined or followup or len(evidence) > 1 or relation in ('holder', 'owner', 'subject')):
        return None
    result = {'route': 'chat/context-graph', 'sources': [], 'details': DETAILS,
              'evidence_messages': sorted(set(evidence)), 'operation': 'symbolic_join'}
    if conflict:
        result.update(response='I have conflicting information about ' + clean(reference) + ': ' +
                      ' or '.join(graph.display(v) for v in conflict) + '. Can you clarify which is right?',
                      confidence=0.5, conflict=True)
    elif value:
        label = graph.display(subject)
        shown = graph.display(value)
        if relation in ('holder', 'owner'):
            verb = ('own' if value == 'user' else 'owns') if relation == 'owner' else ('have' if value == 'user' else 'has')
            text = f'{shown} {verb} {label}.'
        elif relation in ('home', 'work'):
            verb = ('live' if subject == 'user' else 'lives') if relation == 'home' else ('work' if subject == 'user' else 'works')
            text = f'{label} {verb} in {shown}.'
        elif relation == 'location':
            text = f'{label} is in {shown}.'
        elif relation == 'subject':
            text = f'{label} {"teach" if subject == "user" else "teaches"} {shown}.'
        else:
            text = f"{label}'s {relation} is {shown}."
        result.update(response=text[0].upper() + text[1:], confidence=0.9)
    elif joined or followup:
        requested = {'work': 'workplace', 'home': 'home city'}.get(relation, relation)
        result.update(response="I don't know: you haven't stated the " + requested + ' of ' + clean(reference) + '.',
                      confidence=0.2, abstain=True)
    else:
        return None
    return result
