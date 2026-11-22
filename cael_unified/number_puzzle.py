"""Number and code puzzles by trying every candidate (0.4.4 work after release, 2026-11-22). Non-neural.

The subject is "the number", "my integer", "a two-digit code", "a PIN"... The rest of the text is read as constraints:
- **bounds:** greater / more than, above, over, at least, less than, below, under, at most, between;
- **kind:** even, odd, a multiple of / divisible by N, prime, a square number;
- **digits:** different or all the same, add up to N, product N, "the first digit is twice the second plus one",
  "the second digit is 4", "the first digit is 3 more than the second".
Every candidate in range is tested. The reply says which fits, that none fits (the statements contradict each other), or
that several fit. A sentence with number words that can't be read stops the solver.
"""
import re

ROUTE = 'chat/number-puzzle'
NUMW = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18,
        'nineteen': 19, 'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90,
        'hundred': 100}
N = r'(-?\d+|' + '|'.join(sorted(NUMW, key=len, reverse=True)) + r')'
POSW = {'first': 0, 'second': 1, 'third': 2, 'fourth': 3, 'last': -1, 'tens': 0, 'units': -1, 'ones': -1}
SUBJECT = re.compile(r'(?i)\b(?:(two|three|four|2|3|4)-digit\s+)?(number|integer|whole\s+number|code|pin|combination|password|digit)\b')


def out(text, kind):
    return dict(route=f'{ROUTE}-{kind}', response=text, sources=[], reasoning=True, details=f'{kind} (number_puzzle.py)')


def val(w):
    w = w.lower()
    return int(w) if re.fullmatch(r'-?\d+', w) else NUMW[w]


def digits_of(v, width):
    s = str(v).zfill(width) if width else str(abs(v))
    return [int(c) for c in s]


def is_prime(v):
    return v > 1 and all(v % d for d in range(2, int(v ** 0.5) + 1))


def read(text, width):
    """[(description, test(v) -> bool)]; None when a constraint sentence can't be read."""
    cs = []
    for sent in re.split(r'(?<=[.!?;])\s+|\n+|,\s*(?:and\s+)?(?=(?:the|its|it|and)\b)', text):
        s = sent.strip()
        if not s or s.endswith('?'):
            continue
        got = False
        low = s.lower()
        for rx, op in ((r'(?:strictly\s+)?(?:greater|more|bigger|larger|higher)\s+than\s+' + N, '>'), (r'\b(?:above|over|exceeds?)\s+' + N, '>'),
                       (r'\bat\s+least\s+' + N, '>='), (r'\b' + N + r'\s+or\s+more\b', '>='),
                       (r'(?:strictly\s+)?(?:less|smaller|fewer|lower)\s+than\s+' + N, '<'), (r'\b(?:below|under)\s+' + N, '<'),
                       (r'\bat\s+most\s+' + N, '<='), (r'\bno\s+more\s+than\s+' + N, '<='), (r'\b' + N + r'\s+or\s+less\b', '<=')):
            for m in re.finditer(rx, low):
                if re.search(r'\bdigit', low[max(0, m.start() - 30):m.start()]):
                    continue
                k = val(m[1])
                f = {'>': lambda v, k=k: v > k, '>=': lambda v, k=k: v >= k, '<': lambda v, k=k: v < k, '<=': lambda v, k=k: v <= k}[op]
                cs.append((f'{op} {k}', f))
                got = True
        m = re.search(r'\bbetween\s+' + N + r'\s+and\s+' + N, low)
        if m:
            a, b = sorted((val(m[1]), val(m[2])))
            cs.append((f'between {a} and {b}', lambda v, a=a, b=b: a < v < b))
            got = True
        if re.search(r'\bis\s+(?:an\s+)?even\b|\ban\s+even\s+(?:number|integer)\b', low):
            cs.append(('even', lambda v: v % 2 == 0))
            got = True
        if re.search(r'\bis\s+(?:an\s+)?odd\b|\ban\s+odd\s+(?:number|integer)\b', low):
            cs.append(('odd', lambda v: v % 2 == 1))
            got = True
        for m in re.finditer(r'\b(?:a\s+multiple\s+of|divisible\s+by)\s+' + N, low):
            k = val(m[1])
            cs.append((f'multiple of {k}', lambda v, k=k: k and v % k == 0))
            got = True
        if re.search(r'\bis\s+(?:a\s+)?prime\b', low):
            cs.append(('prime', is_prime))
            got = True
        if re.search(r'\bdigits?\s+(?:are|is)\s+(?:all\s+)?(?:different|distinct|unique)\b|\bno\s+(?:digit|two\s+digits)\s+(?:is\s+)?repeat', low):
            cs.append(('different digits', lambda v: len(set(digits_of(v, width))) == len(digits_of(v, width))))
            got = True
        if re.search(r'\bdigits?\s+are\s+(?:all\s+)?(?:the\s+same|identical|equal)\b|\ball\s+(?:its\s+|the\s+|of\s+its\s+)?digits\s+(?:are\s+)?(?:the\s+same|identical|equal)\b', low):
            cs.append(('same digits', lambda v: len(set(digits_of(v, width))) == 1))
            got = True
        m = re.search(r'\b(?:digits?\s+)?(?:add\s+(?:up\s+)?to|sum\s+to|total)\s+' + N + r'|\bsum\s+of\s+(?:the|its)\s+digits\s+is\s+' + N, low)
        if m and re.search(r'\bdigit|\bthey\b|\btogether\b', low):
            k = val(m[1] or m[2])
            cs.append((f'digits add to {k}', lambda v, k=k: sum(digits_of(v, width)) == k))
            got = True
        m = re.search(r'\bproduct\s+of\s+(?:the|its)\s+digits\s+is\s+' + N + r'|\bdigits\s+multiply\s+to\s+' + N, low)
        if m:
            k = val(m[1] or m[2])

            def prod(v, k=k):
                p = 1
                for d in digits_of(v, width):
                    p *= d
                return p == k
            cs.append((f'digit product {k}', prod))
            got = True
        m = re.search(r'\bthe\s+(first|second|third|fourth|last|tens|units|ones)\s+digit\s+is\s+(twice|double|three\s+times|half)\s+(?:the\s+)?(first|second|third|fourth|last|tens|units|ones)'
                      r'(?:\s+(?:one|digit))?(?:\s+(plus|minus|add|less)\s+' + N + r')?', low)
        if m:
            i, j = POSW[m[1]], POSW[m[3]]
            mul = {'twice': 2, 'double': 2, 'three times': 3, 'half': 0.5}[re.sub(r'\s+', ' ', m[2])]
            add = val(m[5]) * (-1 if m[4] in ('minus', 'less') else 1) if m[4] else 0
            cs.append((m[0], lambda v, i=i, j=j, mul=mul, add=add: len(digits_of(v, width)) > max(i, j, -1 - min(i, j, 0)) and
                       digits_of(v, width)[i] == digits_of(v, width)[j] * mul + add))
            got = True
        m = re.search(r'\bthe\s+(first|second|third|fourth|last|tens|units|ones)\s+digit\s+is\s+' + N + r'\s+(more|less|bigger|smaller|greater)\s+than\s+(?:the\s+)?'
                      r'(first|second|third|fourth|last|tens|units|ones)', low)
        if m:
            i, j, k = POSW[m[1]], POSW[m[4]], val(m[2]) * (1 if m[3] in ('more', 'bigger', 'greater') else -1)
            cs.append((m[0], lambda v, i=i, j=j, k=k: digits_of(v, width)[i] == digits_of(v, width)[j] + k))
            got = True
        m = re.search(r'\bthe\s+(first|second|third|fourth|last|tens|units|ones)\s+digit\s+is\s+' + N + r'\s*(?:[.,;]|$)', low)
        if m and not got:
            i, k = POSW[m[1]], val(m[2])
            cs.append((m[0], lambda v, i=i, k=k: digits_of(v, width)[i] == k))
            got = True
        if not got and (re.search(r'\d', s) or re.search(r'(?i)\b(?:twice|digit|sum|product|more\s+than|less\s+than|' + '|'.join(NUMW) + r')\b', s)) \
                and not re.search(r'(?i)\b(?:claims?|says?|slips?|both\s+of\s+these|has\s+a|is\s+a|pick(?:ed|s)?|cho(?:ose|se|sen)|think(?:ing)?\s+of)\b', s):
            return None
    return cs


