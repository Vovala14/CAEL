"""The Reasoner: small word problems and puzzles worked out exactly, with no model.

- Story sums about one person's things: 'Tom has 3 apples. He gives 1 to Sue and buys 4 more. How many does he have now?'
- Chains: 'What's 15% of 240, and then add 20 to it?'
- Sum and difference: 'A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. How much is the ball?'
- Work rates: 'If 5 machines take 5 minutes to make 5 widgets, how long do 100 machines take for 100 widgets?'
- Primes and factors: 'Is 91 a prime number?'
- Rules about individuals: 'Every cat in the house is black. Felix is in the house. What colour is Felix?'
- Follow-ups on the last result: 'And if he eats half of them?', 'And if I get 25 extra minutes?'

Each one is a parse into numbers or rules, then arithmetic or a closure; anything it cannot read exactly is left to the other desks.
"""
import math
import re

ROUTE = 'chat/reason'
WORDS = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
         'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18,
         'nineteen': 19, 'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'a dozen': 12, 'a couple of': 2, 'a': 1, 'an': 1}
NUM = r'(\d+(?:\.\d+)?|' + '|'.join(sorted((w for w in WORDS if w not in ('a', 'an')), key=len, reverse=True)) + r')'


def num(s):
    s = s.lower().strip()
    return float(s) if re.fullmatch(r'\d+(?:\.\d+)?', s) else float(WORDS[s])


def fmt(x):
    if abs(x - round(x)) < 1e-9:
        return f'{int(round(x)):,}'
    return f'{x:,.2f}'.rstrip('0').rstrip('.')


def money(x, sym):
    return f'{sym}{x:,.2f}' if sym else fmt(x)


def out(text, kind, details):
    return dict(route=ROUTE + '-' + kind, response=text, sources=[], reasoning=True, details=details + ' (reasoner.py)')


# ------------------------------------------------------------------ primes
PRIME = re.compile(r'(?i)(?:^|[,.!?:;]\s*|\b(?:me|wondering|curious|know)\s+(?:if\s+|whether\s+)?)(?:is|are)\s+(\d{1,12})\s+(?:a\s+)?prime(?:\s+numbers?)?\s*\??\s*$|\bprime factors? of (\d{1,12})\b|\bfactori[sz]e (\d{1,12})\b')


def factors(n):
    out_, d = [], 2
    while d * d <= n:
        while n % d == 0:
            out_.append(d)
            n //= d
        d += 1 if d == 2 else 2
    if n > 1:
        out_.append(n)
    return out_


def prime(text):
    m = PRIME.search(text)
    if not m:
        return None
    n = int(next(g for g in m.groups() if g))
    if n < 2:
        return out(f'**No.** {n} is not prime: a prime is a whole number greater than 1 whose only divisors are 1 and itself.', 'prime', 'Prime test')
    f = factors(n)
    if m[1]:
        if len(f) == 1:
            return out(f'**Yes**, {n:,} is prime: no whole number from 2 up to its square root (about {math.isqrt(n)}) divides it.', 'prime', 'Prime test by trial division')
        return out(f'**No**, {n:,} is not prime: {n:,} = {" × ".join(map(str, f))}.', 'prime', 'Prime test by trial division')
    if len(f) == 1:
        return out(f'{n:,} is prime, so its only prime factor is itself.', 'prime', 'Factorised by trial division')
    return out(f'{n:,} = **{" × ".join(map(str, f))}**.', 'prime', 'Factorised by trial division')


# ------------------------------------------------------------------ sum and difference
PAIR = re.compile(r'(?i)\b(?:an? |the )?(\w+) and (?:an? |the )?(\w+) (?:cost|costs|weigh|weighs|together cost|are|come to|add up to)\s+(?:a total of\s+|together\s+|in total\s+)?'
                  r'([$£€]?)(\d+(?:\.\d+)?)\s*(kg|g|pounds|lbs?|years?)?(?: in total| altogether| together)?\b')
MORE = re.compile(r'(?i)\bthe (\w+) (?:costs|weighs|is) ([$£€]?)(\d+(?:\.\d+)?)\s*(?:kg|g|pounds|lbs?|years?)? (more|less|heavier|lighter|older|younger|cheaper|dearer) than the (\w+)')
ASK_ONE = re.compile(r'(?i)\bhow (?:much|heavy|old) (?:is|does|do) (?:the )?(\w+)|\bwhat (?:does|is) (?:the )?(\w+)')


