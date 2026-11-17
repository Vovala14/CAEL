"""CAEL's Researcher index v2: fielded retrieval and learning-to-rank over the local index of 285,000 stored questions.
No neural network and no transformer: counting statistics, BM25F and gradient-boosted decision trees.

The pipeline, as modern search engines do it, in three stages:

1. Query model. The whole conversation, not two key words: every content word the user said, weighted by where it was
   said (the last question counts double, the first told sentence one and a half) and by how rare it is in the index;
   then grown with the other spellings of the same word (draughty/drafty, tap/faucet) and with the title words the index
   itself has learned go with it (assoc table: a writer who says "trickle" in a body titles the question "low pressure").
   The Planner's need/want/ask words are weighted up.

2. Candidate generation. A wide, cheap pull from the fielded FTS5 index (fielded.sqlite: title, tags, body, answer kept
   apart): an any-word query over the weighted terms ranked by FTS5's BM25, a title-only pull, and all-words pairs of the
   heaviest terms. Several hundred threads.

3. Re-ranking. For each candidate: BM25F (per-field length normalisation, field weights), per-field BM25, weighted term
   coverage of the title, body and answer, term proximity in title and body, the user's own word pairs in the title,
   title words the user never said, the site classifier's fit, votes and answer quality. A LambdaMART model (gradient
   boosted regression trees trained with LightGBM's lambdarank objective on the index itself, see
   research/index_v2_20261116/train_ltr.py) orders them; the trees are stored as JSON (ltr_model.json) and evaluated
   here with numpy, so CAEL needs no machine-learning library at run time.

search(messages, plan) -> [Hit] best first.
"""
import json
import math
import re
import sqlite3
import threading
from functools import lru_cache
from pathlib import Path

import numpy as np

from . import web_check as wc

HERE = Path(__file__).resolve().parent
MODEL_DIR = HERE.parent / 'models' / 'cael-open-chat-v1'
FIELDED = MODEL_DIR / 'fielded.sqlite'
LTR = HERE / 'ltr_model.json'
FIELDS = ('title', 'tags', 'body', 'answer')
F_WEIGHT = np.array([3.0, 1.5, 1.0, 0.35])           # BM25F field weights
F_B = np.array([0.5, 0.3, 0.75, 0.75])               # per-field length normalisation
K1 = 1.2
TOKEN = re.compile(r"[a-z][a-z0-9']*")
CODE = re.compile(r'```.*?```|`[^`]*`|https?://\S+', re.S)
_local = threading.local()
_stem = lru_cache(maxsize=200000)(wc.stem)
QSTOP = set(wc.GENERIC) | {'really', 'very', 'quite', 'just', 'bit', 'lot', 'still', 'again', 'always', 'never', 'keeps', 'keep', 'thing', 'things',
                            'anything', 'something', 'everything', 'actually', 'even', 'whole', 'every', 'time', 'times', 'minute', 'minutes',
                            'week', 'weeks', 'day', 'days', 'year', 'years', 'month', 'months', 'hour', 'hours', 'last', 'first', 'new', 'old', 'lately',
                            'help', 'helps', 'stop', 'make', 'get', 'got', 'want', 'wants', 'need', 'needs', 'try', 'tried', 'way', 'ways', 'easiest',
                            'best', 'better', 'cheap', 'cheaply', 'properly', 'wrong', 'fix', 'what', 'can', 'could', 'should', 'would', 'doing',
                            'myself', 'yourself', 'ourselves', 'normal', 'awful', 'absolutely', 'completely', 'totally', 'sure', 'kind', 'sort',
                            'say', 'said', 'tell', 'told', 'think', 'thought', 'know', 'mean', 'like', 'around', 'used', 'use', 'using'}


def db():
    con = getattr(_local, 'con', None)
    if con is None:
        if not FIELDED.exists():
            return None
        con = sqlite3.connect(f'file:{FIELDED}?mode=ro', uri=True, check_same_thread=False)
        _local.con = con
    return con


