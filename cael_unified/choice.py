"""Whole-system multiple choice: language model + local evidence retrieval + exact word-problem arithmetic.

No neural networks, no network access. For each question:

1. the count language model scores every option (character-normalised log-likelihood);
2. for short-answer questions, each option's evidence strength is the BM25 score of the
   best passages in CAEL's local Wikipedia store containing both question words and
   that option's own words (the classic information-retrieval solver);
3. if the exact word-problem solver computes a quantity that exactly one option states,
   that option is chosen.

The language and evidence scores are standardised within the question and combined
with a weight chosen on development data (see research/leaderboard_040).
"""
import math
import re
import sqlite3
from pathlib import Path

from .bundle import ROOT
from . import wordmath

KNOWLEDGE = ROOT / 'models/cael-knowledge-v1/knowledge.sqlite'
# ARC Corpus (AI2 science sentences): its own terms forbid redistribution and restrict commercial use, so CAEL never
# uses it at runtime. Only a local research reproduction can opt in with CAEL_RESEARCH_ARC=1 (never shipped or served).
ARC_CORPUS = ROOT / 'data/arc_corpus/arc_corpus.sqlite'
STOP = set('''a an the of to in on for and or is are was were be been being do does did what which who whom whose why how when where
this that these those it its as at by from with without into onto than then so such can could would should will may might must
most least more less best likely following statement statements describes explain explains true false not no yes all some any each
other another one two three four many much very also only just about above below after before during while because if
student students teacher scientist scientists people person they them their there here we our you your he she his her
question answer answers would which used using use uses help helps example'''.split())


def words(text):
    return [w for w in re.findall(r'[a-z0-9]+', text.lower()) if w not in STOP and len(w) > 1]


def standardise(values):
    mean = sum(values) / len(values)
    spread = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
    return [(v - mean) / spread if spread > 1e-9 else 0.0 for v in values]


class Evidence:
    """BM25 evidence from a local FTS5 index: Wikipedia passages, or ARC Corpus sentences."""

    def __init__(self, path=None, table='passages'):
        self.path = Path(path or KNOWLEDGE)
        self.table = table
        self.db = sqlite3.connect(f'file:{self.path}?mode=ro', uri=True, check_same_thread=False)
        self.cache = {}

    def strength(self, question, ending, top=3):
        q = list(dict.fromkeys(words(question)))[:24]
        a = [w for w in dict.fromkeys(words(ending)) if w not in q][:12]
        if not q or not a:
            return 0.0
        query = '(' + ' OR '.join(f'"{w}"' for w in q) + ') AND (' + ' OR '.join(f'"{w}"' for w in a) + ')'
        if query not in self.cache:
            try:
                rows = self.db.execute(f'SELECT bm25({self.table}) FROM {self.table} WHERE {self.table} MATCH ? '
                                       f'ORDER BY bm25({self.table}) LIMIT ?', (query, top)).fetchall()
            except sqlite3.OperationalError:
                rows = []
            # bm25() is lower-is-better; negate so stronger evidence is larger.
            self.cache[query] = sum(-r[0] for r in rows) / top if rows else 0.0
        return self.cache[query]

    def scores(self, context, endings):
        question = context
        if question.startswith('Question: '):
            question = question[len('Question: '):]
        question = question.replace('\nAnswer:', ' ')
        return [self.strength(question, e) for e in endings]


def short_answers(endings, limit=10):
    """Evidence retrieval suits short factual options; long procedural options (PIQA, HellaSwag) are left to the language model."""
    return max(len(e.split()) for e in endings) <= limit


def arc_evidence():
    """The ARC Corpus evidence index: off unless a local research run sets CAEL_RESEARCH_ARC=1 (see ARC_CORPUS)."""
    import os
    if os.environ.get('CAEL_RESEARCH_ARC') != '1':
        return None
    return Evidence(ARC_CORPUS, table='sentences') if ARC_CORPUS.exists() else None


def choose(context, endings, lm_values, evidence=None, weight=0.0, short_limit=10, extra=()):
    """lm_values: score_endings output; extra: further (Evidence, weight) sources. Returns (index, details)."""
    chars = [max(1, v['chars'] - 1) for v in lm_values]
    lm = [v['sum_lnp'] / c for v, c in zip(lm_values, chars)]
    solved = wordmath.match(context, endings)
    if solved is not None:
        return solved, dict(route='exact-arithmetic')
    combined = standardise(lm)
    route = 'language'
    if short_answers(endings, short_limit):
        for source, source_weight in ([(evidence, weight)] if evidence is not None else []) + list(extra):
            if source is None or not source_weight:
                continue
            ev = standardise(source.scores(context, endings))
            combined = [c + source_weight * e for c, e in zip(combined, ev)]
            route = 'language+evidence'
    best = max(range(len(endings)), key=combined.__getitem__)
    return best, dict(route=route)
