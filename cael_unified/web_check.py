"""When CAEL does not know: search the web, check the answer, then reply.

Any reply that amounts to "I don't know" ("I do not have a reliable answer...", "I could not verify...", "Tell me a bit
more...") to a turn that asks for information is replaced by a checked web answer, when one can be found:

1. Query: the content words of the question; a follow-up ("Which one is more dangerous?", "I water them every day.")
   borrows the topic nouns of the earlier turns, so it searches "crocodile alligator dangerous".
2. Search, in parallel: Wikipedia, Simple English Wikipedia and Wikibooks/Wikivoyage (Wikimedia, CC BY-SA 4.0), and
   the open web through public search engines (Brave, DuckDuckGo and Bing via the ddgs metasearch library, plus
   DuckDuckGo instant answers; no API key, no paid service). The top open-web results (one page per publisher, no
   social/video sites) are read with web_fetch, which only connects to public addresses and checks every redirect.
3. Read: the plain text of the top pages; every window of one to three sentences is scored by how much of the
   question it covers (rare words count more), whether it answers the kind of question asked (a "why" wants
   "because / due to / so"), and whether the page is about the question's main noun.
4. Check: the best passage must cover the question's key noun and most of its weight. It is then compared with the
   other pages read: when a passage from a different page says the same thing (shares most of its rare words), the
   reply says the sources agree; with a single strong source it says so; otherwise CAEL reports what it searched and
   that it found no clear answer, instead of guessing. A supporting page must come from a different publisher and
   must not be a near-copy of the same text (many sites copy Wikipedia word for word).

Page text is untrusted data: it is only scored and quoted, never followed. Open-web quotes are kept short (at most
two sentences, 50 words) with the publisher and link. No neural model. CAEL_WEB_SEARCH=0 switches the open web off.
"""
import math
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode, urlparse

from .network import NETWORK, LookupUnavailable

SITES = [('en.wikipedia.org', 'Wikipedia'), ('simple.wikipedia.org', 'Simple English Wikipedia'),
         ('en.wikibooks.org', 'Wikibooks'), ('en.wikivoyage.org', 'Wikivoyage')]
LICENCE = 'CC BY-SA 4.0'
WIKI_HOSTS = {host for host, _ in SITES}
WEB_LICENCE = "short quotation; see the publisher's terms"
SKIP_PUBLISHERS = {'youtube.com', 'youtu.be', 'tiktok.com', 'facebook.com', 'instagram.com', 'pinterest.com', 'x.com',
                   'twitter.com', 'linkedin.com', 'amazon.com', 'ebay.com', 'etsy.com', 'spotify.com', 'apple.com'}
WEB_PAGES = 8
TRACE = {}          # the last check's pages and best candidates, for diagnostics only
FILLER = re.compile(r"(?i)\b(?:in this (?:article|guide|post|video)|we'?ll (?:show|explain|cover|look)|let'?s (?:take a look|dive|explore)|"
                    r"here'?s (?:how|what|everything)|read on|keep reading|you'?ll learn|the right (?:approach|method|technique)|"
                    r"this (?:article|post|page|guide) (?:explains|covers|will|shows|looks)|everything you need|which is why|is essential if|"
                    r"(?:a|the) (?:safe|simple|quick|easy|proven|natural)(?:, [\w-]+)? (?:method|way|guide) to|"
                    r"if you'?re wondering|have you ever wondered|wondering (?:why|how)|the answer may surprise|"
                    r"below,? (?:we|you)|this guide|click here|table of contents|skip to content|best for:|"
                    r"here (?:is|are) (?:my|our|a|the|some) .{0,40}(?:guide|tips|ways|methods)|(?:my|our) (?:professional|expert|complete|ultimate) guide)\b")

DEAD_END = re.compile(r"(?i)^\s*(?:i do not have a reliable answer|i could not verify|i'?m not sure about that one|honestly, i'?m not sure|"
                      r"good question! i don'?t know|i don'?t have reliable knowledge|i cannot answer that reliably|"
                      r"i could not (?:find a matching|confidently match|obtain a source|interpret)|i found background on .*could not verify|"
                      r"i see\. tell me a bit more|i want to keep this connected|oh, i see\. (?:what happened next|tell me more)|"
                      r"(?:nice|got it|i see!?|interesting!?|oh,? i see)\.? (?:what happened next|tell me more about it|how did that come about|"
                      r"what else have you been up to)|thanks for telling me!? what else|i could not verify a readable|i have not interpreted)")
OLD_WEB_DEAD_END = re.compile(r"(?i)^\s*(?:i found pages, but could not read a passage|i did not find a usable public source|"
                              r"i could not reach the search providers|web lookup is turned off)")
ASKS = re.compile(r"(?i)\?|^\s*(?:tell me|give me|show me|explain|describe|suggest|recommend|list|teach me|help me|any (?:tips|ideas|advice))\b|"
                  r"^\s*(?:what|why|how|when|where|which|who|whose|can|could|should|is|are|does|do|will|would)\b")
NOT_WEB = re.compile(r"(?i)^\s*(?:write|rewrite|make it|make that|draft|compose|translate|summari[sz]e|shorten|now make|turn it|change it)\b|"
                     r"\b(?:poem|story|joke|essay|email|message|letter)\b|\bmy (?:name|age)\b|\b(?:are you|do you (?:like|love|enjoy|have|think|feel|know|remember|prefer)|have you|did you|were you|your (?:name|favou?rite|opinion|view|age|day|thoughts)|you like|yourself)\b|"
                     r"\d+\s*(?:[-+*/x×]|times|plus|minus|divided by|multiplied by|to the power of)\s*\d+|\b\d{1,2}:\d{2}\b|\bhow many\b.*\b(?:has|have|left|gives?|buys?)\b|"
                     r"\b(?:every|all|no|some)\s+\w+\b.*\b(?:is|are) \w+.*\?\s*$")
