"""Second-pass ranking of answer passages read from web pages (statistics over the fetched pages; no model).

web_check.score() decides whether a passage may be quoted at all. This module decides which of the allowed passages
answers best, from four signals that do not depend on how the question was worded:

  rarity     BM25 over every sentence fetched for this question: a passage that holds the question's rare words
             beats one that repeats its common words;
  agreement  how many other publishers say something similar (content-word overlap): what several pages state is
             the answer, what one page says in passing is usually an aside or a teaser;
  shape      an answer states something: a definition for "what is", a reason for "why", an instruction for "how do I",
             a figure for "how many"; introductions, promises ("here's how", "read on") and menus do not;
  closeness  the question's words standing near each other inside the passage.
"""
import math
import re

WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*|\d+(?:[.,]\d+)?")
STOP = set('''the a an and or but of to in on at for with by from as is are was were be been being it its this that these those
i you he she we they them his her their our your my me not no do does did can could will would should may might must have has
had if then so than too very just also about into over after before up down out off there here what which who whom when where
why how all any some more most other such only own same each few both s t d ll re ve m your yours'''.split())
TEASER = re.compile(r"(?i)\b(?:here(?:'s| is| are)|in this (?:article|guide|post|video|section)|read on|keep reading|find out|let'?s (?:take|look|dive|explore|"
                    r"break|get|talk)|we(?:'ll| will) (?:show|cover|explain|look|walk|share|discuss|explore)|you(?:'ll| will) (?:learn|find|discover|see)|"
                    r"below (?:are|is|we)|the following|ever wondered|look no further|without further ado|scroll down|check out|sign up|subscribe|"
                    r"newsletter|click here|learn more|our (?:guide|experts?|team|top picks?)|this (?:article|guide|post) (?:will|covers|explains)|"
                    r"everything you need to know|got you covered|we(?:'ve| have) (?:rounded|put together|compiled|gathered)|stay tuned|"
                    r"table of contents|jump to|related:|photo:|image:|credit:|updated on|published on|min read|share this)\b")
IMPERATIVE = re.compile(r"(?i)^(?:first,? |then,? |next,? |finally,? |to \w+[^,]{0,40}, )?(?:use|add|mix|keep|put|place|make|try|start|begin|apply|remove|wash|rinse|"
                        r"clean|wipe|soak|store|avoid|let|leave|set|turn|cut|fill|pour|check|choose|pick|take|give|water|plant|feed|cover|wrap|"
                        r"spray|scrub|dry|heat|cook|bake|boil|stir|bring|hold|press|open|close|replace|practice|practise|write|read|ask|"
                        r"focus|limit|drink|eat|get|go|run|walk|stretch|warm|cool|freeze|thaw|measure|combine|sprinkle|rub|brush|dab|blot)\b")
ADVICE = re.compile(r"(?i)\b(?:should|you can|it helps to|make sure|be sure to|the best way|a good way|one way|is to|by \w+ing|recommend\w*|"
                    r"experts? (?:say|suggest|recommend)|aim (?:for|to)|ideally|works? (?:well|best)|helps?|effective)\b")
REASON = re.compile(r"(?i)\b(?:because|due to|caused by|causes?|as a result|so that|since|owing to|leads? to|results? in|which means|"
                    r"the reason|is why|in order to|thanks to|triggers?|allows?|enables?)\b")
DEFINE = re.compile(r"(?i)^(?:an? |the )?[\w' -]{2,50}? (?:is|are|was|were|refers to|means|describes) (?:an?|the|one of|when|how|any|used)\b")
FIGURE = re.compile(r"\d")
OPENER = re.compile(r"(?i)^(?:and|but|so|or|however|also|additionally|moreover|furthermore|meanwhile|instead|otherwise|then|plus|that said|"
                    r"this|that|these|those|it|they|he|she|such|here|there)\b")


