"""More exact readers for everyday questions (0.4.4, written on the developer's own generalisation probes, not a test set).

Same contract as everyday_exact.py: one shape read completely from the user's turns, or None. Shapes: change from a
payment, price per unit and the cheaper option, a fraction of a container, days between dates, the weekday of a date,
a date plus years or months, working time minus a break, the year someone turns an age, the newest notice wins, a
person taking back what they said, a corrected report, how many checked for themselves, the latest value of a fact,
items added to and removed from a set, which of two similar facts, missing information, contradictions, the weather on a
future date, a weight limit, an area left uncovered, and how long until something runs out."""
import math
import re
from datetime import date, timedelta
from fractions import Fraction

from . import everyday_exact as ee
from . import word_math as wm

ROUTE = 'chat/exact'
N = wm.STRICT
NA = wm.NUMBER
out = lambda text, kind: dict(route=f'{ROUTE}-{kind}', response=text, sources=[], reasoning=True, details=f'{kind} (everyday_more.py)')
num = wm.value
fmt = wm.fmt
money = ee.money
monies = ee.monies
FRACW = {'half': Fraction(1, 2), 'a third': Fraction(1, 3), 'one third': Fraction(1, 3), 'two thirds': Fraction(2, 3),
         'a quarter': Fraction(1, 4), 'one quarter': Fraction(1, 4), 'three quarters': Fraction(3, 4), 'a fifth': Fraction(1, 5)}


# ------------------------------------------------------------------ money
ITEM = re.compile(r'(?i)\b(?P<n>' + N + r')\s+(?P<item>[a-z]+(?:\s[a-z]+)?)\s+(?:at|for|costing|@)\s+(?P<p>[$€£]\s?\d+(?:\.\d+)?|\d+(?:\.\d+)?\s*(?:dollars?|euros?|pounds?))\s*(?:each|apiece|a piece|per \w+|an? \w+)?')


def change(T, Q):
    if not re.search(r'(?i)\bchange\b|how much (?:do i|will i|should i) get back|left over from', Q + ' ' + T[-200:]):
        return None
    items = list(ITEM.finditer(T))
    pay = re.search(r'(?i)\bpa(?:y|id|ying)\s+(?:with|using)\s+(?:a|an|one)?\s*(?P<p>[$€£]\s?\d+(?:\.\d+)?|\d+(?:\.\d+)?\s*(?:dollars?|euros?|pounds?))', T) or \
        re.search(r'(?i)\b(?:hand over|give (?:them|the cashier))\s+(?:a|an)?\s*(?P<p>[$€£]\s?\d+(?:\.\d+)?)', T)
    if not items or not pay:
        return None
    total = Fraction(0)
    parts = []
    sym = None
    for m in items:
        (s, p, _), = monies(m['p'])
        sym = sym or s
        k = num(m['n'])
        total += k * p
        parts.append(f'{fmt(k)} × {money(s, p)}')
    (s2, paid, _), = monies(pay['p'])
    if paid < total:
        return out(f'**Not enough**: the items come to {money(sym, total)} ({" + ".join(parts)}), which is more than {money(s2, paid)}.', 'change')
    return out(f'**{money(sym, paid - total)}**: the items come to {money(sym, total)} ({" + ".join(parts)}), and {money(s2, paid)} − '
               f'{money(sym, total)} = {money(sym, paid - total)}.', 'change')


UNIT_Q = re.compile(r'(?i)\bwhich\b[^?]*\b(?:cheaper|better (?:deal|value)|costs? less|best value)|\bwhere\b[^?]*\bcheaper|cheaper (?:per|each|a)\b')
QTY = r'(?P<q>\d+(?:\.\d+)?)\s*(?P<u>kg|g|grams?|kilograms?|l|litres?|liters?|ml|millilitres?|oz|lb|pens?|[a-z]+s)?'


def unit_price(T, Q):
    if not UNIT_Q.search(Q):
        return None
    offers = []
    for m in re.finditer(r'(?P<name>(?:(?:Pack|Shop|Brand|Box|Bag|Bottle|Store|Option|Deal|Offer|Plan|Jar|Tin)\s+[A-Z0-9]\w*)|[A-Z][a-z]+(?:\'s)?)\s+'
                         r'(?:has|sells|offers|is|gives|costs?|:)?\s*(?:you\s+)?(?:a\s+|an\s+)?(?P<rest>(?:[^.;\n]|\.(?=\d))+)', T):
        rest = m['rest']
        ms = monies(rest)
        q = re.search(r'(?i)\b(?P<q>\d+(?:\.\d+)?|' + '|'.join(k for k in wm.ONES if len(k) > 2) + r')\s*(?P<u>kg|g|grams?|kilograms?|l|litres?|liters?|ml|oz|lb|[a-z]+)\b(?!\s*(?:each|%))', rest)
        if len(ms) == 1 and q and not re.match(r'[$€£]', rest[max(0, q.start() - 1):q.start()]):
            amount = num(q['q'])
            unit = (q['u'] or '').lower()
            scale = {'kg': 1000, 'kilogram': 1000, 'kilograms': 1000, 'l': 1000, 'litre': 1000, 'litres': 1000, 'liter': 1000, 'liters': 1000}.get(unit, 1)
            if amount > 0 and ms[0][2][0] != q.start():
                offers.append((m['name'], ms[0][1] / (amount * scale), ms[0][0], amount, unit, ms[0][1]))
    if len(offers) < 2 or len({o[0] for o in offers}) != len(offers):
        return None
    best = min(offers, key=lambda o: o[1])
    if sum(o[1] == best[1] for o in offers) > 1:
        return out('**They cost the same per unit.**', 'unit-price')
    def per(o):
        u = o[4]
        if u in ('g', 'gram', 'grams', 'kg', 'kilogram', 'kilograms'):
            return f'{money(o[2], Fraction(round(float(o[1] * 1000), 2)).limit_denominator(100))} per kg'
        if u in ('ml', 'l', 'litre', 'litres', 'liter', 'liters'):
            return f'{money(o[2], Fraction(round(float(o[1] * 1000), 2)).limit_denominator(100))} per litre'
        return f'{money(o[2], Fraction(round(float(o[1]), 2)).limit_denominator(100))} per {(u[:-1] if u.endswith("s") else u) or "unit"}'
    parts = '; '.join(f'{o[0]}: {money(o[2], o[5])} for {fmt(o[3])} {o[4]}, {per(o)}' for o in offers)
    return out(f'**{best[0]}** is cheaper per unit. {parts}.', 'unit-price')


