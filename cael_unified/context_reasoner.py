"""General context reasoning over a conversation (CAEL 0.3.6): a semantic layer under conversation_memory.py.

Non-neural. Every user clause is normalised into a compact record:

    subject (entity id), negated, cue flags (change / correction / past / unreal / reported source),
    content lemmas (WordNet base forms, as interned ints), typed values (number, money, time, day, date, colour,
    place, person, duration) and noun chunks, plus the message position.

A question is normalised the same way (wh-type -> expected answer type, subject, focus lemmas). Answers come from
  1. compositional operations over the records (comparisons and superlatives, "same X as", counting, sums and
     time arithmetic, before/after order, threshold rules such as "admits people aged 18 or over");
  2. retrieval: the clauses that best match the question's subject and focus (lemmas, WordNet synonyms and a small
     table of general semantic fields), then the value of the expected type from the best clause, with changes,
     corrections and conflicts decided across matching clauses;
  3. abstention: a question about the conversation that nothing in it supports gets "you didn't mention it".
Every answer carries a confidence; below the threshold the reasoner says it does not know instead of guessing.
"""
from array import array
from functools import lru_cache
import re

from . import conversation_memory as cm

DETAILS = ('Answered from your earlier messages in this chat: each statement is normalised into a small integer record '
           '(who, what, values, when said, negation, corrections), and the answer is the best-supported value or a '
           'combination of stated facts. If nothing you said supports an answer, CAEL says so instead of guessing.')

STOP = {'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'am', 'i', 'me', 'my', 'mine', 'we', 'us', 'our',
        'you', 'your', 'he', 'him', 'his', 'she', 'her', 'it', 'its', 'they', 'them', 'their', 'this', 'that', 'these', 'those',
        'to', 'of', 'in', 'on', 'at', 'for', 'with', 'by', 'from', 'about', 'as', 'into', 'onto', 'over', 'under', 'up', 'down',
        'out', 'off', 'and', 'or', 'but', 'so', 'if', 'then', 'than', 'too', 'very', 'really', 'just', 'also', 'still', 'even',
        'do', 'does', 'did', 'done', 'have', 'has', 'had', 'having', 'will', 'would', 'shall', 'should', 'can', 'could', 'may',
        'might', 'must', 'what', 'which', 'who', 'whom', 'whose', 'where', 'when', 'why', 'how', 'there', 'here', 'not', 'no',
        'yes', 'all', 'any', 'some', 'each', 'every', 'one', 'ones', 'own', 'go', 'going', 'went', 'gone',
        'oh', 'ok', 'okay', 'well', 'yeah', 'lol', 'btw', 'anyway', 'random', 'honestly', 'hm', 'hmm', 'like', 'thing', 'things',
        'again', 'now', 'currently', 'actually', 'right', 'remind', 'know', 'think', 'guess', 'said', 'say', 'says', 'let',
        'make', 'made', 'something', 'anything', 'please', 'mention', 'mentioned', 'remember', 'ever', 'yet', 'already', 'ago',
        'that', 'these', 'other', 'another', 'same', 'such', 'only', 'much', 'many', 'more', 'most', 'less', 'least', 'good', 'best',
        'better', 'great', 'nice', 'lovely', 'bit', 'lot', 'way', 'kind', 'sort'}
NUMBER_WORDS = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
                'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16,
                'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50,
                'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90, 'hundred': 100, 'dozen': 12, 'a dozen': 12, 'half': 0.5}
WORD_FOR = {v: k for k, v in NUMBER_WORDS.items() if isinstance(v, int) and k != 'a dozen'}
MONTHS = ('january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november',
          'december')
DAY_NAMES = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')
CURRENCY = r'(?:euros?|eur|dollars?|usd|bucks|pounds?|gbp|quid|francs?|yen|kronor|krona|crowns?|zloty|pesos?|rupees?)'
UNIT = r'(?:years?(?: old)?|months?|weeks?|days?|hours?|hrs?|minutes?|mins?|seconds?|km|kilomet(?:er|re)s?|miles?|metres?|meters?|' \
       r'm|cm|centimet(?:er|re)s?|mm|millimet(?:er|re)s?|kg|kilos?|grams?|g|litres?|liters?|percent|%|people|guests|chairs|' \
       r'times|pages|steps|floors?|stops|items|pieces)'
TIME_RE = re.compile(r'\b(\d{1,2})(?::(\d\d))?\s*(am|pm|a\.m\.|p\.m\.)|\b(\d{1,2}):(\d\d)\b|\b(noon|midday|midnight)\b', re.I)
DATE_RE = re.compile(r'\b(\d{1,2})(?:st|nd|rd|th)?(?: of)? (' + '|'.join(MONTHS) + r')\b|\b(' + '|'.join(MONTHS) +
                     r') (\d{1,2})(?:st|nd|rd|th)?\b', re.I)
CHANGE = re.compile(cm.CHANGE_CUES + r'|\bchanged our minds?\b|\bchanged my mind\b|\binstead\b|\bfrom now on\b|\bhas been moved\b|'
                    r'\bwas moved\b|\bswitched\b|\bupgraded\b|\breplaced\b|\bturned out\b|\bended up\b|\bin the end\b|\bfinally\b|'
                    r'\bdropped\b|\bslashed\b|\bwent (?:up|down)\b|\brose\b|\bfell\b|\brenamed\b|\bextended\b|\bpostponed\b|'
                    r'\bbrought forward\b|\brelocated\b|\bmoved\b|\bno more\b|\bnot anymore\b|\bnowadays\b|\bthese days\b|\bnew\b', re.I)
CORRECT = re.compile(cm.CORRECTION_CUES + r'|\bmisspoke\b|\bmixed up\b|\bactually\b|\bi meant\b|\bnot \w+,? but\b|\bto be clear\b|'
                     r'\bthat was wrong\b|\bcorrect(?:ion|ing)?\b', re.I)
PAST = re.compile(r'\bused to\b|\bformerly\b|\bpreviously\b|\bonce\b|\bno longer\b|\banymore\b|\bany more\b|\bbefore that\b|'
                  r'\bback then\b|\bwhen i was\b', re.I)
UNREAL = re.compile(r'\b(?:want(?:s|ed)? to|would like|wish(?:es)?|hope(?:s|d)? to|dream(?:s|ed)? (?:of|about)|might|maybe|perhaps|'
                    r'if|unless|thinking (?:of|about)|considering|plan(?:s|ning)? to|going to try|someday|one day)\b', re.I)
REPORT = re.compile(r"^(?P<src>(?:my |the |our |a )?[A-Za-z][\w' ]{0,30}?) (?:says?|said|thinks?|thought|told me|tells me|insists?(?: on)?|"
                    r"claims?|claimed|reckons?|believes?|believed|heard|mentioned|swears?|wrote|texted|reported|states?|stated|"
                    r"is sure|was sure|is convinced|recommends?|suggests?)(?: that)?\b", re.I)
SEMANTIC_FIELDS = [
    {'live', 'home', 'reside', 'base', 'stay', 'flat', 'apartment', 'house', 'address', 'move', 'settle', 'dwell', 'based'},
    {'work', 'job', 'profession', 'career', 'employ', 'occupation', 'trade', 'living', 'employer', 'hire', 'hired'},
    {'study', 'degree', 'major', 'university', 'uni', 'college', 'course', 'graduate', 'school', 'subject'},
    {'cost', 'price', 'pay', 'paid', 'spend', 'spent', 'charge', 'buy', 'bought', 'expensive', 'cheap', 'euro', 'dollar', 'fee'},
    {'arrive', 'come', 'show', 'turn', 'reach', 'join', 'attend', 'guest', 'people', 'invite', 'coming'},
    {'start', 'begin', 'open', 'kick'}, {'end', 'finish', 'close', 'over', 'stop'},
    {'like', 'love', 'enjoy', 'favourite', 'favorite', 'prefer', 'adore', 'fan', 'go-to'},
    {'eat', 'food', 'dish', 'meal', 'cook', 'snack', 'dinner', 'lunch', 'breakfast'},
    {'drink', 'beverage', 'coffee', 'tea'}, {'allergic', 'allergy'}, {'name', 'call', 'named', 'called', 'nickname'},
    {'born', 'birthplace', 'hometown', 'grow', 'raise', 'childhood', 'native', 'origin'},
    {'meet', 'meeting', 'appointment', 'see', 'visit', 'session', 'catch'},
    {'dentist', 'dental', 'tooth', 'teeth', 'orthodontist', 'checkup', 'check', 'doctor', 'gp', 'clinic', 'physio', 'appointment'},
    {'restaurant', 'cafe', 'bistro', 'diner', 'eatery', 'pub', 'bar', 'place', 'spot', 'pizzeria', 'canteen'},
    {'give', 'get', 'receive', 'gift', 'present', 'buy'},
    {'old', 'age', 'turn', 'birthday', 'aged'}, {'tall', 'height', 'short', 'cm'},
    {'pet', 'dog', 'cat', 'animal', 'puppy', 'kitten'}, {'car', 'drive', 'vehicle', 'lift', 'ride'},
    {'leave', 'depart', 'departure', 'flight', 'fly', 'set'},
    {'train', 'rail', 'railway', 'bus', 'coach', 'drive', 'car', 'fly', 'flight', 'plane', 'bike', 'cycle', 'walk', 'taxi', 'ferry',
     'tram', 'metro', 'transport', 'travel', 'commute', 'get'}, {'colour', 'color', 'paint', 'shade'},
    {'code', 'number', 'pin', 'password', 'combination'}, {'speak', 'language', 'fluent'},
    {'play', 'instrument', 'sport', 'hobby'}, {'read', 'book', 'novel'}, {'watch', 'film', 'movie', 'show', 'series'},
    {'sibling', 'brother', 'sister'}, {'kid', 'child', 'son', 'daughter', 'children'},
    {'borrow', 'lend', 'lent', 'give', 'gave', 'owe'}, {'lose', 'lost', 'missing', 'find', 'found'},
    {'put', 'leave', 'left', 'keep', 'store', 'place', 'stash', 'tuck', 'hide'},
    {'size', 'wear', 'fit'}, {'recommend', 'suggest', 'tip', 'advise', 'tell', 'mention', 'point'}, {'fix', 'repair', 'mend'},
    {'plan', 'goal', 'project', 'aim', 'trying', 'objective'}, {'budget', 'afford', 'limit', 'spend'},
    {'deadline', 'due', 'submit', 'hand', 'finish', 'finished', 'complete'}, {'room', 'locker', 'seat', 'table', 'gate', 'platform', 'flat'},
]
FIELD_OF = {}
for _i, _field in enumerate(SEMANTIC_FIELDS):
    for _w in _field:
        FIELD_OF.setdefault(_w, set()).add(_i)
PERSON_REL = cm.RELATIONS | {'friend', 'friends', 'cousins', 'colleagues', 'neighbours', 'neighbors', 'flatmate', 'housemate',
                             'teammate', 'partner', 'wife', 'husband', 'kids', 'parents', 'mum', 'dad', 'grandma', 'grandpa',
                             'grandmother', 'grandfather', 'aunt', 'uncle', 'niece', 'nephew'}