def pair(text):
    m, d = PAIR.search(text), MORE.search(text)
    if not (m and d):
        return None
    a, b = m[1].lower().rstrip('s'), m[2].lower().rstrip('s')
    big, small = d[1].lower().rstrip('s'), d[5].lower().rstrip('s')
    if {big, small} != {a, b}:
        return None
    if d[4].lower() in ('less', 'lighter', 'younger', 'cheaper'):
        big, small = small, big
    total, diff = float(m[4]), float(d[3])
    sym = m[3] or d[2]
    lo, hi = (total - diff) / 2, (total + diff) / 2
    q = ASK_ONE.search(text[d.end():]) or ASK_ONE.search(text)
    want = next((g.lower().rstrip('s') for g in (q.groups() if q else ()) if g), small)
    val, other, other_val = (hi, small, lo) if want == big else (lo, big, hi)
    name = want if want in (big, small) else small
    unit = (' ' + m[5]) if m[5] else ''
    return out(f'The {name} is **{money(val, sym)}{unit}** (and the {other} {money(other_val, sym)}{unit}).\n\n'
               f'Working: the two together are {money(total, sym)}, and the {big} is {money(diff, sym)} more. Take the difference away and what is left is two '
               f'equal shares: {money(total, sym)} − {money(diff, sym)} = {money(total - diff, sym)}, so the {small} is {money(lo, sym)} and the {big} '
               f'{money(lo, sym)} + {money(diff, sym)} = {money(hi, sym)}. Check: {money(lo, sym)} + {money(hi, sym)} = {money(total, sym)}.'
               + (' (The quick answer of ' + money(total - 1, sym) + ' does not work: then the difference would be only ' + money(total - 2 * (total - 1), sym) + '.)'
                  if sym and abs(diff - 1) < 1e-9 and total > 1 else ''), 'pair', 'Sum and difference solved as two equations')


# ------------------------------------------------------------------ work rates
UNIT = r'(seconds?|minutes?|mins?|hours?|hrs?|days?|weeks?)'
RATE = re.compile(r'(?i)\b' + NUM + r' (\w+?)s? (?:take|takes|took|need|needs) ' + NUM + ' ' + UNIT + r' to (\w+) ' + NUM + r' (\w+)|'
                  r'\b(?:it )?takes? ' + NUM + r' (\w+?)s? ' + NUM + ' ' + UNIT + r' to (\w+) ' + NUM + r' (\w+)')
RATE_Q = re.compile(r'(?i)\b' + NUM + r' (\w+?)s?\b(?: (?:take|need))?(?: to (?:\w+) |, | for | making | (?:make|build|dig|paint|produce|bake|pick|eat|do) )' + NUM + r' (\w+)')


def unit_name(u):
    u = u.lower().rstrip('s')
    return {'min': 'minute', 'hr': 'hour'}.get(u, u)


def rate(text):
    m = RATE.search(text)
    if not m or not re.search(r'(?i)\bhow (?:long|many (?:minutes|hours|days|seconds|weeks))\b', text):
        return None
    g = m.groups()
    a, who, t, u, verb, w, what = (g[0:7] if g[0] else g[7:14])
    a, t, w = num(a), num(t), num(w)
    rest = text[m.end():]
    q = RATE_Q.search(rest)
    if not q or not q[2].lower().startswith(who.lower()[:4]):
        return None
    b, v = num(q[1]), num(q[3])
    if not a or not b or not w:
        return None
    each = t * a / w                     # worker-time per item
    ans = each * v / b
    un = unit_name(u)
    plural = lambda x: un + ('' if abs(x - 1) < 1e-9 else 's')
    note = ''
    if a == t == w and b == v:
        note = f' The pattern {fmt(a)}-{fmt(a)}-{fmt(a)} tempts people to say {fmt(b)}, but each {who} makes one {what.rstrip("s")} in {fmt(t)} {plural(t)}, whatever the number of {who}s.'
    return out(f'**{fmt(ans)} {plural(ans)}**.\n\nWorking: {fmt(a)} {who}s make {fmt(w)} {what} in {fmt(t)} {plural(t)}, so one {who} takes {fmt(each)} {plural(each)} '
               f'per {what.rstrip("s")}. {fmt(v)} {what} need {fmt(each * v)} {who}-{plural(2)} of work; shared between {fmt(b)} {who}s that is '
               f'{fmt(each * v)} ÷ {fmt(b)} = {fmt(ans)} {plural(ans)}.{note}', 'rate', 'Work rate: time is proportional to items and inversely to workers')


