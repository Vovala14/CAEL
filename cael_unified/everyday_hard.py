"""Harder everyday shapes (0.4.4 fix after release, 2026-11-22). Test-informed: written after a 56-item hard check in which
CAEL refused or went off-topic on 31 items. Each reader is written for the general shape, not the test wording, and is
checked on fresh wordings it was not written on (tests/test_everyday_hard.py).

Same contract as everyday_exact.py: one shape read completely from the user's turns, or None. Non-neural: regular
expressions, exact arithmetic (fractions), calendar code and exhaustive search.

Shapes:
- sums: a rate with pauses, per-order fees, what is left after sharing equally, packs to buy for a scaled recipe, a
  battery or tank draining at two rates, a fare split when someone gets out halfway, filling or emptying together;
- calendar: the last of N sessions on set weekdays, a flight across time zones, weekdays between two dates, pay for a
  shift past midnight, how often 29 February came round, a meeting time for people in other zones, the Nth day of a year;
- puzzles: who owns which (one each), the fewest steps with two jugs, a number from facts about its digits;
- chat memory: orders changed and dropped, a password or code whose number changed, a list with items crossed off and
  added, a booking moved, money lent and paid back, "the Thursday after next", which bin, swapped slots;
- sources: a notice that applies only on some days, a source that admitted guessing, an adjustment for someone
  else's conditions, a thermometer in the sun, hearsay against a witness;
- trick and unanswerable: riddles with a false premise, a time with no start, a hidden number, a square's diagonal;
- everyday limits: a lift's people and weight limits, the latest time to get up, paint tins, socks in the dark, buy two
  get one free.
"""
import math
import re
from collections import deque
from datetime import date, timedelta
from fractions import Fraction
from itertools import permutations

from . import everyday_exact as ee
from . import word_math as wm

ROUTE = 'chat/exact'
N = wm.STRICT
num = wm.value
fmt = wm.fmt
money = ee.money
DAYS = ee.DAYS
DAY = r'(?:' + '|'.join(DAYS) + r')'
MON = ee.MON
CLOCK = ee.CLOCK
DUR = ee.DUR
CUR = r'[$€£]\s?\d+(?:\.\d+)?'


def out(text, kind):
    return dict(route=f'{ROUTE}-{kind}', response=text, sources=[], reasoning=True, details=f'{kind} (everyday_hard.py)')


def cur(s):
    (sym, v, _), = ee.monies(s)
    return sym, v


def plural(word, n):
    if n == 1:
        return word
    if re.search(r'(?:s|x|ch|sh)$', word):
        return word + 'es'
    if re.search(r'[^aeiou]y$', word):
        return word[:-1] + 'ies'
    return word + 's'


def stem(w):
    w = w.lower().strip()
    if len(w) > 4 and w.endswith('ies'):
        return w[:-3] + 'y'
    if len(w) > 4 and re.search(r'(?:ss|x|z|ch|sh)es$', w):
        return w[:-2]
    if len(w) > 3 and w.endswith('s') and not w.endswith(('ss', 'us', 'is')):
        return w[:-1]
    return w


def listing(xs):
    xs = list(xs)
    if not xs:
        return 'nothing'
    return xs[0] if len(xs) == 1 else ', '.join(xs[:-1]) + ' and ' + xs[-1]


def hm(minutes):
    minutes = Fraction(minutes)
    h, m = divmod(minutes, 60)
    h = int(h)
    m = fmt(m)
    if not h:
        return f'{m} minutes'
    return f'{h} hour{"s" if h != 1 else ""}' + (f' {m} minutes' if m != '0' else '')


DATE = (r'(?:(?P<wd>' + DAY + r'),?\s+)?(?:the\s+)?(?:(?P<d1>\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(?P<m1>' + MON + r')|(?P<m2>' + MON +
        r')\s+(?:the\s+)?(?P<d2>\d{1,2})(?:st|nd|rd|th)?,?)\s+(?P<y>\d{4})')


def dates_in(text):
    got = []
    for m in re.finditer(r'(?i)\b' + DATE + r'\b', text):
        mon = (m['m1'] or m['m2']).lower()
        try:
            d = date(int(m['y']), ee.MONTHS.index(mon) + 1, int(m['d1'] or m['d2']))
        except ValueError:
            continue
        got.append((d, m))
    return got


def show(d):
    return f'{DAYS[d.weekday()].capitalize()} {d.day} {ee.MONTHS[d.month - 1].capitalize()} {d.year}'


def minutes(s):
    return ee.minutes_of(s)


def dur(s):
    return Fraction(ee.duration(s))