@lru_cache(maxsize=65536)
def lemma(word):
    """Dictionary base form ('studied' -> 'study', 'went' -> 'go', 'cousins' -> 'cousin') by WordNet forms and suffix rules."""
    w = word.lower()
    if len(w) <= 2 or not w.isalpha():
        return w
    db = cm._wordnet()
    if db is not None:
        row = db.execute('SELECT base FROM form WHERE form=? LIMIT 1', (w,)).fetchone()
        if row:
            return row[0]
        if db.execute('SELECT 1 FROM lemma WHERE word=? LIMIT 1', (w,)).fetchone() and not w.endswith(('ed', 'ing', 's')):
            return w
        for suffix, repl in (('ies', 'y'), ('ves', 'f'), ('es', ''), ('s', ''), ('ied', 'y'), ('ed', ''), ('ed', 'e'), ('ing', ''),
                             ('ing', 'e')):
            if w.endswith(suffix) and len(w) - len(suffix) >= 3:
                base = w[:-len(suffix)] + repl
                if db.execute('SELECT 1 FROM lemma WHERE word=? LIMIT 1', (base,)).fetchone():
                    return base
                if re.search(r'(.)\1$', base) and db.execute('SELECT 1 FROM lemma WHERE word=? LIMIT 1', (base[:-1],)).fetchone():
                    return base[:-1]
    return w


@lru_cache(maxsize=65536)
def bases(word):
    """All dictionary base forms of a word ('lives' -> {'life', 'live'}, 'left' -> {'leave', 'left'})."""
    w = word.lower()
    out = {lemma(w)}
    db = cm._wordnet()
    if db is not None and w.isalpha() and len(w) > 2:
        out |= {row[0] for row in db.execute('SELECT base FROM form WHERE form=?', (w,))}
        for suffix, repl in (('ies', 'y'), ('es', ''), ('s', ''), ('ied', 'y'), ('ed', ''), ('ed', 'e'), ('ing', ''), ('ing', 'e')):
            if w.endswith(suffix) and len(w) - len(suffix) >= 3:
                base = w[:-len(suffix)] + repl
                if db.execute("SELECT 1 FROM lemma WHERE word=? AND pos='verb' LIMIT 1", (base,)).fetchone():
                    out.add(base)
    return frozenset(out)


@lru_cache(maxsize=16384)
def synonyms(word):
    """The word, its WordNet synonyms (two commonest senses of each part of speech) and semantic-field ids."""
    out = {word}
    db = cm._wordnet()
    if db is not None:
        for (words,) in db.execute('SELECT s.words FROM lemma l JOIN synset s ON s.id=l.synset WHERE l.word=? AND l.rank < 2', (word,)):
            for w in re.findall(r'"([^"]+)"', words):
                if ' ' not in w:
                    out.add(w.lower())
    return frozenset(out)


def number_value(text):
    text = text.lower().replace(',', '')
    if re.fullmatch(r'\d+(?:\.\d+)?', text):
        return float(text)
    return NUMBER_WORDS.get(text)


def fmt(n):
    return str(int(n)) if float(n).is_integer() else f'{n:g}'


class Clause:
    __slots__ = ('index', 'order', 'text', 'low', 'raw', 'subject', 'negated', 'flags', 'source', 'lemmas', 'values', 'chunks', 'mentions',
                 'parent')


LEADING = re.compile(r"^(?:(?i:back|last|next|this|for|on|in|at|after|before|during|since|yesterday|today|tomorrow|tonight|"
                     r"earlier|later|recently|lately|once|then|over|from|when|while|as|being|like)\b[^,]{0,40}?,?\s+)"
                     r"(?=(?:I|We|He|She|They|My|Our|we|he|she|they|my|our)\b|[A-Z][a-z]+ (?:is|was|has|had|did|went|lives|works|got|moved)\b)")


def normalise(text):
    """Surface variants -> plain order: clefts ('It was Zoe who told me' -> 'Zoe told me'), fronted phrases kept as is."""
    text = re.sub(r"^(?:It|it) (?:was|is|'s) ([A-Z][a-z]+|my \w+|the \w+) (?:who|that|which) ", r"\1 ", text)
    text = re.sub(r"^(?:It|it) (?:was|is|'s) (in|at|on|from|with|for) ([^,]+?) that (\w+) ", r"\3 ", text) if False else text
    m = re.match(r"^(?:It|it) (?:was|is) (in|at|on) ([A-Z][\w ]+?) that (.+)$", text)
    if m:
        text = f"{m.group(3)} {m.group(1)} {m.group(2)}"
    return text


# ---------------------------------------------------------------- reading