def respond(messages):
    users = [(m.get('content') or '').strip() for m in messages if m.get('role') == 'user']
    if not users:
        return None
    qs = re.findall(r'[^.!?\n]*\?', users[-1])
    if not qs:
        return None
    q = qs[-1]
    if not re.search(r'(?i)\b(?:what|which)\s+(?:\w+\s+){0,2}(?:number|integer|code|pin|combination|digits?)\b|\bwhat\s+(?:is|could)\s+(?:it|the\s+(?:number|code))\b|'
                     r'\b(?:number|integer|code)\s+(?:fits|satisfies|works)\b|\bwhat\s+fits\b', q):
        return None
    text = '\n'.join(users[-4:])
    m = SUBJECT.search(text)
    if not m:
        return None
    wd = {'two': 2, 'three': 3, 'four': 4, '2': 2, '3': 3, '4': 4}.get((m[1] or '').lower())
    kind = m[2].lower()
    if wd:
        lead_zero = kind in ('code', 'pin', 'combination', 'password')
        rng = range(0 if lead_zero else 10 ** (wd - 1), 10 ** wd)
        width = wd if lead_zero else None
    elif kind == 'digit':
        rng, width = range(0, 10), None
    else:
        rng, width = range(-1000, 10001), None
    cs = read(re.sub(r'[^.!?\n]*\?', ' ', text), width or wd)
    if not cs:
        return None
    fits = [v for v in rng if all(t(v) for _, t in cs)]
    show = (lambda v: str(v).zfill(width)) if width else str
    rules = '; '.join(d for d, _ in cs)
    if not fits:
        return out(f'**None.** No {kind} satisfies every condition ({rules}): they contradict each other.', 'none')
    if len(fits) == 1:
        return out(f'**{show(fits[0])}.** It is the only {kind} that meets every condition ({rules}).', 'unique')
    if len(fits) <= 8:
        return out(f"**It can't be pinned down**: {len(fits)} fit ({', '.join(show(v) for v in fits)}).", 'several')
    return out(f"**It can't be pinned down** from that: {len(fits)} values fit every condition.", 'many')
