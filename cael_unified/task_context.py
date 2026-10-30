"""Keep explicit questions/options/premises together before keyword routing.

This parses structural delimiters only. It never removes a semantic premise,
looks up task IDs, invents an answer, or treats a count-model score as a proof.
"""
import re

LABEL = r'(?:\(([A-Z])\)|\[([A-Z])\]|([A-Z])[.)])'
LINES = re.compile(r'(?m)^\s*'+LABEL+r'[ \t]+')
INLINE = re.compile(r'(?<!\w)'+LABEL+r'\s+')
QUESTION = re.compile(r'(?i)\b(?:what|which|who|where|when|how|whether|choose|select|question|answer|continuation|evaluate|calculate)\b|\?')
OTHER_PURPOSE = re.compile(r'(?i)^\s*(?:please\s+)?(?:quote|translate|proofread|review|write|create|make|draw|compose|generate|explain)\b')


def read(text):
    if not isinstance(text, str) or not 0 < len(text) <= 12000:
        return None
    from .orchestrator import protected_spans, unprotected
    spans = protected_spans(text)
    labels = [m for m in LINES.finditer(text) if unprotected(text, m, spans)]
    if len(labels) < 2:
        labels = [m for m in INLINE.finditer(text) if unprotected(text, m, spans)]
    if len(labels) >= 2:
        context = text[:labels[0].start()].strip()
        if not context or not QUESTION.search(context) or OTHER_PURPOSE.match(context):
            return None
        names = [next(g for g in m.groups() if g) for m in labels]
        if not 2 <= len(names) <= 8 or names != list('ABCDEFGH'[:len(names)]):
            return dict(kind='invalid', message='The option labels are missing, repeated or out of order. Use two to eight distinct options labelled A onward.')
        options = [text[m.end():labels[i+1].start() if i+1 < len(labels) else len(text)].strip() for i, m in enumerate(labels)]
        if any(not value or len(value) > 1500 for value in options):
            return dict(kind='invalid', message='Use one nonempty, bounded answer for each option label.')
        if len(set(value.casefold() for value in options)) != len(options):
            return dict(kind='invalid', message='Two options contain the same answer, so a unique label is not determined. Please provide distinct options or allow both labels.')
        # A standalone Question: is structural; every subsequent clause stays.
        context = re.sub(r'(?i)^question\s*:\s*', '', context, count=1)
        return dict(kind='choice', context=context, options=options)
    if re.match(r'(?i)^\s*(?:premises|facts|scenario|context)\s*:', text) and re.search(r'(?im)^\s*(?:question|query|prove)\s*:', text):
        if '```' in text:
            return None
        return dict(kind='premises', context=text)
    return None