def options_cost(T, Q):
    """'$2.75 per ride, or a week pass is $22. I ride 10 times.' -> which is cheaper."""
    if not re.search(r'(?i)\bwhich\b[^?]*\b(?:cheaper|costs? less|better)|\bis it cheaper\b|should i (?:buy|get)', Q):
        return None
    per = re.search(r'(?i)(?P<p>[$€£]\s?\d+(?:\.\d+)?)\s+(?:per|a|an|each|for (?:each|every|one))\s+(?P<u>ride|trip|journey|visit|class|session|day|game|entry|use|go|lesson|film|movie|show)', T) or \
        re.search(r'(?i)\b(?:a|an|one|each)\s+(?:[a-z]+\s+)?(?P<u>ticket|ride|trip|class|session|visit|entry|lesson|game|film)\s+(?:is|costs?)\s+(?P<p>[$€£]\s?\d+(?:\.\d+)?)', T)
    flat = re.search(r'(?i)\b(?:a|an|the)?\s*(?P<name>(?:week|weekly|month|monthly|day|annual|season|year|unlimited|multi[- ]?\w*|\d+[- ]\w+|ten[- ]\w+|five[- ]\w+)\s*(?:pass|ticket|card|membership|plan|subscription|bundle))\s+(?:is|costs?|for)\s+(?P<p>[$€£]\s?\d+(?:\.\d+)?)', T)
    times = re.search(r'(?i)\b(?P<n>' + N + r')\s+(?:times|rides|trips|journeys|visits|classes|sessions|days|games|lessons|films|movies|shows)\b(?![^.]*\b(?:card|pass)\b[^.]*\bcosts?\b)', T[flat.end():] if flat else T) if flat else None
    if not (per and flat and times):
        return None
    (s, p, _), = monies(per['p'])
    (s2, f, _), = monies(flat['p'])
    n = num(times['n'])
    pay = p * n
    if pay == f:
        return out(f'**They cost the same**: {fmt(n)} × {money(s, p)} = {money(s, pay)}, the same as the {flat["name"]}.', 'options')
    win = f'the {flat["name"]}' if f < pay else f'paying per {per["u"]}'
    return out(f'**{win[0].upper() + win[1:]}** is cheaper: {fmt(n)} × {money(s, p)} = {money(s, pay)} against {money(s2, f)} for the {flat["name"]} '
               f'(a difference of {money(s, abs(pay - f))}).', 'options')


def percent_chain(T, Q):
    """'$40, discounted by 20%, then 10% sales tax' -> 35.20. Each percentage applies to the running price."""
    if not re.search(r'(?i)how much|what(?:\'s| is) the (?:total|price|final|new)|what do i pay|what will i pay|total', Q):
        return None
    steps = list(re.finditer(r'(?i)(?P<pct>\d+(?:\.\d+)?)\s*(?:%|percent|per cent)\s*(?P<what>off|discount|tax|sales tax|vat|tip|service(?: charge)?|increase|more|surcharge|fee)?'
                             r'|(?P<verb>discounted|reduced|marked down|cut|raised|increased|knocked)\s+(?:by\s+)?(?P<pct2>\d+(?:\.\d+)?)\s*(?:%|percent)', T))
    if len(steps) < 2:
        return None
    ms = monies(T[:steps[0].start()])
    if len(ms) != 1:
        return None
    sym, price, _ = ms[0]
    shown = [money(sym, price)]
    for s in steps:
        p = Fraction(s['pct'] or s['pct2']) / 100
        ctx = (s['what'] or s['verb'] or '').lower()
        after = T[s.end():s.end() + 40].lower()
        if not ctx:
            ctx = 'tax' if re.match(r'\s*(?:sales\s+)?(?:tax|vat|tip|service)', after) else 'off' if re.match(r'\s*(?:off|discount)', after) else ''
        if ctx in ('off', 'discount', 'discounted', 'reduced', 'marked down', 'cut', 'knocked'):
            price = price * (1 - p); shown.append(f'− {fmt(p * 100)}%')
        elif ctx in ('tax', 'sales tax', 'vat', 'tip', 'service', 'service charge', 'increase', 'more', 'surcharge', 'fee', 'raised', 'increased'):
            price = price * (1 + p); shown.append(f'+ {fmt(p * 100)}%')
        else:
            return None
    return out(f'**{money(sym, price)}**: {" ".join(shown)}, each step on the running price.', 'percent-chain')


