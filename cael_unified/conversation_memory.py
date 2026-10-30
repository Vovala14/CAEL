"""Structured conversation memory: who/what/where/when facts, updates, conflicts and plans from the open chat window.

Non-neural. Every request carries the whole conversation; this module re-reads the user's messages with authored
sentence frames and keeps what they state as compact integer records instead of text:

    record = (message index, subject id, attribute id, value id, kind, source id)      # six ints, array('i')

Strings are interned once (one table per conversation), so a long chat compresses to a few dozen ints per fact.
Kinds: STATE (said plainly), CHANGE (moved / now / painted / became ...), CORRECTION (sorry, I meant ...),
CLAIM (someone else said it: "Ben says ..."), PAST (no longer / used to).

Answers come only from these records:
  * the current value is the latest STATE/CHANGE/CORRECTION; older values are history ("before that, Paris");
  * two plain statements that disagree about the same thing, or two people who disagree, are a conflict: the
    answer names both and asks which is right (a marked correction or change is not a conflict);
  * pronouns (he, she, it, they, his, her, its, their) resolve to the most recent fitting entity; "my sister"
    resolves to the person the user named as their sister;
  * a plan (goal + steps) tracks finished, skipped and added steps.
Nothing is stored after the window closes.
"""
from array import array
from functools import lru_cache
import json
import re
import sqlite3

from .bundle import ROOT

# Every improvement can be switched off for the before/after ladder in benchmarks/context_035 (all on by default):
#   references (pronouns, "my sister" -> name), updates (history, corrections, "no longer"), conflicts, planning.
FEATURES_ENV = 'CAEL_CONTEXT_FEATURES'


def on(feature):
    import os
    value = os.environ.get(FEATURES_ENV)
    return value is None or feature in value.split(',')

DETAILS = ('Recalled from your earlier messages in this chat window: each statement is kept as a small integer record '
           '(who, what, value, when said, how sure), so later changes and contradictions can be tracked. Nothing is '
           'stored after the window closes.')
WORDNET = ROOT / 'models' / 'cael-dictionary-wn30' / 'dictionary.sqlite'

STATE, CHANGE, CORRECTION, CLAIM, PAST = range(5)
DAYS = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday', 'today', 'tomorrow', 'tonight', 'weekend')
DAY = r'(?:mon|tues|wednes|thurs|fri|satur|sun)day|tomorrow|today|tonight|the weekend'
TIME = r'\d{1,2}(?::\d\d)?\s?(?:am|pm|a\.m\.|p\.m\.)|noon|midnight'
NUMBER = r'\d[\d,]*(?:\.\d+)?'
MONEY = r'(?:\$\s?)?(' + NUMBER + r')(?:\s?(?:dollars|usd|euros?|eur|pounds|gbp|bucks|\$))?'
COLORS = {'red', 'blue', 'green', 'yellow', 'black', 'white', 'silver', 'orange', 'purple', 'grey', 'gray', 'pink', 'brown', 'gold',
          'beige', 'navy', 'teal', 'maroon', 'turquoise', 'violet', 'cream', 'golden', 'dark blue', 'light blue', 'dark green'}
FEMALE = {'sister', 'mother', 'mom', 'mum', 'aunt', 'wife', 'girlfriend', 'daughter', 'niece', 'grandmother', 'grandma', 'fiancee'}
MALE = {'brother', 'father', 'dad', 'uncle', 'husband', 'boyfriend', 'son', 'nephew', 'grandfather', 'grandpa', 'fiance'}
SOCIAL = {'friend', 'best friend', 'neighbor', 'neighbour', 'coworker', 'co-worker', 'colleague', 'roommate', 'flatmate', 'boss',
          'manager', 'partner', 'classmate', 'cousin', 'teammate', 'landlord', 'landlady', 'mentor', 'tutor', 'doctor', 'dentist',
          'therapist', 'trainer', 'teacher', 'child', 'kid', 'parent', 'spouse', 'grandparent', 'grandchild', 'sibling', 'twin'}
RELATIONS = FEMALE | MALE | SOCIAL
OCCUPATIONAL = {'teacher', 'doctor', 'dentist', 'therapist', 'trainer', 'tutor', 'manager', 'mentor', 'landlord', 'landlady', 'boss'}
NOT_JOBS = (RELATIONS - OCCUPATIONAL) | {'person', 'man', 'woman', 'guy', 'girl', 'boy', 'kid', 'fan', 'student', 'native', 'friend', 'member', 'adult',
                        'vegetarian', 'vegan', 'genius', 'nice', 'good', 'great', 'bit', 'lot'}
CHANGE_CUES = r'\b(?:moved|moving|relocated|relocating|now|anymore|any more|no longer|changed?|switched|quit|became|become|new|' \
              r'painted|repainted|again|update|updated|instead|decided|from now on|these days|nowadays|took .{1,20} out|' \
              r'packed up|let us|let\'s|make it|set it|final|rescheduled|postponed|pushed|bumped|raised|cut|lowered|increased|' \
              r'reduced|shifted|since|later|went from|settled|said goodbye|new address|gave up|left the|retrained|retired|' \
              r'swapped|replaced|turned into|is in \w+ now|at present)\b'
CORRECTION_CUES = r'^(?:actually|sorry|oops|correction|wait|scratch that|let me correct|my mistake|i meant|i mean|no,|no wait|' \
                  r'i was wrong|to correct|i misspoke|not \w+,)|\bi (?:meant|mean)\b|\bnot \w+\s*$|\bi was wrong\b|' \
                  r'\bmy mistake\b|\bcorrection\b|\blet me correct\b|\bscratch that\b|\bmy bad\b|\bgot that wrong\b|^hmm,? no\b|' \
                  r'\bmisspoke\b|\bthat was wrong\b|\bi mixed (?:it|that|them) up\b'
STOP = {'the', 'a', 'an', 'my', 'our', 'your', 'is', 'are', 'was', 'were', 'be', 'will', 'to', 'of', 'in', 'on', 'at', 'for', 'with',
        'and', 'or', 'i', 'we', 'you', 'it', 'its', 'this', 'that', 'what', 'when', 'where', 'which', 'who', 'how', 'do', 'does', 'did',
        'am', 'have', 'has', 'had', 'me', 'us', 'now', 'day', 'time', 'place', 'remind', 'can', 'could', 'please', 'tell', 'again',
        'there', 'then', 'so', 'just', 'about', 'by', 'from', 'up', 'set', 'get', 'go', 'going', 'happen', 'happens', 'take', 'takes',
        'actually', 'sorry', 'oops', 'correction', 'wait', 'scratch', 'mistake', 'meant', 'mean', 'not', 'let', 'correct', 'wrong',
        'here', 'one', 'pick', 'picked', 'did', 'held', 'won', 'right', 'know', 'you', 'say', 'says', 'said', 'told', 'thinks',
        'insists', 'sure', 'according', 'but', 'also', 'okay', 'ok', 'oh', 'well', 'currently', 'moment', 'current', 'booked'}
PRONOUN = {'he': 'm', 'him': 'm', 'his': 'm', 'she': 'f', 'her': 'f', 'hers': 'f', 'they': 'p', 'them': 'p', 'their': 'p', 'it': 'n', 'its': 'n'}
NAME_STOP = {'The', 'My', 'We', 'They', 'It', 'He', 'She', 'I', 'Its', 'Their', 'His', 'Her', 'Our', 'This', 'That', 'There', 'Here',
             'Now', 'Last', 'Next', 'Sorry', 'Actually', 'Also', 'But', 'And', 'So', 'Oops', 'Update', 'Correction', 'Wait', 'Done',
             'Help', 'Let', 'Change', 'Drop', 'Add', 'One', 'Please', 'Final', 'Make', 'According', 'Scratch', 'Home', 'By', 'Then',
             'What', 'Where', 'When', 'Who', 'Which', 'How', 'Do', 'Does', 'Did', 'Is', 'Are', 'Can', 'Remind', 'Yes', 'No', 'Ok',
             'Okay', 'Oh', 'Well', 'Hi', 'Hello', 'Thanks', 'Thank', 'Plan', 'Steps', 'Step', 'First', 'Finally', 'Today', 'Tomorrow',
             'You', 'Your', 'Changed', 'New', 'Set', 'Not', 'Just', 'If', 'In', 'On', 'At', 'For', 'With', 'From', 'To', 'Of', 'A', 'An',
             'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday', 'January', 'February', 'March', 'April',
             'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December', 'These', 'Those', 'Traffic', 'Some',
             'Still', 'Every', 'Each', 'Both', 'All', 'Any', 'Most', 'Many', 'Much', 'More', 'Less', 'Very', 'Really', 'Kids', 'Mom', 'Dad',
             'Nothing', 'Someone', 'Somebody', 'Everyone', 'Everybody', 'Nobody', 'Anyone', 'Something', 'Everything', 'Anything',
             'Tonight', 'Yesterday', 'Later', 'Earlier', 'Soon', 'Maybe', 'Perhaps', 'Honestly', 'Sadly', 'Luckily', 'Hopefully',
             'Apparently', 'Personally', 'Usually', 'Sometimes', 'Never', 'Always', 'Often', 'Instead', 'Otherwise', 'Meanwhile',
             'Recently', 'Lately', 'Again', 'Already', 'Unfortunately', 'Fortunately', 'Obviously', 'Basically', 'Literally', 'Guess',
             'Big', 'Good', 'Great', 'Hmm', 'Oh', 'Wow', 'Cross', 'Forget', 'Ticked', 'Just', 'Write', 'Buy', 'Back', 'During',
             'After', 'Before', 'Since', 'Over', 'Once', 'Lol', 'Btw', 'Random', 'Funny', 'Speaking', 'Apparently', 'Ugh', 'Wow',
             'Yay', 'Hey', 'Meh', 'Ooh', 'Aw', 'Ah', 'Phew', 'Whoa', 'Huh', 'Yikes', 'Gosh', 'Nope', 'Yep', 'Sure', 'Thanks', 'Cheers',
             'Seriously', 'Weirdly', 'Strangely', 'Sadly', 'Happily', 'Tonight', 'Yesterday'}
NAME = r"[A-Z][a-z]+(?:-[A-Z][a-z]+)?"
TAIL = r"(?: (?:last|this|next) \w+| a while ago| \w+ \w+ ago| \w+ ago| recently| just now| now| these days| at the moment| currently|"        r" for (?:a|the|\d+|\w+) \w+| by the way| anymore| any more| as well| too)*"


# ---------------------------------------------------------------- lexicon helpers (WordNet, read-only)

@lru_cache(maxsize=1)
def _wordnet():
    if not WORDNET.exists():
        return None
    return sqlite3.connect(f'file:{WORDNET}?mode=ro', uri=True, check_same_thread=False)


