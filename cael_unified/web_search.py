"""Web search when CAEL does not know: search, read the pages, pick the sentences that answer, check agreement.

Search providers, in this order, using whichever are available:
  1. SearxNG                     when CAEL_SEARXNG_URL is set (comma-separated instance URLs; JSON format enabled)
  2. ddgs metasearch             when the `ddgs` package is installed (no key, no quota: queries public search
                                 engines' result pages the way SearxNG does)
  3. DuckDuckGo Instant Answers  always (no key; topic summaries and links, not a full web index)
  4. Wikipedia full-text search  always
  5. Brave Search API            only when no full web index above answered and BRAVE_API_KEY is set (paid quota)
Pages are read through Jina Reader (https://r.jina.ai/<url>, clean text, no key needed) or, if that fails, fetched
directly with httpx (public addresses only, size and time limits) and reduced to text.

The answer is never generated: CAEL scores the pages' sentences against the question (shared content words, plus
the kind of answer asked for: a number, a year, a name), takes the best one and says how many different websites
agree on its key answer. Web text is unchecked, so replies say so and link every source. Question text is sent
to the search providers and Jina Reader. No neural model.
"""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import html
from html.parser import HTMLParser
import ipaddress
import math
import os
import re
import socket
import threading
import time
from urllib.parse import quote, urlparse

UA = 'CAEL/0.3.2 (+https://github.com/Vovala14/CAEL; non-neural assistant)'
STOP = set('a an the of to in on at for with by from as is are was were be been being do does did what which who whom whose why how '
           'when where there their they it its this that these those and or but if then than so very much many can could would '
           'should will shall may might must about into over under after before during tell me please know give find out i you '
           'we he she my your our his her'.split())
NUMBER_WORDS = r'(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|twenty|thirty|forty|fifty|hundred|thousand|million|billion)'
_CACHE = OrderedDict()
_LOCK = threading.Lock()
_RECENT = []                      # timestamps of recent searches, for a global rate limit


class Result:
    def __init__(self, title, url, snippet, provider):
        self.title, self.url, self.snippet, self.provider = title, url, snippet, provider

    def domain(self):
        return (urlparse(self.url).hostname or '').removeprefix('www.')


def cached(key, ttl, make):
    now = time.time()
    with _LOCK:
        hit = _CACHE.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    value = make()
    with _LOCK:
        _CACHE[key] = (now, value)
        while len(_CACHE) > 400:
            _CACHE.popitem(last=False)
    return value


def client():
    import httpx
    return httpx.Client(headers={'User-Agent': UA}, timeout=10, follow_redirects=False)


# ---------------------------------------------------------------- search providers

def brave(query):
    key = os.environ.get('BRAVE_API_KEY', '').strip()
    if not key:
        return []
    with client() as http:
        r = http.get('https://api.search.brave.com/res/v1/web/search', params=dict(q=query, count=8),
                     headers={'Accept': 'application/json', 'X-Subscription-Token': key})
        r.raise_for_status()
        return [Result(x.get('title', ''), x['url'], re.sub(r'<[^>]+>', '', x.get('description', '')), 'Brave Search')
                for x in r.json().get('web', {}).get('results', []) if x.get('url', '').startswith('http')]


def searxng(query):
    out = []
    for base in [u.strip().rstrip('/') for u in os.environ.get('CAEL_SEARXNG_URL', '').split(',') if u.strip()]:
        try:
            with client() as http:
                r = http.get(base + '/search', params=dict(q=query, format='json', language='en'))
                r.raise_for_status()
                out = [Result(x.get('title', ''), x['url'], x.get('content', ''), 'SearxNG')
                       for x in r.json().get('results', [])[:8] if x.get('url', '').startswith('http')]
        except Exception:
            continue
        if out:
            break
    return out


def metasearch(query):
    """The `ddgs` library (MIT): web results from public search engines, no API key or monthly quota. Engines may
    still slow down very frequent queries, so CAEL's own limit of 30 searches a minute stays in place."""
    try:
        from ddgs import DDGS
    except ImportError:
        return []
    hits = DDGS(timeout=10).text(query, region='us-en', safesearch='moderate', max_results=10) or []
    return [Result(h.get('title', ''), h['href'], h.get('body', ''), 'ddgs metasearch')
            for h in hits if str(h.get('href', '')).startswith('http')][:8]