# ------------------------------------------------------------------ chains
START = [
    (re.compile(r'(?i)(\d+(?:\.\d+)?)\s*(?:%|percent|per cent) of ([$£€]?)(\d+(?:,\d{3})*(?:\.\d+)?)'), lambda m: (float(m[1]) * float(m[3].replace(',', '')) / 100, f'{fmt(float(m[1]))}% of {m[2]}{m[3]} = ', m[2])),
    (re.compile(r'(?i)\b(?:half|a half) of ([$£€]?)(\d+(?:\.\d+)?)'), lambda m: (float(m[2]) / 2, f'half of {m[1]}{m[2]} = ', m[1])),
    (re.compile(r'(?i)(?:start (?:with|from)|take|begin with) ([$£€]?)(\d+(?:\.\d+)?)'), lambda m: (float(m[2]), f'{m[1]}{m[2]}', m[1])),
    (re.compile(r'(?i)\bwhat(?:\'s| is) ([$£€]?)(\d+(?:\.\d+)?)\b(?! ?%)'), lambda m: (float(m[2]), f'{m[1]}{m[2]}', m[1])),
]
STEP = re.compile(r'(?i)\b(?:and )?then,? (?:you )?(?:(add|plus|subtract|minus|take away|multiply (?:it |that |this )?by|times|divide (?:it |that |this )?by)\s*(\d+(?:\.\d+)?)'
                  r'|(double|halve|square|triple) (?:it|that|this|the result)|(add|take|subtract) (\d+(?:\.\d+)?)\s*(%|percent)(?: (?:to|from|off))?)')


def chain(text):
    if not re.search(r'(?i)\bthen\b', text):
        return None
    for pat, f in START:
        m = pat.search(text)
        if m and m.start() < (re.search(r'(?i)\bthen\b', text).start()):
            value, shown, sym = f(m)
            break
    else:
        return None
    steps = list(STEP.finditer(text, m.end()))
    if not steps:
        return None
    lines = []
    lines.append((shown + money(value, sym)) if shown.endswith('= ') else f'Start: {money(value, sym)}')
    for s in steps:
        before = value
        if s[1]:
            op, n = s[1].lower(), float(s[2])
            if op in ('add', 'plus'):
                value += n
                lines.append(f'{money(before, sym)} + {fmt(n)} = {money(value, sym)}')
            elif op in ('subtract', 'minus', 'take away'):
                value -= n
                lines.append(f'{money(before, sym)} − {fmt(n)} = {money(value, sym)}')
            elif op.startswith('multiply') or op == 'times':
                value *= n
                lines.append(f'{money(before, sym)} × {fmt(n)} = {money(value, sym)}')
            else:
                if n == 0:
                    return None
                value /= n
                lines.append(f'{money(before, sym)} ÷ {fmt(n)} = {money(value, sym)}')
        elif s[3]:
            op = s[3].lower()
            value = {'double': value * 2, 'halve': value / 2, 'square': value * value, 'triple': value * 3}[op]
            lines.append(f'{op} {money(before, sym)} = {money(value, sym)}')
        else:
            p = float(s[5])
            value = value * (1 + p / 100) if s[4].lower() == 'add' else value * (1 - p / 100)
            lines.append(f'{money(before, sym)} {"+" if s[4].lower() == "add" else "−"} {fmt(p)}% = {money(value, sym)}')
    return out(f'**{money(value, sym)}**.\n\nWorking:\n' + '\n'.join(f'{i}. {l}' for i, l in enumerate(lines, 1)), 'chain', 'Worked the steps in order')