@lru_cache(maxsize=4096)
def ancestors(word):
    """Hypernym words of a noun's two most common senses (WordNet 3.0)."""
    db = _wordnet()
    if db is None:
        return frozenset()
    seen, front = set(), [(word, 0)]
    for form in (word, word[:-1] if word.endswith('s') else None, word[:-2] if word.endswith('es') else None):
        if form and db.execute('SELECT 1 FROM lemma WHERE word=? AND pos="noun"', (form,)).fetchone():
            front = [(form, 0)]
            break
    while front:
        w, depth = front.pop()
        rows = db.execute('SELECT s.hypernyms FROM lemma l JOIN synset s ON s.id=l.synset WHERE l.word=? AND l.pos="noun" '
                          'ORDER BY l.rank LIMIT ?', (w, 2 if depth == 0 else 1)).fetchall()
        for (hypernyms,) in rows:
            for h in json.loads(hypernyms):
                if h not in seen and depth < 14:
                    seen.add(h)
                    front.append((h, depth + 1))
    return frozenset(seen)


@lru_cache(maxsize=8192)
def kinds(word, senses=6, depth=10):
    """Hypernym words over several senses of a noun (wider than ancestors(); used for places and food)."""
    db = _wordnet()
    if db is None or not word:
        return frozenset()
    start = word
    for form in (word, word[:-1] if word.endswith('s') else None, word[:-2] if word.endswith('es') else None,
                 word[:-3] + 'y' if word.endswith('ies') else None):
        if form and db.execute('SELECT 1 FROM lemma WHERE word=? AND pos="noun"', (form,)).fetchone():
            start = form
            break
    seen, front = set(), [(start, 0)]
    while front:
        w, d = front.pop()
        rows = db.execute('SELECT s.hypernyms FROM lemma l JOIN synset s ON s.id=l.synset WHERE l.word=? AND l.pos="noun" '
                          'ORDER BY l.rank LIMIT ?', (w, senses if d == 0 else 1)).fetchall()
        for (hypernyms,) in rows:
            for h in json.loads(hypernyms):
                if h not in seen and d < depth:
                    seen.add(h)
                    front.append((h, d + 1))
    return frozenset(seen)


PLACE_KINDS = {'city', 'town', 'national capital', 'state capital', 'provincial capital', 'capital', 'country', 'municipality', 'port',
               'urban center', 'village'}
FOOD_KINDS = {'food', 'dish', 'foodstuff', 'nutriment', 'edible fruit', 'vegetable', 'meal', 'produce', 'baked goods', 'dessert',
              'fish', 'meat', 'beverage', 'sweet', 'seafood', 'pasta', 'sandwich', 'soup', 'cheese', 'bread'}


def is_place(word):
    """A city, town or country name ('Paris', 'Nairobi') by WordNet."""
    return bool(kinds(word.lower()) & PLACE_KINDS)


def is_food(word):
    return word not in COLORS and bool(kinds(word.lower()) & FOOD_KINDS)       # 'chicken' and 'salmon' are both


@lru_cache(maxsize=1)
def _common():
    try:
        from .dictionary import frequent
        return frozenset(frequent()[:3000])
    except Exception:
        return frozenset()


def common_word(word):
    """'Nothing', 'Today', 'Someone': an everyday English word at the start of a sentence, not a name."""
    return word.lower() in _common()


def is_person_noun(word):
    return word not in NOT_JOBS and bool(ancestors(word) & {'person', 'worker', 'professional', 'skilled worker', 'creator', 'expert'})


def is_job(word):
    """An occupation noun ('nurse', 'software engineer'): a kind of person that is not a relation or social role."""
    head = word.split()[-1]
    return head not in NOT_JOBS and (is_person_noun(head) or head.endswith(('er', 'ist', 'or', 'ian', 'ant', 'ent')) and len(head) > 4)


def is_animal(word):
    return 'animal' in kinds(word, senses=1, depth=16) or word in ('dog', 'cat', 'puppy', 'kitten', 'hamster', 'parrot', 'rabbit', 'bunny', 'fish',
                                                   'turtle', 'horse', 'pony', 'snake', 'lizard', 'goldfish', 'budgie', 'guinea pig')


# ---------------------------------------------------------------- the store

class Store:
    """Interned strings and fixed-width integer records."""
    WIDTH = 6

    def __init__(self):
        self.ids, self.strings = {}, []
        self.data = array('i')
        self.groups = {}                     # entity id -> frozenset of member ids ("Ana and Ben")
        self.aliases = {}                    # "my sister" id -> person id, pet name id -> pet entity id
        self.gender = {}
        self.plan = None
        self.last_event = None
        self.proper = set()

    def show(self, text):
        i = self.ids.get(text)
        return ' '.join(w.capitalize() for w in text.split()) if i in self.proper or text in DAYS else text

    def id(self, text):
        text = norm(text)
        if text not in self.ids:
            self.ids[text] = len(self.strings)
            self.strings.append(text)
        return self.ids[text]

    def text(self, i):
        return self.strings[i]

    def add(self, msg, subject, attribute, value, kind=STATE, source=-1):
        s, a, v = self.id(subject), self.id(attribute), self.id(value)
        if value[:1].isupper():
            self.proper.add(v)                          # shown as written: 'Quito', not 'quito'
        record = (msg, s, a, v, kind, source if isinstance(source, int) else self.id(source))
        d, w = self.data, self.WIDTH
        for k in range(len(d) - w, -1, -w):             # the same fact read twice from one message is kept once
            if d[k] != msg:
                break
            if tuple(d[k:k + 4]) == record[:4]:
                return
        self.data.extend(record)

    def records(self):
        d, w = self.data, self.WIDTH
        for k in range(0, len(d), w):
            yield tuple(d[k:k + w])

    def nbytes(self):
        strings = sum(len(s.encode('utf-8')) + 1 for s in self.strings)
        plan = len(json.dumps(self.plan).encode('utf-8')) if self.plan else 0
        return self.data.itemsize * len(self.data) + strings + 8 * (len(self.aliases) + len(self.groups)) + plan


def norm(text):
    return ' '.join(text.lower().replace('’', "'").split()).strip(' .,;:!?"')


def expand(text):
    text = text.replace('’', "'")
    for short, full in (("n't", ' not'), ("'m", ' am'), ("'re", ' are'), ("'ve", ' have'), ("'ll", ' will'), ("'d", ' would'),
                        ("It's", 'It is'), ("it's", 'it is'), ("What's", 'What is'), ("what's", 'what is'), ("That's", 'That is'),
                        ("that's", 'that is'), ("Let's", 'Let us'), ("let's", 'let us'), ("Where's", 'Where is'), ("Who's", 'Who is'),
                        ("He's", 'He is'), ("he's", 'he is'), ("She's", 'She is'), ("she's", 'she is'), ("There's", 'There is'),
                        ("can not", 'cannot'), ("wo not", 'will not'), ("ca not", 'cannot')):
        text = text.replace(short, full)
    return text.replace('cannot', 'can not')


def sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+|\s*;\s*|\n+', text) if s.strip()]


def content(text):
    return {w for w in re.findall(r"[a-z]+", text.lower()) if w not in STOP and len(w) > 1}


# ---------------------------------------------------------------- reading the conversation

