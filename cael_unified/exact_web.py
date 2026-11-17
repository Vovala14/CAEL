"""Exact answers from the internet, through documented public APIs only (no search-engine scraping, no key).

Three researchers, each returning one finding or None:

1. `wikidata`  A question that names a thing and one of its properties ("What's the capital of Australia?", "Who wrote
               Dracula?", "When was Marie Curie born?", "How tall is the Eiffel Tower?") is answered from the statement
               stored in Wikidata (CC0): the entity is looked up by name, the statement read, and the value given with its
               unit or as a date. The answer is the stored value itself, not a passage that happens to mention it.
2. `sentence`  Any other fact question ("Which planet has the most moons?", "How many bones are in the human body?") is
               searched on Wikipedia in two wordings; the pages are read and every sentence scored by how much of the
               question it covers. The answer must be of the kind asked for (a name for "who", a year for "when", a number
               next to the counted noun for "how many", a planet for "which planet"), and the value most well-matching
               sentences agree on is given in bold with the sentence that states it.
3. `summary`   "What is X?", "Who was X?", "Tell me about X": the opening sentences of the encyclopedia article on X.

A follow-up ("And which one is the hottest?", "When was he born?") is first made into a full question from the turn
before (`standalone`). Page text is data: it is scored and quoted, never followed. No neural model.
"""
import datetime
import html
import os
import re
from urllib.parse import urlencode, quote

from . import web_check as wc
from .network import NETWORK, LookupUnavailable

WIKI = 'en.wikipedia.org'
DATA = 'www.wikidata.org'
MONTHS = 'January February March April May June July August September October November December'.split()

# ----------------------------------------------------------------------------------------------------------------------
# follow-ups

Q_HEAD = re.compile(r"(?i)\b(?:which|what)\s+((?:[a-z]+\s+){0,2}?[a-z]+?)\s+(?:has|have|had|is|are|was|were|do|does|did|can|will|would|"
                    r"should|in|on|of|comes?|came|lives?|makes?|made|won|wins)\b")
LEAD_IN = re.compile(r"(?i)^\s*(?:and|so|ok(?:ay)?|but|then|also|oh|cool|nice|great|interesting|thanks|thank you|got it|right|wow|hm+)\b[,.!\s]*")


def last_question(text):
    parts = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]
    asked = [s for s in parts if s.endswith('?')]
    return asked[-1] if asked else (parts[-1] if parts else text)


def bold_answer(reply):
    hit = re.search(r'\*\*([^*\n]{2,60})\*\*', reply or '')
    return hit[1].strip(' .') if hit else None


def standalone(messages):
    """The last question as it would be asked on its own, using the question before it and CAEL's answer to that."""
    turns = wc.user_turns(messages)
    q = last_question(turns[-1])
    while LEAD_IN.match(q) and len(LEAD_IN.sub('', q, count=1).split()) >= 2:
        q = LEAD_IN.sub('', q, count=1)
    q = q[:1].upper() + q[1:]
    if len(turns) < 2:
        return q
    prev_q = last_question(turns[-2])
    prev_a = next((m.get('content') or '' for m in reversed(messages[:-1]) if m.get('role') == 'assistant'), '')
    if re.search(r'(?i)\b(?:which|what) ones?\b', q):
        # the kind of thing asked about before: "Which planet has ...", "What is the largest planet ..."
        for earlier in reversed(turns[:-1][-3:]):
            eq = last_question(earlier)
            head = Q_HEAD.search(eq)
            noun = head[1].strip() if head else None
            if not noun:
                sup = re.search(r"(?i)\b(?:[a-z]{3,}est|most [a-z]+|least [a-z]+|first|last) ([a-z]+)\b", eq)
                noun = sup[1] if sup and sup[1].lower() not in wc.STOP else None
            if noun:
                return re.sub(r'(?i)\b(which|what) ones?\b', lambda m: f'{m[1]} {noun}', q, count=1)
    named = bold_answer(prev_a)
    obj = re.match(r"(?i)\s*who (?:wrote|painted|directed|composed|invented|discovered|designed|built|founded|created|sang|made) (?:the )?(.+?)\s*\??\s*$", prev_q)
    if obj and re.search(r'(?i)\b(?:it|its)\b', q) and not re.search(r'(?i)\b(?:he|she|him|her|his)\b', q):
        return re.sub(r'(?i)\bit\b', obj[1], q, count=1) if re.search(r'(?i)\bit\b', q) else re.sub(r'(?i)\bits\b', obj[1] + "'s", q, count=1)
    if named and re.search(r'(?i)\b(?:he|she|him|her|his|they|them|their|it|its|there)\b', q) and not re.search(r'\d', named):
        if re.search(r'(?i)\b(?:live|lives|living|people|population|weather|climate|far|located)\b.*\bthere\b', q):
            return re.sub(r'(?i)\bthere\b', 'in ' + named, q, count=1)
        swapped = re.sub(r'(?i)\b(?:he|she|they|it|him|them)\b', named, q, count=1)
        if swapped == q:
            swapped = re.sub(r'(?i)\b(?:his|her|their|its)\b', named + "'s", q, count=1)
        return swapped
    about = ABOUT.match(prev_q.strip())
    if about and re.search(r'(?i)\b(?:it|they|them|those|these)\b', q) and len(about[1].split()) <= 4:
        thing = about[1].strip(' .?!')
        plural = thing.endswith('s') and not thing.endswith('ss')
        if re.search(r'(?i)\bthey\b', q):
            return re.sub(r'(?i)\bthey\b', 'the ' + thing, q, count=1)
        return re.sub(r'(?i)\b(?:it|them|those|these)\b', ('the ' if plural else 'the ') + thing, q, count=1)
    if re.search(r'(?i)\b(?:it|they|them|those|these)\b', q) and len(q.split()) <= 12:
        # no named answer to point back to: what the question before was about ("how a microwave oven heats food" -> "microwave oven")
        try:
            subject = wc.query([m for m in messages[:-1]][:-1] if messages[-2:-1] and messages[-2].get('role') == 'assistant' else messages[:-1])[5]
        except Exception:
            subject = None
        if subject and not {wc.stem(w) for w in wc.content(subject)} <= {wc.stem(w) for w in wc.content(q)}:
            article = 'an ' if subject[:1] in 'aeiou' else 'a '
            swapped = re.sub(r'(?i)\b(?:it|them|those|these)\b', article + subject, q, count=1)
            return swapped if swapped != q else re.sub(r'(?i)\bthey\b', subject + 's', q, count=1)
    return q


# ----------------------------------------------------------------------------------------------------------------------
# 1. Wikidata statements

def wd(**params):
    return NETWORK.json(f'https://{DATA}/w/api.php?' + urlencode(dict(params, format='json')), ttl=86400, timeout=8)