class Context:
    """All user clauses of a conversation with entities, aliases and compact integer records."""

    def __init__(self, messages):
        self.reader = cm.Reader()                    # pronoun resolution, relation links, people
        self.clauses = []
        self.ids, self.strings = {}, []
        self.data = array('i')                       # flat records: index, subject id, flags, lemma ids..., -1
        self.relations = {}                          # 'cousin' -> {'joaquin', ...}
        self.things = []                             # recent non-person nouns for 'it' / 'that place'
        order = 0
        for index, m in enumerate(messages):
            if m.get('role') != 'user':
                continue
            text = cm.expand(m.get('content', ''))
            self.reader.read(index, m.get('content', ''))
            for sentence in cm.sentences(text):
                for part in self.split(sentence):
                    c = self.parse(index, order, part)
                    if c is not None:
                        self.clauses.append(c)
                        order += 1
        self.inherit()
        self.idf = self.weights()
        self.vocabulary = set().union(*[c.lemmas for c in self.clauses]) if self.clauses else set()

    def inherit(self):
        """An update that does not repeat its topic ('Correction: it's 7005', 'We changed our minds, white it is', 'The shop
        dropped it to 550', 'it's gelato these days') takes the topic and subject of the latest earlier clause it is
        about: one sharing a word or semantic field, or holding a value of the same kind when the update is a
        correction or refers back ('it', 'that')."""
        same = lambda kinds: {'money' if k == 'number' else k for k in kinds}
        df = {}
        for c in self.clauses:
            for l in c.lemmas:
                df[l] = df.get(l, 0) + 1
        for k, c in enumerate(self.clauses):
            c.parent = None
            reported_ref = 'reported' in c.flags and re.search(r"\b(?:it|that|this|they|them)\b", c.raw)
            if not ({'change', 'correct'} & c.flags or reported_ref) or 'question' in c.flags:
                continue
            kinds = same({v[0] for v in c.values} - {'person'} or {v[0] for v in c.values})
            refers = re.search(r"\b(?:it|that|this|they|them|those)\b", c.raw) or 'correct' in c.flags
            best, best_score = None, 0.0
            for distance, prev in enumerate(reversed(self.clauses[max(0, k - 60):k])):
                if 'question' in prev.flags:
                    continue
                shared = sum(1.0 / df[l] for l in c.lemmas & prev.lemmas if df.get(l, 99) <= 6)
                fields = any(FIELD_OF.get(a, set()) & FIELD_OF.get(b, set()) for a in c.lemmas for b in prev.lemmas if a != b)
                typed = bool(kinds and kinds & same({v[0] for v in prev.values}))
                score = shared + (0.6 if typed and (refers or fields) else 0) + (0.3 if fields else 0)
                if not shared and not (typed and (refers or fields)) and not ('correct' in c.flags and fields):
                    continue
                score -= distance * 0.002
                if score > best_score:
                    best, best_score = prev, score
            if best is not None:
                prev = best
                c.lemmas = c.lemmas | prev.lemmas
                c.parent = prev.order
                if prev.subject and (c.subject in (None, 'user') or (c.subject or '').startswith('the ')) and \
                        not (c.subject == 'user' and prev.subject.startswith('the ')):
                    c.subject = prev.subject

    def common(self, word):
        """Words too frequent in this conversation to tie an update to one earlier statement."""
        return sum(1 for c in self.clauses if word in c.lemmas) > 6

    def intern(self, text):
        if text not in self.ids:
            self.ids[text] = len(self.strings)
            self.strings.append(text)
        return self.ids[text]

    @staticmethod
    def split(sentence):
        parts = re.split(r'\s*;\s*|,\s+(?:but|and then|while|whereas)\s+|\s+but\s+(?=(?:I|we|he|she|they|my|[A-Z][a-z]+)\b)', sentence)
        return [p for p in parts if p and p.strip()]

    def person_names(self, text):
        names = []
        for n in re.findall(r"\b([A-Z][a-z]+(?:-[A-Z][a-z]+)?)\b", text):
            if n in cm.NAME_STOP or n.lower() in MONTHS or n.lower() in DAY_NAMES:
                continue
            key = n.lower()
            if key in self.reader.store.gender or (not cm.is_place(n) and not self.reader.pet_name(n)) or \
                    re.search(r'\b' + n + r"'s (?:birthday|age|job|wife|husband|partner|mum|mom|dad|son|daughter|kids|children|dog|cat|pet|friend|boyfriend|girlfriend|brother|sister|flat|house|car|phone|favourite|favorite|parents|family|boss|team|bike|name|surname|degree|hobby)\b", text):
                names.append(key)
        return names

    def parse(self, index, order, raw):
        text = raw.strip()
        if not text:
            return None
        c = Clause()
        c.index, c.order, c.text = index, order, text
        text = normalise(text)
        resolved = self.reader.substitute(text)
        low = resolved.lower()
        c.low = low
        c.raw = text.lower()                          # as written: values and 'it'/'that' checks use this
        flags = set()
        if CHANGE.search(low):
            flags.add('change')
        if CORRECT.search(low):
            flags.add('correct')
        if PAST.search(low):
            flags.add('past')
        if UNREAL.search(low):
            flags.add('unreal')
        if '?' in text:
            flags.add('question')
        src = REPORT.match(resolved)
        c.source = None
        if src and not re.match(r'^(?:i|we)\b', src.group('src'), re.I):
            c.source = src.group('src').lower()
            flags.add('reported')
        c.flags = flags
        c.negated = bool(re.search(r"\b(?:not|never|no longer|n't|nobody|nothing|none)\b", low))
        c.subject = self.subject_of(resolved, c.source)
        nd = re.match(r"^[Tt]he ([A-Z][a-z]+?)s? (?:next door|downstairs|upstairs)", text)
        if nd:
            c.subject = nd.group(1).lower()
        pron = re.match(r"^(?:(?:so|and|but|also|oh|well|anyway|btw|honestly|lol|hm+)[,]?\s+)?(He|She|They)\b", text)
        if pron and self.clauses:
            want = {'He': 'm', 'She': 'f', 'They': None}[pron.group(1)]
            people = set(self.reader.store.gender) | {n for names in self.relations.values() for n in names}
            for prev in reversed(self.clauses[-12:]):
                cands = ([prev.subject] if prev.subject in people else []) + sorted(prev.mentions & people)
                if pron.group(1) == 'They' and prev.subject and prev.subject not in ('user',) and not prev.subject.startswith('my '):
                    cands = [prev.subject] + cands
                pick = next((n for n in cands if want is None or self.reader.store.gender.get(n, 'u') in (want, 'u')), None)
                if pick:
                    c.subject = pick
                    break
        # relation links: "my cousin Joaquin", "Joaquin is my cousin"
        for rel, name in re.findall(r"\b[Mm]y ((?:best |older |younger |little |big )?[a-z]+),? ([A-Z][a-z]+)\b", text):
            head = rel.split()[-1]
            if head in PERSON_REL or head.rstrip('s') in PERSON_REL:
                self.relations.setdefault(head.rstrip('s') if head.endswith('s') and head.rstrip('s') in PERSON_REL else head, set()).add(name.lower())
        for name in re.findall(r"\b[Tt]he ([A-Z][a-z]+?)s? (?:next door|downstairs|upstairs|across the (?:road|street|hall))\b", text):
            self.relations.setdefault('neighbour', set()).add(name.lower())
        for name, rel in re.findall(r"\b([A-Z][a-z]+) is my ((?:best |older |younger )?[a-z]+)\b", text):
            head = rel.split()[-1]
            if head in PERSON_REL:
                self.relations.setdefault(head, set()).add(name.lower())
        words = re.findall(r"[A-Za-z][A-Za-z'-]*|\d+(?:[.:,]\d+)?", resolved)
        lemmas = set()
        for w in words:
            lw = w.lower().strip("'")
            if lw.endswith("'s"):
                lw = lw[:-2]
            if lw in STOP or len(lw) < 2:
                continue
            lemmas |= bases(lw)
        # 'it', 'that place', 'there', 'the latter' borrow the last thing talked about
        if re.search(r"\b(?:it|that place|there|that one|this one|the place|the latter|the former)\b", text.lower()) and self.things:
            lemmas.add(self.things[-1])
        c.lemmas = lemmas
        c.values = self.values(text, text)
        c.mentions = set(self.person_names(text))
        c.chunks = self.chunks(text)
        visit = re.search(r"\bvisit(?:ing|ed)? ([A-Z][a-z]+) (?:in|at) ([A-Z][a-z]+)", text)
        if visit and visit.group(1).lower() not in ('the',):
            c.subject = visit.group(1).lower()
            lemmas |= {'live', 'home', 'base'}
            c.lemmas = lemmas
        for noun in re.findall(r"\b(?:a|an|the|that|this|our|my|his|her|their) (?:[a-z]+ )?([a-z]{3,})\b", low):
            if noun not in STOP and not cm.is_person_noun(noun):
                self.things.append(lemma(noun))
        record = [index, self.intern(c.subject or ''), sum(1 << i for i, f in enumerate(
            ('change', 'correct', 'past', 'unreal', 'reported', 'question')) if f in flags) | (64 if c.negated else 0)]
        record += [self.intern(l) for l in sorted(lemmas)]
        self.data.extend(record + [-1])
        return c

    def in_law(self, rel):
        """brother-in-law = a sibling's husband (or spouse's brother); sister-in-law = a sibling's wife (or spouse's sister)."""
        out = set()
        for c in self.clauses:
            m = re.search(r"\bmy (sister|brother)(?: ([a-z]+))? (?:married|is married to|got married to|wed)(?: a (?:man|woman|guy|girl))?(?: (?:called|named))? ([a-z]+)", c.raw)
            if m:
                out.add(m.group(3))
        return out

    def subject_of(self, text, source):
        body = text
        if source:
            m = REPORT.match(text)
            body = text[m.end():].strip() if m else text
        body = re.sub(LEADING, '', body)
        body = re.sub(r"^(?:(?:so|and|but|also|oh|well|anyway|honestly|random,? but|btw|by the way|lol|hm+|yeah|ok|okay|sorry|"
                      r"actually|correction|update|news|guess what)[,:!]?\s+)+", '', body, flags=re.I)
        m = re.match(r"^(?:[Mm]y|[Oo]ur) ((?:best |older |younger |little |big )?[a-z]+)(?:,? ([A-Z][a-z]+))?", body)
        if m:
            if m.group(2):
                head = m.group(1).split()[-1]
                return m.group(2).lower() if head in PERSON_REL else 'my ' + head
            head = m.group(1).split()[-1]
            after = body[m.end(1):m.end(1) + 20]
            if head in PERSON_REL and re.match(r"\s+(?!(?:is|was|has|had|and|who|will|lives|works|said|says|went|got|just|also|loves|likes)\b)[a-z]+\b", after) \
                    and not m.group(2):
                return 'user'
            if head in PERSON_REL:
                names = self.relations.get(head)
                if names and len(names) == 1:
                    return next(iter(names))
                return 'my ' + head
            return 'user'
        m = re.match(r"^([A-Z][a-z]+), (?:my|our) ([a-z]+)\b", body)
        if m and m.group(2) not in PERSON_REL:
            return 'my ' + m.group(2)
        m = re.match(r"^(I|We|I'm|We're)\b", body)
        if m:
            return 'user'
        m = re.match(r"^([A-Z][a-z]+)(?:'s)?\b", body)
        if m and m.group(1) not in cm.NAME_STOP:
            return m.group(1).lower()
        m = re.match(r"^(?:[Tt]he|[Tt]his|[Tt]hat) ([a-z]+(?: [a-z]+)?)", body)
        if m:
            words = m.group(1).split()
            head = words[1] if len(words) == 2 and words[1] not in STOP and is_noun(words[1]) and not words[1].endswith('ed') \
                and not (words[1].endswith('s') and is_verb(lemma(words[1]))) else words[0]
            return 'the ' + lemma(head)
        return None

    def values(self, original, resolved):
        text = resolved
        out = []
        for m in TIME_RE.finditer(text):
            if m.group(6):
                minutes = {'noon': 720, 'midday': 720, 'midnight': 0}[m.group(6).lower()]
            elif m.group(3):
                h = int(m.group(1)) % 12 + (12 if m.group(3).lower().startswith('p') else 0)
                minutes = h * 60 + int(m.group(2) or 0)
            else:
                minutes = int(m.group(4)) * 60 + int(m.group(5))
            out.append(('time', m.group(0), minutes, m.start()))
        for m in DATE_RE.finditer(text):
            day = int(m.group(1) or m.group(4))
            month = (m.group(2) or m.group(3)).lower()
            out.append(('date', m.group(0), MONTHS.index(month) * 31 + day, m.start()))
        for m in re.finditer(r'\b(' + '|'.join(DAY_NAMES) + r')s?\b', text, re.I):
            out.append(('day', m.group(1).capitalize(), DAY_NAMES.index(m.group(1).lower()), m.start()))
        taken = {v[3] for v in out if v[0] == 'time'}
        for m in re.finditer(r'(?:[$€£]\s?)?\b(\d+(?:[.,]\d+)?|' + '|'.join(sorted(NUMBER_WORDS, key=len, reverse=True)) +
                             r')\b(?:\s*(' + CURRENCY + r'|' + UNIT + r')\b)?', text, re.I):
            if m.start() in taken or any(abs(m.start() - t) < 3 for t in taken):
                continue
            word = m.group(1).lower()
            if word in ('one', 'half') and not m.group(2):
                continue                                   # "the one I mentioned", "half the time"
            n = number_value(word)
            if n is None:
                continue
            unit = (m.group(2) or '').lower()
            kind = 'money' if re.match(CURRENCY, unit) or m.group(0)[:1] in '$€£' else 'number'
            out.append((kind, m.group(0).strip(), n, m.start(), unit))
        low = text.lower()
        for colour in sorted(cm.COLORS | {'beige', 'navy', 'gold', 'teal', 'lilac', 'maroon', 'turquoise', 'cream', 'mustard',
                                          'olive', 'coral', 'burgundy', 'violet'}, key=len, reverse=True):
            for m in re.finditer(r'\b' + colour + r'\b', low):
                out.append(('colour', colour, colour, m.start()))
        for m in re.finditer(r"\b([A-Z][a-z]+(?:[ -][A-Z][a-z]+)?)\b", original):
            word = m.group(1)
            if word in cm.NAME_STOP or word.lower() in MONTHS or word.lower() in DAY_NAMES:
                continue
            after_prep = re.search(r"\b(?:in|to|from|near|outside|around|visiting|visit|visited)\s+$", original[:m.start()])
            if (cm.is_place(word.split()[0]) or after_prep and word.lower() not in self.reader.store.gender and m.start() > 0) and \
                    word.lower() not in self.reader.store.gender and \
                    not re.search(r'\b' + word + r"'s (?:birthday|age|job|wife|husband|partner|mum|mom|dad|son|daughter|kids|children|dog|cat|pet|friend|boyfriend|girlfriend|brother|sister|flat|house|car|phone|favourite|favorite|parents|family|boss|team|bike|name|surname|degree|hobby)\b", original):
                out.append(('place', word, word.lower(), m.start()))
            elif m.start() > 0 or word.lower() in self.reader.store.gender or re.match(r"[A-Z][a-z]+, (?:my|our|his|her|their) ", original):
                out.append(('person', word, word.lower(), m.start()))
        return out

    @staticmethod
    def chunks(text):
        """Runs of content words: candidate answers for 'what' questions ('forestry', 'folding chairs')."""
        out, run, start = [], [], 0
        tokens = list(re.finditer(r"[A-Za-z][A-Za-z'-]*|\d+(?:[.:,]\d+)?", text))
        for t in tokens + [None]:
            w = t.group(0).lower() if t else None
            if t is None or w in STOP or w.endswith("'s") and w[:-2] in STOP:
                if run:
                    out.append((' '.join(x.group(0) for x in run), run[0].start()))
                run = []
                continue
            run.append(t)
        return out

    def weights(self):
        df = {}
        for c in self.clauses:
            for l in c.lemmas:
                df[l] = df.get(l, 0) + 1
        n = max(1, len(self.clauses))
        import math
        return {l: math.log(1 + n / k) for l, k in df.items()}

    def nbytes(self):
        return self.data.itemsize * len(self.data) + sum(len(s.encode('utf-8')) + 1 for s in self.strings)


TIME_NOUNS = {'morning', 'evening', 'afternoon', 'night', 'week', 'weekend', 'month', 'year', 'summer', 'winter', 'spring',
              'autumn', 'fall', 'moment', 'end', 'beginning', 'meantime', 'past', 'future', 'today', 'tonight', 'time', 'while', 'day',
              'minute', 'hour', 'second', 'lunch', 'breakfast', 'dinner', 'way', 'end'}
ANSWER_NOUNS = {'colour', 'color', 'time', 'day', 'date', 'city', 'town', 'country', 'place', 'name', 'number', 'kind', 'sort',
                'type', 'thing', 'things', 'one', 'amount', 'lot', 'way', 'part', 'bit', 'year', 'week', 'month', 'moment', 'now',
                'two', 'three', 'four', 'five', 'living', 'work', 'job'}


@lru_cache(maxsize=16384)
def is_verb(word):
    db = cm._wordnet()
    return db is not None and db.execute("SELECT 1 FROM lemma WHERE word=? AND pos='verb' LIMIT 1", (word,)).fetchone() is not None


@lru_cache(maxsize=16384)
def is_noun(word):
    db = cm._wordnet()
    if db is None:
        return True
    return db.execute("SELECT 1 FROM lemma WHERE word=? AND pos='noun' LIMIT 1", (word,)).fetchone() is not None


def matches(ctx, word, lemmas):
    if word in lemmas or synonyms(word) & lemmas:
        return True
    fields = FIELD_OF.get(word)
    return bool(fields) and any(FIELD_OF.get(l, set()) & fields for l in lemmas)


AUX_WORDS = {'of', 'kind', 'sort', 'type', 'do', 'does', 'did', 'is', 'are', 'was', 'were', 'will', 'can', 'could', 'should',
             'would', 'have', 'has', 'had', 'am', 'else', 'about', 'if', 'happened', 'happens'}
IN_LAW = {'brother-in-law', 'sister-in-law', 'in-law', 'in-laws'}


# ---------------------------------------------------------------- questions