class Reader:
    def __init__(self):
        self.store = Store()
        self.recent = []                     # (entity key, kind 'm'/'f'/'u'/'p'/'n') most recent last

    # -- entities and pronouns
    def mention(self, key, kind):
        key = norm(key)
        self.recent = [r for r in self.recent if r[0] != key] + [(key, kind)]

    def person(self, name, rel=None):
        g = self.store.gender.get(norm(name), 'u')
        if rel in FEMALE:
            g = 'f'
        elif rel in MALE:
            g = 'm'
        self.store.gender[norm(name)] = g
        self.mention(name, g)

    def resolve(self, pronoun):
        want = PRONOUN[pronoun.lower()]
        for key, kind in reversed(self.recent):
            if want == 'n' and kind in 'na':
                return key
            if want == 'p' and kind == 'p':
                return key
            if want in 'mf' and kind in (want, 'u', 'a'):      # a pet can be "she" or "he"
                return key
        return None

    def substitute(self, sentence):
        """Replace pronouns with the entity they refer to ('She works as a nurse' -> 'Anna works as a nurse')."""
        if not on('references'):
            return sentence
        def name_of(key):
            return ' and '.join(p.title() for p in key.split(' and ')) if key and key[0].isalpha() and ' ' not in key.replace(' and ', '') \
                else key

        def swap(m):
            word = m.group(0)
            low = word.lower()
            if low == 'it' and re.match(r"(?:rain\w*|snow\w*|seem\w*|look\w*|feel\w*|took|has been|got (?:cold|dark|late|warm)|"
                                       r"(?:is|was) (?:fun|nice|great|good|bad|hard|easy|cold|hot|warm|sunny|cloudy|windy|late|early|"
                                       r"time|a (?:long|busy|good|bad|great|nice)))\b", sentence[m.end():].strip()):
                return word                     # weather / dummy "it", not a thing from earlier
            ref = self.resolve(low)
            if ref is None:
                return word
            shown = name_of(ref) if PRONOUN[low] != 'n' else ref
            after = sentence[m.end():m.end() + 12]
            if low in ('his', 'its', 'their') or low == 'her' and re.match(r"\s+(?!(?:to|in|on|at|for|and|is|was|a|an|the)\b)[a-z]", after):
                return shown + "'s"
            return shown
        return re.sub(r"\b(?:[Hh]e|[Ss]he|[Hh]im|[Hh]is|[Hh]er|[Tt]hey|[Tt]hem|[Tt]heir|[Ii]ts|[Ii]t)\b(?!')", swap, sentence)

    def subject_key(self, phrase):
        """'Anna' -> 'anna'; 'my sister' -> the sister's name when known; 'I' -> 'user'; 'our dog' -> 'my dog'."""
        p = norm(phrase)
        p = re.sub(r'^(?:the|our|my family\'s)\s+', 'my ', p) if re.match(r'(?:our|my family\'s)\s', p) else re.sub(r'^the\s+', '', p)
        if p in ('i', 'me', 'myself', 'we'):
            return 'user'
        alias = self.store.aliases.get(self.store.ids.get(p, -1)) if on('references') else None
        return self.store.text(alias) if alias is not None else p

    # -- statements
    def read(self, index, text):
        text = expand(text)
        if self.read_plan(index, text):
            return
        for raw in sentences(text):
            lowered = raw.lower()
            corrected = bool(re.search(CORRECTION_CUES, lowered))
            changed = bool(re.search(CHANGE_CUES, lowered))
            kind = CORRECTION if corrected else CHANGE if changed else STATE
            s = self.substitute(raw)
            s = re.sub(r'^(?:(?:But|And|Actually|Sorry|Oops|Correction|Wait|Update|Also|Well|So|Oh|Okay|Ok|By the way|Btw|FYI|Now|Changed my mind|'
                       r'Final change|Change of plans?|Let me correct that|Scratch that|My mistake|No wait|No|I was wrong|Hmm|Hmm no|My bad|'
                       r'I got that wrong|Big news|News|Guess what|Good news|Fun fact|Quick update|Heads up|Just so you know|Anyway|'
                       r'Turns out|It turns out|These days|Nowadays|Currently|At the moment|Lately|At present)[,:;!]?\s+)+', '', s,
                       flags=re.I).strip()
            s = s[:1].upper() + s[1:]
            s = re.sub(r'^(?:I should mention that|I want to tell you about|Let me tell you about|You should know|I think|I guess)\s+',
                       '', s)
            self.read_claim(index, s, kind) or self.read_correction(index, s) or self.read_sentence(index, s, kind)

    def read_correction(self, index, s):
        """'... Friday, not Tuesday' anywhere in a sentence, when 'Tuesday' is a value said before: Friday replaces it."""
        if not on('updates'):
            return False
        m = re.search(r"\b((?:[\w']+ ){0,2}[\w']+),?\s+(?:and )?not\s+(?:on\s+|at\s+|in\s+|the\s+)*((?:[\w']+ ){0,2}[\w']+)\s*[.!]?$", s)
        if not m:
            return False
        store = self.store
        before, after = m.group(1).split(), m.group(2).split()
        for n_old in range(len(after), 0, -1):
            old_id = store.ids.get(norm(' '.join(after[:n_old])))
            if old_id is None:
                continue
            for msg, subj, attr, val, kind, src in reversed(list(store.records())):
                if val != old_id:
                    continue
                width = len(store.text(val).split())
                new = norm(' '.join(before[-width:]))
                if new and new != store.text(val):
                    store.add(index, store.text(subj), store.text(attr), new, CORRECTION)
                    return True
        return False

    def read_claim(self, index, s, kind):
        m = re.match(r"^(?:According to\s+(" + NAME + r"),?\s+|(" + NAME + r")\s+(?:says|said|thinks|thought|told me|insists|claims|"
                     r"is sure|believes|swears|reckons|heard|has heard|is convinced|mentioned|wrote|texted|guesses|figures|"
                     r"feels|suspects|read|claimed|insisted|reckoned|believed|is certain)(?:\s+that)?\s+)(.+)$", s)
        if not m:
            return False
        source = norm(m.group(1) or m.group(2))
        self.person(source)
        before = len(self.store.data)
        self.read_sentence(index, m.group(3), CLAIM, source=source)
        return len(self.store.data) > before

    def event_key(self, phrase):
        words = [w for w in re.findall(r"[a-z]+", phrase.lower()) if w not in STOP and w not in DAYS]
        key = ' '.join(words)
        if not key:
            return self.store.last_event
        if self.store.last_event and self.store.last_event != key:
            have, new = set(self.store.last_event.split()), set(words)
            if new <= have:
                return self.store.last_event
        for existing in reversed(self.store.strings):
            if existing.startswith('event:'):
                have = set(existing[6:].split())
                if set(words) <= have or have <= set(words) and len(have) >= 2:
                    return existing[6:]
        return key

    def remember_event(self, index, phrase, attribute, value, kind, source=-1):
        key = self.event_key(phrase)
        if not key:
            return
        self.store.id('event:' + key)
        self.store.last_event = key
        self.mention(key, 'n')
        self.store.add(index, 'event:' + key, attribute, value, kind, source)

    def read_sentence(self, index, s, kind, source=-1):
        store, add = self.store, self.store.add
        s = s.strip().rstrip(' .!')
        low = s.lower()
        found = False

        def fact(subject, attribute, value, k=kind):
            nonlocal found
            add(index, self.subject_key(subject), attribute, value, k, source)
            found = True

        # names introduced with a relation: "my sister Anna", "Anna, my sister", "Anna is my sister", "my sister is called Anna"
        for rel, name in re.findall(r"\b[Mm]y ((?:best )?[a-z]+(?:-[a-z]+)?),? (" + NAME + r")\b", s):
            if rel in RELATIONS:
                self.link(index, rel, name)
                found = True
        for name, rel in re.findall(r"\b(" + NAME + r"),? (?:is )?my ((?:best )?[a-z]+(?:-[a-z]+)?)\b", s):
            if rel in RELATIONS and name not in NAME_STOP:
                self.link(index, rel, name)
                found = True
        m = re.search(r"\b[Mm]y ((?:best )?[a-z]+(?:-[a-z]+)?)(?:'s name is| is called| is named| name is) (" + NAME + r")\b", s)
        if m and m.group(1) in RELATIONS:
            self.link(index, m.group(1), m.group(2))
            found = True
        for name in re.findall(r"\b(" + NAME + r")\b", s):
            if name not in NAME_STOP and not re.search(r"\b(?:in|to|from|of|visit|visited|see|near)\s+" + name + r"\b", s) \
                    and (norm(name) in store.gender or not is_place(name)) and not self.pet_name(name) \
                    and not re.search(r"(?:\b(?:named|called|call|name|goes by|answers to|nicknamed)\s+|\b[a-z]+,\s+)" + name + r"\b", s):
                self.person(name)

        # "My sister Anna lives in Paris" / "Anna, my sister, lives in Paris" -> "Anna lives in Paris" once the link is kept
        s = re.sub(r"\b[Mm]y (?:best )?[a-z]+(?:-[a-z]+)?,? (" + NAME + r")\b,?", lambda m: m.group(1) if norm(m.group(0)[3:].replace(',', '').rsplit(' ', 1)[0]) in RELATIONS else m.group(0), s)
        s = re.sub(r"\b(" + NAME + r"), my (?:best )?[a-z]+,", r"\1", s)
        SUBJ = r"(?P<s>(?:" + NAME + r")(?: and " + NAME + r")?(?:'s [a-z]+)?|[Mm]y (?:best )?[a-z]+(?:-[a-z]+)?(?:'s [a-z]+)?|I|[Ww]e|[Oo]ur [a-z]+|[Tt]he [a-z]+)"
        group = re.match(r"^(?:My friends )?(" + NAME + r") (?:and|is traveling with|is travelling with|is going with) (" + NAME + r")\b", s)
        if group and group.group(1) not in NAME_STOP:
            key = ' and '.join(sorted((group.group(1).lower(), group.group(2).lower())))
            self.mention(key, 'p')
            store.id(key)
            found = True

        # where someone lives / is from / was born
        m = re.match(SUBJ + r" (?:just |recently |finally )?(?:moved|relocated|is moving|has moved|packed up and moved|moved back)(?: back)? to (?P<v>[A-Z][\w .'-]+?)" + TAIL + "$", s)
        if m:
            fact(m['s'], 'home', m['v'], CHANGE if kind != CORRECTION else kind)
        m = re.match(SUBJ + r" (?:does not|do not|no longer) (?:live|lives) in (?P<o>[A-Z][\w .'-]+?)(?: anymore| any more)?$", s)
        if m:
            fact(m['s'], 'home', m['o'], PAST)
        m = re.match(SUBJ + r"(?: still)? (?:lives?|is living|stays|resides|is based|lives over|has (?:a|an) (?:flat|apartment|house|home|place)) in (?:the city of )?(?P<v>[A-Z][\w .'-]+?)(?: now| these days| at the moment| currently| with \w+)?$", s) \
            or re.match(r"^(?:Home for (?P<s>\w+) is|(?P<s2>" + NAME + r")'s home is in) (?P<v>[A-Z][\w .'-]+?)$", s)
        if m:
            fact(m['s'] if 's' in m.groupdict() and m['s'] else m['s2'], 'home', m['v'])
        m = re.match(SUBJ + r" (?:was born in(?: the city of)?|comes from|is (?:originally )?from|is a native of)\s+(?P<v>[A-Z][\w.'-]*(?: [A-Z][\w.'-]*)*)", s) \
            or re.match(SUBJ + r"'s (?:birthplace|hometown|place of birth) is (?P<v>[A-Z][\w .'-]+?)$", s)
        if m:
            fact(m['s'], 'born', m['v'])

        # age
        m = re.match(SUBJ + r" (?:is|just turned|turned|will be|has turned) (?P<v>\d{1,3})(?: years old| years| yo)?(?: this year| last month| today)?$", s) \
            or re.match(SUBJ + r"'s age is (?P<v>\d{1,3})", s)
        if m and int(m['v']) < 130:
            fact(m['s'], 'age', m['v'])

        # jobs
        m = re.search(r"^" + SUBJ + r" is no longer an? (?P<o>[a-z ]+?)(?:,|$)", s)
        if m:
            fact(m['s'], 'job', m['o'], PAST)
        m = re.match(SUBJ + r"(?: quit and)?(?: now| still)? (?:works as|is working as|has a job as|earns a living as|became|has become|"
                     r"changed careers and is|switched jobs and became|switched careers and became|trained as|is employed as|"
                     r"got a job as|now works as|has been) (?:an? )?(?P<v>[a-z][a-z -]*?)(?: now| these days| for years| for \w+ years| at [\w ]+)?$", s) \
            or re.match(SUBJ + r"'s (?:job|profession|occupation|career) is (?:an? )?(?P<v>[a-z][a-z -]*?)$", s) \
            or re.match(r"^(?:These days|Now|Nowadays) " + SUBJ + r" works as (?:an? )?(?P<v>[a-z][a-z -]*?)$", s)
        if m and m['v'] not in NOT_JOBS:
            became = re.search(r'became|become|changed|switched|quit|now|these days', low)
            fact(m['s'], 'job', m['v'], CHANGE if became and kind == STATE else kind)
        else:
            m = re.match(SUBJ + r" is (?:an? )(?P<v>[a-z][a-z-]*(?: [a-z]+)?)(?: now)?$", s)
            if m and is_job(m['v']):
                fact(m['s'], 'job', m['v'])

        # relations described without a name ("my sister really likes sushi") fall through to the frames below

        # favourite food and likes
        m = re.match(SUBJ + r"'s (?:favou?rite|favorite) (?:food|dish|meal|snack|treat) is (?P<v>[\w ]+?)$", s) \
            or re.match(r"^The (?:food|dish|meal) (?P<s>[\w ]+?) (?:likes|loves|enjoys) (?:most|best) is (?P<v>[\w ]+?)$", s) \
            or re.match(SUBJ + r" (?:really |always |also |just )?(?:can not stop eating|eats a lot of|eats lots of|only wants|only eats|loves|"
                        r"likes|adores|enjoys|orders|eats|wants|craves) (?P<v>[\w ]+?)(?: more than anything| the most| best| most| every \w+| a lot| so much)?$", s)
        if m and m['v'].split()[0] not in ('to', 'it', 'that', 'this', 'you', 'me', 'going', 'a', 'the', 'my', 'her', 'his'):
            fact(m['s'], 'food', m['v'])

        # pets and names of things: "Lena has a cat named Luna", "Lena's cat is called Luna", "We named it Coco"
        m = re.match(SUBJ + r" (?:has|got|adopted|owns|bought) (?:a|an|one) (?P<a>[a-z]+)(?:;|,)? (?:named|called|whose name is|its name is) (?P<v>" + NAME + r")", s)
        if m:
            self.pet(index, m['s'], m['a'], m['v'], kind)
            found = True
        m = re.match(SUBJ + r"'s (?P<a>[a-z]+) is (?:called|named) (?P<v>" + NAME + r")$", s) \
            or re.match(r"^(?P<v>" + NAME + r") is the name of " + SUBJ + r"'s (?P<a>[a-z]+)$", s) \
            or re.match(r"^(?P<s>[\w ]+?)'s name is (?P<v>" + NAME + r")$", s)
        if m:
            owner_thing = m['s'] + ("'s " + m['a'] if 'a' in m.groupdict() and m['a'] else '')
            self.pet(index, *self.split_owner(owner_thing), m['v'], kind)
            found = True
        m = re.match(r"^(?:[Ww]e|I|[Tt]he kids|[Mm]y \w+|[Tt]hey) (?:named|called|call|name) (?P<s>[\w' ]+?) (?P<v>" + NAME + r")$", s)
        if m:
            self.pet(index, *self.split_owner(m['s']), m['v'], kind)
            found = True
        m = re.match(r"^(?:[Ww]e|I|[Mm]y family|[Oo]ur family) (?:got|adopted|brought home|bought|have) (?:a|an) (?:new )?(?P<a>[a-z]+)", s) \
            or re.match(r"^There is a new (?P<a>[a-z]+) in (?:our|my) (?:house|home|flat|family)", s)
        if m and is_animal(m['a']):
            self.mention('my ' + m['a'], 'n')
            store.id('my ' + m['a'])
            found = True
        m = re.match(SUBJ + r" (?:has|adopted|owns|got) (?:a|an) (?P<a>[a-z]+)$", s)
        if m and is_animal(m['a']):
            self.mention(self.subject_key(m['s']) + "'s " + m['a'], 'n')

        # colours: "Mila's car is red", "Mila has a red car", "I painted my car blue", "The car that Mila owns is red"
        colour = next((c for c in sorted(COLORS, key=len, reverse=True) if re.search(r'\b' + c + r'\b', low)), None)
        if colour and re.search(r"\b(?:wants?|would like|hopes?|dreams?|wish(?:es)?|might|maybe|if)\b", low):
            colour = None
        if colour:
            owner, thing = self.colour_owner(s, low, colour)
            if thing:
                painted = re.search(r'\b(?:painted|repainted|changed|now|again|dyed|is \w+ now)\b', low)
                k = kind if kind in (CORRECTION, CLAIM) else CHANGE if painted else STATE
                add(index, owner + "'s " + thing, 'color', colour, k, source)
                self.mention(owner + "'s " + thing, 'n')
                found = True

        # where objects are: "I left my keys in the drawer", "I moved my keys to the kitchen counter"
        m = re.search(r"\b(?:my|the|our) (?P<o>[a-z]+(?: [a-z]+)?) (?:is|are)(?: now| still)? (?:in|on|under|inside|at) (?:the|my) (?P<v>[a-z][a-z ]+?)(?: now)?$", low) \
            or re.search(r"\b(?:left|put|keep|kept|moved|placed|stored|relocated|dropped|hid|stashed|set) (?:my|the|our) (?P<o>[a-z]+(?: [a-z]+)?)(?: back)? (?:in|on|into|to|under|inside|at) (?:the|my) (?P<v>[a-z][a-z ]+?)(?: now)?$", low) \
            or re.search(r"\btook (?:my|the) (?P<o>[a-z]+)(?: [a-z]+)? out and put (?:it|them|\w+) (?:in|on|into|under) (?:the|my) (?P<v>[a-z][a-z ]+?)$", low)
        if m and not re.match(r"(?:meeting|appointment|party|concert|exam|match|trip)\b", m['o']):
            moved = re.search(r'\b(?:moved|relocated|took|now|put .* back)\b', low)
            add(index, 'my ' + m['o'], 'location', m['v'], CHANGE if moved and kind == STATE else kind, source)
            self.mention('my ' + m['o'], 'n')
            found = True

        # trips: places visited and wanted
        m = re.search(r"\b(?:I )?(?:visited|went to|spent (?:a|two|three|\w+) (?:week|weeks|days|months?) in|was in|travell?ed to)\s+(?P<v>[A-Z][\w-]+)", s) \
            or re.search(r"\b[Mm]y (?:last|previous) (?:trip|holiday|vacation) was (?:to|in) (?P<v>[A-Z][\w-]+)", s)
        if m and re.match(r"^(?:I|Last|My|In|Two|A)\b", s):
            add(index, 'user', 'visited', m['v'], kind, source)
            found = True
        m = re.search(r"\b(?:want to|would like to|hope to|plan to|planning to|dreaming of a trip to|dream of visiting|going to visit|will visit)\s+(?:visit |see |go to )?(?P<v>[A-Z][\w-]+)", s) \
            or re.search(r"\b[Mm]y next (?:trip|holiday|vacation) (?:will be|is) (?:to|in) (?P<v>[A-Z][\w-]+)", s)
        if m and re.match(r"^(?:I|Next|My|This)\b", s):
            add(index, 'user', 'wants to visit', m['v'], kind, source)
            found = True
        # group trips: "They are going to Rome", "Their destination is Rome", "They leave on Friday"
        m = re.match(SUBJ + r" (?:are|is) (?:going|heading|flying|travell?ing|off) to (?P<v>[A-Z][\w-]+)", s) \
            or re.match(SUBJ + r"'s destination is (?P<v>[A-Z][\w-]+)", s) \
            or re.match(SUBJ + r" (?:chose|picked|selected|decided on) (?P<v>[A-Z][\w-]+)", s)
        if m:
            fact(m['s'], 'destination', m['v'])
        m = re.match(SUBJ + r"(?: will)? (?:leave|leaves|depart|departs|fly out|flies out|set off|sets off) on (?P<v>" + DAY + r")", low, re.I) \
            or re.match(SUBJ + r"'s flight is on (?P<v>" + DAY + r")", low, re.I)
        if m:
            fact(m['s'], 'departure', m['v'])

        # numbers with a unit of money: budgets, limits, goals
        money = re.search(r'(?:\$\s?(' + NUMBER + r')|(' + NUMBER + r')\s?(?:dollars|usd|euros?|pounds|bucks))', low)
        if money:
            value = (money.group(1) or money.group(2)).replace(',', '')
            label = self.money_label(low)
            if label:
                k = kind if kind in (CORRECTION, CLAIM) else CHANGE if re.search(CHANGE_CUES + r'|\bonly\b|\bcan spend\b.*\bnow\b', low) and \
                    any(store.text(r[2]) == label for r in store.records()) else STATE
                add(index, 'user', label, value, k, source)
                found = True

        # events with a day, time or place ("My meeting with Nora is on Friday at 3 pm", "The party is on Saturday")
        day = re.search(r'\b(?:on|for|until|by)\s+(' + DAY + r')\b|\b(' + DAY + r')\b', low)
        time = re.search(r'\bat\s+(' + TIME + r')', low)
        place = re.search(r"\b(?:at|in)\s+((?:the|a)\s+[a-z][a-z' ]+?)(?:\s+on\b|\s+at\b|$)", low) if re.search(
            r'\bmeet|\bmeeting|\bwill be at\b|\bplace\b|\bvenue\b|\blocation\b', low) else None
        if (day or time or place) and not found and not money:
            phrase = self.event_phrase(s, low)
            if phrase is not None:
                if day:
                    self.remember_event(index, phrase, 'day', day.group(1) or day.group(2), kind, source)
                if time:
                    self.remember_event(index, phrase, 'time', time.group(1), kind, source)
                if place:
                    self.remember_event(index, phrase, 'place', re.sub(r'^(?:the|a)\s+', '', place.group(1)), kind, source)
                found = True
        found = self.read_generic(index, s, low, kind, source) or found
        return found

    def event_phrase(self, s, low):
        """The thing that happens: 'my meeting with Nora', 'the party', 'the dentist'; '' -> the last event mentioned."""
        m = re.search(r"\b(?:meeting|meet|meets|seeing|see)\s+(?:with\s+)?(" + NAME + r")\b", s) or re.search(r"\b(" + NAME + r") and I (?:will )?meet\b", s) \
            or re.search(r"\b(" + NAME + r") wants to meet\b", s)
        if m and m.group(1) not in NAME_STOP:
            return 'meeting ' + m.group(1).lower()
        if re.search(r"^(?:we|the meeting|it|our meeting)\b.*\b(?:meet|meeting|place|be at)\b|^the meeting place\b", low) and self.store.last_event:
            return self.store.last_event
        m = re.search(r"\b(?:my|the|our|a|an)\s+((?:[a-z]+\s+)?(?:appointment|meeting|party|concert|exam|test|match|game|interview|"
                      r"flight|class|lesson|wedding|dinner|lunch|show|trip|call|deadline|surgery|checkup|check-up|game|festival|"
                      r"ceremony|reunion|presentation|recital|tournament|race|session|event|date|visit|booking|reservation))\b", low) \
            or re.search(r"\b(?:see|visit|booked me for|go to)\s+the\s+([a-z]+)", low) or re.search(r"^the\s+([a-z]+)\s+(?:booked|is|will)", low)
        if m:
            with_name = re.search(r"\bwith (" + NAME + r")\b", s)
            return m.group(1) + (' ' + with_name.group(1).lower() if with_name and with_name.group(1) not in NAME_STOP else '')
        if re.match(r"^(?:it|that|this)\b", low) and self.store.last_event:
            return self.store.last_event
        m = re.search(r"\b(?:the|my|our|a|an) ([a-z]+) (?:is|opens|starts|begins|closes|ends|happens|takes place|will be|was|runs|kicks off)"
                      r"(?: (?:again|now|still))? (?:on|at|from|until|this|next)\b", low)
        if m and m.group(1) not in STOP:
            return m.group(1)
        words = content(low) - set(DAYS)
        known = [e[6:] for e in self.store.strings if e.startswith('event:') and set(e[6:].split()) & words]
        return known[-1] if known else None

    def money_label(self, low):
        """What an amount of money is for: 'budget trip' ('budget for the trip', 'trip budget'), 'savings goal', 'rent'."""
        money_word = re.search(r'\b(?:budget|limit|spend|spending|cost|price|savings|rent|salary|allowance|fund)\b', low)
        if not money_word:
            return None
        if 'savings' in low:
            return 'savings goal'
        base = 'budget' if re.search(r'\b(?:budget|limit|spend|spending)\b', low) else money_word.group(0)
        q = re.search(r'\b(?:budget|limit|spend\w*|cost|price)\s+(?:for|on|of)\s+(?:the |my |our |a |this )?([a-z]+)', low) \
            or re.search(r'\b([a-z]+)\s+(?:budget|limit)\b', low)
        extra = q.group(1) if q else None
        if extra in STOP or extra in ('new', 'his', 'her', 'their', 'whole', 'total', 'overall', 'spending', 'dollars'):
            extra = None
        if extra is None and re.search(r'\b(?:this|it)\b', low) and self.store.plan:
            extra = self.store.plan['goal'].split()[0]
        return base + (' ' + extra if extra else '')

    def subject_of(self, s):
        """The clause's subject as a store key: a person/group named first, 'my X', the user, or the one person named in it."""
        m = re.match(r"^(" + NAME + r")(?: and (" + NAME + r"))?(?:'s)?\b", s)
        if m and m.group(1) not in NAME_STOP:
            if m.group(2):
                return ' and '.join(sorted((m.group(1).lower(), m.group(2).lower())))
            if norm(m.group(1)) in self.store.gender or self.pet_name(m.group(1)):
                return self.subject_key(m.group(1))
        m = re.match(r"^(?:[Mm]y|[Oo]ur) ((?:best )?[a-z]+)\b", s)
        if m:
            return self.subject_key('my ' + m.group(1))
        if re.match(r"^(?:I|We)\b", s):
            return 'user'
        names = [n for n in re.findall(r"\b(" + NAME + r")\b", s) if norm(n) in self.store.gender]
        if len(set(names)) == 1:
            return norm(names[0])
        return None

    def pet_name(self, name):
        i = self.store.ids.get(norm(name))
        return i is not None and i in self.store.aliases and norm(name) not in self.store.gender

    def read_generic(self, index, s, low, kind, source):
        """Wording-independent pass: typed values in the clause (place, job, food, colour+thing, animal+name, age, day,
        'in the X') attached to the clause subject, with change / ended / unreal cues. Frames above handle the rest."""
        store = self.store
        subject = self.subject_of(s)
        unreal = re.search(r"\b(?:wants? to|would like to|hopes? to|dreams? (?:of|about)|stud(?:y|ies|ying) to be|plans? to|"
                           r"one day|someday|wish(?:es)?|might|maybe|could|should|if)\b", low)
        negative = re.search(r"\b(?:can not stand|hates?|dislikes?|never|not|no longer|nothing but|allergic)\b", low) and \
            not re.search(r'\bnothing makes\b|\bnothing beats\b|\bnot \w+,\s|\bnot only\b', low)
        ended = r"(?:from|left|leaving|goodbye to|out of|gave up(?: being)?|quit|no longer|instead of|not)"
        k_change = CHANGE if kind == STATE and re.search(CHANGE_CUES, low) else kind
        found = False
        people = {k for k, g in self.recent if g in 'mfup'}

        def add(subj, attribute, value, k):
            nonlocal found
            store.add(index, subj, attribute, value, k, source)
            found = True

        # places: 'calls Sydney home', 'has a new address in Cairo', 'said goodbye to Paris and settled in Berlin'
        places = [w for w in re.findall(r"\b([A-Z][a-z]+(?:-[A-Z][a-z]+)?)\b", s[1:]) if w not in NAME_STOP and norm(w) not in store.gender
                  and not self.pet_name(w) and is_place(w)]
        if places and subject and not unreal:
            if re.search(r'\b(?:born|birthplace|native|grew up|comes? from|is from|originally)\b', low):
                attribute = 'born'
            elif ' and ' in subject or re.search(r'\b(?:fly|flying|flies|heading|travel\w*|trip|tickets|destination|holiday|vacation|off to)\b', low):
                attribute = 'destination'
            elif subject == 'user' and re.search(r'\b(?:visited|went to|spent|was in|been to)\b', low):
                attribute = 'visited'
            else:
                attribute = 'home'
            for p in places:
                old = re.search(ended + r"\s+(?:the city of\s+)?" + p + r"\b", s)
                add(subject, attribute, p, PAST if old and len(places) > 1 else k_change if len(places) > 1 else kind if kind != STATE else k_change)
        # jobs: 'makes a living as a chef', 'trained to be a dentist', 'left the journalist job and is now a plumber'
        if subject and subject in people:
            for m in re.finditer(r"\b(?:an?|the)\s+((?:[a-z]+ )?[a-z]+)\b(?:\s+job\b)?", low):
                noun = next((w for w in m.group(1).split() if is_job(w) and w not in COLORS and not is_food(w) and not is_animal(w)), None)
                if noun is None:
                    continue
                before = low[max(0, m.start() - 40):m.start()]
                if re.search(r'\b(?:wants? to (?:be|become)|stud(?:y|ies|ying) to be|hopes? to (?:be|become)|dreams? of becoming|one day)\s*$', before) or \
                        re.search(r'one day|someday', low[m.end():]):
                    continue
                if re.search(r"\b(?:visit\w*|see\w*|met|meet\w*|call\w*|with|for|to|from)\s*$", before) and not re.search(r'\b(?:be|as|became|become)\s*$', before):
                    continue
                past = re.search(r'\b(?:gave up being|quit being|no longer|stopped being|used to be|was once|left)\s*$', before) or low[m.end():].startswith(' job')
                add(subject, 'job', noun, PAST if past else k_change)
        # food: 'is crazy about paella', 'nothing makes Ivy happier than pasta', 'goes wild for tuna'
        if subject and not negative and re.search(r'\b(?:lov|lik|ador|enjoy|eat|order|crav|favou?rite|crazy|wild|happ|pick|cook|snack|treat|'
                                                    r'fan|obsess|addict|want|prefer|devour)\w*', low):
            for word in re.findall(r'\b([a-z]+)\b', low):
                if word not in STOP and is_food(word) and not re.search(r'\b(?:had|ate|drank|bought|made)\s+(?:\w+ )?' + word, low):
                    add(subject, 'food', word, kind)
                    break
        # pets and their names: "Maya's pet dog goes by Rex", "Omar owns a dog, Biscuit", "We gave my kitten the name Olive"
        animal = next((w for w in re.findall(r'\b([a-z]+)\b', low) if w not in STOP and is_animal(w) and w not in ('pet', 'fish') or w == 'fish' and 'pet' in low), None)
        if animal:
            poss = re.search(r"\b(" + NAME + r")'s (?:pet |little |new |old )?" + animal, s)
            owner = self.subject_key(poss.group(1)) if poss else subject if subject and subject in people else 'user'
            key = (owner + "'s " if owner not in ('user',) else 'my ') + animal
            if re.search(r'\b(?:we|us|our|my|i)\b', low) or poss or subject in people:
                self.mention(key, 'a')
            pet = [n for n in re.findall(r"\b(" + NAME + r")\b", s[1:]) if n not in NAME_STOP and norm(n) not in store.gender and not is_place(n)
                   and norm(n) != owner]
            if pet and re.search(r'\b(?:named|called|call|name|goes by|answers to|nicknamed)\b|,\s*' + pet[0] + r'\b', s):
                self.pet(index, owner, animal, pet[0], kind)
                found = True
        elif subject and "'s " not in subject and subject.startswith('my ') and is_animal(subject.split()[-1]):
            pet = [n for n in re.findall(r"\b(" + NAME + r")\b", s) if n not in NAME_STOP and norm(n) not in store.gender]
            if pet and re.search(r'\b(?:named|called|call|name|goes by)\b', low):
                self.pet(index, 'user', subject.split()[-1], pet[0], kind)
                found = True
        # age: 'celebrated turning 50', 'is 36'
        m = re.search(r'\b(?:turn(?:ed|ing|s)?|is|was|aged?|celebrated)\s+(\d{1,3})(?:\s+years?(?: old)?|\s+today|\s+this year)?\b', low)
        if m and subject in people and int(m.group(1)) < 130 and not re.search(r'dollars|\$|%|\bminutes|\bhours|\bkm\b|\bkg\b|\d\s?am\b|\d\s?pm\b|o\'clock', low):
            add(subject, 'age', m.group(1), kind)
        # where things are: 'I stuck my keys in the blue bag', 'The keys went from the coat pocket to the drawer'
        m = re.search(r"\b(?:my|the|our) ([a-z]+)\b((?: [a-z]+){0,6}?) (?:in|on|into|onto|under|inside|to|at) (?:the|my) ([a-z][a-z ]*?)$", low)
        if m and not is_animal(m.group(1)) and not re.search(r'meeting|appointment|party|exam|match|concert|trip|call|dentist|gig', m.group(1)) \
                and (subject in ('user', None) or subject.startswith('my ')) and m.group(1) not in RELATIONS:
            obj = m.group(1)
            frm = re.search(r'\bfrom (?:the|my) ([a-z][a-z ]*?) to (?:the|my) ', low)
            if frm:
                add('my ' + obj, 'location', frm.group(1), PAST)
            moved = frm or re.search(r'\b(?:moved|shifted|took|relocated|transferred|since|later|now)\b', low)
            add('my ' + obj, 'location', m.group(3), CHANGE if moved and kind == STATE else kind)
            self.mention('my ' + obj, 'n')
        # trips of a group: 'They go on Tuesday', 'Their plane takes off on Sunday'
        day = re.search(r'\b(' + DAY + r')\b', low)
        if day and subject and ' and ' in subject:
            add(subject, 'departure', day.group(1), kind)
        return found

    def colour_owner(self, s, low, colour):
        m = re.search(r"\b(" + NAME + r")'s (?P<t>[a-z]+)", s) or re.search(r"\bthe (?P<t>[a-z]+) that (" + NAME + r") (?:owns|has|drives|rides|bought)", s)
        if m:
            return self.subject_key(m.group(1) if m.lastindex and m.group(1) and m.group(1)[0].isupper() else m.group(2)), m['t']
        m = re.match(r"^(" + NAME + r") (?:just |recently |finally )?[a-z]+ (?:a|an|the|her|his)? ?(?:" + colour +
                     r" )?(?P<t>[a-z]+)", s)
        if m and m.group(1) not in NAME_STOP:
            thing = m['t'] if m['t'] != colour else None
            if thing is None:
                after = re.search(r'\b' + colour + r'\s+([a-z]+)', low)
                thing = after.group(1) if after else None
            return self.subject_key(m.group(1)), thing
        m = re.search(r"\b(?:my|the|our)\s+(?:" + colour + r"\s+)?(?P<t>(?:front |back )?[a-z]+)", low) or re.search(r"\b(?:a|an)\s+" + colour + r"\s+(?P<t>[a-z]+)", low)
        if m and m['t'] not in COLORS and m['t'] not in ('mind', 'change', 'way', 'time', 'first', 'last', 'one'):
            if re.search(r'\b' + colour + r'\s+' + m['t'] + r'\b|\b' + m['t'] + r'\b.*\b' + colour + r'\b|\b' + colour + r'\b.*\b' + m['t'] + r'\b', low):
                return 'user', m['t']
        if self.recent and self.recent[-1][1] == 'n' and "'s " in self.recent[-1][0] and re.search(r'\bit\b|\bnow\b', low):
            owner, thing = self.recent[-1][0].split("'s ", 1)
            return owner, thing
        return None, None

    def split_owner(self, phrase):
        p = self.subject_key(phrase)
        if "'s " in p:
            owner, thing = p.split("'s ", 1)
            return owner, thing
        if p.startswith('my '):
            return 'user', p[3:]
        return 'user', p

    def pet(self, index, owner, animal, name, kind):
        owner = self.subject_key(owner) if owner not in ('user',) else owner
        key = (owner + "'s " if owner != 'user' else 'my ') + animal
        self.store.add(index, key, 'name', name, kind)
        self.store.aliases[self.store.id(name)] = self.store.id(key)
        self.mention(key, 'a')

    def link(self, index, rel, name):
        store = self.store
        store.add(index, 'user', rel, name, STATE)
        store.aliases[store.id('my ' + rel)] = store.id(name)
        self.person(name, rel)

    # -- plans
    def read_plan(self, index, text):
        if not on('planning'):
            return False
        low = text.lower()
        store = self.store
        m = re.search(r"\b(?:i want to|i am going to|my goal is to|i plan to|i need to|i am trying to|i would like to|plan to|help me)\s+"
                      r"([a-z][a-z ,'-]+?)(?:[.:]|\s*$|\. )", low)
        steps_m = re.search(r"(?:steps?(?: are)?|plan(?: is)?|to-?do(?: list)?|tasks?|checklist)\s*:\s*(.+)$", low) \
            or re.search(r"\bfirst,?\s+(.+)$", low) or re.search(r'\b1[.)]\s*(.+)$', low)
        listed = re.search(r"\b(?:list|checklist|plan|steps|to-?do list|tasks)\s+(?:to|for)\s+([a-z][a-z ']+?)\s*:\s*(.+)$", low) \
            or re.search(r"^(?:in order )?to ([a-z][a-z ']+?),? (?:i|we) (?:need|have|want|must|should|will need|am going|are going) to (.+)$", low)
        if listed and not (m and steps_m):
            m, steps_m = listed, re.match(r'(?:.*?)(.+)$', listed.group(2))
        if m and steps_m:
            goal = re.sub(r'^(?:keep track:\s*i am going to\s+)', '', m.group(1)).strip()
            if 'keep track' in goal:
                g2 = re.search(r'i am going to ([a-z][a-z ,\'-]+?)[.:]', low)
                goal = g2.group(1) if g2 else goal
            raw = steps_m.group(1)
            parts = re.split(r'\s*(?:\d+[.)]|;|,\s*(?:and\s+)?(?:then\s+|finally\s+)?|\s+then\s+|\s+and finally\s+|\s+and then\s+|,?\s+and\s+(?=[a-z]+ (?:the|a|my|it)\b))\s*', raw)
            steps = [re.sub(r'^(?:first|then|finally|and)\s+', '', p).strip(' .') for p in parts]
            steps = [p for p in steps if p and len(p.split()) <= 8]
            if len(steps) >= 2:
                store.plan = dict(goal=goal, steps=steps, done=[], skipped=[], added=[], said=index)
                store.id('plan:' + goal)
                return True
        plan = store.plan
        if not plan:
            return False
        handled = False
        for sentence in sentences(low):
            sentence = re.sub(r'^(?:also|update|okay|ok|so|change of plans|actually)[,:]?\s+', '', sentence)
            # Preconditions are explicit facts about tasks, not merely their display order.
            # Match complete task labels; a shared noun alone must not bind the wrong step.
            dependency = re.fullmatch(r"(.+?) (?:requires|depends on|can only happen after|can only start after) (.+?)\.?", sentence)
            if dependency:
                def exact_step(value):
                    value = re.sub(r'^(?:the )?(?:step|task)(?: to)?\s+', '', value.strip(' .\"\''))
                    matches = [s for s in plan['steps'] + plan['added'] if s == value]
                    return matches[0] if len(matches) == 1 else None
                step, prerequisite = map(exact_step, dependency.groups())
                if step and prerequisite:
                    requirements = plan.setdefault('dependencies', {}).setdefault(step, [])
                    if prerequisite not in requirements:
                        requirements.append(prerequisite)
                    handled = True
                    continue
            reopened = re.fullmatch(r"(?:reopen|mark as (?:unfinished|not done)|undo completion of)\s*:?\s*(.+?)\.?", sentence)
            if reopened:
                label = reopened[1].strip(' .\"\'')
                if label in plan['steps'] + plan['added']:
                    plan['done'] = [s for s in plan['done'] if s != label]
                    handled = True
                    continue
            m = re.search(r"\b(?:skip|skipping|drop|dropping|remove|removing|cancel|forget about|forget|no need to|decided not to|will not|do not need to|not going to|"
                          r"cross out|scrap|strike|delete|leave out|leaving out|never mind|take out)\s+(?:the step\s+(?:where (?:i|we) |of )?)?(?:\"([^\"]+)\"|'([^']+)'|([a-z][a-z ']+?)(?:,|\.?$))", sentence)
            if m:
                step = self.match_step(m.group(1) or m.group(2) or m.group(3))
                if step and step not in plan['skipped']:
                    plan['skipped'].append(step)
                    handled = True
                    continue
            m = re.search(r"\b(?:add(?: a step)?|one more step|another step|also need to|include)\b[^:]*:\s*[\"']?([a-z][a-z ']+?)[\"']?\.?$", sentence) \
                or re.search(r"\b(?:add(?: a step)?|one more step|another step|also need to|include)[:\s]+[\"']?([a-z][a-z ']+?)[\"']?"
                             r"(?:\s+(?:at the end|to the list|to the plan|as well|too))?\.?$", sentence)
            if m and not self.match_step(m.group(1)):
                plan['added'].append(m.group(1).strip())
                handled = True
                continue
            m = re.search(r"\b(?:do|move|put|swap)\b.*?(?:the step where (?:i|we) |the step to |step )?([a-z][a-z ']+?) (before|after|ahead of) "
                          r"(?:the (?:one|step) where (?:i|we) |the step to |step )?([a-z][a-z ']+?)\.?$", sentence)
            if m:
                first, second = self.match_step(m.group(1)), self.match_step(m.group(3))
                if first and second and first != second:
                    order = plan.setdefault('order', plan['steps'] + plan['added'])
                    order.remove(first)
                    at = order.index(second) + (0 if m.group(2) in ('before', 'ahead of') else 1)
                    order.insert(at, first)
                    handled = True
                    continue
            m = re.search(r"\b(?:finished|completed|done with|did|done:|have done)\s+the first (\w+) steps?", sentence) \
                or re.search(r"\bthe first (\w+) steps? (?:are|is) (?:done|finished|complete)", sentence)
            if m:
                count = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'step': 1}.get(m.group(1), int(m.group(1)) if m.group(1).isdigit() else 1)
                for step in plan['steps'][:count]:
                    if step not in plan['done']:
                        plan['done'].append(step)
                handled = True
                continue
            if re.search(r"\b(?:finished|completed|done with|did|done)\s+(?:with\s+)?the first step\b|\bfirst step is (?:done|finished|complete)\b", sentence):
                plan['done'].append(plan['steps'][0]) if plan['steps'][0] not in plan['done'] else None
                handled = True
                continue
            m = re.search(r"(?:^done:|\b(?:i have |i )?(?:just )?(?:finished|completed|did|done with|ticked off|checked off|crossed off|"
                          r"knocked out|wrapped up|got through)\b|^update:)\s*:?\s*(.+?)(?:\s+(?:are|is) done)?\.?$", sentence) \
                or re.search(r"^(.+?)\s*(?:(?:are|is) )?(?:-|:|,)?\s*(?:done|finished|complete|completed|ticked off|sorted)\.?$", sentence)
            if m:
                any_step = False
                for piece in re.split(r',\s*|\s+and\s+', m.group(1)):
                    step = self.match_step(piece)
                    if step and step not in plan['done']:
                        plan['done'].append(step)
                        any_step = True
                handled = handled or any_step
        return handled

    def match_step(self, text):
        plan = self.store.plan
        words = content(text)
        best, score = None, 0
        for step in plan['steps'] + plan['added']:
            have = content(step)
            overlap = len(words & have)
            if overlap > score and overlap >= max(1, min(len(have), len(words)) - 1):
                best, score = step, overlap
        return best


