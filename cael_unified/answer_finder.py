"""Short factual answers found in Wikipedia's opening paragraphs: superlatives, counts and years.

"What is the largest planet in the solar system?" searches Wikipedia, reads the opening paragraph of the top
articles and accepts an answer only from a sentence that contains the superlative (or a synonym) and the
question's scope words: "Jupiter is ... the largest in the Solar System." Counts need a number right before the
counted thing; years come from a date range in the opening sentence or a sentence with the asked verb.
Nothing is guessed: when no sentence passes these checks the question goes on to the other engines.
Wikipedia text is CC BY-SA 4.0 and every answer links its article. No neural model.
"""
import re
from urllib.parse import urlencode

WIKI = 'https://en.wikipedia.org/w/api.php?'
SYNONYMS = {'largest': ('largest', 'biggest'), 'biggest': ('largest', 'biggest'), 'tallest': ('tallest', 'highest'),
            'highest': ('highest', 'tallest'), 'smallest': ('smallest', 'tiniest'), 'longest': ('longest',),
            'deepest': ('deepest',), 'fastest': ('fastest',), 'hottest': ('hottest',), 'coldest': ('coldest',),
            'oldest': ('oldest',), 'heaviest': ('heaviest',), 'lightest': ('lightest',), 'shortest': ('shortest',),
            'most populous': ('most populous', 'largest'), 'brightest': ('brightest',), 'driest': ('driest',),
            'wettest': ('wettest',), 'widest': ('widest',), 'loudest': ('loudest',), 'busiest': ('busiest',),
            'closest': ('closest', 'nearest'), 'nearest': ('nearest', 'closest'), 'farthest': ('farthest', 'most distant')}
NUMBER_WORDS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
                'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'twenty': 20}
STOP = set('the a an of in on at to for is are was were be what which who how many much does do did there our world earth '
           'known ever and or by with from that this it its as'.split())
SUPERLATIVE = re.compile(r'(?i)^(?:what|which|who)(?:\'s| is| was| are) the (' + '|'.join(sorted(SYNONYMS, key=len, reverse=True))
                         + r') (.+?)(?: (?:in|on|of|from|across) (?:the |our )?(.+?))?\s*[?.!]*$')
COUNT = re.compile(r'(?i)^how many (.+?) (?:are there|are|is|were|does|do|did|has|have) (?:there )?(?:in |on |inside |)(?:an? |the )?(.*?)'
                   r'(?: have| has| contain)?\s*[?.!]*$')
YEAR = re.compile(r'(?i)^(?:in )?(?:what|which) year (?:did|was|were) (?:the )?(.+?) (end|finish|begin|start|happen|take place|occur|sink|'
                  r'fall|open|close|die|win|launch|land)(?:ed|s)?\s*[?.!]*$|^when did (?:the )?(.+?) (end|finish|begin|start|sink|fall|happen)\s*[?.!]*$')
PAST = {'end': 'ended', 'finish': 'finished', 'begin': 'began', 'start': 'started', 'happen': 'happened', 'take place': 'took place',
        'occur': 'occurred', 'sink': 'sank', 'fall': 'fell', 'open': 'opened', 'close': 'closed', 'die': 'died', 'win': 'won',
        'launch': 'launched', 'land': 'landed'}


def words(text):
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP]


def stem(word):
    return re.sub(r'(?:ies|es|s)$', '', word) if len(word) > 4 else word


def sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+(?=[A-Z])', text) if s.strip()]