X = r"(.+?)"
END = r"\s*\??\s*$"
RELATIONS = [
    # (pattern with one group for the thing, properties tried in order, sentence with {x} and {v})
    (rf"what(?:'s| is| was) the capital(?: city)? of {X}{END}", ['P36'], 'The capital of {x} is **{v}**.'),
    (rf"what(?:'s| is) the currency (?:of|in|used in) {X}{END}", ['P38'], 'The currency of {x} is the **{v}**.'),
    (rf"what currency (?:does|do) {X} use{END}", ['P38'], 'The currency of {x} is the **{v}**.'),
    (rf"(?:what(?:'s| is) the population of|how many people live in) {X}{END}", ['P1082'], '{x} has a population of about **{v}**{when}.'),
    (rf"what(?:'s| is| are) the official languages? (?:of|in) {X}{END}", ['P37'], 'The official language of {x}: **{v}**.'),
    (rf"what languages? (?:do they|do people|is|are) (?:speak|spoken) in {X}{END}", ['P37'], 'The official language of {x}: **{v}**.'),
    (rf"who (?:wrote|is the author of|was the author of|authored) {X}{END}", ['P50', 'P58'], '{x} was written by **{v}**.'),
    (rf"who (?:painted|drew|sculpted) {X}{END}", ['P170'], '{x} was made by **{v}**.'),
    (rf"who (?:directed|is the director of|was the director of) {X}{END}", ['P57'], '{x} was directed by **{v}**.'),
    (rf"who (?:composed|wrote the music for) {X}{END}", ['P86'], '{x} was composed by **{v}**.'),
    (rf"who (?:invented|discovered|developed) {X}{END}", ['P61'], '{x}: discovered or invented by **{v}**.'),
    (rf"who (?:founded|started|established|created|is the founder of|was the founder of) {X}{END}", ['P112', 'P170', 'P178'], '{x} was founded or created by **{v}**.'),
    (rf"who (?:designed|built|was the architect of|is the architect of) {X}{END}", ['P84', 'P287', 'P193'], '{x} was designed by **{v}**.'),
    (rf"who (?:is|was) {X}(?:'s|’s) (?:wife|husband|spouse|partner){END}", ['P26'], "{x}'s spouse: **{v}**."),
    (rf"who (?:is|was) {X} married to{END}", ['P26'], "{x}'s spouse: **{v}**."),
    (rf"who (?:is|was) the (?:president|king|queen|monarch|head of state|emperor) of {X}{END}", ['P35'], 'The head of state of {x} is **{v}**.'),
    (rf"who (?:is|was) the (?:prime minister|chancellor|premier|head of government|mayor) of {X}{END}", ['P6'], 'The head of government of {x} is **{v}**.'),
    (rf"who (?:is|was) the (?:ceo|chief executive|boss|head) of {X}{END}", ['P169'], 'The chief executive of {x} is **{v}**.'),
    (rf"when was {X} born{END}", ['P569'], '{x} was born on **{v}**.'),
    (rf"(?:when did {X} die|when was {X} killed){END}", ['P570'], '{x} died on **{v}**.'),
    (rf"where was {X} born{END}", ['P19'], '{x} was born in **{v}**.'),
    (rf"where did {X} die{END}", ['P20'], '{x} died in **{v}**.'),
    (rf"how old (?:is|was) {X}{END}", ['P569'], None),
    (rf"when was {X} (?:founded|established|formed|created|set up|started|opened|invented|discovered|first made)"
     rf"{END}", ['P571', 'P575', 'P1619', 'P580'], '{x}: **{v}**.'),
    (rf"(?:when|(?:in )?(?:what|which) year) (?:was|did|were) {X} (?:released|published|come out|first (?:released|published)|premiere[d]?|written){END}",
     ['P577', 'P571'], '{x} was first published in **{v}**.'),
    (rf"(?:what|which) year was {X} born{END}", ['P569'], '{x} was born on **{v}**.'),
    (rf"(?:when|(?:in )?(?:what|which) year) (?:was|were) {X} (?:built|completed|finished|constructed){END}", ['P1619', 'P571'], '{x} was completed in **{v}**.'),
    (rf"(?:what|which) year (?:was|were) {X} (?:founded|established|opened|invented|discovered){END}", ['P571', 'P575', 'P1619'], '{x}: **{v}**.'),
    (rf"(?:what|which) year did {X} (?:die|end|start|begin){END}", ['P570', 'P582', 'P580'], '{x}: **{v}**.'),
    (rf"how (?:tall|high) is {X}{END}", ['P2048', 'P2044'], '{x} is **{v}** tall.'),
    (rf"how long is {X}{END}", ['P2043'], '{x} is **{v}** long.'),
    (rf"how deep is {X}{END}", ['P4511'], '{x} is up to **{v}** deep.'),
    (rf"how (?:big|large) is {X}{END}", ['P2046'], '{x} covers **{v}**.'),
    (rf"what(?:'s| is) the area of {X}{END}", ['P2046'], '{x} covers **{v}**.'),
    (rf"(?:what|which) country is {X} in{END}", ['P17'], '{x} is in **{v}**.'),
    (rf"(?:what|which) continent is {X} (?:in|on|part of){END}", ['P30'], '{x} is in **{v}**.'),
    (rf"where is {X}(?: located| situated)?{END}", ['P131', 'P17', 'P30'], '{x} is in **{v}**.'),
    (rf"what(?:'s| is) the (?:chemical )?symbol (?:for|of) {X}{END}", ['P246'], 'The chemical symbol for {x} is **{v}**.'),
    (rf"what(?:'s| is) the atomic number of {X}{END}", ['P1086'], 'The atomic number of {x} is **{v}**.'),
    (rf"what(?:'s| is) the (?:highest|tallest) (?:point|mountain|peak) (?:in|of) {X}{END}", ['P610'], 'The highest point of {x} is **{v}**.'),
    (rf"what(?:'s| is) the (?:boiling point) of {X}{END}", ['P2102'], '{x} boils at **{v}**.'),
    (rf"what(?:'s| is) the (?:melting point) of {X}{END}", ['P2101'], '{x} melts at **{v}**.'),
    (rf"what(?:'s| is| are) the (?:scientific|latin|botanical|binomial|taxonomic) names? (?:of|for) {X}{END}", ['P225'], 'The scientific name of {x} is ***{v}***.'),
    (rf"what(?:'s| is| are) {X}(?:'s|’s|s') (?:scientific|latin|botanical|binomial|taxonomic) names?{END}", ['P225'], 'The scientific name of {x} is ***{v}***.'),
    (rf"what(?:'s| is| are) {X} called in latin{END}", ['P225'], 'The scientific name of {x} is ***{v}***.'),
]
RELATIONS = [(re.compile('(?i)^' + p), props, say) for p, props, say in RELATIONS]
UNITS = {'metre': 'm', 'kilometre': 'km', 'square kilometre': 'km²', 'centimetre': 'cm', 'foot': 'ft', 'kilogram': 'kg', 'degree Celsius': '°C',
         'degree Fahrenheit': '°F', 'kelvin': 'K', 'mile': 'miles', 'square metre': 'm²', 'hectare': 'hectares', 'gram': 'g'}


def number(amount):
    value = float(amount)
    if value == int(value):
        return f'{int(value):,}'
    return f'{value:,.2f}'.rstrip('0').rstrip('.')


