"""Source-backed facts, weather and news; no paid or non-commercial APIs."""
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import re
import sqlite3
from urllib.parse import quote, urlencode

from .network import LookupUnavailable, NETWORK
from .news_policy import NewsPolicy, shorten, topical
from .request_policy import RequestPolicy
from .knowledge import KnowledgeStore, edit_distance
from .knowledge_query import KnowledgeQuery, static_allowed, content_words, canonical_question, EXPLICIT_WEB
from .knowledge_html import ArticleText
from .source_quality import intact_text
from . import explain

WIKI = 'https://en.wikipedia.org/w/api.php?'
WD = 'https://www.wikidata.org/w/api.php?'
CCBY = 'https://creativecommons.org/licenses/by/4.0/'
CCBYSA = 'https://creativecommons.org/licenses/by-sa/4.0/'
CC0 = 'https://creativecommons.org/publicdomain/zero/1.0/'


class NewsItems(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.items = []
        self.dated_items = []
        self.date = None
        self.section = None
        self.paragraph = None
        self.records = []

    def handle_starttag(self, tag, attrs):
        identifier = dict(attrs).get('id', '')
        if re.fullmatch(r'\d{4}_[A-Za-z]+_\d{1,2}', identifier):
            try:
                self.date = datetime.strptime(identifier, '%Y_%B_%d').date()
                self.section = None
            except ValueError:
                pass
        if tag == 'li':
            if self.stack:
                self.stack[-1]['children'] = True
            self.stack.append(dict(buffer=[], children=False, date=self.date))
        if tag == 'p' and not self.stack:
            self.paragraph = []

    def handle_endtag(self, tag):
        if tag == 'li' and self.stack:
            item = self.stack.pop()
            if not item['children']:
                text = re.sub(r'\s+', ' ', ''.join(item['buffer'])).strip()
                self.items.append(text)
                self.dated_items.append((item['date'], text))
                self.records.append(dict(date=item['date'], category=self.section, text=text))
        if tag == 'p' and self.paragraph is not None:
            heading = ''.join(self.paragraph).strip()
            if heading in ('Armed conflicts and attacks', 'Arts and culture', 'Business and economy',
                           'Disasters and accidents', 'Health and environment', 'Law and crime',
                           'Politics and elections', 'Science and technology', 'Sports'):
                self.section = heading
            self.paragraph = None

    def handle_data(self, data):
        if self.stack:
            self.stack[-1]['buffer'].append(data)
        elif self.paragraph is not None:
            self.paragraph.append(data)


def source(name, url, licence, licence_url, attribution):
    return dict(source=name, url=url, licence=licence, licence_url=licence_url, attribution=attribution)


def wikidata_date(value):
    """Respect statement precision; unknown months/days are not calendar dates."""
    raw = value.get('time', '').lstrip('+')
    precision = value.get('precision', 9)
    return raw[:10] if precision >= 11 and raw[5:7] != '00' and raw[8:10] != '00' else raw[:7] if precision >= 10 and raw[5:7] != '00' else raw[:4]


WEATHER_WORDS = [('clearsky', 'clear sky'), ('partlycloudy', 'partly cloudy'), ('lightssleet', 'light sleet'),
                 ('heavysleet', 'heavy sleet'), ('lightsnow', 'light snow'), ('heavysnow', 'heavy snow'),
                 ('lightrain', 'light rain'), ('heavyrain', 'heavy rain'), ('showers', ' showers'), ('andthunder', ' and thunder')]


def describe_symbol(symbol):
    """MET Norway symbol codes ("lightrainshowers_day") as words ("light rain showers")."""
    if not symbol:
        return 'conditions unavailable'
    text = re.sub(r'_(?:day|night|polartwilight)$', '', symbol)
    for code, words in WEATHER_WORDS:
        text = text.replace(code, words)
    return ' '.join(text.replace('_', ' ').split())


def result(text, route, sources, note=''):
    checked = datetime.now(timezone.utc).isoformat(timespec='seconds')
    credits = '\n'.join(f"{s['attribution']} — {s['url']} ({s['licence']}; {s['licence_url']})" for s in sources)
    return dict(response=text, route='chat/web-' + route, sources=sources,
                details=f'Retrieved or read from the provider cache at {checked}.\n{note}\n{credits}'.strip())


class FactLookup:
    def __init__(self, network=None):
        self.net = network or NETWORK
        self.news_policy = NewsPolicy()
        self.request_policy = RequestPolicy()
        self.knowledge_query = KnowledgeQuery()
        self.knowledge = KnowledgeStore()

    def entity_search(self, name, limit=3):
        data = self.net.json(WD + urlencode(dict(action='wbsearchentities', format='json',
                             search=name[:180], language='en', limit=limit)), ttl=86400)
        return data.get('search', [])

    def entities(self, ids, props='claims|labels|descriptions'):
        data = self.net.json(WD + urlencode(dict(action='wbgetentities', format='json',
                             ids='|'.join(ids), props=props, languages='en|mul', languagefallback=1)), ttl=300)
        return data.get('entities', {})

    def place(self, name):
        hits = self.entity_search(name)
        entities = self.entities([h['id'] for h in hits]) if hits else {}
        for hit in hits:
            entity = entities.get(hit['id'], {})
            for statement in entity.get('claims', {}).get('P625', []):
                value = statement.get('mainsnak', {}).get('datavalue', {}).get('value', {})
                if value.get('globe', '').endswith('/Q2') and 'latitude' in value:
                    label = entity.get('labels', {}).get('en', {}).get('value', hit['label'])
                    return label, value['latitude'], value['longitude'], hit['id']
        raise LookupUnavailable('No location coordinates found')

    def weather(self, text, messages=None):
        # Common misspellings of the time words, so "tommorow" is never taken for a place.
        text = re.sub(r'(?i)\b(?:tom+or+ow|tomorow|tmrw|tmr|2morrow|2moro)\b', 'tomorrow', text)
        # The place normally follows the weather word ("weather in Haifa tomorrow"); the learned
        # request parser is only a fallback, since it can return a verb ("check") as the subject.
        match = re.search(r'\b(?:weather|forecast|temperature)\b(.*)', text, re.I)
        place = re.sub(r'^(?:forecast\s+)?(?:like\s+)?(?:in|for|at|of)\s+', '', match[1].strip(), flags=re.I) if match else ''
        before = re.search(r'(?i)\b(?:in|at|for)\s+([A-Z][\w\- ]{1,40}?)\s+(?:weather|forecast)\b', text)
        if not re.sub(r'(?i)\b(?:right now|today|tomorrow|tonight|currently|this week(?:end)?|now|be|going to be|will be|like)\b', '', place).strip(' ?,!.') and before:
            place = before[1]
        if not place and not match:
            parsed = self.request_policy.parse(text)
            subject = parsed['subject'] if parsed['intent'] == 'weather' else ''
            if subject and not re.fullmatch(r'(?i)(?:check|tell|show|give|get|find|look|what|is|the|me|you|weather)(?:\s+\w+)?', subject):
                place = subject
        time_words = r'\b(?:right now|today|tomorrow|tonight|currently|this week|this weekend|now|be|going to be|will be|like)\b'
        place = re.sub(time_words, '', place, flags=re.I)
        place = re.sub(r'^\s*(?:for|in|at|of|the)\s+', '', place, flags=re.I).strip(' ?,!.')
        remembered = ''
        if not place and messages:
            from .memory import facts
            remembered = facts(messages[:-1])['attributes'].get('home', '')
            place = remembered
        if not place:
            return result('Which city should I check the weather for?', 'weather', [])
        try:
            label, latitude, longitude, qid = self.place(place)
        except LookupUnavailable:
            return result(f'I could not find a place called "{place}". Which city should I check the weather for?', 'weather', [])
        url = 'https://api.met.no/weatherapi/locationforecast/2.0/compact?' + urlencode(dict(lat=f'{latitude:.4f}', lon=f'{longitude:.4f}'))
        data = self.net.json(url, ttl=600)
        rows = data.get('properties', {}).get('timeseries', [])
        now = datetime.now(timezone.utc)
        target = now + timedelta(days=1) if re.search(r'\btomorrow\b', text, re.I) else now
        rows = [r for r in rows if datetime.fromisoformat(r['time'].replace('Z', '+00:00')) >= target - timedelta(hours=1)]
        if not rows:
            raise LookupUnavailable('Forecast time is outside the available range')
        row = rows[0]
        details = row['data']['instant']['details']
        symbol = row['data'].get('next_1_hours', row['data'].get('next_6_hours', {})).get('summary', {}).get('symbol_code', '')
        conditions = describe_symbol(symbol)
        period = row['data'].get('next_1_hours', row['data'].get('next_6_hours', {}))
        hours = 1 if 'next_1_hours' in row['data'] else 6
        rain = period.get('details', {}).get('precipitation_amount')
        precipitation = f" Precipitation: {rain} mm over the next {hours} {'hour' if hours == 1 else 'hours'}." if rain is not None and re.search(r'\b(?:rain|raining|snow|snowing)\b', text, re.I) else ''
        output = (f"{label}: {conditions}, {details['air_temperature']} °C; wind {details.get('wind_speed', '?')} m/s."
                  f"{precipitation} Forecast at {row['time']} UTC.")
        if remembered:
            output = f'You told me you live in {remembered}, so here is the forecast there. ' + output
        sources = [source('MET Norway', url, 'CC BY 4.0', CCBY, 'Data from MET Norway; formatted by CAEL'),
                   source('Wikidata', 'https://www.wikidata.org/wiki/' + qid, 'CC0 1.0', CC0, 'Location coordinates from Wikidata')]
        return result(output, 'weather', sources, 'This is a forecast, not a measured observation. Times are UTC.')

    def structured_faq(self, text):
        patterns = [
            (r'(?:what is |tell me )?(?:the )?capital of (.+)', 'P36', 'capital'),
            (r'(?:how many people live in|what is the population of|population of) (.+)', 'P1082', 'population'),
            (r'when was (.+?) born', 'P569', 'birth'),
            (r'where is (.+)', 'P17', 'country'),
            (r'(?:what|which) languages? (?:do (?:they|people|you|most people) speak|is spoken|are spoken|does everyone speak) in (.+)', 'P37', 'language'),
            (r"(?:what is |what's |what are )?(?:the )?(?:official |main |national )?languages? (?:of|in) (.+)", 'P37', 'language'),
            (r'who (?:wrote|authored|is the author of|was the author of) (?:the (?:book|novel|play|poem) )?(.+)', 'P50', 'wrote'),
            (r'who painted (.+)', 'P170', 'painted'),
            (r'who (?:directed|was the director of|is the director of) (?:the (?:film|movie) )?(.+)', 'P57', 'directed'),
            (r'who (?:composed|wrote the music (?:for|of)) (.+)', 'P86', 'composed'),
            (r'who (?:invented|discovered) (?:the )?(.+)', 'P61', 'invented'),
            (r'who (?:founded|started|created the company) (.+)', 'P112', 'founded'),
            (r'who (?:designed|was the architect of|built) (?:the )?(.+)', 'P84', 'designed'),
            (r'(?:what is |what\'s )?(?:the )?(?:currency|money) (?:of|in|used in) (?:the )?(.+)', 'P38', 'currency'),
            (r'(?:what is |what\'s )?(?:the )?boiling point of (.+)', 'P2102', 'boiling'),
            (r'(?:what is |what\'s )?(?:the )?melting point of (.+)', 'P2101', 'melting'),
            (r'how (?:tall|high) is (?:the )?(.+)', 'P2048', 'height'),
            (r'how long is (?:the )?(.+)', 'P2043', 'length'),
            (r'(?:when|what year) (?:was|were|did) (?:the )?(.+?) (?:open|opened|open to the public)', 'P1619', 'opened'),
            (r'(?:when|what year) (?:was|were|did) (?:the )?(.+?) (?:released|published|come out|first released)', 'P577', 'released'),
            (r'(?:when|what year) (?:was|were|did) (?:the )?(.+?) (?:founded|established|created|formed|start|started)', 'P571', 'founded-date'),
        ]
        for pattern, prop, kind in patterns:
            match = re.fullmatch(pattern + r'[?.!]*', text.strip(), re.I)
            if match:
                name = match[1].strip(' ?.!,')
                break
        else:
            return None
        creator = kind in ('wrote', 'painted', 'directed', 'composed', 'invented', 'founded', 'designed')
        hits = self.entity_search(name, limit=5 if creator else 1)
        if not hits:
            return None
        qid = hits[0]['id']
        entity = self.entities([qid]).get(qid, {})
        if creator:
            # "Hamlet" is also a village and a film: also search "Hamlet play/book" and take the first match that has
            # an author/creator at all.
            # Wikidata full-text search, limited to items that have the property asked about ("The Tragedy of Hamlet").
            data = self.net.json(WD + urlencode(dict(action='query', list='search', format='json', srlimit=5,
                                                     srsearch=f'{name} haswbstatement:{prop}')), ttl=86400)
            seen = {h['id'] for h in hits}
            for row in data.get('query', {}).get('search', []):
                if row.get('title', '').startswith('Q') and row['title'] not in seen:
                    seen.add(row['title'])
                    hits.append(dict(id=row['title']))
            found = self.entities([h['id'] for h in hits][:50], props='claims|labels|descriptions|sitelinks')
            wanted = re.sub(r'(?i)^the\s+', '', name).lower()

            def fits(identifier):
                item = found.get(identifier, {})
                labels = [item.get('labels', {}).get('en', {}).get('value', '')]
                return bool(item.get('claims', {}).get(prop)) and any(wanted in re.sub(r'(?i)^the\s+', '', l).lower() for l in labels)

            # Among the matches that have an author/creator, the best known one (most Wikipedia language editions).
            candidates = [h['id'] for h in hits if fits(h['id'])] or [h['id'] for h in hits if found.get(h['id'], {}).get('claims', {}).get(prop)]
            if candidates:
                qid = max(candidates, key=lambda i: len(found.get(i, {}).get('sitelinks', {})))
            entity = found.get(qid, entity)
        if kind == 'country' and entity.get('claims', {}).get('P131'):
            prop = 'P131'                        # "Where is the Eiffel Tower?": the city or district, then the country
        if kind == 'height' and not entity.get('claims', {}).get(prop):
            prop = 'P2044'                       # mountains have an elevation above sea level, not a height
        claims = [c for c in entity.get('claims', {}).get(prop, []) if c.get('rank') != 'deprecated'
                  and not c.get('qualifiers', {}).get('P582')]
        preferred = [c for c in claims if c.get('rank') == 'preferred']
        claims = preferred or claims
        if not claims:
            return None
        label = entity.get('labels', {}).get('en', {}).get('value', name)
        if kind == 'population':
            def date(claim):
                return max((q.get('datavalue', {}).get('value', {}).get('time', '') for q in claim.get('qualifiers', {}).get('P585', [])), default='')
            claim = max(claims, key=date)
            value = claim.get('mainsnak', {}).get('datavalue', {}).get('value', {})
            amount = value.get('amount')
            if amount is None or not date(claim):
                return None  # Undated population must not be presented as current.
            dated = max(claim['qualifiers']['P585'], key=lambda q: q.get('datavalue', {}).get('value', {}).get('time', ''))
            output = f"{label}: {int(float(amount)):,} people (Wikidata figure dated {wikidata_date(dated['datavalue']['value'])})."
        elif kind in ('boiling', 'melting'):
            value = claims[0].get('mainsnak', {}).get('datavalue', {}).get('value', {})
            amount, unit = value.get('amount'), value.get('unit', '').rsplit('/', 1)[-1]
            units = {'Q25267': '°C', 'Q42289': '°F', 'Q11579': 'K'}
            if amount is None or unit not in units:
                return None
            number = float(amount)
            celsius = number if units[unit] == '°C' else (number - 32) * 5 / 9 if units[unit] == '°F' else number - 273.15
            output = f'The {kind} point of {label} is {celsius:.1f} °C ({celsius * 9 / 5 + 32:.1f} °F).'.replace('.0 °', ' °')
        elif kind in ('height', 'length'):
            value = claims[0].get('mainsnak', {}).get('datavalue', {}).get('value', {})
            amount, unit = value.get('amount'), value.get('unit', '').rsplit('/', 1)[-1]
            units = {'Q11573': 'm', 'Q828224': 'km', 'Q3710': 'ft', 'Q253276': 'miles', 'Q174728': 'cm'}
            if amount is None or unit not in units:
                return None
            number = float(amount)
            shown = f'{number:,.0f}' if number >= 100 else f'{number:,.1f}'.rstrip('0').rstrip('.')
            extra = f' ({number * 3.28084:,.0f} ft)' if units[unit] == 'm' else f' ({number * 0.621371:,.0f} miles)' if units[unit] == 'km' else ''
            size = 'high above sea level' if prop == 'P2044' else 'tall' if kind == 'height' else 'long'
            output = f'{label} is {shown} {units[unit]}{extra} {size}.'
        elif kind in ('opened', 'released', 'founded-date'):
            times = sorted(c.get('mainsnak', {}).get('datavalue', {}).get('value', {}).get('time', '') for c in claims)
            first = next((c for c in sorted(claims, key=lambda c: c.get('mainsnak', {}).get('datavalue', {}).get('value', {}).get('time', ''))
                          if c.get('mainsnak', {}).get('datavalue')), None)
            if not first or not times[0]:
                return None
            date = wikidata_date(first['mainsnak']['datavalue']['value'])
            months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
            readable = (f'{int(date[8:10])} {months[int(date[5:7]) - 1]} {date[:4]}' if len(date) == 10 else
                        f'{months[int(date[5:7]) - 1]} {date[:4]}' if len(date) == 7 else date)
            verb = {'opened': 'opened', 'released': 'was first released', 'founded-date': 'was founded'}[kind]
            output = f'{label} {verb} on {readable}.' if len(date) == 10 else f'{label} {verb} in {readable}.'
        elif kind == 'birth':
            dates = {c.get('mainsnak', {}).get('datavalue', {}).get('value', {}).get('time', '') for c in claims}
            if len(dates) != 1 or not next(iter(dates)):
                return None
            value = claims[0]['mainsnak']['datavalue']['value']
            date = wikidata_date(value)
            output = f'{label} was born on {date}.'
        else:
            ids = list(dict.fromkeys(c.get('mainsnak', {}).get('datavalue', {}).get('value', {}).get('id') for c in claims))
            ids = [identifier for identifier in ids if identifier]
            if not ids or len(ids) > 4:
                return None
            labels = self.entities(ids, props='labels')
            names = [labels.get(identifier, {}).get('labels', {}).get('en', {}).get('value') for identifier in ids]
            if not all(names):
                return None
            verbs = dict(wrote='was written by', painted='was painted by', directed='was directed by', composed='was composed by',
                         invented='was invented by', founded='was founded by', designed='was designed by')
            if kind == 'capital':
                output = f"The capital of {label} is {', '.join(names)}."
            elif kind == 'currency':
                output = f"The currency of {label} is the {' and the '.join(names)}."
            elif kind in verbs:
                output = f"{label} {verbs[kind]} {' and '.join(names)}."
            elif kind == 'language':
                output = (f"The official language of {label} is {names[0]}." if len(names) == 1
                          else f"The official languages of {label} are {', '.join(names[:-1])} and {names[-1]}.")
            else:
                country = []
                if prop == 'P131':
                    ids = [c.get('mainsnak', {}).get('datavalue', {}).get('value', {}).get('id') for c in entity.get('claims', {}).get('P17', [])]
                    ids = [i for i in ids if i]
                    labels = self.entities(ids[:1], props='labels') if ids else {}
                    country = [labels.get(i, {}).get('labels', {}).get('en', {}).get('value') for i in ids[:1]]
                    country = [c for c in country if c and c not in names]
                output = f"{label} is in {', '.join(names + country)}."
        return result(output, 'wikidata-faq', [source('Wikidata', 'https://www.wikidata.org/wiki/' + qid,
                      'CC0 1.0', CC0, 'Wikidata contributors')], 'Structured source facts can lag changes; check the linked statement references.')

    def leader(self, text):
        match = re.search(r'\b(president|prime minister|ceo)\s+(?:of|at)\s+(.+)', text, re.I)
        if not match:
            return None
        # "the first female prime minister", "the previous CEO": not the current office holder.
        if re.search(r'(?i)\b(?:first|former|previous|last|female|male|youngest|oldest|longest|shortest|second|third|\d{4}|ever|past)\b',
                     text[:match.start()] + ' ' + text[match.end():]):
            return None
        office, name = match.groups()
        name = re.sub(r'\b(?:right now|today|currently)\b', '', name, flags=re.I).strip(' ?.!,')
        property_id = {'president': 'P35', 'prime minister': 'P6', 'ceo': 'P169'}[office.lower()]
        hits = self.entity_search(name, limit=1)
        if not hits:
            return None
        qid = hits[0]['id']
        entity = self.entities([qid]).get(qid, {})
        statements = entity.get('claims', {}).get(property_id, [])
        today = datetime.now(timezone.utc).strftime('+%Y-%m-%d')
        current = []
        for statement in statements:
            if statement.get('rank') == 'deprecated':
                continue
            qualifiers = statement.get('qualifiers', {})
            ends = [v.get('datavalue', {}).get('value', {}).get('time', '')[:11] for v in qualifiers.get('P582', [])]
            starts = [v.get('datavalue', {}).get('value', {}).get('time', '')[:11] for v in qualifiers.get('P580', [])]
            if any(end and end <= today for end in ends) or any(start > today for start in starts):
                continue
            person = statement.get('mainsnak', {}).get('datavalue', {}).get('value', {}).get('id')
            if person:
                current.append((statement.get('rank') == 'preferred', person))
        if any(preferred for preferred, _ in current):
            current = [(preferred, person) for preferred, person in current if preferred]
        ids = list(dict.fromkeys(person for _, person in current))
        if len(ids) != 1:
            return None  # Ambiguous or missing incumbent: do not guess from an old claim.
        labels = self.entities(ids, props='labels')
        person = labels.get(ids[0], {}).get('labels', {}).get('en', {}).get('value')
        if not person:
            return None
        label = entity.get('labels', {}).get('en', {}).get('value', name)
        role = {'president': 'head of state', 'prime minister': 'head of government', 'ceo': 'CEO'}[office.lower()]
        return result(f'Wikidata currently lists {person} as {role} of {label}.', 'wikidata',
                      [source('Wikidata', 'https://www.wikidata.org/wiki/' + qid, 'CC0 1.0', CC0, 'Wikidata contributors')],
                      'Structured statements can lag real events; the linked record contains the supporting references.')

    def wikipedia(self, text, parsed_question=None):
        parsed_question = parsed_question or self.knowledge_query.parse(text)
        query = parsed_question['subject'] if parsed_question else re.sub(r"(?i)^\s*(?:(?:please\s+)?(?:search(?:\s+the\s+(?:web|internet))?(?:\s+for)?|look\s+up)|(?:what|who|where|when)\s+(?:is|are|was|were)|tell\s+me\s+about|explain|define)\s+", '', text)
        query = query.strip(' ?.!,')[:240]
        def search(subject):
            return self.net.json(WIKI + urlencode(dict(action='query', format='json', list='search', srsearch=subject,
                                srlimit=3, srinfo='suggestion|rewrittenquery|totalhits')), ttl=300)
        data = search(query)
        hits = data.get('query', {}).get('search', [])
        correction = None
        suggestion = data.get('query', {}).get('searchinfo', {}).get('suggestion', '')
        # Only the provider's close, single-token correction is eligible. Keep
        # every other subject token and show the interpretation to the user.
        original_words, proposed_words = content_words(query), content_words(suggestion)
        differences = [(a,b) for a,b in zip(original_words, proposed_words) if a != b]
        if not hits and len(original_words) == len(proposed_words) and len(differences) == 1:
            left, right = differences[0]
            # A suggestion that drops letters ("planet" -> "plant") usually
            # replaces a correctly spelled word with a different one.
            if len(left) >= 5 and len(right) >= len(left) and left[0] == right[0] and edit_distance(left,right) <= 2:
                corrected = search(suggestion)
                if corrected.get('query', {}).get('search'):
                    data = corrected
                    hits = data['query']['search']
                    correction = suggestion
                    if parsed_question:
                        parsed_question = dict(parsed_question, subject=suggestion, terms=proposed_words)
        elif hits and len(original_words) == len(proposed_words) and len(differences) == 1:
            # "megadeath": the provider both suggests "megadeth" and ranks the
            # page with exactly that title first. Both signals together are
            # strong enough to accept a dropped letter; either alone is not.
            left, right = differences[0]
            if (min(len(left), len(right)) >= 5 and left[0] == right[0] and edit_distance(left, right) <= 2
                    and hits[0]['title'].casefold() == suggestion.casefold()):
                correction = hits[0]['title']
                if parsed_question:
                    parsed_question = dict(parsed_question, subject=correction, terms=content_words(correction))
        if not hits:
            return result('I could not find a matching Wikipedia page. Try a more specific subject.', 'not-found', [])
        # Search rank is not evidence that a hit is the requested subject.
        # Do not download, retain or cite an unrelated top-ranked article.
        terms = set(parsed_question['terms'] if parsed_question else content_words(query))
        def relevant(hit):
            stem = lambda word: word[:-1] if word.endswith('s') and len(word) > 3 and not word.endswith('ss') else word
            wanted = {stem(word) for word in terms}
            title_terms = {stem(word) for word in content_words(hit['title'])}
            snippet_terms = {stem(word) for word in content_words(re.sub(r'<[^>]+>', '', hit.get('snippet', '')))}
            return not wanted or wanted <= title_terms or (bool(wanted & title_terms) and wanted <= (snippet_terms | title_terms))
        if correction and not parsed_question:
            parsed_question = dict(kind='definition', subject=correction, terms=content_words(correction), static=static_allowed(text), original=text)
            terms = set(parsed_question['terms'])
        matching = [hit for hit in hits if relevant(hit)]
        if not matching:
            return result('I could not confidently match that subject. Please check the spelling or add a little detail.', 'not-found', [])
        title = matching[0]['title']
        data = self.net.json(WIKI + urlencode(dict(action='query', format='json', prop='extracts|info|revisions',
                             titles=title, exintro=1, explaintext=1, inprop='url', redirects=1, rvprop='ids|timestamp')), ttl=300)
        pages = list(data.get('query', {}).get('pages', {}).values())
        page = next((p for p in pages if p.get('extract')), None)
        if not page:
            raise LookupUnavailable('The matching page has no readable summary')
        full_extract = re.sub(r'\s+', ' ', page['extract']).strip()
        if not intact_text(page['extract']) or not intact_text(title):
            return result('I could not verify a readable answer from the connected source.', 'unreadable', [],
                          'The source text contained a known text-loss marker. Missing characters were not guessed or cached.')
        extract = shorten(full_extract, words=55, sentences=2)
        url = page.get('fullurl') or 'https://en.wikipedia.org/wiki/' + quote(title.replace(' ', '_'))
        if 'disambiguation' in extract[:300].lower() or 'may refer to:' in extract[:300].lower():
            return result(f'{title} has several meanings. Please specify which one you mean.\n{url}', 'ambiguous',
                          [source('Wikipedia', url, 'CC BY-SA 4.0', CCBYSA, 'Wikipedia contributors')])
        revision = page.get('revisions', [{}])[0]
        if static_allowed(text) and revision.get('revid') and page.get('pageid'):
            record = dict(pageid=page['pageid'], title=page.get('title', title), revision=revision['revid'],
                          revision_time=revision.get('timestamp'), retrieved_at=datetime.now(timezone.utc).isoformat(),
                          url='https://en.wikipedia.org/w/index.php?oldid=' + str(revision['revid']), article_url=url,
                          licence='CC BY-SA 4.0', sections=[dict(heading='Introduction', paragraphs=[full_extract[:12000]])])
            if parsed_question and parsed_question['kind'] != 'definition':
                try:
                    article = self.net.json(WIKI + urlencode(dict(action='parse', format='json', oldid=revision['revid'],
                                           prop='text', disableeditsection=1)), ttl=86400, timeout=15)
                    parser = ArticleText()
                    parser.feed(article['parse']['text']['*'])
                    if parser.sections:
                        record['sections'] = parser.sections
                except (LookupUnavailable, KeyError, TypeError, ValueError):
                    pass
            try:
                stored = self.knowledge.remember(record)
                selected = self.knowledge.lookup(parsed_question) if stored else None
                if (selected and selected['route'] == 'chat/local-knowledge'
                        and selected.get('knowledge', {}).get('title') == record['title']
                        and any(item['url'] == record['url'] for item in selected.get('sources', []))):
                    selected['route'] = 'chat/web-wikipedia-extractive'
                    selected['knowledge']['internet_used'] = True
                    selected['details'] += ' This request fetched the provider before selecting the excerpt.'
                    if correction:
                        selected['response'] = f'If you mean "{title}": ' + selected['response']
                        selected['details'] += f' Provider spelling suggestion: {query!r} -> {correction!r}.'
                    return selected
            except (OSError, sqlite3.Error):
                pass
        if parsed_question and parsed_question['kind'] in ('cause', 'mechanism', 'comparison', 'time', 'location', 'historical-event'):
            return result(f'I found background on {title}, but could not verify a direct answer to that question from the available passages.', 'answer-not-found',
                          [source('Wikipedia', url, 'CC BY-SA 4.0', CCBYSA, 'Wikipedia contributors')])
        if not static_allowed(text) and re.search(r'(?i)\b(?:latest|current|currently|now|today|version|price|cost|available)\b', text):
            return result('I could not verify that current information from the connected sources.', 'current-not-found',
                          [source('Wikipedia', url, 'CC BY-SA 4.0', CCBYSA, 'Wikipedia contributors')])
        return result((f'If you mean "{title}": ' if correction else '') + extract, 'wikipedia',
                      [source('Wikipedia', url, 'CC BY-SA 4.0', CCBYSA, 'Wikipedia contributors; excerpt shortened and whitespace normalized by CAEL')],
                      'A source excerpt, not a synthesized answer. Reuse of this excerpt remains under CC BY-SA 4.0.')

    def news(self, text, parsed=None):
        parsed = parsed or self.news_policy.parse(text)
        if parsed is None:
            return None
        from .news_time import unsupported_period
        if unsupported_period(text):
            parsed = dict(parsed, period='unsupported', requested_period=unsupported_period(text))
        if parsed.get('period') == 'unsupported':
            scope = parsed.get('requested_period') or 'that date range'
            return dict(response=f'I cannot verify news for that period ({scope}). '
                        'Ask for recent news, today or yesterday, or name a historical topic and year.',
                        route='chat/web-unsupported-news-period', sources=[],
                        details='The requested period was not replaced with a current-news digest. No news feed was fetched.')
        query = parsed['topic']
        if not query:
            return self.topic_news('', period=parsed.get('period', 'recent')) if parsed.get('period') in ('today', 'yesterday') else self.world_news()
        api_query = {'ai': '"artificial intelligence"', 'uk': '"united kingdom"', 'usa': '"united states"', 'us': '"united states"'}.get(query, query)
        params = dict(query=api_query + ' sourcelang:english', mode='artlist', format='json', maxrecords=8, timespan='1h', sort='datedesc')
        if parsed.get('period') in ('today', 'yesterday'):
            now = datetime.now(timezone.utc)
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            if parsed['period'] == 'yesterday':
                start -= timedelta(days=1)
            end = min(now, start + timedelta(days=1) - timedelta(seconds=1))
            params.pop('timespan')
            params.update(startdatetime=start.strftime('%Y%m%d%H%M%S'), enddatetime=end.strftime('%Y%m%d%H%M%S'))
        url = 'https://api.gdeltproject.org/api/v2/doc/doc?' + urlencode(params)
        try:
            data = self.net.json(url, ttl=900, timeout=20)
        except LookupUnavailable:
            return self.topic_news(query, period=parsed.get('period', 'recent'))
        articles = data.get('articles', [])
        lines = []
        seen = set()
        article_sources = []
        for article in articles:
            link = article.get('url', '')
            if not link.startswith(('https://', 'http://')):
                continue
            title = article.get('title', '')
            key = re.sub(r'\W+', '', title.lower())
            if key in seen or not topical(title, query):
                continue
            seen.add(key)
            lines.append(shorten(title, words=20, sentences=1))
            article_sources.append(source(article.get('domain') or 'Article', link, 'Publisher article rights retained; link metadata via GDELT',
                                          'https://www.gdeltproject.org/about.html#termsofuse', 'Publisher article linked only; body and images not fetched'))
            if len(lines) == 3:
                break
        text = f'{query.title()} — recent headlines:\n\n' + '\n\n'.join(lines) if lines else f'I found no verified recent headlines matching {query}. Try a broader topic.'
        if not lines:
            return self.topic_news(query, period=parsed.get('period', 'recent'))
        return result(text, 'news', article_sources + [source('GDELT', 'https://www.gdeltproject.org/', 'GDELT free commercial terms',
                      'https://www.gdeltproject.org/about.html#termsofuse', 'The GDELT Project')],
                      'Headlines and links only. Publisher article text and images are not downloaded or relicensed.')

    def topic_news(self, topic, period='recent'):
        today = datetime.now(timezone.utc).date()
        pages = [today.strftime('%B_%Y')]
        previous = today - timedelta(days=6)
        upper = today
        if period == 'today':
            previous = today
        elif period == 'yesterday':
            previous = upper = today - timedelta(days=1)
        if previous.month != today.month:
            pages.append(previous.strftime('%B_%Y'))
        candidates = []
        for page in pages:
            url = WIKI + urlencode(dict(action='parse', format='json', page='Portal:Current_events/' + page, prop='text', disableeditsection=1))
            data = self.net.json(url, ttl=900)
            parser = NewsItems()
            parser.feed(data['parse']['text']['*'])
            for record in parser.records:
                date, text = record['date'], record['text']
                text = re.sub(r'\s*\([^)]*\bshown\)', '', text, flags=re.I)
                clean = re.sub(r'(?:\s*\([^)]*\))+$', '', text).strip()
                if date and previous <= date <= upper and len(clean.split()) > 8 and topical(clean, topic, source_category=record['category']):
                    candidates.append((date, clean, record['category']))
        candidates.sort(key=lambda item: item[0], reverse=True)
        chosen, seen = [], set()
        remaining = 65
        for date, text, category in candidates:
            key = re.sub(r'\W+', '', text.lower())
            summary = shorten(text, words=60, sentences=1)
            count = len(summary.split())
            if key not in seen and not summary.endswith('…') and count + 1 <= remaining and topical(summary, topic, source_category=category):
                chosen.append((date, summary))
                seen.add(key)
                remaining -= count + 1
            if len(chosen) == 3:
                break
        if not chosen:
            label = 'world news' if not topic else 'news about ' + topic
            period_text = period if period in ('today', 'yesterday') else 'the last seven days'
            return result(f'I could not verify {label} for {period_text}. No matching dated summaries were available.', 'news-not-found', [])
        sources = [source('Wikipedia', 'https://en.wikipedia.org/wiki/Portal:Current_events/' + date.strftime('%Y_%B_') + str(date.day),
                          'CC BY-SA 4.0', CCBYSA, 'Wikipedia contributors; selected and shortened by CAEL') for date, _ in chosen]
        text = (topic.title() or 'World news') + ' — recent updates:\n\n' + '\n\n'.join(date.isoformat() + ': ' + text for date, text in chosen)
        return result(text, 'news-wikipedia-topic', sources,
                      'Dated Wikipedia summaries filtered to the requested topic and time window; UTC dates, CC BY-SA 4.0 retained.')

    def world_news(self, topic=''):
        url = WIKI + urlencode(dict(action='parse', format='json', page='Template:In_the_news', prop='text', disableeditsection=1))
        data = self.net.json(url, ttl=900)
        parser = NewsItems()
        parser.feed(data['parse']['text']['*'])
        items, remaining = [], 65
        for text in parser.items:
            text = re.sub(r'\s*\([^)]*\bshown\)', '', text, flags=re.I)
            if len(text.split()) <= 8 or not topical(text, topic):
                continue
            summary = shorten(text, words=60, sentences=1)
            count = len(summary.split())
            if not summary.endswith('…') and count <= remaining and topical(summary, topic):
                items.append(summary)
                remaining -= count
            if len(items) == 3:
                break
        if not items:
            return result(f'I could not verify recent headlines about {topic or "world news"}. The topic feed is unavailable and the current digest has no matching items.', 'news-not-found', [])
        link = 'https://en.wikipedia.org/wiki/Template:In_the_news'
        heading = topic.title() if topic else 'World news'
        return result(heading + ' — current digest:\n\n' + '\n\n'.join(items), 'news-wikipedia',
                      [source('Wikipedia', link, 'CC BY-SA 4.0', CCBYSA, 'Wikipedia contributors; digest text reformatted by CAEL')],
                      'Wikipedia current digest, filtered to the requested topic. Events may be from earlier days; not a live wire feed. Text remains CC BY-SA 4.0.')

    def explain(self, request):
        """Teach from the matching article's relevant sections, not its one-line definition."""
        subjects = ([request['title']] if request['title'] else []) + [request['subject']]
        if request['focus'] == 'rules' and not request['title']:
            subjects.insert(0, 'rules of ' + request['subject'])   # "Rules of chess" teaches better than "Chess"
        for subject in subjects:
            data = self.net.json(WIKI + urlencode(dict(action='query', format='json', list='search', srsearch=subject,
                                 srlimit=5, srinfo='suggestion')), ttl=300)
            hits = data.get('query', {}).get('search', [])
            suggestion = data.get('query', {}).get('searchinfo', {}).get('suggestion', '')
            wanted = {w.rstrip('s') for w in content_words(subject)}
            title = next((h['title'] for h in hits if wanted <= {w.rstrip('s') for w in content_words(h['title'])}), None)
            if title is None and hits and suggestion and hits[0]['title'].casefold() == suggestion.casefold():
                title = hits[0]['title']
            if title is None:
                continue
            article = self.net.json(WIKI + urlencode(dict(action='parse', format='json', page=title, prop='text|revid',
                                    disableeditsection=1, redirects=1)), ttl=86400, timeout=15)
            parser = ArticleText()
            parser.feed(article['parse']['text']['*'])
            composed = explain.compose(title, parser.sections, request['focus'])
            if not composed:
                continue
            url = 'https://en.wikipedia.org/wiki/' + quote(article['parse'].get('title', title).replace(' ', '_'))
            return result(composed, 'wikipedia-explained',
                          [source('Wikipedia', url, 'CC BY-SA 4.0', CCBYSA, 'Wikipedia contributors; sections selected and shortened by CAEL')],
                          f'Explanation assembled from the sections of "{title}" that match what was asked ({request["focus"]}). '
                          'Quoted text, not CAEL\'s own wording. Reuse remains under CC BY-SA 4.0.')
        return None

    def respond(self, text, messages=None):
        from .factual_context import resolve,needs_topic
        interpreted,context=resolve(text,messages,self.knowledge_query)
        if context is None and needs_topic(text):
            return dict(route='chat/factual-clarify',response='Which topic do you mean? Name it so I can check the answer.',sources=[],
                        details='No unambiguous public subject was found in this conversation; no internet request was made.')
        parsed=self.knowledge_query.parse(interpreted) if context else None
        # A resolved "How does it work?" must keep the established local-first
        # behavior instead of triggering an article fetch solely after expansion.
        answer=self.knowledge.lookup(parsed) if parsed and parsed['static'] else None
        if answer is None:answer=self._respond(interpreted,messages)
        # "When was X born?" answered by a local passage with no year in it (e.g. about X's parents): the date was
        # asked for, so check the structured birth date instead. Local answers that do contain one stay first.
        if (answer is not None and answer.get('route') == 'chat/local-knowledge' and re.match(r'(?i)^\s*when was .+ born\b', interpreted)
                and not re.search(r'(?i)\b(?:born|baptised|baptized)\b[^.]{0,60}\b(?:1\d{3}|20\d\d)\b', answer.get('response', ''))):
            try:
                exact = self.structured_faq(interpreted)
            except (LookupUnavailable, KeyError, TypeError, ValueError, IndexError):
                exact = None
            answer = exact or answer
        if answer is not None and context:
            answer=dict(answer,details=answer.get('details','')+'\nFollow-up topic from this chat: '+context['subject']+'. Question interpreted as: '+context['question'])
        return answer

    def _respond(self, text, messages=None):
        text = canonical_question(text)
        text = re.sub(r'(?i)^(?:can|could|would) you (?:please )?(?=(?:search|look up|check|tell me))', '', text)
        from .news_time import historical_question, unsupported_period
        historical = historical_question(text)
        if historical:
            local = self.knowledge.lookup(historical)
            if local:
                return local
            try:
                return self.wikipedia(text, parsed_question=historical)
            except (LookupUnavailable, KeyError, TypeError, ValueError, IndexError):
                return result('I could not verify that historical event from the connected sources just now.', 'unavailable', [])
        request = self.request_policy.parse(text)
        # An explicit reference search must not become weather/news solely from
        # an out-of-domain classifier guess. Domain-specific requests still use
        # their existing providers rather than encyclopedia background.
        explicit_reference = EXPLICIT_WEB.search(text) and not re.search(
            r'(?i)\b(?:news|headlines|updates?|weather|forecast|temperature|rain|snow|wind|sports?|scores?|fixtures|standings)\b', text)
        if explicit_reference:
            request = dict(intent='faq', subject='')
        sport_result = re.search(r'(?i)\b(?:scores?|fixtures|standings|league table|last game|next game|next match|f1 results)\b|\bwho won\b.*\b(?:match|game|final|race|cup|championship|tournament)\b|\b(?:football|soccer|basketball|nba|nfl|f1|cricket|tennis|hockey)\b.*\bresults\b', text)
        score_definition = re.fullmatch(r'(?i)(?:what is|define|explain) (?:an? |the )?(?:score|fixture|fixtures|standings)[?.!]*', text)
        # A result from a past year is history, not a live score: "Who won the 2022 World Cup?".
        past_year = any(int(y) < datetime.now(timezone.utc).year for y in re.findall(r'\b(19\d\d|20\d\d)\b', text))
        if sport_result and not score_definition and not past_year:
            return result('I cannot verify live scores, fixtures or standings with the connected sources. Ask for sports news instead.', 'unsupported-sports', [])
        if re.search(r'\b(?:stock|crypto|bitcoin|ethereum|btc|eth)\b.*\b(?:price|worth|value)\b|\b(?:price|value)\b.*\b(?:stock|crypto|bitcoin|ethereum|btc|eth)\b|\b(?:live score|last game|next game|f1 results)\b', text, re.I):
            return result('I do not have a verified free commercial feed for live prices or sports results. I will not substitute an old encyclopedia entry for live data.', 'unsupported', [])
        parsed_news = self.news_policy.parse(text)
        if parsed_news and parsed_news.get('period') == 'unsupported':
            return self.news(text, parsed_news)
        if request['intent'] in ('weather', 'faq'):
            parsed_news = None
        elif request['intent'] == 'sports' and not parsed_news:
            parsed_news = dict(topic=request['subject'] or 'sports', limit=3, max_words=75, period='recent', learned=True)
        followup = re.fullmatch(r'(?i)(?:what|how) about (.+?)[?.!]*', text)
        if followup and messages:
            previous = next((message['content'] for message in reversed(messages[:-1]) if message.get('role') == 'user'), '')
            previous_news = self.news_policy.parse(previous)
            if previous_news:
                period = 'yesterday' if re.search(r'(?i)\byesterday\b', text) else 'today' if re.search(r'(?i)\btoday\b', text) else previous_news.get('period', 'recent')
                scope = unsupported_period(text)
                if scope:
                    period = 'unsupported'
                topic = re.sub(r'(?i)\b(?:today|yesterday|recent|latest)\b', '', followup[1]).strip(' ?.!,').lower()[:180]
                if not topic:
                    topic = previous_news['topic']
                    if previous_news.get('period') == 'unsupported' and not topic:
                        period = 'unsupported'  # Ask for an explicit topic rather than invent a world-news scope.
                parsed_news = dict(topic=topic, limit=3, max_words=75, learned=True,
                                   period=period, requested_period=scope or previous_news.get('requested_period'))
        if parsed_news is not None:
            try:
                return self.news(text, parsed_news)
            except (LookupUnavailable, KeyError, TypeError, ValueError, IndexError):
                return result('I could not verify the news feed right now. Please try again shortly.', 'unavailable', [])
        parsed_question = self.knowledge_query.parse(text)
        if parsed_question and parsed_question['static'] and parsed_question['kind'] == 'mechanism':
            local = self.knowledge.lookup(parsed_question)
            if local:
                return local
        request_to_explain = explain.parse(text)
        if request_to_explain:
            try:
                taught = self.explain(request_to_explain)
            except (LookupUnavailable, KeyError, TypeError, ValueError, IndexError):
                taught = None   # fall back to the ordinary lookup (local knowledge first)
            if taught:
                return taught
        parsed_question = self.knowledge_query.parse(text)
        if parsed_question and not parsed_question['terms'] and messages and re.search(r'(?i)\b(?:it|that|this)\b', text):
            previous_text = next((m['content'] for m in reversed(messages[:-1]) if m.get('role') == 'user'), '')
            previous = self.knowledge_query.parse(previous_text)
            if previous and previous['static']:
                parsed_question = dict(parsed_question, subject=previous['subject'], terms=previous['terms'])
        if parsed_question and parsed_question['static']:
            local = self.knowledge.lookup(parsed_question)
            if local:
                return local
        conceptual = bool(parsed_question and parsed_question['kind'] in ('definition', 'cause', 'mechanism')
                          and re.match(r'(?i)^(?:what (?:is|are|causes)|why|how (?:does|do)|explain|define)\b', text)
                          and not re.search(r'(?i)\b(?:today|tomorrow|tonight|now|forecast for|weather in|weather like|weather outside)\b', text))
        # Founding/invention date questions are encyclopedic, even when the
        # learned request classifier guesses weather from "when ... formed".
        conceptual = conceptual or bool(parsed_question and parsed_question.get('event'))
        # The learned classifier alone over-fires on "if", "when", "cold"... ("If it rains, the ground gets wet. Is the
        # ground wet?"); trust it only for a short single question that mentions the weather itself.
        guessed = (request['intent'] == 'weather' and len(text.split()) <= 12 and not re.search(r'[.!?]\s+\S', text.strip())
                   and re.search(r'(?i)\b(?:rain(?:ing|y)?|snow(?:ing|y)?|sunny|cloudy|windy|storm(?:y)?|umbrella|degrees|hot outside|cold outside|warm outside)\b', text)
                   and not re.search(r'(?i)^\s*(?:if|why|can|does|do|is the following)\b', text))
        if not conceptual and (guessed or re.search(r'\b(?:weather|forecast|temperature)\b', text, re.I)):
            method = self.weather
        elif re.search(r'\b(?:news|headlines)\b', text, re.I):
            return None  # Creative/code/definition requests containing "news" are not current-news lookups.
        elif parsed_question or re.search(r'^\s*(?:what|who|when|where|why|which|how (?:old|many|much|long)|explain|define|tell me about|(?:please )?(?:search|look up))\b', text, re.I):
            method = self.wikipedia
        else:
            return None
        if re.search(r'\b(?:you|your|my|i|story)\b', text, re.I) or re.search(r'\b(?:write|debug|fix|create|generate)\b.*\b(?:python|javascript|function|code|script)\b', text, re.I):
            return None
        try:
            if method == self.wikipedia:
                try:                                     # a Wikidata miss or outage falls through to the encyclopedia
                    leader = self.structured_faq(text) or self.leader(text)
                except (LookupUnavailable, KeyError, TypeError, ValueError, IndexError):
                    leader = None
                if leader:
                    return leader
                return self.wikipedia(text, parsed_question=parsed_question)
            return self.weather(text, messages)
        except (LookupUnavailable, KeyError, TypeError, ValueError, IndexError):
            return result('I could not verify that from the internet just now. The source may be unavailable; please try again shortly.', 'unavailable', [])