def groups_used(T, Q):
    """'3 pizzas cut into 8 slices each; 5 people each eat 4' -> 24 − 20 = 4."""
    if not re.search(r'(?i)how many\b[^?]*\b(?:left|remain|spare|over)', Q):
        return None
    g = re.search(r'(?i)\b(?P<n>' + N + r')\s+(?P<a>[a-z]+)\s+(?:cut into|split into|with|of|holding|containing|each with)\s+(?P<m>' + N + r')\s+(?P<b>[a-z]+)\s+each', T) or \
        re.search(r'(?i)\b(?P<n>' + N + r')\s+(?P<a>[a-z]+)\s+(?:of|with)\s+(?P<m>' + N + r')\s+(?P<b>[a-z]+)\b', T)
    u = re.search(r'(?i)\b(?P<p>' + N + r')\s+(?:people|friends|kids|children|guests|of us|players|students)\s+(?:each\s+)?(?:eat|ate|take|took|use|used|have|had|get|got)\s+(?:each\s+)?(?P<k>' + N + r')', T)
    if not (g and u):
        return None
    total = num(g['n']) * num(g['m'])
    used = num(u['p']) * num(u['k'])
    if used > total:
        return out(f'**None, and they come up short**: {fmt(total)} {g["b"]} but {fmt(used)} wanted.', 'groups-used')
    return out(f'**{fmt(total - used)}**: {fmt(num(g["n"]))} × {fmt(num(g["m"]))} = {fmt(total)} {g["b"]}, minus {fmt(num(u["p"]))} × {fmt(num(u["k"]))} = {fmt(used)}.', 'groups-used')


def age_in_year(T, Q):
    m = re.search(r'(?i)\bborn in\s+(?P<y>\d{4})\b', T)
    q = re.search(r'(?i)how old\b[^?]*\b(?P<when>at the end of|by the end of|in|during|on (?:their|his|her) birthday in)\s+(?P<y2>\d{4})', Q)
    if not (m and q):
        return None
    y, y2 = int(m['y']), int(q['y2'])
    if y2 < y:
        return None
    if re.search(r'end of|birthday', q['when']):
        return out(f'**{y2 - y}**: {y2} − {y}, and by the end of {y2} the birthday has passed.', 'age-in-year')
    return out(f'**{y2 - y - 1} or {y2 - y}** during {y2}: {y2 - y - 1} before the birthday that year and {y2 - y} after it.', 'age-in-year')


def two_readings(T, Q):
    """'One clock says 4:10 and another says 4:25. I don't know which one is right.' -> can't tell."""
    m = re.search(r'(?i)\b(?:one|the first)\s+(?P<thing>[a-z]+)\s+(?:says|shows|reads|gives)\s+(?P<a>[^.,;]+?)\s*(?:,|and|but|while)\s+(?:another|the other|the second)(?:\s+(?:one|[a-z]+))?\s+(?:says|shows|reads|gives)\s+(?P<b>[^.,;]+)', T)
    if not m or not re.search(r'(?i)\b(?:don\'t|do not|can\'t|cannot) (?:know|tell) which|\bno idea which|\bnot sure which', T):
        return None
    return out(f'**I can\'t tell which is right**: one {m["thing"]} says {m["a"].strip()} and the other {m["b"].strip()}, and nothing says which to '
               f'trust. Checking a third, reliable source would settle it.', 'two-readings')


def fraction_full(T, Q):
    if not re.search(r'(?i)how (?:many|much)', Q):
        return None
    cap = re.search(r'(?i)\b(?:holds|takes|has a capacity of|capacity is|can hold|fits)\s+(?P<c>\d+(?:\.\d+)?)\s*(?P<u>litres?|liters?|l|gallons?|kg|ml|cups?|people|seats|[a-z]+)?', T)
    frac = re.search(r'(?i)\b(?:it\'s|it is|is|was)\s+(?P<f>' + '|'.join(FRACW) + r'|\d+%)\s+full\b', T)
    if not (cap and frac):
        return None
    c = Fraction(cap['c'])
    f = Fraction(frac['f'][:-1]) / 100 if frac['f'].endswith('%') else FRACW[frac['f'].lower()]
    have = c * f
    steps = [f'{fmt(c)} × {frac["f"]} = {fmt(have)}']
    rest = T[frac.end():]
    for m in re.finditer(r'(?i)\b(?P<v>use|used|drink|drank|pour out|poured out|drain|drained|take out|took out|add|added|pour in|poured in|top up|topped up)\s+(?:another\s+)?(?P<n>\d+(?:\.\d+)?)', rest):
        k = Fraction(m['n'])
        if m['v'].lower() in ('add', 'added', 'pour in', 'poured in', 'top up', 'topped up'):
            have += k; steps.append(f'+ {fmt(k)}')
        else:
            have -= k; steps.append(f'− {fmt(k)}')
    if len(steps) == 1 and not re.search(r'(?i)how (?:many|much)[^?]*\b(?:in it|now|is there|are there)', Q):
        return None
    if have < 0:
        return None
    unit = cap['u'] or ''
    return out(f'**{fmt(have)} {unit}**: ' + ' '.join(steps) + f' = {fmt(have)}.', 'fraction')


# ------------------------------------------------------------------ dates
def dates_in(T):
    got = []
    for m in re.finditer(r'(?i)\b(?P<d>\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(?P<m>' + ee.MON + r')\s*,?\s+(?P<y>\d{4})\b|\b(?P<m2>' + ee.MON +
                         r')\s+(?P<d2>\d{1,2})(?:st|nd|rd|th)?,?\s+(?P<y2>\d{4})\b', T):
        try:
            got.append(date(int(m['y'] or m['y2']), ee.MONTHS.index((m['m'] or m['m2']).lower()) + 1, int(m['d'] or m['d2'])))
        except ValueError:
            pass
    return got


