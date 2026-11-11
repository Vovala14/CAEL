"""Open conversation by retrieval: answer everyday questions with the best human-written answer to the same question.

Index: models/cael-open-chat-v1/open.sqlite (about 285,000 human-written answers: 265k Stack Exchange questions
from 19 everyday sites, OpenAssistant and Dolly; see its SOURCES.md). No neural network and nothing generated:
1. Understand: the content words of the turn, weighted by rarity (IDF over the index). A short follow-up
   ("Is it too late?", "How often should I go?") borrows the topic words of the earlier turns.
2. Recall: SQLite FTS5 BM25 over question titles (and tags / question text with a lower weight).
3. Judge: a stored question is used only if it covers most of the rare words of the turn, contains its main topic
   word, and is itself mostly about what was asked; vote counts and source quality break ties.
4. Write: the answer cleaned of forum talk (edits, "the OP", links, sign-offs) and trimmed to chat length.
"""
from functools import lru_cache
import math
import re
import sqlite3

from .bundle import ROOT

PATH = ROOT / 'models' / 'cael-open-chat-v1' / 'open.sqlite'
STOP = set('''a an the and or but if of to in on at for with from by about as is are was were be been being am do does did done doing have
has had having i me my mine myself you your yours yourself we us our they them their he him his she her it its this that these those there
here what which who whom whose when where why how can could would should will shall may might must just really very so too also some any
all each every no nor only own same than then such into over under again further once more most other up down out off both few s t don
now please tell give know want need like get got make let lets thing things something anything way ways good best one ok okay hi hello hey
thanks thank yes yeah im ive id youre dont doesnt isnt cant wont didnt actually definitely probably maybe still even lot lots bit kind sort
much many anyone someone somebody anybody everyone people person guys advice tips tip suggestions ideas help idea think say said going
today now currently recently already always never ever often else whats hows'''.split())
FOLLOW = re.compile(r"(?i)^\s*(?:and |so |but |ok(?:ay)?,? |ha,? )?(?:what if|what about|how about|and if|is it|is that|does it|do they|"
                    r"why do they|why does it|how often|how long|how much|how many|should i|can i|do i|what (?:should|can) i|"
                    r"which|where|when|is there|are there|any other|what else|then|so do|so does|so is)\b")
PRONOUN = re.compile(r"(?i)\b(?:it|this|that|they|them|these|those|one|there|so)\b")
FORUM = re.compile(r"(?i)\b(?:edit(?:ed)?:|update:|upvot|downvot|this question|your question|the question|the op\b|\bop\b|op's|asker|"
                   r"answer(?:ed|s)? (?:above|below)|other answers?|this answer|my answer|comments?\b|stack ?exchange|this site|"
                   r"hope (?:this|that) helps|good luck!?$|cheers|welcome to|as (?:others|someone) (?:have|has) (?:said|mentioned|pointed)|"
                   r"https?://|www\.|\[\d+\]|see also|tl;dr|disclaimer|i'm not a doctor|ianal|i am not a lawyer|downvote)")


@lru_cache(maxsize=1)
def db():
    if not PATH.exists():
        return None
    return sqlite3.connect(f'file:{PATH}?mode=ro', uri=True, check_same_thread=False)


@lru_cache(maxsize=1)
def _stemmer():
    mem = sqlite3.connect(':memory:', check_same_thread=False)
    mem.executescript("CREATE VIRTUAL TABLE s USING fts5(w, tokenize='porter unicode61'); CREATE VIRTUAL TABLE v USING fts5vocab(s, 'instance');")
    return mem


@lru_cache(maxsize=50000)
def stem(word):
    mem = _stemmer()
    mem.execute('DELETE FROM s')
    mem.execute('INSERT INTO s(rowid, w) VALUES (1, ?)', (word,))
    row = mem.execute('SELECT term FROM v LIMIT 1').fetchone()
    return row[0] if row else word


@lru_cache(maxsize=1)
def total_docs():
    return db().execute('SELECT count(*) FROM doc').fetchone()[0]


@lru_cache(maxsize=50000)
def idf(term):
    row = db().execute('SELECT doc FROM vocab WHERE term = ?', (term,)).fetchone()
    n = row[0] if row else 0
    return math.log((total_docs() + 1) / (n + 1)) if n else 0.0


def words(text):
    return [w for w in re.findall(r"[a-z][a-z0-9']*", text.lower().replace("’", "'")) if len(w) > 1]


def content(text):
    out = []
    for w in words(text):
        w = w.replace("'", '')
        if w not in STOP and len(w) > 1 and not w.isdigit():
            out.append(w)
    return out


