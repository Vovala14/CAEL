"""Which stored thread answers this conversation? A learned, non-neural ranker for the Researcher.

Each candidate thread is described by a dozen plain features of its title against what the user said: weighted recall
and precision of the user's words in the title, neighbouring word pairs found together, rare words shared, title words
the user never used, how likely the thread's site is for this conversation (the index's own site classifier), the
keyword search's rank, and the answer's votes. A logistic regression over these features gives the chance that the
thread is the one asked about.

It was trained on the index itself (research/ranker_20261116/train_ranker.py): the body of a stored question, which
reads like a person describing their situation, should pick its own title over the other titles the keyword search
returns for it. Weights live in ranker_weights.json next to this file. No neural network; nothing is generated.
"""
import json
import math
import re
from functools import lru_cache
from pathlib import Path

NAMES = ['bias', 'f1', 'recall', 'precision', 'pairs', 'rare', 'extra', 'site', 'site_top', 'rank', 'votes', 'title_len', 'all_rare',
         'answer_recall', 'answer_rare', 'body_recall', 'body_precision', 'noun_recall', 'noun_title_all', 'thing_title', 'thing_answer']
WEIGHTS = Path(__file__).with_name('ranker_weights.json')


def _wc():
    from . import web_check as wc
    return wc


def query_weights(turns):
    """{stem: weight} of what the user said; the last turn's words count double, the first one and a half."""
    wc = _wc()
    out = {}
    for i, t in enumerate(turns[-4:]):
        k = 2.0 if i == len(turns[-4:]) - 1 else 1.5 if i == 0 else 1.0
        for w in wc.content(t):
            if w in wc.GENERIC:
                continue
            for f in wc.spelled_stems(w):
                out[f] = max(out.get(f, 0.0), wc.weight(w) * k)
    return out


def pairs_of(turns):
    wc = _wc()
    out = []
    for t in turns[-4:]:
        for sent in re.split(r'(?<=[.!?])\s+', t):
            seq = [wc.stem(w) for w in wc.content(sent) if w not in wc.GENERIC]
            out += [(a, b) for a, b in zip(seq, seq[1:]) if a != b]
    return list(dict.fromkeys(out))[:16]