@lru_cache(maxsize=1)
def meta():
    con = db()
    m = dict(con.execute('SELECT k, v FROM meta').fetchall()) if con is not None else {}
    return dict(n=float(m.get('docs', 284914)), avg=np.array([float(m.get(f'avg_{f}', 1)) for f in FIELDS]))


@lru_cache(maxsize=100000)
def sdf(s):
    con = db()                  # without the optional index every word is treated as rare (no statistics to say otherwise)
    row = con.execute('SELECT title, tags, body, answer FROM sdf WHERE stem = ?', (s,)).fetchone() if con is not None else None
    return np.array(row if row else (0, 0, 0, 0), dtype=float)


def idf(s):
    """BM25 idf of a stem over the whole question (the field where it is most common stands for the document)."""
    n = meta()['n']
    d = float(max(sdf(s).max(), sdf(s)[0] + sdf(s)[2] * 0.6))
    return math.log(1 + (n - d + 0.5) / (d + 0.5))


@lru_cache(maxsize=50000)
def associates(word, kind='bt', limit=6):
    try:
        return tuple(db().execute('SELECT other, score FROM assoc WHERE word = ? AND kind = ? ORDER BY score DESC LIMIT ?', (word, kind, limit)).fetchall())
    except (sqlite3.OperationalError, AttributeError):
        return ()


def toks(text):
    return [_stem(w.replace("'", '')) for w in TOKEN.findall((text or '').lower())]


# ---------------------------------------------------------------- 1. query model

# British words and the American ones most stored questions use (the index is mostly written in American English)
DIALECT = {'lead': ['leash'], 'windscreen': ['windshield'], 'flatmate': ['roommate', 'housemate'], 'flatmates': ['roommates'],
           'housemate': ['roommate'], 'nursery': ['daycare', 'preschool'], 'sweets': ['candy', 'candies'], 'sweet': ['candy'],
           'biscuits': ['cookies'], 'biscuit': ['cookie'], 'mobile': ['cell', 'phone'], 'lift': ['elevator'], 'pavement': ['sidewalk'],
           'bonnet': ['hood'], 'motorway': ['highway', 'freeway'], 'queue': ['line'], 'hoover': ['vacuum'], 'wardrobe': ['closet'],
           'cot': ['crib'], 'pram': ['stroller'], 'pushchair': ['stroller'], 'buggy': ['stroller'], 'dummy': ['pacifier'],
           'trousers': ['pants'], 'chips': ['fries'], 'crisps': ['chips'], 'coriander': ['cilantro'], 'mince': ['ground'],
           'clingfilm': ['wrap'], 'worktop': ['countertop', 'counter'], 'worktops': ['countertops'], 'loo': ['toilet'],
           'maths': ['math'], 'fortnight': ['weeks'], 'postman': ['mailman', 'mail'], 'post': ['mail'], 'parcel': ['package'],
           'tumble': ['dryer'], 'washing': ['laundry', 'wash'], 'solicitor': ['lawyer', 'attorney'],
           'gp': ['doctor', 'physician'], 'chemist': ['pharmacy'], 'sellotape': ['tape'], 'jab': ['shot', 'vaccine'],
           'holidays': ['vacation'], 'jumpers': ['sweaters'], 'courgettes': ['zucchini'], 'aubergines': ['eggplants'], 'nappies': ['diapers'],
           'tyres': ['tires'], 'kerb': ['curb'], 'flat': ['apartment'], 'garden': ['yard'], 'bin': ['trash', 'garbage'], 'bins': ['trash', 'garbage'],
           'rubbish': ['trash', 'garbage'], 'telly': ['tv', 'television'], 'mum': ['mom', 'mother'], 'nan': ['grandma', 'grandmother'],
           'gran': ['grandma', 'grandmother'], 'hob': ['stove', 'cooktop'], 'cooker': ['stove', 'oven'], 'tap': ['faucet'], 'taps': ['faucets'],
           'mould': ['mold'], 'mouldy': ['moldy'], 'colleague': ['coworker'], 'colleagues': ['coworkers'], 'trainers': ['sneakers'],
           'torch': ['flashlight'], 'petrol': ['gas'], 'lorry': ['truck'], 'motorbike': ['motorcycle'], 'handbag': ['purse'],
           'cupboard': ['cabinet', 'closet'], 'cupboards': ['cabinets'], 'draughty': ['drafty', 'draft'], 'draught': ['draft'], 'tyre': ['tire'],
           'grey': ['gray'], 'colour': ['color'], 'zip': ['zipper'], 'aluminium': ['aluminum'], 'nappy': ['diaper'], 'jumper': ['sweater'],
           'courgette': ['zucchini'], 'aubergine': ['eggplant']}