def weights(text, factor=1.0):
    out = {}
    for w in content(text):
        s = stem(w)
        v = idf(s)
        if v > 0.5:
            out[s] = max(out.get(s, 0), v * factor)
    return out


def user_turns(messages):
    return [m['content'] for m in messages if m.get('role') == 'user']


def query_terms(messages):
    """Weighted query stems for the last turn, plus the conversation's topic for short follow-ups."""
    turns = user_turns(messages)
    last = turns[-1]
    q = weights(last)
    follow = len(turns) > 1 and (FOLLOW.search(last) or len(q) <= 2 or (PRONOUN.search(last) and len(q) <= 3))
    topic = {}
    if follow:
        for i, t in enumerate(reversed(turns[:-1])):
            for s, v in weights(t, 0.75 if i == 0 else 0.5).items():
                topic[s] = max(topic.get(s, 0), v)
        for s in q:
            topic.pop(s, None)
    return q, topic


def _clean(answer, limit=900):
    text = answer.replace('\r', '')
    text = re.sub(r'(?m)^>.*$', '', text)
    text = re.sub(r'\s+[–—-]\s+[A-Z][\w.]*(?: [A-Z][\w.]*)?\s*(?=\n|$)', '', text)       # "– Bruce Alderson" signatures
    text = re.sub(r'\[\.\.\.\]|\[…\]', '', text)
    # Hard-wrapped lines inside a paragraph are joined; list items keep their own lines.
    text = re.sub(r'(?<=[^\n])\n(?!\s*(?:[-*•]|\d+[.)])\s)(?=[a-z(\w])', ' ', text)
    paras = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    # A one- or two-word "heading" paragraph ("Grind", "Bean Age") is dropped; its content follows.
    paras = [p for p in paras if len(p.split()) > 2 or re.match(r'\s*(?:[-*•]|\d+[.)])\s', p)]
    kept = []
    for p in paras:
        lines = []
        for line in p.split('\n'):
            sents = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"(])', line.strip())
            sents = [s for s in sents if s and not FORUM.search(s)]
            if sents:
                lines.append(' '.join(sents))
        if lines:
            kept.append('\n'.join(lines))
    if not kept:
        return ''
    out = ''
    for p in kept:
        if out and len(out) + len(p) > limit:
            lines = p.split('\n')
            if len(lines) > 1:
                add = []
                for line in lines:
                    if len(out) + sum(len(a) + 1 for a in add) + len(line) > limit:
                        break
                    add.append(line)
                if len(add) >= 2:
                    out += '\n\n' + '\n'.join(add)
            break
        out += ('\n\n' if out else '') + p
    if len(out) > limit * 1.3:
        sents = re.split(r'(?<=[.!?])\s+', out)
        out = ''
        for s in sents:
            if out and len(out) + len(s) > limit:
                break
            out += (' ' if out else '') + s
    out = re.sub(r'\s*:\s*$', '.', out.strip())
    return out.strip()


ASK_KIND = [('joke', r'\bjokes?\b|\bfunny\b'), ('story', r'\b(?:story|poem|sentences about)\b'),
            ('diff', r'\bdifference between\b|\bvs\.?\b|\bversus\b'), ('why', r'^\s*(?:why|how come)\b')]


BAD_START = re.compile(r"(?i)^\s*(?:from (?:a|the|this|my)\b|as (?:written|mentioned|said|others)|the relevant|looking at your|it sounds like you|"
                       r"in your case|based on your|you(?:'ve| have) (?:asked|mentioned)|you mention|to answer your|i (?:had|have) (?:the same|a similar)|"
                       r"well,? (?:that|it) depends|there are (?:a few|several) (?:issues|questions)|first of all,? (?:your|the)|yes\.?$|no\.?$)")


def answer_quality(answer):
    """0..1: how well an answer reads on its own as a chat reply."""
    a = answer.strip()
    q = 1.0
    if BAD_START.search(a):
        q -= 0.5
    n = len(a)
    if n < 150:
        q -= 0.4
    elif n > 2500:
        q -= 0.2
    q -= 0.15 * min(3, len(FORUM.findall(a)))
    if re.search(r"(?i)\byour (?:photo|picture|code|recipe|post|situation|example|link|setup)\b", a):
        q -= 0.2
    return max(0.0, q)


def _same(answer, said):
    a = re.sub(r"\W+", " ", answer.lower())[:120]
    return a[:80] and a[:80] in re.sub(r"\W+", " ", said.lower())