class Question:
    def __init__(self, ctx, text):
        self.ctx = ctx
        self.stranger = False
        self.text = cm.expand(text).strip()
        low = self.text.lower().rstrip(' ?.!')
        low = re.sub(r"^(?:(?:so|and|ok|okay|hey|quick question|remind me|tell me|do you remember|can you remind me|"
                     r"could you tell me|do you know)[,:]?\s+)+", '', low)
        low = re.sub(r"^(?:at|on|in|by|from|until|till|for|with|to) (?=(?:what|which|whom|whose|when)\b)", '', low)
        self.low = low
        wh = re.match(r"(what time|what day|which day|what date|how many|how much|how old|how long|how far|how tall|"
                      r"what colou?r|which colou?r|where|when|who|whom|whose|which|what|how)\b", low)
        if not wh:
            lead = re.match(r"^([^,]{3,60}),\s*(?=(?:what|which|who|where|when|how|whose)\b)", low)
            if lead:
                low = low[lead.end():] + ' ' + lead.group(1)      # keep the qualifier ('before the career change')
                self.low = low
                wh = re.match(r"(what time|what day|which day|what date|how many|how much|how old|how long|how far|how tall|"
                              r"what colou?r|which colou?r|where|when|who|whom|whose|which|what|how)\b", low)
        self.wh = wh.group(1) if wh else ('yesno' if re.match(r"(?:is|are|was|were|do|does|did|can|could|will|would|has|have|should|"
                                                              r"am)\b", low) else None)
        words = re.findall(r"[a-z][a-z'-]*|\d+", low)
        words = [w[:-2] if w.endswith("'s") else w.strip("'") for w in words]
        self.lemmas = {b for w in words if w not in STOP and len(w) > 1 and w not in ('colour', 'color') for b in bases(w)} | \
            ({'colour'} if re.search(r'colou?r', low) else set())
        self.subjects = self.find_subjects()
        mv = re.search(r"\b(?:did|does|do|will|would|can|could)\b(?: [a-z']+){1,6}? (have|has|own|carry|carrying|bring|wear|keep|take|need|want|"
                       r"buy|get|give|use|make|eat|drink|order|find|lose|see|meet|visit|play|read|watch|study|teach|call|open|fit|unlock|"
                       r"cost|mean|need|like|love|hate|prefer|speak|win|lose)\b\??$", low) or \
            re.search(r"\b(?:was|were|is|are) [a-z]+ (carrying|wearing|holding|using|eating|drinking|reading|watching)\b", low)
        self.verb = lemma(mv.group(1)) if mv else None
        self.lemmas -= self.subjects                  # the person asked about is not evidence of the answer
        self.anchors = self.find_anchors() - self.subjects
        self.places = {w.lower() for w in re.findall(r"\b([A-Z][a-z]+)\b", self.text[1:])
                       if w.lower() not in self.subjects and w not in cm.NAME_STOP and w.lower() not in DAY_NAMES and
                       w.lower() not in MONTHS and any(w.lower() in c.raw for c in ctx.clauses) and cm.is_place(w)}
        cat = re.match(r"(?:which|what) ([a-z]+)\b", self.low)
        self.category = lemma(cat.group(1)) if cat and cat.group(1) not in ANSWER_NOUNS and is_noun(lemma(cat.group(1))) and \
            cat.group(1) not in AUX_WORDS else None
        if self.category and self.category in self.anchors and not any(self.category in c.lemmas for c in ctx.clauses):
            self.anchors.discard(self.category)
        self.expect = self.expected()
        self.past = bool(re.search(r'\b(?:before|previous(?:ly)?|used to|originally|at first|first|old|former(?:ly)?|initially|'
                                   r'earlier|prior)\b', low)) and not re.search(r'\bfirst thing\b|\bthe first\b', low)

    def find_subjects(self):
        ctx, low, out = self.ctx, self.low, set()
        src = re.search(r'\b(?:according to|says?|said|thinks?)\b\s*((?:my |the )?[a-z]+)', low)
        self.source = src.group(1) if src and re.search(r'according to', low) else None
        if self.source:
            low = low.replace(src.group(0), ' ')
        known = set(ctx.reader.store.gender) | {n for c in ctx.clauses for n in c.mentions} | \
            {c.subject for c in ctx.clauses if c.subject} | {n for names in ctx.relations.values() for n in names}
        for m in re.finditer(r"\b([A-Z][a-z]+)\b", self.text[1:]):
            name = m.group(1).lower()
            if name in known and not re.match(r"\s+[A-Z][a-z]+", self.text[1 + m.end():]):
                out.add(name)
            elif name in known:
                self.stranger = True               # 'Ben Franklin' is not the Ben from this chat
        for rel in re.findall(r"\bmy ((?:best |older |younger )?[a-z]+(?:-in-law)?)\b", low):
            head = rel.split()[-1]
            head = head[:-2] if head.endswith("'s") else head
            if head in IN_LAW:
                out |= ctx.in_law(head)
                continue
            follow = re.search(r"\bmy " + re.escape(rel) + r"(?:'s|s)?\s+([a-z]+)", low)
            if follow and follow.group(1) not in STOP and is_noun(lemma(follow.group(1))) and not is_verb(lemma(follow.group(1))) \
                    and not rel.endswith("'s"):
                out.add('user')
                continue
            if head in PERSON_REL or head + 's' in PERSON_REL:
                names = ctx.relations.get(head) or ctx.relations.get(head.rstrip('s')) or ctx.relations.get(head + 's')
                out |= set(names) if names else {'my ' + head}
        if not out and re.search(r"\b(?:i|my|me|we|our|us)\b", low):
            out.add('user')
        return out

    def strict(self, anchor):
        """An anchor that never occurs in the conversation still has to match by synonym or field when it is the
        only one; otherwise it is optional (the question may use a paraphrase CAEL cannot link)."""
        return len(self.anchors) == 1

    def find_anchors(self):
        """Nouns the question is about ('the boots', 'my bike', 'which airline'): a clause must mention every one."""
        out = set()
        for m in re.finditer(r"\b(?:my|our|the|a|an|his|her|their|which|what|whose|how many|how much|[a-z]+'s)\s+(?=((?:[a-z-]+\s+){0,2}[a-z-]+))",
                             self.low):
            for w in m.group(1).split():
                if w in STOP or w in ANSWER_NOUNS or w in DAY_NAMES:
                    break
                lw = lemma(w)
                if lw in ANSWER_NOUNS or lw in PERSON_REL or len(lw) < 3 or not is_noun(lw):
                    continue
                out.add(lw)
        return out

    def expected(self):
        wh, low = self.wh, self.low
        if re.search(r'\b(?:for a living|for work|job|profession|occupation|career|work as|line of work|what does \w+ do)\b', low)                 and wh in ('what', 'how'):
            return 'job'
        if re.search(r'\b(?:called|named|name|nickname|call)\b', low) and wh in ('what', 'which', 'how', 'who'):
            return 'name'
        if re.search(r'\b(?:which|what) (?:street|road|avenue|address)\b', low):
            return 'street'
        if re.match(r"how (?:am|are|is|will|do|does|did) (?:i|we|you|he|she|they|\w+) (?:getting|going|travell?ing|get|go|travel|commuting|commute)\b", low):
            return 'manner'
        if re.search(r'\b(?:which|what) month\b', low):
            return 'month'
        if wh in ('what time',) or re.search(r'\bwhat time\b|\bat what time\b', low):
            return 'time'
        if wh in ('what day', 'which day') or re.search(r'\bwhich day\b|\bwhat day\b', low):
            return 'day'
        if wh == 'what date':
            return 'date'
        if wh in ('what colour', 'what color', 'which colour', 'which color') or re.search(r'\bcolou?r\b|\b(?:what|which) (?:shade|hue|tint)\b', low):
            return 'colour'
        if wh in ('how many',):
            return 'number'
        if re.search(r'\b(?:number|code|pin|size|length|width|height|weight|distance|temperature|speed|score|floor|room|locker|seat|gate|'
                     r'platform|postcode|zip)\??$', low) or re.search(r'\b(?:what|which) (?:\w+ )?(?:length|size|width|height|weight|'
                                                                      r'distance|temperature|speed|number|code)\b', low):
            return 'number'
        if wh == 'how much':
            return 'money' if re.search(r'\b(?:cost|pay|paid|spend|spent|price|charge|budget|owe|earn|rent|worth)\b', low) else 'number'
        if wh in ('how old', 'how long', 'how far', 'how tall'):
            return 'number'
        if wh == 'when':
            return 'when'
        if wh == 'where':
            return 'where'
        if wh in ('who', 'whom', 'whose'):
            return 'person'
        if wh == 'yesno':
            return 'yesno'
        m = re.match(r"(?:what|which) (\w+)", low)
        if m and m.group(1) in ('number', 'code', 'pin', 'size', 'floor', 'room', 'locker', 'seat', 'gate', 'platform', 'year', 'age'):
            return 'number'
        if m and m.group(1) in ('city', 'country', 'town', 'place'):
            return 'where'
        if wh in ('which',) and re.search(r'\bof (?:the|my|them|those|these|us)\b', low):
            return 'choice'
        return 'thing'


# ---------------------------------------------------------------- answering

def overlap(ctx, q, c):
    """Weighted match of the question's focus with a clause: shared lemmas, WordNet synonyms, shared semantic fields."""
    score = 0.0
    for ql in q.lemmas:
        w = ctx.idf.get(ql, 2.0)
        if ql in c.lemmas:
            score += w
            continue
        syn = synonyms(ql)
        if syn & c.lemmas:
            score += 0.8 * w
            continue
        fields = FIELD_OF.get(ql, set())
        if fields and any(FIELD_OF.get(cl, set()) & fields for cl in c.lemmas):
            score += 0.6 * w
    return score


def subject_fit(ctx, q, c):
    if not q.subjects:
        return 0.0
    if c.subject in q.subjects:
        return 2.0
    if c.mentions & q.subjects:
        return 1.0
    if q.subjects == {'user'} and c.subject in (None, 'user') or q.subjects == {'user'} and c.subject and c.subject.startswith('the '):
        return 0.5
    if 'user' in q.subjects and c.subject and c.subject.startswith('my '):
        return 0.6
    return -3.0


def candidates(ctx, q, c):
    """Values in a clause that fit the expected answer type, best first."""
    vals = c.values
    want = q.expect
    neg_spans = [m.end() for m in re.finditer(r"\b(?:not|never|n't|no|gone off|went off|stopped(?: liking)?|sick of|"
                                                 r"tired of|quit|gave up|instead of|rather than|no longer|anymore)\b", c.raw)]
    only = c.raw.find(' only ')

    def negated(pos):
        before = [p for p in neg_spans if p < pos]
        return bool(before) and not (only >= 0 and before[-1] < only < pos)

    def ok(v):
        return not negated(v[3])
    if want == 'time':
        return [v for v in vals if v[0] == 'time' and ok(v)]
    if want == 'day':
        return [v for v in vals if v[0] in ('day', 'date') and ok(v)]
    if want == 'date':
        return [v for v in vals if v[0] in ('date', 'day') and ok(v)]
    if want == 'when':
        return [v for v in vals if v[0] in ('day', 'date', 'time') and ok(v)]
    if want == 'colour':
        return [v for v in vals if v[0] == 'colour' and ok(v)]
    if want == 'money':
        return [v for v in vals if v[0] == 'money' and ok(v)] or [v for v in vals if v[0] == 'number' and ok(v)]
    if want == 'number':
        return [v for v in vals if v[0] in ('number', 'money') and ok(v)]
    if want == 'name':
        return [v for v in vals if v[0] == 'person' and v[2] not in q.subjects and ok(v)]
    if want == 'street':
        return [('street', m.group(0).title(), m.group(0).lower(), m.start()) for m in
                re.finditer(r"\b[a-z]+ (?:street|road|avenue|lane|drive|way|square|close|crescent|boulevard)\b", c.raw)
                if not negated(m.start())]
    if want == 'manner':
        return [('manner', m.group(1), m.group(1), m.start()) for m in
                re.finditer(r"\b(drive|driving|car|train|bus|coach|bike|cycle|cycling|walk|walking|fly|flying|plane|taxi|cab|"
                            r"ferry|boat|tram|metro|subway|scooter|uber|lift)\b", c.raw) if not negated(m.start()) and
                not re.search(r'\b(?:strik|cancel|delay|broke|no )\w*', c.raw[m.end():m.end() + 30])]
    if want == 'month':
        return [('month', m.group(1).capitalize(), m.group(1).lower(), m.start()) for m in
                re.finditer(r'\b(' + '|'.join(MONTHS) + r')\b', c.raw)]
    if want == 'job':
        jobs = []
        for t, pos in c.chunks:
            ws = [w for w in t.lower().split() if cm.is_job(lemma(w)) and lemma(w) not in PERSON_REL]
            if ws:
                jobs.append(('job', ws[-1], ws[-1], pos))
        return [v for v in jobs if ok(v)]
    if want == 'person':
        return [v for v in vals if v[0] == 'person' and v[2] not in q.subjects and ok(v)]
    if want == 'where':
        places = [v for v in vals if v[0] == 'place' and ok(v)]
        if places:
            return places
        spots = [('spot', m.group(2), m.group(2), m.start(2)) for m in
                 re.finditer(r"\b(in|on|at|under|inside|behind|next to|near|by|to|into|onto) (?:the |my |our |a |his |her )?((?:[a-z]+ ){0,2}[a-z]+)",
                             c.raw) if m.group(2).split()[0] not in STOP and m.group(2).split()[-1] not in TIME_NOUNS
                 and not (m.group(1) in ('to', 'into', 'onto') and not re.search(r'\b(?:moved|put|took|placed|brought|left|stuck|tucked|shifted|'
                                                                                 r'stored|hid|dropped|carried)\b', c.raw))]
        return [s for s in spots if ok(s)]
    chunks = [('thing', t, t.lower(), pos) for t, pos in c.chunks]
    out = []
    for v in chunks:
        words = [lemma(w) for w in re.findall(r"[a-z']+|\d+", v[2])]
        rest = [w for w in words if w not in q.lemmas and w not in q.subjects and w != q.verb and not (FIELD_OF.get(w, set()) & set().union(*[FIELD_OF.get(x, set()) for x in q.lemmas]))
                and w not in (c.subject or '').split()]
        if not rest or not ok(v):
            continue
        text = ' '.join(w for w in re.findall(r"[A-Za-z'-]+|\d+", v[1]) if lemma(w.lower()) in rest or w.lower() in rest)
        out.append(('thing', text, text.lower(), v[3]))
    if q.category and q.category not in c.lemmas:
        cat = {q.category} | set(synonyms(q.category))
        typed = [v for v in out if any(cat & (cm.kinds(lemma(w), senses=3) | {lemma(w)}) for w in v[2].split())]
        return typed
    return out