STOP = set('''a an the and or but if of to in on at for with from by about as is are was were be been being am do does did done doing have
has had having i me my mine we us our you your he him his she her it its they them their this that these those there here what which who
whom whose why how when where can could should would will shall may might must not no yes so very just really also too some any all
more most much many lot lots get got gets make makes made thing things stuff way ways good best better well one ones like want need
know tell give please thanks okay ok hi hello hey actually maybe still even only kind sort bit little way something anything every
other else than then now today tonight time year years day days dont doesnt im ive id youre isnt arent wont cant whats lets
tomorrow yesterday until while simple easy quick quickly try trying tried end start ask asked youd youre youve youll together
yeah yep nope gonna wanna pretty sure cool awesome wow lol haha anyway though'''.split())
CUES = {'why': r'\b(?:because|due to|caused by|causes?|(?<!much )so that|as a result|result(?:s|ing)? (?:in|from)|allows?|in order to|since|reason)\b',
        'how': r'\b(?:by|when|first|then|use|using|steps?|place|add|remove|mix|apply|forms?|formed|occurs?|produces?)\b',
        'what': r'\b(?:is|are|refers to|means|known as|called)\b',
        'which': r'\b(?:more|less|most|least|than|larger|smaller|greater|higher|lower|better|worse)\b'}


def plain(text):
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))


def words(text):
    return [w.replace("'", '') for w in re.findall(r"[a-z][a-z0-9'-]*", plain(text).lower().replace('’', "'"))]


def stem(w):
    """Crude ending removal so live / lives / lived / living, and tortoise / tortoises, compare equal."""
    for cut, keep in (('ies', 3), ('ing', 3), ('ed', 3), ('es', 4), ('s', 3), ('ly', 4)):
        if w.endswith(cut) and len(w) - len(cut) >= keep and not w.endswith(('ss', 'us', 'is')):
            w = w[:-len(cut)] + ('y' if cut == 'ies' else '')
            break
    if w.endswith('i') and len(w) > 3:
        w = w[:-1] + 'y'        # studied -> studi -> study
    if len(w) > 3 and w[-1] == w[-2] and w[-1] not in 'lsze':
        w = w[:-1]          # applied to every word, so purr / purring and blot / blotting meet at the same form
    return w[:-1] if len(w) > 3 and w.endswith('e') else w


def content(text):
    return [w for w in words(text) if w not in STOP and len(w) > 2 and not w.isdigit()]


def weight(w):
    """Rarer words count more: inverse document frequency from CAEL's own 285k-answer index, when present."""
    try:
        from . import open_chat
        value = open_chat.idf(open_chat.stem(w))
        return value if value > 0 else 8.0
    except Exception:
        return 4.0 if len(w) > 5 else 3.0


def nouns(ws):
    try:
        from .open_chat import is_noun
        return [w for w in ws if is_noun(w)]
    except Exception:
        return ws


def user_turns(messages):
    return [m['content'] for m in messages if m.get('role') == 'user' and isinstance(m.get('content'), str)]


NEED = {'duration': r'\b(?:\d[\d,.]*|one|two|three|four|five|six|seven|eight|nine|ten|several|few|many)\s+(?:seconds?|minutes?|hours?|days?|weeks?|months?|years?|decades?|centuries)\b|\bbetween (?:c\. )?\d{3,4} and \d{2,4}\b|\bfrom \d{3,4} (?:to|until) \d{2,4}\b',
        'span': r'\b(?:\d[\d,.]*|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:(?:-|–|to)\s*\d[\d,.]*\s*)?(?:seconds?|minutes?|hours?|days?|weeks?|months?|years?|decades?)\b',
        'when': r'\b(?:1\d{3}|20\d{2})\b|\bcentury\b|\b(?:BC|BCE|AD)\b',
        'season': r'\b(?:january|february|march|april|may|june|july|august|september|october|november|december|spring|summer|autumn|fall|winter|frost)\b',
        'count': r'\b\d[\d,.]*\b|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|hundred|thousand|million|billion)\b',
        'who': r'\b[A-Z][a-z]+ (?:[A-Z]\.? )?(?:da |de |van |von )?[A-Z][a-z]+\b',
        'measure': r'\b\d[\d,.]*\s*(?:°\s*[FC]?|degrees?|ºF|ºC)',
        'distance': r'(?<![\d.,])\d[\d,.]*\s*(?:km|kilomet(?:re|er)s?|miles?|mi|metres?|meters?|light[- ]years?)\b'}
GENERIC = {'long', 'take', 'takes', 'took', 'happen', 'happened', 'start', 'started', 'difference', 'different', 'differ', 'mean', 'means',
           'work', 'works', 'wow', 'another', 'fact', 'facts', 'fun', 'interesting', 'tips', 'idea', 'ideas', 'advice',
           'form', 'forms', 'formed', 'doing', 'wrong', 'keep', 'keeps', 'good', 'happens', 'far'}


def need_of(text):
    """The kind of fact a question needs in its answer: a duration, a date, a number or a name."""
    low = text.lower()
    if re.search(r'\bhow long\b|\bhow much time\b', low):
        return 'duration' if re.search(r'\b(?:did|was|were|had)\b', low) else 'span'
    if re.search(r'\bwhen (?:should|do|can|is the best time to)\b.*\b(?:plant|sow|prune|harvest|pick|grow|visit|go|travel|book|fertili[sz]e)\b|'
                 r'\bbest time (?:of year )?to\b', low):
        return 'season'
    if re.search(r'^\s*when\b|\bwhat year\b|\bwhen (?:did|was|were|is)\b', low):
        return 'when'
    if re.search(r'\b(?:what|which)\b.{0,25}\btemperature\b|\bhow (?:hot|cold|warm)\b', low):
        return 'measure'
    if re.search(r"\bhow far\b|\bhow many (?:km|kilomet(?:re|er)s|miles|metres|meters)\b|\bwhat(?:'s| is) the distance\b", low):
        return 'distance'
    if re.search(r'\bhow (?:many|much|old|tall|big|far|high|deep|heavy)\b|\b(?:what|which)\b.{0,25}\b(?:size|age|weight|height)\b', low):
        return 'count'
    if re.search(r'^\s*who\b', low):
        return 'who'
    return None