PHRASES = {'washing up': ['dishes'], 'washing-up': ['dishes'], 'bonfire night': ['fireworks'], 'kitchen roll': ['towel'],
           'tin foil': ['foil'], 'washing machine': ['washer'], 'tumble dryer': ['dryer'], 'car park': ['parking'], 'number plate': ['license'],
           'estate agent': ['realtor'], 'fizzy drink': ['soda'], 'ice lolly': ['popsicle'], 'packed lunch': ['lunch'], 'dressing gown': ['robe'],
           'bin bag': ['trash']}


def other_forms(w):
    return list(dict.fromkeys(list(wc.spellings(w)[1:]) + DIALECT.get(w, [])))


@lru_cache(maxsize=20000)
def title_phrase_count(phrase):
    try:
        return db().execute('SELECT count(*) FROM (SELECT rowid FROM f WHERE f MATCH ? LIMIT 6)', (f'title : "{phrase}"',)).fetchone()[0]
    except (sqlite3.OperationalError, AttributeError):
        return 0


PARTICLES = {'out', 'off', 'over', 'down', 'away', 'back', 'inside', 'outside', 'around', 'about', 'along', 'through', 'together', 'ago',
             'most', 'other', 'others', 'lot', 'lots', 'some', 'every', 'each', 'again', 'already', 'since', 'until'}


def thing_and_problem(turns):
    """The thing the user's trouble is with and the words of the trouble itself: "Our dog pulls really hard on the lead"
    -> thing [dog], problem [pulls, hard, lead]. The thing is the first noun phrase named with a determiner (the Planner's
    thing_of); a two-word thing is kept only when stored titles use it as a phrase ("kitchen knives", "smoke alarm", not
    "dog pulls"). The problem words are the rest of the first sentence and the last question's own content words."""
    if not turns:
        return [], []
    try:
        from .team import thing_of
        thing = thing_of(turns[0]) or ''
    except Exception:
        thing = ''
    parts = thing.split()
    if len(parts) == 2 and title_phrase_count(thing) < 3:
        # a rare pair: either a thing and its verb ("dog pulls", "shoes smell") or a compound whose head is last
        # ("garden gate"): a plural first word or a second word with a verb ending means the verb; else the head noun
        a, b = parts
        try:
            from .open_chat import is_noun
            noun_b = is_noun(b)
        except Exception:
            noun_b = False
        if (a.endswith('s') and not a.endswith('ss')) or re.search(r'(?:s|ed|ing)$', b) or not noun_b or b in ('left', 'went', 'got', 'broke'):
            parts = [a]
        else:
            parts = [b]
    first_sentence = re.split(r'(?<=[.!?])[ ]+', turns[0])[0]
    if parts:
        # the trouble is told after the thing ("Our washing machine | won't spin"); the words before it name the thing
        m = re.search(r'(?i)\b' + re.escape(parts[-1]) + r'\b', first_sentence)
        if m:
            first_sentence = first_sentence[m.end():]
    said = [first_sentence] + ([turns[-1]] if len(turns) > 1 else [])
    thing_stems = [_stem(w) for w in parts]
    problem = []
    for t in said:
        for w in wc.words(t):
            if w in QSTOP or w in wc.STOP or len(w) < 3 or w.isdigit() or _stem(w) in thing_stems or w in PARTICLES or idf(_stem(w)) < 1.5:
                continue
            problem.append(w)
    return parts, list(dict.fromkeys(problem))