def read_history(messages):
    reader = Reader()
    for index, message in enumerate(messages):
        if message.get('role') == 'user':
            reader.read(index, message.get('content', ''))
    return reader


def compression_stats(messages):
    """(raw history bytes, structured store bytes) for one conversation."""
    raw = sum(len(m.get('content', '').encode('utf-8')) for m in messages)
    return raw, read_history(messages).store.nbytes()


# ---------------------------------------------------------------- answering

ATTRIBUTE_CUES = [
    ('born', r'\b(?:born|birthplace|hometown|originally from|native|come from|comes from)\b'),
    ('age', r'\bhow old\b|\bage\b'),
    ('departure', r'\b(?:leave|leaving|depart|departing|departure|fly out|flight|set off)\b'),
    ('destination', r'\b(?:going|traveling|travelling|destination|heading|trip|pick|picked|chose|choose)\b'),
    ('home', r'\bwhere\b.*\bliving\b|\bliving in\b|\b(?:live|lives|lived|based|reside|resides|residing|city is|city does|which city|what city|old city|in now|'
             r'home|address|at present|stay|stays|staying)\b|^where (?:is|was) [a-z]+(?: now| these days| at the moment| currently| at present)?\??$'),
    ('job', r'\b(?:job|jobs|work|works|working|do for a living|profession|occupation|career|do now|earn|earns|money|line of work|'
            r'living|employed|trade)\b|\bdo(?:es)? (?:\w+ ){1,3}do\b'),
    ('food', r'\b(?:food|eat\w*|snack\w*|dish\w*|meal|favou?rite|love to|like to|cook\w*|ador\w*|crav\w*|treat)\b'),
]
PAST_Q = r'\b(?:before|previously|used to|use to|old|originally|original|first|at the start|initially|at first|formerly)\b'


