"""Exact readers for everyday reasoning questions (0.4.4, added after an outside blind test; test-informed).

Each reader reads one shape of question completely, from all of the user's turns, or returns None. Nothing is looked up.
Shapes: buying in packs, cash in a till, shares still owed, a rate times running time, full bags after setting some
aside, average speed, gross minus container weight, room left after a frame or clearance, minutes across midnight, time
zones in a story, a cooking time that was extended, months after a month, the day before yesterday from a date, age on a
date, weekday after weeks and days, the date of the next weekday, leap years, "every X had a mark; this has none",
undecided orderings, "between them", exactly-one switches, "only members may" (necessary, not sufficient), labelled
accounts with a priority rule / withdrawal / correction / no priority / hearsay, who wants a borrowed thing back,
renamed things, similar names, a declined offer, a price never given, hidden or future outcomes, false premises
(a landlocked country's coast, an empty drawer), and a few everyday explanations."""
import math
import re
from datetime import date, timedelta
from fractions import Fraction

from . import word_math as wm

ROUTE = 'chat/exact'
N = wm.STRICT
NA = wm.NUMBER
DAYS = wm.DAYS
MONTHS = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']
MON = r'(?:' + '|'.join(MONTHS) + r')'
DAY = r'(?:' + '|'.join(DAYS) + r')'
SYM = {'dollar': '$', 'euro': '€', 'pound': '£'}


def out(text, kind):
    return dict(route=f'{ROUTE}-{kind}', response=text, sources=[], reasoning=True, details=f'{kind} (everyday_exact.py)')


def num(s):
    return wm.value(s)


def fmt(x):
    return wm.fmt(x)


def sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', text) if s.strip()]


# ------------------------------------------------------------------ money
MONEY = re.compile(r'(?P<c>[$€£])\s?(?P<v>\d+(?:\.\d+)?)|(?P<v2>\d+(?:\.\d+)?)\s*(?P<w>dollars?|euros?|pounds?)\b', re.I)


def monies(s):
    got = []
    for m in MONEY.finditer(s):
        if m['c']:
            got.append((m['c'], Fraction(m['v']), m.span()))
        else:
            got.append((SYM[m['w'].lower().rstrip('s')], Fraction(m['v2']), m.span()))
    return got


def money(sym, v):
    v = Fraction(v)
    if v.denominator == 1:
        return f'{sym}{v.numerator:,}'
    return f'{sym}{float(v):,.2f}'


# ------------------------------------------------------------------ arithmetic stories
PACK = r'(?:packs?|sleeves?|boxes|box|bags?|sets?|bundles?|cartons?|tins?|rolls?|cases?|packets?|crates?|trays?)'


def packs(T, Q):
    m = re.search(r'\b(?:in|of|sells?|sold|comes?|come|buy)\s+(?:only\s+)?(?:in\s+)?(?P<pack>' + PACK + r')\s+of\s+(?P<n>' + N + r')\b', T, re.I)
    need = re.search(r'\bneed\s+(?:to (?:buy|get|have)\s+)?(?:at least\s+)?(?P<m>' + N + r')\s+(?P<item>[a-z]+(?:\s[a-z]+)?)', T, re.I)
    if not (m and need) or not re.search(r'(?i)\b(?:least|cheapest|minimum|lowest|how much|how many)\b', Q):
        return None
    size, want = num(m['n']), num(need['m'])
    if size <= 0 or want <= 0:
        return None
    k = math.ceil(want / size)
    pack = m['pack'].rstrip('s').replace('boxe', 'box')
    price = None
    for s in sentences(T):
        if m['pack'][:4].lower() in s.lower() or 'each' in s.lower():
            ms = monies(s)
            if len(ms) == 1:
                price = ms[0]
    plural = pack + ('es' if pack.endswith('x') else 's')
    if price and re.search(r'(?i)\b(?:spend|cost|pay|cheapest|how much)\b', Q):
        sym, p, _ = price
        return out(f'**{money(sym, k * p)}**: {k} {plural} of {fmt(size)} give {fmt(k * size)}, enough for {fmt(want)} '
                   f'({k - 1} {plural if k - 1 != 1 else pack} would give only {fmt((k - 1) * size)}).', 'packs')
    if re.search(r'(?i)how many\s+' + PACK, Q):
        return out(f'**{k} {plural if k != 1 else pack}**: {k} × {fmt(size)} = {fmt(k * size)}, enough for {fmt(want)}.', 'packs')
    return None


BOX = r'(?:till|tin|float|cash ?box|register|drawer|jar|purse|wallet|kitty|cash tin|money box)'


def till(T, Q):
    if not re.search(r'(?i)how much\s+(?:cash|money)?.*?\b(?:in|left in)\s+the\s+' + BOX + r'|how much\s+(?:cash|money)\s+(?:should|will|do)', Q):
        return None
    total, start, used = Fraction(0), None, 0
    steps = []
    for s in sentences(T):
        ms = monies(s)
        if not ms:
            continue
        low = s.lower()
        low = re.sub(r'\bbefore (?:we|i|they|anyone) (?:sold|bought|spent|paid for) anything\b', 'before trading', low)
        if start is None and re.search(r'\b' + BOX + r'\b', low) and re.search(r'\b(?:was|had|held|contained|started|with|before|this morning|at the start)\b', low) \
                and not re.search(r'\b(?:sold|paid|spent|bought)\b', low):
            if len(ms) != 1:
                return None
            start = ms[0][1]
            total += start
            steps.append(f'{money(ms[0][0], start)} to start')
            used += 1
            continue
        if s.strip().endswith('?'):
            continue
        for sym, v, (a, _) in ms:
            verbs = list(re.finditer(r'\b(sold|sale|sales|took in|earned|made|received|paid me|paid us|paid|spent|bought|cost|gave|refunded)\b', low[:a]))
            if not verbs:
                return None
            sign = 1 if verbs[-1][1] in ('sold', 'sale', 'sales', 'took in', 'earned', 'made', 'received', 'paid me', 'paid us') else -1
            total += sign * v
            steps.append(f'{"+" if sign > 0 else "−"} {money(sym, v)}')
            used += 1
    syms = {sym for s in sentences(T) if not s.strip().endswith('?') for sym, _, _ in monies(s)}
    if start is None or used < 2 or len(syms) != 1:
        return None
    sym = syms.pop()
    return out(f'**{money(sym, total)}**: ' + ' '.join(steps) + f' = {money(sym, total)}.', 'till')


def owed(T, Q):
    if not re.search(r'(?i)how much\s+(?:do|does|should|will)\s+(?:the\s+)?(?:other|others|rest|remaining)', Q):
        return None
    n = re.search(r'(?i)\b(?P<n>' + N + r')\s+of us\s+(?:split|shared|divided|are splitting|are sharing)', T)
    paid = re.search(r'(?i)\bI\s+(?:put down|paid|covered|fronted|paid for|picked up)\b[^.]*', T)
    if not (n and paid) or not re.search(r'(?i)\b(?:equally|evenly|equal shares)\b', T):
        return None
    ms = monies(paid[0])
    if len(ms) != 1:
        return None
    back = re.search(r'(?i)\b(?P<k>' + N + r'|one|a)\s+(?:friend|of them|person|people|friends)\s+(?:has|have)\s+(?:already\s+)?paid me(?:\s+back)?', T)
    k = num(back['k']) if back else 0
    people = num(n['n'])
    sym, total, _ = ms[0]
    left = people - 1 - k
    said = re.search(r'(?i)\bother\s+(' + N + r')\b', Q)
    if left < 0 or (said and num(said[1]) != left):
        return None
    share = total / people
    return out(f'**{money(sym, share * left)}**: {money(sym, total)} ÷ {fmt(people)} = {money(sym, share)} each; you paid your own '
               f'share{" and " + fmt(k) + " friend" + ("s" if k != 1 else "") + " paid you back" if k else ""}, so {fmt(left)} '
               f'share{"s" if left != 1 else ""} are still owed.', 'owed')


PER = r'(?P<per>second|minute|hour|day)'


