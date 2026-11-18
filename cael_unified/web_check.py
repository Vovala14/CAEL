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
import time
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
class PerThread:
    """A dict kept separately for each thread: several questions are checked at the same time (the public worker's
    chat pool, the Mr. Meesix task agents), and one question's state must not show up in another's."""

    def __init__(self):
        self._local = threading.local()

    def _d(self):
        if not hasattr(self._local, 'd'):
            self._local.d = {}
        return self._local.d

    def clear(self):
        self._d().clear()

    def update(self, *a, **k):
        self._d().update(*a, **k)

    def get(self, key, default=None):
        return self._d().get(key, default)

    def __getitem__(self, key):
        return self._d()[key]

    def __setitem__(self, key, value):
        self._d()[key] = value

    def __contains__(self, key):
        return key in self._d()


TRACE = PerThread()  # this thread's last check: pages and best candidates, for diagnostics only
STATE = PerThread()  # this thread's question: whether it asks for a list ("what are some ...", "ideas", "what should I bring")
FILLER = re.compile(r"(?i)\b(?:in this (?:article|guide|post|video)|we'?ll (?:show|explain|cover|look)|let'?s (?:take a look|dive|explore)|"
                    r"here'?s (?:how|what|everything)|read on|keep reading|you'?ll learn|the right (?:approach|method|technique)|"
                    r"this (?:article|post|page|guide) (?:explains|covers|will|shows|looks)|everything you need|which is why|is essential if|"
                    r"(?:a|the) (?:safe|simple|quick|easy|proven|natural)(?:, [\w-]+)? (?:method|way|guide) to|"
                    r"if you'?re wondering|have you ever wondered|wondering (?:why|how)|the answer may surprise|"
                    r"below,? (?:we|you)|this guide|click here|table of contents|skip to content|best for:|"
                    r"here (?:is|are) (?:my|our|a|the|some) .{0,40}(?:guide|tips|ways|methods)|(?:my|our) (?:professional|expert|complete|ultimate) guide|"
                    r"here are (?:\w+ ){0,4}(?:strategies|ideas|steps|reasons|things|signs|options|tricks|hacks|suggestions)|before we (?:dive|get|start|begin)|"
                    r"our guide|let'?s talk about|learn why people trust|co-authored by|staff writer|reviewed by|many (?:parents|people|owners|students|beginners) (?:wonder|ask)|the question often|"
                    r"worth the effort|a common question|find out (?:how|why|what)|learn more about|check out|we (?:asked|spoke|tested|rounded up))\b")

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
yeah yep nope gonna wanna pretty sure cool awesome wow lol haha anyway though shouldnt wouldnt couldnt didnt wasnt werent hasnt havent
hadnt thats theres heres whos hows whys wheres shes hes theyre weve theyve youll ill itll put putting'''.split())
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
           'form', 'forms', 'formed', 'doing', 'wrong', 'keep', 'keeps', 'good', 'happens', 'far',
           'roughly', 'approximately', 'usually', 'typically', 'exactly', 'actually', 'basically', 'generally', 'normally',
           'absolute', 'absolutely', 'really', 'quite', 'pretty', 'think', 'maybe', 'probably', 'okay', 'able', 'some', 'still',
           'anyone', 'someone', 'something', 'anything', 'extra', 'try', 'else', 'lately', 'always', 'never', 'often'}
ANAPHORA = re.compile(r"(?i)^\s*(?:it is because of|this is why|that is why|that's why|because of (?:this|these|that)|these|those|this|they|"
                      r"however|but|also|and|so|then|thus|therefore|moreover|furthermore|in addition|additionally|instead|otherwise|"
                      r"for example|for instance|such|both|either|neither|he|she|his|her|its|their|as a result|as such|here|there)\b")


def scene(messages):
    """What a longer chat is about, from where the user set it up ('learning to play the piano', 'a weekend camping
    trip'): later questions ('What are the absolute essentials to bring?') are searched with it."""
    turns = user_turns(messages)
    if len(turns) < 2:
        return []
    out = []
    for t in turns[:-1]:
        m = re.search(r"(?i)\b(?:learning|studying|practi[sc]ing|training for|taking up|getting into|started|starting)(?: to (?:play|speak|do|learn|use))?"
                      r"(?: the| a| an| my)? ([a-z]+)\b", t)
        if m and m[1].lower() not in STOP and m[1].lower() not in GENERIC and weight(m[1].lower()) > 3.5:
            out.append(m[1].lower())
        m = re.search(r"(?i)\b(?:a|an|my|our|the) (?:weekend |first |new |big |little |small |long |[a-z]+-day |[a-z]+-week )?([a-z]+) (trip|holiday|party|wedding|exam|interview|"
                      r"project|race|marathon|garden|lesson|course|class|diet|plan)\b", t)
        if m:
            out += [m[1].lower(), m[2].lower()]
        m = re.search(r"(?i)\b(?:trip|holiday|vacation|visit|weekend|move|moving|travelling|traveling|going|flying) (?:to|in) (?-i:([A-Z][a-z]+(?: [A-Z][a-z]+)?))", t)
        if m:
            out += [w.lower() for w in m[1].split()]
    if not out:
        first = [w for w in nouns(list(dict.fromkeys(content(turns[0])))) if w not in GENERIC and weight(w) > 4.5 and w not in names_in(turns[0])]
        out = sorted(first, key=lambda w: -weight(w))[:2]
    return list(dict.fromkeys(w for w in out if w not in STOP))[:3]


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


def sentences_of(text):
    return [s for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()] or [text]


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
    elif len(turns) > 1 and '?' in turns[-2] and PRONOUN.search(last) and len(content(last)) <= 5:
        # "How can I avoid it?" after "Why do onions make you cry?": "it" is the whole thing asked about, not just the noun
        for w in dict.fromkeys(content(sentences_of(turns[-2])[-1])):
            if w not in terms and w not in GENERIC:
                terms[w] = weight(w) * 0.6
    if len(turns) > 1 and os.environ.get('CAEL_WEB_SCENE', '1') != '0':
        # what the chat is about ("piano", "camping trip") belongs to every later question in it
        have_now = {stem(w) for w in terms}
        for w in scene(messages):
            if stem(w) not in have_now:
                terms[w] = weight(w) * 0.6
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
        about = [w for w in scene(messages) if stem(w) not in {stem(x) for x in content(natural)}]
        if about:
            out.append((natural.rstrip('?. ') + ' ' + ' '.join(about))[:200])     # "... essentials to bring camping trip"
        out.append(natural[:200])
    if '?' in last and len(turns) > 1 and PRONOUN.search(last) and '?' in turns[-2] and len(content(last)) <= 6:
        # "It's been there since yesterday, is it too late?" after "How can I get a red wine stain out of a white shirt?"
        joined = ' '.join(dict.fromkeys(content(turns[-2]) + [w for w in content(last) if w not in GENERIC]))
        if joined:
            out.insert(0, joined[:200])
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


FACT_Q = re.compile(r"(?i)^\s*(?:what|which|who|where)\b")
SUPERLATIVE = re.compile(r"(?i)\b(?:[a-z]{3,}est|most|capital|first|last|only|inventor|author|founder|president|largest|smallest)\b")
NOT_ENTITY = {'the', 'what', 'which', 'who', 'where', 'when', 'how', 'why', 'this', 'that', 'these', 'here', 'there', 'top', 'best', 'list', 'world',
              'earth', 'wikipedia', 'britannica', 'guide', 'facts', 'fact', 'answer', 'answers', 'home', 'news', 'quora', 'reddit', 'youtube',
              'in', 'on', 'at', 'it', 'its', 'and', 'but', 'for', 'with', 'from', 'a', 'an', 'is', 'are', 'was', 'were', 'of', 'to', 'by', 'as',
              'explained', 'complete', 'ultimate', 'everything', 'you', 'your', 'we', 'our', 'my', 'new', 'more', 'all', 'one', 'two', 'three',
              'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december',
              'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday', 'learn', 'discover', 'find', 'see', 'read', 'did',
              'while', 'although', 'however', 'many', 'some', 'most', 'if', 'so', 'not', 'no', 'yes', 'they', 'he', 'she', 'according', 'today'}


def entity_answer(messages, hits, terms):
    """A plain fact question with a name for an answer ("What's the tallest mountain in the world?"): the name that the
    search results of several independent publishers agree on, quoted in one of their own sentences."""
    last = user_turns(messages)[-1].strip()
    if len(hits) < 4 or len(last.split()) > 16 or not FACT_Q.search(last) or not SUPERLATIVE.search(last):
        return None
    if re.search(r"(?i)\b(?:you|your|i|my|me|we|our|should|best way|difference)\b", last):
        return None
    asked = {stem(w) for w in words(last)}
    votes, shown = {}, {}
    undated = lambda s: re.sub(r'^\s*(?:[A-Z][a-z]{2,8}\.? \d{1,2}, \d{4}|\d+ (?:days?|hours?|weeks?|months?) ago)\s*[·\-–—:]\s*', '', s or '')
    for r in hits:
        r.snippet = undated(r.snippet)
        pub = publisher(r.url)
        text = f'{clean_title(r.title)}. {r.snippet or ""}'
        seen = set()
        for m in re.finditer(r"\b[A-Z][\w'’-]*(?:[ \t]+(?:of|the|de|la|del|da|van|von)[ \t]+[A-Z][\w'’-]*|[ \t]+[A-Z][\w'’-]*)*", text):
            phrase = m.group(0).strip(" .'’-")
            ws = [w for w in phrase.lower().replace('’', "'").split()]
            while ws and ws[0] in NOT_ENTITY:
                ws = ws[1:]; phrase = phrase.split(' ', 1)[1] if ' ' in phrase else ''
            while ws and ws[-1] in NOT_ENTITY:
                ws = ws[:-1]; phrase = phrase.rsplit(' ', 1)[0] if ' ' in phrase else ''
            if not ws or len(' '.join(ws)) < 3 or all(stem(w) in asked or w in NOT_ENTITY for w in ws) or pub.split('.')[0] in ''.join(ws):
                continue
            k = ' '.join(ws)
            if k not in seen:
                seen.add(k)
                votes.setdefault(k, set()).add(pub)
                shown.setdefault(k, phrase)
    if not votes:
        return None
    # "everest" counts for "mount everest": the longest name whose words the shorter mentions share
    full = {}
    for k, pubs in votes.items():
        total = set(pubs)
        for other, opubs in votes.items():
            if other != k and (other in k.split() or k in other.split() or re.search(r'\b' + re.escape(other) + r'\b', k)):
                total |= opubs
        full[k] = total
    ranked = sorted(full, key=lambda k: (-len(full[k]), -len(k.split()), k))
    top = ranked[0]
    rest = [k for k in ranked[1:] if not (k in top or top in k or set(k.split()) & set(top.split()))]
    publishers = {publisher(r.url) for r in hits}
    second = len(full[rest[0]]) if rest else 0
    if len(full[top]) < max(3, 0.5 * len(publishers)) or len(full[top]) < second + 2:
        return None
    name = shown[top]
    best = None
    for r in hits:
        for s in re.split(r'(?<=[.!?])\s+', r.snippet or ''):
            s = s.strip()
            if not (6 <= len(s.split()) <= 45) or not s.endswith(('.', '!')) or not s[0].isupper() or '...' in s or '…' in s or '?' in s:
                continue
            if top.split()[-1] not in s.lower() or ANAPHORA.search(s):
                continue
            have = {stem(w) for w in words(s)}
            cov = sum(v for w, v in terms.items() if stem(w) in have) / (sum(terms.values()) or 1.0)
            if best is None or cov > best[0]:
                best = (cov, s, r)
    others = sorted(full[top])
    if best and best[0] >= 0.5:
        r = best[2]
        pub = publisher(r.url)
        agree = [p for p in others if p != pub][:3]
        response = (f"I looked this up. {best[1]}\n\nSource: {clean_title(r.title)} ({pub}, {r.url}). "
                    f"Checked against {join_names(agree)}, which name {name} too.")
        sources = [dict(source=pub, title=clean_title(r.title), url=r.url, licence=WEB_LICENCE)]
    else:
        response = (f"I looked this up: it's **{name}**.\n\nChecked: {len(others)} independent sources in the search results name it "
                    f"({join_names(others[:4])}).")
        sources = [dict(source=publisher(r.url), title=clean_title(r.title), url=r.url, licence=WEB_LICENCE) for r in hits
                   if publisher(r.url) in others[:3]][:3]
    return dict(route='chat/web-checked', response=response, sources=sources,
                details=f'Search results from {len(publishers)} publishers; {len(others)} name "{name}" (next most named: '
                        f'{shown[rest[0]] if rest else "none"}, {second}).')


def join_names(items):
    items = list(items)
    if not items:
        return 'other results'
    return items[0] if len(items) == 1 else ', '.join(items[:-1]) + ' and ' + items[-1]


def read_open_web(queries, found, errors, hits_out=None):
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
            wanted = {stem(w) for w in content(q)}
            for r in got:
                pub = publisher(r.url)
                if not pub or excluded(r.url) or pub in seen or pub in SKIP_PUBLISHERS or urlparse(r.url).path in ('', '/'):
                    continue
                shown = {stem(w) for w in words(f'{r.title} {getattr(r, "snippet", "") or getattr(r, "text", "") or ""}')}
                if len(wanted) >= 2 and len(wanted & shown) < max(2, (len(wanted) + 1) // 2):
                    errors.append(f'{name}: dropped an unrelated result ({pub})')
                    continue        # a result about something else entirely: not read, not quoted
                seen.add(pub)
                hits.append(r)
    if hits_out is not None:
        hits_out.extend(hits)
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


# Whether the question asks for a list is kept per thread in STATE['listy'], set in answer().
LIST_Q = re.compile(r"(?i)\bwhat are (?:some|the|good|a few)\b|\b(?:ideas|examples|options|essentials|suggestions|recommendations|alternatives)\b|"
                    r"\bwhat (?:should|do|can) (?:i|we) (?:bring|pack|buy|need|take|get|eat|cook|wear)\b|\b(?:recommend|suggest)\b|\bwhich \w+ (?:are|should)\b")
ADVICE = re.compile(r"(?i)^(?:[A-Z][a-z]+ (?:the|a|an|your|it|them|some|with|by|to|up|out|in|on)\b)|\b(?:should|try|avoid|use|make sure|helps?|keep|store|"
                    r"start|aim|choose|best|instead of|rather than|works? (?:well|best)|it'?s (?:best|better|worth)|you can|can help|is to)\b")


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
    if ANAPHORA.search(window) or re.search(r'[»›|]| > |\bClick\b|\bRead more\b|\bSee also\b', window):
        return 0.0, 0.0       # "It is because of these that ..." points at text that is not quoted; "Home » Tips" is a menu
    coverage = covered / total
    if (STATE.get('plan') or {}).get('shape') == 'often' and not re.search(SHAPE_CUES['often'], window, re.I):
        return 0.0, 0.0       # "how often" is answered by a frequency, not by a description
    if web:
        # On "How to Get Rid of Fruit Flies" every sentence inherits the title's words; rank by what the passage itself
        # says (title-only words count half), so "Add a few drops of dish soap..." beats "Best for: ...".
        coverage_rank = (sum(v for w, v in terms.items() if stem(w) in said)
                         + 0.5 * sum(v for w, v in terms.items() if stem(w) in have - said)) / total
    else:
        coverage_rank = coverage
    cue = 0.0 if need else 0.12 if re.search(CUES[kind], window, re.I) else 0.0
    cue += shape_fit(window)              # the shape of answer the Planner asked for
    if need == 'when' and re.search(r'\b(?:in|on) (?:\w+ )?(?:\d{1,2} )?(?:1\d{3}|[1-9]\d{1,2}) ?(?:AD|CE|BC|BCE)?\b|\b(?:1\d{3}|20\d\d)\b', window):
        cue += 0.08          # "in 476" answers "when" better than "in the 5th century"
    if need == 'distance' and re.search(r'\b(?:average|mean|about|approximately|around)\b', window, re.I):
        cue += 0.05          # the usual figure, not the closest or farthest point
    cue += min(0.15, 0.06 * len(context & have))          # the conversation's own words: "painted", "colour", "eggs"
    if need == 'when':
        # "written between 1591 and 1595" answers "when was it written"; "written by Bandello, translated ... in 1562" does not
        verbs = [stem(w) for w in own if key is None or stem(w) != stem(key)]
        if any(re.search(r'(?i)\b' + re.escape(v) + r"\w*(?:\W+\w+){0,2}?\W+(?:in|between|around|about|circa|c\.|during|from|by)\s+(?:the\s+)?(?:early |late |mid-?)?\d{3,4}", window)
               for v in verbs):
            cue += 0.2
    if STATE.get('listy') and window.count(',') >= 2 and re.search(r'(?i)\b(?:such as|including|includes?|like|try|bring|pack|choose|options?|ideas?)\b|:', window):
        cue += 0.15           # "What are some snacks ...?": a passage that names several beats a definition
    if STATE.get('listy') and re.match(r"(?i)(?:an?|the) [\w -]{2,40} (?:is|are) (?:an?|the|typically|usually|generally|defined)\b", window):
        cue -= 0.2
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


SHAPE_CUES = {
    'often': r"\b(?:every|once|twice|three times|each|per)\s+(?:a |an |\d+ |few |couple of |other )?(?:day|week|month|year|season|use|wash)s?\b|\bdaily\b|\bweekly\b|\bmonthly\b|\b\d+ ?(?:to|-) ?\d+ (?:days|weeks|months)\b",
    'normal': r"\b(?:normal|common|usual|typical|natural|most (?:people|beginners|new)|everyone|many people|lots of people|to be expected)\b",
    'steps': r"^(?:try|use|keep|make|put|start|avoid|don'?t|never|always|place|add|remove|check|clean|change|replace|cover|hang|install|ask|set|turn|fill|wash|rinse)\b|"
             r"\b(?:you (?:can|could|should|need to|might)|make sure|it'?s (?:best|a good idea) to|the (?:best|easiest|simplest) way)\b",
    'choose': r"\b(?:better|best|recommend|depends|worth|cheaper|easier|prefer|advantage|downside)\b",
    'why': r"\b(?:because|due to|caused by|so that|as a result|which (?:is|means) why|this is why|that'?s why)\b",
    'amount': r"\b\d[\d,.]*\s*(?:%|percent|minutes?|hours?|days?|weeks?|months?|years?|km|miles?|kg|g|ml|litres?|liters?|cups?|times?|°)",
}
LEADS = {'steps': 'From what I found, this is what usually works:', 'often': 'From what I found:', 'normal': 'From what I found:',
         'why': 'The reason, from what I found:', 'choose': 'What I found, to help you weigh it up:', 'amount': 'From what I found:'}


def shape_fit(window):
    """How well a passage has the shape of answer the Planner asked for (0 when there is no plan)."""
    plan = STATE.get('plan') or {}
    cue = SHAPE_CUES.get(plan.get('shape'))
    return 0.15 if cue and re.search(cue, window, re.I) else 0.0


def answer(messages):
    plan = STATE.get('plan') or {}
    if plan:
        # the Researcher's best case first: someone asked exactly this already (a stored question that is a paraphrase),
        # or it's a place to visit (the travel guide's own recommendations)
        try:
            from . import researchers
            got = researchers.destination(messages) or local_search(plan, messages)
            if got:
                return got
        except Exception:
            pass
        if plan.get('bound') and plan['bound'].rstrip('?').lower() not in user_turns(messages)[-1].lower():
            messages = messages[:-1] + [dict(role='user', content=plan['bound'])]
    terms, key, kind, own, need, subject = query(messages)
    if not terms or not key:
        return None
    text = ' '.join(sorted(terms, key=lambda w: -terms[w])[:7])
    queries = [(text, 2), (subject, 2)] if subject and subject != text else [(text, 3)]
    for q in plan.get('queries', [])[1:3]:
        if q and q not in (text, subject):
            queries.append((q, 2))      # the Planner's other wordings
    # Wikipedia's search wants every word of the query on the page: the three weightiest nouns alone find the article
    # when seven words together find nothing ("microwave oven metal").
    core = ' '.join(sorted([w for w in nouns(list(terms)) if w not in GENERIC] or list(terms), key=lambda w: -terms[w])[:3])
    if core and core not in (text, subject):
        queries.append((core, 2))
    found, errors, threads = [], [], []
    for host, name in SITES:
        pages = 4 if host in ('en.wikipedia.org', 'simple.wikipedia.org') else 2
        t = threading.Thread(target=read_site, args=(host, name, queries, pages, found, errors), daemon=True)
        t.start(); threads.append(t)
    hits = []
    t = threading.Thread(target=read_open_web, args=(list(dict.fromkeys(web_queries(messages, text, subject) + plan.get('queries', [])[:2])), found, errors, hits),
                         daemon=True)
    t.start(); threads.append(t)

    def read_stack():
        try:
            from . import stack_source
            plan_now = plan               # this runs on its own thread: the plan is passed in, not read from per-thread state
            core = plan_now.get('core')
            short = ' '.join(core.split()[:2]) if core else None         # two words: the search needs every word on the page
            found.extend(stack_source.pages(short or text, user_turns(messages)[-1] + (' ' + core if core else ''), network=NETWORK,
                                            sites=plan_now.get('sites') or None))
        except LookupUnavailable as error:
            errors.append(f'Stack Exchange: {error}')
        except Exception as error:
            errors.append(f'Stack Exchange: {type(error).__name__}')
    t = threading.Thread(target=read_stack, daemon=True)
    t.start(); threads.append(t)
    def read_main():
        # The encyclopedia article named after the question's own subject ("Greyhound", "Microwave oven"): a search for
        # the whole question often returns pages that only mention it.
        for name in dict.fromkeys(x for x in (subject, key) if x):
            try:
                got = page_text('en.wikipedia.org', name[:1].upper() + name[1:])
            except (LookupUnavailable, KeyError, TypeError, ValueError):
                continue
            if got and all(f[2] != got[0] or f[1] != 'en.wikipedia.org' for f in found):
                found.append(('Wikipedia', 'en.wikipedia.org') + got)
    t = threading.Thread(target=read_main, daemon=True)
    t.start(); threads.append(t)
    deadline = time.time() + 16           # for the whole check, however many sources are still answering
    for t in threads:
        t.join(timeout=max(0.1, deadline - time.time()))
    found = list(found)
    try:
        agreed = entity_answer(messages, list(hits), terms)
    except Exception:
        agreed = None
    if agreed:
        return agreed
    if not found:
        return dict(route='chat/web-checked-none', sources=[],
                    response=f'I searched the web for "{text}" but could not reach any search engine or site just now, '
                             f'so I would rather not guess. Please try again in a moment.',
                    details='; '.join(errors) or 'No pages returned.')
    candidates = []
    STATE['listy'] = bool(LIST_Q.search(user_turns(messages)[-1]))
    asked = {stem(w) for w in terms}
    required = required_words(user_turns(messages)[-1], own, terms)
    context = ({stem(w) for t in user_turns(messages)[-3:] for w in content(t) if w not in GENERIC} | {stem(w) for w in scene(messages)}) - asked
    for name, host, title, body, url in found:
        wiki = host in WIKI_HOSTS
        extra = re.search(r'\(([^)]*)\)', title)
        if wiki and extra and not {stem(w) for w in content(extra[1])} <= asked:
            continue        # "Mona Lisa (film)" is not the painting
        if not {stem(w) for w in content(title)} & asked:
            continue        # a page about something the question never mentions
        if name in ('Wikivoyage', 'Wikibooks') and not {stem(w) for w in content(title)} <= asked | context:
            continue        # a travel guide's "Dangerous animals" page is not advice on storing food at a campsite
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
        return whole_answer(found, plan, messages) or closest(messages, text, found, terms, key, context, errors, need)
    if os.environ.get('CAEL_PASSAGE_RANK', '1') != '0':
        # Second pass over the allowed passages: word rarity across the fetched pages, agreement between publishers,
        # the shape of an answer, and how close together the question's words stand (passage_rank.py).
        from . import passage_rank
        try:
            candidates = passage_rank.rerank(candidates, user_turns(messages)[-1], found, publisher)
        except Exception:
            pass
        if not candidates:
            return whole_answer(found, plan, messages) or closest(messages, text, found, terms, key, context, errors, need)
    candidates.sort(key=lambda c: -c[0])
    TRACE.update(candidates=candidates[:15], pages=[(f[0], f[2], len(f[3])) for f in found])
    best = candidates[0]
    if best[1] < 0.6:
        return whole_answer(found, plan, messages) or closest(messages, text, found, terms, key, context, errors, need)
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
    single = support is None and not main_article
    if single and (os.environ.get('CAEL_WEB_SINGLE', '1') == '0' or best[1] < 0.7 or best[3] in ('Wikivoyage', 'Wikibooks')):
        return whole_answer(found, plan, messages) or closest(messages, text, found, terms, key, context, errors, need)
    passage = re.sub(r'\s*\[\d+\]', '', best[2]).strip()
    if support:
        check = f'Checked against {support[3]} ("{support[4]}"), which says the same.'
        sources = [(best[3], best[4], best[5]), (support[3], support[4], support[5])]
    elif single:
        # One good passage and no second page that repeats it: give it, and say plainly that it is unconfirmed.
        check = 'I found this in one source only and could not confirm it with a second, so treat it as a pointer rather than a checked fact.'
        sources = [(best[3], best[4], best[5])]
    else:
        check = (f'Checked: this is from the encyclopedia article on {best[4]} itself and answers the question directly; '
                 f'I found no second page that repeats it.')
        sources = [(best[3], best[4], best[5])]
    shape = (STATE.get('plan') or {}).get('shape')
    lead = (LEADS[shape] + ' ') if shape in LEADS and shape_fit(best[2]) else 'I looked this up. ' if len(user_turns(messages)) == 1 else 'I looked that up. '
    wiki_names = set(dict(SITES).values())
    where = f'{best[3]}' if best[3] in wiki_names else f'{best[3]}, {best[5]}'
    # Advice and how-to questions: up to two more points from the other well-matching passages (other pages first).
    more = []
    wiki_set = set(dict(SITES).values())
    if not need and kind in ('how', 'what', 'which') and os.environ.get('CAEL_WEB_MORE', '1') != '0':
        # only passages that match the question about as well as the best one, from the same kind of source
        ranked = sorted((c for c in candidates[1:60] if c[1] >= 0.7 and c[0] >= best[0] - 0.15
                         and (c[3] in wiki_set) == (best[3] in wiki_set) and (c[3] not in wiki_set or c[4] == best[4])),
                        key=lambda c: (c[3] == best[3] and c[4] == best[4], -c[0]))
        for c in ranked:
            text_c = re.sub(r'\s*\[\d+\]', '', c[2]).strip()
            if any(near_copy(text_c, x) or text_c in x or x in text_c for x in [passage] + [m[0] for m in more]):
                continue
            if len({stem(w) for w in content(text_c)} & {stem(w) for w in content(passage)}) > 0.6 * len({stem(w) for w in content(text_c)}):
                continue
            if not ADVICE.search(text_c) or len(text_c.split()) > 45:
                continue        # a further point must itself be advice, not a teaser or background
            more.append((text_c, c))
            if len(more) == 2:
                break
    extra = ''
    if more:
        extra = '\n\nAlso worth knowing:\n' + '\n'.join(f'- {t}' for t, _ in more)
        for _, c in more:
            if (c[3], c[4], c[5]) not in sources:
                sources.append((c[3], c[4], c[5]))
    response = f'{lead}{passage}{extra}\n\nSource: {best[4]} ({where}). {check}'
    if single:
        TRACE.update(single=True)
    licence = lambda n: LICENCE if n in wiki_names else 'CC BY-SA (Stack Exchange)' if n.startswith('Stack Exchange') else WEB_LICENCE
    credits = '\n'.join(f'{n}: "{t}", {u} ({licence(n)})' for n, t, u in sources)
    web_pages = sum(1 for f in found if f[1] == 'web')
    return dict(route='chat/web-single' if single else 'chat/web-checked', response=response,
                sources=[dict(source=n, title=t, url=u, licence=licence(n)) for n, t, u in sources],
                details=f'Searched {", ".join(s[1] for s in SITES)} and the open web for "{text}"; read {len(found)} pages '
                        f'({web_pages} from the open web); coverage {best[1]:.2f}; '
                        f'{"corroborated" if support else "single source"}.\n{credits}' + (f'\nNotes: {"; ".join(errors)}' if errors else ''))


def local_search(plan, messages):
    """The Researcher's first, free and unlimited search: CAEL's own index of 285,000 human-written answers (Stack Exchange's
    everyday sites, OpenAssistant, Dolly), queried the way a person searches: the Planner's two or three key words, all of
    them required ("pigeons balcony", "swim nose", "grocery costs"), then each pair. The best-matching stored question is
    read whole (whole_answer), with the same subject and shape checks as a page from the web."""
    from . import open_chat as oc
    import sqlite3
    if not oc.db() or not plan:
        return None
    core = [w for w in (plan.get('core') or '').split() if w]
    if not core:
        return None
    variants = []
    need, want = list(plan.get('need') or []), list(plan.get('want') or [])
    for x in (plan.get('ask') or [])[:2]:
        for n in (need + want)[:4]:
            if n != x:
                variants += [[x, f] for f in spellings(n)[:2]]      # "dehumidifier carpet", "dehumidifier damp"
    if need:
        # the thing it must be about, with each of the other words in turn ("mirror hang", "window draughty"), in both spellings
        for w in want:
            for f in spellings(w):
                variants += [need + [f]] + [[n, f] for n in spellings(need[-1])]
        for n in need[-1:]:
            for f in spellings(n):
                if f != n:
                    variants += [[f] + want[:1], [f]]
        variants.append(need)
    variants += [core[:3], core[:2]] + [[a, b] for i, a in enumerate(core[:3]) for b in core[i + 1:3]]
    rephrased = [w for w in (plan.get('queries') or [''])[-1].split() if wc_weight(w) > 3.5 and w not in GENERIC][:4] if plan.get('queries') else []
    variants += [[a, b] for i, a in enumerate(rephrased) for b in rephrased[i + 1:]]
    # the same subject under its usual names: "cycling" is "bike" on the bicycle site
    try:
        from .advisor import general
        for w in core[:1]:
            for g in general(w)[:2]:
                variants += [[g, x] for x in core[1:3]]
    except Exception:
        pass
    if len(core) >= 2:
        variants.append(core[1:2])                      # the question's own key word alone ("puncture"), checked below
    seen, found = set(), []
    if INDEX_V2:
        # index v2 (retrieval.py): the whole conversation as a weighted query over the fielded index, BM25F and proximity
        # features, LambdaMART re-ranking; the Planner's variants are pulled too so nothing the old search found is lost
        try:
            from . import retrieval as rv
            hits = rv.search(messages, plan, k=30, extra_queries=variants)
        except Exception:
            hits = []
        for rank, h in enumerate(hits):
            d = h.doc
            if any(d['title'] == f[2] for f in found):
                continue
            name = f'Stack Exchange ({d["site"]})' if d['source'] == 'se' else {'oasst': 'OpenAssistant', 'dolly': 'Dolly'}.get(d['source'], d['source'])
            text = oc._clean(d['raw_answer'], limit=1800)
            if len(text) > 80 and oc.answer_quality(text) >= 0.4:
                found.append((name, 'stackexchange', d['title'], text, '', d['title'] + ' ' + (d['extra'] or '')[:400], d['votes'] or 0, h.score, dict(zip(rv.NAMES, h.f))))
        if found:
            variants = []
    for v in variants:
        v = [w for w in v if re.fullmatch(r"[a-z]+", w)]
        if not v or tuple(v) in seen:
            continue
        seen.add(tuple(v))
        try:
            rows = oc.db().execute('SELECT d.title, d.answer, d.source, d.site, d.votes, d.extra FROM idx JOIN doc d ON d.id = idx.rowid WHERE idx MATCH ? '
                                   'ORDER BY bm25(idx, 6.0, 1.0) LIMIT 8', (' AND '.join(f'"{w}"' for w in v),)).fetchall()
        except sqlite3.OperationalError:
            continue
        for title, body, source, site, votes, extra in rows:
            if any(title == f[2] for f in found):
                continue
            name = f'Stack Exchange ({site})' if source == 'se' else {'oasst': 'OpenAssistant', 'dolly': 'Dolly'}.get(source, source)
            text = oc._clean(body, limit=1800)
            if len(text) > 80 and oc.answer_quality(text) >= 0.4:
                # the stored question's own text, for the subject check: titles often use another word ("long tour" for cycling)
                found.append((name, 'stackexchange', title, text, '', title + ' ' + (extra or '')[:400], votes or 0))
        if len(found) >= (30 if need else 12):
            break
    got = whole_answer(found, plan, messages)
    if got:
        got['details'] = got['details'].replace('(web_check.whole_answer)', "(CAEL's local index of human-written answers; no network)")
        got['response'] = got['response'].replace(', ). One thread', '). One thread')
    return got


_TF_CACHE = {}


def title_features(title, messages, plan=None):
    """Index v2's thing-and-trouble check for any thread title (pages found on the web carry no v2 features)."""
    try:
        from . import retrieval as rv
        turns = tuple(user_turns(messages))
        key = (turns, str(sorted((plan or {}).items(), key=str)))
        q = _TF_CACHE.get(key)
        if q is None:
            q = rv.Query(list(turns), plan)
            _TF_CACHE.clear()
            _TF_CACHE[key] = q
        t = rv.toks(title)
        thing, prob, both, only, _ = rv.thing_problem(q, set(t), t)
        return dict(thing_title=thing, problem_title=prob, thing_and_problem=both, thing_only=only)
    except Exception:
        return {'thing_title': -1, 'problem_title': 1.0}


def confident(f, need=0.25):
    """Index v2 is sure enough of a thread to read it past the Planner's key-word gates: its title names the user's thing
    and the trouble ("How can I stop my dog from pulling on the leash?"), or, with no thing named, most of the trouble."""
    if f.get('thing_title', -1) < 0:
        return f.get('problem_title', 0) >= 0.5
    return f.get('thing_and_problem', 0) > 0 and f.get('problem_title', 0) >= need


def wc_weight(w):
    return weight(w)


INDEX_V2 = os.environ.get('CAEL_INDEX_V2', '1') != '0'
V2_WEIGHT = float(os.environ.get('CAEL_V2_WEIGHT', '1.5'))
V2_TRUST = os.environ.get('CAEL_V2_TRUST', '1') != '0'
ANCHOR = float(os.environ.get('CAEL_ANCHOR', '0.6'))
V2_STRICT = os.environ.get('CAEL_V2_STRICT', '0') != '0'


# British and American spellings of the same everyday words: the stored threads are mostly American ("drafty window")
SPELL = {'draught': 'draft', 'draughty': 'drafty', 'draughts': 'drafts', 'mould': 'mold', 'mouldy': 'moldy', 'colour': 'color', 'colours': 'colors',
         'tyre': 'tire', 'tyres': 'tires', 'aluminium': 'aluminum', 'grey': 'gray', 'favourite': 'favorite', 'organise': 'organize', 'nappy': 'diaper',
         'nappies': 'diapers', 'flat': 'apartment', 'hob': 'stove', 'cooker': 'stove', 'tap': 'faucet', 'taps': 'faucets', 'jumper': 'sweater',
         'trainers': 'sneakers', 'rubbish': 'trash', 'bin': 'trash', 'garden': 'yard', 'lorry': 'truck', 'petrol': 'gas', 'torch': 'flashlight',
         'fringe': 'bangs', 'courgette': 'zucchini', 'aubergine': 'eggplant', 'holiday': 'vacation', 'mum': 'mom', 'plaster': 'drywall',
         'skirting': 'baseboard', 'loft': 'attic', 'kerb': 'curb', 'storey': 'story', 'fibre': 'fiber', 'centre': 'center', 'metre': 'meter',
         'litre': 'liter', 'practise': 'practice', 'snores': 'snoring', 'snore': 'snoring', 'draughtproof': 'weatherstrip', 'blunt': 'dull', 'meowing': 'meow', 'overwatered': 'overwatering'}
SPELL_STEMS = None


def spellings(w):
    """The word and its other spelling: 'draughty' -> ['draughty', 'drafty']."""
    w = w.lower()
    other = SPELL.get(w) or next((k for k, v in SPELL.items() if v == w), None)
    out = [w] + ([other] if other and other != w else [])
    if w.startswith('draught'):
        out.append('draft')                 # "draughty window" is asked as "window drafts" too
    out += MORE_FORMS.get(w, [])
    return list(dict.fromkeys(out))


ANIMAL = re.compile(r"(?i)\b(?:dogs?|puppy|puppies|cats?|kittens?|rabbits?|bunny|bunnies|hamsters?|parrots?|birds?|horses?|guinea pigs?|ferrets?|rats?|fish|"
                    r"budgies?|parakeets?|cockatiels?|canar(?:y|ies)|tortoises?|turtles?|lizards?|snakes?|chickens?|goldfish|pets?)\b")


# irregular plurals and the people a word stands for ("partner" is a husband or a wife in most threads)
MORE_FORMS = {'knives': ['knife'], 'knife': ['knives'], 'leaves': ['leaf'], 'leaf': ['leaves'], 'shelves': ['shelf'], 'shelf': ['shelves'],
              'children': ['child', 'kids'], 'child': ['children', 'kid'], 'kids': ['child', 'children'], 'mice': ['mouse'], 'mouse': ['mice'],
              'teeth': ['tooth'], 'tooth': ['teeth'], 'feet': ['foot'], 'foot': ['feet'], 'wives': ['wife'], 'loaves': ['loaf'], 'geese': ['goose'],
              'partner': ['husband', 'wife', 'spouse', 'boyfriend', 'girlfriend', 'partner'], 'husband': ['spouse', 'partner'], 'wife': ['spouse', 'partner'],
              'toddler': ['toddler', 'baby', 'child', 'kid', 'son', 'daughter'], 'baby': ['infant', 'newborn', 'toddler'],
              'teenager': ['teen', 'teens', 'son', 'daughter'], 'twin': ['twins', 'kids', 'siblings', 'children', 'brothers', 'sisters'],
              'twins': ['twin', 'kids', 'siblings', 'children', 'brothers', 'sisters'], 'tap': ['faucet', 'spigot', 'bib', 'valve'],
              'jet': ['jetlag'], 'sewn': ['sew', 'sewing'], 'sew': ['sewing', 'sewn'], 'marks': ['mark', 'stain', 'stains', 'spots'], 'nap': ['naps', 'napping', 'sleep', 'sleeping', 'awake'], 'vet': ['vets', 'veterinarian', 'vet'], 'budgie': ['budgies', 'parakeet', 'parakeets', 'bird'], 'blunt': ['dull', 'sharpen', 'sharpening'], 'draughty': ['drafty', 'draft', 'drafts', 'seal'],
              'overwatered': ['overwatering', 'rot', 'rotting', 'soggy'], 'wobbly': ['wobble', 'wobbles', 'level', 'uneven'], 'squeaky': ['squeak', 'squeaks'], 'snores': ['snore', 'snoring'], 'snoring': ['snore', 'snores']}


def spelled_stems(w):
    return {stem(x) for x in spellings(w)}


def question_sentence(messages):
    last = user_turns(messages)[-1] if messages else ''
    asked = [x for x in re.split(r'(?<=[.!?])\s+', last) if x.strip().endswith('?')]
    return asked[-1] if asked else last


_SITE_CACHE = {}


def scene_sites(messages):
    """The local index's site classifier on everything the user has said: {'lifehacks': 0.99, ...} for a steam iron."""
    text = ' '.join(user_turns(messages)[-6:])
    if text not in _SITE_CACHE:
        try:
            from . import open_chat as oc
            _SITE_CACHE[text] = oc.site_probs(oc.weights(text))
        except Exception:
            _SITE_CACHE[text] = {}
        if len(_SITE_CACHE) > 500:
            _SITE_CACHE.pop(next(iter(_SITE_CACHE)))
    return _SITE_CACHE[text]


def site_fits(name, messages, plan=None):
    """Does a stored answer's site fit what the conversation is about? Stack Exchange threads: the site must be one the
    classifier gives a real chance (5% or more) or one the Planner chose. OpenAssistant and Dolly answers have no site:
    they are kept only when no single site dominates the conversation (an everyday question with no clear home)."""
    probs = scene_sites(messages)
    if not probs:
        return True
    m = re.search(r'Stack Exchange \(([^)]+)\)', name)
    planned = {x.lower() for x in ((plan or {}).get('sites') or [])}
    if m:
        site = m[1].lower()
        from .stack_source import SITES as SE_SITES
        code = next((k for k, (title, _) in SE_SITES.items() if title.lower() == site), site)
        return probs.get(code, probs.get(site, 0.0)) >= 0.05 or code in planned or site in planned
    top = max(probs.values()) if probs else 0
    return top < 0.6 or probs.get('general', 0) >= 0.05


def title_match(title, messages):
    """F-score between a stored question's title and the conversation, by word weight: recall over the user's words
    (the last question's own words count double, the first told sentence one and a half), precision over the title's words."""
    turns = user_turns(messages)
    if not turns:
        return 0.0
    want = {}
    for i, t in enumerate(turns[-4:]):
        k = 2.0 if t is turns[-1] else 1.5 if i == 0 else 1.0
        for w in content(t):
            if w in GENERIC:
                continue
            for f in spelled_stems(w):
                want[f] = max(want.get(f, 0), weight(w) * k)
    if not want:
        return 0.0
    tw = {}
    for w in content(title):
        if w not in GENERIC:
            tw[stem(w)] = weight(w)
    if not tw:
        return 0.0
    hit_recall = sum(v for f, v in want.items() if f in tw)
    top = sorted(want.values(), reverse=True)[:6]
    recall = hit_recall / (sum(top) or 1)
    precision = sum(v for f, v in tw.items() if f in want) / (sum(tw.values()) or 1)
    return 0.0 if not recall or not precision else 2 * recall * precision / (recall + precision)


RANK_FLOOR = 0.25


def rank_thread(item, rank, messages):
    """The learned ranker's chance that a stored thread is the one this conversation is asking about (None without weights)."""
    from . import thread_ranker as tr
    if not tr.weights():
        return None
    name, host, title, body, url = item[:5]
    about = item[5] if len(item) > 5 else title
    votes = item[6] if len(item) > 6 and isinstance(item[6], (int, float)) else 0
    m = re.search(r'Stack Exchange \(([^)]+)\)', name)
    site = m[1].lower() if m else ''
    from .stack_source import SITES as SE_SITES
    site = next((k for k, (t, _) in SE_SITES.items() if t.lower() == site), site)
    turns = user_turns(messages)
    desc = about[len(title):] if about.startswith(title) else about
    vec = tr.features(turns, title, site, votes, rank, scene_sites(messages), answer=body, body=desc)
    return tr.score(vec)


def told_pairs(messages):
    """Neighbouring content words of what the user told and asked ("shower low pressure" -> (low, pressure), (shower, low))."""
    turns = user_turns(messages)
    text = ' '.join(turns[-4:])
    out = []
    for sent in re.split(r'(?<=[.!?])\s+', text):
        seq = [w for w in content(sent) if w not in GENERIC and w not in ('really', 'very', 'quite', 'just', 'bit', 'lot', 'still', 'again')]
        out += [(a, b) for a, b in zip(seq, seq[1:]) if a != b]
    # the thing and what is wrong with it, said in different sentences ("I pulled a muscle ... It's really tight")
    try:
        from .team import Board, plan as _plan
    except Exception:
        Board = None
    return list(dict.fromkeys(out))[:12]


def whole_answer(found, plan, messages):
    """The Researcher reading a matched Stack Exchange thread as a person would: the stored question is about the same
    subject and asks the same thing, so its best answer is the answer, trimmed to the shape the Planner asked for.
    Only with a plan, only for answers people give from experience (steps, how often, is it normal, which/should, why)."""
    if not plan or plan.get('shape') not in ('steps', 'often', 'normal', 'choose', 'why', 'amount') and not (plan.get('need') and plan.get('own_from') != 'question'
                                                                                                         or plan.get('need') and plan.get('shape') == 'fact' and len(user_turns(messages)) > 1):
        return None
    subject = (plan.get('core') or plan.get('subject') or '').split()
    asked = {w: weight(w) for w in content((plan.get('bound') or '') + ' ' + (plan.get('core') or '')) if w not in GENERIC}
    if not asked:
        return None
    best = None
    core_stems = {stem(w) for w in subject}
    try:
        from .advisor import general
        for w in subject[:1]:
            core_stems |= {stem(g) for g in general(w)[:2]}        # "cycling" also counts as "bike"
    except Exception:
        pass
    need, want = list(plan.get('need') or []), list(plan.get('want') or [])
    need_forms = []
    for w in need:
        forms = spelled_stems(w)
        try:
            from .advisor import general
            forms |= {stem(g) for g in general(w)[:2]}
        except Exception:
            pass
        need_forms.append(forms)
    ask_forms = [spelled_stems(w) for w in (plan.get('ask') or [])]
    ask_hit = True
    want_forms = [spelled_stems(w) for w in want]
    quoted = set(re.findall(r'\nSource: (.+?) \(', ' '.join(str(m.get('content') or '') for m in messages if m.get('role') == 'assistant')))
    kept = []
    probs_seen = {}
    v2_top = max((f[7] for f in found if len(f) > 7), default=None)
    quoted |= set(re.findall(r'; also "(.+?)" \(', ' '.join(str(m.get('content') or '') for m in messages if m.get('role') == 'assistant')))
    for item in found:
        name, host, title, body, url = item[:5]
        # index v2's two best threads for the whole conversation are read even when the Planner's key words miss them
        # (a plan can pick the wrong word: "minute" for a friend who cancels at the last minute)
        trusted = len(item) > 8 and v2_top is not None and V2_TRUST and found.index(item) < 2 and confident(item[8])
        if (V2_STRICT or plan.get('strict')) and not confident(item[8] if len(item) > 8 else title_features(title, messages, plan),
                                                                 0.35 if plan.get('strict') else 0.25):
            # index v2 does not see the user's thing and its trouble in this title: not the same problem. Always so for
            # unasked help (a problem told without a question), where a near-miss thread reads as not listening
            continue
        if title in quoted:
            continue                    # already quoted in this chat: a follow-up needs something new, not the same thread again
        about = item[5] if len(item) > 5 else title
        if host != 'stackexchange':
            continue
        t = {stem(w) for w in content(title)}
        a = {stem(w) for w in content(about)}
        if ANIMAL.search(about) and not ANIMAL.search(' '.join(user_turns(messages))):
            continue                    # a thread about a dog or a cat for a question about people ("snoring")
        if not site_fits(name, messages, plan):
            continue                    # a Minecraft iron farm for a steam iron: the conversation is not about that site's subject
        focus_title = bool(ask_forms) and any(f & t for f in ask_forms) and (any(f & a for f in need_forms) or any(f & a for f in want_forms))
        if need_forms and not focus_title:
            # the plan says what the thread must be about ("mirror", "kitchen knives") and what it should also speak to
            # ("hang", "draughty", "sharpen"): all of the first in the thread and one in its title, one of the second
            if not all(f & a for f in need_forms) or not any(f & t for f in need_forms):
                if not trusted:
                    continue
            if want_forms and not any(f & a for f in want_forms):
                if not trusted:
                    continue
            ask_hit = not ask_forms or any(f & a for f in ask_forms)      # the question's own words ("whetstone", "curtains")
            if want_forms and not any(f & t for f in want_forms + need_forms[:-1]) and len(need_forms) < 2:
                if not trusted:
                    continue                # "mirror" alone in the title is not enough: "hang", "heavy" or the like with it
        elif subject and len(core_stems & a) < min(2, len({stem(w) for w in subject})):
            if not trusted:
                continue                    # the thread must be about the subject and the question: "swim" and "nose", not "nose" alone
        own_words = {stem(w) for w in subject[1:]}
        strict = plan.get('own_from', 'question') == 'question'      # words from the question itself must all be there
        if not need_forms and own_words and (not own_words & t or (strict and not own_words <= a)):
            if not trusted:
                continue                    # every word of what is asked ("survive" and "economy") in the thread, one of them in its title
        a_all = a | {x for w in a for x in spelled_stems(w)}
        cov = sum(v for w, v in asked.items() if w in a_all or spelled_stems(w) & a_all) / sum(asked.values())
        # the stored question's title must itself ask much of the same thing: most of the weight of what is asked (the
        # question sentence and the Planner's key words), so "economy" alone does not turn a long-flight question into fares
        asking = {w: weight(w) for w in content(plan.get('core') or question_sentence(messages)) if w not in GENERIC}
        t_all = t | {x for w in t for x in spelled_stems(w)}
        title_cov = sum(v for w, v in asking.items() if w in t_all or spelled_stems(w) & t_all) / (sum(asking.values()) or 1)
        if title_cov < (0.3 if need_forms and ask_hit else 0.5):
            if not trusted:
                continue                    # most of the weight of the Planner's key words in the stored question's title
        if cov < (0.2 if need_forms else 0.25):
            if not trusted:
                continue
        sents = [x.strip() for x in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"(])', body) if 5 <= len(x.split()) <= 45]
        sents = [x for x in sents if not re.search(r"(?i)\b(?:op\b|this question|your question|other question|edit:|update from|upvot|downvot|https?://|answer above|"
                                                   r"answers? below|tbh|imho|\.se\b|stack ?exchange|this site|video|link|linked|comments?\b|as (?:others|someone) (?:said|mentioned)|"
                                                   r"[a-z]+'s answer|@\w+)", x)
                 and not re.match(r"\s*(?:also|and|but|so|or|then|that|this|it|they)\b[ ,]", x, re.I) and x[:1].isupper()]
        advice = [x for x in sents if re.search(r"(?i)\b(?:you|your|try|use|make sure|avoid|don'?t|should|can|best|need|keep|put|get|start)\b", x)]
        if len(advice) >= 2:
            sents = advice
        if not sents:
            continue
        cue = SHAPE_CUES.get(plan['shape'])
        fit = [x for x in sents if cue and re.search(cue, x, re.I)]
        if plan['shape'] == 'often' and not fit:
            continue                    # "how often" needs a frequency
        picked = (fit[:2] + [x for x in sents if x not in fit])[:4] if fit else sents[:4]
        picked = [x for x in sents if x in picked]                              # in the writer's own order
        # a stored question that asks what was asked ranks first: "How do I prevent window drafts?" over a thread that only
        # mentions windows; then how much of the asked weight the thread covers, and sentences of the wanted shape
        votes = item[6] if len(item) > 6 and isinstance(item[6], (int, float)) else 0
        howto = 0.3 if plan['shape'] == 'steps' and re.match(r"(?i)\s*(?:how (?:do|can|should|to|would)|what(?:'s| is) the (?:best|easiest)|best way|tips|ways? to|what can)", title) else 0
        score = cov + 0.1 * len(fit) + (1.5 * title_cov + 0.08 * math.log1p(max(0, votes)) + howto + (0.5 if ask_forms and ask_hit else 0) if need_forms else 0)
        if len(item) > 7 and v2_top is not None:
            # index v2's LambdaMART score, relative to the best thread it found for this conversation
            score += V2_WEIGHT * max(-3.0, item[7] - v2_top)
        site = re.search(r'\(([^)]+)\)', name)
        site = site[1].lower() if site else ''
        planned_sites = [x.lower() for x in (plan.get('sites') or [])]
        if need_forms and planned_sites and site:
            from .stack_source import SITES as SE_SITES
            names = set(planned_sites) | {SE_SITES[x][0].lower() for x in planned_sites if x in SE_SITES}
            score += 0.3 if site in names else -0.3         # a baking mould for a shower seal is on the wrong site
        if need_forms:
            # a stored question about a narrower case than the user's ("serrated knives", "Japanese knives", "in the wild")
            # ranks below the plain one: each weighty title word the user never said costs a little
            said_stems = {stem(w) for w in content(' '.join(user_turns(messages)))}
            said_stems |= {x for w in list(said_stems) for x in spelled_stems(w)}
            extra = [w for w in content(title) if w not in GENERIC and weight(w) > 5.5 and not (spelled_stems(w) & said_stems)]
            score -= 0.25 * len(extra)
            # the user's own phrase in the stored question's title ("low pressure", "draining slowly", "keeps running") is the
            # strongest sign the thread is about the same problem, not just the same words used differently ("blocking")
            title_seq = [stem(w) for w in content(title)]
            pairs = 0
            for x, y in told_pairs(messages):
                fx, fy = spelled_stems(x), spelled_stems(y)
                pos_x = [i for i, w in enumerate(title_seq) if w in fx]
                pos_y = [i for i, w in enumerate(title_seq) if w in fy]
                if any(abs(i - j) <= 2 for i in pos_x for j in pos_y):
                    pairs += 1
            score += 0.6 * min(2, pairs)
            keys_in_title = sum(1 for f in need_forms + want_forms + ask_forms if f & set(title_seq))
            if focus_title:
                score += 0.6
            # the main ranking: the learned thread ranker (thread_ranker.py), trained on the index itself; the hand-made title
            # match stands in when no weights are present
            learned = rank_thread(item, found.index(item), messages)
            if learned is None:
                score += 3.0 * title_match(title, messages)
            else:
                if learned < RANK_FLOOR:
                    if not trusted:
                        continue            # the ranker is sure enough this thread is not the one asked about
                score += 5.0 * learned
                probs_seen[title] = learned
            if keys_in_title < 2 and not (keys_in_title == 1 and pairs):
                if not trusted:
                    continue                # "How can I brush my toddler's teeth?" for a baby's rash: one shared word is not the same question
            # the user's rarest words in the stored question's title ("Doha", "calf", "rash"): the same case, not a neighbour of it
            rare = {stem(w) for w in content(' '.join(user_turns(messages)[-4:])) if weight(w) >= 7.0 and w not in GENERIC}
            score += 0.4 * min(2, len(rare & set(title_seq)))
            if plan.get('strict') and want_forms and not any(f & t for f in want_forms):
                if not trusted:
                    continue                # a reply to a told problem needs the problem itself in the stored question's title
        kept.append((score, title, picked, name, url, body))
        if best is None or score > best[0]:
            best = (score, title, picked, name, url)
    if not best:
        return None
    composed = compose(kept, plan, messages)
    if composed:
        composed['rank_prob'] = max((probs_seen.get(t, 1.0) for _, t, _, _, _, _ in kept[:1]), default=1.0) if kept else 1.0
        composed['rank_prob'] = max(probs_seen.values()) if probs_seen else 1.0
        return composed
    score, title, picked, name, url = best
    text = ' '.join(picked)
    lead = LEADS.get(plan['shape'], 'From what I found:')
    return dict(route='chat/web-single', response=f'{lead} {text}\n\nSource: {title} ({name}, {url}). One thread with an answer from people who '
                                                  f'have dealt with it; not checked against a second source.',
                sources=[dict(source=name, title=title, url=url, licence='CC BY-SA (Stack Exchange)')], rank_prob=probs_seen.get(title, 1.0),
                details=f'The best answer to a stored question on the same subject ("{title}"), read whole and trimmed to a "{plan["shape"]}" '
                        f'answer (web_check.whole_answer).')


ADVICE_CUE = re.compile(r"(?i)\b(?:you (?:can|could|should|might|need|want|may)|try|use|make sure|avoid|don'?t|do not|check|keep|put|add|remove|replace|"
                        r"clean|wipe|soak|rinse|let it|leave it|give it|start with|instead|best (?:way|thing)|it helps|helps|works|recommend)\b")
JUNK = re.compile(r"(?i)\b(?:op\b|this question|your question|other question|edit:|update:|update from|upvot|downvot|https?://|answer above|answers? below|"
                  r"tbh|imho|\.se\b|stack ?exchange|this site|video|link|linked|comments?\b|as (?:others|someone) (?:said|mentioned)|[a-z]+'s answer|@\w+|"
                  r"pictures? would|photo|good luck|hope (?:this|that) helps|welcome to)")


def compose(kept, plan, messages):
    """The Researcher answering as a person would after reading a few threads: the sentences that speak to what was asked
    (the question's own words first, then the thing and its problem), advice before anecdote, no repeats, from the best
    two or three threads, listed with where they came from. Only sentences people wrote; nothing added."""
    if not kept:
        return None
    kept = sorted(kept, key=lambda k: -k[0])
    top = [k for k in kept if k[0] >= kept[0][0] - 1.2][:3]
    q = question_sentence(messages)
    own = {stem(w): weight(w) for w in content(q) if w not in GENERIC and w not in ('help', 'work', 'thing', 'way', 'really', 'actually')}
    scene = {}
    for w in (plan.get('need') or []) + (plan.get('want') or []):
        for f in spelled_stems(w):
            scene[f] = max(scene.get(f, 0), weight(w))
    follow = len(user_turns(messages)) > 1 and bool(own)
    cue = SHAPE_CUES.get(plan.get('shape'))
    said_before = ' '.join(str(m.get('content') or '') for m in messages[:-1] if m.get('role') == 'assistant')
    cands = []
    for rank, (score, title, picked, name, url, body) in enumerate(top):
        for x in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"(])', body):
            x = re.sub(r'\s+', ' ', x).strip(' -*')
            n = len(x.split())
            if n < 6 or n > 42 or '?' in x or JUNK.search(x) or not x[:1].isupper() or x[:50] in said_before:
                continue
            words = {stem(w) for w in content(x)}
            words |= {f for w in list(words) for f in spelled_stems(w)}
            own_hit = sum(v for w, v in own.items() if w in words or spelled_stems(w) & words)
            scene_hit = sum(v for w, v in scene.items() if w in words)
            # threads whose titles already ask the user's follow-up (coherence.thread_answer): their advice is on point even when a
            # sentence doesn't repeat the question's words ("Pour a kettle of boiling water down it" for "How do I clean it?")
            titled = bool(plan.get('title_asked') and ADVICE_CUE.search(x))
            if follow and not own_hit and not (scene_hit and ADVICE_CUE.search(x)) and not titled:
                continue
            if not own_hit and not scene_hit and not titled:
                continue
            sc = 0.25 * own_hit + 0.12 * scene_hit + (0.8 if ADVICE_CUE.search(x) else 0) + (0.5 if cue and re.search(cue, x, re.I) else 0) - ANCHOR * rank
            if re.match(r"(?i)\s*(?:i|we|my|our|in my|when i|everyone|someone|he|she)\b", x) and not re.search(r"(?i)\b(?:recommend|suggest|would|always|found that|use|try)\b", x):
                continue                    # an anecdote ("I ended up digging...", "Everyone else acted scared...") is not advice
            if re.match(r"(?i)\s*(?:also|and|but|so|or|then|that|this|it|they|these|those|however|anyway|otherwise|only|unless|of course)\b", x):
                continue                    # leans on a sentence that is not quoted
            cands.append((sc, x, title, name))
    cands.sort(key=lambda c: -c[0])
    picked, used = [], []
    for sc, x, title, name in cands:
        toks = set(re.findall(r'[a-z]+', x.lower()))
        if any(len(toks & set(re.findall(r'[a-z]+', y.lower()))) / max(1, len(toks)) > 0.5 for y in picked):
            continue
        if sc < 0.6:
            break
        picked.append(x)
        if (title, name) not in used:
            used.append((title, name))
        if len(picked) >= 4:
            break
    if len(picked) < 2:
        return None
    lead = {'why': 'The usual reasons, from people who have dealt with it:', 'often': 'How often, from people who have dealt with it:',
            'choose': 'What people who have been there say:', 'normal': 'What people who have dealt with it say:'}.get(
        plan.get('shape'), "Here's what people who have dealt with it suggest:")
    bullets = '\n'.join('- ' + x for x in picked)
    order = {(k[1], k[3]): i for i, k in enumerate(top)}
    used.sort(key=lambda u: order.get(u, 99))            # the best-ranked thread is named first
    first = used[0]
    also = ''.join(f'; also "{t}" ({n})' for t, n in used[1:3])
    return dict(route='chat/web-single', response=f'{lead}\n\n{bullets}\n\nSource: {first[0]} ({first[1]}){also}. Answers from people who have dealt '
                                                  f'with it, put together from {len(used)} thread{"s" if len(used) > 1 else ""}; not checked by an expert.',
                sources=[dict(source=n, title=t, url='', licence='CC BY-SA (Stack Exchange)') for t, n in used],
                details=f'Advice sentences that speak to "{q}", from {len(used)} stored thread(s) on the same subject (web_check.compose).')


def closest(messages, text, found, terms, key, context, errors, need=None):
    """No passage passed the strict tests: give the passage nearest to the question from the pages that were read, clearly
    labelled as the closest match, instead of nothing. Still a quotation with its source; never an invented answer."""
    if os.environ.get('CAEL_WEB_SINGLE', '1') == '0' or not found:
        return none_found(text, found)
    total = sum(terms.values()) or 1.0
    wiki_names = set(dict(SITES).values())
    best = None
    for name, host, title, body, url in found:
        wiki = host in WIKI_HOSTS
        if name in ('Wikivoyage', 'Wikibooks'):
            continue
        title_stems = {stem(w) for w in words(title)}
        if not title_stems & {stem(w) for w in terms}:
            continue
        from . import passage_rank
        wanted = set(passage_rank.tokens(user_turns(messages)[-1]))
        if len(wanted) >= 3 and len(wanted & set(passage_rank.tokens(title + ' ' + body))) / len(wanted) < 0.6:
            continue        # the page lacks much of what was asked: it is about something else
        q_toks = passage_rank.tokens(user_turns(messages)[-1])
        seq = passage_rank.tokens(title + ' . ' + body)
        near = {(x, y) for i, x in enumerate(seq) for y in seq[i + 1:i + 3]}
        if len(q_toks) >= 3 and not any((x, y) in near or (y, x) in near for x, y in zip(q_toks, q_toks[1:]) if x != y):
            continue        # none of the question's word pairs stand together anywhere on the page
        sents = sentences(body)
        for i in range(len(sents)):
            for size in (1, 2):
                if i + size > len(sents):
                    break
                window = ' '.join(sents[i:i + size])
                if len(window.split()) > (70 if wiki else 50) or len(window.split()) < 8 or '?' in window or FILLER.search(window):
                    continue
                if re.search(r'https?://|www\.|Retrieved |Accessed |\bet al\.|affiliate|commission|sponsored|\b[A-Z]{3,}(?:\s+[A-Z]{2,}){2,}\b|[»›|]| > ', window):
                    continue
                if ANAPHORA.search(window) or (need and not re.search(NEED[need], window, 0 if need == 'who' else re.I)):
                    continue
                said = {stem(w) for w in words(window)}
                cov = (sum(v for w, v in terms.items() if stem(w) in said) + 0.5 * sum(v for w, v in terms.items() if stem(w) in title_stems - said)) / total
                if key and stem(key) not in said | title_stems:
                    continue
                s = cov + 0.05 * len(context & said) + 0.08 * (len(sents) - i) / max(1, len(sents)) - 0.02 * (size - 1)
                if cov >= 0.6 and (best is None or s > best[0]):
                    best = (s, cov, window, name, title, url)
    if best is None:
        return none_found(text, found)
    passage = re.sub(r'\s*\[\d+\]', '', best[2]).strip()
    where = f'{best[3]}' if best[3] in wiki_names else f'{best[3]}, {best[5]}'
    licence = LICENCE if best[3] in wiki_names else 'CC BY-SA (Stack Exchange)' if best[3].startswith('Stack Exchange') else WEB_LICENCE
    return dict(route='chat/web-closest',
                response=f"I couldn't find a page that answers that exactly, but this is the closest I found: {passage}\n\n"
                         f"Source: {best[4]} ({where}). One source, not confirmed by a second.",
                sources=[dict(source=best[3], title=best[4], url=best[5], licence=licence)],
                details=f'Searched for "{text}"; read {len(found)} pages; no passage passed the strict answer tests, so the nearest passage '
                        f'(coverage {best[1]:.2f}) is quoted as such.' + (f'\nNotes: {"; ".join(errors)}' if errors else ''))


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
        # "What's the tallest mountain in the world?" answered with a long forum post: a plain fact question is looked up.
        factual = bool(RETRIEVED.search(route) and re.match(
            r"(?i)\s*(?:what|who|when|where|which)(?:'s|\s+(?:is|are|was|were|did|does|do))\b", user_turns(messages)[-1])
            and not re.search(r"(?i)\b(?:you|your|i|my|me|we|our)\b", user_turns(messages)[-1]))
        if factual and not dead:
            off_topic = True
        if not (dead or off_topic):
            return result
        found = answer(messages)
    except Exception:
        return result
    if found is None:
        return result
    if found.get('route') == 'chat/web-single' and route.startswith('chat/web-') and not gave_up:
        return result            # "the page was damaged", "the provider is down": an unconfirmed passage does not replace that
    if found.get('route') in ('chat/web-checked-none', 'chat/web-closest') and route.startswith('chat/web-'):
        return result            # CAEL's own lookup already said why it could not answer; keep that more specific reply
    years = re.findall(r'\b(?:1[0-9]{3}|20[0-9]{2})\b', user_turns(messages)[-1])
    if years and found.get('route') in ('chat/web-checked', 'chat/web-single', 'chat/web-closest') and not any(
            y in str(found.get('response', '')) for y in years):
        return result            # "What happened in Asteria in 1847?": a page about Asteria that never mentions 1847 is not an answer
    if off_topic and found.get('route') != 'chat/web-checked':
        if factual and found.get('route') == 'chat/web-single':
            return dict(found, replaced_route=result.get('route'), replaced_because='fact question')
        terms, key, kind, own, need, subject = query(messages)
        mine = {stem(w) for w in own if w in terms}
        far_off = len(mine) >= 3 and len(mine & {stem(w) for w in words(said)}) * 2 < len(mine)
        if far_off and found.get('route') == 'chat/web-single':
            return dict(found, replaced_route=result.get('route'), replaced_because='off topic')
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
    mine = {stem(w) for w in own if w in terms}
    if len(mine) >= 3 and len(mine & have) * 2 < len(mine):
        return False        # "season a cast iron pan" answered with the seasons of the year: one word in four
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

FOLLOW_CUES = [
    (r"(?i)\bwhat (?:will|do|would|should) (?:i|we) need\b|\btools?\b|\bwhat (?:to|should i) buy\b", r"(?i)\byou(?:'ll| will)? need\b|\buse (?:a|an|some)\b|\btools?\b|\bkit\b|\bspanner\b|\bwrench\b|\bscrewdriver\b|\bbuy\b|\bpliers\b"),
    (r"(?i)\bworry|\bdangerous|\bserious|\bsafe\b|\bharm|\brisk|\bbad sign|\bnormal\b", r"(?i)\bsafe\b|\bdanger|\bworr|\bserious|\bharm|\brisk|\bnothing to\b|\bfine\b|\bnormal\b|\bvet\b|\bdoctor\b"),
    (r"(?i)^\s*(?:and |so )?why\b|\bwhat causes\b|\bhow come\b", r"(?i)\bbecause\b|\bcaus|\breason\b|\bdue to\b|\bhappens when\b|\bcomes from\b|\bmeans\b"),
    (r"(?i)\bagain\b|\bprevent|\bstop (?:it|that|this)\b|\bin future\b|\bavoid\b", r"(?i)\bprevent|\bavoid\b|\bregular|\bevery (?:week|month|few)\b|\bin future\b|\bkeep\b|\bonce a\b"),
    (r"(?i)\bfirst\b|\beasiest\b|\bsimplest\b|\bstart\b|\btry\b", r"(?i)\bfirst\b|\bstart\b|\beasiest\b|\bsimplest\b|\btry\b|\bcheck\b"),
    (r"(?i)\bmyself\b|\bourselves\b|\bdiy\b|\bsomeone in\b|\bprofessional\b|\bcall (?:someone|a)\b|\bworth getting\b", r"(?i)\byourself\b|\bdiy\b|\beasy\b|\bprofessional\b|\bplumber\b|\belectrician\b|\bcall\b|\bexpert\b|\btechnician\b"),
    (r"(?i)\bhow long\b|\bhow soon\b|\bhow quickly\b", r"(?i)\b(?:minutes?|hours?|days?|weeks?|months?)\b"),
]


def continue_thread(messages, plan=None):
    """A follow-up that no new thread answers ("What will I need?", "Is it anything to worry about?") after CAEL quoted a
    stored thread: the same thread's other sentences that speak to it, when there are any. People do the same: they read on."""
    from . import open_chat as oc
    turns = user_turns(messages)
    if len(turns) < 2 or not oc.db():
        return None
    q = question_sentence(messages)
    cue = next((want for asked, want in FOLLOW_CUES if re.search(asked, q)), None)
    if not cue:
        return None
    before = [str(m.get('content') or '') for m in messages[:-1] if m.get('role') == 'assistant']
    title = None
    for text in reversed(before):
        m = re.search(r'\nSource: (.+?) \(Stack Exchange \(', text)
        if m:
            title = m[1]
            break
    if not title:
        return None
    rows = oc.db().execute('SELECT answer, site FROM doc WHERE title = ? LIMIT 4', (title,)).fetchall()
    said = ' '.join(before)
    picked = []
    for body, site in rows:
        text = oc._clean(body, limit=4000)
        for x in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"(])', text):
            x = x.strip()
            if 5 <= len(x.split()) <= 45 and re.search(cue, x) and x[:60] not in said and x not in picked and x[:1].isupper() \
                    and not re.search(r"(?i)\b(?:op\b|this question|your question|edit:|upvot|https?://|video|link|@\w+)", x):
                picked.append(x)
        if len(picked) >= 3:
            break
    if not picked:
        return None
    name = f'Stack Exchange ({rows[0][1]})'
    return dict(route='chat/web-single', response=f"From the same thread: {' '.join(picked[:3])}\n\nSource: {title} ({name}). One thread with an answer "
                                                  f"from people who have dealt with it; not checked against a second source.",
                sources=[dict(source=name, title=title, url='', licence='CC BY-SA (Stack Exchange)')],
                details='Further sentences of the thread quoted before, that speak to the follow-up (web_check.continue_thread).')