def facts_about(store, keys, attribute):
    ids = {store.ids.get(k) for k in keys} - {None}
    a = store.ids.get(attribute)
    return [r for r in store.records() if r[1] in ids and r[2] == a]


def keys_for(reader, phrase):
    """All store keys that may name this subject: the name, 'my sister' <-> 'anna', pet names <-> 'my dog'."""
    store = reader.store
    p = reader.subject_key(phrase)
    keys = {p, norm(phrase)}
    if not on('references'):
        return keys
    pid = store.ids.get(p)
    for alias, target in store.aliases.items():
        if target == pid:
            keys.add(store.text(alias))
        if alias == pid:
            keys.add(store.text(target))
    return keys


def verdict(store, rows, ask_past=False):
    """_verdict with values shown as the user wrote them (capitalised names stay capitalised)."""
    v = _verdict(store, rows, ask_past)
    if not v:
        return v
    show = store.show
    v['value'] = show(v['value']) if v.get('value') else v.get('value')
    v['history'] = [show(h) for h in v.get('history') or []]
    if v.get('conflict'):
        v['conflict'] = [show(c) for c in v['conflict']]
    if v.get('sources'):
        v['sources'] = {k: show(x) for k, x in v['sources'].items()}
    return v


def _verdict(store, rows, ask_past=False):
    """(current value, history, conflict) from records about one subject/attribute."""
    if not rows:
        return None
    text = store.text
    if not on('updates'):          # ablation: one slot per fact, no change tracking or history
        rows = [r for r in rows if r[4] != PAST]
        if not rows:
            return None
        values = list(dict.fromkeys(text(r[3]) for r in rows))
        if on('conflicts') and len(values) > 1:
            sources = {text(r[5]): text(r[3]) for r in rows if r[4] == CLAIM} or None
            return dict(value=None, history=[], conflict=values, sources=sources)
        return dict(value=text(rows[-1][3]), history=[], conflict=None)
    if not on('conflicts'):        # ablation: no contradiction check, claims count as plain statements, latest wins
        rows = [(m, s, a, v, CHANGE if k in (CLAIM, STATE) else k, src) for m, s, a, v, k, src in rows]
    claims = [r for r in rows if r[4] == CLAIM]
    own = [r for r in rows if r[4] != CLAIM]
    if ask_past:
        first = [r for r in own if r[4] in (STATE, PAST)] or own or claims
        values = []
        for r in own:
            if text(r[3]) not in values:
                values.append(text(r[3]))
        return dict(value=text(first[0][3]), history=values, conflict=None, past=True)
    if own:
        current, history, conflict = None, [], None
        for r in own:
            value = text(r[3])
            if r[4] == PAST:
                if value not in history:
                    history.append(value)
                if current == value:
                    current = None
                continue
            if current is not None and value != current:
                if r[4] == STATE:
                    conflict = conflict or [current]
                    conflict.append(value)
                else:
                    conflict = None
                if current not in history:
                    history.append(current)
            current = value
        if conflict:
            return dict(value=None, history=history, conflict=list(dict.fromkeys(conflict)), sources=None)
        corrected = any(r[4] == CORRECTION for r in own)
        return dict(value=current, history=[h for h in history if h != current], conflict=None, corrected=corrected)
    by_source = {}
    for r in claims:
        by_source[text(r[5])] = text(r[3])
    values = list(dict.fromkeys(by_source.values()))
    if len(values) > 1:
        return dict(value=None, history=[], conflict=values, sources=by_source)
    return dict(value=values[0], history=[], conflict=None, sources=by_source)