def best_value(ctx, q, c):
    cands = candidates(ctx, q, c)
    if not cands:
        return None
    # the value nearest after the last matched focus word, else the last one
    focus = [m.start() for l in q.lemmas for m in re.finditer(r'\b' + re.escape(l[:5]), c.raw)]
    anchor = max(focus) if focus else -1
    after = [v for v in cands if v[3] > anchor]
    return (after or cands)[0] if q.expect == 'thing' else (after or cands)[0]


def retrieve(ctx, q):
    scored = []
    named = q.subjects - {'user'}
    for c in ctx.clauses:
        if 'question' in c.flags:
            continue
        if q.source and (c.source or '') != q.source and not (c.source or '').endswith(q.source.split()[-1]):
            continue
        if q.source:
            named = set()
        if named and c.subject not in named and not (c.mentions & named) and not (c.subject or '').startswith('my '):
            continue                                 # a fact about somebody else
        if named and c.subject and c.subject not in named and c.subject != 'user' and not c.subject.startswith(('my ', 'the ')) \
                and not (c.mentions & named):
            continue
        if q.anchors and not all(matches(ctx, a, c.lemmas) for a in q.anchors if a in ctx.vocabulary or q.strict(a)):
            continue
        if q.places and not all(re.search(r'\b' + pl + r'\b', c.raw) for pl in q.places):
            continue
        if q.subjects == {'user'} and c.subject and c.subject not in ('user',) and not c.subject.startswith(('my ', 'the ')) \
                and c.subject in ctx.reader.store.gender:
            continue                                 # 'my rabbit' is not Carla's rabbit
        o = overlap(ctx, q, c)
        verb_hit = q.verb and q.verb in {b for w in re.findall(r"[a-z']+", c.raw) for b in bases(w)}
        if o <= 0 and not (verb_hit and named and c.mentions & named):
            continue                                 # bonuses only strengthen a clause that is already about the question
        o += (1.0 if named and c.mentions & named else 0.0) + (1.5 if verb_hit else 0.0)
        if o <= 0:
            continue
        s = o + subject_fit(ctx, q, c)
        if s <= 0.5:
            continue
        v = best_value(ctx, q, c)
        if v is None:
            continue
        scored.append((s, c, v))
    return scored


def say(value):
    return value[1] if isinstance(value, tuple) else str(value)


def decide(ctx, q, scored):
    """Pick the answer across matching clauses: latest change/correction wins, plain disagreement is a conflict."""
    if not scored:
        return None
    top = max(s for s, _, _ in scored)
    if top < min(1.0, 0.6 * sum(ctx.idf.get(l, 0.0) for l in q.lemmas)) or top <= 0.3:
        return None
    present = {a for a in q.anchors if a in ctx.vocabulary}
    close = [x for x in scored if x[0] >= 0.7 * top or (present and present <= x[1].lemmas and x[0] >= 0.3 * top)]
    linked = {x[1].order for x in close}
    for x in sorted(scored, key=lambda x: x[1].order):
        if getattr(x[1], 'parent', None) in linked and x not in close:
            close.append(x)
            linked.add(x[1].order)
    close = sorted(close, key=lambda x: x[1].order)
    distinct = []
    for s, c, v in close:
        key = str(v[2]).lower()
        if not distinct or all(key != str(d[2][2]).lower() for d in distinct):
            distinct.append((s, c, v))
    if len(distinct) == 1:
        return dict(value=distinct[0][2], clause=distinct[0][1], score=top)
    if q.past:
        first = distinct[0]
        return dict(value=first[2], clause=first[1], score=top, note=f'Later it became {say(distinct[-1][2])}.')
    last = distinct[-1]
    marked = {'change', 'correct'} & last[1].flags or any('past' in d[1].flags or d[1].negated for d in distinct[:-1])
    sources = {d[1].source for d in distinct if d[1].source}
    if marked and not sources:
        return dict(value=last[2], clause=last[1], score=top, history=[d[2] for d in distinct[:-1]])
    # only clauses with the subject itself compete; facts about others are not a conflict
    if q.subjects and len({d[1].subject for d in distinct if d[1].subject not in (None, 'user') and not d[1].subject.startswith('the ')}) > 1 \
            and not sources:
        best = max(distinct, key=lambda d: d[0])
        return dict(value=best[2], clause=best[1], score=top)
    return dict(conflict=distinct, score=top)


# ---------------------------------------------------------------- compositional operations

COMPARE = {'old': ('older', 'younger'), 'young': ('younger', 'older'), 'tall': ('taller', 'shorter'), 'short': ('shorter', 'taller'),
           'big': ('bigger', 'smaller'), 'small': ('smaller', 'bigger'), 'fast': ('faster', 'slower'), 'slow': ('slower', 'faster'),
           'heavy': ('heavier', 'lighter'), 'light': ('lighter', 'heavier'), 'early': ('earlier', 'later'), 'late': ('later', 'earlier'),
           'cheap': ('cheaper', 'more expensive'), 'expensive': ('more expensive', 'cheaper'), 'long': ('longer', 'shorter')}
SUPERLATIVE = {'oldest': ('old', 1), 'youngest': ('old', -1), 'tallest': ('tall', 1), 'shortest': ('tall', -1), 'biggest': ('big', 1),
               'smallest': ('big', -1), 'fastest': ('fast', 1), 'slowest': ('fast', -1), 'heaviest': ('heavy', 1), 'lightest': ('heavy', -1),
               'earliest': ('late', -1), 'latest': ('late', 1), 'last': ('late', 1), 'first': ('late', -1), 'cheapest': ('expensive', -1),
               'most expensive': ('expensive', 1), 'longest': ('long', 1), 'older': ('old', 1), 'younger': ('old', -1),
               'taller': ('tall', 1), 'shorter': ('tall', -1)}
NUMERIC_ATTR = {'old': r'(\d{1,3})(?: years? old|\b)|turn(?:ed|s)? (\d{1,3})|aged? (\d{1,3})',
                'tall': r'(\d{2,3}) ?cm|(\d(?:\.\d+)?) ?m(?:etres?|eters?)?\b'}


def order_facts(ctx, dim):
    """Pairwise facts on one dimension: (greater, smaller) person pairs and numeric values, from all clauses."""
    pairs, numbers = [], {}
    more, less = COMPARE[dim]
    for c in ctx.clauses:
        names = [n for n in re.findall(r"\b([A-Z][a-z]+)\b", c.text) if n not in cm.NAME_STOP]
        low = c.low
        for a, word, b in re.findall(r"\b([a-z]+) (?:is|was|are|were|got|arrived|came|finished|showed up|turned up)?\s*(?:a bit |much |slightly |a little )?"
                                     r"(" + re.escape(more) + r"|" + re.escape(less) + r")(?: \w+)? than ([a-z]+)\b", low):
            pairs.append((a, b) if word == more else (b, a))
        if dim == 'late':
            for a, word, b in re.findall(r"\b([a-z]+) (?:arrived|came|got there|showed up|turned up|finished|left|got in|joined)\s+"
                                         r"(?:just |shortly |right |long )?(after|before) ([a-z]+)\b", low):
                pairs.append((a, b) if word == 'after' else (b, a))
            for a, word, b in re.findall(r"\b([a-z]+) (?:arrived|came|got there|showed up|turned up|finished|left)\b.*?\b(first|last)\b", low):
                pass
        if dim in NUMERIC_ATTR and c.subject and len(names) <= 1:
            m = re.search(NUMERIC_ATTR[dim], low)
            if m and (dim != 'old' or re.search(r'\b(?:years? old|turn\w*|aged?|is \d{1,3}\b|age)', low)):
                n = float(next(g for g in m.groups() if g))
                numbers[c.subject] = n
    return pairs, numbers


def rank(ctx, dim, sign, among):
    pairs, numbers = order_facts(ctx, dim)
    people = set(among) | {a for p in pairs for a in p} | set(numbers)
    if among:
        people &= set(among) | {a for p in pairs for a in p}
    if numbers and all(p in numbers for p in people if p in among or not among) and len(numbers) >= 2:
        pool = {p: v for p, v in numbers.items() if not among or p in among}
        if len(pool) >= 2:
            return (max if sign > 0 else min)(pool, key=pool.get)
    # topological extreme over "greater than" pairs (numbers add pairs too)
    names = sorted(numbers)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if numbers[a] != numbers[b]:
                pairs.append((a, b) if numbers[a] > numbers[b] else (b, a))
    pool = (set(among) if among else people) & ({a for p in pairs for a in p} | set(numbers))
    if not pool:
        return None
    if sign > 0:
        top = [p for p in pool if not any(b == p and a in pool | {x for x, _ in pairs} for a, b in pairs)]
    else:
        top = [p for p in pool if not any(a == p for a, b in pairs)]
    return top[0] if len(top) == 1 else None


ORDINALS = {'first': 0, 'second': 1, 'third': 2, 'fourth': 3, 'fifth': 4, 'sixth': 5, 'last': -1, '1st': 0, '2nd': 1, '3rd': 2,
            '4th': 3}