class Query:
    def __init__(self, turns, plan=None):
        self.turns = [t for t in turns if t][-4:]
        self.plan = plan or {}
        self.w = {}              # stem -> weight
        self.orig = {}           # stems the user actually said -> weight
        self.words = {}          # stem -> a surface word for the FTS query
        self.seq = []            # per turn: the user's content stems in order (for pairs and proximity)
        for i, t in enumerate(self.turns):
            k = 2.0 if i == len(self.turns) - 1 else 1.5 if i == 0 else 1.0
            seq = []
            for w in wc.words(t):
                if w in QSTOP or w in wc.STOP or len(w) < 3 or w.isdigit():
                    continue
                s = _stem(w)
                seq.append(s)
                v = k * idf(s)
                if v > self.orig.get(s, 0):
                    self.orig[s] = v
                    self.words[s] = w
            self.seq.append(seq)
        planned = {}
        for key, boost in (('need', 1.5), ('ask', 1.3), ('want', 1.3)):
            for w in self.plan.get(key) or []:
                for f in wc.spellings(w):
                    planned[_stem(f)] = max(planned.get(_stem(f), 1.0), boost)
        self.planned = planned
        for s, v in list(self.orig.items()):
            self.orig[s] = v * planned.get(s, 1.0)
        self.w = dict(self.orig)
        self.exp = {}
        low = ' '.join(self.turns).lower()
        top_v = max(self.orig.values(), default=1.0)
        for ph, forms in PHRASES.items():
            if ph in low:
                for f in forms:
                    fs = _stem(f)
                    if fs not in self.orig:
                        self.exp[fs] = max(self.exp.get(fs, 0), 0.55 * top_v)
                        self.words.setdefault(fs, f)
        for s, v in list(self.orig.items()):
            w = self.words[s]
            for f in other_forms(w):
                fs = _stem(f)
                if fs not in self.orig:
                    self.exp[fs] = max(self.exp.get(fs, 0), 0.8 * v * min(1.0, idf(fs) / max(idf(s), 1e-6)))
                    self.words.setdefault(fs, f)
            for other, score in associates(w):
                os_ = _stem(other)
                if os_ not in self.orig and score >= 0.2:
                    self.exp[os_] = max(self.exp.get(os_, 0), 0.35 * score * v)
                    self.words.setdefault(os_, other)
        for s, v in self.exp.items():
            self.w[s] = max(self.w.get(s, 0), v)
        self.pairs = set()
        for seq in self.seq:
            self.pairs |= {(a, b) for a, b in zip(seq, seq[1:]) if a != b}
        self.top = sorted(self.orig, key=lambda s: -self.orig[s])
        # the thing and its trouble, each with its other forms (thing: spellings and dialect; trouble: also the title words
        # the index learned go with it, "fogs" -> "condensation")
        thing, problem = thing_and_problem(self.turns)
        self.thing = [{_stem(w)} | {_stem(f) for f in other_forms(w)} for w in thing[-1:]]
        for w in thing[-1:]:
            for f in other_forms(w):
                self.words.setdefault(_stem(f), f)
            self.words.setdefault(_stem(w), w)
        self.problem = {}
        for w in problem:
            s = _stem(w)
            v = self.orig.get(s, idf(s))
            forms = {s: 1.0}
            for f in other_forms(w):
                forms.setdefault(_stem(f), 0.9)
                self.words.setdefault(_stem(f), f)
            for other, score in associates(w, 'bt', 4):
                if score >= 0.25:
                    forms.setdefault(_stem(other), 0.5)
                    self.words.setdefault(_stem(other), other)
            self.problem[s] = (v, forms)

    def fts_terms(self, n_orig=12, n_exp=6):
        out = [self.words[s] for s in self.top[:n_orig]]
        out += [self.words[s] for s in sorted(self.exp, key=lambda s: -self.exp[s])[:n_exp]]
        return [w for w in dict.fromkeys(out) if re.fullmatch(r'[a-z]+', w)]


