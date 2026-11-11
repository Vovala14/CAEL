"""Free public search plus bounded page reads and conservative extraction.

DDGS uses explicitly named public search engines, never its encyclopedia-first
auto mode. No paid API or remote reader. Source agreement is not proof.
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

UA = 'CAEL/0.3.6 (+https://github.com/Vovala14/CAEL; non-neural assistant)'
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
    return httpx.Client(headers={'User-Agent': UA}, timeout=4, follow_redirects=False)


# ---------------------------------------------------------------- search providers

def searxng(query):
    out = []
    for base in [u.strip().rstrip('/') for u in os.environ.get('CAEL_SEARXNG_URL', '').split(',') if u.strip()][:1]:
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
    # Each engine is asked on its own: with a combined backend list, one refusing engine fails the whole search.
    def one(engine):
        try:
            return DDGS(timeout=4, verify=True).text(query, region='us-en', safesearch='moderate', max_results=8, backend=engine) or []
        except Exception:
            return []
    # Engines refuse automated queries now and then (measured 2026-11-11: Bing and Yahoo answer most often), so all are
    # asked at once and whatever arrives is used; if every one refuses, Yahoo and then Bing are asked once more.
    with ThreadPoolExecutor(max_workers=5) as pool:
        batches = list(pool.map(one, ('bing', 'yahoo', 'duckduckgo', 'brave', 'mojeek')))
    for engine in ('yahoo', 'bing'):
        if any(batches):
            break
        batches.append(one(engine))
    out, urls = [], set()
    for rank in range(8):                     # interleave engines: each one's top result first
        for hits in batches:
            if rank < len(hits):
                h = hits[rank]
                url = str(h.get('href', ''))
                host = (urlparse(url).hostname or '').removeprefix('www.')
                if not url.startswith('http') or url in urls or host.endswith(('bing.com', 'duckduckgo.com', 'brave.com', 'mojeek.com')):
                    continue                  # ad and redirect links of the engines themselves
                urls.add(url)
                out.append(Result(h.get('title', ''), url, h.get('body', ''), 'ddgs metasearch'))
    return out[:8]


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


PROVIDERS = (('SearxNG', searxng), ('ddgs metasearch', metasearch), ('DuckDuckGo', duckduckgo), ('Wikipedia', wikipedia))
WEB_INDEXES = ('SearxNG', 'ddgs metasearch')

def capabilities():
    from importlib.util import find_spec
    return {'full_web':bool(find_spec('ddgs') or os.environ.get('CAEL_SEARXNG_URL')),
            'ddgs':bool(find_spec('ddgs')),'searxng_configured':bool(os.environ.get('CAEL_SEARXNG_URL')),
            'paid_api':False,'remote_page_reader':False,'reader':'bounded public HTTP text'}

def search(query,force=False,exclude_wikipedia=False):
    from .web_evidence import public_query,excluded
    if os.environ.get('CAEL_WEB_SEARCH','1')=='0' or not public_query(query):return [],[]
    cache_key=('search',query.casefold(),exclude_wikipedia)
    now=time.time()
    with _LOCK:
        hit=_CACHE.get(cache_key)
        if not force and hit and now-hit[0]<900:return hit[1]
        _RECENT[:]=[value for value in _RECENT if now-value<60]
        if len(_RECENT)>=30:return [],['local rate limit reached']
        _RECENT.append(now)
    results=[];used=[];urls=set();available=capabilities()
    for name,provider in PROVIDERS:
        if name=='SearxNG' and not available['searxng_configured']:continue
        if name=='ddgs metasearch' and not available['ddgs']:continue
        if name=='Wikipedia' and exclude_wikipedia:continue
        try:found=provider(query)
        except Exception:used.append(name+': unavailable');continue
        used.append(name+(': results' if found else ': no results'))
        for r in found:
            if r.url in urls or (exclude_wikipedia and excluded(r.url)):continue
            urls.add(r.url);results.append(r)
        if len(results)>=4 and name in WEB_INDEXES:break
    # Empty/network failures are not cached as a six-hour negative answer.
    if results:
        with _LOCK:
            _CACHE[cache_key]=(now,(results,used))
            while len(_CACHE)>400:_CACHE.popitem(last=False)
    return results,used

def public_host(url):
    from .web_fetch import destination,Blocked
    try:destination(url);return True
    except (Blocked,ValueError):return False

def read_page(url,force=False):
    from .web_fetch import fetch
    key=('page',url)
    with _LOCK:
        hit=_CACHE.get(key)
        if not force and hit and time.time()-hit[0]<300:return dict(hit[1],cached=True)
    value=fetch(url)
    if value.get('status')=='read':
        with _LOCK:
            _CACHE[key]=(time.time(),value)
            while len(_CACHE)>400:_CACHE.popitem(last=False)
    return value

def read(url):
    return read_page(url).get('text','')

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


def best_sentences(question, pages, web_index=False, sentence_reader=None):
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
        for _, s in (sentence_reader or sentences)(text):
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
    # Return a reproducible call to the installed reader; never execute a script.
    return ('from cael_unified import web_search\n'
            'answer = web_search.answer('+repr(query)+', force=True)\n'
            'print(answer["response"] if answer else "No public question")\n')


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


RECENT = re.compile(r'(?i)\b(?:latest|most recent|newest|current(?:ly)?|right now|these days|this (?:year|month|week)|nowadays|today)\b')


def answer(text,force=False,exclude_wikipedia=False):
    from .web_evidence import answer as grounded
    return grounded(text,force=force,exclude_wikipedia=exclude_wikipedia)


ASK_SCRIPT = re.compile(r'(?i)^\s*(?:please\s+)?(?:write|create|make|give me|build)\s+(?:me\s+)?(?:a\s+)?(?:python\s+)?(?:script|program|code|function|tool)\s+'
                        r'(?:that|to|which)\s+(?:searches|search|looks up|look up|finds|find)\s+(?:the web|online|the internet|google|duckduckgo)?\s*(?:for\s+)?(.*?)\s*[?.!]*$')

def script_reply(text):
    m = ASK_SCRIPT.match(text)
    if not m or not re.search(r'(?i)\b(?:web|online|internet|search engine|google|duckduckgo|searx|brave)\b', text):
        return None
    query = m[1].strip(' "\'') or 'your question'
    return dict(route='chat/code-web-search', sources=[],
                response=f'```python\n{script(query)}```\nThis uses CAEL’s installed free search and bounded public-page reader. '
                         'It reports source support and conflicts rather than treating snippets as verified answers. No paid API or remote page-reader service.',
                details='A Python search script written from CAEL\'s search template. No neural model.')