def date_text(value):
    """'+1867-11-07T00:00:00Z' with its precision -> '7 November 1867' / 'November 1867' / '1867'."""
    m = re.match(r'([+-])(\d+)-(\d\d)-(\d\d)', value['time'])
    if not m:
        return None
    year, month, day, precision = int(m[2]), int(m[3]), int(m[4]), value.get('precision', 9)
    era = ' BC' if m[1] == '-' else ''
    if precision >= 11 and month and day:
        return f'{day} {MONTHS[month - 1]} {year}{era}'
    if precision == 10 and month:
        return f'{MONTHS[month - 1]} {year}{era}'
    if precision == 9:
        return f'{year}{era}'
    if precision == 8:
        return f'the {year // 10 * 10}s{era}'
    if precision == 7:
        return f'the {(year - 1) // 100 + 1}th century{era}'
    return f'{year}{era}'


def labels(ids):
    ids = [i for i in dict.fromkeys(ids) if i]
    if not ids:
        return {}
    got = wd(action='wbgetentities', ids='|'.join(ids[:40]), props='labels', languages='en')
    return {k: v.get('labels', {}).get('en', {}).get('value') for k, v in got.get('entities', {}).items()}


def statement(entity, prop):
    """The current value(s) of a property: preferred rank first, then the latest dated one, else all normal ones."""
    claims = [c for c in entity.get('claims', {}).get(prop, []) if c.get('rank') != 'deprecated' and c.get('mainsnak', {}).get('snaktype') == 'value']
    if not claims:
        return []
    preferred = [c for c in claims if c.get('rank') == 'preferred']
    if preferred:
        return preferred
    ended = lambda c: bool(c.get('qualifiers', {}).get('P582'))
    current = [c for c in claims if not ended(c)] or claims

    def stamp(c):
        for q in ('P585', 'P580'):
            for s in c.get('qualifiers', {}).get(q, []):
                if s.get('snaktype') == 'value':
                    return s['datavalue']['value']['time'].lstrip('+')
        return ''
    dated = [c for c in current if stamp(c)]
    if dated and prop in ('P1082', 'P35', 'P6', 'P169', 'P2046', 'P36', 'P38'):
        return [max(dated, key=stamp)]
    return current


def render(claims):
    """(text, year of the statement or None) for a list of claims of one property."""
    values, units, items, when = [], [], [], None
    for c in claims[:6]:
        v = c['mainsnak']['datavalue']
        if v['type'] == 'wikibase-entityid':
            items.append(v['value']['id'])
        elif v['type'] == 'time':
            values.append(date_text(v['value']))
        elif v['type'] == 'quantity':
            unit = v['value'].get('unit', '1').rsplit('/', 1)[-1]
            values.append((number(v['value']['amount']), unit if unit.startswith('Q') else None))
            units.append(unit if unit.startswith('Q') else None)
            for s in c.get('qualifiers', {}).get('P585', []):
                if s.get('snaktype') == 'value':
                    when = s['datavalue']['value']['time'][1:5]
        elif v['type'] in ('string', 'monolingualtext'):
            values.append(v['value'] if isinstance(v['value'], str) else v['value'].get('text'))
    if items:
        names = labels(items)
        values = [names[i] for i in items if names.get(i)]
    elif units:
        names = labels(units)
        values = [f"{n} {UNITS.get(names.get(u), names.get(u))}".strip() if u else n for n, u in values[:1]]
    values = [v for v in dict.fromkeys(values) if v]
    if not values:
        return None, None
    return wc.join_names(values[:4]), when


def wikidata(question):
    q = re.sub(r'\s+', ' ', question.strip())
    for pattern, props, say in RELATIONS:
        m = pattern.match(q)
        if not m:
            continue
        thing = next((g for g in m.groups() if g), '').strip(' ?.')
        thing = re.sub(r'(?i)^(?:the (?:film|movie|book|novel|play|song|painting|city|country|company|river|mountain) )', '', thing)
        if not thing or len(thing.split()) > 7 or re.search(r'(?i)\b(?:my|your|our|i|you|me)\b', thing):
            return None
        found = wd(action='wbsearchentities', search=re.sub(r'(?i)^the ', '', thing), language='en', uselang='en', type='item', limit=8).get('search', [])
        if not found:
            return None
        got = wd(action='wbgetentities', ids='|'.join(f['id'] for f in found), props='claims|labels|sitelinks', languages='en', sitefilter='enwiki')
        for prop, f in [(prop, f) for prop in props for f in found]:
            if True:
                entity = got.get('entities', {}).get(f['id'], {})
                if 'enwiki' not in entity.get('sitelinks', {}):
                    continue                    # things without an encyclopedia article are rarely what is being asked about
                label = entity.get('labels', {}).get('en', {}).get('value') or thing
                claims = statement(entity, prop)
                if not claims:
                    continue
                if prop == 'P61' and len(claims) > 1:
                    # several claimants: name the one the encyclopedia article mentions most, and list the others
                    people = labels([c['mainsnak']['datavalue']['value']['id'] for c in claims if c['mainsnak']['datavalue']['type'] == 'wikibase-entityid'])
                    page = wc.page_text(WIKI, entity.get('sitelinks', {}).get('enwiki', {}).get('title') or label)
                    counts = sorted(((len(re.findall(r'\b' + re.escape(n.split()[-1]) + r'\b', page[1] if page else '')), n) for n in people.values() if n), reverse=True)
                    if len(counts) < 2 or counts[0][0] < 2 * max(1, counts[1][0]):
                        return None
                    url = f'https://www.wikidata.org/wiki/{f["id"]}'
                    rest = wc.join_names([n for _, n in counts[1:4]])
                    return dict(route='chat/web-exact', answer=counts[0][1], confidence=0.85,
                                response=f'**{counts[0][1]}** is the name most associated with it. {label[:1].upper() + label[1:]} has more than one claimant: '
                                         f'{rest} also worked on it.\n\nSource: Wikidata, "{label}" ({url}), and the Wikipedia article on it.',
                                sources=[dict(source='Wikidata', title=label, url=url, licence='CC0')],
                                details=f'Wikidata statement P61 of {f["id"]} lists {len(counts)} people; the Wikipedia article names {counts[0][1]} most often.')
                value, when = render(claims)
                if not value:
                    continue
                if re.search(r'(?i)\b(?:what|which) year\b|\bin what year\b', q) or (say and 'in **{v}**' in say):
                    yr = re.search(r'\b(\d{3,4})(?: BC)?$', value)
                    if yr:
                        value = yr[0]           # "what year": the year, not a placeholder 1 January
                if say is None:             # how old
                    born = claims[0]['mainsnak']['datavalue']['value']
                    died = statement(entity, 'P570')
                    y, mth, d = int(born['time'][1:5]), int(born['time'][6:8]) or 1, int(born['time'][9:11]) or 1
                    if died:
                        e = died[0]['mainsnak']['datavalue']['value']
                        ey, em, ed = int(e['time'][1:5]), int(e['time'][6:8]) or 1, int(e['time'][9:11]) or 1
                        age = ey - y - ((em, ed) < (mth, d))
                        text = f'{label} was born on {value} and died on {date_text(e)}, aged **{age}**.'
                    else:
                        now = datetime.date.today()
                        age = now.year - y - ((now.month, now.day) < (mth, d))
                        if age > 122:
                            return None
                        text = f'{label} was born on {value}, so {label} is **{age}** years old.'
                else:
                    if prop == 'P225' and label.lower() == value.lower():
                        label = thing               # "The scientific name of clover is Trifolium", not "of Trifolium"
                    text = say.format(x=label[:1].upper() + label[1:] if say.startswith('{x}') else label, v=value,
                                      when=f' ({when} figure)' if when else '')
                url = f'https://www.wikidata.org/wiki/{f["id"]}'
                return dict(route='chat/web-exact', response=f'{text}\n\nSource: Wikidata, "{label}" ({url}).', answer=value, confidence=0.95,
                            sources=[dict(source='Wikidata', title=label, url=url, licence='CC0')],
                            details=f'Wikidata statement {prop} of {f["id"]} ("{label}"), read through the Wikidata API.')
        return None
    return None