# ---------------------------------------------------------------- 2. candidates

def candidates(q, limit=300, extra_queries=()):
    con = db()
    if con is None:
        return []
    terms = q.fts_terms()
    if not terms:
        return []
    got = {}

    def pull(expr, n, tag):
        try:
            for (rid,) in con.execute('SELECT rowid FROM f WHERE f MATCH ? ORDER BY bm25(f, 4.0, 2.0, 1.5, 0.4) LIMIT ?', (expr, n)):
                got.setdefault(rid, set()).add(tag)
        except sqlite3.OperationalError:
            pass

    pull(' OR '.join(f'"{w}"' for w in terms), limit, 'any')
    pull('title : (' + ' OR '.join(f'"{w}"' for w in terms) + ')', 150, 'title')
    heavy = [q.words[s] for s in q.top[:5] if re.fullmatch(r'[a-z]+', q.words[s])]
    for i, a in enumerate(heavy):
        for b in heavy[i + 1:]:
            pull(f'"{a}" AND "{b}"', 30, 'pair')
    if q.thing:
        heads = [w for w in dict.fromkeys(q.words.get(x, x) for x in q.thing[0]) if re.fullmatch(r'[a-z]+', w)][:3]
        for s_, (v, forms) in sorted(q.problem.items(), key=lambda kv: -kv[1][0])[:4]:
            alts = [w for w in dict.fromkeys(q.words.get(f, f) for f, k in forms.items() if k >= 0.5) if re.fullmatch(r'[a-z]+', w)][:4]
            if alts and heads:
                pull('title : ((' + ' OR '.join(f'{w}*' for w in heads) + ') AND (' + ' OR '.join(f'"{w}"' for w in alts) + '))', 25, 'thing')
    for v in extra_queries:
        v = [w for w in v if re.fullmatch(r'[a-z]+', w)]
        if v:
            pull(' AND '.join(f'"{w}"' for w in v), 12, 'plan')
    return list(got.items())


# ---------------------------------------------------------------- 3. features

NAMES = ['bm25f', 'bm25_title', 'bm25_tags', 'bm25_body', 'bm25_answer', 'title_cov', 'title_cov_top3', 'title_prec', 'body_cov', 'answer_cov',
         'all_cov', 'exp_title', 'prox_title', 'prox_body', 'pairs_title', 'pairs_body', 'unsaid_title', 'unsaid_title_n', 'last_turn_title',
         'first_turn_title', 'need_title', 'want_title', 'ask_title', 'need_all', 'site_prob', 'site_top', 'votes', 'quality', 'is_se', 'title_len',
         'howto', 'question_mark', 'animal_mismatch', 'n_pulls', 'in_title_pull', 'answer_len', 'top1_title', 'top1_any', 'thing_title', 'problem_title', 'thing_and_problem', 'thing_only', 'thing_missing', 'hand']
HOWTO = re.compile(r"(?i)^\s*(?:how (?:do|can|should|to|would|does|did)|what(?:'s| is| are) the (?:best|easiest|right)|best way|tips|ways? to|what can|"
                   r"why (?:does|do|is|are|did|won'?t|doesn'?t)|is (?:it|there)|should i|what (?:causes|could|should|to do))")


def _min_gap(pos_a, pos_b):
    if not pos_a or not pos_b:
        return None
    best = 10 ** 6
    for i in pos_a:
        for j in pos_b:
            d = abs(i - j)
            if d and d < best:
                best = d
    return best if best < 10 ** 6 else None


