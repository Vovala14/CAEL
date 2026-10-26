"""Predefined, wording-independent grading for the context benchmark.

A reply passes when:
  * every group in criteria["any"] has at least one term present (case-insensitive, word-bounded);
  * no criteria["none"] term is present, unless the sentence holding it marks it as past/replaced (OLD_OK cues);
  * clarify items: the reply signals the conflict (CLARIFY cues) - naming the options is enough when it asks a question;
  * no_clarify items: the reply does not claim a conflict.
  * abstain items (the conversation never said it): the reply admits it does not know (ABSTAIN cues) and names none of
    the criteria["none"] distractor values.
"""
import re

OLD_OK = ('before', 'previous', 'used to', 'earlier', 'original', 'moved from', 'at first', 'formerly', 'no longer', 'not anymore',
          'changed from', 'instead of', 'was ', 'initially', 'not ', 'skipp', 'dropp', 'removed', 'old ', 'replac', 'from ', 'done', 'finished',
          'completed', 'corrected', 'superseded')
CLARIFY = ('which', 'clarify', 'conflict', 'contradict', 'two different', 'disagree', 'confirm', 'inconsistent', 'differ',
           'not sure', 'both said', 'mixed', 'unclear', 'can you check')


def has(text, term):
    return re.search(r'(?<![a-z0-9])' + re.escape(term.lower()) + r'(?![a-z0-9])', text) is not None


def sentences(text):
    return [s for s in re.split(r'(?<=[.!?;\n])\s+|\n', text) if s.strip()]


ABSTAIN = ("don't know", 'do not know', "haven't told", 'have not told', "didn't tell", 'did not tell', "didn't mention",
           'did not mention', 'not mentioned', 'never mentioned', 'no information', "don't have", 'do not have', "can't tell",
           'cannot tell', 'can not tell', 'not sure', 'unknown', "wasn't mentioned", 'was not mentioned', 'not say', "didn't say",
           'no record', 'nothing about', 'not been told', "haven't said", 'have not said', 'no way to know', "couldn't find",
           'could not find', 'not stated', 'unclear')


def grade(reply, criteria):
    text = (reply or '').lower().replace('’', "'")
    if criteria.get('abstain'):
        # unsupported question: the conversation never said it, so the reply must say so and must not guess a listed value
        return any(c in text for c in ABSTAIN) and not any(has(text, t) for t in criteria.get('none', []))
    ok_any = all(any(has(text, t) for t in group) for group in criteria.get('any', []))
    stale = False
    for term in criteria.get('none', []):
        for s in sentences(text):
            if has(s, term) and not any(cue in s for cue in OLD_OK):
                stale = True
    flags = any(c in text for c in CLARIFY)
    if criteria.get('clarify'):
        named = sum(any(has(text, t) for t in g) for g in criteria.get('any', []))
        return (flags or (named >= 2 and '?' in text)) and named >= 1
    if criteria.get('no_clarify') and any(c in text for c in ('conflict', 'contradict', 'inconsistent', 'two different')):
        return False
    return ok_any and not stale