def op_ordinal(ctx, q):
    """'What was the second thing I packed?' -> the 2nd item of the list in the clause about packing."""
    m = re.search(r"\b(first|second|third|fourth|fifth|sixth|last|1st|2nd|3rd|4th)\b (?:thing|item|one|place|stop|step|city|book|"
                  r"person|guest|dish|course|task|country|song|film|movie|game|pet|gift|present)?", q.low)
    if not m or q.wh not in ('what', 'which', 'who', 'where'):
        return None
    focus = q.lemmas - {m.group(1), 'thing', 'item', 'one'}
    best = None
    for c in ctx.clauses:
        items = re.search(r"((?:(?:an?|the|my|some) )?[\w' -]+?(?:, (?:(?:an?|the|my|some) )?[\w' -]+?)+,? and (?:(?:an?|the|my|some) )?[\w' -]+?)(?:[.!]|$| for| to| in| on)", c.low)
        if not items:
            continue
        score = sum(1 for f in focus if f in c.lemmas or synonyms(f) & c.lemmas)
        if score and (best is None or score > best[0]):
            parts = [re.sub(r"^(?:an?|the|my|some) ", '', x.strip()) for x in re.split(r",\s*(?:and\s+)?|\s+and\s+", items.group(1))]
            parts = [x for x in parts if x]
            first = parts[0].split()
            if len(first) > 2:                       # 'i packed a binoculars' -> 'binoculars'
                parts[0] = re.sub(r"^.*\b(?:an?|the|my|some)\s+", '', parts[0]) if re.search(r"\b(?:an?|the|my|some)\s+", parts[0]) else first[-1]
            best = (score, parts)
    if not best:
        return None
    k = ORDINALS[m.group(1)]
    parts = best[1]
    if k >= len(parts):
        return None
    return parts[k][0].upper() + parts[k][1:] + '.'


def op_superlative(ctx, q):
    m = re.search(r"\b(most expensive|" + '|'.join(k for k in SUPERLATIVE if ' ' not in k) + r")\b", q.low)
    if not m or q.wh not in ('who', 'which', 'whose', 'what') and not re.search(r'\bwho\b|\bwhich\b', q.low):
        return None
    dim, sign = SUPERLATIVE[m.group(1)]
    if m.group(1) in ('first', 'last') and not re.search(r'\b(?:arriv|got there|came|show|turn|finish|left|get there|join)', q.low):
        return None
    among = names_in_question(ctx, q)
    who = rank(ctx, dim, sign, among)
    return f'{who.title()}.' if who else None


def names_in_question(ctx, q):
    names = set(ctx.person_names(q.text))
    for rel in re.findall(r"\bmy ([a-z]+?)s?\b", q.low):
        names |= ctx.relations.get(rel, set())
    return names


def op_same(ctx, q):
    m = re.search(r"\b(?:same (\w+) as|as (\w+) as) ([A-Za-z]+(?:'s)?)(?: (\w+))?", q.text, re.I) or \
        re.search(r"\b(?:match(?:es)?|the same as) the (\w+) of ([A-Z][a-z]+)'s (\w+)", q.text)
    if not m:
        return None
    groups = [g for g in m.groups() if g]
    ref = next((g.rstrip("'s").lower() for g in groups if g[:1].isupper()), None)
    if not ref:
        return None
    attr = groups[0].lower()
    kind = 'colour' if attr in ('colour', 'color') else 'place' if attr in ('city', 'town', 'country', 'place') else \
        'day' if attr in ('day',) else None
    ref_vals, others = None, {}
    for c in ctx.clauses:
        vals = [v for v in c.values if (kind is None or v[0] == kind or kind == 'place' and v[0] == 'place')
                and v[2] != (c.subject or '')]
        if not vals:
            continue
        owner = c.subject
        poss = re.match(r"^([A-Z][a-z]+)'s\b", c.text)
        if poss:
            owner = poss.group(1).lower()
        if not owner:
            continue
        if owner == ref:
            ref_vals = vals[0][2]
        else:
            others.setdefault(owner, vals[0][2])
    if ref_vals is None:
        return None
    match = [o for o, v in others.items() if v == ref_vals and o not in ('user',)]
    if not match:
        return f'Nobody else you mentioned has the same {attr} as {ref.title()}.'
    return ' and '.join(x.title() for x in match) + '.'


def op_count(ctx, q):
    if q.wh != 'how many':
        return None
    m = re.search(r"\bhow many (?:of (?:those|these|the|my|them|us)(?: \w+)? )?(\w+)?.*?\b(?:live|lives|work|works|have|has|are|were|is|"
                  r"own|owns|speak|speaks|play|plays|went|go|like|likes)\b(?: in| at| on)? (.+)$", q.low)
    if not m:
        return None
    target = m.group(2).strip()
    tl = {lemma(w) for w in re.findall(r'[a-z]+', target) if w not in STOP}
    vl = {lemma(w) for w in re.findall(r'[a-z]+', q.low.split(m.group(2))[0]) if w not in STOP} - {'many'}
    found = set()
    for c in ctx.clauses:
        if c.negated or 'unreal' in c.flags:
            continue
        if tl and tl <= {lemma(w) for w in re.findall(r'[a-z]+', c.low)} and (not vl or vl & c.lemmas or any(synonyms(x) & c.lemmas for x in vl)):
            subj = c.subject or (sorted(c.mentions)[0] if c.mentions else None)
            if subj:
                found.add(subj)
            for n in c.mentions:
                if re.search(r'\b' + n + r'\b and\b|\band ' + n + r'\b', c.low):
                    found.add(n)
    if not found:
        return None
    n = len(found)
    return f'{fmt(n)} ({WORD_FOR.get(n, fmt(n))}): ' + ', '.join(x.title() for x in sorted(found)) + '.'


def op_sum(ctx, q):
    if not re.search(r'\b(?:together|in total|altogether|total|combined|sum|both)\b', q.low) or q.wh not in ('how much', 'how many', 'what'):
        return None
    vals = []
    for c in ctx.clauses:
        if 'question' in c.flags or c.negated:
            continue
        if overlap(ctx, q, c) + subject_fit(ctx, q, c) < 1.0:
            continue
        kind = 'money' if q.expect == 'money' else None
        for v in c.values:
            if v[0] == 'money' or (kind is None and v[0] == 'number'):
                vals.append(v[2])
    if len(vals) < 2:
        return None
    return f'{fmt(sum(vals))} in total ({" + ".join(fmt(v) for v in vals)}).'


def op_time(ctx, q):
    """'When does the film finish?' = start time + duration; 'how long' between two times."""
    if not re.search(r'\b(?:finish|end|over|done|arrive|get there|land|back|ready)\b', q.low) or q.expect not in ('time', 'when'):
        return None
    start = dur = None
    for c in ctx.clauses:
        if overlap(ctx, q, c) < 0.5 and not (start and re.search(r'\b(?:lasts?|takes?|long|runs? for|hours?|minutes?)\b', c.low)):
            continue
        t = [v for v in c.values if v[0] == 'time']
        if t and re.search(r'\b(?:start|begin|leave|depart|open|kick|at)\w*', c.low):
            start = t[0][2]
        d = re.search(r'\b(\d+(?:\.\d+)?|' + '|'.join(NUMBER_WORDS) + r')(?: and a half)? (hours?|hrs?|minutes?|mins?)\b', c.low)
        if d and re.search(r'\b(?:lasts?|takes?|long|runs? for|hours?|minutes?)\b', c.low):
            n = number_value(d.group(1)) or 0
            n += 0.5 if 'and a half' in d.group(0) else 0
            dur = n * 60 if d.group(2).startswith('h') else n
    if start is None or dur is None:
        return None
    end = int(start + dur) % 1440
    h, mnt = divmod(end, 60)
    ampm = 'am' if h < 12 else 'pm'
    return f'At {h % 12 or 12}{":%02d" % mnt if mnt else ""} {ampm}.'


RULE = re.compile(r"\b(?:only )?(?:admits?|allows?|accepts?|lets?|is for|is open to|requires?|must be|need to be|have to be|can join|can enter|"
                  r"can drive|can vote|can go)\b.*?\b(?:aged |at least |over |older than |under |younger than |below |above )?(\d{1,3})"
                  r"(?: or (over|older|above|more|under|younger|below|less))?", re.I)


def op_rule(ctx, q):
    """'The club only admits people aged 18 or over' + ages -> who can join / can X join."""
    if not re.search(r'\b(?:can|could|may|allowed|eligible|qualif|old enough|join|enter|drive|vote)\b', q.low):
        return None
    rule = None
    for c in ctx.clauses:
        m = RULE.search(c.low)
        if m and not c.subject in (None,) or m and re.search(r'\b(?:club|class|team|course|event|bar|ride|venue|gym|only|rule|must)\b', c.low):
            if m:
                limit = float(m.group(1))
                tail = (m.group(2) or '') + ' ' + c.low[m.start():m.end() + 12]
                if re.search(r'\b(?:under|younger|below|less)\b', tail):
                    rule = ('<', limit if re.search(r'or (?:under|younger|below|less)', tail) else limit - 1e-9, c)
                elif re.search(r'\bover\b(?! or)|\bolder than\b|\babove\b', tail) and not re.search(r'or over|or older|or above|or more', tail):
                    rule = ('>', limit, c)
                else:
                    rule = ('>=', limit, c)
    if not rule:
        return None
    _, ages = order_facts(ctx, 'old')
    if not ages:
        return None
    op, limit, _ = rule
    ok = lambda a: a >= limit if op == '>=' else a > limit if op == '>' else a <= limit
    named = names_in_question(ctx, q)
    if q.wh == 'yesno' and named:
        who = next(iter(named))
        if who not in ages:
            return None
        verdict = 'Yes' if ok(ages[who]) else 'No'
        return f'{verdict}: {who.title()} is {fmt(ages[who])}, and the limit is {fmt(limit)}.'
    pool = {p: a for p, a in ages.items() if not named or p in named}
    yes = [p for p, a in pool.items() if ok(a)]
    if not yes:
        return 'None of them: ' + ', '.join(f'{p.title()} is {fmt(a)}' for p, a in pool.items()) + f' (limit {fmt(limit)}).'
    return ' and '.join(p.title() for p in yes) + f' ({", ".join(f"{p.title()} is {fmt(a)}" for p, a in pool.items())}; limit {fmt(limit)}).'


def op_same_day(ctx, q):
    """'What else do I have on the day of my dentist visit?'"""
    m = re.search(r"\b(?:on|for) the (?:same )?day (?:of|as) (?:my |the |our )?(.+)$", q.low)
    if not m:
        return None
    ref = {lemma(w) for w in re.findall(r'[a-z]+', m.group(1)) if w not in STOP}
    day = None
    for c in ctx.clauses:
        if ref & c.lemmas:
            d = [v for v in c.values if v[0] in ('day', 'date')]
            if d:
                day = d[0][2]
                ref_clause = c
    if day is None:
        return None
    others = []
    for c in ctx.clauses:
        if c is ref_clause or c.negated:
            continue
        if any(v[0] in ('day', 'date') and v[2] == day for v in c.values):
            things = [t for t, _ in c.chunks if not re.search(r'\b(?:' + '|'.join(DAY_NAMES) + r')\b', t.lower())]
            if things:
                others.append(things[0])
    return ('Also on that day: ' + '; '.join(others) + '.') if others else None


def op_yesno_compare(ctx, q):
    """Yes/no questions decided by comparing two stated times or numbers ('Will the pool still be open when we arrive?')."""
    if q.wh != 'yesno':
        return None
    times = []
    for c in ctx.clauses:
        if overlap(ctx, q, c) + subject_fit(ctx, q, c) < 1.0:
            continue
        for v in c.values:
            if v[0] == 'time':
                kind = 'close' if re.search(r'\b(?:close|shut|end|until|till|stop|last)\w*', c.low) else \
                    'arrive' if re.search(r'\b(?:arriv|get there|land|reach|get in|be there)\w*', c.low) else 'other'
                times.append((kind, v))
    close = [v for k, v in times if k == 'close']
    arrive = [v for k, v in times if k == 'arrive']
    if not close or not arrive:
        return None
    c, a = close[-1], arrive[-1]
    if re.search(r'\b(?:still )?open\b|\bin time\b|\bmake it\b', q.low):
        ok = a[2] < c[2]
        return f'{"Yes" if ok else "No"}: you arrive at {a[1]} and it closes at {c[1]}.'
    return None