def say_conflict(subject_text, v, attribute_phrase):
    if v.get('sources'):
        parts = [f'{name.title()} says {value}' for name, value in v['sources'].items()]
        return (f"I have conflicting information about {attribute_phrase}: " + ', but '.join(parts) +
                '. They disagree, so I can not tell which is right. Can you check which one is correct?')
    options = ' or '.join(v['conflict'])
    return (f"You told me two different things about {attribute_phrase}: {options}. These contradict each other, "
            f"and neither was marked as a correction. Which one is right?")


def history_note(v):
    if v.get('history'):
        before = ', then '.join(v['history'])
        return f' Before that: {before}.' if not v.get('corrected') else f' (Corrected; earlier you said {before}.)'
    return ''


def answer(response):
    return dict(response=response, route='chat/context-memory', sources=[], details=DETAILS)


def title(key):
    if key == 'user':
        return 'You'
    if key.startswith('my '):
        return 'Your ' + key[3:]
    if "'s " in key:
        owner, thing = key.split("'s ", 1)
        return ('Your' if owner == 'user' else owner.title() + "'s") + ' ' + thing
    return ' and '.join(part.title() for part in key.split(' and '))


QUESTION = re.compile(r"^(?:what|where|when|who|which|how|do|does|did|is|are|can|could|remind|tell)\b|\?\s*$", re.I)