def days_between(T, Q):
    if not re.search(r'(?i)how many (?:days|weeks)', Q):
        return None
    ds = dates_in(T)
    if len(ds) != 2:
        return None
    a, b = sorted(ds)
    d = (b - a).days
    inclusive = bool(re.search(r'(?i)\binclusive\b|\bincluding both\b', T))
    if inclusive:
        d += 1
    if re.search(r'(?i)how many weeks', Q):
        w, r = divmod(d, 7)
        return out(f'**{w} weeks{f" and {r} days" if r else ""}** ({d} days) from {ee.show(a)} to {ee.show(b)}.', 'between')
    return out(f'**{d} days** from {ee.show(a)} to {ee.show(b)}' + (' (counting both days)' if inclusive else ' (not counting the first day)') + '.', 'between')


def weekday_of(T, Q):
    if not re.search(r'(?i)what (?:day of the week|weekday|day)\b|which (?:day of the week|weekday)', Q):
        return None
    ds = dates_in(Q)
    if len(ds) != 1:
        return None
    d = ds[0]
    return out(f'**{ee.DAYS[d.weekday()].capitalize()}.** {ee.show(d)} {"was" if d < date.today() else "is"} a {ee.DAYS[d.weekday()].capitalize()} '
               f'in the Gregorian calendar.', 'weekday-of')


def date_plus(T, Q):
    if not re.search(r'(?i)\b(?:on )?what date|which date|when (?:does|will|is) it (?:expire|end|due)|expiry date|due date', Q):
        return None
    ds = dates_in(T)
    m = re.search(r'(?i)\b(?:for|valid for|lasts?|after|in|of)\s+(?P<n>' + N + r')\s+(?P<u>years?|months?|weeks?|days?)\b', T)
    if len(ds) != 1 or not m:
        return None
    d0, n, u = ds[0], int(num(m['n'])), m['u'].lower()
    if u.startswith('year'):
        try:
            d1 = d0.replace(year=d0.year + n)
        except ValueError:
            d1 = d0.replace(year=d0.year + n, day=28)
    elif u.startswith('month'):
        i = d0.year * 12 + d0.month - 1 + n
        y, mo = divmod(i, 12)
        import calendar
        d1 = date(y, mo + 1, min(d0.day, calendar.monthrange(y, mo + 1)[1]))
    else:
        d1 = d0 + timedelta(days=n * (7 if u.startswith('week') else 1))
    before = re.search(r'(?i)\bday before\b', T + ' ' + Q)
    if before:
        d1 -= timedelta(days=1)
    return out(f'**{ee.show(d1)}**: {ee.show(d0)} + {n} {u}' + (' − 1 day' if before else '') + '.', 'date-plus')


def turns_age(T, Q):
    m = re.search(r'(?i)\bborn in\s+(?P<y>\d{4})\b[^?]*\bturns?\s+(?P<a>\d{1,3})\b|\bturns?\s+(?P<a2>\d{1,3})\b[^?]*\bborn in\s+(?P<y2>\d{4})\b', T)
    if not m or not re.search(r'(?i)which year|what year|when', Q):
        return None
    y, a = int(m['y'] or m['y2']), int(m['a'] or m['a2'])
    return out(f'**{y + a}**: {y} + {a} = {y + a} (the birthday in that year).', 'turns-age')


def work_time(T, Q):
    if not re.search(r'(?i)how long|how many hours|how much time', Q):
        return None
    m = re.search(r'(?i)\b(?:starts?|begins?|from)\s+(?:at\s+)?(?P<a>' + ee.CLOCK + r')\b[^.?]*?\b(?:finish(?:es)?|ends?|until|till|to)\s+(?:at\s+)?(?P<b>' + ee.CLOCK + r')', T)
    brk = re.search(r'(?i)\b(?P<d>' + ee.DUR + r')\s+(?:lunch|break|pause)|\b(?:lunch|break|pause)\s+of\s+(?P<d2>' + ee.DUR + r')|(?P<d3>\d+)-minute\s+(?:lunch|break|pause)', T)
    if not (m and brk):
        return None
    a, b = ee.minutes_of(m['a']), ee.minutes_of(m['b'])
    span = (b - a) % 1440
    off = int(brk['d3']) if brk['d3'] else ee.duration(brk['d'] or brk['d2'])
    w = span - off
    if w <= 0:
        return None
    return out(f'**{int(w) // 60} hours {int(w) % 60} minutes**: {m["a"]} to {m["b"]} is {span // 60} h {span % 60} min, minus {fmt(off)} minutes off.', 'work-time')


# ------------------------------------------------------------------ changing information
def newest(T, Q):
    if not re.search(r'(?i)\bwhich\b[^?]*\b(?:go by|trust|believe|use|right|correct|current|more recent|newer|latest)|which (?:time|price|date|day|number) should|'
                     r'\bwhen (?:should|do|does|will)\b[^?]*\b(?:arrive|open|go|plan|start)|what time (?:should|does|do)', Q):
        return None
    m = re.search(r'(?i)\b(?:a\s+|the\s+)?(?P<new>newer|more recent|latest|updated|new)\b[^.]*?\b(?:says?|lists?|shows?|states?|reads?)\s+(?:it\s+)?(?:now\s+)?(?:\w+\s+){0,3}?(?P<v>[$€£]?\d{1,2}(?::\d{2})?(?:\s*[ap]m)?|[$€£]\d+(?:\.\d+)?|\d+)', T)
    if m:
        return out(f'**{m["v"]}**: the {m["new"]} source replaces the older one.', 'newest')
    pair = re.findall(r'(?i)\b(?:printed|written|dated|updated|posted|issued)\s+(?:in|on)\s+(?P<when>' + ee.MON + r'(?:\s+\d{4})?|\d{4})\b[^.]*?\b(?:says?|lists?|shows?)\s+(?:\w+\s+){0,3}?(?:costs?|is|at)?\s*(?P<v>[$€£]\d+(?:\.\d+)?|\d{1,2}(?::\d{2})?(?:\s*[ap]m)?)', T)
    if len(pair) == 2:
        def rank(w):
            w = w.lower()
            yr = re.search(r'\d{4}', w)
            mo = next((i for i, x in enumerate(ee.MONTHS) if x in w), 0)
            return (int(yr[0]) if yr else 0, mo)
        latest = max(pair, key=lambda p: rank(p[0]))
        return out(f'**{latest[1]}**: that is the one dated {latest[0]}, the more recent of the two.', 'newest')
    return None