DECREASE = r'(?:gave|give|given|used|use|lost|lose|sold|sell|spent|spend|ate|eat|broke|threw|donated|lent|sent|posted|returned|' \
           r'dropped|removed|took out|gave away|got rid of)'
INCREASE = r'(?:bought|buy|got|received|found|added|won|collected|picked up|was given|were given|made|baked)'


def quantity(word):
    w = word.lower()
    return number_value(w) if number_value(w) is not None else None


def op_remaining(ctx, q):
    """'I had 16 stamps' + 'I gave 7 of them to my niece' -> how many do I still have: 9."""
    m = re.match(r"how many (\w+)", q.low)
    if not m or not re.search(r'\b(?:still|left|remaining|now|anymore|at the moment|currently)\b', q.low):
        return None
    thing = lemma(m.group(1))
    total, steps, seen = None, [], False
    for c in ctx.clauses:
        nums = re.findall(r"\b(\d+|" + '|'.join(k for k in NUMBER_WORDS if ' ' not in k) + r")\b", c.raw)
        about = thing in c.lemmas or synonyms(thing) & c.lemmas or (seen and re.search(r'\b(?:them|of them|those|these|it)\b', c.raw))
        if not about or not nums:
            continue
        n = quantity(nums[0])
        if n is None:
            continue
        if total is None and re.search(r'\b(?:had|have|has|own|owned|got|bought|collected|started with|there were|there are)\b', c.raw):
            total, seen = n, True
            steps.append(f'{fmt(n)}')
        elif total is not None and re.search(r'\b' + DECREASE + r'\b', c.raw):
            total -= n
            steps.append(f'- {fmt(n)}')
        elif total is not None and re.search(r'\b' + INCREASE + r'\b', c.raw):
            total += n
            steps.append(f'+ {fmt(n)}')
    if total is None or len(steps) < 2:
        return None
    return f'{fmt(total)} ({" ".join(steps)} = {fmt(total)}).'


def op_weekday(ctx, q):
    """'What day comes right after the market day?', 'the day before my exam', 'Today is Monday' + 'arrives in 7 days'."""
    if q.expect not in ('day', 'when') and not re.search(r'\bweekday\b|\bwhat day\b|\bwhich day\b', q.low):
        return None
    shift = 0
    m = re.search(r"\b(?:the )?day (after|before) (?:the |my |our )?(.+)$", q.low) or \
        re.search(r"\b(?:right |just )?(after|before) (?:the |my |our )?(.+?)(?: day)?$", q.low)
    today = None
    for c in ctx.clauses:
        t = re.search(r'\btoday is (' + '|'.join(DAY_NAMES) + r')\b', c.raw)
        if t:
            today = DAY_NAMES.index(t.group(1))
    if m:
        ref = {lemma(w) for w in re.findall(r'[a-z]+', m.group(2)) if w not in STOP and w not in ('day', 'come', 'comes')}
        for c in ctx.clauses:
            if ref & c.lemmas or any(synonyms(r) & c.lemmas for r in ref):
                d = [v for v in c.values if v[0] == 'day']
                if d:
                    base = d[-1][2]
                    shift = 1 if m.group(1) == 'after' else -1
                    return f'{DAY_NAMES[(base + shift) % 7].capitalize()} (the day {m.group(1)} {DAY_NAMES[base].capitalize()}).'
    if today is not None:
        focus = q.lemmas - {'weekday', 'day', 'get', 'come', 'arrive', 'here'}
        for c in ctx.clauses:
            n = re.search(r'\bin (\d+|' + '|'.join(k for k in NUMBER_WORDS if ' ' not in k) + r') days?\b', c.raw)
            if n and (not focus or focus & c.lemmas or any(synonyms(f) & c.lemmas for f in focus)):
                k = int(quantity(n.group(1)))
                return f'{DAY_NAMES[(today + k) % 7].capitalize()} (today is {DAY_NAMES[today].capitalize()}, plus {k} days).'
    return None


def op_available(ctx, q):
    """'Only Ingrid and Diego have a driving licence, Hugo doesn't' + 'Diego is away on Friday' -> who could drive me on Friday."""
    m = re.match(r"who (?:could|can|is able to|would be able to|might) (\w+)", q.low)
    if not m:
        return None
    verb = lemma(m.group(1))
    able, unable = [], set()
    for c in ctx.clauses:
        if verb in c.lemmas or synonyms(verb) & c.lemmas or (FIELD_OF.get(verb, set()) and any(FIELD_OF.get(l, set()) & FIELD_OF[verb] for l in c.lemmas)):
            names = [n.lower() for n in re.findall(r"\b([A-Z][a-z]+)\b", c.text) if n not in cm.NAME_STOP]
            neg = re.findall(r"\b([A-Z][a-z]+) (?:does not|doesn't|can't|cannot|can not|does n't|has no|hasn't|has not)\b", c.text)
            for n in names:
                if n not in {x.lower() for x in neg} and n not in able:
                    able.append(n)
            unable |= {x.lower() for x in neg}
    if not able:
        return None
    day = re.search(r'\b(' + '|'.join(DAY_NAMES) + r')\b', q.low)
    for c in ctx.clauses:
        if re.search(r'\b(?:away|busy|working|sick|out of town|abroad|unavailable|on holiday|travelling|traveling|can\'t|cannot|not free)\b', c.raw) and \
                (not day or day.group(1) in c.raw):
            for n in c.mentions:
                unable.add(n)
    left = [n for n in able if n not in unable]
    if not left:
        return 'Nobody: ' + ', '.join(n.title() for n in able) + ' can not.'
    return ' and '.join(n.title() for n in left) + (' (' + ', '.join(n.title() for n in able if n in unable) + ' is not available).' if any(n in unable for n in able) else '.')


def op_eliminate(ctx, q):
    """'My key is in one of three places: the top drawer, the middle drawer or the bottom drawer' + 'It's not in the top
    one' + 'I checked the middle one, nothing there' -> the bottom drawer."""
    if q.wh not in ('where', 'which', 'what', 'who') or not re.search(r'\b(?:must|has to|could|should|can|left)\b', q.low):
        return None
    options, focus = None, q.lemmas - {'must', 'place'}
    for c in ctx.clauses:
        m = re.search(r"\bone of (?:the |these |those |\w+ )?(?:\w+ )?(?:places|options|spots|rooms|drawers|boxes|bags|people|ones)?:?\s*(.+)$",
                      c.raw)
        if m and (not focus or focus & c.lemmas):
            parts = [re.sub(r"^(?:the|a|an|my) ", '', x.strip(' .')) for x in re.split(r",\s*(?:or\s+)?|\s+or\s+", m.group(1))]
            options = [x for x in parts if x]
    if not options or len(options) < 2:
        return None
    common = set.intersection(*[set(o.split()) for o in options])
    keys = {o: [w for w in o.split() if w not in common] or o.split() for o in options}
    left = list(options)
    out_cue = r"(?:\bnot\b|n't\b|\bnever\b|\bchecked\b|\bsearched\b|\blooked (?:in|under|behind)\b|\bnothing\b|\bempty\b|\bruled out\b)"
    for c in ctx.clauses:
        if not re.search(out_cue, c.raw):
            continue
        for opt in list(left):
            if all(re.search(r'\b' + re.escape(w) + r'\b', c.raw) for w in keys[opt]) and len(left) > 1:
                left.remove(opt)
    if len(left) == 1 and len(left) < len(options):
        return f'In the {left[0]} (the other options were ruled out).'
    return None


def op_rate(ctx, q):
    """'charges 2 euros for each day a book is overdue' + 'brought it back 4 days late' -> 8 euros."""
    if q.wh not in ('how much', 'what') or not re.search(r'\b(?:fine|owe|cost|pay|charge|fee|total|bill)\b', q.low):
        return None
    rate = unit = None
    for c in ctx.clauses:
        m = re.search(r"(\d+(?:\.\d+)?)\s*(" + CURRENCY + r")?\s*(?:for |per |a |an )(?:each |every )?(\w+)", c.raw)
        if m and re.search(r'\b(?:charge|cost|fee|fine|per|each|every)\w*', c.raw):
            rate, unit, money = float(m.group(1)), lemma(m.group(3)), m.group(2) or ''
            continue
        if rate is not None:
            n = re.search(r"\b(\d+|" + '|'.join(k for k in NUMBER_WORDS if ' ' not in k) + r") (\w+)", c.raw)
            if n and lemma(n.group(2)) == unit:
                total = rate * quantity(n.group(1))
                return f'{fmt(total)} {money}'.strip() + f' ({fmt(rate)} x {fmt(quantity(n.group(1)))} {unit}s).'
    return None


def op_relative(ctx, q):
    """'My sister Hana is 6 years older than me' + 'I'm 35' -> Hana is 41."""
    m = re.match(r"how (old|tall) (?:is|was|are) ([a-z]+)", q.low)
    if not m:
        return None
    who = m.group(2)
    if who in ('my',):
        return None
    _, ages = order_facts(ctx, 'old' if m.group(1) == 'old' else 'tall')
    user_age = None
    for c in ctx.clauses:
        a = re.match(r"^(?:i am|i'm|i turned|i just turned) (\d{1,3})\b(?! (?:minutes|hours|days|km|kg))", c.raw)
        if a:
            user_age = float(a.group(1))
    for c in ctx.clauses:
        if who not in c.mentions and c.subject != who:
            continue
        r = re.search(r"\b(\d+|" + '|'.join(k for k in NUMBER_WORDS if ' ' not in k) + r") (?:years?|cm|centimet\w+) (older|younger|taller|shorter) than (me|[a-z]+)", c.raw)
        if r:
            base = user_age if r.group(3) == 'me' else ages.get(r.group(3))
            if base is None:
                continue
            n = quantity(r.group(1))
            value = base + n if r.group(2) in ('older', 'taller') else base - n
            ref = 'you' if r.group(3) == 'me' else r.group(3).title()
            return f'{who.title()} is {fmt(value)} ({ref}: {fmt(base)}, {r.group(2)} by {fmt(n)}).'
    return None


def op_category_count(ctx, q):
    """'How many animals do we have altogether?' with '2 goldfish' + '4 ducks': sum counts of kinds of the asked category."""
    m = re.match(r"how many (\w+)", q.low)
    if not m or not re.search(r'\b(?:altogether|in total|total|combined|all together|overall)\b', q.low):
        return None
    category = lemma(m.group(1))
    total, parts = 0, []
    for c in ctx.clauses:
        if c.negated or 'unreal' in c.flags or 'question' in c.flags:
            continue
        for n, noun in re.findall(r"\b(\d+|" + '|'.join(k for k in NUMBER_WORDS if ' ' not in k) + r") ([a-z]+)", c.raw):
            base = lemma(noun)
            if base == category or category in cm.kinds(base, senses=2) or category in synonyms(base):
                total += quantity(n)
                parts.append(f'{n} {noun}')
    if len(parts) < 2:
        return None
    return f'{fmt(total)} ({" + ".join(parts)}).'



def money_values(c):
    return [v for v in c.values if v[0] in ('money', 'number') and not v[4:5] == ('',) or v[0] == 'money']


def op_budget(ctx, q):
    """'Am I still within budget?': the latest budget against everything said to be spent."""
    if not re.search(r'\b(?:within|over|under|above|below|inside|exceed\w*|blow\w*|stay\w*) (?:the |my |our )?budget\b|\bafford\b|'
                     r'\benough money\b|\bmoney left\b|\bleft (?:in|of) (?:the |my )?budget\b', q.low):
        return None
    budget, spent, parts = None, 0.0, []
    for c in ctx.clauses:
        nums = [v for v in c.values if v[0] in ('money', 'number')]
        if not nums or 'question' in c.flags:
            continue
        if re.search(r'\b(?:budget|limit|can spend|allowed to spend)\b', c.raw):
            budget = nums[-1][2]
        elif re.search(r'\b(?:spent|spend|paid|pay|cost|costs|bought|deposit|another|plus)\b', c.raw):
            spent += nums[0][2]
            parts.append(fmt(nums[0][2]))
    if budget is None or not parts:
        return None
    left = budget - spent
    verdict = 'Yes' if left >= 0 else 'No'
    return f'{verdict}: you have spent {fmt(spent)} ({" + ".join(parts)}) of a {fmt(budget)} budget, so {fmt(abs(left))} ' + \
        ('is left.' if left >= 0 else 'over.')


