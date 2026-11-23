"""General clock and calendar reasoning (0.4.4 work after release, 2026-11-22). Non-neural.

The text is read as typed facts, not as one sentence shape:
- clock times (07:05, 7:41 am, 8:30 pm, noon), each with the words around it;
- durations ("12 minutes", "three full minutes", "an hour and a half"), frequencies ("every eighteen minutes");
- time-zone offsets ("UTC+2", "two hours ahead of UTC", "one hour behind");
- dates and weekdays, ordinal weekdays ("the second and fourth Fridays"), opening days ("opens Tuesday through Saturday").
A solver is picked by what the facts and the question contain:
- **next departure:** a first departure, a frequency, my arrival and any time I need before leaving;
- **pick from options:** a target time, the durations needed, and a list of candidate times, with "latest" or
  "earliest" in the question;
- **overlap:** two free windows, each on its own clock, and "how long together";
- **two clocks:** two reported times on different clocks, and "how far apart";
- **ordinal weekdays:** a known weekday date and "the second and fourth Fridays";
- **working days:** "by the end of the fourth working day after" a date, with the opening days.
Each solver shows its working, and returns nothing when a needed fact is missing.
"""
import re
from datetime import date, timedelta

ROUTE = 'chat/time'
NUMW = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18,
        'nineteen': 19, 'twenty': 20, 'twenty-five': 25, 'thirty': 30, 'forty': 40, 'forty-five': 45, 'fifty': 50, 'sixty': 60, 'ninety': 90}
for _t, _v in (('twenty', 20), ('thirty', 30), ('forty', 40), ('fifty', 50)):
    for _o, _ov in (('one', 1), ('two', 2), ('three', 3), ('four', 4), ('five', 5), ('six', 6), ('seven', 7), ('eight', 8), ('nine', 9)):
        NUMW[f'{_t}-{_o}'] = _v + _ov
NUM = r'(\d+(?:\.\d+)?|' + '|'.join(sorted(NUMW, key=len, reverse=True)) + r'|an?|half\s+an?)'
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
ORD = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5, 'last': -1, '1st': 1, '2nd': 2, '3rd': 3, '4th': 4, '5th': 5}
ORDW = {1: 'first', 2: 'second', 3: 'third', 4: 'fourth', 5: 'fifth', 6: 'sixth', 7: 'seventh', 8: 'eighth', 9: 'ninth', 10: 'tenth'}


def out(text, kind):
    return dict(route=f'{ROUTE}-{kind}', response=text, sources=[], reasoning=True, details=f'{kind} (time_engine.py)')


def num(w):
    w = w.lower().strip()
    if re.fullmatch(r'\d+(?:\.\d+)?', w):
        return float(w)
    if re.fullmatch(r'an?', w):
        return 1
    if re.fullmatch(r'half\s+an?', w):
        return 0.5
    return NUMW.get(w)


# ------------------------------------------------------------------ facts
CLOCK = re.compile(r'(?i)\b(\d{1,2})(?::|\.)(\d{2})\s*(a\.?m\.?|p\.?m\.?)?(?![\d])|\b(\d{1,2})\s*(a\.?m\.?|p\.?m\.?)(?![a-z])|\b(noon|midday|midnight)\b')


def clocks(text):
    """[(minutes, start, end, is_12h)]"""
    got = []
    for m in CLOCK.finditer(text):
        if m[6]:
            v = 720 if m[6].lower() in ('noon', 'midday') else 0
            got.append((v, m.start(), m.end(), False))
            continue
        if m[1]:
            h, mi, ap = int(m[1]), int(m[2]), m[3]
        else:
            h, mi, ap = int(m[4]), 0, m[5]
        if h > 24 or mi > 59:
            continue
        if ap:
            h = h % 12 + (12 if ap.lower().startswith('p') else 0)
        got.append((h * 60 + mi, m.start(), m.end(), bool(ap)))
    return got


DUR = re.compile(r'(?i)\b' + NUM + r'(?:\s+(?:full|whole|more|extra|further))?\s*(?:-\s*)?(hours?|hrs?|h|minutes?|mins?)\b(?:\s+and\s+(?:a\s+)?(half|' + NUM[1:-1] + r')\s*(minutes?|mins?)?)?')