# ------------------------------------------------------------------ story sums
HAS = re.compile(r'(?i)\b([A-Z][a-z]+|I|we|she|he|they) (?:has|have|had|owns?|starts? (?:out )?with|started with|collected|bought|baked|picked) ' + NUM + r' ([a-z]+)')
ADD = r'(?:buys?|bought|gets?|got|finds?|found|receives?|received|picks?|picked|is given|was given|wins?|won|earns?|earned|adds?|added|makes?|made|bakes?|baked|collects?|collected)'
SUB = r'(?:gives?(?: away)?|gave(?: away)?|loses?|lost|eats?|ate|sells?|sold|drops?|dropped|uses?|used|spends?|spent|breaks?|broke|donates?|donated|throws? away|threw away|lends?|lent|shares?)'
EVENT = re.compile(r'(?i)\b(?:(' + ADD + r')|(' + SUB + r'))\s+(?:(?:him|her|them|me|us)\s+)?(?:another\s+)?(half|a third|a quarter|' + NUM[1:-1] + r')\b(?:\s+(?:of\s+)?(?:them|it|those))?(?:\s+(more|extra))?|\b(doubles?|doubled|triples?|tripled)\b')
HOW_MANY = re.compile(r'(?i)\bhow many(?: \w+)? (?:does|do|did|is|are|has|have|will|would)\b|\bhow many (?:are|is) (?:left|there)\b|\bhow many \w+ (?:now|left)\b')
FRACTION = {'half': 0.5, 'a third': 1 / 3, 'a quarter': 0.25}


def apply(value, ev):
    if ev[5]:
        k = 2 if ev[5].lower().startswith('doubl') else 3
        return value * k, f'{"doubled" if k == 2 else "tripled"}: {fmt(value)} × {k} = {fmt(value * k)}'
    amount = ev[3].lower()
    if amount in FRACTION:
        n = value * FRACTION[amount]
    else:
        n = num(amount)
    verb = (ev[1] or ev[2]).lower()
    if ev[1]:
        return value + n, f'{verb} {fmt(n)}: {fmt(value)} + {fmt(n)} = {fmt(value + n)}'
    return value - n, f'{verb} {fmt(n)}: {fmt(value)} − {fmt(n)} = {fmt(value - n)}'


def story(text):
    h = HAS.search(text)
    if not h or not HOW_MANY.search(text):
        return None
    value, thing = num(h[2]), h[3]
    if len(re.findall(r'(?i)\b(?:has|have) ' + NUM, text)) > 1:
        return None                     # two people's counts: a comparison puzzle for the other solvers
    if re.search(r'(?i)\b(?:' + ADD + '|' + SUB + r')\s+(?:some|a few|several|many|a lot|lots|any|more)\b', text):
        return None                     # 'receive some': an unknown amount, so no exact total
    if re.search(r'(?i)\beach\b|\bper\b|\bwith ' + NUM + r' \w+', text):
        return None                     # groups ('4 boxes with 6 apples each') are the group helper's
    q = re.search(r'(?i)\bhow many(?: (\w+))? (?:does|do|did|will|would|has|have) ([A-Z][a-z]+|he|she|they|I|we|you)\b', text)
    if q and q[2][:1].isupper() and q[2] not in ('I',) and h[1] not in (q[2],) and h[1][:1].isupper() and h[1] != 'I':
        return None                     # asks about someone else ('How many does Ana have?' after Sam's stickers)
    if q and q[1] and lemma(q[1]) != lemma(thing):
        return None                     # counts a different thing than the story started with
    lines = [f'start: {fmt(value)} {thing}']
    for ev in EVENT.finditer(text, h.end()):
        if ev[3] and ev[3].lower() in ('a', 'an') and not ev[4]:
            continue
        value, line = apply(value, ev)
        lines.append(line)
    if len(lines) < 2 or value < 0 or abs(value - round(value)) > 1e-9:
        return None
    return out(f'**{fmt(value)} {thing}**.\n\nWorking:\n' + '\n'.join(f'{i}. {l}' for i, l in enumerate(lines, 1)), 'story', 'Followed the story step by step')


# ------------------------------------------------------------------ rules about individuals
RULE = re.compile(r'(?i)\b(?:all|every|each|any) (?:the )?([a-z]+?)s?\b((?: (?:in|at|on|from|of|who|that) [a-z ]+?)?) (is|are|can|have|has) (?:an? )?([a-z-]+(?: [a-z-]+)?)\s*[.!;]')
NO_RULE = re.compile(r'(?i)\b(?:no) ([a-z]+?)s?\b((?: (?:in|at|on|from|of) [a-z ]+?)?) (is|are|can|has|have) (?:an? )?([a-z-]+(?: [a-z-]+)?)\s*[.!;]')
FACT = re.compile(r'\b([A-Z][a-z]+) (?:is|lives|sits|stays|works) (?:an? |in |at |on |from |of )?(?:the )?([a-z]+(?: [a-z]+)?)\s*[.!;]')
WHAT = re.compile(r'(?i)\bwhat (colou?r|kind|type|size|shape) (?:is|are) ([A-Z][a-z]+)|\b(?:is|can|does|has) ([A-Z][a-z]+) (?:have )?(?:an? )?([a-z-]+(?: [a-z-]+)?)\s*\?')
COLOURS = {'black', 'white', 'red', 'blue', 'green', 'yellow', 'brown', 'grey', 'gray', 'orange', 'pink', 'purple', 'golden', 'ginger'}