# ----------------------------------------------------------------------------------------------------------------------
# 2. Wikipedia sentences

TYPES = {
    'planet': 'Mercury Venus Earth Mars Jupiter Saturn Uranus Neptune'.split(),
    'continent': ['Africa', 'Antarctica', 'Asia', 'Europe', 'North America', 'South America', 'Australia', 'Oceania'],
    'ocean': ['Pacific Ocean', 'Atlantic Ocean', 'Indian Ocean', 'Arctic Ocean', 'Southern Ocean'],
    'month': MONTHS,
    'day': 'Monday Tuesday Wednesday Thursday Friday Saturday Sunday'.split(),
}
SPECIAL = re.compile(r"(?i)\b([a-z]{3,}est|most|least|first|last|only)\b")
NOT_SPECIAL = {'west', 'east', 'rest', 'best', 'test', 'forest', 'interest', 'request', 'suggest', 'honest', 'nest', 'guest', 'latest', 'chest', 'harvest'}
KEEP = {'end', 'ended', 'start', 'started', 'began', 'begin', 'die', 'died', 'born', 'won', 'win', 'made', 'built', 'founded', 'invented'}
ENDS = re.compile(r'\b(?:end|finish|die|death|close|stop|last|fall|fell|collaps\w*|abolish\w*|dissolv\w*)\b')
NUM = r'(?:\d[\d,]*(?:\.\d+)?(?:\s(?:million|billion|trillion|thousand))?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)'
PERSON = re.compile(r"\b((?:[A-Z][a-z'’-]+|[A-Z]\.)(?:\s+(?:[A-Z][a-z'’-]+|[A-Z]\.|de|da|van|von|di|del|le|la|bin|ibn)){1,3})\b")
NAME = re.compile(r"\b([A-Z][\w'’-]+(?:\s+(?:of|the|de|del|da)\s+[A-Z][\w'’-]+|\s+[A-Z][\w'’-]+){0,3})\b")
NOT_NAME = set('The This That These Those It Its He She They His Her Their In On At As By For From With And But Or If When While Although However '
               'Since After Before During Because A An Some Many Most Other Others Another There Here Today Both Each All One Two Three Solar System '
               'According Despite Like Unlike Under Over Until Its'.split())
UNIT = {
    'speed': r'(?:km/h|km/s|m/s|mph|m⋅s−1|(?:kilomet(?:re|er)s?|met(?:re|er)s?|miles) per (?:second|hour)|knots)',
    'area': r'(?:km2|km²|square (?:kilomet(?:re|er)s?|miles|met(?:re|er)s?)|sq\.? mi|hectares|acres)',
    'length': r'(?:km|kilomet(?:re|er)s?|miles?|mi|met(?:re|er)s?|m|feet|foot|ft|cm|centimet(?:re|er)s?|mm|inches|light[- ]years?|AU|astronomical units?)',
    'time': r'(?:years?|days?|hours?|minutes?|seconds?|months?|weeks?|decades?|centuries|milliseconds?)',
    'mass': r'(?:kg|kilograms?|tonnes?|tons?|pounds?|lbs?|grams?|ounces?)',
    'temperature': r'(?:°\s?[CF]|K|degrees?(?: Celsius| Fahrenheit)?|kelvins?)',
}
UNIT['size'] = UNIT['area'] + '|' + UNIT['length']
UNIT['any'] = '|'.join(UNIT[k] for k in ('speed', 'area', 'length', 'time', 'mass', 'temperature')) + '|%|percent'
MEASURES = [
    (r'\bhow far\b|\bdistance\b', 'length', r'distance|away|apart|far|from'),
    (r'\bhow (?:tall|high)\b|\bheight\b', 'length', r'tall|height|high|elevation|rises|stands'),
    (r'\bhow long (?:does|did|do|will|would|has|have|can)\b|\bduration\b|\bhow long is (?:a|an|the) (?:day|year|flight|trip|journey|season|game|match|pregnancy)\b', 'time', r''),
    (r'\bhow long\b|\blength\b', 'length', r'long|length'),
    (r'\bhow deep\b|\bdepth\b', 'length', r'deep|depth'),
    (r'\bhow (?:big|large|wide)\b|\b(?:diameter|size|width|radius|circumference|area)\b', 'size', r'diameter|size|area|wide|width|covers|radius|large|across'),
    (r'\bhow (?:heavy|much (?:does|do) .* weigh)\b|\b(?:weight|mass)\b', 'mass', r'weigh|mass|heavy'),
    (r'\bhow (?:hot|cold|warm)\b|\b(?:temperature|boiling point|melting point|freezing point)\b', 'temperature', r'temperature|hot|cold|boil|melt|freez|°'),
    (r'\bhow fast\b|\bspeed\b', 'speed', r'speed|fast|velocity|travel|reach'),
    (r'\bhow old\b|\b(?:age|lifespan|life expectancy)\b|\bhow long (?:do|does|can) .* live\b', 'time', r'old|age|live|lifespan|life|ago'),
]