def features(q, doc, pulls=(), probs=None, said_turns=None):
    """doc: dict(title, tags, body, answer, site, votes, q, source)."""
    fields = [toks(doc['title']), toks(doc.get('tags', '')), toks(doc.get('body', '')), toks(doc.get('answer', ''))]
    lens = np.array([len(f) for f in fields], dtype=float)
    avg = meta()['avg']
    norm = 1 - F_B + F_B * lens / np.maximum(avg, 1e-6)
    tf = {}
    pos = [{}, {}, {}, {}]
    for k, f in enumerate(fields):
        for i, s in enumerate(f):
            if s in q.w:
                tf.setdefault(s, np.zeros(4))[k] += 1
                pos[k].setdefault(s, []).append(i)
    bm25f = 0.0
    per = np.zeros(4)
    for s, v in tf.items():
        qw = q.w[s]
        i = idf(s)
        t = float((F_WEIGHT * v / norm).sum())
        bm25f += qw * i * t / (K1 + t)
        per += qw * i * (v / norm) / (K1 + v / norm)
    tot_orig = sum(q.orig[s] for s in q.top[:6]) or 1.0
    top3 = sum(q.orig[s] for s in q.top[:3]) or 1.0
    title_set, body_set, ans_set = set(fields[0]), set(fields[2]) | set(fields[1]), set(fields[3])
    title_cov = sum(q.orig[s] for s in q.top[:6] if s in title_set) / tot_orig
    title_cov3 = sum(q.orig[s] for s in q.top[:3] if s in title_set) / top3
    body_cov = sum(q.orig[s] for s in q.top[:6] if s in body_set) / tot_orig
    ans_cov = sum(q.orig[s] for s in q.top[:6] if s in ans_set) / tot_orig
    all_cov = sum(q.orig[s] for s in q.top[:6] if s in title_set | body_set | ans_set) / tot_orig
    exp_title = sum(q.exp[s] for s in q.exp if s in title_set and s not in q.orig) / tot_orig
    content_title = [s for s in fields[0] if s not in wc.STOP and s not in QSTOP and len(s) > 2]
    tw = {s: idf(s) for s in content_title}
    title_prec = sum(v for s, v in tw.items() if s in q.w) / (sum(tw.values()) or 1.0)
    unsaid = [s for s, v in tw.items() if s not in q.w and v > 6.0]
    unsaid_w = sum(tw[s] for s in unsaid)

    def prox(k):
        best = 0.0
        top = [s for s in q.top[:6] if s in pos[k]]
        for i, a in enumerate(top):
            for b in top[i + 1:]:
                g = _min_gap(pos[k][a], pos[k][b])
                if g:
                    best = max(best, (q.orig[a] + q.orig[b]) / tot_orig / g)
        return best

    def pair_hits(k):
        n = 0
        for a, b in q.pairs:
            g = _min_gap(pos[k].get(a, []), pos[k].get(b, []))
            if g and g <= 2:
                n += 1
        return n

    last = set(q.seq[-1]) if q.seq else set()
    first = set(q.seq[0]) if q.seq else set()
    lw = sum(q.orig.get(s, 0) for s in last) or 1.0
    fw = sum(q.orig.get(s, 0) for s in first) or 1.0
    last_title = sum(q.orig.get(s, 0) for s in last if s in title_set) / lw
    first_title = sum(q.orig.get(s, 0) for s in first if s in title_set) / fw
    plan = q.plan

    def plan_hit(key, where):
        ws = plan.get(key) or []
        if not ws:
            return -1.0
        return float(any(any(_stem(f) in where for f in wc.spellings(w)) for w in ws))

    need = plan.get('need') or []
    need_all = -1.0 if not need else float(all(any(_stem(f) in (title_set | body_set) for f in wc.spellings(w)) for w in need))
    site = doc.get('site') or ''
    probs = probs or {}
    sp = probs.get(site, 0.0) if site else (0.3 if max(probs.values(), default=0) < 0.6 else 0.05)
    site_top = float(bool(site) and probs and site == max(probs, key=probs.get))
    said = said_turns if said_turns is not None else ' '.join(q.turns)
    animal = float(bool(wc.ANIMAL.search(doc['title'] + ' ' + doc.get('body', '')[:300])) and not wc.ANIMAL.search(said))
    top1 = q.top[0] if q.top else None
    out = [bm25f, *per.tolist(), title_cov, title_cov3, title_prec, body_cov, ans_cov, all_cov, exp_title, prox(0), prox(2), pair_hits(0),
            pair_hits(2), unsaid_w, len(unsaid), last_title, first_title, plan_hit('need', title_set), plan_hit('want', title_set),
            plan_hit('ask', title_set), need_all, sp, site_top, math.log1p(max(0, doc.get('votes') or 0)), float(doc.get('q') or 0),
            float(doc.get('source') == 'se'), float(len(content_title)), float(bool(HOWTO.match(doc['title']))), float('?' in doc['title']),
            animal, float(len(pulls)), float('title' in pulls), math.log1p(lens[3]), float(top1 in title_set), float(top1 in (title_set | body_set)), *thing_problem(q, title_set, fields[0], body_set), 0.0]
    out[-1] = float(fallback_score([out])[0])
    return out