@lru_cache(maxsize=1)
def wordnet():
    path = ROOT / 'models' / 'cael-dictionary-wn30' / 'dictionary.sqlite'
    return sqlite3.connect(f'file:{path}?mode=ro', uri=True, check_same_thread=False) if path.exists() else None


@lru_cache(maxsize=50000)
def is_noun(word):
    """True when the word is mainly a noun in WordNet (most-tagged sense), or unknown to WordNet."""
    wn = wordnet()
    if wn is None:
        return True
    bases = [word]
    for cut, add in (('ies', 'y'), ('es', ''), ('s', ''), ('ied', 'y'), ('ed', ''), ('ed', 'e'), ('ing', ''), ('ing', 'e'), ('er', ''), ('est', '')):
        if word.endswith(cut) and len(word) - len(cut) >= 3:
            bases.append(word[:-len(cut)] + add)
    if len(word) > 4 and word[-3] == word[-4] and word.endswith(('ed', 'er')):
        bases.append(word[:-3])
    for b in bases:
        rows = wn.execute('SELECT pos, max(tagged), count(*) FROM lemma WHERE word = ? GROUP BY pos', (b,)).fetchall()
        if rows:
            score = {('adj' if pos in ('adjective', 'satellite', 'adj', 's', 'a') else pos): (t or 0) + 0.1 * n for pos, t, n in rows}
            return score.get('noun', -1) >= max(score.values())
    return True


PERSONAL = re.compile(r"(?i)\b(?:my|our|his|her)\s+(?:\w+'s\s+)?(?:wife|husband|son|daughter|kids?|child(?:ren)?|baby|toddler|girlfriend|boyfriend|"
                      r"partner|mom|mum|dad|mother|father|parents?|brother|sister|friend|boss|landlord|neighbou?r)\b|\b\d+[- ](?:year|month|week|day)s?[- ]old\b")


def qtype(text):
    t = text.lower().strip()
    if re.search(r"^\s*(?:(?:and|so|but|then),? )?(?:why|how come)\b|\bwhat (?:causes|makes)\b|\bwhy (?:do|does|is|are|did)\b", t):
        return 'why'
    if re.search(r"\bhow (?:do|can|should|would|could|to|does|did|often|long|much|many)\b|\bwhat(?:'s| is) the best way\b|\bways? to\b|\btips?\b|\badvice\b", t):
        return 'how'
    if re.search(r"^\s*what\b|\bwhich\b", t):
        return 'what'
    return 'other'


@lru_cache(maxsize=1)
def site_sizes():
    return dict(db().execute('SELECT site, n FROM sitesize').fetchall())


def site_probs(weighted):
    """Naive Bayes over title words: which site (or general chat) a question most likely belongs to. Flat prior."""
    sizes = site_sizes()
    logp = {site: 0.0 for site in sizes}
    for term, w in weighted.items():
        counts = dict(db().execute('SELECT site, n FROM siteterm WHERE term = ?', (term,)).fetchall())
        if not counts:
            continue
        f = min(1.0, w / 6.0)
        for site, size in sizes.items():
            logp[site] += f * math.log((counts.get(site, 0) + 0.2) / (size + 1.0) * 1000)
    top = max(logp.values())
    z = sum(math.exp(v - top) for v in logp.values())
    return {site: math.exp(v - top) / z for site, v in logp.items()}


def candidates(q, topic, limit=200):
    terms = list(q) + [t for t in topic if t not in q]
    if not terms:
        return []
    match = ' OR '.join(f'"{t}"' for t in terms)
    try:
        return db().execute('SELECT d.id, d.title, d.extra, d.answer, d.source, d.site, d.context, d.q, d.votes, bm25(idx, 6.0, 1.0) '
                            'FROM idx JOIN doc d ON d.id = idx.rowid WHERE idx MATCH ? ORDER BY bm25(idx, 6.0, 1.0) LIMIT ?',
                            (match, limit)).fetchall()
    except sqlite3.OperationalError:
        return []