def reply(messages):
    """Answer a question about earlier messages from the structured record store, or None."""
    if not messages or messages[-1].get('role') != 'user':
        return None
    history = messages[:-1]
    if sum(1 for m in history if m.get('role') == 'user') < 1:
        return None
    question = expand(messages[-1]['content']).strip()
    if not QUESTION.search(question):
        return None
    if any(m.get('role') == 'user' and re.match(r'(?i)^\s*(?:facts|premises|given|suppose|scenario)\s*:',
                                                 m.get('content', '')) for m in history):
        return None                                    # an explicit "Facts:" scenario belongs to reasoning_chat
    if on('graph'):
        from . import conversation_graph
        joined = conversation_graph.reply(messages)
        if joined is not None:
            return joined
    general = None
    if on('planning'):
        planned = read_history(history)
        result = plan_answer(planned, question) if planned.store.plan else None
        if result:
            return answer(result)
    if on('reasoner'):
        from . import context_reasoner                 # 0.3.6: general clause records, reasoning and abstention
        general = context_reasoner.answer(messages)
        if general and (general.get('operation') or general.get('conflict')):
            return general                             # an answer combined from several statements beats a single-fact match
    reader = read_history(history)
    if reader.store.data or reader.store.plan:
        for handler in (plan_answer, money_answer, relation_answer, name_answer, colour_answer, trip_answer, visit_answer,
                        location_answer, person_answer, event_answer):
            result = handler(reader, question)
            if result:
                if general and (general.get('abstain') or general.get('update')):
                    return general                     # never-answered topic, or a change the older handlers do not track
                return answer(result)
    return general


def plan_answer(reader, q):
    plan = reader.store.plan
    low = q.lower()
    if not plan or not on('planning'):
        return None
    order = [s for s in plan.get('order', plan['steps'] + plan['added']) if s not in plan['skipped']]
    for s in plan['added']:
        if s not in order:
            order.append(s)
    remaining = [s for s in order if s not in plan['done']]
    dependencies = plan.get('dependencies', {})
    blocked = {s: [p for p in dependencies.get(s, []) if p not in plan['done']] for s in remaining}
    blocked = {s: prerequisites for s, prerequisites in blocked.items() if prerequisites}
    ready = [s for s in remaining if s not in blocked]
    notes = []
    if plan['done']:
        notes.append('Done: ' + ', '.join(plan['done']) + '.')
    if plan['skipped']:
        notes.append('Skipped: ' + ', '.join(plan['skipped']) + '.')
    if blocked:
        notes.append('Blocked: ' + '; '.join(s + ' needs ' + ', '.join(p) for s, p in blocked.items()) + '.')
    if dependencies and re.search(r'\b(?:which|what) (?:steps|tasks) (?:are|can i) (?:ready|start)|\bwhat can (?:i|we) start\b', low):
        return ('Ready tasks: ' + '; '.join(ready) + '. ' if ready else 'No task is ready. ') + ' '.join(notes)
    nth = re.search(r'\b(first|second|third|fourth|fifth|sixth|last|final) (?:step|task|thing)\b', low)
    if nth and re.search(r'\bwhat|\bwhich', low):
        k = {'first': 0, 'second': 1, 'third': 2, 'fourth': 3, 'fifth': 4, 'sixth': 5, 'last': -1, 'final': -1}[nth.group(1)]
        if -len(order) <= k < len(order):
            return f"The {nth.group(1)} step is: {order[k]}."
    if re.search(r'\bhow many (?:steps|tasks|things)\b', low):
        n = len(remaining)
        return f"{n} step{'s' if n != 1 else ''} left" + (': ' + '; '.join(remaining) if remaining else '') + '. ' + ' '.join(notes)
    if re.search(r'\b(?:project|plan|list)\b[^?]*\bfor\??$|\bwhat (?:is|was) (?:the|this|my) (?:whole )?(?:project|plan|goal|list)(?: again)?\??$', low):
        return f"Your goal is to {plan['goal']}."
    if re.search(r'\b(?:my|our) (?:goal|aim|objective)\b|\b(?:am i|are we|was i|were we) trying to (?:do|get done|achieve|finish)\b|\bthe (?:plan|list) (?:is )?(?:for|about)\??$|\bwhat (?:is|was) the plan\??$', low):
        return f"Your goal is to {plan['goal']}."
    if re.search(r'\bnext (?:step|task|thing to do|thing)\b|\b(?:should|do|must|can) (?:i|we) do (?:next|now)\b|\bcomes? (?:next|after)\b|^what now\b|\bmy next\b|\bwhat(?: is|\'s) next\b|\bnext on\b|\bafter that\b', low):
        if not remaining:
            return 'Every step is done. ' + ' '.join(notes)
        if not ready:
            return 'No task is ready: the remaining steps have unmet prerequisites. Please clarify the dependencies. ' + ' '.join(notes)
        return f'Next step: {ready[0]}. ' + ' '.join(notes)
    if re.search(r'\b(?:left|remain\w*|still need|still have|to do|outstanding|pending|still open|open on|unfinished|not done|undone)\b', low):
        if not remaining:
            return 'Nothing is left: every step is done. ' + ' '.join(notes)
        return 'Still to do: ' + '; '.join(remaining) + '. ' + ' '.join(notes)
    if re.search(r'\b(?:my|our) (?:steps|plan)\b|\bthe (?:steps|plan)\??$', low) and not re.search(r'\bto (?!do\b)[a-z]+', low):
        return 'Your plan: ' + '; '.join(plan['steps'] + plan['added']) + '. ' + ' '.join(notes)
    return None


def money_answer(reader, q):
    low = q.lower()
    if not re.search(r'\b(?:budget|limit|spend|spending|how much|savings|cost|price|rent|salary|allowance)\b', low) or \
            not re.search(r'\b(?:my|our|i|we|this|it|me|us)\b', low):
        return None
    store = reader.store
    labels = [s for s in store.strings if s.startswith(('budget', 'savings', 'cost', 'price', 'rent', 'salary', 'allowance'))]
    if not labels:
        return None
    words = content(low) - {'much', 'spend', 'spending', 'limit', 'budget', 'settle', 'settled'}
    want = 'savings goal' if 'savings' in low else None

    def score(label):
        have = set(label.split())
        return (label == want, len(words & have), -len(have - words))
    label = max(labels, key=score)
    rows = facts_about(store, {'user'}, label)
    v = verdict(store, rows)
    if not v:
        return None
    what = 'your ' + label.replace('budget ', 'budget for the ').replace('budget for the monthly', 'monthly budget')
    if v['conflict']:
        return say_conflict('user', v, what)
    return f"{what[0].upper() + what[1:]} is {v['value']} dollars." + history_note(v)


def relation_answer(reader, q):
    m = re.search(r"\b(?:who is|who's|name of|what is the name of|what is) my ((?:best )?[a-z]+(?:-[a-z]+)?)(?:'s name| is)?\b", q.lower()) \
        or re.search(r"\bwho my ((?:best )?[a-z]+) is\b", q.lower())
    if not m or m.group(1) not in RELATIONS:
        return None
    rest = q.lower().split(m.group(1), 1)[-1].strip(" ?.!")
    if rest and not re.fullmatch(r"(?:'s )?(?:name|called|named)?\s*(?:again)?", rest):
        return None
    rows = facts_about(reader.store, {'user'}, m.group(1))
    v = verdict(reader.store, rows)
    if not v:
        return None
    if v['conflict']:
        return say_conflict('user', v, f'your {m.group(1)}')
    return f"Your {m.group(1)} is {v['value'].title()}."


def name_answer(reader, q):
    low = q.lower()
    if not re.search(r"\b(?:name|named|called|call)\b", low):
        return None
    store = reader.store
    m = re.search(r"\b(" + NAME + r")'s ([a-z]+)\b", q) or re.search(r"\bdid (" + NAME + r") (?:name|call) (?:the|her|his|their) ([a-z]+)", q)
    if m:
        keys = {reader.subject_key(m.group(1)) + "'s " + m.group(2)}
    else:
        m = re.search(r"\b(?:our|my|the) ([a-z]+)(?:'s)?\b", low)
        if not m or m.group(1) in ('name', 'names'):
            return None
        keys = {'my ' + m.group(1)}
        if not re.search(r'\b(?:my|our|i|we)\b', low):     # "the dog" may be anyone's; "my dog" is only the user's
            keys |= {k for k in store.strings if k.endswith("'s " + m.group(1))}
    rows = [r for r in store.records() if store.text(r[1]) in keys and store.text(r[2]) == 'name']
    v = verdict(store, rows)
    if not v:
        return None
    subject = title(store.text(rows[-1][1]))
    if v['conflict']:
        return say_conflict(subject, v, f'the name of {subject.lower()}')
    return f"{subject} is called {v['value'].title()}."