def op_changed(ctx, q):
    """'What changed about the budget?' -> from 600 to 1000."""
    m = re.search(r"\bwhat (?:changed|has changed|is different|was changed) (?:about|with|in|for) (?:the |my |our )?(.+)$", q.low) or \
        re.search(r"\bhow (?:did|has) (?:the |my |our )?(.+?) change\b", q.low)
    if not m:
        return None
    focus = {b for w in re.findall(r'[a-z]+', m.group(1)) if w not in STOP for b in bases(w)}
    values = []
    for c in ctx.clauses:
        if focus & c.lemmas or any(synonyms(f) & c.lemmas for f in focus):
            for v in c.values:
                if v[0] in ('money', 'number', 'day', 'date', 'time', 'colour', 'place') and (not values or values[-1][2] != v[2]):
                    values.append(v)
    if len(values) < 2:
        return None
    return f'It changed from {values[0][1]} to {values[-1][1]}' + (f' (via {", ".join(v[1] for v in values[1:-1])})' if len(values) > 2 else '') + '.'


LESS = {'cheaper': ('cost', -1), 'costs less': ('cost', -1), 'less expensive': ('cost', -1), 'more expensive': ('cost', 1),
        'costs more': ('cost', 1), 'pricier': ('cost', 1)}


def op_which_of(ctx, q):
    """'Which of the two sleeps all day?' with 'We got a puppy and a kitten' + 'He chews everything, she sleeps all day';
    'The latter is cheaper'; 'The second one was easily the best'."""
    if not re.search(r'\bwhich (?:of (?:the|those|these|them|my) (?:two|three|four|\w+)|one)\b|\bwhich \w+ did (?:i|we) (?:like|love|enjoy|prefer)\b', q.low):
        return None
    pair = None
    for c in ctx.clauses:
        m = re.search(r"(?:between |got |have |bought |read |saw |watched |visited |met |a |an |the )((?:(?:a|an|the|my) )?[\w ]+?)((?:, (?:(?:a|an|the|my) )?[\w ]+?)*),? (?:and|or) "
                      r"((?:a|an|the|my) )?([\w ]+?)(?:[.,;:!]|$| last| this| for| at| in)", c.raw)
        listed = re.search(r":\s*(.+)$", c.text)
        if listed and ',' in listed.group(1):
            pair = [x.strip(' .') for x in re.split(r",\s*(?:and\s+|or\s+)?|\s+and\s+|\s+or\s+", listed.group(1)) if x.strip(' .')]
        elif m:
            first = re.sub(r"^(?:a|an|the|my) ", '', m.group(1).strip()).split()[-1]
            middle = [re.sub(r"^(?:a|an|the|my) ", '', x.strip()).split()[-1] for x in m.group(2).split(',') if x.strip()]
            pair = [first] + middle + [m.group(4).split()[-1]]
    if not pair:
        return None
    focus = q.lemmas - {'two', 'three', 'one', 'which'}
    comp = next((v for k, v in LESS.items() if k in q.low), None)
    for c in reversed(ctx.clauses):
        raw = c.raw
        if comp and re.search(r'\b(?:cheaper|less expensive|costs? less|more expensive|pricier|costs? more)\b', raw):
            cheap = bool(re.search(r'\b(?:cheaper|less expensive|costs? less)\b', raw))
            pick = re.search(r'\bthe (former|latter|first|second)\b', raw)
            if pick:
                k = 0 if pick.group(1) in ('former', 'first') else -1
                if cheap != (comp[1] < 0):
                    k = -1 - k if len(pair) == 2 else k
                return f'The {pair[k]}.'
        if not (focus & c.lemmas or any(synonyms(f) & c.lemmas for f in focus)):
            continue
        for pos_word in (r'\bthe (former|latter|first one|second one|third one|last one)\b', r'\b(he|she)\b'):
            for m in re.finditer(pos_word, raw):
                tail = raw[m.end():m.end() + 60]
                head_part = re.split(r'[,;.]', tail)[0]
                words = {b for w in re.findall(r"[a-z']+", head_part) for b in bases(w)}
                if focus & words or any(synonyms(f) & words for f in focus) or re.search(r'\b(?:best|favourite|favorite|liked most|loved)\b', head_part):
                    word = m.group(1)
                    k = {'former': 0, 'first one': 0, 'he': 0, 'latter': -1, 'second one': 1, 'she': 1, 'third one': 2, 'last one': -1}[word]
                    if k < len(pair):
                        return f'{pair[k][0].upper() + pair[k][1:]}.'
    return None


def op_one_other(ctx, q):
    """'I carry two keys. One opens the office, the other opens the studio.' -> 'What does the second key open?'."""
    m = re.search(r"\bthe (first|second|other|1st|2nd) (\w+)", q.low)
    if not m:
        return None
    k = 0 if m.group(1) in ('first', '1st') else 1
    for c in ctx.clauses:
        pair = re.search(r"\b(?:one|the first(?: one)?) (\w+) (?:the |a |my )?([\w ]+?),? (?:and |while |but )?the (?:other|second)(?: one)? (\w+) (?:the |a |my )?([\w ]+?)[.!]?$", c.raw)
        if pair:
            verb = lemma(pair.group(1))
            if q.verb and q.verb not in (verb, lemma(pair.group(3))) and not (synonyms(q.verb) & {verb}):
                continue
            answer = pair.group(2) if k == 0 else pair.group(4)
            return answer[0].upper() + answer[1:] + '.'
    return None

OPERATIONS = (op_one_other, op_which_of, op_budget, op_changed, op_remaining, op_category_count, op_relative, op_weekday, op_available, op_eliminate, op_rate, op_ordinal, op_superlative, op_same, op_count, op_sum, op_time, op_rule, op_same_day, op_yesno_compare)


# ---------------------------------------------------------------- entry point

RECALL = re.compile(r"^(?:what|which|who|whom|whose|where|when|how many|how much|how old|how long|is|are|was|were|did|does|do|"
                    r"has|have|can|could|will|would)\b", re.I)
ADVICE = re.compile(r"\b(?:should i|shall i|how (?:do|can|could|should) (?:i|we|you)|how to|can you|could you|would you|"
                    r"where (?:can|could|should|do) (?:i|we) (?:find|buy|get|go|eat|stay)|find a|good place|"
                    r"recommend|suggest|ideas?|tips?|any advice|what if|why|explain|tell me (?:a|about)|write|give me|"
                    r"help me|what's the best|what is the best|best way|meaning of|define|translate|calculate)\b", re.I)


def personal(ctx, q):
    """A question about something the user would have told CAEL earlier (so 'not mentioned' is the honest answer)."""
    if not RECALL.match(q.low) or ADVICE.search(q.low):
        return False
    if q.subjects - {'user'}:
        return True
    if q.anchors and re.search(r'\b(?:the|my|our)\b', q.low) and any(q.anchors <= c.lemmas for c in ctx.clauses):
        return True                                  # 'the hiking group' was talked about, but not what is asked
    return bool(re.search(r"\b(?:my|our|me|us)\b|\b(?:did|do|am|was|have|will|can|could|would|should|are|were) (?:i|we)\b", q.low))


def about_conversation(ctx, q):
    """Is the question about this chat? It names someone from it, is personal ('my', 'we', 'me'), or refers back to
    something introduced in it ('the hiking group', 'those five people', 'the second one')."""
    if re.search(r"\bmy name\b|\byour name\b", q.low):
        return False                                 # names are handled with greetings (memory.py)
    if q.subjects - {'user'}:
        return True
    if re.search(r"\b(?:my|our|me|us)\b|\b(?:did|do|does|am|was|have|has|will|can|could|would|should|are|were|had) (?:i|we)\b|\b(?:i|we|mine|ours)\b", q.low):
        return True
    if re.search(r"\b(?:those|these|them|the two|the three|the latter|the former|the first one|the second one|the other one|"
                 r"that one|this one|of them|which one)\b", q.low):
        return True
    for m in re.finditer(r"\b(?:the|that|this) ((?:[a-z-]+ ){0,2}[a-z-]+)", q.low):
        words = [lemma(w) for w in m.group(1).split() if w not in STOP]
        if words and any(w in ctx.vocabulary for w in words if is_noun(w) and w not in ANSWER_NOUNS):
            return True
    return False


def describe(q):
    words = [w for w in re.findall(r"[a-z']+", q.low) if w not in STOP and w not in ('colour', 'color')]
    return ' '.join(words[-4:]) if words else 'that'


def answer(messages):
    """dict(response=..., route='chat/context-reasoning', confidence=...) or None to let other routes answer."""
    if not messages or messages[-1].get('role') != 'user':
        return None
    history = messages[:-1]
    if sum(1 for m in history if m.get('role') == 'user') < 2:
        return None
    ctx = Context(history)
    q = Question(ctx, messages[-1]['content'])
    if not q.wh or q.stranger:
        return None
    present = {a for a in q.anchors if a in ctx.vocabulary or any(matches(ctx, a, c.lemmas) for c in ctx.clauses)}
    if q.anchors and not present and not personal(ctx, q):
        return None                                  # about something never discussed here: a general question
    out = lambda text, confidence: dict(response=text, route='chat/context-reasoning', confidence=confidence, sources=[], details=DETAILS)
    for op in OPERATIONS:
        try:
            result = op(ctx, q)
        except Exception:
            result = None
        if result:
            answer_ = out(result, 0.7)
            answer_['operation'] = op.__name__
            return answer_
    if not about_conversation(ctx, q):
        return None                                  # a general question ('Where do penguins live?') for other routes
    if q.expect == 'yesno':
        return None if not personal(ctx, q) else out(f"I'm not sure: you didn't mention anything that settles that ({describe(q)}).", 0.3)
    decision = decide(ctx, q, retrieve(ctx, q))
    if decision and decision.get('conflict'):
        parts = decision['conflict']
        if any(p[1].source for p in parts):
            said = '; '.join(f"{(p[1].source or 'you').capitalize()} said {say(p[2])}" for p in parts)
            result = out(f'I have conflicting information: {said}. They disagree, so I am not sure which is right. Can you check?', 0.6)
            result['conflict'] = True
            return result
        options = ' or '.join(say(p[2]) for p in parts)
        result = out(f'You told me two different things: {options}. Which one is right?', 0.6)
        result['conflict'] = True
        return result
    if decision:
        value = say(decision['value'])
        updated = bool(decision.get('history'))
        text = value[0].upper() + value[1:] if q.expect in ('thing',) else value
        note = ''
        if decision.get('history'):
            note = ' (Before that: ' + ', '.join(say(h) for h in decision['history']) + '.)'
        if decision.get('note'):
            note = ' ' + decision['note']
        result = out(f'{text}.{note}', min(0.95, decision['score'] / 6))
        result['update'] = updated
        return result
    if personal(ctx, q) or about_conversation(ctx, q) and RECALL.match(q.low) and not ADVICE.search(q.low):
        result = out(f"I don't know: you didn't mention {describe(q)} in this chat.", 0.2)
        # evidence for abstaining: the thing asked about was talked about, and no clause about it holds the asked value
        result['abstain'] = bool(q.anchors) and any(q.anchors <= c.lemmas for c in ctx.clauses)
        return result
    return None