def question_kind(text):
    low = text.lower()
    for kind in ('why', 'how', 'which', 'what'):
        if re.search(r'\b' + kind + r'\b', low):
            return kind
    if re.search(r'\b(?:is|are|does|do|can|should)\b.*\b(?:or|than|more|less)\b', low):
        return 'which'
    return 'how' if re.search(r'\b(?:tips|steps|clean|make|fix|stop|get rid|remove|grow|cook)\b', low) else 'what'


PRONOUN = re.compile(r"(?i)\b(?:it|its|they|them|their|these|those|he|she|his|him|one|ones|there)\b|"
                     r"\bthat\b(?=\s*(?:\?|$|is\b|was\b|'s\b))|\bher\b(?!\s+(?:own|first))")
COMMON_CAPS = {'i', 'the', 'a', 'an', 'it', 'this', 'that', 'my', 'and', 'but', 'so', 'yes', 'no', 'hi', 'hey', 'hello', 'thanks', 'actually',
               'anyway', 'well', 'oh', 'ok', 'okay', 'cool', 'great', 'sorry', 'just', 'really', 'not', 'very', 'what', 'how', 'why', 'when',
               'where', 'who', 'which', 'do', 'does', 'did', 'is', 'are', 'can', 'could', 'should', 'would', 'tell', 'mind', 'sounds', 'yeah',
               'nice', 'wow', 'good', 'remind', 'by', 'also', 'she', 'he', 'they', 'we', 'you', 'any', 'some', 'got', 'thank'}


def names_in(text):
    """Proper names in a turn ("Oppenheimer", "Lake District", "Belem Tower"), lower-cased; sentence-initial common words skipped."""
    out = []
    for m in re.finditer(r"\b[A-Z][a-z'’]+(?:\s+[A-Z][a-z'’]+)*", text):
        for w in m.group(0).lower().replace('’', "'").split():
            w = w.removesuffix("'s")
            if w not in COMMON_CAPS and w not in STOP and len(w) > 2 and w not in out:
                out.append(w)
    return out


def cited_title(messages):
    """The source CAEL cited in its last reply ("Source: Pastel de nata (Wikipedia)"): what a follow-up's "it" means."""
    for m in reversed(messages[:-1]):
        if m.get('role') == 'assistant':
            hit = re.search(r'\nSource: (.+?) \(', m.get('content') or '')
            return hit[1] if hit else None
    return None


def query(messages):
    """(terms with weights, key noun, question kind) for the last user turn, borrowing topic nouns for follow-ups."""
    turns = user_turns(messages)
    last = turns[-1]
    own = [w for w in dict.fromkeys(content(last)) if w not in GENERIC]
    terms = {w: weight(w) for w in own}
    own_nouns = [w for w in nouns(own) if terms[w] > 2.5]
    follow = not own_nouns or PRONOUN.search(last) or '?' not in last
    topic = []
    if follow and len(turns) > 1:
        cited = cited_title(messages)
        if re.search(r'(?i)\b(?:he|she|him|his|her)\b', last):
            prev = next((m.get('content') or '' for m in reversed(messages[:-1]) if m.get('role') == 'assistant'), '')
            person = re.findall(r'\b([A-Z][a-z]+(?: [A-Z]\.)? [A-Z][a-z]+)\b', prev.split('\n\n')[0])
            if person:
                topic += [w for w in content(person[0]) if w not in terms]
        if cited and PRONOUN.search(last) and not topic:
            topic += [w for w in content(re.sub(r'\s*\([^)]*\)', '', cited)) if w not in terms][:3]
        for earlier in reversed(turns[:-1][-2:]):
            if topic:
                break       # the nearest turn that has a topic, not a mix of everything said before
            for w in names_in(earlier) + nouns(list(dict.fromkeys(content(earlier)))):
                if w not in terms and w not in GENERIC and w not in topic and weight(w) > 2.5 and (not w.endswith('ing') or re.search(
                        r'(?i)\b(?:finished|started|stopped|done|the|my|love|enjoy|hate|tried|about) ' + w + r'\b', earlier)):
                    topic.append(w)
        prev = next((m.get('content') or '' for m in reversed(messages[:-1]) if m.get('role') == 'assistant'), '')
        kind_word = re.search(r'(?i)\b(film|movie|novel|book|series|album|song|band|game|painting|tower|castle|church|museum|city|town|'
                              r'island|country|river|mountain|lake|play|opera|poem|dish|dessert|pastry)\b', prev)
        if topic and kind_word and kind_word[1].lower() not in terms and kind_word[1].lower() not in topic:
            topic.insert(1, kind_word[1].lower())
        for w in topic[:3]:
            terms[w] = weight(w) * 0.9
    if '?' not in last and len(turns) > 1:
        for w in dict.fromkeys(content(turns[-2])):
            if w not in terms and w not in GENERIC:
                terms[w] = weight(w) * 0.8
    ranked = sorted(own_nouns + topic[:3], key=lambda w: -terms[w])
    key = ranked[0] if ranked else (max(terms, key=terms.get) if terms else None)
    kind_text = last if re.search(r'(?i)\b(?:why|how|what|which|when|who)\b', last) or len(turns) == 1 else turns[-2]
    # The subject to look up on its own: the borrowed topic for a follow-up ("rainbow", "mona lisa"), else the key noun.
    subject = ' '.join(topic[:2]) if topic else ' '.join(w for w in ranked[:2]) if ranked else key
    return terms, key, question_kind(kind_text), set(own), need_of(last), subject


def api(host, **params):
    return NETWORK.json(f'https://{host}/w/api.php?' + urlencode(dict(params, format='json')), ttl=86400, timeout=10)


def search(host, text, limit):
    found = api(host, action='query', list='search', srsearch=text[:250], srlimit=limit, srnamespace=0)
    return [h['title'] for h in found.get('query', {}).get('search', [])
            if not h['title'].startswith(('List of', 'Lists of')) and '(disambiguation)' not in h['title']]