def features(turns, title, site, votes, rank, probs, q=None, pairs=None, answer='', body='', thing=None):
    """The feature vector of one candidate thread (see NAMES)."""
    wc = _wc()
    q = q if q is not None else query_weights(turns)
    pairs = pairs if pairs is not None else pairs_of(turns)
    title_words = [w for w in wc.content(title) if w not in wc.GENERIC]
    tw = {wc.stem(w): wc.weight(w) for w in title_words}
    seq = [wc.stem(w) for w in title_words]
    top = sorted(q.values(), reverse=True)[:6]
    hit = sum(v for f, v in q.items() if f in tw)
    recall = hit / (sum(top) or 1)
    precision = sum(v for f, v in tw.items() if f in q) / (sum(tw.values()) or 1)
    f1 = 0.0 if not recall or not precision else 2 * recall * precision / (recall + precision)
    npairs = 0
    for a, b in pairs:
        pa = [i for i, w in enumerate(seq) if w == a]
        pb = [i for i, w in enumerate(seq) if w == b]
        if any(abs(i - j) <= 2 for i in pa for j in pb):
            npairs += 1
    rare = sum(1 for f, v in q.items() if v >= 7.0 and f in tw)
    all_rare = sum(1 for f, v in q.items() if v >= 7.0)
    extra = sum(1 for f, v in tw.items() if f not in q and v > 5.5)
    p_site = probs.get(site, 0.0) if site else probs.get('general', 0.0)
    top_site = 1.0 if probs and site and max(probs, key=probs.get) == site else 0.0
    # the answer and the stored question's own description: do they talk about what the user talked about?
    ans = {wc.stem(w) for w in wc.content(answer[:3000])} if answer else set()
    bod = {wc.stem(w): wc.weight(w) for w in wc.content(body[:1500]) if w not in wc.GENERIC} if body else {}
    top_sum = sum(top) or 1
    ans_recall = sum(v for f, v in sorted(q.items(), key=lambda x: -x[1])[:8] if f in ans) / (sum(sorted(q.values(), reverse=True)[:8]) or 1)
    ans_rare = sum(1 for f, v in q.items() if v >= 7.0 and f in ans)
    body_recall = sum(v for f, v in q.items() if f in bod) / (sum(q.values()) or 1)
    body_precision = sum(v for f, v in bod.items() if f in q) / (sum(bod.values()) or 1)
    # every thing the user named counts, however common the word ("car" in "my dog hates the car")
    nouns = set()
    for t in turns[-3:]:
        for w in wc.content(t):
            if w not in wc.GENERIC and len(w) > 2 and _noun(w):
                nouns |= wc.spelled_stems(w)
    named_in_title = len(nouns & set(tw))
    noun_recall = named_in_title / (len({wc.stem(w) for t in turns[-3:] for w in wc.content(t) if w not in wc.GENERIC and len(w) > 2 and _noun(w)}) or 1)
    # the thing the user is talking about ("the kitchen drawer", "our washing machine"): in the title, and in the answer
    if thing is None:
        thing = thing_words(turns)
    forms = set()
    for w in thing:
        forms |= wc.spelled_stems(w)
    thing_title = 1.0 if forms and forms & set(tw) else 0.0
    thing_answer = 1.0 if forms and forms & ans else 0.0
    return [1.0, f1, recall, precision, min(npairs, 3) / 3, min(rare, 3) / 3, min(extra, 4) / 4, p_site, top_site,
            1.0 / (1 + rank), math.log1p(max(0, votes or 0)) / 6, min(len(seq), 15) / 15, min(all_rare, 4) / 4,
            ans_recall, min(ans_rare, 3) / 3, body_recall, body_precision, min(1.0, noun_recall), 1.0 if named_in_title >= 2 else 0.0,
            thing_title, thing_answer]


_THING = {}


def thing_words(turns):
    """The words of the thing the user's first told sentence is about (team.thing_of), cached per conversation."""
    key = turns[0] if turns else ''
    if key not in _THING:
        try:
            from .team import thing_of
            _THING[key] = (thing_of(key) or '').split()
        except Exception:
            _THING[key] = []
        if len(_THING) > 5000:
            _THING.pop(next(iter(_THING)))
    return _THING[key]


_NOUNS = {}


def _noun(w):
    if w not in _NOUNS:
        try:
            from . import open_chat as oc
            wn = oc.wordnet()
            bases = {w, w[:-1] if w.endswith('s') else w, w[:-2] if w.endswith('es') else w, w[:-3] + 'y' if w.endswith('ies') else w}
            _NOUNS[w] = wn is None or any(wn.execute('SELECT 1 FROM lemma WHERE word = ? AND pos = "noun" LIMIT 1', (b,)).fetchone() for b in bases)
        except Exception:
            _NOUNS[w] = True
    return _NOUNS[w]


@lru_cache(maxsize=1)
def weights():
    try:
        return json.loads(WEIGHTS.read_text())['w']
    except Exception:
        return None


CROSS = ['f1', 'precision', 'pairs', 'noun_recall', 'thing_title', 'answer_recall', 'answer_rare', 'body_recall', 'site_top', 'rank', 'votes', 'extra']


def expand(vec):
    """The features and their pairwise products (a logistic regression with interactions: still no neural network)."""
    idx = [NAMES.index(n) for n in CROSS]
    out = list(vec)
    for i, a in enumerate(idx):
        for b in idx[i:]:
            out.append(vec[a] * vec[b])
    return out


def score(vec):
    w = weights()
    if not w:
        return None
    if len(w) != len(vec):
        vec = expand(vec)
    z = sum(a * b for a, b in zip(w, vec))
    return 1 / (1 + math.exp(-max(-30, min(30, z))))