def verb(v):
    v = v.lower()
    return {'are': 'is', 'have': 'has'}.get(v, v)


def lemma(w):
    w = w.lower().strip()
    return w[:-1] if w.endswith('s') and not w.endswith('ss') else w


def individuals(text):
    rules = []                          # (class, restriction, property, positive)
    for m in RULE.finditer(text):
        rules.append((lemma(m[1]), m[2].strip().lower(), m[4].lower(), True, verb(m[3])))
    for m in NO_RULE.finditer(text):
        rules.append((lemma(m[1]), m[2].strip().lower(), m[4].lower(), False, verb(m[3])))
    q = WHAT.search(text)
    if not rules or not q:
        return None
    name = q[2] or q[3]
    facts = {lemma(f[2]) for f in FACT.finditer(text) if f[1] == name} | {f[2].lower() for f in FACT.finditer(text) if f[1] == name}
    places = {re.sub(r'^(?:in|at|on|from|of) (?:the )?', '', f[0].split(' ', 2)[-1].rstrip('.!; ')).lower()
              for f in FACT.finditer(text) if f[1] == name}
    known, why, assumed = set(facts), [], []
    for _ in range(4):
        for cls, where, prop, pos, vb in rules:
            spot = re.sub(r'^(?:in|at|on|from|of|who|that) (?:the )?', '', where)
            in_class = cls in known
            in_place = bool(spot) and (spot in places or spot in known)
            if (in_class and (not spot or in_place)) or (in_place and not in_class):
                key = prop if pos else 'not ' + prop
                if key not in known:
                    known.add(key)
                    known.add(lemma(prop))
                    why.append((cls, where, prop, pos, vb))
                    if in_place and not in_class:
                        assumed.append(cls)
    if not why:
        return None
    rule_text = lambda r: f'{"every" if r[3] else "no"} {r[0]}{(" " + r[1]) if r[1] else ""} {r[4]} {r[2]}'
    caveat = (f' (This assumes {name} is a {assumed[0]}: the rule is only about {assumed[0]}s{(" " + why[0][1]) if why[0][1] else ""}.)' if assumed else '')
    if q[1]:
        kind = q[1].lower()
        hit = next((r for r in why if r[3] and (kind not in ('colour', 'color') or r[2] in COLOURS)), None)
        if not hit:
            return None
        return out(f'**{hit[2].capitalize()}.** {name} is {hit[2]}, because {rule_text(hit)}.{caveat}', 'rules', 'Applied the general rule to the individual')
    prop = q[4].lower()
    hit = next((r for r in why if r[2] == prop or lemma(r[2]) == lemma(prop)), None)
    if not hit:
        return None
    if hit[3]:
        return out(f'**Yes.** {name} {hit[4]} {prop}, because {rule_text(hit)}.{caveat}', 'rules', 'Applied the general rule to the individual')
    return out(f'**No.** {name} {"cannot" if hit[4] == "can" else "does not have" if hit[4] == "has" else "is not"} {prop}, because {rule_text(hit)}.{caveat}', 'rules', 'Applied the general rule to the individual')


# ------------------------------------------------------------------ follow-ups on the last result
LAST_NUM = re.compile(r'^\*\*([$£€]?)(\d[\d,]*(?:\.\d+)?)\s*([a-z]+)?\*\*')
LAST_CLOCK = re.compile(r'^\*\*(\d{1,2}):(\d{2})\*\*|^(?:You arrive at|It now starts at) \*\*(\d{1,2}):(\d{2})\*\*')
FOLLOW_TIME = re.compile(r'(?i)^\s*(?:and |but |what )?(?:if|about|with)?\b.*?\b(\d+(?:\.\d+)?|an?|half an?) (?:extra |more |additional )?(minutes?|mins?|hours?|hrs?)\b(?: (extra|more|longer|later|earlier|less|delay|late))?')
FOLLOW_NUM = re.compile(r'(?i)^\s*(?:and |but |ok,? |so )?(?:what )?(?:if|about|then)\b')