def page_text(host, title):
    data = api(host, action='query', prop='extracts|info', explaintext=1, exsectionformat='plain', inprop='url',
               redirects=1, titles=title)
    for page in data.get('query', {}).get('pages', {}).values():
        text = page.get('extract') or ''
        if text and not re.search(r'(?i)\bmay (?:also )?refer to\b', text[:400]):
            return page.get('title', title), text[:60000], page.get('fullurl') or f'https://{host}/wiki/' + title.replace(' ', '_')
    return None


def sentences(text):
    text = re.sub(r'\s+', ' ', re.sub(r'\n+(?:[A-Z][^.\n]{0,60}\n)', '\n', text))
    out = []
    for s in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"(])', text):
        s = s.strip()
        if 25 <= len(s) <= 500 and not re.search(r'(?i)^(?:see also|references|external links|further reading|notes)\b|\{\\|\\displaystyle', s):
            out.append(s)
    return out


def read_site(host, name, queries, pages, found, errors):
    """Search the site for the full question and for its subject alone; read the top pages of both."""
    try:
        titles = []
        for q, n in queries:
            for title in search(host, q, 3)[:n]:
                if title not in titles:
                    titles.append(title)
        for title in titles[:pages]:
            got = page_text(host, title)
            if got and all(f[2] != got[0] or f[1] != host for f in found):
                found.append((name, host) + got)
    except LookupUnavailable as error:
        errors.append(f'{name}: {error}')
    except (KeyError, TypeError, ValueError):
        errors.append(f'{name}: unreadable reply')


def web_queries(messages, text, subject):
    """What to type into a search engine: the question itself when it is a plain public question (a pronoun replaced by
    the topic: "How long did it take?" -> "How long did mona lisa take?"), and always the keyword form."""
    from .web_evidence import public_query
    turns = user_turns(messages)
    last = turns[-1].strip()
    out = []
    natural = public_query(last) if '?' in last else None
    if natural:
        if len(turns) > 1 and subject and not {stem(w) for w in content(subject)} <= {stem(w) for w in content(natural)}:
            swapped = re.sub(r'(?i)\b(?:it|they|them|this|that|these|those)\b', subject, natural, count=1)
            natural = swapped if swapped != natural else subject + ' ' + natural
        out.append(natural[:200])
    if '?' not in last and len(turns) > 1:
        # "I water them every day." after "My houseplants keep dying. What am I doing wrong?": search both together,
        # as keywords only (the turns may be personal).
        both = ' '.join(dict.fromkeys(w for w in content(turns[-2]) + content(last) if w not in {'wrong'}))
        if both:
            out.append(both[:200])
    if text and text not in out:
        out.append(text)
    return out


def publisher(url):
    from .web_evidence import publisher as of
    return of(url)


def read_open_web(queries, found, errors):
    """Search the open web with public engines and read the top result pages (one per publisher)."""
    if os.environ.get('CAEL_WEB_SEARCH', '1') == '0':
        errors.append('open web: switched off (CAEL_WEB_SEARCH=0)')
        return
    try:
        from . import web_search, web_fetch
        from .web_evidence import excluded
    except Exception:
        errors.append('open web: search modules unavailable')
        return
    hits, seen = [], set()
    for q in queries:
        for name, provider in (('web search', web_search.metasearch), ('DuckDuckGo', web_search.duckduckgo)):
            try:
                got = web_search.cached(('web_check', name, q.casefold()), 900, lambda: provider(q))
            except Exception as error:
                errors.append(f'{name}: {type(error).__name__}')
                continue
            for r in got:
                pub = publisher(r.url)
                if not pub or excluded(r.url) or pub in seen or pub in SKIP_PUBLISHERS or urlparse(r.url).path in ('', '/'):
                    continue
                seen.add(pub)
                hits.append(r)
    if not hits:
        errors.append('open web: no results')
        return

    def read(r):
        try:
            page = web_fetch.fetch(r.url, timeout=6)
        except Exception:
            return None
        if page.get('status') == 'read' and len(page.get('text', '')) > 200:
            return r, page
        return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        for got in pool.map(read, hits[:WEB_PAGES]):
            if got:
                r, page = got
                title = page_title(r.title, page['text']) or publisher(r.url)
                body = web_body(page['text'], title)
                if len(body) > 200:
                    found.append((publisher(page.get('url') or r.url), 'web', title,
                                  body[:60000], page.get('url') or r.url))


def web_body(text, title=''):
    """Only the paragraphs of a fetched page: menus, headings, captions, credits and cookie lines are dropped."""
    keep = []
    for line in re.split(r'\n|(?=\b(?:Method|Step|Tip|Option|Way|Solution|Hack)\s+#?\d+\s*[:.)])', text):
        line = re.sub(r'(?:\b(?:Share|Post|Pin) (?:on|to|via) [A-Z][\w]*\s*)+', '', line)
        if title and len(title) > 12 and line.strip().casefold().startswith(title.casefold()):
            line = line.strip()[len(title):].lstrip(' -–—|:')
            line = re.sub(r'^(?:[A-Z][\w’\'&]*\s+){1,5}(?=[A-Z][a-z]+\s+[a-z])', '', line) if ' - ' in text[:300] else line
        line = re.sub(r"^(?:Method|Step|Tip|Option|Way|Solution|Hack)\s+#?\d+\s*[:.)]\s*"
                      r"(?:(?:[A-Z0-9][\w’'&-]*|\([^)]*\)|the|a|an|of|and|for|to|in|on|with|or|vs\.?)\s+)*?(?=[A-Z][a-z]+\s+[a-z])",
                      '', line.strip())
        n = len(line.split())
        if '\ufffd' in line or n < 8 or (n < 15 and not re.search(r'[.!?:)]["”’]?$', line)):
            continue
        if re.search(r'(?i)cookie|subscribe|sign up|log in|newsletter|all rights reserved|advertisement|getty images|shutterstock|\bphoto(?:graph)? by\b', line):
            continue
        keep.append(line)
    return '\n'.join(keep)