def colour_answer(reader, q):
    low = q.lower()
    if not re.search(r'\bcolou?r\b', low):
        return None
    store = reader.store
    m = re.search(r"\b(" + NAME + r")'s ((?:front )?[a-z]+)\b", q) or re.search(r"\bthe ([a-z]+) (?:that )?(" + NAME + r")\b", q)
    if m and m.group(1)[0].isupper():
        key = reader.subject_key(m.group(1)) + "'s " + m.group(2)
    elif m:
        key = reader.subject_key(m.group(2)) + "'s " + m.group(1)
    else:
        m = re.search(r"\b(?:my|the|our) ((?:front |back )?[a-z]+)\b", low)
        if not m:
            return None
        key = "user's " + m.group(1)
    rows = [r for r in store.records() if store.text(r[1]) == key and store.text(r[2]) == 'color']
    if not rows:
        thing = key.split("'s ", 1)[1]
        rows = [r for r in store.records() if store.text(r[1]).endswith("'s " + thing) and store.text(r[2]) == 'color'
                and store.text(r[1]).split("'s ")[0] == key.split("'s ")[0]]
    past = bool(re.search(PAST_Q, low))
    v = verdict(store, rows, ask_past=past)
    if not v:
        return None
    subject = title(key)
    if v.get('conflict'):
        return say_conflict(subject, v, f'the colour of {subject.lower()}')
    if past:
        later = [h for h in v['history'] if h != v['value']]
        return f"{subject} was originally {v['value']}." + (f" It was later changed to {', then '.join(later)}." if later else '')
    return f"{subject} is {v['value']}." + history_note(v)


def trip_answer(reader, q):
    names = [n for n in re.findall(r"\b(" + NAME + r")\b", q) if n not in NAME_STOP]
    if len(names) < 2:
        return None
    key = ' and '.join(sorted(n.lower() for n in names[:2]))
    low = q.lower()
    attribute = 'departure' if re.search(r'\b(?:leave|leaving|depart|flight|fly out|when|what day|which day)\b', low) else 'destination'
    rows = facts_about(reader.store, {key}, attribute)
    if not rows and attribute == 'destination':
        return None
    v = verdict(reader.store, rows)
    if not v:
        return None
    who = ' and '.join(n.title() for n in key.split(' and '))
    if v['conflict']:
        return say_conflict(who, v, f"{who}'s trip")
    if attribute == 'destination':
        return f"{who} are going to {v['value'].title()}." + history_note(v)
    return f"{who} leave on {v['value'].title()}." + history_note(v)


def visit_answer(reader, q):
    low = q.lower()
    store = reader.store
    if not re.search(r'\b(?:visit|visited|trip|holiday|vacation|go next|want to go|went|been to)\b', low) or re.search(r"\b" + NAME + r"\b", q[1:]):
        return None
    wanted = bool(re.search(r'\b(?:next|want|hoping|hope|plan|planning|dream|will|would like)\b', low))
    rows = facts_about(store, {'user'}, 'wants to visit' if wanted else 'visited')
    v = verdict(store, rows)
    if not v or v['conflict']:
        return None
    other = verdict(store, facts_about(store, {'user'}, 'visited' if wanted else 'wants to visit'))
    note = (f" (You already visited {other['value'].title()} before.)" if wanted else f" (Next you want to visit {other['value'].title()}, not yet visited.)") if other and other['value'] else ''
    return (f"You want to visit {v['value'].title()} next." if wanted else f"You visited {v['value'].title()}.") + note


def location_answer(reader, q):
    low = q.lower()
    m = re.search(r"\bwhere (?:is|are|did i (?:leave|put|keep|last put)|can i find|could i find|have i put|do i keep) (?:my|the|our) ([a-z]+(?: [a-z]+)?)\b", low) \
        or re.search(r"\bwhere my ([a-z]+) (?:is|are)\b", low) \
        or re.search(r"\b(?:where|look for|find|locate|search for)\b.*?\b(?:my|the|our) ([a-z]+(?: [a-z]+)?)\b", low)
    if not m:
        return None
    store = reader.store
    words = set(m.group(1).split())
    keys = [k for k in store.strings if k.startswith('my ') and set(k[3:].split()) & words]
    rows = [r for r in store.records() if store.text(r[1]) in keys and store.text(r[2]) == 'location']
    v = verdict(store, rows)
    if not v:
        return None
    thing = store.text(rows[-1][1])[3:]
    verb = 'are' if thing.endswith('s') and not thing.endswith('ss') else 'is'
    if v['conflict']:
        return say_conflict('user', v, f'where your {thing} {verb}')
    return f"Your {thing} {verb} in the {v['value']}." + (f" (You moved {'them' if verb == 'are' else 'it'} from the {', then the '.join(v['history'])}.)" if v['history'] else '')


def person_answer(reader, q):
    low = q.lower()
    store = reader.store
    m = re.search(r"\b(" + NAME + r")(?:'s)?\b", q[1:])
    subject = None
    if m and m.group(1) not in NAME_STOP:
        # only someone named earlier in this chat, and not another person who shares the first name ("Ben Franklin")
        if norm(m.group(1)) not in store.gender and norm(m.group(1)) not in store.ids or re.match(r"\s+[A-Z][a-z]+", q[1 + m.end():]):
            return None
        subject = m.group(1)
    else:
        rel = re.search(r"\bmy ((?:best )?[a-z]+)\b", low)
        if rel and rel.group(1) in RELATIONS:
            subject = 'my ' + rel.group(1)
        elif re.search(r'\b(?:do i|am i|did i|was i|were i|have i|my)\b', low):
            subject = 'I'
    if subject is None:
        return None
    keys = keys_for(reader, subject)
    if subject.startswith('my '):
        alias = store.aliases.get(store.ids.get(subject, -1))
        if alias is not None:
            keys |= keys_for(reader, store.text(alias))
    past = bool(re.search(PAST_Q, low)) and not re.search(r'\bnow\b', low)
    for attribute, cue in ATTRIBUTE_CUES:
        if not re.search(cue, low):
            continue
        rows = facts_about(store, keys, attribute)
        if not rows:
            # Knowing a named person's residence/job does not establish a
            # different personal attribute. Keep the answer tied to this chat.
            if attribute in ('home', 'born', 'age', 'job', 'food') and any(
                    facts_about(store, keys, known) for known in ('home', 'born', 'age', 'job', 'food')):
                who = title(reader.subject_key(subject)) if subject != 'I' else 'you'
                attribute_name = dict(home='current home', born='birthplace', age='age', job='job', food='food preference')[attribute]
                if who.startswith(('Your ', 'My ')):
                    who = 'your ' + who.split(' ', 1)[1]
                owner = 'your' if subject == 'I' else who+"'s"
                about = 'you' if subject == 'I' else 'them'
                return 'You have not told me '+owner+' '+attribute_name+' in this chat. I cannot infer it from a different fact about '+about+'.'
            continue
        v = verdict(store, rows, ask_past=past and attribute in ('home', 'job', 'food'))
        who = title(reader.subject_key(subject)) if subject != 'I' else 'You'
        if who.startswith('My '):
            who = 'Your ' + who[3:]
        phrase = dict(home='where ' + who + ' lives', born='where ' + who + ' was born', age=who + "'s age", job=who + "'s job",
                      food='what ' + who + ' likes to eat', destination=who + "'s trip", departure=who + "'s trip")[attribute]
        if v.get('conflict'):
            return say_conflict(who, v, phrase)
        value = v['value']
        if v.get('past'):
            verb = dict(home='lived in', job='worked as', food='liked')[attribute]
            return f"{who} {verb} {value.title() if attribute == 'home' else value} before." + \
                (f" Now: {v['history'][-1].title() if attribute == 'home' else v['history'][-1]}." if len(v['history']) > 1 else '')
        note = history_note(v)
        if attribute == 'home':
            return f"{who} {'live' if who == 'You' else 'lives'} in {value.title()}" + (' now.' if v['history'] else '.') + note
        if attribute == 'born':
            return f"{who} {'were' if who == 'You' else 'was'} born in {value.title()}."
        if attribute == 'age':
            return f"{who} {'are' if who == 'You' else 'is'} {value} years old."
        if attribute == 'job':
            art = 'an' if value[0] in 'aeiou' else 'a'
            return f"{who} {'work' if who == 'You' else 'works'} as {art} {value}" + (' now.' if v['history'] else '.') + note
        if attribute == 'food':
            return f"{who} {'love' if who == 'You' else 'loves'} {value}." + note
        if attribute == 'destination':
            return f"{who} {'are' if ' and ' in who else 'is'} going to {value.title()}."
        if attribute == 'departure':
            return f"{who} {'leave' if ' and ' in who else 'leaves'} on {value.title()}."
    return None


def event_answer(reader, q):
    low = q.lower()
    store = reader.store
    events = [s[6:] for s in store.strings if s.startswith('event:')]
    if not events:
        return None
    asks = 'place' if re.search(r'\bwhere\b|\bplace\b|\bvenue\b|\blocation\b', low) else 'day' if re.search(
        r'\bwhen\b|\bday\b|\bdate\b|\bwhat time\b', low) else None
    if asks is None:
        return None
    qwords = content(low) | {n.lower() for n in re.findall(r"\b(" + NAME + r")\b", q) if n not in NAME_STOP}
    qwords |= {'meeting'} if re.search(r'\bmeet(?:ing)?\b', low) else set()
    best = max(events, key=lambda e: (len(set(e.split()) & qwords), -len(set(e.split()) - qwords)))
    if not set(best.split()) & qwords:
        return None
    attrs = ['place'] if asks == 'place' else ['day', 'time']
    parts, conflict = [], None
    for attribute in attrs:
        rows = facts_about(store, {'event:' + best}, attribute)
        v = verdict(store, rows)
        if not v:
            continue
        if v['conflict']:
            conflict = v
            break
        parts.append((attribute, v))
    what = 'your ' + best if best.startswith('meeting') else 'the ' + best
    if conflict:
        return say_conflict(what, conflict, 'when ' + what + ' is' if asks == 'day' else 'where ' + what + ' is')
    if not parts:
        return None
    v = parts[0][1]
    if asks == 'place':
        return f"{what[0].upper() + what[1:]} is at the {v['value']}." + history_note(v)
    when = v['value'].title() if parts[0][0] == 'day' else v['value']
    time = next((p[1]['value'] for p in parts if p[0] == 'time'), None)
    return f"{what[0].upper() + what[1:]} is on {when}" + (f' at {time}' if time and parts[0][0] == 'day' else '') + '.' + history_note(v)