class Finder:
    def __init__(self, net):
        self.net = net

    def intros(self, *queries, limit=6):
        """Opening paragraphs of the top search results for each query: (title, intro, url, article length)."""
        titles = []
        for query in queries:
            found = self.net.json(WIKI + urlencode(dict(action='query', format='json', list='search', srsearch=query[:200],
                                                         srlimit=limit, srnamespace=0)), ttl=86400)
            for hit in found.get('query', {}).get('search', []):
                if not hit['title'].startswith(('List of', 'Lists of')) and hit['title'] not in titles:
                    titles.append(hit['title'])
        if not titles:
            return []
        ordered = []
        for start in range(0, min(len(titles), 12), 6):
            batch = titles[start:start + 6]
            pages = self.net.json(WIKI + urlencode(dict(action='query', format='json', prop='extracts|info', exintro=1, explaintext=1,
                                                         exlimit='max', inprop='url', redirects=1, titles='|'.join(batch))), ttl=86400)
            by_title = {p.get('title'): p for p in pages.get('query', {}).get('pages', {}).values() if p.get('extract')}
            redirects = {r['from']: r['to'] for r in pages.get('query', {}).get('redirects', [])}
            for title in batch:
                page = by_title.get(redirects.get(title, title))
                if page and not re.search(r'(?i)\bmay (?:also )?refer to\b', page['extract'][:400]):
                    ordered.append((page['title'], page['extract'], page.get('fullurl', 'https://en.wikipedia.org/wiki/' + page['title'].replace(' ', '_')),
                                    page.get('length', 0)))
        return ordered

    def answer(self, text):
        q = text.strip()
        m = SUPERLATIVE.match(q)
        if m:
            return self.superlative(m[1].lower(), m[2], m[3] or '')
        m = YEAR.match(q)
        if m:
            return self.year(m[1] or m[3], (m[2] or m[4]).lower())
        m = COUNT.match(q)
        if m and m[2]:
            return self.count(m[1], m[2])
        return None

    def superlative(self, adjective, thing, scope):
        thing_words = words(thing)
        scope_words = [stem(w) for w in words(scope)]
        if not thing_words:
            return None
        noun = stem(thing_words[-1])
        noun_re = r'(?:' + re.escape(noun) + r'(?:s|es)?)'
        synonyms = r'(?:' + '|'.join(re.escape(s) for s in SYNONYMS[adjective]) + r')'
        # Between the superlative and the noun only the question's own words or neutral ones ("the fastest land animal",
        # "the largest known star"), so "the largest prehistoric animals" does not answer "the largest animal".
        between = '|'.join(re.escape(w) for w in set(thing_words[:-1]) | {'known', 'living', 'extant', 'natural', 'single'})
        # The noun must be the head noun: "the largest ocean," but not "the largest ocean current".
        head_end = r'(?=\s*(?:[,.;:()]|$)|\s+(?:in|of|on|by|and|that|which|to|from|with|for|after|ever|known|anywhere|outside|at|as)\b)'
        modified = synonyms + r'(?:\s+(?:' + between + r'))*\s+' + noun_re + head_end
        # The sentence's own subject must be described by the superlative right after "is":
        #   "Mount Elbrus is the highest mountain in Russia and Europe."   "It is the largest country in the world"
        #   "Jupiter is the fifth planet from the Sun and the largest in the Solar System."
        copula = r'(?:\s*\([^)]*\))?(?:,[^,.]{0,80},)?\s+(?:is|was|remains|ranks as)\s+(?:also\s+)?(?:the\s+|earth\'s\s+|the\s+world\'s\s+)'
        forms = [copula + r'(?:[\w-]+\s+){0,2}?' + modified,
                 copula + r'(?:[\w-]+\s+){0,2}?' + noun_re + r'\b[^.]{0,60}?\band\s+the\s+' + synonyms + r'\b']
        # A superlative limited to a place the question did not ask about: "the highest mountain in Ecuador".
        narrower = re.compile(noun_re + r'\s+(?:in|of|on|within|entirely within)\s+(?:the\s+)?([A-Z][\w-]+(?:\s+(?:and\s+)?[A-Z][\w-]+)*)')
        candidates = []
        # Exact-phrase searches find the articles that say it ("the largest country"); plain keyword search mostly
        # returns "List of ..." pages.
        phrases = [f'"{s} {thing}" {scope}'.strip() for s in SYNONYMS[adjective][:2]] + [f'{adjective} {thing} {scope}'.strip()]
        for title, intro, url, length in self.intros(*phrases):
            head = re.escape(re.sub(r'\s*\(.*', '', title).lower())
            for sentence in sentences(intro)[:4]:
                low = sentence.lower()
                hit = None
                for form in forms:
                    hit = re.match(r'(?:the\s+)?(?:' + head + r'|it)' + form, low)
                    if hit:
                        break
                if not hit:
                    continue
                # "fourth-largest", "second-longest", "39th-highest" are not the superlative asked for.
                word = list(re.finditer(synonyms, low[:hit.end()]))[-1]
                if re.search(r'(?:\d|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|\dth|\dnd|\drd|\dst)[- ]$', low[:word.start()]):
                    continue
                place = narrower.search(sentence[word.start():word.start() + 120])
                if place:
                    named = {stem(w) for w in words(place[1])}
                    if not (named & set(scope_words) or named & {'world', 'earth', 'solar', 'universe', 'planet'}):
                        continue                 # "the highest mountain in Ecuador" does not answer "on Earth"
                low_stems = {stem(w) for w in re.findall(r'[a-z0-9]+', low)} | {stem(w) for w in words(title)}
                if not all(w in low_stems for w in scope_words):
                    continue
                candidates.append((length, title, sentence, url))
                break
        if not candidates:
            return None
        length, title, sentence, url = max(candidates)          # the best-known article wins (cheetah over a record-holding mite)
        return self.reply(f'**{title}**. {sentence}', title, url)

    def count(self, thing, scope):
        thing_words = [stem(w) for w in words(thing)]
        scope_words = [stem(w) for w in words(scope)]
        if not thing_words:
            return None
        noun = re.escape(words(thing)[-1])
        noun_pattern = noun + r'|' + re.escape(stem(words(thing)[-1]))
        for title, intro, url, length in self.intros(f'how many {thing} {scope}'.strip(), f'number of {thing} {scope}'.strip()):
            for sentence in sentences(intro)[:6]:
                low = sentence.lower()
                low_stems = {stem(w) for w in re.findall(r'[a-z0-9]+', low)} | {stem(w) for w in words(title)}
                if scope_words and not any(w in low_stems for w in scope_words):
                    continue
                found = list(re.finditer(r'\b(\d[\d,]*|' + '|'.join(NUMBER_WORDS) + r')\s+(?:[a-z-]+\s+){0,2}(?:' + noun_pattern + r')\b', low))
                if found:
                    # "around 270 bones at birth ... around 206 bones by adulthood": the settled (last) figure, with the sentence.
                    return self.reply(f'**{found[-1][1]}**. {sentence}', title, url)
        return None

    def year(self, event, verb):
        wanted_end = verb in ('end', 'finish', 'close', 'fall', 'die')
        for title, intro, url, length in self.intros(event):
            if not set(stem(w) for w in words(event)) & set(stem(w) for w in words(title) + words(intro[:200])):
                continue
            first = sentences(intro)[:1]
            span = re.search(r'\(([^()]*?\b(1\d{3}|20\d\d))\s*[–—-]\s*([^()]*?\b(1\d{3}|20\d\d))\)', intro[:400])
            if span and verb in ('end', 'finish', 'begin', 'start', 'close', 'open'):
                year = span[4] if wanted_end else span[2]
                when = (span[3] if wanted_end else span[1]).strip()
                return self.reply(f'**{year}** ({when}). {first[0] if first else ""}'.strip(), title, url)
            past = PAST.get(verb, verb + 'ed')
            for sentence in sentences(intro)[:6]:
                m = re.search(r'\b' + re.escape(past) + r'\b[^.]*?\b(1\d{3}|20\d\d)\b', sentence, re.I)
                if m:
                    return self.reply(f'**{m[1]}**. {sentence}', title, url)
        return None

    @staticmethod
    def reply(text, title, url):
        text = f'{text}\n\n**Source:** [{title} (Wikipedia)]({url.replace(" ", "%20").replace(")", "%29")})'
        return dict(response=text, route='chat/web-answer', sources=[dict(source=f'Wikipedia: {title}', url=url, licence='CC BY-SA 4.0',
                    licence_url='https://creativecommons.org/licenses/by-sa/4.0/', attribution='Wikipedia contributors')],
                    details='Found in the opening paragraph of the linked Wikipedia article; the sentence had to contain the '
                            'question\'s superlative, count or event words. Wikipedia text is CC BY-SA 4.0. No neural model.')


def reply(text, net=None):
    if len(text) > 200 or not (SUPERLATIVE.match(text.strip()) or COUNT.match(text.strip()) or YEAR.match(text.strip())):
        return None
    from .network import LookupUnavailable, NETWORK
    try:
        return Finder(net or NETWORK).answer(text)
    except (LookupUnavailable, KeyError, TypeError, ValueError, IndexError):
        return None