def page_title(found_title, text):
    """The page's own <title> (its first text line) when the search engine's title is missing or run together."""
    first = (text.splitlines() or [''])[0].strip()
    title = clean_title(found_title)
    if (not title or len(title) > 100 or re.search(r'[a-z][A-Z][a-z]{2,}\b.*[a-z][A-Z]', title)) and 3 <= len(first) <= 120:
        title = clean_title(first)
    return title[:100]


def clean_title(title):
    """'Why Do Cats Purr? | Purina UK' -> 'Why Do Cats Purr?' (site names after a separator are not the topic)."""
    return re.split(r'\s+[|\-–—:]\s+(?=[^|\-–—:]*$)', (title or '').strip())[0].strip() if title else ''


def near_copy(a, b):
    wa, wb = {stem(w) for w in content(a)}, {stem(w) for w in content(b)}
    return bool(wa and wb) and len(wa & wb) / len(wa | wb) >= 0.7


AUTHOR_VERBS = {'wrote', 'written', 'write', 'directed', 'direct', 'painted', 'paint', 'composed', 'compose', 'invented', 'invent',
                'founded', 'found', 'designed', 'design', 'built', 'created', 'create', 'made', 'make', 'discovered', 'sang', 'sung',
                'developed', 'produced', 'author', 'director'}


def score(window, title, terms, key, kind, own, need, context=frozenset(), web=False, required=()):
    said = {stem(w) for w in words(window)}
    if need == 'who' and re.search(r'\bby (?:the )?(?:\w+ ){0,3}[A-Z][a-z]+ (?:[A-Z]\. )?[A-Z][a-z]+', window):
        said |= {stem(w) for w in own if w in AUTHOR_VERBS}
    have = said | {stem(w) for w in words(title)}
    total = sum(terms.values()) or 1.0
    covered = sum(v for w, v in terms.items() if stem(w) in have)
    if key and stem(key) not in have:
        return 0.0, 0.0
    if need and not re.search(NEED[need], window, 0 if need == 'who' else re.I):
        return 0.0, 0.0       # "how long" needs a duration, "when" a date, "how many" a number, "who" a name
    if need and need not in ('who', 'measure'):     # "37 F" is the temperature; it need not say the word
        # The figure must be about what was asked: "how long to heal" needs "heal" in the sentence with the "2 weeks",
        # not a history paragraph's "5,000 years" next to the word tattoo.
        verbs = {stem(w) for w in own if key is None or stem(w) != stem(key)} - {stem(w) for w in required}
        if verbs and not any(re.search(NEED[need], part, re.I) and verbs & {stem(w) for w in words(part)}
                             for part in re.split(r'(?<=[.!?])\s+', window)):
            return 0.0, 0.0
    if any(stem(w) not in have for w in required):
        return 0.0, 0.0
    own_total = sum(terms[w] for w in own if w in terms)
    if own_total and sum(terms[w] for w in own if w in terms and stem(w) in have) < 0.5 * own_total:
        return 0.0, 0.0       # the question's own words, not just the borrowed topic
    if kind == 'why' and not need and not re.search(CUES['why'], window, re.I):
        return 0.0, 0.0       # a "why" question needs a reason: because, due to, causes, so that ...
    if FILLER.search(window):
        return 0.0, 0.0       # an article's introduction ("you can remove it with the right approach") is not an answer
    if re.search(r'https?://|www\.|\b[\w-]+\.(?:com|org|net|co\.uk)/|Retrieved |Accessed |\bet al\.|“[^”]{10,}”\s*[A-Z][\w ]+,|'
                 r'Research source|Expert Source|has been viewed|\b[A-Z]{3,}(?:\s+[A-Z]{2,}){2,}\b', window):
        return 0.0, 0.0
    caps = re.findall(r"\b[A-Za-z][\w'’-]*", window)
    if len(caps) >= 6 and sum(w[0].isupper() for w in caps) > 0.5 * len(caps):
        return 0.0, 0.0       # "Scientific American Enzyme That Makes You Cry - Crystal Structure of ..." is a reference list
    if '?' in window:
        return 0.0, 0.0       # a question ("That begs the question: is it worth ...?") is not an answer
    coverage = covered / total
    if web:
        # On "How to Get Rid of Fruit Flies" every sentence inherits the title's words; rank by what the passage itself
        # says (title-only words count half), so "Add a few drops of dish soap..." beats "Best for: ...".
        coverage_rank = (sum(v for w, v in terms.items() if stem(w) in said)
                         + 0.5 * sum(v for w, v in terms.items() if stem(w) in have - said)) / total
    else:
        coverage_rank = coverage
    cue = 0.0 if need else 0.12 if re.search(CUES[kind], window, re.I) else 0.0
    if need == 'when' and re.search(r'\b(?:in|on) (?:\w+ )?(?:\d{1,2} )?(?:1\d{3}|[1-9]\d{1,2}) ?(?:AD|CE|BC|BCE)?\b|\b(?:1\d{3}|20\d\d)\b', window):
        cue += 0.08          # "in 476" answers "when" better than "in the 5th century"
    if need == 'distance' and re.search(r'\b(?:average|mean|about|approximately|around)\b', window, re.I):
        cue += 0.05          # the usual figure, not the closest or farthest point
    cue += min(0.15, 0.06 * len(context & have))          # the conversation's own words: "painted", "colour", "eggs"
    if re.search(r'(?i)\b(?:likely an error|was an error|disputed|apocryphal|myth|legend has it|falsely|incorrectly|no evidence)\b', window):
        cue -= 0.25
    on_page = 0.08 if key and stem(key) in {stem(w) for w in words(title)} else 0.0
    # "Eiffel Tower replicas and derivatives" is a side page; the article named after the subject comes first.
    on_page -= min(0.24, 0.08 * len({stem(w) for w in content(title)} - {stem(w) for w in terms} - context))
    length = -0.06 * max(0, len(window) - 600) / 300
    return coverage_rank + cue + on_page + length, coverage