def follow(messages):
    text = (messages[-1].get('content') or '').strip()
    if len(text.split()) > 16 or len(messages) < 3:
        return None
    said = next((m.get('content') or '' for m in reversed(messages[:-1]) if m.get('role') == 'assistant'), '')
    c = LAST_CLOCK.search(said)
    if c:
        t = FOLLOW_TIME.search(text)
        if t and re.search(r'(?i)\b(?:extra|more|longer|later|another|additional|delay|delayed|late|earlier|less|fewer|sooner|added?|give)\b|\bif\b', text):
            h, mi = int(c[1] or c[3]), int(c[2] or c[4])
            amount = {'a': 1, 'an': 1, 'half a': 0.5, 'half an': 0.5}.get(t[1].lower(), None)
            amount = float(t[1]) if amount is None else amount
            minutes = amount * (60 if t[2].lower().startswith('h') else 1)
            sign = -1 if re.search(r'(?i)\b(?:earlier|less|fewer|sooner|shorter)\b', text) else 1
            total = (h * 60 + mi + sign * minutes) % (24 * 60)
            hh, mm = int(total // 60), int(round(total % 60))
            dur = (f'{fmt(minutes / 60)} hour' + ('' if minutes == 60 else 's')) if minutes % 60 == 0 else f'{fmt(minutes)} minutes'
            return out(f'**{hh:02d}:{mm:02d}** ({h:02d}:{mi:02d} {"+" if sign > 0 else "−"} {dur}).', 'time-followup', 'Moved the last clock time')
        return None
    n = LAST_NUM.search(said)
    asked = next((m.get('content') or '' for m in reversed(messages[:-1]) if m.get('role') == 'user'), '')
    if not n or not FOLLOW_NUM.search(text) or not (HAS.search(asked) and HOW_MANY.search(asked)):   # only after a story sum
        return None
    value, sym, thing = float(n[2].replace(',', '')), n[1], n[3] or ''
    fake = 'x has ' + fmt(value) + ' things. ' + text
    evs = list(EVENT.finditer(fake, len('x has ' + fmt(value) + ' things.')))
    evs = [e for e in evs if not (e[3] and e[3].lower() in ('a', 'an') and not e[4])]
    if not evs:
        return None
    lines = [f'start: {fmt(value)}{(" " + thing) if thing else ""}']
    for e in evs:
        value, line = apply(value, e)
        lines.append(line)
    if value < 0:
        return None
    shown = (sym + fmt(value)) if sym else fmt(value)
    return out(f'**{shown}{(" " + thing) if thing else ""}**.\n\nWorking:\n' + '\n'.join(f'{i}. {l}' for i, l in enumerate(lines, 1)),
               'story-followup', 'Carried on from the last result')


def story_reply(messages):
    """A story sum, tried after the other desks (team.py)."""
    text = (messages[-1].get('content') or '').strip()
    if not text or len(text) > 400:
        return None
    try:
        return story(text)
    except (ValueError, KeyError, ZeroDivisionError, IndexError):
        return None


# ------------------------------------------------------------------ legs
LEGS = {'dog': 4, 'cat': 4, 'horse': 4, 'cow': 4, 'sheep': 4, 'pig': 4, 'goat': 4, 'rabbit': 4, 'mouse': 4, 'hamster': 4,
        'donkey': 4, 'lion': 4, 'tiger': 4, 'elephant': 4, 'zebra': 4, 'giraffe': 4, 'bear': 4, 'fox': 4, 'deer': 4,
        'chicken': 2, 'hen': 2, 'duck': 2, 'goose': 2, 'bird': 2, 'parrot': 2, 'ostrich': 2, 'owl': 2, 'turkey': 2,
        'person': 2, 'people': 2, 'human': 2, 'child': 2, 'children': 2, 'man': 2, 'men': 2, 'woman': 2, 'women': 2,
        'spider': 8, 'ant': 6, 'bee': 6, 'beetle': 6, 'insect': 6, 'fly': 6, 'butterfly': 6,
        'snake': 0, 'fish': 0, 'goldfish': 0, 'worm': 0, 'snail': 0}
SINGULAR = {'people': 'person', 'children': 'child', 'men': 'man', 'women': 'woman', 'geese': 'goose', 'mice': 'mouse',
            'sheep': 'sheep', 'fish': 'fish', 'deer': 'deer', 'flies': 'fly', 'butterflies': 'butterfly', 'puppies': 'dog',
            'kittens': 'cat', 'geese.': 'goose'}
LEG_WORDS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
             'a': 1, 'an': 1, 'twelve': 12, 'eleven': 11, 'twenty': 20}