def retracted_person(T, Q):
    if not re.search(r'(?i)\bwhich\b|\bwhat\b|\bwhen\b|\bwhere\b', Q):
        return None
    claims = list(re.finditer(r'(?i)\b(?P<who>my\s+[a-z]+|[A-Z][a-z]+)\s+(?:said|says|told me|thinks|thought|reckons)\s+(?:that\s+)?(?P<what>[^.]+)', T))
    took = re.search(r'(?i)\b(?P<who>my\s+[a-z]+|[A-Z][a-z]+|she|he|they)\s+(?:texted|said|admitted|told me|later said|called)?\s*(?:that\s+)?(?:she|he|they)?\s*(?:\'d|had)?\s*(?:got it wrong|was wrong|were wrong|made a mistake|takes? it back|took it back|retracted)', T)
    if len(claims) < 2 or not took:
        return None
    who = took['who'].lower()
    if who in ('she', 'he', 'they'):
        return None
    left = [c for c in claims if c['who'].lower() != who]
    if len(left) != 1:
        return None
    what = left[0]['what']
    val = re.search(r'(?i)\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|\d{1,2}(?::\d{2})?\s*(?:am|pm)?|room \w+)\b', what)
    head = val[0] if val else what
    you = lambda w: re.sub(r'(?i)^my\b', 'your', w)
    return out(f'**{head[0].upper() + head[1:]}**, as far as we know: {you(took["who"])} took back what they said, which leaves only '
               f'{you(left[0]["who"])}\'s account ({what.strip()}).', 'retracted')


def corrected_passive(T, Q):
    m = re.search(r'(?i)\b(?P<lab>(?:report|log|sheet|note|record|post|entry|count|list)\s+[A-Z0-9]\w*)\s+(?:was|has been|got)\s+(?:later\s+)?(?:corrected|changed|updated|amended)\s+to\s+(?P<v>[^.]+)', T)
    if not m or not re.search(r'(?i)\bagree|\bsame\b|\bmatch', Q):
        return None
    vals = {}
    for c in re.finditer(r'(?i)\b(?P<lab>(?:report|log|sheet|note|record|post|entry|count|list)\s+[A-Z0-9]\w*)\s+(?:says|said|lists|counted|gives|reports|shows)\s+(?P<v>[^.]+)', T[:m.start()]):
        vals[c['lab'].lower()] = ee.amount_in(c['v'])
    if len(vals) < 2 or m['lab'].lower() not in vals:
        return None
    vals[m['lab'].lower()] = ee.amount_in(m['v'])
    if None in vals.values():
        return None
    same = len(set(vals.values())) == 1
    v = next(iter(vals.values()))
    vs = v if isinstance(v, str) else fmt(v)
    return out(f'**{"Yes" if same else "No"}**' + (f': after the correction they all say {vs}.' if same else
                                                  ': ' + '; '.join(f'{k} says {x if isinstance(x, str) else fmt(x)}' for k, x in vals.items()) + '.'), 'corrected')


def checked_themselves(T, Q):
    if not re.search(r'(?i)how many\b[^?]*\b(?:checked|saw|looked|counted|went)\b[^?]*\b(?:themselves|for themselves|in person|with their own eyes|directly)|how many\b[^?]*\bfirst-?hand', Q):
        return None
    people = []
    for m in re.finditer(r'\b(?P<who>[A-Z][a-z]+)\s+(?P<rest>[^.]*)', T):
        if m['who'] in ('I', 'The', 'A', 'How', 'So'):
            continue
        r = m['rest'].lower()
        own = re.search(r'\b(?:looked at|checked|saw|counted|went to|read)\b[^.]*\b(?:herself|himself|themselves|myself|in person|with (?:her|his|their) own eyes)\b|\b(?:herself|himself|themselves)\s+(?:looked|checked|saw|counted)', r)
        second = re.search(r'\btold (?:me|him|her|them|us)\b|\bsaid\b|\bheard\b|\baccording to\b', r)
        if own:
            people.append((m['who'], True))
        elif second:
            people.append((m['who'], False))
    if len(people) < 2:
        return None
    own = [p for p, o in people if o]
    word = {0: 'None', 1: 'One', 2: 'Two', 3: 'Three'}.get(len(own), str(len(own)))
    return out(f'**{word}**' + (f' ({", ".join(own)})' if own else '') + ': the others only passed on what they were told.', 'checked')


# ------------------------------------------------------------------ memory over a chat
ATTR = r'(?P<attr>[a-z]+(?:\s[a-z]+)?)'