def required_words(last, own, terms):
    """Words the passage must contain: the question's rare nouns ("iceland", "teenager") and both halves of a compound
    noun ("phone battery", "bike chain", "baking soda"): a page about electric-car batteries does not answer a phone question."""
    need = [w for w in nouns(sorted(own)) if terms.get(w, 0) >= 6.5]
    seq = words(last)
    for a, b in zip(seq, seq[1:]):
        if a in own and b in own and a not in GENERIC and b not in GENERIC and nouns([a]) and nouns([b]):
            need += [a, b]
    return list(dict.fromkeys(need))


def facts_in(text, need):
    return set(re.findall(NEED[need], text, 0 if need == 'who' else re.I)) if need else set()


def agrees(a, b, terms, need):
    """Two passages say the same thing: the same key fact (date, number, name) when the question needs one, else
    a good share of the same rarer words beyond the question's own."""
    if need:
        # The figure itself must be repeated: the same number (with its unit) or the same name.
        if need == 'who':
            # the same person named, not the question's own words ("Roman Empire")
            asked = {stem(w) for w in terms}
            names = lambda t: {n for n in re.findall(NEED['who'], t) if not {stem(w) for w in words(n)} <= asked} | \
                              {n for n in re.findall(r'(?<=[a-z,] )[A-Z][a-z]{3,}\b', t) if stem(n.lower()) not in asked}
            return bool(names(a) & names(b))
        figures = lambda t: {m.group(0).lower().replace(',', '') for m in re.finditer(NEED[need], t, re.I)}
        numbers = lambda t: set(re.findall(r'\d[\d,.]*', ' '.join(figures(t))))

        def with_unit(t):
            out = set()
            for f in figures(t):
                unit = re.findall(r'[a-z°]+', f)
                for n in re.findall(r'\d[\d.]*', f):
                    out.add((n, stem(unit[-1]) if unit else ''))
            return out
        if need in ('span', 'duration', 'measure', 'distance') and with_unit(a) & with_unit(b):
            return True
        return bool(figures(a) & figures(b)) or bool({n for n in numbers(a) if len(n) >= 2} & numbers(b))
    asked = {stem(w) for w in terms}
    wa = {stem(w) for w in content(a) if weight(w) > 3} - asked
    wb = {stem(w) for w in content(b) if weight(w) > 3} - asked
    if len(wa) < 2 or len(wb) < 2:
        return False
    shared = wa & wb
    return len(shared) >= 2 and len(shared) / min(len(wa), len(wb)) >= 0.25


def answer(messages):
    terms, key, kind, own, need, subject = query(messages)
    if not terms or not key:
        return None
    text = ' '.join(sorted(terms, key=lambda w: -terms[w])[:7])
    queries = [(text, 2), (subject, 2)] if subject and subject != text else [(text, 3)]
    found, errors, threads = [], [], []
    for host, name in SITES:
        pages = 4 if host in ('en.wikipedia.org', 'simple.wikipedia.org') else 2
        t = threading.Thread(target=read_site, args=(host, name, queries, pages, found, errors), daemon=True)
        t.start(); threads.append(t)
    t = threading.Thread(target=read_open_web, args=(web_queries(messages, text, subject), found, errors), daemon=True)
    t.start(); threads.append(t)
    for t in threads:
        t.join(timeout=25)
    found = list(found)
    if not found:
        return dict(route='chat/web-checked-none', sources=[],
                    response=f'I searched the web for "{text}" but could not reach any search engine or site just now, '
                             f'so I would rather not guess. Please try again in a moment.',
                    details='; '.join(errors) or 'No pages returned.')
    candidates = []
    asked = {stem(w) for w in terms}
    required = required_words(user_turns(messages)[-1], own, terms)
    context = {stem(w) for t in user_turns(messages)[-3:] for w in content(t) if w not in GENERIC} - asked
    for name, host, title, body, url in found:
        wiki = host in WIKI_HOSTS
        extra = re.search(r'\(([^)]*)\)', title)
        if wiki and extra and not {stem(w) for w in content(extra[1])} <= asked:
            continue        # "Mona Lisa (film)" is not the painting
        if not {stem(w) for w in content(title)} & asked:
            continue        # a page about something the question never mentions
        sents = sentences(body)
        for i in range(len(sents)):
            for size in ((1, 2, 3) if wiki else (1, 2)):
                if i + size > len(sents):
                    break
                window = ' '.join(sents[i:i + size])
                if not wiki and len(window.split()) > 50:
                    break       # open-web quotes stay short: the publisher's text is quoted, not copied
                if not wiki and re.search(r'(?i)\bhow (?:to|often to|long to|much to|many \w+ to)\b|\bis a (?:common )?question\b|'
                                          r'\bdepends on (?:a few|several|many|the)\b|affiliate|commission|sponsored', window):
                    continue    # the page restating the question, or its sales notice
                s, cov = score(window, title, terms, key, kind, own, need, context, web=not wiki, required=required)
                if s > 0:
                    early = 0.1 * (len(sents) - i) / max(1, len(sents))      # the lead and early sections state the main facts
                    candidates.append((s - 0.03 * (size - 1) + early, cov, window, name, title, url))
    TRACE.clear(); TRACE.update(candidates=[], pages=[(f[0], f[2], len(f[3])) for f in found], errors=list(errors))
    if not candidates:
        return none_found(text, found)
    candidates.sort(key=lambda c: -c[0])
    TRACE.update(candidates=candidates[:15], pages=[(f[0], f[2], len(f[3])) for f in found])
    best = candidates[0]
    if best[1] < 0.6:
        return none_found(text, found)
    # The check: a different source must say the same thing. One source alone is not enough. Two pages of one
    # publisher, or a site that copied the same text, are not independent.
    def independent(c):
        if c[3] == best[3] and (c[3] not in dict(SITES).values() or c[4] == best[4]):
            return False
        return not near_copy(best[2], c[2])
    # Look for support among every page's own best passages (one verbose page cannot crowd the others out).
    per_page, pool = {}, []
    for c in candidates[1:]:
        k = (c[3], c[4])
        if per_page.get(k, 0) < 40:
            per_page[k] = per_page.get(k, 0) + 1
            pool.append(c)
    if need in ('who', 'distance') and os.environ.get('CAEL_WEB_CONSENSUS') != '0':   # names and distances agree exactly; dates/counts too loosely
        # A fact question (a number, a date, a name): the answer most independent publishers agree on wins, not the single
        # best-worded passage ("Julius Caesar, the first emperor" on one site against "Augustus" on four others).
        def backers(c):
            out = set()
            for x in pool + [candidates[0]]:
                if x is c or x[1] < 0.4 or x[3] == c[3] or near_copy(c[2], x[2]):
                    continue
                if agrees(c[2], x[2], terms, need):
                    out.add(x[3])
            return out
        top = [c for c in candidates[:30] if c[1] >= 0.6 and c[0] >= candidates[0][0] - 0.12]     # near-best passages only
        if top:
            ranked = sorted(top, key=lambda c: (-len(backers(c)), -c[0]))
            if backers(ranked[0]):
                best = ranked[0]
                pool = [c for c in pool + [candidates[0]] if c is not best]
    support = next((c for c in pool if c[1] >= 0.4 and independent(c)
                    and agrees(best[2], c[2], terms, need)), None)
    main_article = (best[3] == 'Wikipedia' and {stem(w) for w in content(best[4])} <= {stem(w) for w in content(subject)} | {stem(key)}
                    and best[1] >= 0.85 and '?' in user_turns(messages)[-1])
    if support is None and not main_article:
        return none_found(text, found)
    passage = re.sub(r'\s*\[\d+\]', '', best[2]).strip()
    if support:
        check = f'Checked against {support[3]} ("{support[4]}"), which says the same.'
        sources = [(best[3], best[4], best[5]), (support[3], support[4], support[5])]
    else:
        check = (f'Checked: this is from the encyclopedia article on {best[4]} itself and answers the question directly; '
                 f'I found no second page that repeats it.')
        sources = [(best[3], best[4], best[5])]
    lead = 'I looked this up. ' if len(user_turns(messages)) == 1 else 'I looked that up. '
    wiki_names = set(dict(SITES).values())
    where = f'{best[3]}' if best[3] in wiki_names else f'{best[3]}, {best[5]}'
    response = f'{lead}{passage}\n\nSource: {best[4]} ({where}). {check}'
    licence = lambda n: LICENCE if n in wiki_names else WEB_LICENCE
    credits = '\n'.join(f'{n}: "{t}", {u} ({licence(n)})' for n, t, u in sources)
    web_pages = sum(1 for f in found if f[1] == 'web')
    return dict(route='chat/web-checked', response=response,
                sources=[dict(source=n, title=t, url=u, licence=licence(n)) for n, t, u in sources],
                details=f'Searched {", ".join(s[1] for s in SITES)} and the open web for "{text}"; read {len(found)} pages '
                        f'({web_pages} from the open web); coverage {best[1]:.2f}; '
                        f'{"corroborated" if support else "single source"}.\n{credits}' + (f'\nNotes: {"; ".join(errors)}' if errors else ''))