def thing_problem(q, title_set, title_toks, body_set=frozenset()):
    """Is the stored question about the user's thing, and does its title name the trouble? Title stems are matched whole
    or as a prefix ("sunflower" in "sunflowers", "leash" in "leashes")."""
    def has(st):
        return st in title_set or (len(st) >= 4 and any(t.startswith(st) for t in title_toks))
    thing = -1.0 if not q.thing else float(any(has(x) for x in q.thing[0]))
    tot = sum(v for v, _ in q.problem.values()) or 1.0
    prob = sum(v * max((k for f, k in forms.items() if has(f)), default=0.0) for v, forms in q.problem.values()) / tot
    missing = float(bool(q.thing) and thing == 0 and not any(x in body_set for x in q.thing[0]))
    return [thing, prob, float(thing > 0 and prob > 0), float(thing > 0 and prob == 0), missing]


def split_extra(extra, source):
    extra = extra or ''
    if source != 'se':
        return '', extra
    m = re.match(r'^ ?(.*?)  (.*)$', extra, re.S)
    if m and len(m[1].split()) <= 8:
        return m[1].strip(), m[2]
    return '', extra


def load_docs(ids):
    from . import open_chat as oc
    con = oc.db()
    out = {}
    ids = list(ids)
    for k in range(0, len(ids), 400):
        part = ids[k:k + 400]
        for did, title, extra, answer, source, site, q, votes in con.execute(
                f'SELECT id, title, extra, answer, source, site, q, votes FROM doc WHERE id IN ({",".join("?" * len(part))})', part):
            tags, body = split_extra(extra, source)
            out[did] = dict(id=did, title=title or '', tags=tags.replace('-', ' '), body=CODE.sub(' ', body)[:3000], answer=CODE.sub(' ', answer or '')[:4000],
                            raw_answer=answer or '', extra=extra or '', source=source, site=site or '', q=q, votes=votes or 0)
    return out


# ---------------------------------------------------------------- ranker (trees as JSON, numpy evaluation)

@lru_cache(maxsize=1)
def model():
    if not LTR.exists():
        return None
    m = json.loads(LTR.read_text(encoding='utf-8'))
    trees = []
    for t in m['trees']:
        trees.append(tuple(np.array(t[k]) for k in ('feature', 'threshold', 'left', 'right', 'value', 'default_left')))
    return dict(trees=trees, names=m['names'], meta=m)