def asks(question):
    """(kind, type word, counted noun, unit class, cue) of a fact question; kind None when this researcher does not take it."""
    low = re.sub(r"^\s*(?:and |so )?(?:roughly|approximately|about|around)\s+(?=how\b)", '', question.lower().strip())
    none = (None, None, None, None, None)
    if re.search(r"\b(?:i|my|me|we|our|you|your)\b", low) or re.match(r'\s*(?:why|should|can|could|would|is|are|does|do|did|was|were|will|has|have)\b', low):
        return none
    if re.match(r"\s*(?:what|which) (?:kind|type|sort|brand) of\b.*\b(?:best|good|better|should|recommend)", low) or re.search(r"\bis (?:the )?best\b.*\bfor (?:me|my|us)\b", low):
        return none                                 # a recommendation, not a fact
    if re.match(r"\s*what (?:causes|makes|happens|is the (?:reason|cause))\b", low):
        return none                                 # an explanation, answered from the article itself (summary)
    m = re.match(r"\s*how many ([a-z]+(?: [a-z]+)?)\b", low)
    if m:
        noun = m[1].split()
        counted = noun[0] if len(noun) == 1 or noun[1] in ('are', 'is', 'do', 'does', 'did', 'were', 'have', 'has', 'in', 'on', 'can', 'make', 'live') \
            or noun[0] in ('people', 'persons', 'speakers', 'users', 'students', 'children', 'adults', 'players', 'members', 'countries') else noun[1]
        return 'count', None, counted, None, None
    if re.match(r"\s*how (?:much|long|tall|high|far|big|large|old|deep|heavy|fast|hot|cold|warm|wide)\b", low) or re.match(
            r"\s*what(?:'s| is| was) the (?:average |mean |maximum |top |total |approximate )?(?:speed|distance|height|length|temperature|size|weight|mass|age|"
            r"diameter|depth|width|radius|circumference|duration|lifespan|life expectancy|boiling point|melting point|freezing point)\b", low):
        for pattern, unit, cue in MEASURES:
            if re.search(pattern, low):
                return 'measure', None, None, unit, cue
        return 'measure', None, None, 'any', ''
    if re.match(r"\s*who\b", low):
        return 'who', None, None, None, None
    if re.match(r"\s*(?:when\b|(?:in )?(?:what|which) year\b)", low):
        return 'when', None, None, None, None
    if re.match(r"\s*where\b", low):
        return 'where', None, None, None, None
    if re.match(r"\s*(?:which|what)\b", low):
        for w in re.findall(r'[a-z]+', low):
            if w in TYPES or w.rstrip('s') in TYPES:
                return 'which', w if w in TYPES else w.rstrip('s'), None, None, None
        if re.match(r"\s*what(?:'s| is| are| was| were) (?:a|an)\b|\s*what does\b|\s*what do\b", low):
            return none                             # a definition or an explanation, not a name
        if any(w.lower() not in NOT_SPECIAL for w in SPECIAL.findall(low)) or re.match(
                r"\s*(?:which|what) (?!is\b|are\b|was\b|were\b|does\b|do\b|did\b|if\b|about\b|would\b|should\b|can\b)[a-z]+ [a-z]+", low) or re.search(
                r"\bthe (?:name|capital|author|inventor|founder|currency|symbol|title|winner|main) \b", low):
            return 'which', None, None, None, None
    return none


def clean(sentence):
    s = re.sub(r'\[(?:update|\d+|citation needed|note \d+)\]', '', sentence)
    s = re.sub(r'\s*\((?:/[^)]*/|[^)]*(?:pronounced|listen|IPA)[^)]*)\)', '', s)
    return re.sub(r'\s+', ' ', s).strip()


def split(text):
    """Sentences, with "Mr. Watson" and "St. Louis" kept whole."""
    text = re.sub(r'\b(Mr|Mrs|Ms|Dr|St|Jr|Sr|Prof|Gen|Col|Capt|Lt|Mt|vs|No|c|ca|approx)\. ', '\\1.\u2060', text)
    return [s.replace('\u2060', ' ') for s in wc.sentences(text)]


def search(text, limit=6):
    got = wc.api(WIKI, action='query', list='search', srsearch=text[:250], srlimit=limit, srnamespace=0)
    out = []
    for h in got.get('query', {}).get('search', []):
        if '(disambiguation)' in h['title']:
            continue
        out.append((h['title'], re.sub(r'<[^>]+>', '', html.unescape(h.get('snippet', '')))))
    return out


TITLES = set('President King Queen Sir Dr Professor Captain Cosmonaut Astronaut Emperor Pope Saint General Prince Princess Lord Lady Physicist '
             'Scientist Inventor Author Engineer Chemist Explorer Mathematician Painter Composer American British French German Italian Russian '
             'Soviet Scottish English Greek Dutch Spanish Polish Chinese Japanese Indian'.split())


def names(text, asked_stems, person=False):
    out = []
    for m in (PERSON if person else NAME).finditer(text):
        name = m[1]
        while name.split() and name.split()[0] in NOT_NAME:
            name = name.split(' ', 1)[1] if ' ' in name else ''
        first = name.split()[0] if name.split() else ''
        if person and len(name.split()) > 2 and (first.endswith('s') or first in TITLES):
            name = name.split(' ', 1)[1]    # "Astronauts Valentina Tereshkova", "President Abraham Lincoln"
        if person and len(name.split()) < 2:
            continue
        if not name or name in NOT_NAME or {wc.stem(w) for w in wc.words(name)} <= asked_stems or re.fullmatch(r'[A-Z]?\d+', name):
            continue
        if name.endswith(("'s", "’s")) or text[m.end(1):m.end(1) + 2] in ("'s", "’s") or name in MONTHS:
            continue
        out.append(name)
    return out


def phrase_at(tokens, special, head, known=frozenset()):
    """Where the question's "<special> <head>" stands in a sentence ("longest river", "most ... moons"): the index of the
    special word, or None. Words between the two that the question did not use count against the match."""
    for i, t in enumerate(tokens):
        if t != special:
            continue
        if not head:
            return i, 0
        for j in range(i + 1, min(len(tokens), i + 5)):
            if wc.stem(tokens[j]) == head:
                # words between the two that the question did not use narrow the claim ("largest fog desert")
                return i, sum(1 for t in tokens[i + 1:j] if wc.stem(t) not in known and t not in ('known', 'and'))
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ''
        if nxt and nxt not in ('and', 'of', 'in', 'on', 'by', 'among', 'at', 'to', 'with', 'known', 'ever', 'so', 'yet', 'or', 'but'):
            continue                        # "the world's largest source of ..." is about something else
        for j in range(max(0, i - (12 if special in ('most', 'least', 'only') else 6)), i):
            if wc.stem(tokens[j]) == head:
                return i, 0                 # "The Pacific Ocean is the largest ...", "293 moons ..., the most of any planet"
    return None