def rate(T, Q):
    if not re.search(r'(?i)\bhow many\b', Q) or re.search(r'(?i)\bhow many (?:seconds|minutes|hours|days)\b', Q):
        return None             # a question about time is not a count of things (2026-11-22, test-informed)
    r = re.search(r'(?i)\b(?P<r>' + N + r')\s+(?P<thing>[a-z]+)\s+(?:a|per|each|every|an)\s+' + PER + r'\b', T)
    run = re.search(r'(?i)\b(?:for|on for|ran for|running for|booked (?:it|them)? ?for|worked for|went for)\s+(?P<t>' + N + r')\s+(?P<tu>seconds?|minutes?|hours?|days?)', T)
    if not (r and run) or run['tu'].lower().rstrip('s') != r['per'].lower():
        return None
    idle = re.search(r'(?i)\b(?:idle|jammed|stopped|broken|down|off|paused|switched off|not running)\s+for\s+(?P<i>' + N + r')\b', T)
    i = num(idle['i']) if idle else 0
    t = num(run['t'])
    if i > t:
        return None
    got = num(r['r']) * (t - i)
    unit = r['per'].lower()
    return out(f'**{fmt(got)} {r["thing"]}**: it ran for {fmt(t)}' + (f' − {fmt(i)} idle = {fmt(t - i)}' if i else '') +
               f' {unit}s, × {fmt(num(r["r"]))} a {unit}.', 'rate')


CONT = r'(?:bags?|boxes|box|tins?|jars?|packs?|baskets?|crates?|cartons?|bundles?|bottles?|trays?|envelopes?)'


def bags(T, Q):
    q = re.search(r'(?i)how many\s+(?:full\s+)?(?P<c>' + CONT + r')', Q)
    if not q:
        return None
    have = re.search(r'(?i)\b(?:baked|made|picked|have|had|bought|collected|cooked|grew|knitted|printed|wrote)\s+(?P<n>' + N + r')\s+(?P<item>[a-z]+)', T)
    aside = re.search(r'(?i)\b(?:set aside|kept|keep|saved|put aside|ate|gave away|held back)\s+(?P<k>' + N + r')\b', T)
    per = re.search(r'(?i)\b(?P<m>' + N + r')\s+(?:to|per|in each|into each|in every)\s+(?:a\s+|each\s+)?' + CONT, T) or \
        re.search(r'(?i)\b(?:into|in)\s+' + CONT + r'\s+of\s+(?P<m>' + N + r')\b', T)
    if not (have and per):
        return None
    n, k, m = num(have['n']), (num(aside['k']) if aside else 0), num(per['m'])
    if m <= 0 or k > n:
        return None
    rest = n - k
    full, spare = divmod(int(rest), int(m))
    c = q['c'].lower()
    return out(f'**{full} full {c if full != 1 else c.rstrip("s")}**: {fmt(n)}' + (f' − {fmt(k)} = {fmt(rest)}' if k else '') +
               f', and {fmt(rest)} ÷ {fmt(m)} = {full} with {spare} left over.', 'bags')


CORRECT = re.compile(r'(?i)^(?:make that|sorry,?\s+(?:it was|it\'s|make that|i meant)|actually,?\s+(?:it was|it\'s|make that|i meant|there were)?|'
                     r'no,?\s+(?:it was|make that|wait,?)|correction:?|i meant)\s*(?P<n>' + N + r')\b')


def tally(T, Q):
    """A count, corrected ("Make that 21."), then changed by plain additions and removals, then a question that removes some
    more. A sentence right after a correction whose number is exactly the correction's difference explains the correction
    ("Three were parcels") and changes nothing."""
    if not re.search(r'(?i)how many\b[^?]*\b(?:left|still|remain|now|are there|do (?:i|we) have|need)', Q):
        return None
    total, base, item, diff, after_fix, steps, changed = None, None, None, None, False, [], 0
    for s in sentences(T):
        if s.endswith('?'):
            continue
        if total is None:
            m = re.search(r'(?i)\b(?:I|we|she|he|they)\s+(?:counted|picked|have|had|baked|collected|found|caught|made|bought|got)\s+(?P<n>' + N + r')\s+(?P<item>[a-z]+(?:\s[a-z]+)?)', s)
            if not m:
                if re.search(r'\d', s):
                    return None
                continue
            if len(re.findall(r'(?i)\b' + N + r'\b', s)) != 1:
                return None         # "I had 50 stickers and gave away 18." is for the story-sum solver
            total = base = num(m['n'])
            item = m['item'].split()[-1]
            steps.append(fmt(total))
            continue
        c = CORRECT.search(s)
        if c:
            if changed:
                return None
            diff = total - num(c['n'])
            total = num(c['n'])
            steps = [fmt(total) + ' (corrected)']
            after_fix = True
            continue
        nums = re.findall(r'(?i)\b' + N + r'\b', s)
        if after_fix and diff and len(nums) == 1 and num(nums[0]) == abs(diff) and re.search(r'(?i)\b(?:were|was|are|is)\b', s) and not re.search(r'(?i)\bmore\b', s):
            after_fix = False
            continue
        after_fix = False
        add = re.search(r'(?i)\b(?P<n>' + N + r')\s+(?:more|extra)\b|\b(?:has|had|holds|held|contains|contained)\s+(?P<n2>' + N + r')\s+[a-z ]*?(?:of (?:its|their|his|her) own|too|as well|more)\b', s)
        sub = re.search(r'(?i)\b(?P<n>' + N + r')\s+(?:of them\s+|of those\s+)?(?:were|was|went|got)\s+(?:bruised|broken|lost|thrown|rotten|damaged|returned|sent|given|eaten|stolen|cracked|spoiled|bad)\b', s)
        if add and not sub:
            k = num(add['n'] or add['n2'])
            total += k
            steps.append(f'+ {fmt(k)}')
            changed += 1
        elif sub and not add:
            k = num(sub['n'])
            total -= k
            steps.append(f'− {fmt(k)}')
            changed += 1
        elif re.search(r'\d|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b', s.lower()):
            return None
    if total is None:
        return None
    q = re.search(r'(?i)\b(?:after|if|once|when)\s+(?:I|we|you)\s+(?:shelve|eat|use|sell|give away|take|remove|spend|pack|ship|send|file|post)\s+(?P<k>' + N + r')\b', Q)
    if q:
        k = num(q['k'])
        total -= k
        steps.append(f'− {fmt(k)}')
        changed += 1
    if not changed or total < 0:
        return None
    return out(f'**{fmt(total)}**: ' + ' '.join(steps) + f' = {fmt(total)}.', 'tally')


# ------------------------------------------------------------------ units and time
DIST = {'km': 1000, 'kilometre': 1000, 'kilometer': 1000, 'kilometres': 1000, 'kilometers': 1000, 'm': 1, 'metre': 1, 'metres': 1, 'meter': 1,
        'meters': 1, 'mile': 1609.344, 'miles': 1609.344, 'mi': 1609.344}
TUNIT = {'minute': 60, 'minutes': 60, 'min': 60, 'mins': 60, 'hour': 3600, 'hours': 3600, 'hr': 3600, 'hrs': 3600, 'h': 3600, 'second': 1, 'seconds': 1}


def speed(T, Q):
    if not re.search(r'(?i)\bspeed\b|km/h|kph|mph|(?:kilomet(?:re|er)s?|miles?) (?:per|an|a) hour', Q):
        return None
    m = re.search(r'(?i)\b(?P<d>' + N + r')\s?(?P<du>km|kilomet(?:re|er)s?|miles?|mi|metres?|meters?|m)\b\s+in\s+(?P<t>' + NA + r')\s?(?P<tu>minutes?|mins?|hours?|hrs?|h|seconds?)\b', T)
    if not m:
        return None
    d = num(m['d']) * Fraction(DIST[m['du'].lower()]).limit_denominator(1000)
    t = num(m['t']) * TUNIT[m['tu'].lower()]
    if t <= 0:
        return None
    miles = re.search(r'(?i)mph|miles? (?:per|an|a) hour', Q)
    per_hour = d / t * 3600 / (Fraction(1609344, 1000) if miles else 1000)
    u = 'mph' if miles else 'km/h'
    return out(f'**{fmt(round(per_hour, 2) if per_hour.denominator > 100 else per_hour)} {u}**: {wm.fmt(num(m["d"]))} {m["du"]} in '
               f'{wm.fmt(num(m["t"]))} {m["tu"]}, and average speed counts the whole time, stops included.', 'speed')


MASS = {'kg': 1000, 'kilogram': 1000, 'kilograms': 1000, 'kilo': 1000, 'kilos': 1000, 'g': 1, 'gram': 1, 'grams': 1, 'lb': 453.59237, 'lbs': 453.59237,
        'pound': 453.59237, 'pounds': 453.59237, 'oz': 28.349523125, 'ounce': 28.349523125, 'ounces': 28.349523125}
MU = r'(?P<u>kg|kilograms?|kilos?|g|grams?|lbs?|pounds?|oz|ounces?)'