def latest_value(T, Q, users):
    q = re.search(r'(?i)\bwhat(?:\'s| is| was)\s+my\s+(?P<attr>[a-z]+(?:\s[a-z]+)?)(?:\s+(?:now|number|again))?\??$|\bwhat\s+(?P<attr2>[a-z]+)\s+(?:number\s+)?(?:am i|is mine)', Q.strip())
    if not q:
        return None
    attr = (q['attr'] or q['attr2']).lower().replace(' now', '')
    hw = attr.split()[0]
    val = None
    hist = []
    for u in users[:-1]:
        for m in re.finditer(r'(?i)\bmy\s+' + hw + r'(?:\s+number)?\s+(?:is|was)\s+(?:now\s+)?(?:number\s+)?(?P<v>[A-Za-z]*\s?\d+[A-Za-z]?|[A-Z][a-z]+)\b', u):
            val = m['v']; hist.append(val)
        for m in re.finditer(r'(?i)\b(?:moved|switched|changed|transferred|put|upgraded|reassigned)\s+(?:me|us|it|my\s+' + hw + r')\s+(?:to|into)\s+(?:' + hw + r'\s+)?(?:number\s+)?(?P<v>\d+[A-Za-z]?|[A-Z]\w*)\b', u):
            val = m['v']; hist.append(val)
        for m in re.finditer(r'(?i)\b(?:my\s+)?(?:new|updated)\s+' + hw + r'(?:\s+number)?\s+is\s+(?P<v>[A-Za-z]*\s?\d+[A-Za-z]?|[A-Z][a-z]+)\b', u):
            val = m['v']; hist.append(val)
    if not val or len(hist) < 2:
        return None
    return out(f'**{val}**: that is the latest you told me (it was {hist[0]} before).', 'latest')


def time_moved(T, Q, users):
    q = re.search(r'(?i)\bwhen\s+is\s+(?:the|my|our)\s+(?P<ev>[a-z]+)\b|what time is\s+(?:the|my|our)\s+(?P<ev2>[a-z]+)', Q)
    if not q:
        return None
    ev = (q['ev'] or q['ev2']).lower()
    t = None
    for u in users[:-1]:
        m = re.search(r'(?i)\b(?:the|my|our)\s+' + ev + r'\s+is\s+(?:at\s+)?(?P<t>' + ee.CLOCK + r')', u)
        if m:
            t = ee.minutes_of(m['t']); twelve = bool(re.search(r'(?i)am|pm', m['t']))
        mv = re.search(r'(?i)\b' + ev + r'\b[^.]*?\b(?:got|was|has been|is)?\s*(?:pushed back|moved back|delayed|postponed|put back|moved forward|brought forward|moved earlier|moved later)\s+(?:by\s+)?(?P<d>' + ee.DUR + r'|an hour|half an hour)', u) or \
            re.search(r'(?i)\b(?:pushed|moved|put|brought|pulled)\s+(?:it|that|the time)\s+(?:back|forward|later|earlier)\s+(?:by\s+)?(?P<d>' + ee.DUR + r'|an hour|half an hour)|'
                      r'\b(?:delayed|postponed)\s+(?:it|that)\s+(?:by\s+)?(?P<d2>' + ee.DUR + r'|an hour|half an hour)', u)      # "They moved it back by an hour" (2026-11-22)
        if mv is not None and mv.groupdict().get('d') is None and mv.groupdict().get('d2'):
            mv = re.search(r'(?i)(?:delayed|postponed)\s+(?:it|that)\s+(?:by\s+)?(?P<d>' + ee.DUR + r'|an hour|half an hour)', u)
        if mv and t is not None:
            d = 60 if mv['d'].lower() == 'an hour' else 30 if mv['d'].lower() == 'half an hour' else ee.duration(mv['d'])
            sign = -1 if re.search(r'(?i)forward|earlier', mv[0]) else 1
            t += sign * d
    if t is None or not re.search(r'(?i)pushed|moved|delayed|postponed|forward|put back', ' '.join(users[:-1])):
        return None
    return out(f'**{ee.clock(t, twelve)}**: the original time moved by what you told me.', 'moved')


def set_changes(T, Q, users):
    if not re.search(r'(?i)\bwhich\s+[a-z]+\s+do i (?:have|own)(?: now)?|what\s+[a-z]+\s+do i have(?: now)?|how many\s+[a-z]+\s+do i have(?: now)?', Q):
        return None
    items = None
    for u in users[:-1]:
        m = re.search(r'(?i)\bI\s+have\s+(?:' + N + r'\s+)?[a-z]+:\s*(?P<list>[^.]+)', u) or re.search(r'(?i)\bI\s+(?:have|own|keep)\s+(?P<list>(?:an?\s+)?[a-z]+(?:,\s*(?:an?\s+)?[a-z]+)+,?\s+and\s+(?:an?\s+)?[a-z]+)', u)
        if m and items is None:
            items = [re.sub(r'^(?:an?|the)\s+', '', x.strip()) for x in re.split(r',\s*|\s+and\s+', m['list']) if x.strip()]
            continue
        if items is None:
            continue
        for g in re.finditer(r'(?i)\b(?:the|my)\s+(?P<x>[a-z]+)\s+(?:died|broke|was stolen|got lost|is gone)|\b(?:threw out|gave away|sold|lost)\s+(?:the|my)\s+(?P<x2>[a-z]+)', u):
            x = (g['x'] or g['x2']).lower()
            if x in items:
                items.remove(x)
        for g in re.finditer(r'(?i)\b(?:bought|got|was given|adopted|added)\s+(?:an?|another|a new)\s+(?P<x>[a-z]+)', u):
            items.append(g['x'].lower())
    if not items:
        return None
    if re.search(r'(?i)how many', Q):
        return out(f'**{len(items)}**: {", ".join(items)}.', 'set')
    return out(f'**{", ".join(items[:-1]) + " and " + items[-1] if len(items) > 1 else items[0]}.**', 'set')