def values_in(s, title, kind, type_word, noun, unit, cue, asked_stems, special, head, verb, in_lead, known=frozenset()):
    """The values of the asked kind that a sentence states, and whether its wording matches the question's own phrase."""
    bare = re.sub(r'\s*\([^)]*\)', '', title)
    title_stems = {wc.stem(w) for w in wc.words(bare)}
    tokens = wc.words(s)
    exact = False
    upto = len(s)
    if special:
        at = phrase_at(tokens, special, head, known)
        if at is None or at[1]:
            return [], False
        if re.search(r"(?i)\b\w+(?:'s|’s) (?:\w+ )?" + special + r'\b', s) and not re.search(r"(?i)\b(?:world|earth)(?:'s|’s) (?:\w+ )?" + special, s):
            return [], False                # "France's longest river" is not the longest river
        if re.search(r'(?i)\b(?:second|third|fourth|fifth|sixth|\d+(?:st|nd|rd|th)|one of the|among the|of the)[ -](?:\w+ )?' + special + r'\b', s):
            return [], False                # "the second hottest after Venus", "one of the largest"
        exact = at[1] == 0
        found = re.search(r'(?i)\b' + special + r'\b', s)
        upto = found.start() if found else len(s)
    if kind in ('which', 'where', 'who'):
        before = s[:upto] if special else s
        if kind == 'which' and type_word:
            got = [n for n in TYPES[type_word] if re.search(r'\b' + re.escape(n) + r'\b', before)]
            if special and got:
                got = got[-1:]
        elif kind == 'who' and verb and not special:
            got = []
            v = re.search(r'(?i)\b' + re.escape(verb[:max(4, len(verb) - 2)]) + r'\w*\b', s)
            if v:
                by = re.match(r'(?:\s+\w+){0,3}?\s+by\s+', s[v.end():])
                if by:
                    got = names(s[v.end() + by.end():v.end() + by.end() + 60], asked_stems, person=True)[:1]
                else:
                    got = names(s[max(0, v.start() - 70):v.start()], asked_stems, person=True)[-1:]
                exact = bool(got)
        else:
            got = names(before, asked_stems, person=kind == 'who')
            if special and got:
                got = got[-1:]              # the subject nearest to "is the longest ..."
        if not got and special and re.search(r'(?i)\b(?:it|its|which)\b', s[:upto]) and (
                bare in TYPES[type_word] if type_word else not title_stems <= asked_stems) and (kind != 'who' or len(bare.split()) > 1):
            got = [bare]                    # "..., making it the hottest planet": the article's own subject
        return got, exact
    if kind == 'when':
        full = re.findall(r'\b(\d{1,2} (?:%s) \d{4}|(?:%s) \d{1,2}, \d{4})\b' % ('|'.join(MONTHS), '|'.join(MONTHS)), s)
        found = full or re.findall(r'\b(1\d{3}|20\d{2}|\d{1,4} (?:BC|BCE|AD))\b', s)
        if len(found) > 1 and ENDS.search(' '.join(asked_stems)) and re.search(r'\d\s*(?:–|-|to|until)\s*(?:\d|[A-Z])', s):
            return found[-1:], exact        # "(1 September 1939 – 2 September 1945)" and the question asks for the end
        return found[:1], exact
    if kind == 'count':
        n = wc.stem(noun)
        out = []
        for m in re.finditer(r'(?i)\b(' + NUM + r')((?:\s+[a-z-]+){0,2}?)\s+([a-z]+)\b', s):
            before = s[:m.start()].rstrip().rsplit(' ', 1)[-1].lower()
            if wc.stem(m[3].lower()) == n and not re.search(r'(?i)\b(?:of|in|and|to|than|or)\b', m[2]) and before not in (
                    'the', 'these', 'those', 'all', 'his', 'her', 'their', 'its', 'other', 'first', 'last', 'top', 'only', 'least', 'to', 'another', 'than', 'every'):
                out.append(m[1].lower())
        return out, in_lead and title_stems <= asked_stems
    if kind == 'measure':
        if cue and not re.search(r'(?i)\b(?:' + cue + r')', s):
            return [], False
        out = [m[0].strip() for m in re.finditer(r'(?<![\w.,])' + NUM.replace('(?:\\d', '(?:(?:about |around |approximately |roughly )?\\d', 1)
                                                 + r'[\s-]*(?:' + UNIT[unit] + r')(?![\w/⋅])', s)]
        return [re.sub(r'^(?:about|around|approximately|roughly) ', '', o) for o in out[:1]], in_lead and title_stems <= asked_stems
    return [], False


