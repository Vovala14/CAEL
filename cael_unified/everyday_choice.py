"""Everyday choices by checking every option (0.4.4 work after release, 2026-11-22). Non-neural.

- **Matching requirements:** "My jar takes a screw-on lid with a 70 mm inner diameter. The shop has a 70 mm push-on, a
  72 mm screw-on and a 70 mm screw-on. Which one meets both requirements?" The options are read from a list. Each
  option's features are its measurements and the words that tell the options apart. The requirements are the features
  named in the other sentences.
- **Pay per use or buy a pass:** "$6 per class, or $40 for a monthly pass. I go 9 times. Which is cheaper?"
- **Smallest unused number:** "numbers 1, 2, 4 and 7 are in use; someone returns 2; which do I get?"
- **Whole items per batch:** "one sheet for every two pages, each document starting on a fresh sheet; a three-page
  letter and a five-page leaflet" means each document is rounded up separately.
"""
import math
import re

ROUTE = 'chat/choice'
NUMW = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12,
        'fifteen': 15, 'twenty': 20, 'once': 1, 'twice': 2}
N = r'(\d+(?:\.\d+)?|' + '|'.join(NUMW) + r')'
MEAS = re.compile(r'(?i)\b(\d+(?:\.\d+)?)\s*(mm|cm|m|ml|l|g|kg|inch(?:es)?|in|w|v|gb|tb|mah|hz|"|size\s+\d+)\b|\bsize\s+(\d+(?:\.\d+)?)\b')
ORDINAL = ['first', 'second', 'third', 'fourth', 'fifth', 'sixth']


def out(text, kind):
    return dict(route=f'{ROUTE}-{kind}', response=text, sources=[], reasoning=True, details=f'{kind} (everyday_choice.py)')


def num(w):
    w = w.lower()
    return float(w) if re.fullmatch(r'\d+(?:\.\d+)?', w) else NUMW[w]


# ------------------------------------------------------------------ matching requirements
def options_in(text):
    """The longest list of 'a/an ...' options: [(raw, start)]."""
    best = None
    for m in re.finditer(r'(?i)\b(?:has|have|sells?|offers?|stocks?|options?\s+are|choices\s+are|there\s+(?:is|are)|between|:)\s+((?:an?|the|one)\s+[^,.;:]+?'
                         r'(?:\s*,\s*(?:and\s+|or\s+)?(?:an?|the|one)\s+[^,.;:]+?)+)\s*(?:[.;?]|$)', text):
        parts = re.split(r'(?i)\s*,\s*(?:and\s+|or\s+)?|\s+(?:and|or)\s+(?=(?:an?|the|one)\s)', m[1])
        parts = [re.sub(r'(?i)^(?:an?|the|one)\s+', '', p.strip()) for p in parts if p.strip()]
        if len(parts) >= 2 and (best is None or len(parts) > len(best[0])):
            best = (parts, m.start(1), m.end(1))
    return best


def features(s):
    f = set()
    for m in MEAS.finditer(s):
        if m[3]:
            f.add(('size', float(m[3])))
        else:
            u = m[2].lower()
            if u.startswith('size'):
                f.add(('size', float(re.search(r'\d+', u)[0])))
            else:
                f.add((u.rstrip('es') if u.startswith('inch') else u, float(m[1])))
    for w in re.findall(r"(?i)\b([a-z]+(?:-[a-z]+)+|[a-z]{3,})\b", s):
        f.add(('word', w.lower()))
    return f


def match_requirements(text, q):
    if not re.search(r'(?i)\b(?:which|what)\s+(?:one|option|lid|size|model|item|of\s+them|\w+)?\s*(?:meets|fits|matches|satisfies|works|suits|should|do\s+i|would)\b', q):
        return None
    facts = re.sub(r'[^.!?\n]*\?', ' ', text)
    got = options_in(facts)
    if not got:
        return None
    opts, a, b = got
    feats = [features(o) for o in opts]
    words = [{v for k, v in f if k == 'word'} for f in feats]
    distinct = set().union(*words) - set.intersection(*words)       # words that tell the options apart
    req_text = facts[:a] + ' ' + facts[b:]
    rf = features(req_text)
    req = {x for x in rf if x[0] != 'word' or x[1] in distinct}
    # a measurement requirement only counts in a unit the options use
    units = {k for f in feats for k, _ in f if k != 'word'}
    req = {x for x in req if x[0] == 'word' or x[0] in units}
    if len(req) < 2 and not re.search(r'(?i)\b(?:one|single|the)\s+requirement\b', q):
        return None
    fits = [i for i, f in enumerate(feats) if req <= {(k, v) for k, v in f}]
    named = ', '.join(f'{v:g} {k}' if k != 'word' else v for k, v in sorted(req, key=str))
    if not fits:
        return out(f'**None of them.** You need {named}, and no option has all of that.', 'match-none')
    if len(fits) > 1:
        return out(f"**More than one fits**: " + ' and '.join(f'the {opts[i]}' for i in fits) + f' all have {named}.', 'match-several')
    i = fits[0]
    others = [f'the {opts[j]}' for j in range(len(opts)) if j != i]
    return out(f'**The {opts[i]}** (the {ORDINAL[i]} one). It is the only option with {named}; ' + ' and '.join(others) +
               ' each miss at least one requirement.', 'match')


# ------------------------------------------------------------------ pay per use or a pass
MONEY = r'([£$€])\s?(\d+(?:\.\d{2})?)'