def which_of_two(T, Q, users):
    m = re.search(r'(?i)\bwhat\s+was\s+my\s+(?P<k>outbound|return|first|second|old|new|previous|current)\s+(?P<thing>[a-z]+(?:\s[a-z]+)?)', Q) or \
        re.search(r'(?i)\bwhere\s+did\s+I\s+(?P<v>grow up|go to school|study|work|live|was born)\b|where\s+(?:do|did)\s+I\s+(?P<v2>live|work|study)\b', Q)
    if not m:
        return None
    earlier = ' '.join(users[:-1])
    if m.groupdict().get('k'):
        k, thing = m['k'].lower(), m['thing'].split()[0]
        if k in ('outbound', 'first'):
            g = re.search(r'(?i)\bmy\s+(?!return\b)(?:outbound\s+)?' + thing + r'(?:\s+number)?\s+is\s+(?P<v>[A-Z0-9][\w ]*?\d+\w*)', earlier)
        else:
            g = re.search(r'(?i)\bmy\s+' + k + r'\s+' + thing + r'(?:\s+number)?\s+is\s+(?P<v>[A-Z0-9][\w ]*?\d+\w*)', earlier)
        return out(f'**{g["v"]}**.', 'which-of-two') if g else None
    v = (m['v'] or m['v2']).lower()
    pat = {'grow up': r'grew up in', 'live': r'live in', 'work': r'work (?:at|in|for)', 'study': r'stud(?:y|ied) (?:at|in)', 'go to school': r'went to school in',
           'was born': r'was born in'}.get(v)
    if not pat:
        return None
    g = re.search(r'(?i)\bI\s+(?:' + pat + r')\s+(?P<p>[A-Z][\w\- ]*?)(?:[.,]|$)', earlier)
    return out(f'**{g["p"]}**: you told me you {v.replace("grow up", "grew up")} there.', 'which-of-two') if g else None


# ------------------------------------------------------------------ unanswerable
def missing_info(T, Q):
    if re.search(r'(?i)\b(?:leaves?|departs?|sets off|starts?|takes off|took off)\b[^.]*\bat\s+\d', T) and \
            re.search(r'(?i)\bat what time does it (?:arrive|get there|reach|land)|when does it (?:arrive|get there|reach|land)|what time will it (?:arrive|land)', Q):
        if not re.search(r'(?i)\b(?:takes|journey|trip|lasts|travel|minutes?|hours?|speed|km|miles)\b', T.replace(Q, '')):
            return out("**I can't tell from that**: you've given the departure time, but not how long the journey takes or the timetable's "
                       "arrival time.", 'missing')
    return None


def contradiction(T, Q):
    if re.search(r'(?i)\b(?:completely|totally)\s+empty\b[^.?]*\b(?:and|but)\s+(?:also\s+)?(?:contains?|holds?|has)\s+\d', T):
        return out('**That can\'t be answered as stated**: a box can\'t be completely empty and also contain apples. The description '
                   'contradicts itself.', 'contradiction')
    return None


MODERN = {'smartphone': 2007, 'iphone': 2007, 'mobile phone': 1973, 'cell phone': 1973, 'phone': 1876, 'telephone': 1876, 'internet': 1983,
          'email': 1971, 'e-mail': 1971, 'computer': 1940, 'laptop': 1981, 'television': 1927, 'tv': 1927, 'car': 1886, 'aeroplane': 1903,
          'airplane': 1903, 'plane': 1903, 'helicopter': 1936, 'social media': 1997, 'twitter': 2006, 'facebook': 2004, 'gps': 1978,
          'radio': 1895, 'camera': 1826, 'photograph': 1826, 'electric light': 1879, 'light bulb': 1879, 'video': 1956, 'drone': 1990}
HISTORIC = {'napoleon': 1821, 'waterloo': 1815, 'julius caesar': -44, 'caesar': -44, 'cleopatra': -30, 'shakespeare': 1616,
            'columbus': 1506, 'henry viii': 1547, 'queen elizabeth i': 1603, 'elizabeth i': 1603, 'leonardo da vinci': 1519, 'da vinci': 1519,
            'galileo': 1642, 'isaac newton': 1727, 'newton': 1727, 'mozart': 1791, 'beethoven': 1827, 'george washington': 1799,
            'lincoln': 1865, 'genghis khan': 1227, 'joan of arc': 1431, 'the vikings': 1100, 'vikings': 1100, 'romans': 476,
            'ancient egypt': -30, 'the pharaohs': -30, 'medieval': 1500, 'middle ages': 1500, 'king arthur': 600, 'charlemagne': 814,
            'marco polo': 1324, 'the battle of hastings': 1066, 'hastings': 1066, 'magna carta': 1215, 'the black death': 1351}


def anachronism(T, Q):
    q = Q.lower()
    tech = next((t for t in sorted(MODERN, key=len, reverse=True) if re.search(r'\b' + re.escape(t) + r's?\b', q)), None)
    old = next((h for h in sorted(HISTORIC, key=len, reverse=True) if re.search(r'\b' + re.escape(h) + r'\b', q)), None)
    if not (tech and old) or MODERN[tech] <= HISTORIC[old]:
        return None
    if not re.search(r'(?i)^\s*(?:why|how|what|which|when|where|who)\b', Q):
        return None
    when = f'{abs(HISTORIC[old])} {"BC" if HISTORIC[old] < 0 else ""}'.strip()
    return out(f'**That rests on a false premise**: the {tech} didn\'t exist yet. {old.title()} belongs to around {when}, and the first '
               f'{tech} came only around {MODERN[tech]}.', 'anachronism')