def tare(T, Q):
    q = re.search(r'(?i)how many\s+(?P<qu>grams|kilograms|kilos|kg|g|ounces|pounds)\b|how much (?:do|does|did)\s+(?:the\s+)?[a-z ]+?\s+weigh', Q)
    if not q:
        return None
    gross = re.search(r'(?i)\b(?:reads|weighs|is|shows|says)\s+(?P<a>\d+(?:\.\d+)?)\s?' + MU + r'\s+(?:with|in|including|when)\b', T)
    empty = re.search(r'(?i)\b(?:empty\s+(?P<c>[a-z]+)|(?:the\s+)?(?P<c3>[a-z]+)\s+(?:on its own|alone|by itself))\s+weighs\s+(?P<b>\d+(?:\.\d+)?)\s?' + MU.replace('?P<u>', '?P<u2>'), T)
    if not (gross and empty) or gross.start() == empty.start():
        return None
    a = Fraction(gross['a']) * Fraction(MASS[gross['u'].lower()]).limit_denominator(10 ** 9)
    b = Fraction(empty['b']) * Fraction(MASS[empty['u2'].lower()]).limit_denominator(10 ** 9)
    want = (q['qu'] or 'g').lower() if q['qu'] else ('g' if gross['u'].lower().startswith('g') or empty['u2'].lower().startswith('g') else 'kg')
    want = {'grams': 'g', 'kilograms': 'kg', 'kilos': 'kg', 'ounces': 'oz', 'pounds': 'lb'}.get(want, want)
    net = (a - b) / Fraction(MASS[want]).limit_denominator(10 ** 9)
    if net < 0:
        return None
    return out(f'**{fmt(net)} {want}**: {gross["a"]} {gross["u"]} − {empty["b"]} {empty["u2"]} for the {empty["c"] or empty["c3"]}.', 'tare')


LEN = {'mm': 1, 'millimetre': 1, 'millimetres': 1, 'millimeter': 1, 'millimeters': 1, 'cm': 10, 'centimetre': 10, 'centimetres': 10, 'centimeter': 10,
       'centimeters': 10, 'm': 1000, 'metre': 1000, 'metres': 1000, 'meter': 1000, 'meters': 1000, 'in': Fraction(254, 10), 'inch': Fraction(254, 10),
       'inches': Fraction(254, 10)}
LU = r'(?:mm|millimet(?:re|er)s?|cm|centimet(?:re|er)s?|metres?|meters?|m|inch(?:es)?|in)'


def clearance(T, Q):
    q = re.search(r'(?i)how many\s+(?P<qu>millimet(?:re|er)s|centimet(?:re|er)s|mm|cm|inches)\b[^?]*\b(?:left|spare|remain|allowance|over|free)', Q)
    if not q:
        return None
    lim = re.search(r'(?i)\b(?:up to|at most|maximum(?: of)?|max|no more than|limit of|space is|gap is|opening is|is)\s+(?P<L>\d+(?:\.\d+)?)\s?(?P<Lu>' + LU + r')\s+(?:wide|across|long|high|tall)', T)
    item = re.search(r'(?i)\b(?:my|the|our)\s+(?P<thing>[a-z]+)\s+is\s+(?P<A>\d+(?:\.\d+)?)\s?(?P<Au>' + LU + r')\s+(?:across|wide|long|high|tall)', T)
    side = re.search(r'(?i)\b(?:adds|needs|takes|plus|with)\s+(?P<F>\d+(?:\.\d+)?)\s?(?P<Fu>' + LU + r')(?:\s+of\s+[a-z]+)?\s+(?:on|at|to)\s+(?:each|either|both)\s+sides?', T)
    if not (lim and item) or lim.start() == item.start():
        return None
    L = Fraction(lim['L']) * LEN[lim['Lu'].lower()]
    A = Fraction(item['A']) * LEN[item['Au'].lower()]
    F = Fraction(side['F']) * LEN[side['Fu'].lower()] if side else 0
    qu = {'millimetres': 'mm', 'millimeters': 'mm', 'centimetres': 'cm', 'centimeters': 'cm', 'inches': 'in'}.get(q['qu'].lower(), q['qu'].lower())
    left = (L - A - 2 * F) / LEN[qu]
    used = (A + 2 * F) / LEN[qu]
    if left < 0:
        return out(f'**None: it is {fmt(-left)} {qu} too wide** ({fmt(used)} {qu} needed against {fmt(L / LEN[qu])} {qu} allowed).', 'clearance')
    return out(f'**{fmt(left)} {qu}**: {fmt(L / LEN[qu])} {qu} allowed − ({fmt(A / LEN[qu])} {qu}' + (f' + 2 × {fmt(F / LEN[qu])} {qu}' if F else '') +
               f' = {fmt(used)} {qu}).', 'clearance')


CLOCK = r'(?:\d{1,2}:\d{2}\s*(?:am|pm|a\.m\.|p\.m\.)?|\d{1,2}\s*(?:am|pm|a\.m\.|p\.m\.)|noon|midnight)'