def duckduckgo(query):
    """DuckDuckGo Instant Answer API: an abstract (with its source) and related topic links."""
    with client() as http:
        r = http.get('https://api.duckduckgo.com/', params=dict(q=query, format='json', no_html=1, skip_disambig=1, t='cael'))
        r.raise_for_status()
        data = r.json()
    out = []
    if data.get('AbstractText') and data.get('AbstractURL'):
        out.append(Result(data.get('Heading', ''), data['AbstractURL'], data['AbstractText'], 'DuckDuckGo (' + (data.get('AbstractSource') or 'source') + ')'))
    if data.get('Answer'):
        out.append(Result('DuckDuckGo answer', 'https://duckduckgo.com/?q=' + quote(query), str(data['Answer']), 'DuckDuckGo'))
    for topic in (data.get('Results') or []) + (data.get('RelatedTopics') or []):
        if isinstance(topic, dict) and topic.get('FirstURL') and topic.get('Text'):
            out.append(Result(topic['Text'][:80], topic['FirstURL'], topic['Text'], 'DuckDuckGo'))
        if len(out) >= 6:
            break
    return out


def wikipedia(query):
    with client() as http:
        r = http.get('https://en.wikipedia.org/w/api.php', params=dict(action='query', format='json', list='search', srsearch=query,
                                                                       srlimit=5, srnamespace=0))
        r.raise_for_status()
        hits = r.json().get('query', {}).get('search', [])
    return [Result(h['title'], 'https://en.wikipedia.org/wiki/' + quote(h['title'].replace(' ', '_')),
                   re.sub(r'<[^>]+>', '', html.unescape(h.get('snippet', ''))), 'Wikipedia') for h in hits]


PROVIDERS = (('SearxNG', searxng), ('ddgs metasearch', metasearch), ('DuckDuckGo', duckduckgo), ('Wikipedia', wikipedia),
             ('Brave Search', brave))
# Providers that search the whole web (not only topic summaries or one encyclopedia).
WEB_INDEXES = ('SearxNG', 'ddgs metasearch', 'Brave Search')


def search(query):
    def run():
        results, used = [], []
        for name, provider in PROVIDERS:
            if name == 'Brave Search' and any(u in WEB_INDEXES for u in used):
                continue                                 # the paid API only when the free web indexes failed
            try:
                found = provider(query)
            except Exception:
                found = []
            if found:
                used.append(name)
            for r in found:
                if r.url not in {x.url for x in results}:
                    results.append(r)
            if len(results) >= 8 and name in WEB_INDEXES:
                break                                    # a full web index answered; no need for the topic APIs
        return results, used
    return cached(('search', query.lower()), 6 * 3600, run)


# ---------------------------------------------------------------- reading pages