def best(messages, min_score=None):
    if not db():
        return None
    q, topic = query_terms(messages)
    if not q and not topic:
        return None
    allw = dict(topic)
    allw.update(q)
    total = sum(allw.values())
    turns = user_turns(messages)
    last_nouns = {stem(w) for w in content(turns[-1]) if is_noun(w) and idf(stem(w)) > 1.5}
    need = min(2, len(last_nouns))
    ranked = sorted(q or topic, key=lambda t: -(q or topic)[t])
    tops = set(ranked[:2])
    topic_nouns = sorted({stem(w) for t in turns[:-1][-2:] for w in content(t) if is_noun(w) and stem(w) in topic},
                         key=lambda t: -topic.get(t, 0))
    topic_anchor = topic_nouns[0] if topic_nouns else (max(topic, key=topic.get) if topic else None)
    used = [m['content'] for m in messages if m.get('role') == 'assistant']
    last = user_turns(messages)[-1].lower()
    wanted = [k for k, p in ASK_KIND if re.search(p, last)]
    wanted_type = qtype(turns[-1]) if not topic else qtype(turns[-1]) if qtype(turns[-1]) != 'other' else 'other'
    probs = site_probs(allw)
    top, top_score = None, 0.0
    for row in candidates(q, topic):
        title = {stem(w.replace("'", '')) for w in content(row[1])}
        extra = {stem(w.replace("'", '')) for w in content(row[2])} - title
        if (len(title & last_nouns) < need if last_nouns else not (title & tops)) or (topic_anchor and topic_anchor not in title and topic_anchor not in extra):
            continue
        if any(_same(row[3], u) for u in used):
            continue
        cov = (sum(v for s, v in allw.items() if s in title) + 0.5 * sum(v for s, v in allw.items() if s in extra)) / total
        tw = {s: idf(s) for s in title}
        prec = sum(v for s, v in tw.items() if s in allw) / (sum(tw.values()) or 1)
        if cov < 0.55 or prec < 0.35:
            continue
        tk = qtype(row[1])
        if (wanted_type == 'why' and tk != 'why') or (wanted_type in ('how', 'what') and tk == 'why') \
                or (wanted_type == 'why' and re.search(r'(?i)\buses? for\b|\bhow to\b', row[1])):
            continue
        kind_ok = all(re.search(p, row[1].lower()) for k, p in ASK_KIND if k in wanted and k in ('joke', 'diff'))
        if not kind_ok:
            continue
        score = 0.6 * cov + 0.4 * prec + 0.06 * (row[7] or 0.5) + 0.02 * math.log1p(max(0, row[8] or 0)) + 0.12 * answer_quality(row[3])
        ps = probs.get(row[5] if row[4] == 'se' else 'general', 0)
        if ps < 0.01:
            continue            # "get my toddler to eat vegetables" is a parenting question, not a gardening one
        score += 0.25 * ps
        if row[4] == 'oasst':
            score += 0.03
        if PERSONAL.search(row[1]) and not PERSONAL.search(' '.join(turns)):
            score -= 0.15       # "my wife's e-bike", "my 6 month old cat": an answer written for someone else's situation
        if re.search(r'\d', row[1]) and not re.search(r'\d', ' '.join(turns)):
            score -= 0.05
        if score > top_score:
            top, top_score = row, score
    if top is None or top_score < (min_score or 0.62):
        return None
    text = _clean(top[3])
    if len(text) < 60:
        return None
    return dict(score=top_score, title=top[1], source=top[4], site=top[5], text=text)


SOURCE_NAMES = {'se': 'Stack Exchange ({site}.stackexchange.com, CC BY-SA 4.0)', 'oasst': 'OpenAssistant (Apache 2.0)',
                'dolly': 'databricks-dolly-15k (CC BY-SA 3.0)'}


ASKING = re.compile(r"(?i)\?|^\s*(?:tell me|give me|show me|explain|describe|suggest|recommend|list|teach me|help me|any (?:tips|ideas|advice|suggestions))\b|"
                    r"\b(?:any (?:tips|ideas|advice|suggestions|recommendations)|what should i|how (?:do|can|should) i|i (?:need|want) (?:some )?(?:advice|tips|ideas|help))\b")


def reply(messages):
    turns = user_turns(messages)
    if not turns:
        return None
    if not ASKING.search(turns[-1]) and not (len(turns) > 1 and ASKING.search(turns[-2]) and len(turns[-1].split()) <= 14
                                             and not re.search(r"(?i)\b(?:thanks?|thank you|cool|great|ok(?:ay)?|got it|i see)\b", turns[-1])):
        return None              # a statement ("I had a long day") is conversation, not a search query              # a statement ("I had a long day") is conversation, not a search query
    hit = best(messages)
    if not hit:
        return None
    src = SOURCE_NAMES[hit['source']].format(site=hit['site'])
    return dict(route='chat/open-retrieval', response=hit['text'], sources=[],
                details=f'A human-written answer from {src} to the question "{hit["title"][:160]}" (match {hit["score"]:.2f}). '
                        'Retrieved, not generated; no neural model.')