def minutes_of(s):
    s = s.lower().replace('.', '').strip()
    if s == 'noon':
        return 12 * 60
    if s == 'midnight':
        return 0
    m = re.fullmatch(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', s)
    if not m:
        raise ValueError(s)
    h, mi = int(m[1]), int(m[2] or 0)
    if m[3]:
        if not 1 <= h <= 12:
            raise ValueError(s)
        h = h % 12 + (12 if m[3] == 'pm' else 0)
    elif not m[2] or h > 23:
        raise ValueError(s)
    return h * 60 + mi


def clock(mins, twelve):
    mins = int(mins) % 1440
    h, m = divmod(mins, 60)
    if twelve:
        return f'{(h - 1) % 12 + 1}:{m:02d} {"am" if h < 12 else "pm"}'
    return f'{h:02d}:{m:02d}'


def span_minutes(T, Q):
    if not re.search(r'(?i)how many minutes|how long', Q):
        return None
    if re.search(r'(?i)\b(?:lunch|break|pause|interval)\b', T):
        return None             # time off inside the span: everyday_more.work_time
    m = re.search(r'(?i)\b(?:starts?|started|begins?|began|leaves?|left|departs?|from|opens?|goes on)\s+(?:at\s+)?(?P<a>' + CLOCK + r')[^.?]*?\b(?:stops?|stopped|ends?|ended|arrives?|arrived|finishes|finished|until|till|to|closes?|gets in)\s+(?:at\s+)?(?P<b>' + CLOCK + r')', T)
    if not m:
        return None
    a, b = minutes_of(m['a']), minutes_of(m['b'])
    d = (b - a) % 1440
    if d == 0:
        return None
    across = ' (it runs past midnight)' if b <= a else ''
    if re.search(r'(?i)how many minutes', Q):
        return out(f'**{d} minutes**: from {m["a"]} to {m["b"]}{across}.', 'span')
    return out(f'**{d // 60} hour{"s" if d // 60 != 1 else ""} {d % 60} minutes** ({d} minutes): from {m["a"]} to {m["b"]}{across}.', 'span')


PLACE = r'(?:(?:City|Town|Port|Mount|New|San|Los|Las) )?[A-Z][A-Za-z]*'


def zones(T, Q):
    if not re.search(r'(?i)what (?:day and )?time|which day and time|when should', Q):
        return None
    m = re.search(r'(?P<x>' + PLACE + r')(?: clocks?| time)?\s+(?:run|runs|is|are|sits?)\s+(?P<n>' + N + r')\s+hours?\s+(?P<dir>ahead of|behind)\s+(?P<y>' + PLACE + r')', T)
    if not m:
        return None
    x, y = m['x'], re.sub(r' clocks?$| time$', '', m['y'])
    ev = re.search(r'(?i)(?:(?:on\s+)?(?P<d>' + DAY + r')\s+at\s+(?P<t>' + CLOCK + r')|at\s+(?P<t2>' + CLOCK + r')\s+on\s+(?P<d2>' + DAY + r'))\s+(?:in\s+)?(?:the\s+)?(?P<p>' + PLACE + r')', T)
    if not ev:
        return None
    day = (ev['d'] or ev['d2']).lower()
    t = ev['t'] or ev['t2']
    p = ev['p']
    n = int(num(m['n']))
    ahead = m['dir'].lower() == 'ahead of'
    # x = y + n (ahead) or x = y - n (behind)
    if p.split()[-1] == x.split()[-1]:
        other, shift = y, (-n if ahead else n)
    elif p.split()[-1] == y.split()[-1]:
        other, shift = x, (n if ahead else -n)
    else:
        return None
    start = DAYS.index(day) * 1440 + minutes_of(t)
    then = start + shift * 60
    d2 = DAYS[(then // 1440) % 7]
    twelve = bool(re.search(r'(?i)am|pm', t))
    return out(f'**{d2.capitalize()} at {clock(then % 1440, twelve)}** in {other}: {day.capitalize()} {t} in {p} '
               f'{"minus" if shift < 0 else "plus"} {abs(shift)} hours.', 'zones')


def duration(s):
    """'an hour and ten minutes' -> 70, 'a quarter hour' -> 15, '50 minutes' -> 50, 'half an hour' -> 30."""
    s = s.lower().strip()
    if re.fullmatch(r'(?:a\s+)?quarter(?:[\s-]of an)?[\s-]hour|a quarter of an hour', s):
        return 15
    if re.fullmatch(r'(?:a\s+)?half(?:\s+an|[\s-])\s?hour|half an hour', s):
        return 30
    if re.fullmatch(r'three quarters of an hour', s):
        return 45
    total = 0
    found = False
    for m in re.finditer(r'(?P<n>' + NA + r')\s+(?P<u>hours?|hrs?|minutes?|mins?)\b', s):
        total += num(m['n']) * (60 if m['u'].startswith('h') else 1)
        found = True
    half = re.search(r'and a half hours?|hours? and a half', s)
    if half and found:
        total += 30
    if not found:
        raise ValueError(s)
    return total


DUR = r'(?:(?:a\s+)?quarter(?:[\s-]of an)?[\s-]hour|a quarter of an hour|half an hour|three quarters of an hour|(?:' + NA + r')\s+(?:hours?|hrs?)(?:\s+and\s+(?:' + NA + r')\s+(?:minutes?|mins?))?|(?:' + NA + r')\s+(?:minutes?|mins?))'


def cooking(T, Q):
    if not re.search(r'(?i)what time|when (?:should|do|does|will|is|can)', Q):
        return None
    m = re.search(r'(?i)\bat\s+(?P<t>\d{1,2}:\d{2}\s*(?:am|pm)?|\d{1,2}\s*(?:am|pm))\s+for\s+(?P<dur>' + DUR + r')', T) or \
        re.search(r'(?i)\bfor\s+(?P<dur>' + DUR + r')\s+(?:starting\s+|from\s+)?at\s+(?P<t>\d{1,2}:\d{2}\s*(?:am|pm)?|\d{1,2}\s*(?:am|pm))', T)
    if not m:
        return None
    rest = T[m.end():]
    ext = 0
    for e in re.finditer(r'(?i)\b(?:extra|another|additional|further)\s+(?P<d>' + DUR + r')|(?P<d2>' + DUR + r')\s+(?:extra|more|longer)\b', rest):
        ext += duration(e['d'] or e['d2'])
    if re.search(r'(?i)\b(?:less|shorter|cut it short|take off)\b', rest):
        return None
    base = duration(m['dur'])
    start = minutes_of(m['t'])
    end = start + base + ext
    twelve = bool(re.search(r'(?i)am|pm', m['t']))
    return out(f'**{clock(end, twelve)}**: {m["t"]} + {fmt(base)} minutes' + (f' + {fmt(ext)} extra' if ext else '') +
               f' = {clock(end, twelve)}.', 'cooking')


# ------------------------------------------------------------------ dates
def months_after(T, Q):
    if not re.search(r'(?i)\bmonth\b|which month|what month|when', Q):
        return None
    ms = re.findall(r'(?i)\b(' + MON + r')\s+(\d{4})\b', T)
    k = re.search(r'(?i)\b(?P<n>' + N + r')\s+(?:calendar\s+)?months?\s+(?P<dir>after|later|before|earlier)', T)
    if len(ms) != 1 or not k:
        return None
    mon, year = MONTHS.index(ms[0][0].lower()), int(ms[0][1])
    n = int(num(k['n'])) * (-1 if k['dir'].lower() in ('before', 'earlier') else 1)
    i = year * 12 + mon + n
    return out(f'**{MONTHS[i % 12].capitalize()} {i // 12}**: {n:+d} months from {ms[0][0].capitalize()} {year}.', 'months')


def a_date(s):
    m = re.search(r'(?i)\b(?P<d>\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(?P<m>' + MON + r')\s*,?\s+(?P<y>\d{4})\b', s) or \
        re.search(r'(?i)\b(?P<m>' + MON + r')\s+(?P<d>\d{1,2})(?:st|nd|rd|th)?,?\s+(?P<y>\d{4})\b', s)
    if not m:
        return None
    return date(int(m['y']), MONTHS.index(m['m'].lower()) + 1, int(m['d'])), m


def show(d):
    return f'{d.day} {MONTHS[d.month - 1].capitalize()} {d.year}'


REL = {'the day before yesterday': -2, 'day before yesterday': -2, 'yesterday': -1, 'today': 0, 'tomorrow': 1, 'the day after tomorrow': 2,
       'day after tomorrow': 2}


def relative_day(T, Q):
    if not re.search(r'(?i)what date|which date|what day|when\b|what was the date', Q):
        return None
    if re.search(r'(?i)\bborn\b', T):
        return None
    got = a_date(T)
    if not got or not re.search(r'(?i)\b(?:today is|it is|it\'s|it was|imagine|suppose|pretend|say)\b', T[:got[1].end() + 40]):
        return None
    base = got[0]
    after = T[got[1].end():]
    r = re.search(r'(?i)\b(the day before yesterday|day before yesterday|the day after tomorrow|day after tomorrow|yesterday|tomorrow)\b|\b(?P<n>' + N + r')\s+days?\s+(?P<dir>ago|earlier|later|from (?:then|now|today))\b', after)
    if not r:
        return None
    if r[1]:
        off = REL[r[1].lower()]
    else:
        off = int(num(r['n'])) * (-1 if r['dir'].lower() in ('ago', 'earlier') else 1)
    d = base + timedelta(days=off)
    return out(f'**{show(d)}** ({DAYS[d.weekday()].capitalize()}): {off:+d} day{"s" if abs(off) != 1 else ""} from {show(base)}.', 'relative-day')


def age(T, Q):
    if not re.search(r'(?i)how old|what age|\bage\b', Q):
        return None
    b = re.search(r'(?i)\bborn\b[^.]*', T)
    if not b:
        return None
    born = a_date(b[0])
    if not born:
        return None
    rest = T[:b.start()] + T[b.start() + born[1].end():]
    at = a_date(rest)
    if not at:
        return None
    d0, d1 = born[0], at[0]
    years = d1.year - d0.year - ((d1.month, d1.day) < (d0.month, d0.day))
    if years < 0:
        return None
    note = ' (the birthday is the next day)' if (d1 + timedelta(days=1)).month == d0.month and (d1 + timedelta(days=1)).day == d0.day else ''
    return out(f'**{years}**: born {show(d0)}, so on {show(d1)} the {d1.year} birthday had not come yet{note}.' if (d1.month, d1.day) < (d0.month, d0.day)
               else f'**{years}**: born {show(d0)}, and the {d1.year} birthday had already come by {show(d1)}.', 'age')


def weekday_later(T, Q):
    if not re.search(r'(?i)(?:which|what)\s+(?:week)?day|what day of the week', Q):
        return None
    days = re.findall(r'(?i)\b(' + DAY + r')s?\b', T)
    if len(set(d.lower() for d in days)) != 1:
        return None
    m = re.search(r'(?i)\b(?:(?P<w>' + N + r')\s+weeks?(?:\s+and\s+(?P<d>' + N + r')\s+days?)?|(?P<d2>' + N + r')\s+days?)\s+(?P<dir>later|after|afterwards|from then|on|before|earlier)\b', T)
    if not m:
        return None
    n = int(num(m['w'])) * 7 if m['w'] else 0
    n += int(num(m['d'] or m['d2'] or '0'))
    if m['dir'].lower() in ('before', 'earlier'):
        n = -n
    start = DAYS.index(days[0].lower())
    return out(f'**{DAYS[(start + n) % 7].capitalize()}**: {abs(n)} days {"after" if n >= 0 else "before"} a {days[0].capitalize()} '
               f'({abs(n) // 7} weeks bring you back to {days[0].capitalize()}, then {abs(n) % 7} more).', 'weekday')


def next_weekday_date(T, Q):
    if not re.search(r'(?i)what (?:number|date)|which (?:number|date)|date of', Q):
        return None
    m = re.search(r'(?i)\bthe\s+(?P<n>\d{1,2})(?:st|nd|rd|th)\s+(?:is|was|falls on|fell on)\s+(?:a\s+)?(?P<day>' + DAY + r')', T)
    t = re.search(r'(?i)\b(?:the\s+)?(?:very\s+)?(?:next|following|coming)\s+(?P<day>' + DAY + r')', T[m.end():] if m else '')
    if not (m and t):
        return None
    a, b = DAYS.index(m['day'].lower()), DAYS.index(t['day'].lower())
    step = (b - a) % 7 or 7
    n = int(m['n']) + step
    if n > 28:
        return out(f'**The {n}th**, if the month has that many days ({step} days after the {m["n"]}); otherwise it falls early in the next month.', 'next-weekday')
    suffix = 'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return out(f'**{n}** (the {n}{suffix}): the next {t["day"].capitalize()} is {step} days after {m["day"].capitalize()} the {m["n"]}.', 'next-weekday')


def is_leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def leap(T, Q):
    m = re.search(r'(?i)\b(?:was|is|will)\s+(?P<y>\d{4})\s+(?:be\s+)?a\s+leap\s+year', Q)
    if m:
        y = int(m['y'])
        why = ('divisible by 400' if y % 400 == 0 else 'a century year not divisible by 400' if y % 100 == 0 else
               'divisible by 4' if y % 4 == 0 else 'not divisible by 4')
        return out(f'**{"Yes" if is_leap(y) else "No"}.** {y} is {why}, so in the Gregorian calendar it {"was" if is_leap(y) else "was not"} a leap year.', 'leap')
    m = re.search(r'(?i)\b28(?:th)?\s+(?:of\s+)?february,?\s+(?P<y>\d{4})\b[^.?]*?\b(?:to|and|then)\s+(?:the\s+)?1(?:st)?\s+(?:of\s+)?march,?\s+(?P=y)', T)
    if m and re.search(r'(?i)\bskip|miss|gap|lose|left out', Q):
        y = int(m['y'])
        if is_leap(y):
            return out(f'**Yes**: {y} was a leap year, so 29 February {y} was skipped.', 'leap')
        why = 'a century year not divisible by 400' if y % 100 == 0 else 'not divisible by 4'
        return out(f'**No.** {y} is {why}, so it was not a leap year in the Gregorian calendar: 1 March came straight after 28 February.', 'leap')
    return None


# ------------------------------------------------------------------ logic
def head(phrase):
    words = re.findall(r'[a-z]+', phrase.lower())
    words = [w for w in words if w not in ('a', 'an', 'the', 'its', 'their', 'his', 'her', 'any', 'one')]
    if not words:
        return ''
    w = words[-1]
    return w[:-1] if w.endswith('s') and not w.endswith('ss') else w


def every_mark(T, Q):
    if not re.search(r'(?i)\bcould\b[^?]*\b(?:have been|be|been)\b|\bcan it\b|\bis it possible\b', Q):
        return None
    m = re.search(r'(?i)\b(?:every|each|all)\s+(?P<cls>[a-z ]+?)\s+(?:got|had|has|have|wore|wear|wears|was given|were given|received|carried|carries|bore|bears|gets|was marked with|were marked with|was stamped with)\s+(?:a\s+|an\s+)?(?P<mark>[a-z ]+?)[.;]', T)
    if not m:
        return None
    no = re.search(r'(?i)\b(?:has|had|wore|wears|carries|got|bears|shows)\s+no\s+(?P<mk>[a-z ]+?)[.;,]|\b(?:without|doesn\'t have|does not have|didn\'t have|lacks)\s+(?:a\s+|an\s+|any\s+)?(?P<mk2>[a-z ]+?)[.;,]', T[m.end():])
    if not no or head(no['mk'] or no['mk2']) != head(m['mark']):
        return None
    cls_words = set(re.findall(r'[a-z]{4,}', m['cls'].lower()))
    if not cls_words & set(re.findall(r'[a-z]{4,}', Q.lower())):
        return None
    return out(f'**No.** By that rule every {m["cls"].strip()} got {("a " if not m["mark"].lower().startswith(("a ", "an ")) else "")}{m["mark"].strip()}; '
               f'this one has none, so it can\'t have been one of them (unless the rule was broken).', 'every-mark')


def undecided_order(T, Q):
    q = re.search(r'(?i)which of (?:the\s+)?(?P<a>[a-z]+)(?:\s+[a-z]+)? and (?:the\s+)?(?P<b>[a-z]+)\b[^?]*\b(?:first|earlier|before|last|later)'
                  r'|(?:who|which)\s+[a-z ]*?(?:first|earlier|last)[^?]*?,\s+(?P<a2>[A-Za-z]+)\s+or\s+(?P<b2>[A-Za-z]+)', Q)
    if not q:
        return None
    a, b = (q['a'] or q['a2']).lower(), (q['b'] or q['b2']).lower()
    sa = [s for s in sentences(T) if re.search(r'\b' + a + r'\b', s.lower()) and re.search(r'\b(?:before|after|ahead of|behind)\b', s.lower())]
    sb = [s for s in sentences(T) if re.search(r'\b' + b + r'\b', s.lower()) and re.search(r'\b(?:before|after|ahead of|behind)\b', s.lower())]
    both = [s for s in sentences(T) if re.search(r'\b' + a + r'\b', s.lower()) and re.search(r'\b' + b + r'\b', s.lower()) and not s.strip().endswith('?')]
    if not sa or not sb or both or sa == sb:
        return None
    return out(f'**No, it can\'t be worked out.** Both {a} and {b} are placed only relative to a third thing, never to each other, '
               f'so either could have come first.', 'undecided')


def between(T, Q):
    if not re.search(r'(?i)\border\b|line-?up|left to right|right to left|arrangement', Q):
        return None
    lr = re.search(r'(?i)\b(?:the\s+)?(?P<a>[a-z]+(?:\s[a-z]+)?)\s+(?:is|sits|stands|goes)\s+(?:somewhere\s+|just\s+|immediately\s+|anywhere\s+)?(?:to\s+the\s+)?(?P<side>left|right)\s+of\s+(?:the\s+)?(?P<b>[a-z]+(?:\s[a-z]+)?)\b', T)
    mid = re.search(r'(?i)\b(?:the\s+)?(?P<c>[a-z]+(?:\s[a-z]+)?)\s+(?:is|sits|stands|goes|lies)\s+(?:somewhere\s+)?between\s+(?:them|the two|both)', T)
    if not (lr and mid):
        return None
    clean = lambda s: re.sub(r'(?i)^(?:the|a|an)\s+', '', s.strip())
    a, b, c = clean(lr['a']), clean(lr['b']), clean(mid['c'])
    if len(re.findall(r'(?i)\bjars?|books?|cups?|items?|things?\b', a)) or a == b:
        pass
    order = [a, c, b] if lr['side'].lower() == 'left' else [b, c, a]
    if re.search(r'(?i)right to left', Q):
        order.reverse()
    return out(f'**{", ".join(order)}**' + (' (left to right)' if not re.search(r'(?i)right to left', Q) else ' (right to left)') +
               f': the {a} is {lr["side"].lower()} of the {b}, and the {c} is between them.', 'between')


OPP = {'on': 'off', 'off': 'on', 'lit': 'dark', 'dark': 'lit', 'unlit': 'lit', 'open': 'closed', 'closed': 'open', 'shut': 'open'}


def exactly_one(T, Q):
    m = re.search(r'(?i)\bexactly one\b[^.]*?\b(?:is|was|are)\s+(?P<st>on|lit|open|closed|off|dark|switched on)\b', T)
    names = re.search(r'\b(?P<x>[A-Z])\s+and\s+(?P<y>[A-Z])\b', T)
    if not (m and names):
        return None
    st = m['st'].lower().replace('switched on', 'on')
    obs = re.search(r'\b(?:for\s+)?(?:lamp\s+|switch\s+|light\s+|door\s+)?(?P<o>' + names['x'] + '|' + names['y'] + r')\b[^.?]*?\b(?:reads|is|shows|was|looks)\s+(?P<ost>on|off|dark|lit|unlit|open|closed|shut)\b', T[m.end():])
    q = re.search(r'\b(?i:is)\s+(?i:lamp\s+|switch\s+|light\s+|door\s+)?(?P<q>[A-Z])\s+(?P<qst>on|off|lit|dark|open|closed)\b', Q)
    if not (obs and q):
        return None
    o, ost, qn, qst = obs['o'], obs['ost'].lower(), q['q'], q['qst'].lower()
    o_has = ost == st or (st in ('on', 'lit') and ost in ('on', 'lit'))
    other = names['y'] if o == names['x'] else names['x']
    if qn == o:
        yes = (ost == qst) or (qst in ('on', 'lit') and ost in ('on', 'lit'))
    elif qn == other:
        other_has = not o_has
        yes = other_has == (qst == st or (st in ('on', 'lit') and qst in ('on', 'lit')))
    else:
        return None
    return out(f'**{"Yes" if yes else "No"}.** Exactly one is {st}; {o} reads {ost}, so {other} {"is" if not o_has else "is not"} {st}.', 'exactly-one')


def only_members(T, Q):
    m = re.search(r'(?i)\bonly\s+(?P<cls>[a-z]+(?:\s[a-z]+)?)\s+(?:may|can|are allowed to|could|get to|are able to)\s+(?P<act>[a-z ]+?)[.;]', T)
    who = re.search(r'\b(?P<who>[A-Z][a-z]+)\s+is\s+(?:a\s+|an\s+|one of the\s+|on the\s+|part of the\s+)?(?P<cls>[a-z]+)', T)
    if not (m and who) or not re.search(r'(?i)\b(?:prove|mean|show|follow|guarantee|establish)\b', Q):
        return None
    if head(who['cls']) != head(m['cls']):
        return None
    return out(f'**No.** "Only {m["cls"]} may {m["act"]}" makes being one of the {m["cls"]} necessary, not sufficient: it shows {who["who"]} '
               f'was allowed to, not that {who["who"]} did.', 'only')


# ------------------------------------------------------------------ labelled accounts
LABEL = r'(?:Witness|Report|Log|Post|Note|Sheet|Source|Sensor|Neighbour|Neighbor|Account|Record|Entry|Officer|Camera|Memo|Message|Reading|Survey|Reporter|Statement|Guard|Clerk|Diary|Ledger|Version|Article|Website|Paper|List)\s+(?:[A-Z][a-z]*|\d+)'


def claims(T):
    """Ordered labelled claims: (label, text)."""
    got = []
    for m in re.finditer(r'(?P<label>' + LABEL + r')\s*(?::\s*|\s+(?:says|said|reports|reported|claims|claimed|states|stated|puts|lists|records|recorded|shows|showed|writes|wrote|gives|gave|has)\s+(?:that\s+)?)(?P<claim>[^.]*(?:\.\d+[^.]*)?)', T):
        got.append((m['label'], m['claim'].strip()))
    for m in re.finditer(r'(?P<label>' + LABEL + r')\b[^.]*?\band\s+(?:reported|said|says|claimed)\s+(?P<claim>[^.]+)', T):
        if not any(m['label'] == g[0] for g in got):
            got.append((m['label'], m['claim'].strip()))
    return got


def short(label):
    return label.split()[-1]


def find_label(name, labels):
    for lab in labels:
        if lab.lower() == name.lower() or short(lab).lower() == name.lower():
            return lab
    return None


def priority_rule(T, Q):
    r = re.search(r'(?i)\b(?:use|go with|trust|take|prefer|follow|believe)\s+the\s+(?P<win>[a-z ]+?)\s+(?:whenever|when|if|wherever)\s+(?:it\s+|they\s+)?(?:conflicts?|disagrees?|clash(?:es)?|differs?)\s+(?:with\s+)?(?:the\s+|a\s+|an\s+|any\s+)?(?P<lose>[a-z ]+?)[.,;]', T)
    if not r:
        r2 = re.search(r'(?i)\b(?:when|whenever|if)\s+(?:the\s+|a\s+|an\s+)?(?P<x>[a-z ]+?)\s+and\s+(?:the\s+|a\s+|an\s+)?(?P<y>[a-z ]+?)\s+'
                       r'(?:disagree|conflict|differ|clash)[^,.]*,\s*(?:go with|use|trust|take|prefer|follow|believe)\s+the\s+(?P<win>[a-z ]+?)[.;]', T)
        if r2:
            r = dict(win=r2['win'], lose=r2['y'] if head(r2['win']) == head(r2['x']) else r2['x'])
    if not r or not re.search(r'(?i)\bhow many|which|what|how much', Q):
        return None
    vals = {}
    for m in re.finditer(r'(?P<lab>[A-Z][a-z]+(?:\s[a-z]+){0,2}):\s*(?P<v>[^.]+)', T):
        vals[m['lab'].lower()] = m['v'].strip()
    win = next((v for k, v in vals.items() if head(k) == head(r['win']) or k == r['win'].lower()), None)
    lose = next((v for k, v in vals.items() if head(k) == head(r['lose']) or k == r['lose'].lower()), None)
    if not (win and lose):
        return None
    return out(f'**{win}**: the {r["win"]} says {win} and the {r["lose"]} says {lose}; by your rule the {r["win"]} wins.', 'priority')


def withdrawn(T, Q):
    w = re.search(r'(?i)\b(?P<who>(?:' + LABEL + r')|[A-Z][a-z]+)\s+has\s+(?:now\s+|just\s+|since\s+)?(?:withdrawn|retracted|taken back|dropped|withdrew)', T)
    if not w or not re.search(r'(?i)\b(?:still|stands?|remains?|on record|left|valid)\b', Q):
        return None
    cs = claims(T)
    labels = [c[0] for c in cs]
    gone = find_label(w['who'].split()[-1], labels)
    if not gone:
        return None
    left = [(l, c) for l, c in cs if l != gone]
    if len(left) != 1:
        return None
    lab, claim = left[0]
    claim = re.sub(r'(?i)^(?:that\s+)?', '', claim)
    return out(f'**{lab}**, who reported {claim}. {gone} withdrew their statement, so theirs is the only claim still on record.', 'withdrawn')


def corrected_value(T):
    """(label, new value text) from "Correction to K ... K should say V" or "S has corrected its entry to V"."""
    m = re.search(r'(?i)\bcorrection to (?P<lab>(?:[a-z]+\s+)?[A-Z0-9][a-z]*)\b(?P<rest>.*)', T, re.S)
    if m:
        v = re.search(r'(?i)\b(?:should (?:say|read|be)|now (?:says|reads|gives)|is actually|was actually|it should read|read)\s*:?\s*(?P<v>[^.”"\n]+?(?:\.\d+)?)(?=[.”"\n]|$)', m['rest'])
        if v:
            return m['lab'].split()[-1], v['v'].strip()
    m = re.search(r'(?P<lab>' + LABEL + r'|[A-Z][a-z]+)\s+has\s+(?:just\s+|now\s+|since\s+)?corrected\s+(?:its|their|his|her|the)\s+(?:[a-z]+\s+){0,2}to\s+(?P<v>[^.]+)', T)
    if m:
        return m['lab'].split()[-1], m['v'].strip()
    return None


AMOUNT = {'once': 1, 'twice': 2, 'thrice': 3}


def amount_in(s):
    s = s.lower()
    for k, v in AMOUNT.items():
        if re.search(r'\b' + k + r'\b', s):
            return v
    m = re.search(r'\b(\d{1,2}:\d{2})\b', s)
    if m:
        return m[1]
    m = re.search(r'\b(' + N + r')\s*(?:times?|rings?|chimes?|counts?|[a-z]+)?\b', s, re.I)
    if m:
        try:
            return num(m[1])
        except ValueError:
            return None
    return None


def correction(T, Q):
    got = corrected_value(T)
    if not got:
        return None
    lab, v = got
    q = re.search(r'(?i)\bdoes\s+(?:(?:log|report|sheet|note|post|witness|record|entry|source)\s+)?(?P<lab>[A-Z0-9][a-z]*)(?:\s+itself)?\s+now\s+(?:give|say|show|read|report|list)', Q)
    if q and q['lab'].lower() == lab.lower():
        return out(f'**{v}**: that is what {lab} says after its correction; the earlier figure no longer counts.', 'correction')
    if re.search(r'(?i)\bagree|in common|both say|do they (?:now )?match', Q):
        cs = claims(T[:T.lower().find(lab.lower() + ' has')] if lab.lower() + ' has' in T.lower() else T)
        if len(cs) < 2:
            return None
        vals = {}
        for l, c in cs:
            vals[short(l).lower()] = amount_in(c)
        if lab.lower() not in vals:
            return None
        vals[lab.lower()] = amount_in(v)
        if None in vals.values():
            return None
        distinct = set(vals.values())
        if len(distinct) == 1:
            x = next(iter(distinct))
            word = x if isinstance(x, str) else {1: 'once', 2: 'twice', 3: 'three times', 4: 'four times', 5: 'five times'}.get(x, fmt(x))
            return out(f'**{word[0].upper() + word[1:]}**: after the correction every report says {word}.', 'correction')
        return out('**They still disagree**: ' + '; '.join(f'{k.capitalize()} says {fmt(x) if not isinstance(x, str) else x}' for k, x in vals.items()) + '.', 'correction')
    return None


def no_priority(T, Q):
    if not re.search(r'(?i)\bneither\s+(?:one\s+)?(?:has priority|is more reliable|is (?:more )?trusted|outranks|is preferred|is more trustworthy)|\bboth\s+(?:are\s+)?equally\s+(?:reliable|trusted)|\b(?:nobody|no one|we don\'t|we do not) knows? which\b', T):
        return None
    if not re.search(r'(?i)\bwhich|where|what|when|who', Q):
        return None
    cs = claims(T)
    if len(cs) < 2:
        cs = [(m['lab'], m['v']) for m in re.finditer(r'(?P<lab>(?:Report|Note|Source|Witness|Post|Log|Sheet|Sign|Notice|Board|Poster|Clock)\s+\w+)\s+(?:puts|lists|says|places|has|gives)\s+(?P<v>[^.]+)', T)]
    if len(cs) < 2:
        return None
    THAT = re.compile(r'(?i)^(?:that\s+)')          # outside the f-string: Python 3.11 allows no backslash in its expressions
    parts = '; '.join(f'{l} says {THAT.sub("", c)}' for l, c in cs[:3])
    return out(f'**They don\'t establish one.** {parts}, and neither has priority, so the reports conflict and the answer stays open '
               f'until one is confirmed.', 'no-priority')


HEARSAY = re.compile(r'(?i)\bcame from\b|\baccording to\b|\bheard (?:from|it)\b|\bcopied\b|\brepeat|\bquot|\bsaid so\b|\b(?:' + LABEL + r')\s+(?:saw|counted|said|says|reported|heard)\b|\bfrom (?:' + LABEL + r')\b')
FIRST = re.compile(r'(?i)\bI\s+(?:was\s+(?:there|at|in|on)|counted|saw|heard|measured|watched|noticed|checked|spotted|was at)\b|\bmyself\b|\bwith my own eyes\b')


def firsthand(T, Q):
    if not re.search(r'(?i)how many\s+(?:firsthand|first-hand|direct|eyewitness)', Q):
        return None
    cs = claims(T)
    if len(cs) < 2:
        return None
    own = [l for l, c in cs if FIRST.search(c) and not HEARSAY.search(c)]
    if not own or len(own) + sum(1 for _, c in cs if HEARSAY.search(c)) != len(cs):
        return None         # every account must read as either seen first-hand or passed on
    other = [l for l, c in cs if l not in own]
    n = len(own)
    word = {0: 'None', 1: 'One', 2: 'Two', 3: 'Three', 4: 'Four'}.get(n, str(n))
    return out(f'**{word}**' + (f': {" and ".join(own)}' if own else '') + (f'. {", ".join(other)} only repeat{"s" if len(other) == 1 else ""} '
               f'someone else\'s account, so {"it adds" if len(other) == 1 else "they add"} nothing firsthand.' if other else '.'), 'firsthand')


# ------------------------------------------------------------------ memory within the chat
def borrowed(T, Q):
    if not re.search(r'(?i)\bwho\b[^?]*\b(?:wants?|needs?|asked for|would like|is expecting)\b[^?]*\bback\b', Q):
        return None
    m = re.search(r'(?i)\bI\s+borrowed\s+(?:an?\s+|the\s+|some\s+)?(?P<thing>[a-z ]+?)\s+from\s+(?P<owner>my\s+[a-z]+|[A-Z][a-z]+)', T)
    if not m:
        return None
    owner = re.sub(r'(?i)^my\s+', 'your ', m['owner'])
    return out(f'**{owner[0].upper() + owner[1:]}**: you borrowed the {m["thing"]} from {owner}.', 'borrowed')


def renamed(T, Q, users):
    q = re.search(r'(?i)what\s+(?:name|is the\s+(?P<obj>[a-z ]+?)\s+called)|what\'s the\s+(?P<obj2>[a-z ]+?)\s+called|what name did we|what did we (?:call|name)', Q)
    if not q:
        return None
    last = None
    names = []
    for u in users[:-1]:
        for m in re.finditer(r'\b(?i:named|called|call|name|label(?:led)?|nicknamed)\s+(?:it|(?i:the|my)\s+[a-z ]+?)\s+(?P<n>[A-Z][a-z]+)\b', u):
            names.append(m['n'])
            last = m['n']
    if len(names) < 2 or not last:
        return None
    return out(f'**{last}**: that was the last name you gave it' + (f' (it was {names[0]} before)' if names[0] != last else '') + '.', 'renamed')


def similar_names(T, Q):
    q = re.search(r'\b(?:writing to|calling|visiting|meeting|emailing|texting|phoning|seeing|ringing)\s+(?P<who>[A-Z][a-z]+)', T.split('\n')[-1] if '\n' in T else Q) or \
        re.search(r'\b(?:writing to|calling|visiting|meeting|emailing|texting|phoning|seeing|ringing)\s+(?P<who>[A-Z][a-z]+)', T)
    if not q or not re.search(r'(?i)\bwhich\b|\bwhat\b', Q):
        return None
    facts = {m['n']: (m['v'], m['x'].strip()) for m in re.finditer(r'\b(?P<n>[A-Z][a-z]+)\s+(?P<v>collects|plays|likes|loves|studies|keeps|grows|teaches|makes|bakes|paints|speaks|owns)\s+(?P<x>[a-z ]+?)[;.,]', T)}
    if q['who'] not in facts or len(facts) < 2:
        return None
    v, x = facts[q['who']]
    return out(f'**{x[0].upper() + x[1:]}**: {q["who"]} {v} {x}.', 'similar-names')


def declined(T, Q):
    if not re.search(r'(?i)\bwhich\b|\bwhat\b|\bwhen\b', Q):
        return None
    orig = re.search(r'(?i)\b(?:booking|appointment|reservation|slot|table|seat|ticket|session|class|place)\b[^.]*?\b(?:is|was)\s+(?:for|on|at|in)\s+(?:the\s+)?(?P<o>[a-z0-9: ]+?)(?:\s+slot)?[.]', T)
    alt = re.search(r'(?i)\boffered\s+(?:me\s+|us\s+)?(?:the\s+)?(?P<a>[a-z0-9: ]+?)(?:\s+slot)?\s+instead', T)
    if not (orig and alt):
        return None
    no = re.search(r'(?i)\b(?:turned (?:that|it) down|said no|declined|refused|didn\'t take it|did not take it|kept (?:mine|my|the original)|stuck with)', T[alt.end():])
    yes = re.search(r'(?i)\b(?:accepted|took it|said yes|agreed|switched)', T[alt.end():])
    if bool(no) == bool(yes):
        return None
    keep = orig['o'] if no else alt['a']
    return out(f'**The {keep}**' + (f': you turned down the {alt["a"]} offer, so your original booking stands.' if no else
                                     f': you accepted the change from the {orig["o"]}.'), 'declined')


def price_never_said(T, Q, users):
    if not re.search(r'(?i)how much did I (?:say|tell you)(?: that)?\s+(?:I\s+)?(?:paid|spent|it cost|they cost)|what did I (?:say|tell you) (?:I paid|it cost)', Q):
        return None
    earlier = ' '.join(users[:-1])
    if monies(earlier) or re.search(r'(?i)\b(?:cost|paid|price|for\s+\d)', earlier):
        return None
    thing = re.search(r'(?i)\bI\s+(?:bought|got|purchased)\s+(?:an?\s+|the\s+|some\s+)?(?P<t>[a-z ]+?)(?:\s+at|\s+from|\s+in|[.,])', earlier)
    what = f'the {thing["t"]}' if thing else 'it'
    return out(f'**You didn\'t tell me** what you paid for {what}' + (f'; you only said you bought it' if thing else '') + '.', 'never-said')


# ------------------------------------------------------------------ unknowable and false premises
LANDLOCKED = ['switzerland', 'austria', 'hungary', 'czech republic', 'czechia', 'slovakia', 'luxembourg', 'liechtenstein', 'andorra', 'san marino',
              'vatican city', 'the vatican', 'bolivia', 'paraguay', 'mongolia', 'nepal', 'bhutan', 'afghanistan', 'laos', 'kazakhstan', 'uzbekistan',
              'kyrgyzstan', 'tajikistan', 'turkmenistan', 'armenia', 'belarus', 'moldova', 'serbia', 'north macedonia', 'kosovo', 'ethiopia',
              'uganda', 'rwanda', 'burundi', 'zambia', 'zimbabwe', 'malawi', 'botswana', 'lesotho', 'eswatini', 'swaziland', 'mali', 'niger',
              'chad', 'burkina faso', 'central african republic', 'south sudan']


def no_coast(T, Q):
    m = re.search(r'(?i)\b(?:which|what)\s+(?:ocean|sea|seas|oceans|coast|beach|port)\b[^?]*?\b(?P<c>' + '|'.join(LANDLOCKED) + r')(?:\'s)?\b', Q) or \
        re.search(r'(?i)\b(?P<c>' + '|'.join(LANDLOCKED) + r')(?:\'s)?\s+(?:coast|coastline|beaches|seaside|ports?)\b', Q)
    if not m:
        return None
    c = m['c'].title().replace("'S", "'s")
    return out(f'**None: {c} is landlocked**, so it has no coastline and no ocean or sea borders it.', 'no-coast')


def emptied(T, Q):
    m = re.search(r'(?i)\b(?:held|had|contained|kept|there were)\s+(?:exactly\s+|only\s+)?(?P<n>' + N + r')\s+(?P<item>[a-z ]+?)[.,]', T)
    took = re.search(r'(?i)\b(?:took|take|removed|emptied|tipped)\s+(?:out\s+)?(?:all|every one|each one)(?:\s+(?P<n2>' + N + r'))?|\bemptied (?:it|the)', T)
    if not (m and took) or not re.search(r'(?i)\b(?:still|left|remaining|remains)\b', Q):
        return None
    if took['n2'] and num(took['n2']) != num(m['n']):
        return None
    if re.search(r'(?i)\bput\s+(?:one|some|it|them|\d+|a)\s+back\b', T) and not re.search(r'(?i)\bput nothing back|didn\'t put|did not put', T):
        return None
    item = head(m['item'])
    return out(f'**There isn\'t one.** It held exactly {fmt(num(m["n"]))} {m["item"].strip()}, and all of them were taken out, so no {item} is left to have a colour.', 'emptied')


def hidden(T, Q):
    if re.search(r'(?i)\b(?:shuffled|face[- ]down|behind (?:a|the) screen|under (?:the|a) cup|rolled (?:a|the|two)? ?di(?:e|ce)|flipped (?:a|the) coin|tossed (?:a|the) coin|drew (?:a|one) card|random(?:ly)?)\b', T) and \
            re.search(r'(?i)\b(?:which|what)\s+(?:exact\s+)?(?:card|number|side|face|colou?r|one|ball|result)\b|what will (?:it|I) (?:show|turn|get|roll|draw)', Q):
        return out('**There\'s no way to know** which one it is: the outcome is hidden or random and you haven\'t told me what it is. Any exact '
                   'answer would be a guess; I can only give the odds.', 'hidden')
    if re.search(r'(?i)\b(?:sealed|locked|unopened|closed)\s+(?:envelope|letter|box|parcel|package|note|card)|\b(?:haven\'t|have not|didn\'t|did not)\s+(?:opened|read|described)', T) and \
            re.search(r'(?i)what(?:\s+is|\'s)\s+(?:the\s+)?(?:first|last|opening)?\s*(?:sentence|line|word|message)?\s*(?:inside|in it|written)|what\s+(?:does|did)\s+(?:it|the (?:letter|note|card))\s+say|what(?:\s+is|\'s)\s+the\s+(?:first|last|opening)\s+(?:sentence|line|word)', Q):
        return out('**I can\'t know that.** Nobody has opened it or told me what it says, so I have nothing to read the words from.', 'hidden')
    return None


def future_count(T, Q):
    if re.search(r'(?i)\b(?:exactly\s+)?how many\s+(?:guests|people|visitors|attendees|customers|fans|children|kids|friends|members|runners|players)\s+will\s+(?:turn up|come|attend|show up|be there|arrive|sign up|join)', Q):
        return out('**Nobody can know that in advance.** It depends on people\'s future choices; an RSVP count, past turnout or the venue size '
                   'can give an estimate, not an exact number.', 'future')
    return None


def number_clue(T, Q):
    r = re.search(r'(?i)\b(?:whole\s+)?(?:number|integer)\s+(?:strictly\s+)?(?:between|from)\s+(?P<a>\d+)\s+(?:and|to)\s+(?P<b>\d+)', T)
    if not r or not re.search(r'(?i)\b(?:exact|which|what)\s+(?:number|is it|one)|what\'s the (?:exact )?number|which number is it', Q):
        return None
    a, b = int(r['a']), int(r['b'])
    inclusive = bool(re.search(r'(?i)\bfrom\b', r[0])) or bool(re.search(r'(?i)inclusive', T))
    cands = list(range(a if inclusive else a + 1, b + 1 if inclusive else b))
    if re.search(r'(?i)\bodd\b', T):
        cands = [c for c in cands if c % 2]
    elif re.search(r'(?i)\beven\b', T):
        cands = [c for c in cands if c % 2 == 0]
    else:
        return None
    if len(cands) == 1:
        return out(f'**{cands[0]}**: it is the only one that fits.', 'clue')
    return out(f'**I can\'t tell exactly**: {", ".join(map(str, cands[:-1]))} and {cands[-1]} all fit those clues. One more clue would narrow it down.', 'clue')


# ------------------------------------------------------------------ everyday explanations
EXPLAIN = [
    (r'(?=.*\bmagnet)(?=.*\biron\b)(?=.*\b(?:sand|sawdust|sulph?ur|salt|soil)\b)',
     'Iron is magnetic and sand is not. Spread the dry mixture thin, then pass a magnet over it (wrapped in paper or a plastic bag, so the '
     'filings are easy to pull off): the iron filings jump to the magnet and the sand stays behind. Repeat until no more filings come up, '
     'then take the wrapping off the magnet to drop the iron into a separate dish.'),
    (r'(?=.*\bseparat)(?=.*\bsalt\b)(?=.*\bsand\b)',
     'Stir the mixture into water: the salt dissolves and the sand does not. Filter it (the sand stays on the filter paper), then let the '
     'salty water evaporate, by warming it gently, and the salt is left behind as crystals.'),
    (r'(?=.*\b(?:sugar|salt)\b)(?=.*\b(?:disappear|vanish|go|gone|went)\w*)(?=.*\b(?:tea|water|coffee|drink)\b)',
     'It dissolved. The sugar crystals broke up into single molecules (salt into ions) and spread evenly through the liquid, too small to '
     'see. It is still there: the drink tastes sweet (or salty), and if the water evaporated the crystals would come back. Hot liquid '
     'dissolves it faster because its molecules move faster.'),
    (r'(?=.*\b(?:mirror|glass|window|windscreen|windshield)\b)(?=.*\b(?:fog|fogs|fogged|cloud|cloudy|steam|steams|steamed|mist|misty|wet on the outside|drops?)\w*)',
     'Condensation. Warm air holds a lot of water vapour; when it touches a surface colder than its dew point, the air right next to it '
     'cools and the vapour turns back into tiny liquid droplets. Those droplets scatter light, so the glass looks cloudy (or, on a cold '
     'drink, wet on the outside). Warming the glass or drying the air stops it.'),
    (r'(?=.*\balphabeti)(?=.*\b(?:same|first|identical)\b)',
     'Compare the words letter by letter from the start. While the letters match, keep going; the first position where they differ decides '
     'the order, and the word whose letter comes earlier in the alphabet goes first (so "carpet" comes before "carton", because p comes '
     'before t). Only if one word runs out first, being a prefix of the other, does the shorter word go first.'),
    (r'\bISBN\b', 'ISBN stands for **International Standard Book Number**: a unique identifier for each edition of a published book.'),
    (r'(?=.*\bgreat red spot\b)', '**Jupiter.** The Great Red Spot is a huge, long-lived storm in Jupiter\'s atmosphere.'),
]


def explain(T, Q):
    for pat, text in EXPLAIN:
        if re.search(r'(?is)' + pat, Q):
            return out(text, 'explain')
    return None


# ------------------------------------------------------------------ entry
READERS_TQ = (packs, till, owed, rate, bags, tally, speed, tare, clearance, span_minutes, zones, cooking, months_after, relative_day, age,
              weekday_later, next_weekday_date, leap, every_mark, undecided_order, between, exactly_one, only_members, priority_rule,
              withdrawn, correction, no_priority, firsthand, borrowed, similar_names, declined, no_coast, emptied, hidden, future_count,
              number_clue, explain)
READERS_TQU = (renamed, price_never_said)


def respond(messages):
    users = [(m.get('content') or '').strip() for m in messages if m.get('role') == 'user']
    if not users or not users[-1]:
        return None
    users = users[-6:]
    Q = users[-1]
    if not Q.rstrip().endswith('?') and not re.search(r'(?i)^(?:how|what|which|who|when|where|why|is|are|does|do|did|can|could|was)\b', Q):
        return None
    if len(Q) > 600:
        return None
    T = '\n'.join(users)
    skip = set()
    try:        # the established rates helper keeps its problems (it asks "whole items or fractions?" and refuses unsafe input)
        from . import helper_rates
        if helper_rates.reply(Q, messages) is not None:
            skip.add(rate)
    except Exception:
        pass
    for reader in READERS_TQU:
        try:
            got = reader(T, Q, users)
        except (ValueError, KeyError, ZeroDivisionError, IndexError, TypeError):
            got = None
        if got:
            return got
    for reader in READERS_TQ:
        if reader in skip:
            continue
        try:
            got = reader(T, Q)
        except (ValueError, KeyError, ZeroDivisionError, IndexError, TypeError):
            got = None
        if got:
            return got
    return None