def sentence(messages, question=None):
    question = question or standalone(messages)
    kind, type_word, noun, unit, cue = asks(question)
    if kind is None:
        return None
    own = [w for w in dict.fromkeys(wc.content(question)) if w not in wc.GENERIC]
    q_tokens = wc.words(question)
    special = next((w.lower() for w in SPECIAL.findall(question) if w.lower() not in NOT_SPECIAL and
                    not re.search(r'(?i)\b' + re.escape(w) + r' (?:language|tongue)\b', question)), None)
    head = None
    if special:
        after = [w for w in q_tokens[q_tokens.index(special) + 1:] if w not in wc.STOP or w in ('people', 'person')]
        head = wc.stem(after[0]) if after and q_tokens.index(after[0]) - q_tokens.index(special) <= 2 else (wc.stem(type_word) if type_word else None)
    verb = None
    m = re.match(r"(?i)\s*who (?!is\b|was\b|are\b|were\b|did\b|does\b|has\b|had\b)([a-z]+)\b", question)
    if m:
        verb = m[1].lower()
    terms = {w: wc.weight(w) for w in own}
    if special:
        terms.setdefault(special, 4.0)
    for w in q_tokens:
        if w in KEEP or w == verb:
            terms.setdefault(w, 3.0)
    if type_word:
        terms.setdefault(type_word, 3.0)
    # what the chat is about belongs to a short follow-up ("What year was the first call made?" after the telephone)
    turns = wc.user_turns(messages) if messages else [question]
    borrowed = []
    if len(turns) > 1 and len(own) <= 3 and question.rstrip('?').lower() in turns[-1].lower():
        prev = last_question(turns[-2])
        borrowed = [w for w in wc.nouns(list(dict.fromkeys(wc.content(prev)))) if w not in terms and w not in wc.GENERIC and wc.weight(w) > 4][:2]
        for w in borrowed:
            terms[w] = wc.weight(w) * 0.7
    if not terms or sum(terms.values()) < 6:
        return None
    asked_stems = {wc.stem(w) for w in q_tokens}
    keywords = ' '.join(sorted(terms, key=lambda w: -terms[w])[:6])
    natural = question.rstrip('?. ') + (' ' + ' '.join(borrowed) if borrowed else '')
    hits, seen = [], set()
    batches = [search(natural), search(keywords)]
    for rank in range(6):
        for batch in batches:
            if rank < len(batch) and batch[rank][0] not in seen:
                seen.add(batch[rank][0])
                hits.append(batch[rank])
    total = sum(terms.values())
    stems = {wc.stem(w): v for w, v in terms.items()}
    known = set(stems) | {wc.stem(w) for w in borrowed}
    pool, read = [], 0
    for order, (title, snippet) in enumerate(hits[:7]):
        if title.startswith(('List of', 'Lists of', 'Timeline of', 'Index of', 'Outline of')):
            continue                        # tables, and their search snippets are fragments
        try:
            got = wc.page_text(WIKI, title)
        except LookupUnavailable:
            got = None
        if not got:
            continue
        read += 1
        title_stems = {wc.stem(w) for w in wc.words(re.sub(r'\([^)]*\)', '', title))}
        extra = re.search(r'\(([^)]*)\)', title)
        if extra and not {wc.stem(w) for w in wc.content(extra[1])} & set(stems) and not title_stems & set(stems):
            continue
        sents = split(got[1][:40000])
        for i, raw in enumerate(sents):
            s = clean(raw)
            n = len(s.split())
            if n < 5 or n > 60 or '?' in s:
                continue
            if re.search(r"(?i)\bthe (?:most|largest|biggest|highest|youngest|oldest|greatest|longest|tallest)\b", question) and \
                    re.search(r"(?i)\b(?:outside (?:of )?(?:the )?\w+|except(?:ing)?|excluding|other than|apart from|second|third|after (?:the )?\w+|among (?:\w+ )?(?:non|women|female))\b", s) \
                    and not re.search(r"(?i)\b(?:outside|except|excluding|other than|apart from|second|third|after|among)\b", question):
                continue                    # "the country with the most Spanish speakers outside the Hispanophone world" is not the most
            have = {wc.stem(w) for w in wc.words(s)}
            if re.search(r'(?i)\bnative (?:language|speakers?|tongue)|\bmother tongue\b|\bL1\b', s):
                have |= {wc.stem('first'), wc.stem('language')}      # "first language" is said "native language" on most pages
            cov = sum(v if w in have else 0.5 * v if w in title_stems and w != special else 0 for w, v in stems.items()) / total
            if cov < 0.6:
                continue
            values, exact = values_in(s, title, kind, type_word, noun, unit, cue, asked_stems, special, head, verb, i < 6, known)
            if not values:
                continue
            inside = sum(v for w, v in stems.items() if w in have) / total
            if kind == 'measure' and inside >= 0.9:
                exact = True                # the sentence itself has every word of the question and a value in the right unit
            score = cov + 0.1 * inside + 0.15 * exact + 0.05 * (1 - i / max(1, len(sents))) + 0.04 * (1 - order / 7) \
                - 0.002 * max(0, n - 30) - (0.15 if wc.ANAPHORA.search(s) else 0)
            usual = re.search(r"(?i)\b(?:usually|typically|normally|generally|traditionally|commonly|mostly)\s+(?:have|has|had|with|come with|feature|use)\s+"
                              r"([a-z0-9]+)\s+(?:\w+\s+)?" + re.escape((noun or 'x')[:4]), s) if kind == 'count' and noun else None
            variant = None
            if kind == 'count':
                for w in own:
                    if w == noun:
                        continue
                    vm = re.search(r"(?i)\b(?:the|a|an)\s+([a-z]+)\s+" + re.escape(w) + r"s?\b", s)
                    if vm and vm[1].lower() not in question.lower() and vm[1].lower() not in (
                            'standard', 'typical', 'modern', 'common', 'basic', 'regular', 'normal', 'average', 'whole', 'entire', 'first', 'same', 'usual'):
                        variant = vm[1]
                        break
            if variant:
                score -= 0.6                # "The Tahitian ukulele has eight strings" is about one kind, not the instrument asked about
                usual = None
            if usual and any(usual[1].lower() == v.lower() for v in values):
                score += 0.8                # the usual case ("usually have four strings"), not a variant ("Tahitian ukuleles have eight")
                values = [v for v in values if v.lower() == usual[1].lower()]
                exact = True
            pool.append((score, s, title, values, exact))
    if not pool:
        return None
    pool.sort(key=lambda c: -c[0])
    if os.environ.get('CAEL_EXACT_DEBUG'):
        for c in pool[:8]:
            print('   ~', round(c[0], 2), c[3], c[4], '|', c[2], '|', c[1][:150])
    top = [c for c in pool if c[0] >= pool[0][0] - (0.3 if kind == 'count' else 0.15)][:20]
    votes = {}
    for score, s, title, values, exact in top:
        for v in dict.fromkeys(values):
            key = re.sub(r'[\s,]', '', v.lower()) if kind in ('count', 'measure') else v.lower()
            votes.setdefault(key, [0.0, v, set(), 0, False])
            votes[key][0] += score
            votes[key][2].add(title)
            votes[key][3] += 1
            votes[key][4] = votes[key][4] or exact
    for a in list(votes):                   # "Everest" counts for "Mount Everest", "1876" for "10 March 1876"
        for b in list(votes):
            if a != b and re.search(r'\b' + re.escape(a) + r'\b', b):
                votes[b][0] += 0.5 * votes[a][0]
                votes[b][2] |= votes[a][2]
                votes[b][3] += votes[a][3]
    if kind == 'count':
        ranked = sorted(votes.values(), key=lambda v: (-v[4], -v[3], -v[0]))
    elif kind in ('who', 'which', 'where'):
        ranked = sorted(votes.values(), key=lambda v: (-v[4], -len(v[2]), -v[0]))
    else:
        ranked = sorted(votes.values(), key=lambda v: (-v[4], -v[0]))
    win = ranked[0]
    best = next((c for c in top if any(v.lower() == win[1].lower() for v in c[3])),
                None) or next(c for c in top if any(win[1].lower() in v.lower() or v.lower() in win[1].lower() for v in c[3]))
    if best[0] < 0.8:
        return None
    pages, runner = len(win[2]), (ranked[1] if len(ranked) > 1 else None)
    if kind == 'count':
        sure = win[4] or (win[3] >= 2 and (runner is None or win[3] > runner[3] or win[0] >= 1.15 * runner[0])) or \
            (best[0] >= 1.1 and best is top[0] and (runner is None or win[0] >= 1.25 * runner[0]))     # one sentence with every word asked, well ahead
    elif kind == 'measure':
        sure = win[4] or pages >= 2 or runner is None or (best[0] >= 0.85 and best is top[0])
    else:
        sure = win[4] or pages >= 2 or runner is None or win[0] >= 1.4 * runner[0]
    if not sure:
        return None
    value = win[1]
    if re.fullmatch(r'[a-z]+', value):
        value = value.capitalize()
    other = next((t for t in win[2] if t != best[2]), None)
    check = f' Checked against the article "{other}", which says the same.' if other else ''
    url = f'https://en.wikipedia.org/wiki/{quote(best[2].replace(" ", "_"))}'
    return dict(route='chat/web-exact', response=f'**{value}.** {best[1]}\n\nSource: {best[2]} (Wikipedia).{check}', answer=value,
                confidence=min(0.95, 0.62 + 0.1 * (pages - 1) + 0.15 * win[4] + 0.2 * (best[0] - 0.8)),
                sources=[dict(source='Wikipedia', title=best[2], url=url, licence=wc.LICENCE)],
                details=f'Wikipedia searched for "{natural}" and "{keywords}"; {read} pages read; {len(pool)} sentences state a value of the asked kind '
                        f'({kind}); "{value}" in {win[3]} sentence(s) on {pages} page(s).')


# ----------------------------------------------------------------------------------------------------------------------
# 3. Article openings

ABOUT = re.compile(r"(?i)^\s*(?:(?:can|could) you (?:please )?(?:tell me|explain)(?: to me)?(?: about| what causes| what makes| what)?|"
                   r"what (?:causes|makes)|tell me (?:a bit |a little |something |more )?about|"
                   r"what do you know about|explain how|explain|describe|define|what(?:'s| is| are| was| were)|who(?:'s| is| was| were)|what does|what do|"
                   r"how (?:do|does|did))\s+"
                   r"(?:(?:a|an|the)\s+)?(.+?)(?:\s+(?:mean|means|stand for|do|does|work|works|worked|function|functions|form|forms|happen|happens|occur|occurs|grow|grows))?\s*\??\s*$")