def animal(word):
    w = word.lower()
    w = SINGULAR.get(w, w[:-1] if w.endswith('s') and w[:-1] in LEGS else w)
    return w if w in LEGS else None


def legs(text):
    """'I have 2 dogs and 3 cats. How many legs if I count only the dogs?' -> 8, with the working."""
    if not re.search(r'(?i)\bhow many (?:legs|feet|paws)\b', text):
        return None
    counts = []
    for m in re.finditer(r'(?i)\b(\d{1,4}|' + '|'.join(LEG_WORDS) + r')\s+([a-z]+)\b', text):
        kind = animal(m[2])
        if kind:
            n = int(m[1]) if m[1].isdigit() else LEG_WORDS[m[1].lower()]
            counts.append((kind, n, m[2]))
    if not counts:
        return None
    asked = text[re.search(r'(?i)\bhow many (?:legs|feet|paws)\b', text).start():]
    only = [animal(w) for w in re.findall(r'(?i)\b(?:only|just)\s+(?:the\s+|my\s+)?([a-z]+)', asked)]
    only += [animal(w) for w in re.findall(r'(?i)\b(?:do|does)\s+(?:the\s+|my\s+)?([a-z]+)\s+have\b', asked)]
    only = [w for w in only if w]
    picked = [c for c in counts if c[0] in only] if only else counts
    if not picked:
        return None
    total = sum(LEGS[k] * n for k, n, _ in picked)
    working = ' + '.join(f'{n} {w} × {LEGS[k]}' for k, n, w in picked)
    left = [w for k, n, w in counts if c_not(picked, k)]
    plural = len(left) > 1 or (left and left[0].endswith('s') and left[0] not in ('mouse',))
    note = f' The {" and ".join(left)} {"are" if plural else "is"} not counted, as you asked.' if only and left else ''
    if len(picked) == 1 and picked[0][1] == 1 and not only:
        k, _, w = picked[0]
        return out(f'**{LEGS[k]} legs** (a {w} has {LEGS[k]}).', 'legs', 'Legs counted per animal from a fixed table')
    return out(f'**{total} legs** ({working} = {total}).{note}', 'legs', 'Legs counted per animal from a fixed table')


def c_not(picked, kind):
    return all(k != kind for k, _, _ in picked)


# ------------------------------------------------------------------ sums said in words ("9 times 6")
SPOKEN = re.compile(r'(?i)^\s*(?:(?:so|ok|okay|um+|well|and)[,\s]+)*(?:what(?:\'s| is)|calculate|work out|how much is|tell me)?\s*'
                    r'(-?\d+(?:\.\d+)?)\s+(times|multiplied by|divided by|over|plus|minus|added to|take away|less)\s+(-?\d+(?:\.\d+)?)\s*[?.!]*\s*$')


def spoken(text):
    m = SPOKEN.match(text)
    if not m:
        return None
    a, word, b = float(m[1]), m[2].lower(), float(m[3])
    sign = {'times': '×', 'multiplied by': '×', 'divided by': '÷', 'over': '÷', 'plus': '+', 'added to': '+',
            'minus': '−', 'take away': '−', 'less': '−'}[word]
    if sign == '÷' and b == 0:
        return out("Dividing by zero has no answer.", 'arith', 'Arithmetic said in words')
    value = {'×': a * b, '÷': a / b if b else 0, '+': a + b, '−': a - b}[sign]
    return out(f'**{fmt(value)}** ({fmt(a)} {sign} {fmt(b)} = {fmt(value)}).', 'arith', 'Arithmetic said in words')


def respond(messages):
    text = (messages[-1].get('content') or '').strip()
    if not text or len(text) > 400:
        return None
    for solver in (spoken, prime, pair, rate, chain, individuals, legs):          # story sums run last in the team (story_reply)
        try:
            got = solver(text)
        except (ValueError, KeyError, ZeroDivisionError, IndexError):
            got = None
        if got is not None:
            return got
    try:
        # comparisons, spoken numbers, conversions, what is left, differences, sharing, weekdays, sorting (word_math.py)
        from . import word_math
        got = word_math.respond(messages)
        if got is not None:
            return got
    except Exception:
        pass
    try:
        return follow(messages)
    except (ValueError, KeyError, ZeroDivisionError, IndexError):
        return None