def durations(text):
    """[(minutes, start, end)] for every stated length of time."""
    got = []
    for m in DUR.finditer(text):
        v = num(m[1])
        if v is None:
            continue
        unit = m[2].lower()
        mins = v * 60 if unit.startswith('h') else v
        if m[3]:
            if m[3].lower() == 'half' and unit.startswith('h'):
                mins += 30
            elif num(m[3]) is not None and m[4]:
                mins += num(m[3])
        got.append((int(round(mins)), m.start(), m.end()))
    return got


def fmt(mins, twelve):
    mins %= 1440
    h, mi = divmod(mins, 60)
    if twelve:
        return f'{(h - 1) % 12 + 1}:{mi:02d} {"am" if h < 12 else "pm"}'
    return f'{h:02d}:{mi:02d}'


def span(m):
    h, mi = divmod(int(m), 60)
    if h and mi:
        return f'{h} h {mi} min'
    return f'{h} hour' + ('s' if h != 1 else '') if h else f'{mi} minutes'


OFFSET = re.compile(r'(?i)\b(?:UTC|GMT)\s*([+-−])\s*(\d{1,2})(?::(\d{2}))?\b|\b' + NUM + r'\s+hours?\s+(ahead\s+of|behind|before|after)\s+(?:UTC|GMT|the\s+other|mine|my\s+clock|ours)\b')


def offset_near(text, start, end):
    """The UTC offset in minutes that applies to the clock at text[start:end], from the same clause, or None."""
    lo = max(text.rfind('.', 0, start), text.rfind(';', 0, start), text.rfind('\n', 0, start)) + 1
    hi = min([i for i in (text.find('.', end), text.find(';', end), text.find('\n', end)) if i >= 0] or [len(text)])
    clause = text[lo:hi]
    m = OFFSET.search(clause)
    if m:
        if m[1]:
            v = int(m[2]) * 60 + int(m[3] or 0)
            return -v if m[1] in '-−' else v
        v = num(m[4])
        if v is None:
            return None
        return int(v * 60) if m[5].lower() in ('ahead of', 'after') else -int(v * 60)
    if re.search(r'(?i)\b(?:UTC|GMT)\b', clause):
        return 0
    return None


