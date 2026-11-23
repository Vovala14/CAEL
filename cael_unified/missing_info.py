"""Questions that the stated facts can't answer (0.4.4 work after release, 2026-11-22). Non-neural.

Four general checks, each replying with what is missing instead of a guess:
- **Only comparisons:** every number is a difference or a bound ("four minutes quicker", "both younger than ten"), but
  the question asks for an actual value.
- **Not decided yet:** a random choice happens later ("will choose a digit tomorrow") and the question wants certainty now.
- **Hidden identity:** the records hide who it was ("withheld number", "anonymous") and the question asks who, or
  whether it was the same person.
- **Wrong count for a shape:** the question speaks of three corners of a square, or five sides of a triangle.
"""
import re

ROUTE = 'chat/missing-info'
NUMW = r'(?:\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|fifty|hundred|half|a\s+quarter)'
COMPARE = re.compile(r'(?i)\b(?:quicker|faster|slower|more|less|fewer|longer|shorter|older|younger|taller|heavier|lighter|cheaper|dearer|'
                     r'earlier|later|bigger|smaller|than|apart|difference|extra|over|under|up\s+to|at\s+most|at\s+least)\b')
SHAPES = {'triangle': 3, 'triangular': 3, 'square': 4, 'rectangle': 4, 'rectangular': 4, 'oblong': 4, 'pentagon': 5, 'hexagon': 6, 'octagon': 8}
COUNT = {'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8}


def out(text, kind):
    return dict(route=f'{ROUTE}-{kind}', response=text, sources=[], reasoning=True, details=f'{kind} (missing_info.py)')


def only_comparisons(text, q):
    if not re.search(r'(?i)\b(?:what\s+(?:was|is|were)|how\s+(?:long|many|much|old|far|tall|heavy|big)\b)', q):
        return None
    if re.search(r'(?i)\b(?:how\s+much\s+(?:quicker|faster|slower|more|less|older|younger|longer|shorter)|difference|apart|compare)\b', q):
        asks_gap = True
    else:
        asks_gap = False
    facts = re.sub(r'[^.!?\n]*\?', ' ', text)
    nums = list(re.finditer(r'(?i)\b' + NUMW + r'\b', facts))
    nums = [m for m in nums if not re.match(r'(?i)(?:one|two)\b', m[0]) or re.search(r'(?i)\s+(?:minutes?|hours?|years?|km|miles?|metres?|kg|cm|days?)\b', facts[m.end():m.end() + 10])]
    if not nums:
        return None
    for m in nums:
        after = re.split(r'[.;,!?\n]', facts[m.end():m.end() + 30])[0]
        before = re.split(r'[.;,!?\n]', facts[max(0, m.start() - 16):m.start()])[-1]
        if not COMPARE.search(after + ' ' + before):
            return None         # an actual value is stated somewhere
    if asks_gap:
        if re.search(r'(?i)\b(?:than|under|below|at\s+most|younger|older)\b', facts) and not re.search(r'(?i)\b(?:quicker|faster|slower|more|less|longer|shorter)\s+than\b', facts):
            return out("**It can't be worked out.** You gave only limits, not the actual values, so the gap could be anything within those "
                       'limits.', 'bounds-only')
        return None
    quoted = [re.split(r'[.;,!?\n]', facts[m.start():m.end() + 30])[0].strip() for m in nums]
    return out("**It can't be worked out from that.** You gave only how the values compare (" + '; '.join(quoted[:2]) + '), not an actual '
               'value. Any starting value fits, so one real measurement is needed.', 'comparisons-only')


def not_decided(text, q):
    if not re.search(r'(?i)\bwill\s+(?:choose|pick|draw|roll|spin|select|generate|be\s+(?:chosen|drawn|picked|rolled))\b|\brandom(?:ly)?\b|\blottery\b|\bdice\b|\bcoin\b', text):
        return None
    if not re.search(r'(?i)\b(?:tomorrow|later|next\s+\w+|tonight|will)\b', text):
        return None
    if not re.search(r'(?i)\b(?:certain(?:ty)?|for\s+sure|exact(?:ly)?|guarantee\w*|definitely|now)\b', q):
        return None
    return out("**None, not with certainty.** The choice hasn't been made yet, so no exact result can be written down now. Only what "
               'every possible result shares is certain (for example, its pattern or format).', 'not-decided')


def hidden_identity(text, q):
    if not re.search(r'(?i)\b(?:withheld|hidden|hides?|anonymous(?:ly)?|unknown\s+(?:caller|sender|number)|private\s+number|no\s+caller\s+id|unsigned|unnamed)\b', text):
        return None
    if not re.search(r'(?i)\bwho\b|\bwhich\b|\bsame\s+person\b|\bone\s+person\b|\bdifferent\s+(?:people|person)\b', q):
        return None
    if re.search(r'(?i)\bsame\s+person\b|\bone\s+person\b|\bdifferent\s+(?:people|person)\b|\btwice\b', q + ' ' + text):
        return out("**There's no way to tell from those records.** They hide who it was, so one person twice and two different people "
                   'look exactly the same. Only another source (the caller, the provider, a message) could settle it.', 'hidden')
    return out("**There's no way to tell from that.** It hides who it was, so the identity can't be worked out from it; only another "
               'source could settle it.', 'hidden')


def shape_count(text, q):
    m = re.search(r'(?i)\b(' + '|'.join(SHAPES) + r')\b', text)
    if not m:
        return None
    n = SHAPES[m[1].lower()]
    k = re.search(r'(?i)\b(?:of\s+)?(?:the|its|all)\s+(two|three|four|five|six|seven|eight|\d)\s+(corners|sides|edges|angles|vertices)\b', q)
    if not k or COUNT.get(k[1].lower()) == n:
        return None
    return out(f"**The question doesn't fit the shape.** A {m[1].lower()} has {n} {k[2].lower()}, not {k[1].lower()}. If it's a "
               f'{m[1].lower()}, its corners are all right angles (90°), so none is sharper than the others.' if n == 4 else
               f"**The question doesn't fit the shape.** A {m[1].lower()} has {n} {k[2].lower()}, not {k[1].lower()}.", 'shape-count')


def respond(messages):
    users = [(m.get('content') or '').strip() for m in messages if m.get('role') == 'user']
    if not users:
        return None
    qs = re.findall(r'[^.!?\n]*\?', users[-1])
    if not qs:
        return None
    q = qs[-1]
    text = '\n'.join(users[-4:])
    for fn in (shape_count, hidden_identity, not_decided, only_comparisons):
        got = fn(text, q)
        if got:
            return got
    return None