def summary(question):
    m = ABOUT.match(question.strip())
    if not m:
        return None
    thing = m[1].strip(' .?!"\'')
    if not thing or len(thing.split()) > 5 or re.search(r"(?i)\b(?:my|your|our|i|you|me|we|this|that|it|they|best|difference|between|way|"
                                                         r"point|reason|meaning of life)\b", thing) or SPECIAL.search(thing):
        return None
    got = None
    try:
        got = wc.page_text(WIKI, thing[:1].upper() + thing[1:])
    except LookupUnavailable:
        return None
    asked = {wc.stem(w) for w in wc.content(thing)} or {wc.stem(w) for w in wc.words(thing)}
    if got and not asked <= {wc.stem(w) for w in wc.words(got[0])} and asked <= {wc.stem(w) for w in wc.words(got[1][:1500])}:
        pass                    # a redirect ("Northern lights" -> "Aurora") whose opening names what was asked
    elif not got or not asked <= {wc.stem(w) for w in wc.words(got[0])}:
        got = None
        for title, _ in search(thing, 4):
            title_stems = {wc.stem(w) for w in wc.words(re.sub(r'\([^)]*\)', '', title))}
            if asked <= title_stems and len(title_stems) <= len(asked) + 1:
                got = wc.page_text(WIKI, title)
                break
    if not got:
        # the everyday name of something with a different article title ("northern lights" -> "Aurora"): Wikidata knows both
        try:
            for f in wd(action='wbsearchentities', search=thing, language='en', uselang='en', type='item', limit=12).get('search', []):
                if re.search(r'(?i)\b(?:disambiguation|given name|family name|film|song|album|band|novel|television|edition|book|episode|single|painting|'
                             r'video game|game|magazine|newspaper|company|ship|play|musical|poem|series|character|horse|racehorse|fanzine)\b', f.get('description', '')):
                    continue
                ent = wd(action='wbgetentities', ids=f['id'], props='sitelinks', sitefilter='enwiki').get('entities', {}).get(f['id'], {})
                title = ent.get('sitelinks', {}).get('enwiki', {}).get('title')
                if title:
                    cand = wc.page_text(WIKI, title)
                    if cand and asked <= {wc.stem(w) for w in wc.words(cand[1][:2000])}:
                        got = cand
                        break
        except LookupUnavailable:
            pass
    if not got:
        return None
    title, body, url = got
    sents = [clean(s) for s in wc.sentences(body[:4000])][:3]
    text, count = '', 0
    for s in sents:
        if count and len((text + ' ' + s).split()) > 75:
            break
        text, count = (text + ' ' + s).strip(), count + 1
    if len(text.split()) < 8:
        return None
    return dict(route='chat/web-exact', response=f'{text}\n\nSource: {title} (Wikipedia).', confidence=0.8,
                sources=[dict(source='Wikipedia', title=title, url=url, licence=wc.LICENCE)],
                details=f'The opening of the Wikipedia article "{title}".')


def within(messages):
    """A follow-up about something just explained from an article ("Why can you only see them near the poles?" after the
    aurora): the sentence of that same article that answers it, with the reason words a 'why' needs."""
    prev = next((m.get('content') or '' for m in reversed(messages[:-1]) if m.get('role') == 'assistant'), '')
    src = re.search(r'\nSource: (.+?) \(Wikipedia\)', prev)
    if not src:
        return None
    q = standalone(messages)
    got = wc.page_text(WIKI, src[1])
    if not got:
        return None
    want = {wc.stem(w): wc.weight(w) for w in wc.content(q) if w not in wc.GENERIC and wc.weight(w) > 2.5}
    title_words = {wc.stem(w) for w in wc.words(got[0])}
    want = {k: v for k, v in want.items() if k not in title_words}         # the article's own subject is everywhere
    if not want:
        return None
    why = re.match(r'(?i)\s*why\b', q)
    best = None
    for i, raw in enumerate(split(got[1][:60000])):
        s = clean(raw)
        if not 6 <= len(s.split()) <= 55 or s in prev:
            continue
        have = {wc.stem(w) for w in wc.words(s)}
        cov = sum(v for k, v in want.items() if k in have) / sum(want.values())
        if cov < 0.5:
            continue
        if why and not re.search(r'(?i)\b(?:because|due to|since|as a result|caused by|so that|which (?:is|are) why|owing to|results? (?:in|from))\b', s):
            continue
        score = cov - 0.002 * i
        if best is None or score > best[0]:
            best = (score, s)
    if not best:
        return None
    return dict(route='chat/web-exact', response=f'{best[1]}\n\nSource: {got[0]} (Wikipedia).', confidence=0.75,
                sources=[dict(source='Wikipedia', title=got[0], url=got[2], licence=wc.LICENCE)],
                details=f'The sentence of the article "{got[0]}" (cited in the previous reply) that answers the follow-up "{q}".')


# ----------------------------------------------------------------------------------------------------------------------

ORIGIN = re.compile(r"(?i)^\s*(?:and |so )?(?:where (?:does|do|did) (?:the |a |an )?(.+?) (?:come from|originate|originally come from)(?: originally)?|"
                    r"where (?:is|are|was|were) (?:the |a |an )?(.+?) (?:from )?originally(?: from)?|what(?:'s| is) the origin of (?:the |a |an )?(.+?)|"
                    r"where (?:was|were) (?:the |a |an )?(.+?) (?:invented|first made|developed))\s*\??\s*$")
ORIGIN_CUE = re.compile(r"(?i)\b(?:originat\w*|developed in|comes? from|came from|invented in|first (?:made|built|appeared|developed)|introduced (?:to|in|into|by)|"
                        r"native to|adaptation of|derived from|brought (?:to|by)|arrived in)\b")


def origin(question):
    """'Where does the ukulele come from originally?': the sentence of its encyclopedia article that says where it began."""
    m = ORIGIN.match(question.strip())
    if not m:
        return None
    thing = next(g for g in m.groups() if g).strip(' ?.')
    if not thing or len(thing.split()) > 5 or re.search(r"(?i)\b(?:my|your|our|i|you|me|we|it|they|this|that)\b", thing):
        return None
    got = wc.page_text(WIKI, thing[:1].upper() + thing[1:])
    asked = {wc.stem(w) for w in wc.content(thing)}
    if not got or not asked <= {wc.stem(w) for w in wc.words(got[0] + ' ' + got[1][:600])}:
        got = None
        for title, _ in search(thing, 4):
            if asked <= {wc.stem(w) for w in wc.words(title)}:
                got = wc.page_text(WIKI, title)
                break
    if not got:
        return None
    title, body, url = got
    for s in [clean(x) for x in wc.sentences(body[:12000])]:
        if ORIGIN_CUE.search(s) and 6 <= len(s.split()) <= 50 and re.search(r"\b[A-Z][a-z]+", s[1:]) and not wc.ANAPHORA.search(s[:12]) and \
                not re.search(r"(?i)\b(?:word|words|meaning|etymolog\w*|the name|named after|spelling|term)\b", s):
            return dict(route='chat/web-exact', response=f'{s}\n\nSource: {title} (Wikipedia).', confidence=0.7, answer=s,
                        sources=[dict(source='Wikipedia', title=title, url=url, licence=wc.LICENCE)],
                        details=f'The first sentence of the Wikipedia article "{title}" that says where it began (exact_web.origin).')
    return None


def answer(messages):
    """The first researcher that is sure. None when the question is not a fact question or nothing certain was found."""
    if os.environ.get('CAEL_WEB_SEARCH', '1') == '0' or os.environ.get('CAEL_EXACT_WEB', '1') == '0':
        return None
    question = standalone(messages)
    turns = wc.user_turns(messages)
    leans = len(turns) > 1 and not re.search(r"(?i)\b(?:in|of|on|for|from|at|by) (?:the |a |an )?[a-z]", question) and not re.search(r"\s[A-Z][a-z]", question)
    finders = [lambda: wikidata(question), lambda: origin(question)]
    finders += [lambda: sentence(messages, question), lambda: sentence(None, question)] if leans else [lambda: sentence(None, question)]
    for find in finders + [lambda: summary(question)]:
        try:
            got = find()
        except LookupUnavailable:
            got = None
        except Exception:
            got = None
        if got and got.get('confidence', 0) >= 0.6:
            return dict(got, question=question)
    return None