# ================================================================== sums
def rate_pauses(T, Q):
    if not re.search(r'(?i)\bhow (?:many (?:seconds|minutes|hours)|long)\b', Q):
        return None
    r = re.search(r'(?i)\b(?P<r>' + N + r')\s+(?P<thing>[a-z]+)\s+(?:a|an|per|each|every)\s+(?P<per>second|minute|hour)\b', T)
    p = re.search(r'(?i)\b(?:paus|stop|rest|break|cool|wait|halt)\w*\b[^.]*?\bfor\s+(?P<d>' + N + r')\s+(?P<du>seconds?|minutes?|hours?)\b[^.]*?\bafter\s+every\s+(?P<k>' + N + r')\s+(?P<kt>[a-z]+)', T) or \
        re.search(r'(?i)\bafter\s+every\s+(?P<k>' + N + r')\s+(?P<kt>[a-z]+)[^.]*?\b(?:paus|stop|rest|break|cool|wait|halt)\w*\b[^.]*?(?:for\s+)?(?P<d>' + N + r')\s+(?P<du>seconds?|minutes?|hours?)\b', T)
    job = re.search(r'(?i)\b(?P<n>\d+)[-\s](?P<jt>[a-z]+)\s+(?:job|run|batch|order|print|task|load)\b', T) or \
        re.search(r'(?i)\b(?:print|make|produce|process|copy|pack|fill|bake|scan|do|finish)(?:es|s|ing)?\s+(?P<n>' + N + r')\s+(?P<jt>[a-z]+)', Q) or \
        re.search(r'(?i)\b(?P<n>' + N + r')\s+(?P<jt>[a-z]+)\b', Q)
    if not (r and p and job):
        return None
    thing = stem(r['thing'])
    if stem(p['kt']) != thing or stem(job['jt']) != thing:
        return None
    per = {'second': Fraction(1, 60), 'minute': Fraction(1), 'hour': Fraction(60)}
    rate = num(r['r']) / per[r['per'].lower()]               # per minute
    n, k = num(job['n']), num(p['k'])
    pause = num(p['d']) * per[p['du'].lower().rstrip('s')]
    if rate <= 0 or k <= 0 or n <= 0:
        return None
    work = n / rate
    stops = int((n - 1) // k)
    total = work + stops * pause
    unit = 'hours' if re.search(r'(?i)how many hours', Q) else 'seconds' if re.search(r'(?i)how many seconds', Q) else 'minutes'
    shown = total / 60 if unit == 'hours' else total * 60 if unit == 'seconds' else total
    things = plural(thing, 2)
    return out(f'**{fmt(shown)} {unit}**: {fmt(n)} {things} at {fmt(num(r["r"]))} a {r["per"].lower()} is {fmt(work)} minutes of work, plus '
               f'{stops} pause{"s" if stops != 1 else ""} of {fmt(pause)} minutes (after every {fmt(k)} {things}, but not after the last one).',
               'rate-pauses')


def order_fees(T, Q):
    if not re.search(r'(?i)how much|\btotal\b|altogether|in all|spend|spent|\bcost\b|pay', Q):
        return None
    each = re.search(r'(?i)(?P<p>' + CUR + r')\s+(?:each|apiece|a (?:ticket|piece|head|seat)|per (?:ticket|item|person|seat|head|one))', T)
    fee = re.search(r'(?i)(?P<f>' + CUR + r')\s+(?:\w+\s+)?(?:fee|charge)\s+(?:per|for each|on each|each)\s+(?P<o>order|booking|transaction|delivery|basket)', T)
    if not (each and fee):
        return None
    qty = list(re.finditer(r'(?i)\b(?:ordered|bought|booked|order(?:ed)?\s+(?:for|of)|booking\s+(?:for|of)|another\s+(?:order|booking)\s+(?:for|of))\s+(?:another\s+)?(?P<q>' + N + r')\b', T))
    if not qty:
        return None
    if len(qty) > 1 and not re.search(r'(?i)\b(?:separate|another|second|new|later|again|different)\b', T):
        return None
    sym, p = cur(each['p'])
    _, f = cur(fee['f'])
    qs = [num(m['q']) for m in qty]
    total = sum(qs) * p + len(qs) * f
    o = fee['o'].lower()
    return out(f'**{money(sym, total)}**: {fmt(sum(qs))} at {money(sym, p)} = {money(sym, sum(qs) * p)}, plus the {money(sym, f)} fee on each of '
               f'{len(qs)} {plural(o, len(qs))} = {money(sym, len(qs) * f)}.', 'order-fees')


CONTAINERS = r'(?:boxes|box|packs?|bags?|packets?|tins?|jars?|cartons?|crates?|trays?|sets?|bundles?|cases?|rolls?|tubs?|sleeves?)'


def leftover(T, Q):
    if not re.search(r'(?i)\b(?:left over|leftover|remain\w*|spare|left)\b', Q):
        return None
    if not re.search(r'(?i)\b(?:same number|equally|evenly|as many (?:each )?as possible|the same amount|equal (?:number|share)s?)\b', T):
        return None
    total, parts = Fraction(0), []
    for m in re.finditer(r'(?i)\b(?P<a>' + N + r')\s+' + CONTAINERS + r'\s+of\s+(?P<b>' + N + r')\b', T):
        total += num(m['a']) * num(m['b'])
        parts.append(f'{fmt(num(m["a"]))} × {fmt(num(m["b"]))}')
    for m in re.finditer(r'(?i)\b(?P<c>' + N + r')\s+(?:loose|extra|spare|single|separate|odd)\b', T):
        total += num(m['c'])
        parts.append(fmt(num(m['c'])))
    share = re.search(r'(?i)\b(?:to|between|among|amongst|for)\s+(?:each\s+of\s+)?(?:the\s+|my\s+)?(?P<n>' + N + r')\s+(?P<who>[a-z]+)', T)
    if not parts or not share or total <= 0:
        return None
    n = num(share['n'])
    if n <= 0 or total.denominator != 1 or n.denominator != 1:
        return None
    each, left = divmod(int(total), int(n))
    return out(f'**{left}**: there are {" + ".join(parts)} = {fmt(total)} in all; {fmt(n)} {share["who"]} get {each} each '
               f'({each * int(n)}), leaving {left}.', 'leftover')


UNITS = {'g': 1, 'gram': 1, 'grams': 1, 'kg': 1000, 'kilo': 1000, 'kilos': 1000, 'kilogram': 1000, 'kilograms': 1000,
         'ml': 1, 'millilitre': 1, 'millilitres': 1, 'milliliter': 1, 'milliliters': 1, 'l': 1000, 'litre': 1000, 'litres': 1000,
         'liter': 1000, 'liters': 1000}
QU = r'(?P<q>\d+(?:\.\d+)?)\s*(?P<u>kg|kilos?|kilograms?|g|grams?|ml|millilit(?:re|er)s?|l|lit(?:re|er)s?)\b'


def packs_needed(T, Q):
    pk = re.search(r'(?i)how many\s+(?P<pk>packs?|packets?|bags?|tins?|jars?|bottles?|cartons?|boxes|blocks?|bars?|tubs?|sachets?)', Q)
    if not pk:
        return None
    base = re.search(r'(?i)\bfor\s+(?P<s>' + N + r')\s+(?:people|persons|servings|guests|portions|adults)\b[^.]*?\b(?:uses?|needs?|takes?|calls? for|requires?)\s+' + QU, T)
    if not base:
        return None
    rest = T[base.end():]
    target = re.search(r'(?i)\b(?:cook|mak|bak|feed|prepar|serv|cater)\w*\s+(?:it\s+|this\s+|them\s+)?for\s+(?P<m>' + N + r')\b', rest) or \
        re.search(r'(?i)\bfor\s+(?P<m>' + N + r')\s+(?:people|persons|guests|of us)\b', rest)
    pack = re.search(r'(?i)\b(?:sold|comes?|available|only)\s+(?:only\s+)?in\s+(?:\w+\s+)?' + QU.replace('?P<q>', '?P<ps>').replace('?P<u>', '?P<pu>'), rest) or \
        re.search(QU.replace('?P<q>', '?P<ps>').replace('?P<u>', '?P<pu>') + r'\s*(?:packs?|packets?|bags?|tins?|jars?|bottles?|cartons?|boxes|blocks?|bars?|tubs?)', rest, re.I)
    if not (target and pack):
        return None
    u1, u2 = UNITS[base['u'].lower()], UNITS[pack['pu'].lower()]
    if {base['u'].lower()[0], pack['pu'].lower()[0]} & {'l', 'm'} and not ({base['u'].lower()[0], pack['pu'].lower()[0]} <= {'l', 'm'}):
        return None             # grams against litres
    need = Fraction(base['q']) * u1 * num(target['m']) / num(base['s'])
    size = Fraction(pack['ps']) * u2
    packs = math.ceil(need / size)
    unit = 'g' if base['u'].lower()[0] in 'gk' else 'ml'
    return out(f'**{packs} {plural(stem(pk["pk"]), packs)}**: {fmt(Fraction(base["q"]))} {base["u"]} for {fmt(num(base["s"]))} is '
               f'{fmt(need)} {unit} for {fmt(num(target["m"]))}, and {fmt(need)} ÷ {fmt(size)} = {fmt(need / size)}, rounded up to whole packs.',
               'packs-needed')


def drain(T, Q):
    if not re.search(r'(?i)\bhow many (?:more )?hours\b|\bhow long\b', Q):
        return None
    start = re.search(r'(?i)\b(?:is at|at|on|has|starts? (?:at|on)|showing)\s+(?P<s>\d+(?:\.\d+)?)\s*%', T)
    target = re.search(r'(?i)\b(?:reach|hit|get to|gets? (?:down )?to|drops? to|falls? to|be (?:at|down to)|down to|goes? down to)\s+(?P<e>\d+(?:\.\d+)?)\s*%', Q + ' ' + T)
    rates = list(re.finditer(r'(?i)(?P<r>\d+(?:\.\d+)?)\s*%\s*(?:an?|per|each|every)\s+hour\s*(?P<ctx>(?:(?!\band\s+\d|\d+(?:\.\d+)?\s*%)[^,.;])*)', T))
    phase = re.search(r'(?i)(?P<ctx>[^.;]*?)\bfor\s+(?P<t>' + N + r')\s+hours?\b(?P<after>[^.]*)', T[rates[-1].end():] if rates else '')
    if not (start and target and len(rates) == 2 and phase):
        return None
    words = lambda s: {stem(w) for w in re.findall(r'[a-z]{4,}', s.lower())} - {'hour', 'then', 'leave', 'just', 'with'}
    act = words(phase['ctx'] + ' ' + phase['after'][:0])
    match = [i for i, r in enumerate(rates) if words(r['ctx']) & act]
    if len(match) != 1:
        return None
    first, second = rates[match[0]], rates[1 - match[0]]
    s, e, t = Fraction(start['s']), Fraction(target['e']), num(phase['t'])
    r1, r2 = Fraction(first['r']), Fraction(second['r'])
    after = s - r1 * t
    if after <= e:
        return out(f'**It reaches {fmt(e)}% before the switch**: {fmt(s)}% − {fmt(t)} × {fmt(r1)}% = {fmt(after)}%.', 'drain')
    h = (after - e) / r2
    return out(f'**{fmt(h)} hours**: {fmt(s)}% − {fmt(t)} hours × {fmt(r1)}% = {fmt(after)}%, then ({fmt(after)} − {fmt(e)}) ÷ {fmt(r2)}% an hour '
               f'= {fmt(h)} hours.', 'drain')


def fare_halfway(T, Q):
    tot = re.search(r'(?i)\b(?:shared|split|took|got)\s+(?:a|an|the)\s+(?P<p>' + CUR + r')\s+(?P<what>taxi|cab|ride|fare|uber|car)', T) or \
        re.search(r'(?i)\b(?:taxi|cab|ride|fare)\s+(?:cost|came to|was)\s+(?P<p>' + CUR + r')', T)
    grp = re.search(r'(?i)\b(?P<g>' + N + r')\s+of\s+us\b', T)
    left = re.search(r'(?i)\b(?P<who>[A-Z][a-z]+)\s+(?:got out|got off|left|was dropped off|hopped out|jumped out)\s+(?:exactly\s+|at\s+the\s+|right\s+)?(?:halfway|half way|half-way)', T)
    if not (tot and grp and left):
        return None
    g = int(num(grp['g']))
    a = re.search(r'(?i)first half[^.]*?\b(?:split|shared|divided)\s+(?P<a>' + N + r')\s+ways', T)
    b = re.search(r'(?i)second half[^.]*?\b(?:split|shared|divided)\s+(?P<b>' + N + r')\s+ways', T) or \
        re.search(r'(?i)second half\s+(?P<b>' + N + r')\s+ways', T)
    a = int(num(a['a'])) if a else g
    b = int(num(b['b'])) if b else g - 1
    if b <= 0 or a <= 0:
        return None
    sym, p = cur(tot['p'])
    half = p / 2
    who = left['who']
    if re.search(r'\b' + who + r'\b', Q):
        return out(f'**{money(sym, half / a)}**: the first half of the fare is {money(sym, half)}, split {a} ways; {who} got out at halfway, '
                   f'so pays nothing towards the second half.', 'fare-halfway')
    if re.search(r'(?i)\b(?:each of the others|the others|i\b|me\b|each of us who stayed|the rest)', Q):
        return out(f'**{money(sym, half / a + half / b)}** each: {money(sym, half)} ÷ {a} for the first half plus {money(sym, half)} ÷ {b} '
                   f'for the second half.', 'fare-halfway')
    return None


def together(T, Q):
    if not re.search(r'(?i)\b(?:together|both|at the same time|at once|all (?:two|three) of them)\b', Q) or \
            not re.search(r'(?i)how long|how many (?:hours|minutes|days)', Q):
        return None
    got, seen = [], set()
    pat = (r'(?P<who>\b(?:[Pp]ipe|[Tt]ap|[Hh]ose|[Pp]ump|[Mm]achine|[Pp]rinter|[Ww]orker|[Dd]rain|[Ii]nlet|[Oo]utlet|[Vv]alve)\s+[A-Z0-9]\w*|\b(?!If\b|It\b|The\b|A\b|An\b|One\b|When\b)[A-Z][a-z]+)'
           r'(?P<mid>[^.;,]*?)\b(?:in|within|takes)\s+(?P<t>' + N + r')\s+(?P<u>hours?|minutes?|days?)')
    for m in re.finditer(pat, T):
        who = m['who'].lower()
        if who in seen:
            continue
        seen.add(who)
        sign = -1 if re.search(r'(?i)\b(?:drain|empt|leak|lets? out)\w*', m['mid']) else 1
        got.append((m['who'], sign, num(m['t']), m['u'].lower().rstrip('s')))
    if len(got) < 2 or len({u for *_, u in got}) != 1:
        return None
    rate = sum(Fraction(s) / t for _, s, t, _ in got)
    if rate <= 0:
        return out('**Never**: it drains at least as fast as it fills.', 'together')
    t = 1 / rate
    unit = got[0][3]
    extra = f' = {hm(t * 60)}' if unit == 'hour' and t.denominator != 1 else ''
    parts = ' + '.join(f'{"−" if s < 0 else ""}1/{fmt(x)}' for _, s, x, _ in got).replace('+ −', '− ')
    return out(f'**{fmt(t)} {unit}s{extra}**: together they do {parts} = {fmt(rate)} of the job per {unit}, so 1 ÷ {fmt(rate)} = {fmt(t)} {unit}s.',
               'together')


# ================================================================== calendar and clock
def sessions(T, Q):
    if not re.search(r'(?i)\b(?:date|when|which day|what day)\b', Q) or not re.search(r'(?i)\blast\b|\bfinal\b|\b\d+(?:st|nd|rd|th)\b', Q):
        return None
    ev = re.search(r'(?i)\b(?:every|each|on)\s+(?P<days>' + DAY + r's?(?:\s*(?:,|and|&)\s*' + DAY + r's?)*)', T)
    count = re.search(r'(?i)\bfor\s+(?P<n>' + N + r')\s+(?P<what>sessions|classes|lessons|meetings|weeks|appointments|visits|games|matches)\b', T)
    ds = dates_in(T)
    if not (ev and count and ds):
        return None
    if re.search(r'(?i)\b(?:except|skip\w*|apart from|half[- ]term|holiday)\b', T) and not re.search(r'(?i)\bno (?:breaks|gaps|holidays)\b', T):
        return None
    wds = sorted({DAYS.index(w.lower().rstrip('s')) if w.lower().rstrip('s') in DAYS else DAYS.index(w.lower())
                  for w in re.findall(r'(?i)' + DAY, ev['days'])})
    start = ds[0][0]
    n = int(num(count['n']))
    nth = re.search(r'(?i)\b(?P<k>\d+)(?:st|nd|rd|th)\s+(?:session|class|lesson|meeting|appointment|visit)', Q)
    if count['what'].lower() == 'weeks':
        if nth:
            return None
        end = start + timedelta(weeks=n)
        d = end - timedelta(days=1)
        while d.weekday() not in wds:
            d -= timedelta(days=1)
        return out(f'**{show(d)}**: the last {listing(DAYS[w].capitalize() for w in wds)} in the {n} weeks from {show(start)}.', 'sessions')
    k = int(nth['k']) if nth else n
    if k > n or k < 1:
        return None
    d, seen, got = start, 0, None
    while seen < k:
        if d.weekday() in wds:
            seen += 1
            got = d
        d += timedelta(days=1)
    note = '' if start.weekday() in wds else ' (the start date is not itself a session day, so counting begins at the next one)'
    return out(f'**{show(got)}**: counting {listing(DAYS[w].capitalize() + "s" for w in wds)} from {show(start)}, session {k} falls there{note}.',
               'sessions')


OFF = r'(?:UTC|GMT)\s*(?P<s{i}>[+\-−])\s*(?P<h{i}>\d{1,2})(?::(?P<m{i}>\d{2}))?|(?:UTC|GMT)(?![+\-−\s]*\d)'


def offsets(text):
    got = []
    for m in re.finditer(r'(?i)\b(?:UTC|GMT)\s*(?:(?P<s>[+\-−])\s*(?P<h>\d{1,2})(?::(?P<m>\d{2}))?)?', text):
        if m['s']:
            v = int(m['h']) * 60 + int(m['m'] or 0)
            got.append((-v if m['s'] in '-−' else v, m))
        else:
            got.append((0, m))
    return got


def flight_zones(T, Q):
    if not re.search(r"(?i)what(?:'s| is| will be)?\s+(?:the\s+)?(?:local\s+)?time|when (?:do|will|does) (?:i|we|it|the \w+) (?:land|arrive|get)", Q):
        return None
    dep =re.search(r'(?i)\b(?:leaves?|departs?|takes? off|left|departed|sets? off)\b[^.]*?\bat\s+(?P<t>' + CLOCK + r')', T)
    d = re.search(r'(?i)\b(?:flight|journey|trip|crossing|it)\s+(?:takes|lasts|is|will take)\s+(?P<d>' + DUR + r'(?:,?\s+(?:and\s+)?\d+\s+minutes?)?)', T)
    offs = offsets(T)
    if not (dep and d and len(offs) == 2):
        return None
    if offs[0][1].start() < dep.start() - 120:
        return None
    t0 = minutes(dep['t'].strip())
    utc = t0 - offs[0][0] + dur(d['d'])
    local = utc + offs[1][0]
    day = int(local // 1440)
    when = {0: 'the same day', 1: 'the next day', -1: 'the day before', 2: 'two days later'}.get(day, f'{day} days later')
    twelve = bool(re.search(r'(?i)am|pm', dep['t']))
    o = lambda v: f'UTC{"+" if v >= 0 else "−"}{abs(v) // 60}' + (f':{abs(v) % 60:02d}' if v % 60 else '')
    return out(f'**{ee.clock(local % 1440, twelve)}** local time, {when}: {dep["t"].strip()} at {o(offs[0][0])} is {ee.clock(utc_mod(t0 - offs[0][0]), False)} UTC; '
               f'plus {hm(dur(d["d"]))} is {ee.clock(utc_mod(utc), False)} UTC, which is {ee.clock(local % 1440, False)} at {o(offs[1][0])}.', 'flight-zones')


def utc_mod(x):
    return int(x) % 1440


def weekdays_between(T, Q):
    if not re.search(r'(?i)how many\s+(?:week ?days|working days|work days|business days|school days)', Q):
        return None
    ds = dates_in(Q) or dates_in(T)
    if len(ds) != 2:
        return None
    a, b = sorted(d for d, _ in ds)
    both = re.search(r'(?i)both (?:ends|days|dates)|inclusive|including (?:both|the first and last)', Q + ' ' + T)
    excl = re.search(r'(?i)\bexclusive\b|not counting|excluding', Q + ' ' + T)
    if excl:
        a, b = a + timedelta(1), b - timedelta(1)
    n = sum((a + timedelta(i)).weekday() < 5 for i in range((b - a).days + 1))
    total = (b - a).days + 1
    how = 'counting both ends' if both or not excl else 'not counting the two end dates'
    return out(f'**{n}**: {show(a)} to {show(b)} is {total} days {how}, of which {n} are Monday to Friday.', 'weekdays')


def shift_pay(T, Q):
    if not re.search(r'(?i)how much|\bworth\b|\bearn|\bpaid\b|\bpay\b|how many (?:paid )?hours', Q):
        return None
    m = re.search(r'(?i)\b(?:from|runs? from|starts? at|begins? at)\s+(?P<a>' + CLOCK + r')\s+(?:to|until|till|and (?:ends|finishes) at|-|–)\s+(?P<b>' + CLOCK + r')', T)
    rate = re.search(r'(?i)(?P<p>' + CUR + r')\s+(?:an|per|a|each)\s+hour', T)
    if not (m and rate) or not re.search(r'(?i)\bshift\b|\bwork\b', T):
        return None
    brk = re.search(r'(?i)(?P<d>\d+)-minute\s+(?P<k>unpaid|paid)?\s*(?:break|lunch|rest)|(?P<d2>' + DUR + r')\s+(?P<k2>unpaid|paid)?\s*(?:break|lunch|rest)|'
                    r'(?P<k3>unpaid|paid)\s+(?:break|lunch|rest)\s+of\s+(?P<d3>' + DUR + r')', T)
    span = (minutes(m['b']) - minutes(m['a'])) % 1440
    off = 0
    if brk:
        kind = (brk['k'] or brk['k2'] or brk['k3'] or 'unpaid').lower()
        length = Fraction(brk['d']) if brk['d'] else dur(brk['d2'] or brk['d3'])
        if kind == 'unpaid':
            off = length
    paid = Fraction(span) - off
    sym, p = cur(rate['p'])
    if re.search(r'(?i)how many (?:paid )?hours', Q):
        return out(f'**{fmt(paid / 60)} hours**: {m["a"].strip()} to {m["b"].strip()} is {hm(span)}' + (f', minus the {fmt(off)}-minute unpaid break.' if off else '.'), 'shift-pay')
    return out(f'**{money(sym, paid / 60 * p)}**: {m["a"].strip()} to {m["b"].strip()} is {hm(span)}' + (f', minus the {fmt(off)}-minute unpaid break' if off else '') +
               f' = {fmt(paid / 60)} paid hours × {money(sym, p)}.', 'shift-pay')


def leap_birthdays(T, Q):
    if not re.search(r'(?i)how many', Q):
        return None
    born = [(d, m) for d, m in dates_in(T) if d.month == 2 and d.day == 29]
    if not born or not re.search(r'(?i)\bborn\b', T):
        return None
    b = born[0][0]
    later = [d for d, m in dates_in(T) if d > b]
    if not later:
        return None
    end = later[-1]
    before = re.search(r'(?i)\bbefore\b', T[born[0][1].end():])
    ys = [y for y in range(b.year + 1, end.year + 1) if ee.is_leap(y) and (date(y, 2, 29) < end if before else date(y, 2, 29) <= end)]
    return out(f'**{len(ys)}**' + (f' ({listing(str(y) for y in ys)})' if ys else '') + f': 29 February only exists in leap years, and between '
               f'{show(b)} and {show(end)} the leap years are {listing(str(y) for y in ys) if ys else "none"}.', 'leap-birthdays')


def meeting_zones(T, Q):
    if not re.search(r'(?i)what time|when is', Q) or not re.search(r'(?i)\b(?:each|both|all) of us\b|\bfor (?:me|us|my \w+|each)\b|\bin [A-Z][a-z]+', Q):
        return None
    base = re.search(r'(?i)\bat\s+(?P<t>' + CLOCK + r')\s+(?P<city>[A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s+time\b', T)
    if not base:
        return None
    ref = base['city']
    people = []
    for m in re.finditer(r"(?P<who>I'?m|I am|[Mm]y\s+[a-z]+(?:\s+is)?|[A-Z][a-z]+\s+is)\s+in\s+(?P<place>[A-Z][a-z]+(?:\s[A-Z][a-z]+)?)[^.]*?\b(?P<h>" + N +
                         r")\s+hours?\s+(?P<dir>behind|ahead of|ahead)\s*(?P<of>[A-Z][a-z]+)?", T):
        if m['of'] and m['of'] != ref.split()[-1] and m['of'] != ref:
            return None
        shift = int(num(m['h'])) * (1 if m['dir'].startswith('ahead') else -1)
        who = m['who']
        who = 'you' if re.match(r"(?i)i'?m|i am", who) else re.sub(r'(?i)^my\s+([a-z]+).*', r'your \1', who).replace(' is', '')
        people.append((who, m['place'], shift))
    if not people:
        return None
    t = minutes(base['t'])
    twelve = bool(re.search(r'(?i)am|pm', base['t']))
    day = lambda x: '' if 0 <= x < 1440 else ' the next day' if x >= 1440 else ' the day before'
    parts = [f'{w} in {p}: **{ee.clock((t + s * 60) % 1440, twelve)}**{day(t + s * 60)} ({base["t"]} {"+" if s >= 0 else "−"} {abs(s)} hours)' for w, p, s in people]
    return out(f'The call is at {base["t"]} in {ref}. For ' + '; for '.join(parts) + '.', 'meeting-zones')


def nth_day(T, Q):
    found = list(re.finditer(r'(?i)\b(?P<n>\d{1,3})(?:st|nd|rd|th)\s+day\s+of\s+(?P<y>\d{4})(?P<more>(?:\s*(?:,|and|or|versus|vs\.?|with)\s*(?:the\s+\d{1,3}(?:st|nd|rd|th)\s+day\s+of\s+|of\s+)?\d{4})*)', T))
    if not found or not re.search(r'(?i)\bwhich|\bwhat|\bwhen|\bcompare', Q):
        return None
    pairs = []
    for m in found:
        pairs.append((int(m['n']), int(m['y'])))
        for y in re.findall(r'\b(\d{4})\b', m['more']):
            pairs.append((int(m['n']), int(y)))
    pairs = list(dict.fromkeys(pairs))
    ds = []
    for n, y in pairs:
        if not 1 <= n <= (366 if ee.is_leap(y) else 365):
            return None
        ds.append(date(y, 1, 1) + timedelta(n - 1))
    if len(ds) == 1:
        return out(f'**{show(ds[0])}**.', 'nth-day')
    if len(ds) != 2:
        return None
    md = lambda d: (d.month, d.day)
    shows = f'{show(ds[0])} and {show(ds[1])}'
    if md(ds[0]) == md(ds[1]):
        return out(f'**Neither**: both fall on the same calendar date ({shows}).', 'nth-day')
    early = min(ds, key=md)
    leap = [d.year for d in ds if ee.is_leap(d.year)]
    why = f' {leap[0]} is a leap year, so 29 February pushes its later days one date earlier.' if len(leap) == 1 and max(md(d) for d in ds) > (2, 28) else ''
    return out(f'**{early.year}**: its day falls on {early.day} {ee.MONTHS[early.month - 1].capitalize()}; the two dates are {shows}.{why}', 'nth-day')


# ================================================================== puzzles
ROLE_VERBS = {'own': ('owns', 'own', 'has', 'have', 'keeps', 'keep'), 'has': ('has', 'have', 'owns', 'own'), 'drink': ('drinks', 'drink', 'ordered', 'order', 'has', 'have'),
              'play': ('plays', 'play'), 'drive': ('drives', 'drive'), 'like': ('likes', 'like'), 'wear': ('wears', 'wear'),
              'choose': ('chose', 'choose', 'picked', 'pick'), 'order': ('ordered', 'order', 'has', 'have'), 'study': ('studies', 'study'),
              'speak': ('speaks', 'speak'), 'bring': ('brought', 'bring', 'brings'), 'grow': ('grows', 'grow'), 'teach': ('teaches', 'teach')}


def assignment(T, Q):
    m = re.search(r'(?P<names>[A-Z][a-z]+(?:\s*,\s*[A-Z][a-z]+)*,?\s+and\s+[A-Z][a-z]+)\s+each\s+(?P<verb>[a-z]+)\s+(?:one|a)\s+(?:different\s+)?(?P<noun>[a-z]+)'
                  r'(?:\s*[:,\-–]\s*|\s+(?:from|out of|among)\s+)(?:namely\s+)?(?P<items>(?:an?\s+|the\s+)?[a-z]+(?:\s[a-z]+)?(?:\s*,\s*(?:an?\s+|the\s+)?[a-z]+(?:\s[a-z]+)?)*,?\s+(?:and|or)\s+(?:an?\s+|the\s+)?[a-z]+(?:\s[a-z]+)?)', T)
    if not m:
        return None
    names = re.findall(r'[A-Z][a-z]+', m['names'])
    items = [re.sub(r'^(?:an?|the)\s+', '', x.strip()) for x in re.split(r'\s*,\s*|\s+(?:and|or)\s+', m['items']) if x.strip()]
    items = [x for x in items if x]
    if len(names) != len(items) or not 2 <= len(names) <= 6:
        return None
    v = m['verb'].lower()
    base = v[:-1] if v.endswith('s') and v[:-1] in ROLE_VERBS else v
    forms = set(ROLE_VERBS.get(base, (v, base)))
    forms |= {v, base}
    VB = r'(?:' + '|'.join(sorted(forms, key=len, reverse=True)) + r')'
    IT = r'(?:the\s+|an?\s+)?(?P<x>' + '|'.join(re.escape(i) for i in sorted(items, key=len, reverse=True)) + r')'
    IT2 = IT.replace('?P<x>', '?P<y>')
    NM = r'(?P<p>' + '|'.join(names) + r')'
    rest = T[m.end():]
    cons = []
    for s in re.split(r'(?<=[.;!])\s+|\n+', rest):
        if s.strip().endswith('?') or not s.strip():
            continue
        hit = False
        for c in re.finditer(NM + r"\s+(?:does\s*n[o']t|doesn'?t|did\s*n[o']t|didn'?t|does not|did not|never)\s+" + VB + r'\s+' + IT, s):
            cons.append(('not', c['p'], c['x'])); hit = True
        for c in re.finditer(NM + r'\s+' + VB + r'\s+neither\s+' + IT + r'\s+nor\s+' + IT2, s):
            cons += [('not', c['p'], c['x']), ('not', c['p'], c['y'])]; hit = True
        for c in re.finditer(NM + r'\s+' + VB + r'\s+(?!neither)' + IT, s):
            cons.append(('is', c['p'], c['x'])); hit = True
        for c in re.finditer(NM + r"(?:'s)?\s+(?:" + re.escape(m['noun']) + r'\s+)?is\s+(?:not\s+|n\'t\s+)?' + IT, s):
            cons.append(('not' if re.search(r"\bnot\b|n't", c[0]) else 'is', c['p'], c['x'])); hit = True
        for c in re.finditer(IT + r'\s+(?:belongs|goes|went)\s+to\s+' + NM, s):
            cons.append(('is', c['p'], c['x'])); hit = True
        for c in re.finditer(r'(?:neither|nor)\s+' + NM, s):
            pass
        if not hit and any(re.search(r'\b' + nm + r'\b', s) for nm in names) and any(i in s.lower() for i in items):
            return None             # a clue we could not read: do not guess
    if not cons:
        return None
    sols = []
    for perm in permutations(items):
        a = dict(zip(names, perm))
        if all((a[p] == x) == (k == 'is') for k, p, x in cons):
            sols.append(a)
    q1 = re.search(r'(?i)\bwho\s+' + VB.replace('(?:', '(?:') + r'\s+' + IT, Q) or re.search(r'(?i)\bwhose\s+(?:' + re.escape(m['noun']) + r'\s+is\s+)?' + IT, Q) or \
        re.search(r'(?i)\b(?:which person|who)\b[^?]*\b' + IT, Q)
    q2 = re.search(r'(?i)\bwhat\s+(?:' + re.escape(m['noun']) + r'\s+)?(?:does|did)\s+' + NM + r'\s+' + VB, Q) or re.search(r'(?i)\bwhat\s+is\s+' + NM + r"'s\s+" + re.escape(m['noun']), Q)
    if not sols:
        return out('**The clues contradict each other**: no way of giving one each fits them all.', 'assignment')
    if q1:
        x = q1['x']
        who = {next(p for p in names if s[p] == x) for s in sols}
        if len(who) == 1:
            w = who.pop()
            full = sols[0] if len(sols) == 1 else None
            extra = (' The only arrangement that fits: ' + '; '.join(f'{p} the {full[p]}' for p in names) + '.') if full else ''
            return out(f'**{w}.**{extra}', 'assignment')
        return out(f'**It can\'t be determined**: it could be {listing(sorted(who))}.', 'assignment')
    if q2:
        p = q2['p']
        what = {s[p] for s in sols}
        if len(what) == 1:
            return out(f'**The {what.pop()}.**', 'assignment')
        return out(f'**It can\'t be determined**: it could be the {" or the ".join(sorted(what))}.', 'assignment')
    return None


def jugs(T, Q):
    js = list(dict.fromkeys(re.findall(r'(?i)\b(?P<c>\d+)[- ](?:litre|liter|l|gallon|pint|cup)\s+(?:jug|bucket|container|can|bottle|jar)', T)))
    goal = re.search(r'(?i)\b(?:exactly|precisely|measure(?: out)?|get|end up with|have)\s+(?:exactly\s+)?(?P<g>\d+)\s+(?:litres?|liters?|l|gallons?|pints?|cups?)'
                     r'(?:\s+in\s+the\s+(?P<which>\d+)[- ](?:litre|liter|l|gallon|pint|cup)\s+\w+)?', T)
    if len(js) != 2 or not goal or not re.search(r'(?i)fewest|minimum|least|smallest number|how many steps|how many moves', T):
        return None
    a, b = int(js[0]), int(js[1])
    g = int(goal['g'])
    which = int(goal['which']) if goal['which'] else None
    if which not in (None, a, b) or a == b:
        return None
    ok = lambda s: (s[0] == g and which in (None, a)) or (s[1] == g and which in (None, b))
    seen = {(0, 0): None}
    q = deque([(0, 0)])
    found = None
    while q:
        s = q.popleft()
        if ok(s):
            found = s
            break
        x, y = s
        moves = [((a, y), f'fill the {a}'), ((x, b), f'fill the {b}'), ((0, y), f'empty the {a}'), ((x, 0), f'empty the {b}'),
                 ((x - min(x, b - y), y + min(x, b - y)), f'pour the {a} into the {b}'), ((x + min(y, a - x), y - min(y, a - x)), f'pour the {b} into the {a}')]
        for n, how in moves:
            if n not in seen:
                seen[n] = (s, how)
                q.append(n)
    if not found:
        return out(f'**It can\'t be done**: no sequence of fills, empties and pours ever leaves exactly {g} litres there.', 'jugs')
    path = []
    s = found
    while seen[s]:
        prev, how = seen[s]
        path.append((how, s))
        s = prev
    path.reverse()
    steps = '; '.join(f'{i + 1}. {how} ({x}, {y})' for i, (how, (x, y)) in enumerate(path))
    return out(f'**{len(path)} steps**: {steps}. The numbers are the litres in the {a} and the {b}; a search of every possible move finds nothing shorter.', 'jugs')


DIGIT = {'hundreds': 0, 'tens': 1, 'units': 2, 'ones': 2, 'first': 0, 'second': 1, 'third': 2, 'last': 2, 'middle': 1}
MULT = {'twice': 2, 'double': 2, 'three times': 3, 'triple': 3, 'four times': 4, 'half': Fraction(1, 2)}


def digits(T, Q):
    size = re.search(r'(?i)\b(?P<k>two|three|four|2|3|4)[- ]digit (?:number|code|pin)', T)
    if not size or not re.search(r'(?i)what is the (?:number|code|pin)|which number|what number|find the', Q + ' ' + T[-80:]):
        return None
    k = {'two': 2, 'three': 3, 'four': 4}.get(size['k'].lower(), None) or int(size['k'])
    pos = dict(DIGIT)
    if k == 2:
        pos = {'tens': 0, 'units': 1, 'ones': 1, 'first': 0, 'second': 1, 'last': 1}
    if k == 4:
        pos = {'thousands': 0, 'hundreds': 1, 'tens': 2, 'units': 3, 'ones': 3, 'first': 0, 'second': 1, 'third': 2, 'fourth': 3, 'last': 3}
    P = r'(?P<a>' + '|'.join(pos) + r')'
    P2 = P.replace('?P<a>', '?P<b>')
    tests = []
    text = T
    for s in re.split(r'(?<=[.;])\s+|,\s+and\s+|\s+and\s+(?=the\s)', text):
        sl = s.lower()
        m = re.search(r'digits\s+(?:that\s+|which\s+)?(?:add up to|adds up to|sum to|total|make)\s+(?P<n>\d+)', sl)
        if m:
            tests.append(lambda d, n=int(m['n']): sum(d) == n); continue
        m = re.search(r'product of (?:the |its )?digits\s+is\s+(?P<n>\d+)', sl)
        if m:
            tests.append(lambda d, n=int(m['n']): math.prod(d) == n); continue
        m = re.search(P + r' digit\s+is\s+(?P<k>\d+)\s+(?P<dir>more|less|greater|smaller|bigger|fewer)\s+than\s+(?:the\s+)?' + P2 + r' digit', sl)
        if m:
            sg = 1 if m['dir'] in ('more', 'greater', 'bigger') else -1
            tests.append(lambda d, a=pos[m['a']], b=pos[m['b']], k=int(m['k']), sg=sg: d[a] == d[b] + sg * k); continue
        m = re.search(P + r' digit\s+is\s+(?P<m>twice|double|three times|triple|four times|half)\s+(?:the\s+)?' + P2 + r' digit', sl)
        if m:
            tests.append(lambda d, a=pos[m['a']], b=pos[m['b']], f=MULT[m['m']]: d[a] == f * d[b]); continue
        m = re.search(P + r' digit\s+is\s+(?:equal to|the same as)\s+(?:the\s+)?' + P2 + r' digit', sl)
        if m:
            tests.append(lambda d, a=pos[m['a']], b=pos[m['b']]: d[a] == d[b]); continue
        m = re.search(P + r' digit\s+is\s+(?P<n>\d)\b', sl)
        if m:
            tests.append(lambda d, a=pos[m['a']], n=int(m['n']): d[a] == n); continue
        m = re.search(r'\b(?:it|the number)\s+is\s+(?P<p>even|odd)', sl)
        if m:
            tests.append(lambda d, p=m['p']: (d[-1] % 2 == 0) == (p == 'even')); continue
        if re.search(r'\bdigit', sl) and re.search(r'\d|twice|more|less|same', sl) and not re.search(r'\b(?:two|three|four|2|3|4)[- ]digit', sl):
            return None             # a digit clue we could not read
    if len(tests) < 2:
        return None
    lo = 10 ** (k - 1)
    sols = [n for n in range(lo, 10 ** k) if all(t([int(c) for c in str(n)]) for t in tests)]
    if len(sols) == 1:
        return out(f'**{sols[0]}**: it is the only {k}-digit number that fits every clue (all {9 * lo} were checked).', 'digits')
    if not sols:
        return out('**No number fits**: the clues contradict each other.', 'digits')
    return out(f'**It can\'t be determined**: {len(sols)} numbers fit, for example {", ".join(map(str, sols[:4]))}.', 'digits')


# ================================================================== chat memory
PRON = r'(?:she|he|they)'


def _subject(s, names, last):
    found = [n for n in re.findall(r'\b[A-Z][a-z]+\b', s) if n in names]
    return found[0] if found else last


ITEM = r"(?P<item>(?!and\b|like\b|too\b|instead\b|now\b|please\b)[a-z]+(?:\s(?!and\b|like\b|too\b|instead\b|now\b|please\b|as\b|for\b)[a-z]+)?)"


def orders(T, Q, users):
    q = re.findall(r'(?i)how many\s+((?:hot\s+|iced\s+|green\s+|herbal\s+|fruit\s+)?[a-z]+)', Q)
    whatq = re.search(r'(?i)what (?:do|should) (?:i|we) order|what(?:\'s| is) the order|what (?:is|does) (?P<who>[A-Z][a-z]+) (?:having|want|getting)', Q)
    if not q and not whatq:
        return None
    want = r"(?:wants?|would like|is having|will have|'ll have|asked for|orders?|ordered|is getting|gets?|takes?)"
    order, names, last = {}, [], None
    for u in users[:-1] + [users[-1].split('?')[0] if '?' in users[-1] else '']:
        for s in re.split(r'(?<=[.!])\s+|\n+', u):
            for m in re.finditer(r'\b(?P<who>[A-Z][a-z]+)\s+' + want + r'\s+(?:an?\s+|the\s+|some\s+|a\s+cup\s+of\s+|one\s+)?' + ITEM, s):
                if m['who'] in ('I', 'We', 'Then', 'And'):
                    continue
                order[m['who']] = m['item'].lower(); names.append(m['who']); last = m['who']
            ch = re.search(r'(?i)\b(?P<who>[A-Z][a-z]+)?\s*(?:has\s+)?(?:changed (?:her|his|their) mind|switched|swapped|would rather|wants something else)', s)
            if ch:
                who = ch['who'] if ch['who'] in order else _subject(s, order, last)
                new = re.search(r"(?i)(?:" + PRON + r"(?:'ll| will| would| wants?| is having)?|to|for|instead)\s+(?:have|take|get|go for|switch to|want)?\s*(?:an?\s+|the\s+|some\s+)?" + ITEM, s[ch.end():])
                same = re.search(r'(?i)\b(?:like|same as|what)\s+(?P<o>[A-Z][a-z]+)', s[ch.end():])
                if who in order:
                    if new and not re.fullmatch(r'(?:the same|same)', new['item']) and new['item'] not in ('have', 'take', 'get', 'what'):
                        order[who] = new['item'].lower()
                    elif same and same['o'] in order:
                        order[who] = order[same['o']]
                    last = who
            gone = re.search(r"(?i)\b(?P<who>[A-Z][a-z]+)\s+(?:has\s+)?(?:just\s+)?(?:left|gone home|had to go|isn'?t coming|is not coming|doesn'?t want anything|cancelled)", s)
            drop = re.search(r"(?i)\b(?:drop|cancel|remove|scrap|forget|skip)\s+(?:(?P<who>[A-Z][a-z]+)'s|his|her|their)\s+(?:order|drink|one)", s)
            if gone and gone['who'] in order:
                order.pop(gone['who']); last = gone['who']
            elif drop:
                who = drop['who'] or (gone['who'] if gone else last)
                order.pop(who, None)
    if len(names) < 2:
        return None
    if whatq and whatq['who']:
        w = whatq['who']
        return out(f'**{order[w]}**.' if w in order else f'**Nothing**: {w}\'s order was dropped.', 'orders')
    counts = {}
    for v in order.values():
        counts[stem(v)] = counts.get(stem(v), 0) + 1
    if q:
        parts = []
        for x in q:
            k = stem(x)
            if k not in counts and k not in {stem(w) for w in re.findall(r'[a-z]+', ' '.join(users[:-1]).lower())}:
                return None             # something never ordered at all: not this shape
            parts.append(f'{counts.get(k, 0)} {plural(k, counts.get(k, 0))}')
        who = '; '.join(f'{p}: {v}' for p, v in order.items())
        return out(f'**{listing(parts)}**: the orders now are {who}.', 'orders')
    return out('**' + listing(f'{n} {plural(k, n)}' for k, n in counts.items()) + '**: ' + '; '.join(f'{p}: {v}' for p, v in order.items()) + '.', 'orders')


def code_change(T, Q, users):
    q = re.search(r"(?i)\bwhat(?:'s| is)\s+(?:my|the|our)\s+(?P<thing>(?:[\w-]+\s){0,2}(?:password|code|pin|passcode|combination|number))(?:\s+now)?", Q)
    if not q:
        return None
    head = q['thing'].split()[-1].lower()
    val = None
    for u in users[:-1]:
        for s in re.split(r'(?<=[.;!])\s+|\n+', u):
            m = re.search(r'(?i)\b(?:my|the|our)\s+(?:[\w-]+\s){0,2}' + head + r'\s+(?:is|was)\s+(?:now\s+)?["\']?(?P<v>[A-Za-z]*[-_ ]?\d+)["\']?', s)
            if m and not re.search(r'(?i)\bchang|\bnew\b|\bnow\b', s):
                val = m['v']; continue
            if val is None:
                continue
            new = re.search(r'(?i)\b(?:changed|updated|reset)\b[^.]*?\bto\s+["\']?(?P<v>[A-Za-z]*[-_ ]?\d+)["\']?', s) or \
                re.search(r'(?i)\bnew\s+' + head + r'\s+is\s+["\']?(?P<v>[A-Za-z]*[-_ ]?\d+)', s)
            if new:
                val = new['v']; continue
            d = re.search(r'(?i)\b(?:number|digits?)\b[^.]*?\b(?:is\s+)?(?P<d>' + N + r')\s+(?P<dir>higher|lower|more|less|bigger|smaller|up|down)\b', s) or \
                re.search(r'(?i)\b(?P<dir>added|add|subtract(?:ed)?|took)\s+(?P<d>' + N + r')\s+(?:to|from|off)\s+the\s+number', s)
            if d:
                tail = re.search(r'(\d+)$', val)
                if not tail:
                    return None
                k = int(num(d['d'])) * (1 if d['dir'].lower() in ('higher', 'more', 'bigger', 'up', 'added', 'add') else -1)
                if re.search(r'(?i)\b(?:different|new) word\b', s):
                    return None
                val = val[:tail.start()] + str(int(tail[1]) + k)
    if val is None:
        return None
    return out(f'**{val}**: the latest change you told me about.', 'code-change')


LIST_ITEM = r'(?:an?\s+|the\s+|my\s+|some\s+)?(?P<x>[a-z][a-z-]*(?:\s[a-z][a-z-]*)?)'


def list_edits(T, Q, users):
    if not re.search(r"(?i)what(?:'s| is| do i)?\s+(?:still\s+)?(?:left|need|remain\w*)|what(?:'s| is)\s+(?:still\s+)?(?:on|in)\s+(?:the|my)\s+(?:list|bag)|how many (?:things|items) (?:are )?(?:left|still)", Q):
        return None
    items, last = None, None
    for u in users[:-1] + [users[-1].rsplit('?', 1)[0].rsplit('.', 1)[0] if '.' in users[-1] else '']:
        start = 0
        if items is None:
            m = re.search(r'(?i)\b(?:[a-z-]+\s+)?list\s*(?:is|has|so far)?\s*:\s*(?P<l>[^.\n]+)', u) or re.search(r'(?i)\b(?:need|pack|bring|buy)\s*:\s*(?P<l>[^.\n]+)', u)
            if not m:
                continue
            items = [re.sub(r'^(?:an?|the|my|some)\s+', '', x.strip().lower()) for x in re.split(r'\s*,\s*|\s+and\s+', m['l']) if x.strip()]
            start = m.end()
        for s in re.split(r'(?<=[.;!])\s+|\n+|\.\s*', u[start:]):
            sl = s.lower()
            here = [x for x in items if re.search(r'\b' + re.escape(x) + r'\b', sl)]
            if here:
                last = here[-1]
            for m in re.finditer(r'\b(?:take|cross|strike|knock|tick|leave)\s+(?:the\s+|my\s+)?(?P<x>[a-z][a-z-]*(?:\s[a-z][a-z-]*)?|it)\s+off\b|'
                                 r'\b(?:take|cross|strike|knock|tick)\s+off\s+(?:the\s+|my\s+)?(?P<x2>[a-z][a-z-]*(?:\s[a-z][a-z-]*)?)|'
                                 r'\b(?:remove|drop|delete|scrap|skip|forget about)\s+(?:the\s+|my\s+)?(?P<x3>[a-z][a-z-]*(?:\s[a-z][a-z-]*)?|it)\b|'
                                 r"\b(?:already\s+|just\s+|have\s+|i\s+)?(?:packed|bought|got|did|done|finished|sent|posted|paid)\s+(?:the\s+|my\s+)?(?P<x4>[a-z][a-z-]*(?:\s(?!so\b|and\b|too\b)[a-z][a-z-]*)?|it|them)\b|"
                                 r"\b(?:don'?t|do not|no longer)\s+need\s+(?:the\s+|my\s+|an?\s+)?(?P<x5>[a-z][a-z-]*(?:\s[a-z][a-z-]*)?|it)\b|\bno need for\s+(?:the\s+|an?\s+)?(?P<x6>[a-z][a-z-]*)", sl):
                x = next(g for g in m.groups() if g)
                if x in ('it', 'them', 'that', 'those'):
                    x = last
                x = _match_item(x or '', items)
                if x:
                    items.remove(x)
            for m in re.finditer(r"\b(?:add|put|include|also need|also pack|don'?t forget)\s+(?:on\s+)?(?:an?\s+|the\s+|some\s+|my\s+)?(?P<x>[a-z][a-z-]*(?:\s(?!to\b|and\b|on\b|too\b|as\b)[a-z][a-z-]*)?)", sl):
                x = m['x'].strip()
                if x not in items and x not in ('it', 'that', 'them'):
                    items.append(x)
                    last = x
    if items is None:
        return None
    if re.search(r'(?i)how many', Q):
        return out(f'**{len(items)}**: {listing(items)}.', 'list-edits')
    return out(f'**{listing(items).capitalize() if items else "Nothing"}**' + ('.' if items else ': everything has been crossed off.'), 'list-edits')


def _match_item(x, items):
    x = x.strip().lower()
    if x in items:
        return x
    for i in items:
        if stem(i) == stem(x) or i.split()[-1] == x or x.split()[-1] == i:
            return i
    first = x.split()[0]
    for i in items:
        if i == first:
            return i
    return None


def booking(T, Q, users):
    if not re.search(r'(?i)\bwhat\s+(?:table|room|seat|gate|platform|time)\b|\bwhich\s+(?:table|room|seat|gate|platform)\b|\bwhen\s+(?:is|are)\s+(?:we|our|the|my)\b', Q):
        return None
    KIND = r'(?P<k>table|room|seat|gate|platform|court|pitch|desk|bay)'
    slot, kind, t, twelve, changed = None, None, None, False, 0
    for u in users[:-1]:
        for s in re.split(r'(?<=[.;!])\s+|\n+', u):
            m = re.search(r'(?i)\b' + KIND + r'\s+(?P<n>\d+[A-Za-z]?)\b', s)
            if m:
                if slot is not None:
                    changed += 1
                slot, kind = m['n'], m['k'].lower()
            c = re.search(r'(?i)\b(?:at|for)\s+(?P<t>' + CLOCK + r')', s)
            if c and not re.search(r'(?i)same time', s):
                if t is not None:
                    changed += 1
                t, twelve = minutes(c['t']), bool(re.search(r'(?i)am|pm', c['t']))
            mv = re.search(r'(?i)\b(?P<dir>push|pushed|move|moved|put|delay|delayed|bring|brought|pull|pulled)\b[^.]*?\b(?P<w>back|forward|later|earlier)?\s*(?:by\s+)?(?P<d>' + DUR + r'|an hour|half an hour)(?P<w2>\s+(?:later|earlier))?', s)
            if mv and t is not None and not c:
                d = 60 if mv['d'].lower() == 'an hour' else 30 if mv['d'].lower() == 'half an hour' else dur(mv['d'])
                way = (mv['w'] or mv['w2'] or '').strip().lower()
                if mv['dir'].lower().startswith(('bring', 'brought', 'pull')) or way in ('forward', 'earlier'):
                    d = -d
                elif not way and not mv['dir'].lower().startswith('delay'):
                    return None
                t += d
                changed += 1
    if slot is None or not changed or re.search(r'(?i)\b' + DAY + r'\b|\btomorrow\b', T):
        return None             # a table, room or court that moved; a change of day is time_moved's or the reasoner's
    parts = []
    if slot is not None and re.search(r'(?i)\b(?:table|room|seat|gate|platform|court|pitch|desk|bay)\b', Q):
        parts.append(f'{kind.capitalize()} {slot}')
    if t is not None and re.search(r'(?i)\btime\b|\bwhen\b', Q):
        parts.append(ee.clock(t, twelve))
    if not parts:
        return None
    return out(f'**{" at ".join(parts)}**: after the changes you told me about.', 'booking')


def debts(T, Q, users):
    if not re.search(r'(?i)how much (?:am i|are we) owed|how much (?:does|do) (?P<w>[A-Z][a-z]+)\s+(?:still\s+)?owe|how much (?:is|are) (?:still )?owed|owed in total', Q):
        return None
    bal, last, sym = {}, None, None
    for u in users[:-1] + [users[-1].rsplit('?', 1)[0] if '.' in users[-1] else '']:
        for s in re.split(r'(?<=[.;!])\s+|,\s*then\s+|\s+then\s+|\n+', u):
            m = re.search(r'(?i)\blent\s+(?P<list>[A-Z][a-z]+\s+' + CUR + r'(?:\s*(?:,|and)\s*[A-Z][a-z]+\s+' + CUR + r')*)', s)
            if m:
                for p in re.finditer(r'(?P<who>[A-Z][a-z]+)\s+(?P<a>' + CUR + r')', m['list']):
                    sy, v = cur(p['a']); sym = sym or sy
                    bal[p['who']] = bal.get(p['who'], 0) + v; last = p['who']
                continue
            m = re.search(r'(?i)\blent\s+(?P<a>' + CUR + r')\s+to\s+(?P<who>[A-Z][a-z]+)', s)
            if m:
                sy, v = cur(m['a']); sym = sym or sy
                bal[m['who']] = bal.get(m['who'], 0) + v; last = m['who']; continue
            who = _subject(s, bal, last)
            if who not in bal:
                continue
            last = who
            pb = re.search(r'(?i)\b(?:paid|given|gave|handed)\s+(?:me\s+)?back\s+(?P<a>' + CUR + r'|half|a third|a quarter|everything|all(?: of it)?|the lot|in full|the whole \w+)|'
                           r'\brepaid\s+(?P<a2>' + CUR + r'|half|everything|all of it|in full)|\bpaid\s+(?:me\s+)?(?P<a3>' + CUR + r')\s+back|'
                           r'\b(?:pays?|paid|gives?|gave|returns?|returned|sends?|sent)\s+(?:me\s+)?(?:back\s+)?(?:another|a further|an extra|a second)\s+(?P<a4>' + CUR + r')', s)
            if pb:
                a = (pb['a'] or pb['a2'] or pb['a3'] or pb['a4']).lower()
                if re.match(r'[$€£]', a):
                    bal[who] -= cur(a)[1]
                elif a == 'half':
                    bal[who] -= bal[who] / 2
                elif a in ('a third', 'a quarter'):
                    bal[who] -= bal[who] * (Fraction(1, 3) if 'third' in a else Fraction(1, 4))
                else:
                    bal[who] = 0
            br = re.search(r'(?i)\b(?:borrowed|took|asked for)\s+(?:another|a further|an extra|a new|more|)\s*(?P<a>' + CUR + r')', s)
            if br:
                bal[who] += cur(br['a'])[1]
    if len(bal) < 1 or sym is None:
        return None
    w = re.search(r'(?i)how much (?:does|do) (?P<w>[A-Z][a-z]+)', Q)
    if w and w['w'] in bal:
        return out(f'**{money(sym, bal[w["w"]])}**.', 'debts')
    total = sum(bal.values())
    return out(f'**{money(sym, total)}**: ' + '; '.join(f'{p} owes {money(sym, v)}' for p, v in bal.items()) + '.', 'debts')


def weekday_after_next(T, Q, users):
    if not re.search(r"(?i)what(?:'s| is)\s+the\s+date|which date|what date", Q):
        return None
    today = None
    for d, m in dates_in(T):
        if re.search(r'(?i)\btoday(?:\'s| is)\b[^.]{0,12}$', T[max(0, m.start() - 20):m.start()]):
            today = d
    if today is None:
        return None
    pick = None
    for u in users:
        for m in re.finditer(r'(?i)(?P<neg>\bnot\s+)?(?:the\s+)?(?P<a>' + DAY + r')\s+after\s+next|(?P<neg2>\bnot\s+)?\b(?P<b>this coming|this|coming|next|a week on)\s+(?P<wd>' + DAY + r')|(?P<neg3>\bnot\s+)?\bon\s+(?P<c>' + DAY + r')\b', u):
            if m['neg'] or m['neg2'] or m['neg3']:
                continue
            if m['a']:
                pick = (DAYS.index(m['a'].lower()), 1)
            elif m['b']:
                k = {'this coming': 0, 'this': 0, 'coming': 0, 'next': 0, 'a week on': 1}[m['b'].lower()]
                pick = (DAYS.index(m['wd'].lower()), k)
            else:
                pick = (DAYS.index(m['c'].lower()), 0)
    if pick is None:
        return None
    wd, extra = pick
    ahead = (wd - today.weekday()) % 7 or 7
    d = today + timedelta(days=ahead + 7 * extra)
    return out(f'**{show(d)}**: today is {show(today)}, the coming {DAYS[wd].capitalize()} is the {(today + timedelta(ahead)).day}th'.replace('1th', '1st').replace('2th', '2nd').replace('3th', '3rd').replace('11st', '11th').replace('12nd', '12th').replace('13rd', '13th') +
               (f', and the one after that is the {d.day}th.' if extra else '.'), 'after-next')


def bins(T, Q, users):
    q = re.search(r'(?i)\bwhere\s+(?:do|does|should|would)\s+(?P<items>.+?)\s+go\b|which bins?\s+(?:do|does|should)\s+(?P<items2>.+?)\s+go', Q)
    if not q:
        return None
    rules, rest = [], None
    for m in re.finditer(r'(?i)\b(?P<bin>[a-z]+)(?:\s+bin)?\s+(?:is\s+)?for\s+(?P<cat>[a-z ]+?)(?=\s*(?:,|\.|;|\band\b|$))', T):
        cat = m['cat'].strip().lower()
        if re.search(r'everything else|anything else|the rest|general waste|all other', cat):
            rest = m['bin'].lower()
        else:
            rules.append((stem(cat.split()[-1]), m['bin'].lower(), False))
    for m in re.finditer(r'(?i)\b(?P<item>[a-z]+(?:\s[a-z]+)?)\s+(?:now\s+|also\s+)?(?:go|goes)\s+(?:in|into)\s+the\s+(?P<bin>[a-z]+)\s+bin', T):
        item = re.sub(r'(?i)^(?:that|today|from today|now)\s+', '', m['item'].lower())
        rules.append((stem(item), m['bin'].lower(), True))
    if not rules:
        return None
    items = [re.sub(r'^(?:an?|the|my|some)\s+', '', x.strip().lower()) for x in re.split(r'\s*,\s*|\s+and\s+', q['items'] or q['items2']) if x.strip()]
    got = []
    for it in items:
        s = ' '.join(stem(w) for w in it.split())
        bin_ = None
        for key, b, explicit in reversed(rules):
            if explicit and (key == s or key.endswith(' ' + s) or s.endswith(key)):
                bin_ = (b, 'the newer rule')
                break
        if not bin_:
            for key, b, explicit in rules:
                if not explicit and re.search(r'\b' + re.escape(key) + r'\b', s):
                    bin_ = (b, f'it is {key}')
                    break
        if not bin_ and rest:
            bin_ = (rest, 'everything else')
        if not bin_:
            return None
        got.append(f'the {it}: **{bin_[0]}** ({bin_[1]})')
    return out('; '.join(got).capitalize() + '.', 'bins')


SLOT = r'(?P<k>' + MON + r'|' + DAY + r'|week \d+|day \d+|round \d+|slot \d+)'


def slots(T, Q, users):
    if not re.search(r'(?i)\b(?:which|what|who|whose)\b', Q):
        return None
    TITLE = r"(?P<v>[A-Z][\w'’-]*(?:\s(?:of|the|and|[A-Z][\w'’-]*))*)"
    board = {}
    for u in users[:-1]:
        for s in re.split(r'(?<=[.;!])\s+|\n+', u):
            for m in re.finditer(r'(?i)\b' + SLOT + r'\s*(?:is|:|=|will be|-)\s*' + TITLE.replace('[A-Z]', '[A-Z]'), s):
                if m['k'].lower() not in board or not board:
                    board[m['k'].lower()] = m['v'].strip()
            sw = re.search(r'(?i)\bswap(?:ped)?\s+' + SLOT.replace('?P<k>', '?P<a>') + r'\s+(?:and|with)\s+' + SLOT.replace('?P<k>', '?P<b>'), s)
            if sw:
                a, b = sw['a'].lower(), sw['b'].lower()
                if a in board and b in board:
                    board[a], board[b] = board[b], board[a]
            rp = re.search(r'(?i)\breplace[ds]?\s+(?:whatever is\s+(?:now\s+)?(?:in|on|for)\s+|the\s+\w+\s+(?:in|for|on)\s+|)' + SLOT + r"(?:'s\s+\w+)?\s+with\s+" + TITLE, s)
            if rp and rp['k'].lower() in board:
                board[rp['k'].lower()] = rp['v'].strip()
    if len(board) < 2:
        return None
    q = re.search(r'(?i)\b(?:in|on|for)\s+' + SLOT + r'\b', Q)
    if q and q['k'].lower() in board:
        return out(f'**{board[q["k"].lower()]}**: ' + '; '.join(f'{k.capitalize()}: {v}' for k, v in board.items()) + '.', 'slots')
    return None


# ================================================================== sources
def scoped_notice(T, Q):
    if not re.search(r'(?i)\bwhen\b|\bwhat time\b', Q):
        return None
    base = re.search(r'(?i)\b(?:timetable|schedule|sign|website|leaflet|poster|app)\b[^.]*?\b(?:says|lists|shows|said|gives)\b[^.]*?(?P<t>' + CLOCK + r')', T)
    new = re.search(r'(?i)\b(?:notice|update|announcement|email|message|letter|sign)\b[^.]*?(?P<t>' + CLOCK + r')[^.]*?\b(?:on\s+)?(?P<scope>weekdays|weekends|' + DAY + r's)\s+only\b', T) or \
        re.search(r'(?i)\b(?:notice|update|announcement|email|message|letter)\b[^.]*?\b(?:on\s+)?(?P<scope>weekdays|weekends|' + DAY + r's)\s+only\b[^.]*?(?P<t>' + CLOCK + r')', T)
    today = re.search(r'(?i)\btoday(?:\'s| is)\s+(?:a\s+)?(?P<wd>' + DAY + r')', T)
    if not (base and new and today) or base['t'] == new['t']:
        return None
    wd = DAYS.index(today['wd'].lower())
    sc = new['scope'].lower()
    applies = wd < 5 if sc == 'weekdays' else wd >= 5 if sc == 'weekends' else DAYS[wd] == sc.rstrip('s')
    if applies:
        return out(f'**{new["t"]}**: the newer notice applies on {sc}, and today is a {DAYS[wd].capitalize()}.', 'scoped-notice')
    return out(f'**{base["t"]}**: the change to {new["t"].strip()} applies on {sc} only, and today is a {DAYS[wd].capitalize()}, so the usual time stands.',
               'scoped-notice')


VALUE = r'(?P<v>room\s+\w+|gate\s+\w+|platform\s+\w+|table\s+\w+|floor\s+\w+|' + CLOCK + r'|' + DAY + r'|' + CUR + r')'
UNSURE = (r"(?:only\s+)?(?:been\s+)?(?:guessing|guessed|wasn'?t sure|was not sure|made it up|didn'?t (?:really |actually )?know|was wrong|got it wrong|"
          r"misremembered|was mistaken|had it wrong|wasn'?t certain)")


def credibility(T, Q):
    if not re.search(r'(?i)\bwhich\b|\bwhat\b|\bwhere\b|\bwhen\b', Q):
        return None
    claims = []
    for m in re.finditer(r'(?P<who>[A-Z][a-z]+)(?:,\s*who\s+(?P<role>[^,]+),)?\s+(?:told me|told us|said|says|emailed\s+\w+|texted\s+\w+|wrote|announced|posted|messaged\s+\w+|confirmed|insists)'
                         r'\s+(?:that\s+)?(?P<what>[^.]+)', T):
        v = re.search(r'(?i)\b' + VALUE, m['what'])
        if v:
            claims.append((m['who'], m['role'], v['v'], m['what'].strip()))
    if len(claims) < 2 or len({c[2].lower() for c in claims}) < 2:
        return None
    took = {m['who'] for m in re.finditer(r'(?P<who>[A-Z][a-z]+)\s+(?:later\s+|then\s+)?(?:admitted|said|confessed|conceded|told me|texted)\s+(?:that\s+)?(?:she|he|they)\s*(?:\'d|had|was|were)?\s*' + UNSURE, T)}
    left = [c for c in claims if c[0] not in took]
    if took and len({c[2].lower() for c in left}) == 1:
        c = left[0]
        role = f', who {c[1].strip()},' if c[1] else ''
        return out(f'**{c[2][0].upper() + c[2][1:]}**: {listing(sorted(took))} admitted to guessing, which leaves {c[0]}{role} saying {c[2]}.', 'credibility')
    if not took:
        auth = [c for c in claims if c[1] and re.search(r'(?i)\b(?:booked|organis|organiz|runs?|manages?|arranged|chairs?|owns?|set up|is in charge)', c[1])]
        if len(auth) == 1:
            c = auth[0]
            return out(f'**{c[2][0].upper() + c[2][1:]}** is the better bet: {c[0]} {c[1].strip()}, so is the one who would know.', 'credibility')
    return None


CONDITIONS = r'(?P<cond>runs? hot|runs? cold|runs? fast|runs? slow|is (?:a )?fan|is (?:very )?(?:hot|cold|strong|weak|old|small|big)|is at altitude|is slow|is fast)'


def adjusted_for_other(T, Q):
    if not re.search(r'(?i)how long|how many|what temperature|how hot|how much', Q):
        return None
    base = re.search(r'(?i)\b(?:recipe(?: card)?|instructions?|label|packet|manual|guide|pack|box)\s+(?:says|said|states|reads|tells you)\s+(?:to\s+)?(?:\w+\s+){0,3}?(?:for\s+)?(?P<v>\d+)\s*(?P<u>minutes|mins|hours|degrees|°C|°F|days)', T)
    adj = re.search(r'(?i)\b(?:my|her|his|their)\s+(?P<thing>[a-z]+)\s+' + CONDITIONS + r'[^.\d]*?(?P<v2>\d+)', T)
    mine = re.search(r'(?i)\bmy\s+(?P<thing>[a-z]+)\s+(?:is|runs|is just)\s+(?P<m>normal|standard|average|fine|ordinary|regular|accurate|typical|not\s+\w+|(?:a\s+)?(?:hot|cold|fan|fast|slow))\b', T[adj.end():] if adj else '')
    if not (base and adj and mine) or stem(mine['thing']) != stem(adj['thing']):
        return None
    cond = re.sub(r'^(?:runs?|is)\s+(?:a\s+|very\s+)?', '', adj['cond'].lower())
    m = mine['m'].lower()
    same = re.sub(r'^a\s+', '', m) == cond
    if same:
        return out(f'**{adj["v2"]} {base["u"]}**: your {mine["thing"]} {adj["cond"]} too, so the adjusted figure fits you.', 'adjusted')
    return out(f'**{base["v"]} {base["u"]}**, as the {base[0].split()[0].lower()} says: the {adj["v2"]} was an adjustment for {"an" if adj["thing"][0] in "aeiou" else "a"} {adj["thing"]} that '
               f'{adj["cond"]}, and yours is {m}.', 'adjusted')


HOT = r'(?:direct sun(?:light)?|the sun|sunlight|a sunny window|a radiator|the radiator|radiator|a heater|the heater|heater|the oven|oven|the stove|stove|a fire|the fire|fireplace|a lamp|the lamp|kettle|the kettle)'
COLD = r'(?:a draught|draught|draft|the fridge|fridge|freezer|air ?con\w*|an open window|the open window|a fan|the fan|an air vent|the vent|vent)'


def biased_reading(T, Q):
    if not re.search(r'(?i)best estimate|actual|real|true|which (?:one|reading|figure)|what(?:\'s| is) the (?:room )?temperature|how (?:hot|warm|cold)', Q):
        return None
    m = re.search(r'(?i)\b(?:read|show|say|give)\s+(?P<a>-?\d+(?:\.\d+)?)\s*(?P<u>°\s*[CF]|degrees(?:\s+\w+)?)?\s+and\s+(?P<b>-?\d+(?:\.\d+)?)\s*(?P<u2>°\s*[CF]|degrees(?:\s+\w+)?)', T)
    if not m:
        return None
    a, b = m['a'], m['b']
    u = (m['u2'] or m['u'] or '').replace(' ', '')
    bias = re.search(r'(?i)\b(?:the\s+)?(?P<v>-?\d+(?:\.\d+)?)\s*(?:°\s*[CF]|degrees?)?\s*(?:one|reading|thermometer|gauge)?\s+(?:sits|is|was|hangs|stands|is placed|is mounted|is kept)\s+'
                     r'(?:right\s+|directly\s+)?(?:in|by|next to|near|above|on|beside|over|under)\s+(?P<c>' + HOT + r'|' + COLD + r')', T)
    if not bias or bias['v'] not in (a, b):
        return None
    other = b if bias['v'] == a else a
    hot = re.fullmatch(r'(?i)' + HOT, bias['c'])
    if hot and Fraction(bias['v']) < Fraction(other) or not hot and Fraction(bias['v']) > Fraction(other):
        return None
    return out(f'**About {other} {u}**: the {bias["v"]} {u} reading is {"pushed up" if hot else "pulled down"} by {bias["c"]}, so the other one is the fair reading of the room.',
               'biased-reading')


def hearsay(T, Q):
    if not re.search(r'(?i)\breliable|\btrust|\bwhose|\bwhat time|\bwhen did', Q):
        return None
    direct = re.search(r'(?P<a>[A-Z][a-z]+)\s+(?:says|said)\s+(?:that\s+)?(?:she|he|they)\s+(?:saw|watched|heard|noticed|was there when|signed for)\s+[^.]*?\b(?:at|around|about)\s+(?P<t>' + CLOCK + r'|\d{1,2})\b', T)
    rep = re.search(r'(?P<b>[A-Z][a-z]+)\s+(?:says|said)\s+(?:that\s+)?(?P<a>[A-Z][a-z]+)\s+(?:told|said to)\s+(?:her|him|them|me)\b[^.]*?\b(?:at|around|about)\s+(?P<t>' + CLOCK + r'|\d{1,2})\b', T)
    if not (direct and rep) or rep['a'] != direct['a']:
        return None
    t = direct['t']
    if re.fullmatch(r'\d{1,2}', t):
        t += re.search(r'(?i)\b(am|pm)\b', T)[1] if re.search(r'(?i)\b(am|pm)\b', T) else ''
    return out(f'**{direct["a"]}\'s: {t}**. {direct["a"]} saw it; {rep["b"]} is only repeating what {direct["a"]} said, and second-hand retelling is where '
               f'details like the time drift.', 'hearsay')


# ================================================================== trick and unanswerable
RIDDLES = [
    (r'\bsurvivors?\b.*\bburied\b|\bburied\b.*\bsurvivors?\b', '**Nowhere**: survivors are alive, so they aren\'t buried.'),
    (r'\bmoses\b.*\b(?:ark|animals?)\b', '**None**: it was Noah, not Moses, who took animals onto the ark (in the story).'),
    (r'\broosters?\b.*\begg\b', '**There is no egg**: roosters don\'t lay eggs.'),
    (r'\belectric train\b.*\bsmoke\b', '**There is no smoke**: an electric train doesn\'t make any.'),
    (r'\b(?:kilo|kilogram|pound|tonne|ton)\s+of\s+feathers\b.*\b(?:kilo|kilogram|pound|tonne|ton)\s+of\s+\w+|\b(?:kilo|kilogram|pound|tonne|ton)\s+of\s+\w+\b.*\b(?:kilo|kilogram|pound|tonne|ton)\s+of\s+feathers',
     '**They weigh the same**: a kilo is a kilo, whatever it is made of.'),
    (r'\bhow many birthdays\b.*\baverage\b', '**One**: you are born once; everything after is an anniversary of it.'),
    (r'\bsheep\b.*\ball but\s+(?P<n>\d+)\b.*\b(?:die|died)\b', None),
]


def riddles(T, Q):
    text = (T + ' ' + Q).lower()
    for pat, ans in RIDDLES:
        m = re.search(pat, text)
        if m:
            if ans is None:
                return out(f'**{m["n"]}**: "all but {m["n"]}" died means {m["n"]} are left.', 'riddle')
            return out(ans, 'riddle')
    return None


def no_start(T, Q):
    if not re.search(r'(?i)\bwhat time\b|\bwhen\b', Q) or not re.search(r'(?i)\b(?:arriv|land|finish|end|get (?:in|there|back|home)|done|ready)\w*', Q):
        return None
    if re.search(r'\b(?:' + CLOCK + r')(?![a-z])', T, re.I) or re.search(r'(?i)\bnow\b|\bnoon\b|\bmidnight\b|\bo\'?clock\b|\bdawn\b', T):
        return None
    if not re.search(r'(?i)\b(?:sometime|some time|at some point|earlier|this morning|this afternoon|this evening|in the morning|yesterday|today)\b', T):
        return None
    d = re.search(r'(?i)\b(?:took|takes|lasted|lasts|for)\s+(?P<d>' + DUR + r'|an hour|half an hour)', T)
    if not d:
        return None
    return out(f'**It can\'t be determined**: you said how long it took ({d["d"]}), but not when it started. Arrival = departure time + {d["d"]}.', 'no-start')


def hidden_number(T, Q):
    m = re.search(r'(?i)\b(?:thinking of|picked|chosen|chose|have)\s+(?:a|an)\s+(?:whole\s+|secret\s+|random\s+)?(?:number|integer)\s+(?:from|between)\s+(?P<a>-?\d+)\s+(?:and|to)\s+(?P<b>-?\d+)', T)
    if not m:
        return None
    lo, hi = sorted((int(m['a']), int(m['b'])))
    excl = re.search(r'(?i)\bbetween\b', m[0]) and not re.search(r'(?i)inclusive|including', T)
    span = list(range(lo, hi + 1))
    q = Q.lower()
    tests = {r'\beven\b': lambda n: n % 2 == 0, r'\bodd\b': lambda n: n % 2 == 1,
             r'\bprime\b': lambda n: n > 1 and all(n % k for k in range(2, int(n ** 0.5) + 1))}
    for pat, f in tests.items():
        if re.search(r'\bis it\b[^?]*' + pat, q):
            if all(f(n) for n in span):
                return out('**Yes**: every number in that range is.', 'hidden-number')
            if not any(f(n) for n in span):
                return out('**No**: no number in that range is.', 'hidden-number')
            return out('**It can\'t be determined**: you haven\'t said which number it is, and the range has both kinds.', 'hidden-number')
    if re.search(r'\bwhat(?:\'s| is) (?:it|the number|my number)|which number|guess', q):
        return out(f'**It can\'t be determined**: it could be any of the numbers from {lo} to {hi}' + (' (or just strictly between them)' if excl else '') + '.', 'hidden-number')
    return None


def shapes(T, Q):
    q = Q.lower()
    want = re.search(r'\b(diagonal|area|perimeter|side|circumference|radius|diameter)\b', q)
    if not want:
        return None
    unit = re.search(r'(?i)\d\s*(?P<u>mm|cm|m|km|inches|inch|in|ft|feet)(?![a-z])', T)
    u = unit['u'] if unit else ''
    w = want[1]
    sq = re.search(r'(?i)\bsquare\b[^.?]*?\b(?:has\s+)?(?:a|an|its|the)?\s*(?P<k>perimeter|area|side|diagonal)\s+(?:length\s+)?(?:of|is)\s+(?P<v>\d+(?:\.\d+)?)', T)
    if sq:
        v = Fraction(sq['v'])
        k = sq['k'].lower()
        side = {'perimeter': v / 4, 'side': v}.get(k)
        if k == 'area':
            r = math.isqrt(int(v)) if v.denominator == 1 else None
            side = Fraction(r) if r is not None and r * r == v else Fraction(math.sqrt(v)).limit_denominator(1000)
        if k == 'diagonal':
            side = None
        if side is None:
            if w == 'side':
                return out(f'**{fmt(v)}/√2 ≈ {float(v) / math.sqrt(2):.2f} {u}**.', 'shape')
            if w == 'area':
                return out(f'**{fmt(v * v / 2)} {u}²**: area = diagonal² ÷ 2.', 'shape')
            return None
        if w == 'diagonal':
            return out(f'**{fmt(side)}√2 ≈ {float(side) * math.sqrt(2):.2f} {u}**: the side is {fmt(side)} {u}' + (f' ({fmt(v)} ÷ 4)' if k == 'perimeter' else '') +
                       ', and the diagonal of a square is the side × √2.', 'shape')
        if w == 'area':
            return out(f'**{fmt(side * side)} {u}²**: the side is {fmt(side)} {u}.', 'shape')
        if w == 'perimeter':
            return out(f'**{fmt(4 * side)} {u}**: 4 × {fmt(side)}.', 'shape')
        if w == 'side':
            return out(f'**{fmt(side)} {u}**.', 'shape')
    ci = re.search(r'(?i)\bcircle\b[^.?]*?\b(?:has\s+)?(?:a|an|its|the)?\s*(?P<k>radius|diameter|circumference)\s+(?:of|is)\s+(?P<v>\d+(?:\.\d+)?)', T)
    if ci:
        v = float(ci['v'])
        r = {'radius': v, 'diameter': v / 2, 'circumference': v / (2 * math.pi)}[ci['k'].lower()]
        got = {'area': (math.pi * r * r, f'{u}²', 'π × r²'), 'circumference': (2 * math.pi * r, u, '2 × π × r'), 'radius': (r, u, ''), 'diameter': (2 * r, u, '')}.get(w)
        if got:
            return out(f'**About {got[0]:.2f} {got[1]}**' + (f': {got[2]} with r = {r:g} {u}.' if got[2] else '.'), 'shape')
    return None


# ================================================================== everyday limits
def lift(T, Q):
    if not re.search(r'(?i)\bcan (?:they|we|all|everyone|it)|one trip|together|\bfit\b|\bsafe\b|\ballowed\b|go up together', Q):
        return None
    lim = re.search(r'(?i)\b(?:rated|limit\w*|max\w*|capacity|takes|holds|carries)\s+(?:is\s+|of\s+|for\s+|at\s+)?(?P<p>' + N + r')\s+(?:people|persons|passengers)\s+(?:or|and|/)\s+(?P<kg>\d+(?:\.\d+)?)\s*kg', T)
    grp = re.search(r'(?i)\b(?P<n>' + N + r')\s+(?:people|persons|passengers|adults|friends|workers)\b[^.]*?\b(?:averag\w*|weigh\w*|of|at)\s+(?:about\s+)?(?P<w>\d+(?:\.\d+)?)\s*kg', T)
    if not (lim and grp):
        return None
    n, w = num(grp['n']), Fraction(grp['w'])
    each = not re.search(r'(?i)averag|on average|each', grp[0]) and re.search(r'(?i)\bin total|between them|altogether', grp[0])
    load = w if each else n * w
    extras = [(Fraction(m['x']), m['what']) for m in re.finditer(r'(?i)\b(?:with|plus|and)\s+(?:a|an|their|one)\s+(?P<x>\d+(?:\.\d+)?)\s*kg\s+(?P<what>[a-z]+)', T)]
    total = load + sum(x for x, _ in extras)
    P, K = num(lim['p']), Fraction(lim['kg'])
    over = []
    if n > P:
        over.append(f'{fmt(n)} people is more than {fmt(P)}')
    if total > K:
        over.append(f'{fmt(total)} kg is more than {fmt(K)} kg')
    sums = f'{fmt(n)} × {fmt(w)} kg = {fmt(load)} kg' + ''.join(f' + {fmt(x)} kg {what}' for x, what in extras) + (f' = {fmt(total)} kg' if extras else '')
    if over:
        return out(f'**No**: {"; ".join(over)} ({sums}).', 'lift')
    return out(f'**Yes**: {fmt(n)} people is within {fmt(P)}, and {sums} is within {fmt(K)} kg.', 'lift')


def latest_start(T, Q):
    q = re.search(r'(?i)\blatest\s+(?:time\s+)?(?:i|we|she|he|they)\s+(?:can|could|should|must)\s+(?P<act>wake up|wake|get up|leave|set off|start|go)', Q) or \
        re.search(r'(?i)\bwhen\s+(?:is the latest|must|should)\s+(?:i|we)\s+(?P<act>wake up|wake|get up|leave|set off|start)', Q)
    if not q:
        return None
    ev = re.search(r'(?i)\b(?P<d>' + DUR + r'|an hour|half an hour)\s+before\s+(?:a|an|the|my|our)?\s*(?P<t>' + CLOCK + r')\s+(?P<what>[a-z]+)', T) or \
        re.search(r'(?i)\b(?P<d>' + DUR + r'|an hour|half an hour)\s+before\s+(?:a|an|the|my|our)?\s*(?P<what>[a-z]+)\s+(?:at|leaves at|departs at|starts at)\s+(?P<t>' + CLOCK + r')', T)
    deadline = None
    if ev:
        before = 60 if ev['d'].lower() == 'an hour' else 30 if ev['d'].lower() == 'half an hour' else dur(ev['d'])
        deadline = minutes(ev['t']) - before
        used = [ev.span()]
        twelve = bool(re.search(r'(?i)am|pm', ev['t']))
        lead = f'you need to be there by {ee.clock(deadline, twelve)} ({ev["t"]} − {ev["d"]})'
    else:
        by = re.search(r'(?i)\b(?:be|get|arrive)\s+(?:there|at \w+|in)\s+(?:by|at|for)\s+(?P<t>' + CLOCK + r')', T)
        if not by:
            return None
        deadline = minutes(by['t'])
        used = [by.span()]
        twelve = bool(re.search(r'(?i)am|pm', by['t']))
        lead = f'you need to be there by {by["t"]}'
    steps = []
    for m in re.finditer(r'(?i)(?P<pre>[^.,;]{0,40}?)\b(?P<d>' + DUR + r'|an hour|half an hour)(?=(?P<post>[^.,;]{0,40}))', T):
        if any(a <= m.start('d') < b for a, b in used):
            continue
        ctx = (m['pre'] + ' ' + m['post']).lower()
        travel = bool(re.search(r'\b(?:drive|driving|walk|journey|trip|ride|travel|commute|bus|train|taxi|cycle|flight|get there)\b', ctx))
        d = 60 if m['d'].lower() == 'an hour' else 30 if m['d'].lower() == 'half an hour' else dur(m['d'])
        steps.append((d, travel, m['d']))
    if not steps:
        return None
    act = q['act'].lower()
    if act in ('leave', 'set off', 'go'):
        steps = [s for s in steps if s[1]]
        if not steps:
            return None
    t = deadline - sum(d for d, *_ in steps)
    return out(f'**{ee.clock(t, twelve)}**: {lead}, minus ' + ' and '.join(x for *_, x in steps) + f' = {ee.clock(t, twelve)}.', 'latest-start')


def paint(T, Q):
    if not re.search(r'(?i)how many\s+(?P<k>tins|cans|pots|litres|liters)', Q):
        return None
    wall = re.search(r'(?i)(?P<w>\d+(?:\.\d+)?)\s*m\s+(?:wide|long|across)\s+(?:and|by|x|×)\s+(?P<h>\d+(?:\.\d+)?)\s*m\s+(?:high|tall)', T) or \
        re.search(r'(?i)(?P<w>\d+(?:\.\d+)?)\s*m\s*(?:by|x|×)\s*(?P<h>\d+(?:\.\d+)?)\s*m\b', T)
    cover = re.search(r'(?i)\bcovers?\s+(?P<c>\d+(?:\.\d+)?)\s*(?:m²|m2|sq(?:uare)?\.?\s*m(?:etres|eters)?)\s+(?:per|a|each)\s+lit(?:re|er)', T)
    if not (wall and cover):
        return None
    walls = re.search(r'(?i)\b(?P<n>' + N + r')\s+(?:such\s+|identical\s+|of these\s+)?walls\b', T)
    area = Fraction(wall['w']) * Fraction(wall['h']) * (num(walls['n']) if walls else 1)
    holes = [Fraction(m['a']) for m in re.finditer(r'(?i)(?P<a>\d+(?:\.\d+)?)\s*(?:m²|m2|sq(?:uare)?\.?\s*m(?:etres|eters)?)\s+(?:window|door|opening|fireplace)', T)]
    net = area - sum(holes)
    coats = re.search(r'(?i)\b(?P<k>one|two|three|four|\d)\s+coats?\b', T)
    k = num(coats['k']) if coats else 1
    litres = net * k / Fraction(cover['c'])
    tin = re.search(r'(?i)(?P<t>\d+(?:\.\d+)?)[- ]?(?:litre|liter|l)\s+(?:tins?|cans?|pots?)|(?:tins?|cans?|pots?)\s+of\s+(?P<t2>\d+(?:\.\d+)?)\s*(?:litres?|liters?|l)\b', T)
    show_l = f'{float(litres):.2f}'.rstrip('0').rstrip('.')
    work = f'{fmt(area)} m²' + (f' − {" − ".join(fmt(h) for h in holes)} m² = {fmt(net)} m²' if holes else '') + f', × {fmt(k)} coat{"s" if k != 1 else ""} = {fmt(net * k)} m², ÷ {cover["c"]} m² per litre = {show_l} litres'
    if re.search(r'(?i)litres|liters', Q) and not tin:
        return out(f'**{show_l} litres**: {work}.', 'paint')
    if not tin:
        return None
    size = Fraction(tin['t'] or tin['t2'])
    n = math.ceil(litres / size)
    return out(f'**{n} tin{"s" if n != 1 else ""}**: {work}, and {fmt(size)}-litre tins means {n}.', 'paint')


def pigeonhole(T, Q):
    if not re.search(r'(?i)\b(?:sure|certain|guarantee\w*)\b', Q) or not re.search(r'(?i)how many', Q):
        return None
    cols = re.findall(r'(?i)\b(?P<n>' + N + r')\s+(?P<c>black|white|red|blue|green|yellow|grey|gray|brown|pink|purple|orange|navy|beige|cream|'
                      r'silver|gold|tan|khaki|violet|striped|spotted|plain)\b', T)
    group = re.search(r'(?i)\b(?P<g>(?:' + N + r'\s+[a-z]+(?:\s*,\s*and\s+|\s*,\s*|\s+and\s+))+' + N + r'\s+[a-z]+)\s+(?:socks|gloves|marbles|balls|beads|sweets|counters|shirts|pens|cards|buttons)\b', T)
    if group:           # "8 grey, 5 navy and 3 brown socks": any colour word
        cols = re.findall(r'(?i)\b(?P<n>' + N + r')\s+(?P<c>[a-z]+)\b', group['g'])
    if len(cols) < 2:
        return None
    counts = {c.lower(): int(num(n)) for n, c in cols}
    q = Q.lower()
    pair_of = re.search(r'\bpair of (?P<c>\w+)|\btwo (?P<c2>\w+) (?:socks|gloves|ones)', q)
    one_each = re.search(r'\bone of each|\bboth colou?rs|\bevery colou?r', q)
    if pair_of and (pair_of['c'] or pair_of['c2']) in counts:
        c = pair_of['c'] or pair_of['c2']
        if counts[c] < 2:
            return out(f'**You can\'t**: there are fewer than two {c} ones.', 'pigeonhole')
        n = sum(v for k, v in counts.items() if k != c) + 2
        return out(f'**{n}**: in the worst case you first pull out every one that isn\'t {c} ({n - 2}), then two {c}.', 'pigeonhole')
    if one_each:
        n = sum(counts.values()) - min(counts.values()) + 1
        return out(f'**{n}**: in the worst case every one of the more common colours comes out first.', 'pigeonhole')
    if re.search(r'match|pair|same colou?r|two of the same', q):
        k = len(counts)
        return out(f'**{k + 1}**: with {k} colours, {k} could all be different, so the next one must match one of them. How many of each there are doesn\'t matter.', 'pigeonhole')
    return None


def deal(T, Q):
    if not re.search(r'(?i)how much|what (?:do|will) i pay|cost', Q):
        return None
    d = re.search(r'(?i)\bbuy\s+(?P<b>' + N + r'),?\s+get\s+(?P<f>' + N + r'|one|a)\s+(?:free|for free)', T) or \
        re.search(r'(?i)\b(?P<x>' + N + r')\s+for\s+(?:the price of\s+)?(?P<y>' + N + r')\b(?!\s*[$€£%])', T)
    each = re.search(r'(?i)(?P<p>' + CUR + r')\s+(?:each|apiece|a (?:piece|pack|candle|bottle|item|one)|per \w+)', T) or re.search(r'(?i)\bare\s+(?P<p>' + CUR + r')\b', T)
    want = re.search(r'(?i)\b(?:want|need|buy|buying|get|getting|take)\s+(?P<n>' + N + r')\b', T[d.end():] if d else '') if d else None
    if not (d and each and want):
        return None
    if d.groupdict().get('b'):
        b, f = num(d['b']), (1 if d['f'].lower() in ('one', 'a') else num(d['f']))
    else:
        x, y = num(d['x']), num(d['y'])
        if y >= x:
            return None
        b, f = y, x - y
    n = num(want['n'])
    group = b + f
    full, rem = divmod(int(n), int(group))
    paid = full * int(b) + min(rem, int(b))
    sym, p = cur(each['p'])
    return out(f'**{money(sym, paid * p)}**: {fmt(n)} items is {full} full deal{"s" if full != 1 else ""} of {fmt(group)} (pay for {fmt(b)} in each) '
               f'plus {rem} more, so you pay for {paid} × {money(sym, p)}.', 'deal')


def spend(T, Q):
    """'I bought 3 notebooks at $4 each and 2 pens at $1.50 each. How much did I spend?' (chat probes, 2026-11-22)."""
    if not re.search(r'(?i)how much (?:did|do|will|would|does) (?:i|we|it|they|that|this|she|he) (?:spend|pay|cost|come to|owe)|what(?:\'s| is| was) the total|'
                     r'how much (?:in total|altogether|all together)|what (?:did|do|will) (?:i|we) pay', Q):
        return None
    if re.search(r'(?i)\b(?:fee|charge|discount|off\b|deal|free|tax|vat|tip|deposit|change|split|share|each of us|per person)\b', T):
        return None             # those have their own readers
    items = list(re.finditer(r'(?i)\b(?P<n>' + N + r')\s+(?P<item>[a-z]+(?:\s[a-z]+)?)\s+(?:at|for|costing|@)\s+(?P<p>' + CUR + r')\s*(?:each|apiece|a piece|per \w+|an? \w+)?', T))
    if not items or len(T) > 400:
        return None
    total, parts, sym = Fraction(0), [], None
    for m in items:
        s, p = cur(m['p'])
        sym = sym or s
        k = num(m['n'])
        total += k * p
        parts.append(f'{fmt(k)} × {money(s, p)}')
    return out(f'**{money(sym, total)}**: ' + ' + '.join(parts) + (f' = {money(sym, total)}.' if len(parts) > 1 else '.'), 'spend')


# ================================================================== the reader
READERS_TQ = (rate_pauses, order_fees, leftover, packs_needed, drain, fare_halfway, together, sessions, flight_zones, weekdays_between, shift_pay,
              leap_birthdays, meeting_zones, nth_day, assignment, jugs, digits, scoped_notice, credibility, adjusted_for_other, biased_reading,
              hearsay, riddles, no_start, hidden_number, shapes, lift, latest_start, paint, pigeonhole, deal, spend)
READERS_TQU = (orders, code_change, list_edits, booking, debts, weekday_after_next, bins, slots)


def respond(messages):
    users = [(m.get('content') or '').strip() for m in messages if m.get('role') == 'user']
    if not users or not users[-1]:
        return None
    users = users[-6:]
    Q = users[-1]
    if not Q.rstrip().endswith('?') and not re.search(r'(?i)^(?:how|what|which|who|when|where|why|is|are|does|do|did|can|could|was)\b', Q):
        return None
    T = '\n'.join(users)
    qs = re.findall(r'(?:[^.!?\n]|\.(?=\d))*\?', Q)
    q = qs[-1] if qs else Q
    for r in READERS_TQU:
        try:
            got = r(T, q, users)
        except (ValueError, KeyError, ZeroDivisionError, IndexError, TypeError, AttributeError, StopIteration):
            got = None
        if got:
            return got
    for r in READERS_TQ:
        try:
            got = r(T, q)
        except (ValueError, KeyError, ZeroDivisionError, IndexError, TypeError, AttributeError, StopIteration):
            got = None
        if got:
            return got
    return None