def none_found(text, found):
    return dict(route='chat/web-checked-none', sources=[],
                response="I looked this up, but I couldn't find an answer that two independent sources agree on, so I'd rather not "
                         "guess. If you can add a detail or put it another way, I'll look again.",
                details=f'Searched for "{text}"; no passage covered the question well enough and was confirmed by a second source.')


def wants_info(messages):
    turns = user_turns(messages)
    if not turns:
        return False
    last = turns[-1].strip()
    unquoted = re.sub(r"(?:^|\s)['\"“‘][^'\"”’]{3,80}['\"”’](?=[\s?.!,]|$)", ' it', last)
    if not last or len(last) > 400 or NOT_WEB.search(unquoted):
        return False
    if re.match(r"(?i)\s*(?:can|could|shall|will|would) we\b|\s*(?:are|do|will|would|can|could) you (?:be|like|love|want|miss|feel|have feelings|remember me)\b", last):
        return False            # "Can we be friends?" is said to CAEL, not a question about the sitcom
    try:
        from .personal_facts import personal_question
        from .chat_memory import RECALL
        if personal_question(last) or RECALL.search(last):
            return False        # about the user: answered from the conversation, never from the web
    except Exception:
        pass
    if re.search(r'\d', ' '.join(turns[-3:])) and re.search(
            r"(?i)\bhow (?:many|much|long)\b.*\b(?:i|my|we|our|each|left|now|instead)\b|\bwhat time\b|\bnew (?:arrival|time|total|price)\b|"
            r"\bin each\b|\bwhat if\b|^\s*(?:and|so) if\b|\bwhen do (?:i|we) (?:arrive|get|land|finish)\b|\bwhich days?\b", last):
        return False            # a calculation over numbers the user gave: a search engine has no part in it
    if ASKS.search(last):
        return True
    # A short detail added to an earlier question ("I water them every day.", "It's a non-stick one."): it refers back
    # to the question or shares a word with it. "My partner Sam works night shifts." is news, not a detail.
    if not (len(turns) > 1 and len(last.split()) <= 14 and ASKS.search(turns[-2]) and not NOT_WEB.search(turns[-2])):
        return False
    shared = {stem(w) for w in content(last)} & {stem(w) for w in content(turns[-2])}
    return bool(shared) or bool(re.search(r"(?i)\b(?:it|its|it's|them|they|this|that|these|those|one)\b", last))


KEEP_LOCAL = re.compile(r'(?:helper/|chat/native-|chat/local-knowledge|chat/world-fact|chat/fixture|chat/smalltalk-|chat/story|'
                        r'chat/web-unsupported-)')


