"""Learned rewrites (0.4.4 fix after release, 2026-11-22). Non-neural.

The rules in learned_rewrites.json were not written by hand. tools/autofix.py learns them:
- it paraphrases word problems CAEL already answers correctly (WordNet synonyms, number words, dropped filler words,
  contractions, other names);
- it finds the paraphrases where the answer changes;
- it learns a phrase rule (the paraphrase's wording -> the wording CAEL reads) from a word-level diff, with numbers
  generalised;
- it keeps a rule only if it fixes at least one paraphrase and breaks none of the problems it was checked on.

At answer time the rules make one more reading for the thinking swarm (think.readings). They never replace what the
user said: the vote decides.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).with_name('learned_rewrites.json')


@lru_cache(maxsize=1)
def rules():
    try:
        data = json.loads(PATH.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return ()
    out = []
    for r in data.get('rules', []):
        try:
            out.append((re.compile(r['pattern'], re.I), r['replace'], r.get('id', '')))
        except re.error:
            continue
    return tuple(out)


ACTIVE = None          # tools/autofix.py sets a candidate rule list here while it checks rules


def rewrite(text, active=None):
    """The text with every rule that matches applied once, and the ids of the rules used."""
    used = []
    active = active if active is not None else ACTIVE
    for pat, rep, rid in (active if active is not None else rules()):
        new = pat.sub(lambda m: m.expand(rep), text)
        if new != text:
            text = new
            used.append(rid)
    return text, used


def reload():
    rules.cache_clear()