class _Text(HTMLParser):
    SKIP = {'script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'noscript', 'svg'}

    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in ('p', 'br', 'li', 'h1', 'h2', 'h3', 'tr', 'div'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def public_host(url):
    """Direct fetches only go to public internet addresses (never this machine or a private network)."""
    host = urlparse(url).hostname
    if not host or urlparse(url).scheme not in ('http', 'https'):
        return False
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except OSError:
        return False
    return all(ipaddress.ip_address(a.split('%')[0]).is_global for a in addresses)


def read(url):
    """Clean page text: Jina Reader first, then a direct, guarded fetch."""
    def run():
        try:
            with client() as http:
                r = http.get('https://r.jina.ai/' + url, headers={'Accept': 'text/plain', 'X-Return-Format': 'text'}, timeout=15)
                if r.status_code == 200 and len(r.text) > 300:
                    return r.text[:200000]
        except Exception:
            pass
        if not public_host(url):
            return ''
        try:
            with client() as http:
                r = http.get(url, timeout=10)
                if r.status_code != 200 or 'html' not in r.headers.get('content-type', '') or len(r.content) > 3_000_000:
                    return ''
                parser = _Text()
                parser.feed(r.text)
                return re.sub(r'\n\s*\n+', '\n', ''.join(parser.parts))[:200000]
        except Exception:
            return ''
    return cached(('read', url), 24 * 3600, run)


# ---------------------------------------------------------------- choosing the answer

def stem(word):
    for ending in ('ing', 'ies', 'es', 's', 'ed'):
        if len(word) > len(ending) + 2 and word.endswith(ending):
            base = word[:-len(ending)]
            if ending in ('ing', 'ed') and len(base) > 2 and base[-1] == base[-2] and base[-1] not in 'ls':
                base = base[:-1]                     # "winning" -> "win", "stopped" -> "stop"
            return base
    return word


def terms(text):
    """Content words, stemmed; hyphenated words also count as their parts ("first-generation" -> first, generation)."""
    import unicodedata
    plain = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode()      # "Reykjavík" -> "Reykjavik"
    words = re.findall(r"[a-z0-9][a-z0-9'-]*", plain.lower())
    words += [part for w in words if '-' in w for part in w.split('-')]
    return [stem(IRREGULAR.get(w, w)) for w in words if w not in STOP and len(w) > 1]


# Irregular past forms count as the asked verb: "When did the Berlin Wall fall?" ... "the Berlin Wall fell".
IRREGULAR = {'fell': 'fall', 'fallen': 'fall', 'sank': 'sink', 'sunk': 'sink', 'began': 'begin', 'begun': 'begin', 'won': 'win',
             'wrote': 'write', 'written': 'write', 'built': 'build', 'died': 'die', 'found': 'find', 'made': 'make', 'took': 'take',
             'went': 'go', 'gone': 'go', 'gave': 'give', 'given': 'give', 'ran': 'run', 'sang': 'sing', 'sung': 'sing', 'drew': 'draw',
             'drawn': 'draw', 'flew': 'fly', 'flown': 'fly', 'rose': 'rise', 'risen': 'rise', 'lost': 'lose', 'led': 'lead', 'held': 'hold',
             'opened': 'open', 'ended': 'end', 'started': 'start', 'released': 'release', 'invented': 'invent', 'discovered': 'discover',
             'founded': 'found', 'designed': 'design', 'composed': 'compose', 'painted': 'paint', 'directed': 'direct'}


def kind_of(question):
    q = question.lower()
    if re.match(r'(?:how (?:many|much|long|tall|far|old|big|heavy|fast|deep|high))', q):
        return 'number'
    if re.match(r'(?:when|(?:in )?what year|which year)', q):
        return 'year'
    if re.match(r'who (?:is|was|are|were) (?:an? |the )?[A-Z]', question.strip()[:1].lower() + question.strip()[1:]) and \
            not re.search(r'(?i)\b(?:ceo|president|founder|leader|head|director|author|owner|king|queen|mayor|inventor)\b', q):
        return 'other'                                   # "Who is Hayao Miyazaki?": a description, not a name
    if re.match(r'who\b', q):
        return 'name'
    if re.match(r'where\b', q):
        return 'place'
    return 'other'


ENDS = re.compile(r'(?im)^\s*(?:#+\s*)?(?:references|notes|see also|external links|further reading|bibliography|sources|citations|footnotes)\s*$')
CITATION = re.compile(r'(?i)^["“\d\s^↑]|retrieved\b|archived\b|\bisbn\b|\bdoi\b|\bpp?\.\s*\d|\bvol\.\s*\d|accessed on|\(\d{4}\)\.\s*["“]|^\W*\d+\s+\d+\s')


def sentences(text):
    """(position, sentence) for the body of a page: no reference lists, citation lines, menus or cookie notices."""
    end = ENDS.search(text)
    text = text[:end.start()] if end and end.start() > 500 else text
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', ' ', text)                    # images
    text = re.sub(r'\[([^\]]+)\]\((?:[^()]|\([^)]*\))*\)', r'\1', text)  # markdown links -> their text
    text = re.sub(r'(?m)^(?:Title|URL Source|Published Time|Markdown Content|Warning):.*$', ' ', text)
    text = re.sub(r'(?m)^\s*(?:#+|[*\-|=>]+)\s*', ' ', text)
    text = re.sub(r'\[\d+\]|\[[a-z]\]|\[citation needed\]|\[edit\]', ' ', text)
    for _ in range(2):                                   # pronunciations and asides: "A sommelier (UK: /ˈsɒm.../), chef de vin"
        text = re.sub(r'\s*\([^()]{0,200}\)', '', text)
    text = re.sub(r'\b(Mr|Mrs|Ms|Dr|St|Jr|Sr|Prof|Gen|Lt|Col|No|vs|etc|U\.S|e\.g|i\.e)\.', r'\1', text)   # not sentence ends
    text = re.sub(r'(?im)^\s*(?:for (?:the|other|a)\b[^\n]*?\bsee\b[^\n]*|this article is about[^\n]*|"[^"\n]+" redirects here[^\n]*|'
                  r'not to be confused with[^\n]*|look up [^\n]*\bin wiktionary[^\n]*|[^\n]*\bat wikipedia\'s sister projects[^\n]*)$', ' ', text)
    index = 0
    for line in text.split('\n'):                        # a line break ends a sentence: captions stay separate
        line = re.sub(r'\s+', ' ', line).strip()
        for s in re.split(r'(?<=[.!?])\s+(?=[A-Z"“])', line):
            s = s.strip()
            if not s:
                continue
            index += 1
            if 6 <= len(s.split()) <= 60 and s[-1:] in '.!' and not CITATION.search(s) and \
                    not re.search(r'(?i)cookie|sign in|log in|subscribe|javascript|privacy policy|all rights reserved|\|', s):
                yield index, s


UNITS = r'(?:m|metres?|meters?|km|kilometres?|kilometers?|ft|feet|foot|miles?|cm|mm|kg|kilograms?|tonnes?|tons?|pounds?|lb|g|grams?|' \
        r'years?|days?|hours?|minutes?|seconds?|people|inhabitants|residents|%|percent|°c|°f|degrees|storeys|stories|floors|km/h|mph)'
NOT_NAMES = {'The', 'This', 'It', 'In', 'On', 'At', 'He', 'She', 'They', 'Its', 'His', 'Her', 'A', 'An', 'Origins', 'History', 'However',
             'After', 'Before', 'During', 'Since', 'When', 'While', 'Although', 'According', 'Today', 'January', 'February', 'March',
             'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'}


LENGTH_UNITS = r'(?:m|metres?|meters?|km|kilometres?|kilometers?|ft|feet|foot|miles?|mi|cm|mm|li)'
NAME = r'((?:[A-Z][a-z\'’-]+|[A-Z]\.)(?:\s+(?:[A-Z][a-z\'’-]+|[A-Z]\.|(?:de|van|von|da|del|le|la)\b))+)'


def new_name(name, question_terms):
    """A name is an answer only if it adds a word the question did not already contain ("Gustave Eiffel" for the Eiffel Tower)."""
    words = name.split()
    return words[0] not in NOT_NAMES and not {stem(w) for w in name.lower().split()} <= set(question_terms)


def key_answer(sentence, kind, question_terms, question=''):
    """The short answer inside a sentence, used to check whether different pages agree."""
    q = question.lower()
    if kind == 'year':
        years = list(re.finditer(r'\b(1\d{3}|20\d\d)\b', sentence))
        if not years:
            return None
        # The year closest to the asked action: "the fall of the Berlin Wall on 9 November 1989 ... reunification in 1990".
        action = re.search(r'\b(\w+ed|fall|fell|wrote|written|built|began|begin|end|start|release|open|die|born|sank|sink|won|win)\b', q)
        if action:
            stem_word = stem(action[1])[:5]
            spots = [m.start() for m in re.finditer(r'\b' + re.escape(stem_word) + r'|\bfell\b|\bsank\b|\bbegan\b', sentence.lower())]
            if spots:
                return min(years, key=lambda y: min(abs(y.start() - s) for s in spots))[1]
        return years[0][1]
    if kind == 'number':
        if re.match(r'how (?:tall|high|long|far|deep|wide)', q):
            follow = LENGTH_UNITS
        elif re.search(r'\bpopulation|how many people|inhabitants\b', q):
            follow = r'(?:people|inhabitants|residents|million|billion)'
        else:
            nouns = '|'.join(re.escape(t) for t in question_terms if len(t) > 2)
            follow = UNITS + (r'|(?:[a-z-]+\s+){0,2}(?:' + nouns + r')[a-z]*' if nouns else '')
        m = re.search(r'\b(\d[\d,]*(?:\.\d+)?|' + NUMBER_WORDS + r')\s*(?:' + follow + r')\b', sentence.lower())
        if not m and 'population' in q:
            m = re.search(r'\bpopulation (?:of|was|is|was estimated at|of about|of around)?\s*(?:about |around |approximately )?(\d[\d,]{3,})', sentence.lower())
        return m[1].replace(',', '') if m else None
    if kind in ('name', 'place'):
        # "designed by Gustave Eiffel", "Jensen Huang is the CEO", "CEO Jensen Huang": the name next to the asked role.
        verb = re.search(r'\b(?:\w+ed|wrote|written|built|founded|invented|discovered|painted|composed|directed|led|ceo|president|founder|'
                         r'made|created|started|owns?|runs?|leads?|plays?|sang|sings?)\b', q)
        if kind == 'name':
            patterns = [r'\bby\s+(?:the\s+)?(?:[a-z]+\s+){0,2}' + NAME]
            role = re.search(r'\b(ceo|president|founder|leader|head|director|chairman|prime minister|king|queen)\b', q)
            if role:
                r_ = r'(?i:' + re.escape(role[1]) + r')'
                patterns += [NAME + r',?\s+(?:is|was|has been|became)\s+(?:the\s+)?(?:\w+\s+){0,2}' + r_,
                             r_ + r'(?:\s+and\s+\w+)?,?\s+' + NAME, NAME + r'\s+\((?:\w+\s+){0,2}' + r_]
            for pattern in patterns:
                m = re.search(pattern, sentence)
                if m:
                    name = m.group(m.lastindex)
                    if new_name(name, question_terms):
                        return name
            if verb is None:
                return None
        # A person needs a first and last name; a winner can be a team or a country ("Argentina won ...").
        person = kind == 'name' and not re.search(r'\b(?:won|win|wins|champion|champions|beat|defeated)\b', q)
        for m in re.finditer(NAME if person else r'\b((?:[A-Z][a-z\'’-]+)(?:\s+(?:[A-Z][a-z\'’-]+|de|of))*)', sentence):
            if new_name(m[1], question_terms):
                return m[1]
    return None


def subject_of(question):
    """The thing the question is about: "Who designed the Eiffel Tower?" -> "Eiffel Tower"."""
    capital = r'(?:[A-Z][\w\'’-]*|[a-z]+[A-Z][\w\'’-]*)'                # "Eiffel", "iPhone"
    caps = re.findall(r'\b((?:' + capital + r'|of|the|de)(?:\s+(?:' + capital + r'|of|the|de))*)', question[1:])
    caps = [c.strip() for c in caps if c.strip() and c.strip().lower() not in ('i', 'the', 'of', 'de') and not re.match(r'(?i)^(?:who|what|when|where|how|which|why)\b', c)]
    caps = [re.sub(r'^(?:the|of)\s+|\s+(?:the|of)$', '', c) for c in caps]
    # "CEO of Nvidia" -> "Nvidia": job titles are what is asked, not the subject.
    caps = [re.sub(r'^(?:CEO|President|Prime Minister|King|Queen|Founder|Leader|Head|Mayor|Governor|Director)\s+of\s+', '', c) for c in caps]
    if caps:
        best = max(caps, key=len)
        year = re.search(r'\b(1\d{3}|20\d\d)\s+(?:the\s+)?' + re.escape(best), question)
        return f'{year[1]} {best}' if year else best          # "2022 World Cup", not every World Cup
    shopping = re.search(r'(?i)\b(?:the|a|an)\s+(?:best|top|good|cheapest|greatest|nicest|most popular)\s+((?:[a-z-]+\s+){0,2}?[a-z-]+?)'
                         r'\s*(?:to (?:buy|get|use|watch|read|learn|visit|play)|for \w+(?: \w+)?|in \w+)?\s*\??$', question)
    if shopping:
        return shopping[1]                                   # "the best phone to buy" -> "phone"
    m = re.search(r'\b(?:the|a|an)\s+((?:[a-z-]+\s+){0,2}[a-z-]+)\s*(?:\?|$|\b(?:released|built|founded|made|invented|written|discovered|start|begin|end|fall)\b)', question.lower())
    if not m:
        m = re.search(r'\b(?:does|do|did|is|are|was|were)\s+(?:an?\s+|the\s+)?((?:[a-z-]+\s+){0,2}[a-z-]+?)(?:\s+(?:have|has|do|does|mean|work|live|eat|cost|weigh|use))?\s*\??$', question.lower())
    subject = m[1] if m else ''
    return re.sub(r'\s+(?:have|has|do|does|mean|work|live|eat|cost|weigh|use|is|are)$', '', subject)


def link(result):
    """A Markdown link naming the page and its website: [Berlin Wall (en.wikipedia.org)](https://...)."""
    title = re.sub(r'[\[\]]', '', (result.title or result.domain()).strip())[:80]
    site = result.domain()
    label = title if site in title.lower() else f'{title} ({site})'
    return f'[{label}]({result.url.replace(" ", "%20").replace(")", "%29")})'


def best_sentences(question, pages, web_index=False):
    q = terms(question)
    if not q:
        return []
    kind = kind_of(question)
    weight = {t: 1.0 + (0.5 if len(t) > 6 else 0) for t in q}
    subject = subject_of(question)
    subject_terms = set(terms(subject))
    winner = bool(re.search(r'(?i)\bwho (?:won|wins|win|beat|defeated)\b|\bwinner of\b', question))
    definition = bool(re.match(r'(?i)\s*(?:what|who)(?:\'s| is| are| was| were| does| do)\s+(?:an?\s+|the\s+)?[\w\s-]+?(?:\s+do|\s+mean|\s+work)?\s*\??$', question)) \
        and kind_of(question) == 'other'
    # Action words of the question ("designed", "released", "fall") count double: the sentence must say the asked thing.
    raw_actions = re.findall(r'\b(\w+ed|fall|fell|wrote|written|built|began|begin|end|start|release|open|die|born|sank|sink|won|win)\b', question.lower())
    actions = {stem(IRREGULAR.get(w, w)) for w in raw_actions} - subject_terms
    scored = []
    def exact_page(result):
        title_terms = set(terms(re.sub(r'\s*\(.*', '', result.title)))
        return bool(subject_terms) and subject_terms <= title_terms and title_terms <= subject_terms | {'the'}
    # Encyclopedia only: when the subject has its own page ("Berlin Wall"), only that page answers; side articles
    # mention it in passing. With a web index (SearxNG, ddgs, Brave) other sites may answer too, if they name the subject.
    if not web_index and any(exact_page(r) for r, _ in pages):
        pages = [(r, t) for r, t in pages if exact_page(r)]
    for rank, (result, text) in enumerate(pages):
        title_terms = set(terms(re.sub(r'\s*\(.*', '', result.title)))
        on_topic = bool(subject_terms) and subject_terms <= title_terms
        exact = exact_page(result)                                          # "Berlin Wall", not "The Wall – Live in Berlin"
        mentions = 0
        for _, s in sentences(text):
            have = set(terms(s))
            # Position counts from the first sentence that names the subject (menus and captions come before it).
            if not subject_terms or subject_terms & have:
                mentions += 1
            position = max(mentions - 1, 0)
            if subject_terms and not on_topic and not subject_terms <= have:
                continue                                 # a side article must name the subject itself
            hit = sum(weight[t] * (2 if t in actions else 1) for t in set(q) if t in have)
            if hit < max(1.0, 0.5 * len(set(q))):
                continue
            score = hit / math.sqrt(max(len(have), 1)) * 3
            score += 1.0 / (1 + position / 8) + 0.3 / (1 + rank)      # opening sentences and top results first
            score += 3.0 if exact else 1.0 if on_topic else 0             # the subject's own page first
            if definition and exact:
                score += 4.0 / (1 + position / 2)                         # "what is X": the page's opening definition
            if winner and re.search(r'\b(?:won|wins|crowned|beat|defeated|champions?|victory|winners?)\b', s, re.I):
                score += 2.0                                              # "Argentina were crowned the champions"
            answer = key_answer(s, kind, q, question)
            if kind != 'other':
                score += 1.5 if answer else -2
            scored.append((score, s, result, answer))
    scored.sort(key=lambda x: -x[0])
    return scored


def script(query):
    """The search, as a stand-alone Python script anyone can run (requires: pip install httpx)."""
    return f'''import os
import httpx

QUERY = {query!r}
HEADERS = {{"User-Agent": "my-search-script/1.0"}}


def search(query):
    """ddgs (no key), then Brave (with BRAVE_API_KEY), a SearxNG instance (CAEL_SEARXNG_URL), DuckDuckGo Instant Answers."""
    try:
        from ddgs import DDGS
        hits = DDGS().text(query, max_results=8)
        if hits:
            return [(h["title"], h["href"]) for h in hits]
    except ImportError:
        pass
    if os.environ.get("BRAVE_API_KEY"):
        r = httpx.get("https://api.search.brave.com/res/v1/web/search", params={{"q": query, "count": 8}},
                      headers={{**HEADERS, "X-Subscription-Token": os.environ["BRAVE_API_KEY"]}}, timeout=10)
        return [(x["title"], x["url"]) for x in r.json().get("web", {{}}).get("results", [])]
    if os.environ.get("CAEL_SEARXNG_URL"):
        r = httpx.get(os.environ["CAEL_SEARXNG_URL"].rstrip("/") + "/search", params={{"q": query, "format": "json"}},
                      headers=HEADERS, timeout=10)
        return [(x["title"], x["url"]) for x in r.json().get("results", [])[:8]]
    r = httpx.get("https://api.duckduckgo.com/", params={{"q": query, "format": "json", "no_html": 1}}, headers=HEADERS, timeout=10)
    data = r.json()
    links = [(data.get("Heading", ""), data["AbstractURL"])] if data.get("AbstractURL") else []
    return links + [(t["Text"], t["FirstURL"]) for t in data.get("RelatedTopics", []) if "FirstURL" in t][:5]


def read(url):
    """Jina Reader returns a page as clean text (free, no key)."""
    return httpx.get("https://r.jina.ai/" + url, headers=HEADERS, timeout=20).text


if __name__ == "__main__":
    words = {{w for w in QUERY.lower().split() if len(w) > 3}}
    for title, url in search(QUERY)[:3]:
        text = read(url)
        best = max(text.split(". "), key=lambda s: len(words & set(s.lower().split())), default="")
        print(f"{{title}}\\n  {{url}}\\n  {{best.strip()[:300]}}\\n")
'''


# ---------------------------------------------------------------- entry points

QUESTION = re.compile(r'(?i)^\s*(?:(?:in|on|at|by|from|for|during|since|until) (?:what|which|whom)|name|what|which|who|whom|whose|when|where|why|how|is|are|was|were|does|do|did|can|could|has|have|'
                      r'tell me about|search(?: the web| online)? for|look up|find out|google)\b')
# Words naming the kind of answer wanted; a sentence that gives the answer need not repeat them.
ANSWER_TYPES = {'year', 'city', 'countri', 'country', 'person', 'place', 'date', 'day', 'month', 'name', 'kind', 'type',
                'has', 'have', 'had', 'did', 'doe', 'does', 'mani', 'many', 'much'}
PERSONAL = re.compile(r'(?i)\b(?:i|me|my|mine|myself|you|your|yours|yourself|we|our|us)\b')


def says_asked(question, text, subject_terms=None):
    """Whether a passage says the asked thing, not only names the subject: "Scotland is a country ..." does not answer
    "What is the national animal of Scotland?". Answer-type words (year, city ...) need not appear."""
    if subject_terms is None:
        subject_terms = set(terms(subject_of(question)))
    focus = set(terms(question)) - subject_terms - ANSWER_TYPES
    need = len(focus) if len(focus) <= 2 else -(-len(focus) * 3 // 5)
    return len(focus & set(terms(text))) >= need


def should_search(text):
    """A factual question CAEL could not answer: not personal, not about the future, not small talk."""
    if len(text) > 300 or '```' in text or not QUESTION.match(text):
        return False
    if PERSONAL.search(re.sub(r'(?i)^\s*(?:can|could) you (?:please )?(?:tell me|search|look up|find)\b', '', text)):
        return False
    future = [int(y) for y in re.findall(r'\b(20\d\d)\b', text) if int(y) > time.gmtime().tm_year]
    if future:
        return False
    # Buying advice ("the best phone to buy", "which laptop should I get") is not a fact a web sentence can settle.
    if re.search(r'(?i)\b(?:best|top|cheapest|good)\b.*\b(?:to buy|to get|should i (?:buy|get)|for me)\b|\bwhich\b.*\bshould i\b|\brecommend\b', text):
        return False
    return len(terms(text)) >= 1


def answer(text):
    """Search the web for a question; None if nothing on the pages answers it."""
    question = re.sub(r'(?i)^\s*(?:please\s+)?(?:can you\s+|could you\s+)?(?:search(?: the web| online)? for|look up|find out|google)\s+', '', text).strip()
    query = re.sub(r'[?!.]+$', '', question)
    with _LOCK:
        now = time.time()
        _RECENT[:] = [t for t in _RECENT if now - t < 60]
        if len(_RECENT) >= 30:                           # be polite to the free services: at most 30 searches a minute
            return None
        _RECENT.append(now)
    results, used = search(query)
    subject = subject_of(question)
    if subject:
        try:                                                 # the subject's own encyclopedia page, looked up directly
            own = [r for r in wikipedia(subject)[:2] if r.url not in {x.url for x in results}]
        except Exception:
            own = []
        results = own + results
    if not results:
        return None
    subject_terms = set(terms(subject))
    def closeness(r):
        title = set(terms(re.sub(r'\s*\(.*', '', r.title)))
        if subject_terms and subject_terms <= title and title <= subject_terms | {'the'}:
            return 0                                         # exactly the subject's page ("Sommelier")
        return 1 if subject_terms and subject_terms <= title else 2   # then pages about it ("Sommelier knife")
    results = sorted(results, key=closeness)
    top = results[:4]
    with ThreadPoolExecutor(max_workers=4) as pool:
        texts = list(pool.map(lambda r: read(r.url), top))
    pages = [(r, t if t else r.snippet) for r, t in zip(top, texts)]       # a search snippet only when the page could not be read
    web_index = any(p in used for p in WEB_INDEXES)
    if web_index:
        # A web index's own result descriptions often answer the question directly ("Argentina won ... on penalties");
        # each counts for its own website.
        pages += [(r, r.snippet if r.snippet.rstrip().endswith(('.', '!', '?')) else r.snippet.rstrip() + '.')
                  for r in results[:8] if r.provider in WEB_INDEXES and len(r.snippet.split()) >= 6]
    scored = best_sentences(question, pages, web_index)
    # The sentence must say the asked thing, not only name the subject: "Scotland is a country ..." does not answer
    # "What is the national animal of Scotland?". Answer-type words (year, city ...) need not appear.
    scored = [x for x in scored if says_asked(question, x[1], subject_terms)]
    if not scored or scored[0][0] < 1.6:
        return None
    best_score, best, source, key = scored[0]
    # Agreement: different websites if a web index was used, otherwise different pages.
    close = [x for x in scored[:15] if x[0] >= 0.6 * best_score]           # only near-best sentences may confirm
    if key:
        same = [r for s, _, r, k in close if k and k.lower() == key.lower()]
    else:
        # No extracted name/number/year: the first new word of the best sentence ("Diamond", "Iron", "Mars") is its
        # answer, and other near-best sentences confirm it when they say the same word.
        asked = set(terms(question))
        new = [t for t in terms(best) if t not in asked]
        head = new[0] if new else None
        same = [source] + [r for _, sent, r, _ in close if r is not source and head and head in terms(sent)[:6]]
    sites = {r.domain() for r in same}
    agree = sorted(sites) if len(sites) > 1 else sorted({r.url for r in same})
    links = []
    for r in [source] + [r for _, _, r, k in scored[1:12] if r.domain() in agree and r is not source] + top:
        if r.url not in [l.url for l in links]:
            links.append(r)
        if len(links) >= 3:
            break
    # Confirmed only when different websites agree; pages of one site (all Wikipedia) are not independent.
    confident = len(sites) >= 2
    # Where the data came from, as clickable links in the reply itself.
    shown = [r for r in links if r.domain() in sites] if confident else [source]
    cited = ', '.join(link(r) for r in shown[:3])
    if confident:
        lead = f'From a web search: **{key}**.' if key else 'From a web search:'
        body = (f'{lead}\n\n> {best}\n\n{len(sites)} different websites agree on this.\n\n'
                f'**Sources:** {cited}')
    else:
        body = (f'I don\'t know this for sure. The most relevant sentence I found on the web:\n\n> {best}\n\n'
                f'**Source:** {cited}. It is the only website that said this, and I could not check it, so please verify it there.')
    sources = [dict(source=f'{r.title or r.domain()} ({r.domain()})', url=r.url, licence='see the website',
                    licence_url=r.url, attribution=r.domain()) for r in links]
    details = (f'Searched with {", ".join(used)}; read {len(top)} pages through Jina Reader or a direct fetch; picked the sentence that '
               f'shares the most key words with the question and contains the kind of answer asked for. Web pages are not checked by CAEL. '
               f'Your question was sent to the search services and Jina Reader. No neural model.\n\nThe same search as a Python script:\n'
               f'```python\n{script(query)}```')
    return dict(response=body, route='chat/web-search' + ('' if confident else '-unconfirmed'), sources=sources, details=details,
                search=dict(providers=used, query=query, agreeing_sites=agree))


ASK_SCRIPT = re.compile(r'(?i)^\s*(?:please\s+)?(?:write|create|make|give me|build)\s+(?:me\s+)?(?:a\s+)?(?:python\s+)?(?:script|program|code|function|tool)\s+'
                        r'(?:that|to|which)\s+(?:searches|search|looks up|look up|finds|find)\s+(?:the web|online|the internet|google|duckduckgo)?\s*(?:for\s+)?(.*?)\s*[?.!]*$')


def script_reply(text):
    m = ASK_SCRIPT.match(text)
    if not m or not re.search(r'(?i)\b(?:web|online|internet|search engine|google|duckduckgo|searx|brave)\b', text):
        return None
    query = m[1].strip(' "\'') or 'your question'
    return dict(route='chat/code-web-search', sources=[],
                response=f'```python\n{script(query)}```\nIt searches with the free `ddgs` library (no key), or Brave (if you set '
                         f'`BRAVE_API_KEY`), a SearxNG instance (`CAEL_SEARXNG_URL`) or DuckDuckGo Instant Answers, reads the top pages as clean text with Jina Reader, '
                         f'and prints the sentence from each page that best matches your words. Install with `pip install httpx ddgs`.',
                details='A Python search script written from CAEL\'s search template. No neural model.')