def improve(messages, result):
    """Replace a don't-know reply with a checked web answer when the turn asks for information."""
    try:
        if not isinstance(messages, list) or not isinstance(result, dict) or os.environ.get('CAEL_WEB_SEARCH', '1') == '0':
            return result        # web lookups switched off (benchmarks): nothing is fetched and nothing is replaced
        said = str(result.get('response', '')).strip()
        # CAEL's older single-pass web lookup (web_evidence.py) also gives up in these routes; check more widely then.
        route = str(result.get('route', ''))
        from .chat_memory import TRUSTED_MEMORY
        if TRUSTED_MEMORY.search(route):
            return result        # "652." to "Which locker is mine?" comes from what the user said
        if KEEP_LOCAL.match(route) and not DEAD_END.search(said):
            return result        # an exact, sourced or social answer of CAEL's own is not replaced by a search
        gave_up = route in ('chat/web-evidence-insufficient', 'chat/web-evidence-no_results', 'chat/web-evidence-unavailable',
                            'chat/web-evidence-disabled', 'chat/web-evidence-single-source', 'chat/web-evidence-conflict')
        dead = gave_up or DEAD_END.search(said) or OLD_WEB_DEAD_END.search(said) or broken(messages, said, route) or (
            len(said.split()) <= 3 and OPEN_ROUTES.search(route) and not re.search(r'\d', said)
            # "Weekend." to "What should I pack?" is not an answer; "Saturday." to "When is the dinner?" is
            and re.search(r'(?i)\b(?:should|could|can|need|best|good|recommend|tips?|how)\b', user_turns(messages)[-1]))
        if not wants_info(messages):
            return result
        off_topic = not dead and OPEN_ROUTES.search(route) and not addresses(messages, said)
        if not (dead or off_topic):
            return result
        found = answer(messages)
    except Exception:
        return result
    if found is None:
        return result
    if found.get('route') == 'chat/web-checked-none' and route.startswith('chat/web-'):
        return result            # CAEL's own lookup already said why it could not answer; keep that more specific reply
    years = re.findall(r'\b(?:1[0-9]{3}|20[0-9]{2})\b', user_turns(messages)[-1])
    if years and found.get('route') == 'chat/web-checked' and not any(y in str(found.get('response', '')) for y in years):
        return result            # "What happened in Asteria in 1847?": a page about Asteria that never mentions 1847 is not an answer
    if off_topic and found.get('route') != 'chat/web-checked':
        if not (RETRIEVED.search(route) and misses_subject(messages, said)):
            return result        # CAEL's own answer stays unless the web gives a checked one
        # ... unless it is not about the question's subject at all (a forum post on billing for "data analyst interview")
    return dict(found, replaced_route=result.get('route'), replaced_because='off topic' if off_topic else 'did not know')


def broken(messages, said, route=''):
    """A reply that is wrong whatever the web says: it echoes the question back, pastes the user's noun into an
    unrelated template, or describes CAEL when the user quoted "tell me about yourself"."""
    last = user_turns(messages)[-1]
    asked = re.split(r'(?<=[.!])\s+', last.strip())[-1].rstrip('?. ').lower()
    if len(asked) > 12 and asked in said.lower():
        return True             # "You loved Interstellar too. Is the science in it accurate?. What part stood out..."
    if re.search(r'(?i)\bthe smallest visible piece of\b|\bmake the first step so small\b', said) and not re.search(
            r'(?i)\b(?:start|motivat|procrastinat|focus|habit|stuck|overwhelm|lazy|begin|putting off)\w*', last):
        return True             # the getting-started template is not an answer to "How do I avoid blisters?"
    if route == 'chat/talk-persona' and re.search(r"['\"“‘]", last) and re.search(r'(?i)\b(?:answer|respond|say|reply)\b', last):
        return True             # "How should I answer 'tell me about yourself'?" is not about CAEL
    return False


OPEN_ROUTES = re.compile(r'^chat/(?:core-(?:open|knowledge|plan|explain|fallback|reflect)|open-retrieval|corpus|local-|context-reasoning|'
                         r'talk-|dialogue-|memory-clarify|smalltalk-quiet|web-wikipedia|web-search)')


# Answers quoted from a retrieval index (forum posts and the like), as opposed to CAEL's authored answers, which often
# answer without repeating the question's noun ("Yes, it is normal ... calluses form ...").
RETRIEVED = re.compile(r'^chat/(?:core-open|open-retrieval|corpus|local-other|local-unknown)')


def misses_subject(messages, said):
    terms, key, kind, own, need, subject = query(messages)
    have = {stem(w) for w in words(said)}
    nouns_asked = [w for w in nouns(sorted(own)) if terms.get(w, 0) >= 4.5] or ([key] if key else [])
    return bool(nouns_asked) and not any(stem(w) in have for w in nouns_asked)


def addresses(messages, said):
    """Does a reply answer the question at all? The same lexical tests a web passage must pass: the question's key noun
    and rare/compound nouns, most of its own words, the kind of fact asked for ("how long" -> a span), a reason for
    "why". Questions the reply asks back are not part of the answer."""
    body = ' '.join(x for x in re.split(r'(?<=[.!?])\s+', said) if not x.strip().endswith('?'))
    if len(body.split()) < 4:
        return False
    asked = re.split(r'(?<=[.!])\s+', user_turns(messages)[-1].strip())[-1].rstrip('?. ').lower()
    if broken(messages, said):
        return False

    terms, key, kind, own, need, subject = query(messages)
    if not terms or not key:
        return True
    have = {stem(w) for w in words(body)}
    if stem(key) not in have:
        return False
    required = required_words(user_turns(messages)[-1], own, terms)
    if any(stem(w) not in have for w in required):
        return False
    own_total = sum(terms[w] for w in own if w in terms)
    if own_total and sum(terms[w] for w in own if w in terms and stem(w) in have) < 0.5 * own_total:
        return False
    if need and not re.search(NEED[need], body, 0 if need == 'who' else re.I):
        return False
    if kind == 'why' and not need and not re.search(CUES['why'], body, re.I):
        return False
    return True