def per_use_or_pass(text, q):
    if not re.search(r'(?i)\b(?:cheaper|cheapest|better\s+(?:deal|value)|save|worth\s+it|which\s+(?:option|way|is\s+better))\b', q):
        return None
    if re.search(r'(?i)\b(?:extra|surcharge|except|unless|even\s+with)\b', text):
        return None
    per = re.search(MONEY + r'\s*(?:per|a|an|each)\s+(visit|class|session|ride|trip|lesson|entry|game|day|use|journey|swim)\b', text)
    pas = re.search(r'(?i)' + MONEY + r'\s*(?:for\s+)?(?:an?\s+)?(?:(weekly|monthly|annual|yearly|season|month|week|unlimited|day)\s+)?(?:pass|membership|ticket|card|subscription)\b|'
                    r'\b(?:pass|membership|subscription)\s+(?:costs?|is|for)\s+' + MONEY, text)
    if not per or not pas:
        return None
    unit = per[3].lower()
    p = float(per[2])
    sym = per[1]
    pass_price = float(pas[2] if pas[2] else pas[5])
    m = re.search(r'(?i)\b' + N + r'\s+(?:times|' + unit + r's?|visits|sessions|classes|rides|trips|lessons)\b|\b(?:go|come|visit|ride|swim|play|train)\s+' + N + r'\s+times\b', text[max(per.end(), 0):] + ' ' + text)
    if not m:
        return None
    n = num(m[1] or m[2])
    pay = n * p
    def money(v):
        return f'{sym}{v:,.2f}'.replace('.00', '')
    if abs(pay - pass_price) < 1e-9:
        return out(f'**They cost the same**: {n:g} × {money(p)} = {money(pay)}, the same as the pass.', 'pass-same')
    cheaper = 'paying each time' if pay < pass_price else 'the pass'
    diff = abs(pay - pass_price)
    breakeven = math.floor(pass_price / p) + 1
    return out(f'**{cheaper.capitalize()}, by {money(diff)}.** Paying each time: {n:g} × {money(p)} = {money(pay)}; the pass: {money(pass_price)}. '
               f'The pass starts to win from {breakeven} {unit}s.', 'pass')


# ------------------------------------------------------------------ smallest unused number
def smallest_unused(text, q):
    if not re.search(r'(?i)\bsmallest\s+(?:unused|free|available|positive|number|ticket)|\blowest\s+(?:unused|free|available)', text):
        return None
    if not re.search(r'(?i)\b(?:which|what)\b.*\b(?:ticket|number|do\s+i\s+get|will\s+i\s+get|get)\b', q):
        return None
    m = re.search(r'(?i)\bnumbers?\s+((?:\d+\s*,\s*)*\d+(?:\s*,?\s*and\s+\d+)?)\s+(?:are|is)\s+(?:in\s+use|taken|used|out|handed\s+out|occupied)', text)
    if not m:
        return None
    used = {int(x) for x in re.findall(r'\d+', m[1])}
    freed = set()
    for r in re.finditer(r'(?i)\b(?:returns?|returned|hands?\s+back|handed\s+back|gives?\s+back|frees?|freed|releases?)\s+(?:number\s+|ticket\s+)?(\d+)', text):
        freed.add(int(r[1]))
    for r in re.finditer(r'(?i)\b(?:takes?|took|gets?|got)\s+(?:number\s+|ticket\s+)?(\d+)\b', text):
        used.add(int(r[1]))
    used -= freed
    k = 1
    while k in used:
        k += 1
    return out(f'**{k}.** In use now: ' + ', '.join(map(str, sorted(used))) + (f' (after {", ".join(map(str, sorted(freed)))} came back)' if freed else '') +
               f', so the smallest unused positive number is {k}.', 'smallest-unused')


# ------------------------------------------------------------------ whole items per batch
def per_batch(text, q):
    m = re.search(r'(?i)\bone\s+(\w+)\s+(?:for\s+)?(?:every|per|for\s+each)\s+(pair|two|three|four|' + N[1:-1] + r')\s+(?:of\s+)?(\w+)', text)
    if not m or not re.search(r'(?i)\bhow\s+many\s+' + m[1][:4], q):
        return None
    k = 2 if m[2].lower() in ('pair', 'two') else int(num(m[2]))
    fresh = re.search(r'(?i)\b(?:each|every)\s+(?:document|file|item|order|batch|job|one)\s+(?:starts?|starting|begins?|beginning|on|gets?)\s+(?:on\s+)?(?:a\s+)?(?:fresh|new|separate|its\s+own)\b|'
                      r'\bstarting\s+each\s+\w+\s+on\s+a\s+(?:fresh|new)\b', text)
    items = [(num(x[1]), x[0]) for x in re.finditer(r'(?i)\b' + N + r'-' + m[3].rstrip('s') + r's?\b|\b' + N[:-1] + r')\s+' + m[3] + r'\b', text) if x[1]]
    items = [(int(n), raw) for n, raw in items]
    if len(items) < 2 or not fresh:
        return None
    each = [math.ceil(n / k) for n, _ in items]
    total = sum(each)
    pooled = math.ceil(sum(n for n, _ in items) / k)
    return out(f'**{total} {m[1]}s.** Each starts on its own {m[1]}, so round up separately: ' +
               '; '.join(f'{n} {m[3]} → {e}' for (n, _), e in zip(items, each)) +
               (f'. (Pooled together it would be {pooled}, but the fresh start for each adds the difference.)' if pooled != total else '.'), 'per-batch')


def respond(messages):
    users = [(m.get('content') or '').strip() for m in messages if m.get('role') == 'user']
    if not users:
        return None
    qs = re.findall(r'[^.!?\n]*\?', users[-1])
    if not qs:
        return None
    q = qs[-1]
    text = '\n'.join(users[-4:])
    for fn in (smallest_unused, per_batch, per_use_or_pass, match_requirements):
        try:
            got = fn(text, q)
        except (ValueError, KeyError, IndexError, TypeError, ZeroDivisionError):
            got = None
        if got:
            return got
    return None