def tree_scores(X):
    """Sum of the boosted trees' outputs for each row of X (nodes as flat arrays; a negative child index is a leaf)."""
    m = model()
    if m is None:
        return None
    X = np.asarray(X, dtype=float)
    out = np.zeros(len(X))
    rows = np.arange(len(X))
    for feat, thr, left, right, value, dleft in m['trees']:
        node = np.zeros(len(X), dtype=int)
        active = np.ones(len(X), dtype=bool)
        while active.any():
            idx = rows[active]
            nd = node[idx]
            x = X[idx, feat[nd]]
            go_left = np.where(np.isnan(x), dleft[nd].astype(bool), x <= thr[nd])
            nxt = np.where(go_left, left[nd], right[nd])
            node[idx] = nxt
            leaf = nxt < 0
            active[idx[leaf]] = False
        out += value[-node - 1]
    return out


def fallback_score(F):
    """Without trained trees: a hand-weighted mix of the strongest features (BM25F, title coverage, proximity)."""
    F = np.asarray(F, dtype=float)
    ix = {n: i for i, n in enumerate(NAMES)}
    return (F[:, ix['bm25f']] / 10 + 2.0 * F[:, ix['title_cov']] + 1.0 * F[:, ix['title_prec']] + 0.8 * F[:, ix['prox_title']]
            + 0.4 * F[:, ix['pairs_title']] + 0.5 * F[:, ix['site_prob']] + 0.05 * F[:, ix['votes']] - 0.08 * F[:, ix['unsaid_title_n']]
            + V21 * (1.0 * F[:, ix['thing_and_problem']] + 1.0 * F[:, ix['problem_title']] - 0.6 * F[:, ix['thing_only']] - 1.0 * F[:, ix['thing_missing']]))


V21 = float(__import__('os').environ.get('CAEL_V21', '1'))
LTR_ALPHA = float(__import__('os').environ.get('CAEL_LTR_ALPHA', '0'))


def blend(F):
    """The hand-weighted BM25F mix, plus the LambdaMART trees' opinion at weight LTR_ALPHA (both standardised over this
    conversation's candidates). The trees learned from stored questions turned into conversations; the hand mix holds up
    better on real conversations, so the trees adjust it rather than replace it."""
    h = fallback_score(F)
    t = tree_scores(F) if LTR_ALPHA else None
    if t is None:
        return h
    z = lambda v: (v - v.mean()) / (v.std() + 1e-9)
    return z(h) + LTR_ALPHA * z(t)


class Hit:
    __slots__ = ('id', 'doc', 'score', 'f')

    def __init__(self, did, doc, score, f):
        self.id, self.doc, self.score, self.f = did, doc, score, f

    def __repr__(self):
        return f'Hit({self.score:.3f}, {self.doc["title"][:60]!r})'


def search(messages, plan=None, k=30, extra_queries=(), probs=None, limit=300):
    turns = wc.user_turns(messages) if messages and isinstance(messages[0], dict) else list(messages)
    if not turns or db() is None:
        return []
    q = Query(turns, plan)
    if not q.orig:
        return []
    cands = candidates(q, limit=limit, extra_queries=extra_queries)
    if not cands:
        return []
    docs = load_docs([c for c, _ in cands])
    if probs is None:
        try:
            probs = wc.scene_sites([dict(role='user', content=t) for t in turns])
        except Exception:
            probs = {}
    said = ' '.join(turns)
    F, keep = [], []
    for did, pulls in cands:
        d = docs.get(did)
        if not d:
            continue
        F.append(features(q, d, pulls, probs, said))
        keep.append(d)
    if not F:
        return []
    s = blend(F)
    order = np.argsort(-s)
    hits, seen = [], set()
    for i in order:
        t = keep[i]['title'].strip().lower()
        if t in seen:
            continue
        seen.add(t)
        hits.append(Hit(keep[i]['id'], keep[i], float(s[i]), F[i]))
        if len(hits) >= k:
            break
    return hits