def stem(w):
    w = w.lower().strip("'’-")
    for suf, rep in (('ies', 'y'), ('ing', ''), ('ed', ''), ('es', ''), ('s', '')):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            w = w[:-len(suf)] + rep
            break
    return w[:-1] if len(w) > 4 and w.endswith('e') else w


def tokens(text):
    return [stem(w) for w in WORD.findall(text) if w.lower() not in STOP and len(w) > 1]


def split(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"(])', re.sub(r'\s+', ' ', text)) if 20 <= len(s.strip()) <= 500]


def kind_of(question):
    q = question.lower().strip()
    if re.search(r'\bwhy\b|\bhow come\b|\bwhat causes?\b|\breason\b', q):
        return 'why'
    if re.search(r'\bhow (?:many|much|long|far|old|tall|big|often|fast|hot|cold|heavy|deep|high)\b|\bwhat (?:year|percent\w*|temperature|age)\b|\bwhen\b', q):
        return 'figure'
    if re.search(r"\bhow (?:do|does|can|should|would|could|to|did)\b|\b(?:best|good|easy|quick) way\b|\btips?\b|\bwhat should i\b|\bwhat can i\b|"
                 r"\bany (?:ideas|advice|suggestions|tricks)\b|\bhow\b", q):
        return 'how'
    if re.search(r"\bwhat(?:'s| is| are| was| were)\b|\bwhat does .* mean\b|\bdefine\b|\bwho (?:is|was|are)\b", q):
        return 'what'
    if re.match(r"(?:is|are|was|were|do|does|did|can|could|should|will|would|has|have)\b", q):
        return 'yesno'
    return 'what'


def shape(passage, kind):
    """-1 .. +1: does the passage have the form of an answer to this kind of question?"""
    first = split(passage)[0] if split(passage) else passage
    s = 0.0
    if TEASER.search(passage):
        s -= 0.6
    if passage.rstrip().endswith((':', '…', '...')) or re.search(r'(?:\.\.\.|…)\s*$', passage):
        s -= 0.4            # a lead-in to a list or a cut-off snippet, not the answer itself
    if OPENER.match(first):
        s -= 0.2            # opens by pointing back at text that is not quoted
    n = len(WORD.findall(passage))
    if n < 9:
        s -= 0.3
    content = tokens(passage)
    if n and len(content) / n < 0.35:
        s -= 0.15           # mostly function words: says little
    if re.search(r'(?i)\b(?:i|my|me|we|our)\b', passage) and not re.search(r'(?i)\b(?:study|research|scientists|experts)\b', passage):
        s -= 0.1            # a personal story more often than a general answer
    if kind == 'why':
        s += 0.4 if REASON.search(passage) else -0.2
    elif kind == 'how':
        s += 0.4 if IMPERATIVE.match(first) else 0.25 if ADVICE.search(passage) else -0.1
        if re.search(r'(?:1[5-9]|20)[0-9][0-9]', passage) or re.search(r'(?i) (?:invented|founded|originated|was first|history|nicknamed?) ', passage):
            s -= 0.35           # the history of the thing is not how to do it
    elif kind == 'what':
        s += 0.35 if DEFINE.match(first) else 0.0
    elif kind == 'figure':
        s += 0.3 if FIGURE.search(passage) else -0.3
    elif kind == 'yesno':
        s += 0.2 if re.search(r"(?i)\b(?:yes|no|not|never|always|generally|usually|can|cannot|is safe|is not|are not|does not|do not|it is possible|unlikely|likely)\b", passage) else 0.0
    return max(-1.0, min(1.0, s))


def closeness(passage, asked):
    """1 when the question's words sit together in the passage, towards 0 when they are scattered."""
    toks = [stem(w) for w in WORD.findall(passage)]
    pos = [i for i, t in enumerate(toks) if t in asked]
    found = {toks[i] for i in pos}
    if len(found) < 2:
        return 0.0
    best = len(toks)
    for a in range(len(pos)):               # smallest window that holds every found word once
        seen = set()
        for b in range(a, len(pos)):
            seen.add(toks[pos[b]])
            if len(seen) == len(found):
                best = min(best, pos[b] - pos[a] + 1); break
    return min(1.0, len(found) / best * 1.5)


def rerank(candidates, question, pages, publisher=lambda url: url):
    """candidates: (score, coverage, passage, source name, title, url). Returns them re-scored, best first.

    pages: (name, host, title, body, url) of everything fetched for the question: the corpus for word rarity and
    for agreement between publishers.
    """
    if not candidates:
        return candidates
    kind = kind_of(question)
    asked = set(tokens(question))
    corpus = []                              # (publisher, token set) per sentence
    page_cover = {}                          # url -> share of the question's words the whole page holds
    page_pairs = {}                          # url -> how many of the question's word pairs stand together on the page
    q_toks = tokens(question)
    pairs = {(a, b) for a, b in zip(q_toks, q_toks[1:]) if a != b}
    for name, host, title, body, url in pages:
        pub = publisher(url) or host
        seq = tokens(title + ' . ' + body)
        on_page = set(seq)
        page_cover[url] = len(asked & on_page) / (len(asked) or 1)
        near = set()
        for i, t in enumerate(seq):
            for u in seq[i + 1:i + 3]:
                near.add((t, u)); near.add((u, t))
        page_pairs[url] = sum(1 for p in pairs if p in near)
        for s in split(body)[:400]:
            corpus.append((pub, set(tokens(s))))
    n = len(corpus) or 1
    df = {}
    for _, ts in corpus:
        for t in ts:
            df[t] = df.get(t, 0) + 1
    avg = sum(len(ts) for _, ts in corpus) / n or 1.0

    def idf(t):
        return math.log(1 + (n - df.get(t, 0) + 0.5) / (df.get(t, 0) + 0.5))
    top = sum(idf(t) for t in asked) or 1.0
    out = []
    for c in candidates:
        base, cov, passage, name, title, url = c[:6]
        toks = tokens(passage)
        tf = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        k1, b = 1.2, 0.75
        bm = sum(idf(t) * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(toks) / avg)) for t in asked if t in tf)
        rarity = min(1.0, bm / (top * 1.3))
        mine, pub = set(toks), publisher(url) or name
        # agreement: other publishers with a sentence sharing a good part of this passage's informative words
        info = {t for t in mine if t not in asked} or mine
        backers = set()
        for other, ts in corpus:
            if other != pub and other not in backers and len(info & ts) >= max(2, 0.34 * min(len(info), 12)) and len(mine & ts) / (len(ts) or 1) >= 0.3:
                backers.add(other)
        agreement = min(1.0, len(backers) / 2)
        cover = page_cover.get(url, 1.0)
        delta = 0.22 * rarity + 0.25 * agreement + 0.30 * shape(passage, kind) + 0.10 * closeness(passage, asked) + 0.25 * (cover - 0.7)
        out.append((base + delta, cov, passage, name, title, url, cover) + tuple(c[6:]))
    # a page that lacks a good part of the question's words is about something else ("Games Animation" for "party games
    # for adults"): its passages are dropped
    out = [c for c in out if c[6] >= 0.6 or len(asked) < 3]
    # "cast iron" side by side on the cookware page, apart on a TV series page: when some page holds the question's
    # phrases, pages that hold none of them are dropped, and the rest gain by how many they hold
    most = max((page_pairs.get(c[5], 0) for c in out), default=0)
    if most:
        out = [(c[0] + 0.3 * page_pairs.get(c[5], 0) / most,) + c[1:] for c in out if page_pairs.get(c[5], 0) > 0]
    out = [c[:6] + c[7:] for c in out]
    out.sort(key=lambda c: -c[0])
    return out


def explain(passage, question, pages=()):
    """The separate signals for one passage (for traces and tests)."""
    kind = kind_of(question)
    return dict(kind=kind, shape=shape(passage, kind), closeness=closeness(passage, set(tokens(question))))