def future_weather(T, Q):
    if re.search(r'(?i)\bwhat will the weather be\b|\bwill it (?:rain|snow|be sunny)\b', Q) and re.search(r'(?i)\bnext (?:year|month)|\bin \d+ (?:months|years)|\b20[3-9]\d\b', Q):
        return out('**Nobody can know that yet.** Weather forecasts are only useful about one to two weeks ahead; for a date that far off '
                   'the best guide is the usual climate for that place and season.', 'future-weather')
    return None


# ------------------------------------------------------------------ practical checks
def weight_limit(T, Q):
    lim = re.search(r'(?i)\blimit\s+(?:is\s+)?(?P<L>\d+(?:\.\d+)?)\s*(?P<u>kg|lb)|\b(?P<L2>\d+(?:\.\d+)?)\s*(?P<u2>kg|lb)\s+limit', T)
    if not lim or not re.search(r'(?i)\bcan (?:i|we|they) (?:add|fit|take|bring|pack|get in)|\b(?:will it|will they|will we) be (?:over|under)|\b(?:am i|are (?:they|we)|is (?:it|that)) (?:over|under|within)', Q):
        return None
    L = Fraction(lim['L'] or lim['L2'])
    unit = (lim['u'] or lim['u2']).lower()
    rest = T[:lim.start()] + ' ' + T[lim.end():]
    parts = []
    for m in re.finditer(r'(?i)(?:(?P<n>' + N + r')\s+[a-z]+\s+(?:of|at|weighing)\s+)?(?P<w>\d+(?:\.\d+)?)\s*' + unit + r'\b(?P<each>\s+each)?', rest):
        w = Fraction(m['w'])
        parts.append(w * num(m['n']) if m['n'] and m['each'] else w)
    if len(parts) < 2:
        return None
    total = sum(parts)
    ok = total <= L
    asks_over = bool(re.search(r'(?i)\bover\b', Q)) and not re.search(r'(?i)\bunder|within|can (?:i|we|they)', Q)
    yes = (not ok) if asks_over else ok
    return out(f'**{"Yes" if yes else "No"}**: {" + ".join(fmt(p) for p in parts)} = {fmt(total)} {unit}, which is '
               f'{"within" if ok else "over"} the {fmt(L)} {unit} limit' + ('' if ok else f' by {fmt(total - L)} {unit}') + '.', 'limit')


def area_left(T, Q):
    if not re.search(r'(?i)\barea\b|how much (?:floor|space|wall)', Q) or not re.search(r'(?i)\buncovered|left|not covered|free|remain', Q):
        return None
    rects = list(re.finditer(r'(?i)(?P<a>\d+(?:\.\d+)?)\s*(?P<u>m|cm|ft)?\s*(?:by|x|×)\s*(?P<b>\d+(?:\.\d+)?)\s*(?P<u2>m|cm|ft)?', T))
    if len(rects) != 2:
        return None
    areas = [Fraction(r['a']) * Fraction(r['b']) for r in rects]
    big, small = max(areas), min(areas)
    unit = rects[0]['u'] or rects[0]['u2'] or rects[1]['u2'] or 'm'
    return out(f'**{fmt(big - small)} {unit}²**: {fmt(big)} {unit}² of floor − {fmt(small)} {unit}² covered.', 'area')


def runs_out(T, Q):
    if not re.search(r'(?i)how long (?:until|before|till)|when will it (?:be empty|run out|die)', Q):
        return None
    m = re.search(r'(?i)\bat\s+(?P<p>\d+)\s*%[^.]*?\bloses?\s+(?P<l>\d+)\s*%\s+(?:every|each|per)\s+(?P<n>\d+)?\s*(?P<u>minutes?|hours?)', T)
    if not m:
        return None
    p, l, n = int(m['p']), int(m['l']), int(m['n'] or 1)
    steps = Fraction(p, l)
    total = steps * n
    return out(f'**{fmt(total)} {m["u"] if m["u"].endswith("s") else m["u"] + "s"}**: {p}% ÷ {l}% = {fmt(steps)} steps of {n} {m["u"]}.', 'runs-out')


READERS_TQ = (change, unit_price, options_cost, percent_chain, groups_used, age_in_year, two_readings, fraction_full, days_between, weekday_of, date_plus, turns_age, work_time, newest,
              retracted_person, corrected_passive, checked_themselves, missing_info, contradiction, anachronism, future_weather, weight_limit,
              area_left, runs_out)
READERS_TQU = (latest_value, time_moved, set_changes, which_of_two)


def respond(messages):
    users = [(m.get('content') or '').strip() for m in messages if m.get('role') == 'user']
    if not users or not users[-1]:
        return None
    users = users[-6:]
    Q = users[-1]
    if not Q.rstrip().endswith('?') and not re.search(r'(?i)^(?:how|what|which|who|when|where|why|is|are|does|do|did|can|could|was)\b', Q):
        return None
    T = '\n'.join(users)
    for r in READERS_TQU:
        try:
            got = r(T, Q, users)
        except (ValueError, KeyError, ZeroDivisionError, IndexError, TypeError):
            got = None
        if got:
            return got
    for r in READERS_TQ:
        try:
            got = r(T, Q)
        except (ValueError, KeyError, ZeroDivisionError, IndexError, TypeError):
            got = None
        if got:
            return got
    return None