# ------------------------------------------------------------------ solvers
def next_departure(text, q):
    ev = re.search(r'(?i)\bevery\s+' + NUM + r'\s*(minutes?|mins?|hours?)\b', text)
    if not ev or not re.search(r'(?i)\b(?:earliest|first|next|soonest|which|what\s+time|when)\b', q):
        return None
    period = num(ev[1]) * (60 if ev[2].lower().startswith('h') else 1)
    cs = clocks(text)
    if len(cs) < 2 or not period:
        return None
    first = cs[0]
    me = next((c for c in cs[1:] if re.search(r'(?i)\b(?:I|we)\s+(?:\w+\s+){0,3}(?:reach|arrive|get|am|are|will\s+be|turn\s+up|show\s+up)\b',
                                                 text[max(0, c[1] - 60):c[1]])), None)
    if not me:
        return None
    need = 0
    for d, s, e in durations(text):
        if ev.start() <= s < ev.end():
            continue
        ctx = text[max(0, s - 60):e + 60]
        if re.search(r'(?i)\b(?:need|takes?|have\s+to|must|before|load|walk|buy|get)\b', ctx):
            need += d
    ready = me[0] + need
    k = max(0, -(-(ready - first[0]) // int(period)))
    dep = first[0] + k * int(period)
    twelve = first[3] or me[3]
    why = f'Departures are {fmt(first[0], twelve)} plus every {span(period)}'
    why += f'; you arrive at {fmt(me[0], twelve)}' + (f' and need {span(need)} first, so you are ready at {fmt(ready, twelve)}' if need else '')
    return out(f'**The {fmt(dep, twelve)}.** {why}. The first departure at or after that is {fmt(dep, twelve)}'
               + (f' (the one before, {fmt(dep - int(period), twelve)}, is too early).' if k > 0 else '.'), 'next-departure')


def pick_option(text, q):
    latest = re.search(r'(?i)\b(?:latest|last)\b', q)
    earliest = re.search(r'(?i)\b(?:earliest|first|soonest)\b', q)
    if not (latest or earliest):
        return None
    cs = clocks(text)
    # the candidates: three or more times listed together, or two or more after "at"/"are" in one clause
    groups, cur = [], []
    for c in cs:
        if cur and re.fullmatch(r'(?i)\s*(?:,|,?\s*and|,?\s*or)\s*', text[cur[-1][2]:c[1]]):
            cur.append(c)
        else:
            if len(cur) >= 2:
                groups.append(cur)
            cur = [c]
    if len(cur) >= 2:
        groups.append(cur)
    if not groups:
        return None
    opts = groups[-1]
    others = [c for c in cs if c not in opts]
    if len(others) != 1:
        return None
    target = others[0]
    need = sum(d for d, s, e in durations(text) if not any(o[1] <= s < o[2] for o in opts))
    twelve = target[3]
    if latest:
        limit = target[0] - need
        ok = [o for o in opts if o[0] <= limit]
        if not ok:
            return out(f'**None of them works.** You need {span(need)} before {fmt(target[0], twelve)}, so you must arrive by '
                       f'{fmt(limit, twelve)}, and every option is later.', 'pick-none')
        best = max(ok, key=lambda o: o[0])
        later = [o for o in opts if o[0] > limit]
        return out(f'**The {fmt(best[0], best[3])}.** You need {span(need)} in all before {fmt(target[0], twelve)}, so you must arrive by '
                   f'{fmt(limit, twelve)}.' + (f' The {" and ".join(fmt(o[0], o[3]) for o in later)} would be too late.' if later else ''), 'pick-latest')
    limit = target[0] + need
    ok = [o for o in opts if o[0] >= limit]
    if not ok:
        return out(f'**None of them works**: you are only ready at {fmt(limit, twelve)}, after every option.', 'pick-none')
    best = min(ok, key=lambda o: o[0])
    return out(f'**The {fmt(best[0], best[3])}.** You are ready at {fmt(limit, twelve)} ({fmt(target[0], twelve)} plus {span(need)}), and that is '
               f'the first option at or after it.', 'pick-earliest')


def windows(text):
    """[(start_utc, end_utc, raw)] for 'free 18:00 to 20:00 UTC' style windows."""
    got = []
    cs = clocks(text)
    for a, b in zip(cs, cs[1:]):
        mid = text[a[2]:b[1]]
        if not re.fullmatch(r'(?i)\s*(?:to|until|till|-|–|and)\s*', mid):
            continue
        off = offset_near(text, a[1], b[2])
        if off is None:
            return None
        s, e = a[0] - off, b[0] - off
        if e <= s:
            e += 1440
        got.append((s, e, text[a[1]:b[2]], off))
    return got


def overlap(text, q):
    if not re.search(r'(?i)\b(?:how\s+(?:many\s+minutes|long|much\s+time)|overlap|together|both)\b', q):
        return None
    ws = windows(text)
    if not ws or len(ws) != 2:
        return None
    (s1, e1, r1, o1), (s2, e2, r2, o2) = ws
    best = 0
    for shift in (-1440, 0, 1440):
        best = max(best, min(e1, e2 + shift) - max(s1, s2 + shift))
    def utc(m):
        return fmt(m, False) + ' UTC'
    why = f'In UTC the windows are {utc(s1)}–{utc(e1)} and {utc(s2)}–{utc(e2)}.'
    if best <= 0:
        return out(f'**No time at all**: the windows don\'t overlap. {why}', 'overlap-none')
    return out(f'**{int(best)} minutes** ({span(best)}). {why}', 'overlap')


def two_clocks(text, q):
    if not re.search(r'(?i)\bhow\s+(?:far|many\s+minutes|much\s+time|long)\s+apart\b|\bdifference\b|\bapart\b', q):
        return None
    cs = clocks(text)
    if len(cs) != 2:
        return None
    offs = [offset_near(text, c[1], c[2]) for c in cs]
    if None in offs:
        return None
    u = [c[0] - o for c, o in zip(cs, offs)]
    d = abs(u[0] - u[1]) % 1440
    d = min(d, 1440 - d)
    why = f'In UTC they are {fmt(u[0], False)} and {fmt(u[1], False)}.'
    if d == 0:
        return out(f'**They are the same moment: 0 minutes apart.** {why}', 'two-clocks')
    return out(f'**{span(d)} apart.** {why}', 'two-clocks')


DATE = re.compile(r'(?i)\b(?:(\d{1,2})(?:st|nd|rd|th)?\s+(' + '|'.join(MONTHS) + r')|(' + '|'.join(MONTHS) + r')\s+(\d{1,2})(?:st|nd|rd|th)?)(?:,?\s+(\d{4}))?\b')


def dates(text, default_year=None):
    got = []
    for m in DATE.finditer(text):
        d = int(m[1] or m[4])
        mo = MONTHS.index((m[2] or m[3]).capitalize()) + 1
        y = int(m[5]) if m[5] else default_year
        if not y:
            yy = re.search(r'\b(19|20)\d{2}\b', text)
            y = int(yy[0]) if yy else None
        if not y:
            continue
        try:
            got.append((date(y, mo, d), m.start(), m.end(), bool(m[1])))
        except ValueError:
            continue
    return got


def show_date(d, uk):
    return f'{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]} {d.year}' if uk else f'{DAYS[d.weekday()]}, {MONTHS[d.month - 1]} {d.day}, {d.year}'


def ordinal_weekdays(text, q):
    m = re.search(r'(?i)\b((?:first|second|third|fourth|fifth|last|1st|2nd|3rd|4th|5th)(?:\s*(?:,|and|&)\s*(?:the\s+)?(?:first|second|third|fourth|fifth|last|1st|2nd|3rd|4th|5th))+)\s+(' +
                  '|'.join(DAYS) + r')s?\b', text)
    if not m:
        return None
    wd = DAYS.index(m[2].capitalize())
    ks = [ORD[w.lower()] for w in re.findall(r'(?i)first|second|third|fourth|fifth|last|1st|2nd|3rd|4th|5th', m[1])]
    ds = dates(text)
    month = None
    if ds:
        month = (ds[0][0].year, ds[0][0].month)
        uk = ds[0][3]
    else:
        mm = re.search(r'(?i)\b(' + '|'.join(MONTHS) + r')\s+(\d{4})\b', text)
        if not mm:
            return None
        month = (int(mm[2]), MONTHS.index(mm[1].capitalize()) + 1)
        uk = True
    y, mo = month
    all_wd = [date(y, mo, d) for d in range(1, 32) if _ok(y, mo, d) and date(y, mo, d).weekday() == wd]
    picks = [all_wd[k - 1] if k > 0 else all_wd[-1] for k in ks if k <= len(all_wd)]
    if not picks:
        return None
    if re.search(r'(?i)\b(?:later|last|second\s+one|latter)\b', q):
        d = max(picks)
    elif re.search(r'(?i)\b(?:earlier|first\s+one|former|sooner)\b', q):
        d = min(picks)
    elif re.search(r'(?i)\bwhich\s+dates|\bwhat\s+dates|\bboth\b', q):
        return out('**' + ' and '.join(show_date(d, uk) for d in picks) + '.**', 'ordinal-weekdays')
    else:
        return None
    return out(f'**{show_date(d, uk)}.** The {m[2].capitalize()}s that month fall on ' + ', '.join(str(x.day) for x in all_wd) +
               f', so the {" and ".join(ORDW.get(k, "last") if k > 0 else "last" for k in ks)} are the ' + ' and '.join(str(p.day) for p in picks) + '.', 'ordinal-weekdays')


def _ok(y, m, d):
    try:
        date(y, m, d)
        return True
    except ValueError:
        return False


def working_days(text, q):
    m = re.search(r'(?i)\b(?:the\s+)?(\w+)\s+(working|business|work|open|opening|trading|school)\s+days?\s+(?:after|from|following)\b', text)
    m2 = re.search(r'(?i)\bwithin\s+' + NUM + r'\s+(working|business|work|open|trading)\s+days\b', text)
    if not m and not m2:
        return None
    if m:
        k = ORD.get(m[1].lower()) or (int(num(m[1])) if num(m[1]) else None)
    else:
        k = int(num(m2[1]))
    if not k or k < 1:
        return None
    ds = dates(text)
    if not ds:
        return None
    start = ds[0][0]
    open_days = set(range(5))
    r = re.search(r'(?i)\b(?:open|opens|works|operates|trades|staffed)\s+(?:from\s+)?(' + '|'.join(DAYS) + r')\s+(?:to|through|thru|until|till|-|–)\s+(' + '|'.join(DAYS) + r')\b', text)
    if r:
        a, b = DAYS.index(r[1].capitalize()), DAYS.index(r[2].capitalize())
        open_days = {(a + i) % 7 for i in range((b - a) % 7 + 1)}
    closed = {DAYS.index(c.capitalize()) for c in re.findall(r'(?i)\bclosed\s+(?:on\s+)?(' + '|'.join(DAYS) + r')s?\b', text)}
    open_days -= closed
    if not open_days:
        return None
    d, n, seen = start, 0, []
    while n < k:
        d += timedelta(days=1)
        if d.weekday() in open_days:
            n += 1
            seen.append(d)
    uk = ds[0][3]
    days = ', '.join(f'{DAYS[x.weekday()][:3]} {x.day}' for x in seen)
    return out(f'**{show_date(d, uk)}.** Counting only open days after {show_date(start, uk)}: {days}, and the {ORDW.get(k, str(k) + "th")} of those is the deadline.', 'working-days')


def ages_later(text, q):
    """'Both twins were nine on June 1, 2011 ... on June 1, 2023, what was their combined age?'"""
    if not re.search(r'(?i)\bhow\s+old\b|\bage[sd]?\b', q):
        return None
    m = re.search(r'(?i)\b(?:was|were|turned|is|are)\s+(?:both\s+|each\s+|all\s+)?' + NUM + r'(?:\s+years?\s+old)?\b', text)
    if not m or num(m[1]) is None:
        return None
    n0 = int(num(m[1]))
    ds = dates(text)
    if len(ds) != 2:
        return None
    (d1, *_), (d2, *_rest) = ds
    years = d2.year - d1.year - ((d2.month, d2.day) < (d1.month, d1.day))
    exact = (d2.month, d2.day) == (d1.month, d1.day)
    count = 2 if re.search(r'(?i)\b(?:twins|both|the\s+two|two\s+(?:people|children|kids|sisters|brothers))\b', text) else 1
    combined = re.search(r'(?i)\b(?:combined|total|together|sum|add(?:ed)?\s+up)\b', q)
    if count > 1 and not combined and not re.search(r'(?i)\beach\b', q):
        return None
    age = n0 + years
    uk = ds[0][3]
    when = show_date(d2, uk)
    if not exact:
        if combined and count > 1:
            return None
        return out(f'**{age} or {age + 1}**, depending on whether the birthday had come yet by {when}: {years} full years passed since they were {n0}.', 'age-range')
    if combined and count > 1:
        return out(f'**{age * count}.** Exactly {years} years later each of them was {n0} + {years} = {age}, and {count} × {age} = {age * count}.', 'age-combined')
    return out(f'**{age}.** Exactly {years} years later: {n0} + {years} = {age}.', 'age')


SHIFT = re.compile(r'(?i)\b(?:move|moved|push|pushed|shift|shifted|bring|brought|put|reschedule|rescheduled|delay|delayed)\b[^.?!]*?\b'
                   r'(back|forward|forwards|ahead|earlier|later|up)\b(?:\s+by)?\s+' + NUM + r'\s*(hours?|hrs?|minutes?|mins?)\b|'
                   r'\b(?:move|moved|push|pushed|shift|shifted|bring|brought|put)\b[^.?!]*?\b' + NUM + r'\s*(hours?|hrs?|minutes?|mins?)\s+'
                   r'(back|forward|forwards|ahead|earlier|later)\b')


def time_shift(text, q):
    """'Move my meeting back two hours. It's at 14:00.' -> 'back' is ambiguous: 16:00 if later, 12:00 if earlier.
    A later 'I meant earlier' settles it."""
    if not re.search(r'(?i)\bwhat\b.*\btime\b|\bwhen\b|\bwhat\s+should\s+i\s+(?:put|enter|write|set)\b|\bnew\s+time\b', q):
        return None
    m = SHIFT.search(text)
    if not m:
        return None
    word, n, unit = (m[1], m[2], m[3]) if m[1] else (m[6], m[4], m[5])
    v = num(n)
    if v is None:
        return None
    d = int(v * 60) if unit.lower().startswith('h') else int(v)
    cs = [c for c in clocks(text)]
    if len(cs) != 1:
        return None
    t0, twelve = cs[0][0], cs[0][3]
    meant = re.findall(r'(?i)\bi\s+meant\s+(earlier|later|before|after|forward|back)\b|\b(?:no|sorry)[,.]?\s+(earlier|later)\b', text)
    meant = [a or b for a, b in meant]
    word = (meant[-1] if meant else word).lower()
    later, earlier = fmt(t0 + d, twelve), fmt(t0 - d, twelve)
    if word in ('earlier', 'before', 'up'):
        return out(f'**{earlier}.** Moving {fmt(t0, twelve)} {span(d)} earlier gives {earlier}.', 'shift')
    if word in ('later', 'after'):
        return out(f'**{later}.** Moving {fmt(t0, twelve)} {span(d)} later gives {later}.', 'shift')
    if word in ('forward', 'forwards', 'ahead'):     # "bring it forward" usually means earlier
        return out(f'**{earlier}**, if "{word}" means earlier, which is the usual reading. If you meant later, it would be {later}.', 'shift-ambiguous')
    return out(f'**{later}**, if "{word}" means later, which is the usual reading. If you meant earlier, it would be {earlier}.', 'shift-ambiguous')


def duration_between(text, q):
    """'leaves at 14:15 and arrives at 16:05, how many minutes did the trip take?'"""
    if not re.search(r'(?i)\bhow\s+(?:many\s+(?:minutes|hours)|long)\b', q):
        return None
    if re.search(r'(?i)\bevery\b|\bdelay|\blate\b|\bearly\b|\bstop(?:s|ped)?\s+for\b|\bbreak\b', text):
        return None
    cs = clocks(text)
    if len(cs) != 2 or durations(re.sub(r'(?i)how\s+many\s+minutes', '', text)):
        return None
    a, b = cs
    if not re.search(r'(?i)\b(?:leaves?|left|departs?|departed|starts?|started|begins?|began|from|set\s+off)\b', text[max(0, a[1] - 40):a[1]]) or \
            not re.search(r'(?i)\b(?:arrives?|arrived|gets?\s+in|got\s+in|ends?|ended|finish(?:es|ed)?|to|until|lands?|landed|docks?|docked|reach(?:es|ed)?|'
                          r'pulls?\s+in|pulled\s+in|comes?\s+in|came\s+in|stops?|stopped|returns?|returned|gets?\s+back|got\s+back)\b', text[a[2]:b[1]]):
        return None
    if offset_near(text, a[1], a[2]) not in (None, 0) or offset_near(text, b[1], b[2]) not in (None, 0):
        return None
    d = (b[0] - a[0]) % 1440
    twelve = a[3] or b[3]
    minutes = re.search(r'(?i)how\s+many\s+minutes', q)
    nouns = [n for n in re.findall(r'(?i)\bthe\s+([a-z]+)\b', q) if n.lower() not in ('trip', 'time', 'answer', 'same', 'whole', 'total')] or \
        re.findall(r'(?i)\bthe\s+(trip)\b', q)
    what = f'The {nouns[-1].lower()}' if nouns else 'It'
    head = f'{d} minutes' if minutes else span(d)
    return out(f'**{what} took {head}**, from {fmt(a[0], twelve)} to {fmt(b[0], twelve)}' + (f' ({span(d)}).' if minutes and d >= 60 else '.'), 'duration')


SOLVERS = (time_shift, duration_between, next_departure, pick_option, overlap, two_clocks, ordinal_weekdays, working_days, ages_later)


def respond(messages):
    users = [(m.get('content') or '').strip() for m in messages if m.get('role') == 'user']
    if not users:
        return None
    qs = re.findall(r'[^.!?\n]*\?', users[-1])
    if not qs:
        return None
    q = qs[-1]
    text = '\n'.join(users[-4:])
    for solve in SOLVERS:
        try:
            got = solve(text, q if solve is not ordinal_weekdays else users[-1])
        except (ValueError, IndexError, ZeroDivisionError, TypeError):
            got = None
        if got:
            return got
    return None
