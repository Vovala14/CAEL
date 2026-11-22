"""General arithmetic word problems, solved from the quantities and their units (no per-phrasing patterns, no model).

Every number in the text becomes a quantity with a unit ("250 g", "$12 per month", "8 minutes, twice"). The question
names the unit that is wanted. Rates are multiplied or divided until only the wanted unit is left, then the remaining
amounts are added or subtracted by the cue next to them ("spent", "gives", "left"). Clock times, percentages, compared
options, averages and "older than / twice as many as" chains are separate small solvers on the same quantities.

A reply is given only when every number in the problem was used; otherwise None, so nothing is guessed.
"""
import math
import re
from fractions import Fraction as F

ONES = dict(zero=0, one=1, two=2, three=3, four=4, five=5, six=6, seven=7, eight=8, nine=9, ten=10, eleven=11, twelve=12,
            thirteen=13, fourteen=14, fifteen=15, sixteen=16, seventeen=17, eighteen=18, nineteen=19)
TENS = dict(twenty=20, thirty=30, forty=40, fifty=50, sixty=60, seventy=70, eighty=80, ninety=90)
NUM = r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
SYN = {'hrs': 'hour', 'hr': 'hour', 'h': 'hour', 'mins': 'minute', 'min': 'minute', 'secs': 'second', 'sec': 'second',
       'kilometres': 'km', 'kilometers': 'km', 'kilometre': 'km', 'kilometer': 'km', 'kms': 'km', 'metres': 'm', 'meters': 'm',
       'metre': 'm', 'meter': 'm', 'litres': 'litre', 'liters': 'litre', 'liter': 'litre', 'l': 'litre', 'grams': 'g',
       'gram': 'g', 'kilograms': 'kg', 'kilogram': 'kg', 'kilos': 'kg', 'kilo': 'kg', 'people': 'person', 'persons': 'person',
       'children': 'child', 'kids': 'child', 'kid': 'child', 'men': 'man', 'women': 'woman', 'yrs': 'year', 'yr': 'year',
       'millilitres': 'ml', 'milliliters': 'ml', 'centimetres': 'cm', 'centimeters': 'cm', 'lbs': 'lb', 'pounds': 'lb',
       'feet': 'foot', 'ft': 'foot', 'boxes': 'box', 'glasses': 'glass', 'buses': 'bus', 'classes': 'class', 'mph': 'mph',
       'shelves': 'shelf', 'loaves': 'loaf', 'knives': 'knife', 'halves': 'half', 'leaves': 'leaf', 'sq': 'square',
       'pence': 'p', 'times': 'time', 'mi': 'mile', 'ounces': 'oz', 'ounce': 'oz', 'cups': 'cup'}
TIME = dict(second=F(1, 60), minute=F(1), hour=F(60), day=F(1440), week=F(10080), month=F(43200), year=F(525600))
CAL = {('year', 'month'): 12, ('year', 'week'): 52, ('year', 'day'): 365, ('month', 'day'): 30, ('month', 'week'): 4,
       ('week', 'day'): 7, ('day', 'hour'): 24, ('hour', 'minute'): 60, ('minute', 'second'): 60, ('day', 'minute'): 1440,
       ('week', 'hour'): 168, ('hour', 'second'): 3600, ('year', 'hour'): 8760, ('km', 'm'): 1000, ('m', 'cm'): 100,
       ('kg', 'g'): 1000, ('litre', 'ml'): 1000, ('$', 'cent'): 100, ('lb', 'oz'): 16, ('foot', 'inch'): 12}
MEASURE = set(TIME) | {'km', 'm', 'cm', 'mile', 'g', 'kg', 'litre', 'ml', '$', 'lb', 'oz', 'foot', 'inch', 'cup', '%'}
LENGTH = {'km', 'm', 'cm', 'mile', 'foot', 'inch'}
PEOPLE = {'person', 'guest', 'student', 'friend', 'child', 'adult', 'passenger', 'member', 'player', 'employee', 'visitor',
          'customer', 'runner', 'pupil', 'colleague', 'attendee', 'traveller', 'traveler', 'delegate', 'diner', 'seat'}
OCCASION = {'day', 'time', 'night', 'evening', 'morning', 'session', 'shift', 'weekday', 'weekend'}
AGENT = {'painter', 'worker', 'person', 'man', 'woman', 'machine', 'pump', 'tap', 'printer', 'builder', 'cook', 'typist',
         'cleaner', 'robot', 'employee', 'gardener', 'pipe', 'hose', 'baker', 'mechanic', 'volunteer', 'helper'}
STOP = set('''to and or of in on at for by the a an is are was were be been right wrong correct more less fewer each per every
off from with than then but so if i he she we they it you left away back total extra other others now already today
yesterday tomorrow that this these those my your his her our their as not no only just about around over under after before
later earlier ago long old tall high wide deep far away out up down into onto do does did can will would should could has
have had get got am pm who what which when where why how too also both all some any there here still yet per plus minus
remaining altogether apiece instead until till between among while because since although though'''.split())
ADJ = set('''big small large little red blue green new old full whole different additional free fresh ripe extra spare more
other long short heavy light dozen single double clean dirty empty broken good bad same equal identical separate
chocolate wooden plastic metal paper glass cotton yellow white black brown pink purple orange grey gray'''.split())
NEG = r'giv\w+|gave|spen[dt]\w*|los[te]\w*|lose|ate|eats?|eaten|us(?:e|es|ed|ing)|sold|sells?|pa(?:y|ys|id|ying)|donat\w+|broke\w*|breaks?|remov\w+|took|takes?|taken|leak\w*|withdr[ae]w\w*|minus|drank|drinks?|burn\w*|threw|throws?|sent|sends?|lent|lends?|drop\w*|wast\w+|discount\w*|coupon|refund\w*|cut\w*|deduct\w*|owes?|cost\w*|fee|fees|charg\w+|travel\w*|commut\w+|walk\w*|driv\w+|drove|queue\w*|wait\w*|away'
POS = r'gets?|got|gain\w*|f(?:ind|inds|ound)|earn\w*|receiv\w+|w[io]ns?|sav(?:e|es|ed|ing)|add\w*|another|deposit\w*|plus|pick\w*|collect\w*|mak(?:e|es|ing)|made|bak\w+|grow\w*|grew|bonus|rais\w+|gift\w*|given|inherit\w*'
BUY = r'buy\w*|bought|purchas\w+|order\w*'
LEFT = r'\b(left|remain\w*|still|spare|actually|change|rest|net|after (?:that|all|this|paying|buying|spending))\b'
TOTAL = r'\b(total|altogether|in all|combined|overall|sum|spen[dt]|spending|cost\w*|pay|owe|bill|both|together)\b'
WH = r'\b(how (?:many|much|long|far|old|fast|tall|heavy|big)|what|when|which|who|whats)\b'


def norm(text):
    t = text.replace('’', "'").replace('−', '-').replace('–', '-').replace('—', ', ').replace('×', ' x ')
    t = re.sub(r"\b(what|how|that|it|there)'s\b", r'\1 is', t, flags=re.I)
    t = re.sub(r'\b(an?|one) hour and a half\b', '90 minutes', t, flags=re.I)
    t = re.sub(r'\b(\d+) and a half (hours?)\b', lambda m: f'{m[1]}.5 {m[2]}', t, flags=re.I)
    t = re.sub(r'\bhalf an hour\b', '30 minutes', t, flags=re.I)
    t = re.sub(r'\b(a )?quarter of an hour\b', '15 minutes', t, flags=re.I)
    # "an hour" is one hour, except as the "per" part of a rate ("$18 an hour", "4 litres an hour")
    t = re.sub(r'\ban? (hour|minute)\b', lambda m: m[0] if re.search(r'(?:\d|%)\s*(?:[a-z]+\s+)?(?:of \w+\s+)?$', m.string[:m.start()], re.I) else '1 ' + m[1], t, flags=re.I)
    t = re.sub(r'\b(a|one) dozen\b', '12', t, flags=re.I)
    t = re.sub(r'\bhalf a dozen\b', '6', t, flags=re.I)
    t = re.sub(r'\ba couple of\b', '2', t, flags=re.I)
    t = re.sub(r'\btwice\b', '2 times', t, flags=re.I)
    t = re.sub(r'\bthrice\b', '3 times', t, flags=re.I)
    t = re.sub(r'\bonce (a|an|per|every)\b', r'1 time \1', t, flags=re.I)
    t = re.sub(r'\bhalf of\b', '50% of', t, flags=re.I)

    def tens(m):
        return str(TENS[m[1].lower()] + (ONES[m[2].lower()] if m[2] else 0))
    t = re.sub(r'\b(%s)(?:[- ](%s))?\b' % ('|'.join(TENS), '|'.join(list(ONES)[1:10])), tens, t, flags=re.I)

    def ones(m):
        w, nxt = m[1].lower(), (m[2] or '').lower()
        if w == 'one' and (not nxt or nxt in STOP or re.search(r'\b(another|the other)\b', t, re.I) or re.search(r'\b(which|the|this|that|each|no|every|any|only)\s+$', t[:m.start()], re.I)):
            return m[0]
        return str(ONES[w]) + m[0][len(m[1]):]
    t = re.sub(r'\b(%s)\b(?=(?:[- ]([a-z]+))?)' % '|'.join(ONES), ones, t, flags=re.I)
    t = re.sub(r'\b(\d+) hundred\b', lambda m: str(int(m[1]) * 100), t, flags=re.I)
    t = re.sub(r'\b(\d+) thousand\b', lambda m: str(int(m[1]) * 1000), t, flags=re.I)
    t = re.sub(r'(\d)\s*k\b(?!m)', r'\g<1>000', t)
    t = re.sub(r'(?<=\d)-(?=[a-z])', ' ', t, flags=re.I)
    return re.sub(r'\s+', ' ', t).strip()


def unit(word):
    w = word.lower()
    if w in SYN:
        return SYN[w]
    if w.endswith('ies') and len(w) > 4:
        return w[:-3] + 'y'
    if re.search(r'(ch|sh|x|ss)es$', w):
        return w[:-2]
    if w.endswith('s') and not w.endswith('ss') and len(w) > 2 and w not in ('bus', 'gas', 'glass', 'class'):
        return w[:-1]
    return w


def plural(u, v):
    if u in ('km', 'm', 'cm', 'g', 'kg', 'ml', 'mph', 'oz', 'lb', 'p') or v == 1:
        return u
    if ' ' in u:
        return u.rsplit(' ', 1)[0] + ' ' + plural(u.rsplit(' ', 1)[1], v)
    irregular = dict(person='people', child='children', man='men', woman='women', foot='feet', shelf='shelves', loaf='loaves',
                     knife='knives', leaf='leaves', half='halves')
    if u in irregular:
        return irregular[u]
    if u.endswith('y') and u[-2:-1] not in 'aeiou':
        return u[:-1] + 'ies'
    return u + ('es' if re.search(r'(ch|sh|x|s)$', u) else 's')


def num(v):
    v = F(v)
    if v.denominator == 1:
        return f'{int(v):,}'
    return f'{float(v):,.2f}'.rstrip('0').rstrip('.')


def fmt(v, u=None, d=None):
    v = F(v)
    if u == '$':
        s = ('-' if v < 0 else '') + '$' + (f'{int(abs(v)):,}' if v.denominator == 1 else f'{float(abs(v)):,.2f}')
    elif u == '%':
        s = num(v) + '%'
    elif u == 'minute' and d is None and v >= 60:
        h, m = divmod(v, 60)
        s = f'{num(h)} {plural("hour", h)}' + (f' {num(m)} {plural("minute", m)}' if m else '')
    elif u == 'hour' and d is None and v.denominator != 1 and (v * 60).denominator == 1:
        return fmt(v * 60, 'minute')
    elif u:
        s = f'{num(v)} {plural(u, v)}'
    else:
        s = num(v)
    return s + (f' per {d}' if d else '')


def conv(a, b):
    """How many b make one a (None when the units are unrelated)."""
    if a == b or (a in PEOPLE and b in PEOPLE and 'person' in (a, b)):
        return F(1)
    if (a, b) in CAL:
        return F(CAL[a, b])
    if (b, a) in CAL:
        return F(1, CAL[b, a])
    if a in TIME and b in TIME:
        return TIME[a] / TIME[b]
    return None


class Q:
    def __init__(self, v, u=None, d=None, **kw):
        self.v, self.u, self.d = F(v), u, d
        self.sign = kw.get('sign', 0); self.sent = kw.get('sent', 0); self.inq = kw.get('inq', False)
        self.subst = kw.get('subst'); self.pos = kw.get('pos', 10 ** 6); self.cue = kw.get('cue', ''); self.pre = kw.get('pre', '')

    def __repr__(self):
        return f'<{fmt(self.v, self.u, self.d)}{" ?" if self.inq else ""} {self.sign:+d}>'


def sentences(t):
    return [s.strip() for s in re.split(r'(?<=[.!?;])(?<![ap]\.m\.)\s+(?=[A-Za-z"\'($]|\d)|\n+', t) if s.strip()]


def question_of(sents):
    """(index, start offset) of the question: the last sentence with a wh-word or '?'."""
    for i in range(len(sents) - 1, -1, -1):
        m = list(re.finditer(WH, sents[i], re.I))
        if m:
            first = m[0].start()
            # facts stated before the wh-clause of the same sentence stay facts ("If I ... , how many ...")
            cut = max((x.start() for x in m if x.start() == 0 or sents[i][x.start() - 2:x.start()] in (', ', 'n ', 'd ', 'o ', 't ')), default=first)
            return i, cut
        if sents[i].endswith('?'):
            return i, 0
    return None, 0


def extract(t):
    """Quantities of the text in order, the question sentence, and whether every digit was understood."""
    sents = sentences(t)
    qi, qcut = question_of(sents)
    if qi is None:
        return None
    out = []
    pattern = re.compile(r'(?P<cur>[$£€])\s?(?P<m>%s)|(?P<n>%s)\s?(?P<pct>%%|percent\b)?' % (NUM, NUM))
    for si, s in enumerate(sents):
        ms = list(pattern.finditer(s))
        inherited = 0
        for k, m in enumerate(ms):
            pre = s[(ms[k - 1].end() if k else 0):m.start()]
            if out and out[-1].sent == si and out[-1].d == 'each':      # that "each" belongs to the amount before
                pre = re.sub(r'^\s*(?:\w+\s+){0,2}?(each|apiece)\b', ' ', pre, flags=re.I)
            post = s[m.end():(ms[k + 1].start() if k + 1 < len(ms) else len(s))]
            v = F((m['m'] or m['n']).replace(',', ''))
            q = Q(v, sent=si, pos=m.start(), inq=(si == qi and m.start() >= qcut), pre=pre)
            if m['cur']:
                q.u = '$'
            elif m['pct']:
                q.u = '%'
            else:
                w = re.match(r'\s*-?\s*([a-zA-Z]+)\b(?:\s+([a-zA-Z]+)\b)?', post)
                if re.match(r'\s*of (us|them|you|my friends|the \w+)\b', post, re.I):
                    q.u = 'person'
                elif w:
                    w1, w2 = w[1].lower(), (w[2] or '').lower()
                    if w1 in ('dollars', 'dollar', 'bucks', 'euros', 'euro', 'quid'):
                        q.u = '$'; post = post[w.end(1):]
                    elif w1 in ('cents', 'cent'):
                        q.u = '$'; q.v = v / 100; post = post[w.end(1):]
                    elif w1 in ('square', 'sq', 'cubic') and w2:
                        q.u = ('cubic ' if w1 == 'cubic' else 'square ') + unit(w2); post = post[w.end(2):]
                    elif w1 in ADJ and w2 and w2 not in STOP:
                        q.u = unit(w2); post = post[w.end(2):]
                    elif w1 not in STOP and w1 not in ('x', 'am', 'pm'):
                        q.u = unit(w1); post = post[w.end(1):]
            of = re.match(r'\s*of\s+(?:the\s+|my\s+)?([a-z]+)', post, re.I)
            if of and q.u in MEASURE:
                q.subst = of[1].lower(); post = post[of.end():]
            # rate: "$12 a month", "4 litres per hour", "6 litres per 100 km", "$4 each", "each table seats 6"
            den = re.match(r'\s*(?:(?!and\b|but\b|or\b|then\b|so\b)\w+\s+){0,2}?(per|a|an|every|each|for each|for every)\s+(?:(%s)\s+)?([a-z]+)\b' % NUM, post, re.I)
            if den and den[1].lower() in ('a', 'an') and not re.match(r'\s*(a|an)\b', post, re.I):
                den = None
            if den and den[3].lower() not in STOP | {'way', 'while', 'lot', 'bit', 'few', 'little', 'couple', 'total', 'one'} \
                    and not (den[1].lower() in ('a', 'an') and q.u == unit(den[3])):
                q.d = unit(den[3])
                if den[2]:
                    q.v /= F(den[2].replace(',', ''))
                    s = s[:m.end() + (len(s[m.end():]) - len(post)) + den.start(2)] + ' ' * len(den[2]) + s[m.end() + (len(s[m.end():]) - len(post)) + den.end(2):]
                    ms = ms[:k + 1] + [x for x in pattern.finditer(s) if x.start() > m.end()]
            elif re.match(r'\s*(?:(?!and\b|but\b|or\b|then\b|so\b)\w+\s+){0,2}?(each|apiece)\b(?!\s+way)', post, re.I):
                q.d = 'each'
            else:
                e = re.search(r'\b(?:each|every|per)\s+([a-z]+)\b[^,;]*$', pre, re.I)
                pack = re.search(r'\b([a-z]+s) of\s*$', pre, re.I)
                if pack and unit(pack[1]) not in STOP | MEASURE and not m['cur'] and not m['pct']:
                    q.d = unit(pack[1])
                    e = None
                if q.d:
                    pass
                elif e and e[1].lower() not in STOP and not (e[1].lower().endswith('s') and unit(e[1]) not in MEASURE):
                    q.d = unit(e[1])
                elif re.search(r'\beach\b[^,;]*$', pre, re.I):
                    q.d = 'each'
            if re.search(r'\b(each way|both ways|there and back|and back|round trip|return trip|back and forth|to and from|(?:and )?the same (?:again|back|to (?:get|come|go|drive|walk) (?:back|home))|same (?:coming|going|getting) (?:back|home))\b', post, re.I):
                q.v *= 2; q.cue = 'twice'
            cues = [(x.start(), -1) for x in re.finditer(r'\b(?:%s)\b' % NEG, pre, re.I)] + \
                   [(x.start(), 1) for x in re.finditer(r'\b(?:%s)\b' % POS, pre, re.I)] + \
                   [(x.start(), -1 if q.u == '$' else 1) for x in re.finditer(r'\b(?:%s)\b' % BUY, pre, re.I)]
            if re.match(r'\s*(?:\w+\s+){0,2}?(off|discount|less|cheaper)\b', post, re.I):
                cues.append((10 ** 6, -1))
            q.sign = max(cues)[1] if cues else inherited
            inherited = q.sign
            out.append(q)
    return out, sents, qi, qcut


# ---------------------------------------------------------------- clock times
CLOCK = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\b\.?|\b(\d{1,2}):(\d{2})\b|\b(noon|midday|midnight)\b|\b(\d{1,2})\s*o'?clock\b", re.I)
DUR = re.compile(r'(\d+(?:\.\d+)?)\s*-?\s*(hours?|hrs?|h|minutes?|mins?)\b', re.I)


def clock(t):
    q = sentences(t)[-1].lower() if sentences(t) else ''
    times, spans, style = [], [], False
    for m in CLOCK.finditer(t):
        if m[6]:
            v = 0 if m[6].lower() == 'midnight' else 720; style = True
        elif m[3]:
            v = (int(m[1]) % 12 + (12 if m[3].lower() == 'p' else 0)) * 60 + int(m[2] or 0); style = True
        elif m[4]:
            v = int(m[4]) * 60 + int(m[5])
        else:
            v = int(m[7]) * 60
        times.append((m.start(), v, bool(m[3] or m[6]))); spans.append(m.span())
    if not times:
        return None
    # times written without am/pm take the half of the day of a marked time when that keeps them in order
    rest = ''.join(' ' * len(c) if any(a <= i < b for a, b in spans) else c for i, c in enumerate(t))
    durs, every = [], None
    for m in DUR.finditer(rest):
        v = F(m[1]) * (60 if m[2].lower().startswith('h') else 1)
        before = bool(re.match(r'\s*(?:\w+\s+){0,2}?(before|early|earlier|ahead|prior|in advance|beforehand)\b', rest[m.end():], re.I))
        if re.search(r'\bevery\s*$', rest[:m.start()], re.I):
            every = v
        elif durs and m.start() - durs[-1][3] <= 6 and re.fullmatch(r'[\s,]*(and)?\s*', rest[durs[-1][3]:m.start()]):
            durs[-1] = (durs[-1][0], durs[-1][1] + v, before, m.end())
        else:
            durs.append((m.start(), v, before, m.end()))
        rest = rest[:m.start()] + ' ' * (m.end() - m.start()) + rest[m.end():]
    if re.search(r'\d', rest) or re.search(r'\b(pushed|postponed|delayed|brought forward|moved|rescheduled|time zone|timezone)\b', t, re.I):
        return None

    def show(v):
        v = int(v) % 1440; h, m = divmod(v, 60)
        if not style:
            return f'{h}:{m:02d}'
        return f'{(h - 1) % 12 + 1}:{m:02d} {"am" if h < 12 else "pm"}'

    def span(v):
        return fmt(F(v), 'minute') if v >= 60 else f'{num(v)} {plural("minute", v)}'
    asks_when = re.search(r'\b(when|what time|by what time|at what time)\b', q)
    asks_long = re.search(r'\b(how long|how many (hours|minutes)|how much (time|sleep)|duration)\b', q)
    if every and len(times) == 2 and not durs:
        start, arrive = sorted(v for _, v, _ in times)
        wait = (-(arrive - start)) % int(every)
        return f'You wait **{span(wait)}**: the next one after {show(arrive)} is at {show(arrive + wait)}.' if wait else \
            f'No wait: one leaves at {show(arrive)} exactly.'
    if every:
        return None
    if asks_long and len(times) == 2 and not durs:
        a, b = times[0][1], times[1][1]
        gap = (b - a) % 1440 or 1440
        return f'**{span(gap)}** (from {show(a)} to {show(b)}).'
    if asks_when and len(times) == 1 and durs:
        need = re.search(r'\b(should|need|must|have to|latest|supposed)\b', q)
        starty = re.search(r'\b(leave|set off|head out|start|begin|get up|wake|depart|go|put|set (?:the|my|an) alarm|be up|order|book|call)\b', q)
        endy = re.search(r'\b(end|finish\w*|done|over|arrive|land|get there|get back|be back|ready|get home|reach)\b', q)
        back = bool(need and starty and not endy)
        v, steps = times[0][1], [show(times[0][1])]
        for _, d, before, _ in durs:
            sign = -1 if (back or before) else 1
            v += sign * d; steps.append(('− ' if sign < 0 else '+ ') + span(d))
        if not style and v >= 1440:
            return None
        return f'**{show(v)}** ({" ".join(steps)} = {show(v)}).'
    return None


# ---------------------------------------------------------------- "older than", "twice as many as"
def relations(t):
    names = r"([A-Z][a-z]+|I|my \w+|the \w+)"
    eq, val = [], {}
    body = re.sub(r'\b(years?|yrs?) old\b', '', t)
    for s in re.split(r'(?<=[.;!?])\s+|,\s+(?:and|but)\s+|\s+and\s+(?=[A-Z])', body):
        m = re.search(names + r"(?: is| was| has| had| scored| weighs| gets| got| am| have)\s+(%s)\s*(?:\w+\s+){0,2}?(older|younger|taller|shorter|heavier|lighter|more|less|fewer|ahead|behind)\b(?:\s+\w+){0,2}?\s+than\s+" % NUM + names, s)
        if m:
            sign = 1 if m[3] in ('older', 'taller', 'heavier', 'more', 'ahead') else -1
            eq.append((m[1], m[4], F(1), sign * F(m[2].replace(',', '')))); continue
        m = re.search(names + r"(?: is| was| has| had| scored| weighs| am| have)\s+(?:(%s) times|(half))\s+as\s+\w+(?:\s+\w+)?\s+as\s+" % NUM + names, s)
        if m:
            eq.append((m[1], m[4], F(m[2]) if m[2] else F(1, 2), F(0))); continue
        m = re.search(names + r"(?: is| was| has| had| scored| weighs| am| have)\s+(%s)\b(?!\s*(?:times|%%))" % NUM, s)
        if m and not re.search(WH, s, re.I):
            val[m[1]] = F(m[2].replace(',', ''))
    if not eq:
        return None
    for _ in range(len(eq) + 1):
        for a, b, k, c in eq:
            if b in val and a not in val:
                val[a] = k * val[b] + c
            elif a in val and b not in val and k:
                val[b] = (val[a] - c) / k
    q = sentences(t)[-1]
    who = [n for n in val if re.search(r'\b%s\b' % re.escape(n), q)]
    asked = [n for n in {x for e in eq for x in e[:2]} if re.search(r'\b%s\b' % re.escape(n), q)]
    if len(who) != 1 or len(asked) != 1 or not re.search(r'\bhow (old|many|much|tall|heavy|far)\b', q, re.I):
        return None
    n = who[0]
    age = re.search(r'\bhow old\b', q, re.I)
    chain = []
    for a, b, k, c in eq:
        if a in val and b in val:
            how = (f'{num(k)} × {num(val[b])}' if k != 1 else num(val[b])) + (f' {"+" if c > 0 else "−"} {num(abs(c))}' if c else '')
            chain.append(f'{a} = {how} = {num(val[a])}')
    return f'**{num(val[n])}**' + (' years old' if age else '') + f' ({"; ".join(reversed(chain))}).'


# ---------------------------------------------------------------- percentages
def percent(qs, q, text):
    pct = [x for x in qs if x.u == '%']
    base = [x for x in qs if x.u != '%']
    ql = q.lower()
    full = text.lower()
    if re.search(r'\b(what|which|how (?:many|much)) (?:percent\w*|%)|\bpercentage\b', ql) and not pct:
        if len(base) != 2 or (base[0].u or base[1].u) != (base[1].u or base[0].u):
            return None
        a, b = base[0].v, base[1].v
        u = base[0].u or base[1].u
        if re.search(r'\b(discount|off|increase\w*|decrease\w*|drop\w*|r[io]se|risen|went (?:up|down)|reduc\w+|change\w*|cheaper|saving|grew|grow\w*|fell|fall\w*|markup|raise)\b', full):
            if not a:
                return None
            ch = (b - a) / a * 100
            return f'**{num(abs(ch))}%** ({fmt(a, u)} → {fmt(b, u)} is a change of {fmt(abs(b - a), u)}, and {fmt(abs(b - a), u)} ÷ {fmt(a, u)} = {num(abs(ch))}%).'
        whole = next((x.v for x in base if re.search(r'\b(out of|of the|total of|from)\s*$', x.pre, re.I)), max(a, b))
        part = a if whole == b else b
        if not whole:
            return None
        return f'**{num(part / whole * 100)}%** ({num(part)} ÷ {num(whole)} = {num(part / whole)}, × 100).'
    if len(pct) == 1 and len(base) == 1:
        p, b = pct[0].v, base[0]
        share = b.v * p / 100
        near = (pct[0].pre + ' ' + full).lower()
        asks_part = re.search(r'\b(how much|what) (?:\w+ ){0,4}?(tip|tax|discount|saving|interest|deposit|commission|fee|vat)\b|\b(do i|would i|will i|did i) save\b|how much (?:is|was) (?:that|the) (?:tip|tax|discount)', ql)
        after_pct = pct[0].pos > base[0].pos or pct[0].sent > base[0].sent
        of = re.search(r'(?:%|percent)\s*(?:\w+\s+){0,2}?of\b', full)
        if re.search(r'\b(off|discount\w*|sale|reduc\w+|markdown|marked down|cheaper|coupon|cut|drops?|dropped|decreas\w+|fell|falls?|los[te]s?|depreciat\w+)\b', full) and not asks_part:
            return f'**{fmt(b.v - share, b.u)}** ({num(p)}% of {fmt(b.v, b.u)} is {fmt(share, b.u)}, and {fmt(b.v, b.u)} − {fmt(share, b.u)} = {fmt(b.v - share, b.u)}).'
        if re.search(r'\b(tax|tip|vat|interest|increas\w+|raise|rise|rose|markup|gratuity|service charge|surcharge|grows?|grew|goes up|went up|added|plus)\b', full) and not asks_part \
                and re.search(r'\b(total|pay|cost|altogether|now|new|after|with|including|end up|owe|have|be|worth|earn|make|salary|price)\b', ql):
            return f'**{fmt(b.v + share, b.u)}** ({num(p)}% of {fmt(b.v, b.u)} is {fmt(share, b.u)}, and {fmt(b.v, b.u)} + {fmt(share, b.u)} = {fmt(b.v + share, b.u)}).'
        if asks_part or of:
            return f'**{fmt(share, b.u)}** ({num(p)}% of {fmt(b.v, b.u)} = {fmt(b.v, b.u)} × {num(p / 100)}).'
    return None


# ---------------------------------------------------------------- the general unit solver
def target_of(q, facts):
    """(unit wanted, per-unit wanted) from the question sentence."""
    ql = q.lower()
    units = [f.u for f in facts if f.u]
    per = re.search(r'\b(?:per|for each|for one|for a single|each|every|an?)\s+(?!(?:way|year|month|week|day|hour|minute)\b.*\b(?:in|over)\b)([a-z]+)\b(?=[^a-z]*$|\s+(?:cost|costs|pay|pays|get|gets|receive|receives|owe|owes|have|has)\b)', ql)
    d = None
    if per and unit(per[1]) not in STOP:
        d = unit(per[1])
        if d in ('person', 'one', 'friend', 'of', 'guest', 'member') or not any(d == x for x in units):
            d = 'each' if re.search(r'\b(each|per (?:person|head)|apiece|everyone|everybody)\b', ql) else (d if any(d == x for x in units) else None)
    elif re.search(r'\b(each(?: (?:person|one|of (?:us|them)|friend|guest|member))?|per (?:person|head)|apiece|everyone|everybody)\b', ql):
        d = 'each'
    if re.search(r'\bhow (long|much time|much longer)\b', ql):
        return 'time', d
    if re.search(r'\b(how far|what distance|how many (?:km|kilomet\w+|miles|met\w+))\b', ql):
        return next((u for u in units if u in LENGTH), 'length'), d
    if re.search(r'\bhow fast|what speed\b', ql):
        return 'speed', d
    m = re.search(r'\bhow (?:many|much)\s+(?:more\s+|extra\s+|full\s+|whole\s+|total\s+|of the\s+|of\s+)?([a-z]+)((?:\s+[a-z]+){0,2})', ql)
    units += [f.d for f in facts if f.d]
    if m:
        w = m[1]
        if unit(w) not in units and not any(f.subst == w for f in facts):
            for w2 in m[2].split():
                if w2 == 'time':
                    return 'time', d
                if unit(w2) in units or any(f.subst == w2 for f in facts):
                    w = w2; break
            else:
                if m[1] == 'square':
                    return next((f.u for f in facts if f.u and f.u.startswith('square')), None), d
        for f in facts:
            if f.subst and f.subst == w:
                return f.u, d
        if w in ('money', 'cash') or (unit(w) not in units and '$' in units and 'how much' in ql and re.search(r'\b(spen[dt]|pay|paid|cost|costs|price|earn\w*|make|made|owe|save\w*|bill|charge\w*|worth|afford|budget)\b', ql)):
            return '$', d
        if w not in STOP and w not in ('will', 'would', 'must', 'might', 'were'):
            if 'how much' in m[0] and unit(w) not in units:
                return None, d                 # a mass noun that is not a unit ("how much paint"): the unit left over
            return unit(w), d
        if '$' in units and not re.search(r'\bhow many\b', ql):
            return '$', d
        return None, d
    if re.search(r'\b(price|cost|costs|pay|paid|spen[dt]|earn\w*|make|made|owe|bill|total cost|save\w*|charge\w*|income|profit|rent|wage\w*|salary)\b', ql) and '$' in units:
        return '$', d
    return None, d


def same(u, t):
    if t is None or u == t:
        return True
    if t == 'time':
        return u in TIME
    if t == 'length':
        return u in LENGTH
    return conv(u, t) is not None if u and t else False


def general(qs, sents, qi, qcut=0):
    q = sents[qi]
    ql = q.lower()
    asked = ql[qcut:]
    facts = [x for x in qs if not x.inq]
    query = [x for x in qs if x.inq]
    if not facts:
        return None
    steps = []
    # a period named in the question without a number: "in a year", "per week"
    for m in re.finditer(r'\b(?:(?:in|over|for|after|during)\s+(?:a|an|one|the|each)|per|each|every|a|an)\s+(?:whole\s+|full\s+|single\s+)?([a-z]+)\b', asked):
        if unit(m[1]) in TIME and not any(x.u == unit(m[1]) for x in query):
            query.append(Q(1, unit(m[1]), inq=True))
    if re.search(r'\b(yearly|annual\w*)\b', ql):
        query.append(Q(1, 'year', inq=True))
    if re.search(r'\b(weekly)\b', ql):
        query.append(Q(1, 'week', inq=True))
    if re.search(r'\b(monthly)\b', ql):
        query.append(Q(1, 'month', inq=True))
    # numbers written without a unit take the unit of the amount before them ("gives 5 to Mia")
    last = None
    for f in facts:
        if f.u is None:
            f.u = last
        elif f.u not in ('$', '%') and f.d is None:
            last = f.u
        elif last is None and f.d is None:
            last = f.u
    t, per = target_of(q, facts)
    known = [f.u for f in facts + query if f.u and f.u not in ('$', '%') and f.d is None]
    for f in facts:
        if f.u is None and not any(g.d == 'each' and g.sent == f.sent for g in facts):
            f.u = known[0] if known else (t if t not in (None, 'time', 'length', 'speed', '$') else None)
    # a price named by its item ("coffee is $3.50 ... two coffees"): a rate per item
    for f in facts:
        noun = re.search(r"\b([a-z]+)\s+(?:is|are|costs?|was|were|sells? for|goes? for|go for|runs?)\s*(?:only\s+|just\s+|about\s+)?$", f.pre, re.I)
        if f.u == '$' and f.d is None and noun and any(g.d is None and g.u == unit(noun[1]) for g in facts + query) \
                and not any(g.sent == f.sent and g.u == unit(noun[1]) for g in facts):
            f.d = unit(noun[1])
    if per in TIME and any(x.u == per for x in query):
        per = None
    for x in query:
        if x.u is None:
            cands = {f.u for f in facts if f.u and f.d is None} | {f.d for f in facts if f.d and f.d != 'each'}
            cands -= {t}
            x.u = next(iter(cands)) if len(cands) == 1 else None
    # "$4 each": the thing counted in the same sentence, or the subject ("Tickets are $12 each")
    for i, f in enumerate(facts):
        if f.d == 'each':
            near = [g for g in facts[:i] if g.sent == f.sent and g.d is None and g.u not in MEASURE]
            subj = re.search(r'\b([A-Za-z]+s)\s+(?:are|cost|costs|is|were|sell for|go for)\s*(?:only\s+|just\s+|about\s+)?$', f.pre)
            if near:
                f.d = near[-1].u
            elif subj and unit(subj[1]) not in STOP:
                f.d = unit(subj[1])
                for g in facts:
                    if g.u is None and g.sent == f.sent:
                        g.u = f.d
    if any(x.u is None for x in facts + query) or any(f.d == 'each' and not per for f in facts):
        return None
    items = list(facts)

    def use(*xs):
        for x in xs:
            if x in items:
                items.remove(x)

    # 1. Two amounts tied together in one sentence ("250 g for 12 cookies"), scaled to the amount in the question.
    for a, b in zip(facts, facts[1:]):
        if not (a.sent == b.sent and a.d is None and b.d is None and a.u != b.u and conv(a.u, b.u) is None):
            continue
        for x in query + [f for f in facts if f.sent != a.sent and f.d is None and f in items]:
            for mine, other in ((a, b), (b, a)):
                c = conv(x.u, mine.u)
                if c is None or x.d or not same(other.u, t) or not mine.v or (not x.inq and t is None):
                    continue
                amount = x.v * c
                if mine.u in AGENT and other.u in TIME and (t in ('time',) or t in TIME):
                    v = other.v * mine.v / amount
                    steps.append(f'{fmt(mine.v, mine.u)} × {fmt(other.v, other.u)} = {num(other.v * mine.v)} {mine.u}-{plural(other.u, 2)} of work, ÷ {num(amount)} = {fmt(v, other.u)}')
                else:
                    v = other.v * amount / mine.v
                    steps.append(f'{fmt(other.v, other.u)} ÷ {num(mine.v)} × {num(amount)} = {fmt(v, other.u)}')
                use(a, b, x)
                items.append(Q(v, other.u, sent=a.sent, pos=a.pos, sign=other.sign))
                if x in query:
                    query.remove(x)
                break
            else:
                continue
            break
        if per and a in items and b in items and not query:
            for n_, d_ in ((a, b), (b, a)):
                if d_.u == per and d_.v:
                    v = n_.v / d_.v
                    steps.append(f'{fmt(n_.v, n_.u)} ÷ {num(d_.v)} = {fmt(v, n_.u)} per {per}')
                    use(a, b); items.append(Q(v, n_.u, per, sent=a.sent, pos=a.pos)); break
    # 2. Rates: multiply by the amount of their "per" unit, or divide a total by them.
    for _ in range(8):
        changed = False
        for r in [x for x in items if x.d]:
            if r not in items or (per and (r.d == per or (per == 'each' and r.d not in MEASURE))):
                continue                      # used already, or "per person" as wanted: added to each share below
            mult = [x for x in query if x.u == r.d and not x.d]
            plains = [x for x in items if x.d is None and x is not r and (x.u == r.d or x.u in PEOPLE and r.d in PEOPLE and conv(x.u, r.d))]
            if not mult and not plains and not any(x.d and x is not r and (x.u == r.d or (x.u in OCCASION and x.d != r.d)) for x in items):
                mult = [x for x in query if conv(x.u, r.d) is not None and not x.d]
                plains = [x for x in items if x.d is None and x is not r and conv(x.u, r.d) is not None]
            freq = r.u in OCCASION and t != r.u and not any(x.u == r.u or x.d == r.u for x in items if x is not r)
            base = [x for x in items if x is not r and not (x.d and conv(x.d, r.d) is not None)] if freq else []
            chain = [x for x in items if x.d and x is not r and x.u == r.d]
            if chain and not freq:            # rate x rate: "$22 an hour" with "8 hours a day"
                c = chain[0]; v = r.v * c.v
                steps.append(f'{fmt(r.v, r.u)} × {num(c.v)} = {fmt(v, r.u)} per {c.d}')
                use(r, c); items.append(Q(v, r.u, c.d, sent=r.sent, pos=r.pos, sign=r.sign)); changed = True
            elif freq and (len(base) == 1 or (base and all(b.u == base[0].u and b.d == base[0].d for b in base))):
                # a frequency ("5 days a week") multiplies whatever happens each time
                use(r)
                for b in base:
                    v = b.v * r.v
                    steps.append(f'{fmt(b.v, b.u, b.d)} × {num(r.v)} = {fmt(v, b.u)} per {r.d}')
                    if b.d is None:
                        use(b); items.append(Q(v, b.u, r.d, sent=b.sent, pos=b.pos, sign=b.sign))
                    else:
                        b.v, b.d = v, r.d
                changed = True
            elif mult:
                x = mult[0]; amount = x.v * conv(x.u, r.d)
                v = r.v * amount
                steps.append(f'{fmt(r.v, r.u)} × {num(amount)} = {fmt(v, r.u)}' + (f' ({fmt(x.v, x.u)} = {fmt(amount, r.d)})' if x.u != r.d else ''))
                use(r); items.append(Q(v, r.u, sent=r.sent, pos=r.pos, sign=r.sign)); r.done = x; changed = True
            elif plains:
                amount = sum(x.v * conv(x.u, r.d) for x in plains)
                if len(plains) > 1:
                    steps.append(' + '.join(fmt(x.v, x.u) for x in plains) + f' = {fmt(amount, r.d)}')
                v = r.v * amount
                steps.append(f'{fmt(r.v, r.u)} × {num(amount)} = {fmt(v, r.u)}')
                # other rates over the same unit share the amount ("$10 an hour plus $2 an hour bonus")
                twins = [x for x in items if x.d == r.d and x is not r]
                use(r, *([] if twins else plains)); items.append(Q(v, r.u, sent=r.sent, pos=r.pos, sign=r.sign)); changed = True
            elif chain:                       # rate x rate: "2 litres a day" with "5 days a week"
                c = chain[0]; v = r.v * c.v
                steps.append(f'{fmt(r.v, r.u)} × {num(c.v)} = {fmt(v, r.u)} per {c.d}')
                use(r, c); items.append(Q(v, r.u, c.d, sent=r.sent, pos=r.pos, sign=r.sign)); changed = True
            else:
                tot = [x for x in items if x.d is None and x is not r and conv(x.u, r.u) is not None] or \
                      [x for x in query if x.d is None and conv(x.u, r.u) is not None][:1]
                wants_den = (t is None and (r.u != '$' or 'how many' in ql) or same(r.d, t) or (t and r.d == t)) and not (per and per == r.d)
                if tot and wants_den and not (t and t != r.d and same(r.u, t)) and r.v:
                    amount = sum(x.v * conv(x.u, r.u) * (-1 if x.sign < 0 and len(tot) > 1 else 1) for x in tot)
                    v = amount / r.v
                    discrete = r.d not in MEASURE
                    note = ''
                    if discrete and v.denominator != 1:
                        if r.u != '$' and not re.search(r'\b(can|could|afford|full|complete|whole|fit|fill|make|get out of)\b', ql):
                            note = f', so **{fmt(math.ceil(v), r.d)}** are needed (a part-full one still counts)'
                            steps.append(f'{fmt(amount, r.u)} ÷ {num(r.v)} = {num(v)}{note}'); v = F(math.ceil(v))
                        else:
                            whole = F(math.floor(v)); over = amount - whole * r.v
                            steps.append(f'{fmt(amount, r.u)} ÷ {num(r.v)} = {num(v)}, so {fmt(whole, r.d)} with {fmt(over, r.u)} left over'); v = whole
                            r.over = (over, r.u)
                    else:
                        steps.append(f'{fmt(amount, r.u)} ÷ {num(r.v)} = {fmt(v, r.d)}')
                    use(r, *tot); new = Q(v, r.d, sent=r.sent, pos=r.pos); new.over = getattr(r, 'over', None); items.append(new); changed = True
        if not changed:
            break
    # 3. A share for each ("split evenly between 4"): total ÷ people.
    if per:
        rates = [x for x in items if x.d and (x.d == per or per == 'each')]
        heads = [x for x in items if x.d is None and (x.u == per or (per == 'each' and x.u not in MEASURE))]
        money = [x for x in items if x.d is None and x not in heads]
        if len(heads) == 1 and money and all(m.u == money[0].u for m in money) and heads[0].v:
            total = sum(m.v for m in money)
            if len(money) > 1:
                steps.append(' + '.join(fmt(m.v, m.u) for m in money) + f' = {fmt(total, money[0].u)}')
            v = total / heads[0].v
            steps.append(f'{fmt(total, money[0].u)} ÷ {num(heads[0].v)} = {fmt(v, money[0].u)} each')
            use(heads[0], *money); items.append(Q(v, money[0].u, per, sent=money[0].sent, pos=money[0].pos)); rates = [x for x in items if x.d]
        if rates and len(rates) == len(items) and all(r.u == rates[0].u for r in rates):
            v = sum(r.v for r in rates)
            if len(rates) > 1:
                steps.append(' + '.join(fmt(r.v, r.u) for r in rates) + f' = {fmt(v, rates[0].u)}')
            return answer(v, rates[0].u, 'each' if per == 'each' else None, steps, per if per != 'each' else None)
        return None
    if any(x.d for x in items):
        # a rate is the answer itself only when the question asks for one ("how fast")
        return None
    if not items:
        return None
    # 4. What is left is in one unit: add, or take away what was spent, given, used.
    u0 = items[0].u
    if not all(conv(x.u, u0) is not None for x in items):
        if t is None or t in ('time', 'length') or any(x.u in MEASURE for x in items) or not re.search(TOTAL + r'|\bhow many\b', ql):
            return None
        if any(x.u == t for x in items):            # "how many apples" among apples and pears: not a sum
            return None
        steps.append(' + '.join(fmt(x.v, x.u) for x in items) + f' = {num(sum(x.v for x in items))}')
        return answer(sum(x.v for x in items), t, None, steps)
    if t and not all(same(x.u, t) for x in items):
        return None
    items.sort(key=lambda x: (x.sent, x.pos))
    small = min((x.u for x in items), key=lambda u: conv(u, u0))
    vals = [(x.v * conv(x.u, small), x) for x in items]
    if len(vals) == 1:
        v, x = vals[0]
        over = getattr(x, 'over', None)
        if not steps:
            return None
        if over and re.search(r'\b(left|remain\w*|change|over)\b', ql):
            return answer(v, x.u, None, steps, extra=f', with **{fmt(*over)}** left over')
        return answer(v, x.u, None, steps)
    if len(vals) == 2 and re.search(r'\b(profit|difference|gap|how much (?:more|less|longer|taller|older|heavier|further|farther|cheaper|faster)|how many more|how many fewer|loss|gain(?:ed)?|lost overall)\b', asked):
        (a, _), (b, _) = vals
        steps.append(f'{fmt(max(a, b), small)} − {fmt(min(a, b), small)} = {fmt(abs(a - b), small)}')
        return answer(abs(a - b), small, None, steps)
    left = re.search(LEFT, ql) or re.search(r'\bhow (long|much time) do i (?:\w+ )?have\b', ql)
    total = re.search(TOTAL, ql) and not left
    if any(x.inq for _, x in vals):
        return None
    signs = []
    for i, (v, x) in enumerate(vals):
        if i == 0:
            signs.append(1)
        elif total:
            signs.append(-1 if (x.sign < 0 and re.search(r'\b(off|discount\w*|coupon|refund\w*|deduct\w*)\b', x.pre, re.I)) else 1)
        elif left:
            signs.append(1 if x.sign > 0 else -1)
        else:
            mixed = len({y.sign < 0 for _, y in vals}) > 1
            signs.append(-1 if x.sign < 0 and mixed else 1)
    v = sum(s * val for s, (val, _) in zip(signs, vals))
    if v < 0:
        return None
    expr = fmt(vals[0][0], small)
    for s, (val, _) in zip(signs[1:], vals[1:]):
        expr += (' + ' if s > 0 else ' − ') + fmt(val, small)
    steps.append(f'{expr} = {fmt(v, small)}')
    return answer(v, small, None, steps)


def answer(v, u, d, steps, per=None, extra=''):
    head = f'**{fmt(v, u)}**' + (' each' if d == 'each' else f' per {per}' if per else '') + extra
    if not steps:
        return head + '.'
    return head + '.\n\nWorking: ' + '; '.join(steps) + '.'


# ---------------------------------------------------------------- compared options, averages, rectangles
def compare(qs, sents, qi):
    ql = sents[qi].lower()
    m = re.search(r'\b(cheaper|cheapest|less expensive|costs? less|better (?:deal|value)|best (?:deal|value)|more expensive|costs? more|dearer|priciest|faster|quicker|quickest|fastest|slower|longer|shorter|more|less|bigger|smaller|larger|most|least)\b', ql)
    if not m or not re.search(r'\b(which|who|what|whose|is)\b', ql):
        return None
    options = {}
    for x in qs:
        if not x.inq and x.u not in (None, '%'):
            options.setdefault(x.sent, []).append(x)
    if len(options) == 1 and len(next(iter(options.values()))) == 2:
        a, b = next(iter(options.values()))            # "X is $9 a month, Y is $95 a year"
        if a.u == b.u and (a.d or b.d or True):
            options = {('a', a.sent): [a], ('b', b.sent): [b]}
    if len(options) != 2 or [x for x in qs if not x.inq and x.u in (None, '%')]:
        return None
    period = [x for x in qs if x.inq]
    for p in re.finditer(r'\b(?:(?:in|over|for|after)\s+(?:a|an|one|the)|per|each|every|a|an)\s+([a-z]+)\b', ql):
        if unit(p[1]) in TIME:
            period.append(Q(1, unit(p[1])))
    if re.search(r'\b(yearly|annual\w*)\b', ql):
        period.append(Q(1, 'year'))
    if len(period) > 1:
        return None
    vals = []
    for si, xs in options.items():
        if isinstance(si, tuple):
            text = xs[0].pre
            si = si[1]
            label = re.search(r"((?:[A-Za-z0-9']+\s+){1,3}?)(?:costs?|is|are|charges?|sells?|takes?|offers?|has|have|pays?|was)\s*(?:only\s+|just\s+)?$", text)
            label = re.sub(r'^(?:and|but|while|whereas|or)\s+', '', label[1].strip(), flags=re.I) if label else f'the {"first" if not vals else "second"} option'
            vals.append(None)
        else:
            label = None
        if label is not None:
            vals.pop()
            if xs[0].d and period and conv(period[0].u, xs[0].d) is not None:
                amount = period[0].v * conv(period[0].u, xs[0].d)
                vals.append((label, xs[0].v * amount, xs[0].u, f'{fmt(xs[0].v, xs[0].u)} × {num(amount)}' if amount != 1 else fmt(xs[0].v, xs[0].u)))
            elif xs[0].d:
                vals.append((label, xs[0].v, xs[0].u, None, xs[0].d))
            else:
                vals.append((label, xs[0].v, xs[0].u, None))
            continue
        label = re.match(r"\s*((?:[A-Z][\w']*|the|a|an|my|option|plan|store|shop|deal)\s+(?:[A-Za-z0-9']+\s+){0,2}?)(?=(?:costs?|is|are|charges?|sells?|takes?|offers?|has|have|pays?|gives?|was|will|would|uses?)\b)", sents[si])
        label = label[1].strip() if label else f'the {"first" if not vals else "second"} option'
        if len(xs) == 1 and xs[0].d and period and conv(period[0].u, xs[0].d) is not None:
            amount = period[0].v * conv(period[0].u, xs[0].d)
            vals.append((label, xs[0].v * amount, xs[0].u, f'{fmt(xs[0].v, xs[0].u)} × {num(amount)}' if amount != 1 else fmt(xs[0].v, xs[0].u)))
        elif len(xs) == 1 and xs[0].d and not period:
            vals.append((label, xs[0].v, xs[0].u, None, xs[0].d))
        elif len(xs) == 1 and not xs[0].d:
            vals.append((label, xs[0].v, xs[0].u, None))
        elif len(xs) == 2 and not xs[0].d and not xs[1].d and xs[0].u != xs[1].u:
            n_, d_ = (xs[0], xs[1]) if xs[0].u in MEASURE and (xs[1].u not in MEASURE or xs[0].u == '$') else (xs[1], xs[0])
            if not d_.v:
                return None
            vals.append((label, n_.v / d_.v, n_.u, f'{fmt(n_.v, n_.u)} ÷ {num(d_.v)}', d_.u))
        else:
            return None
    (la, va, ua, wa, *da), (lb, vb, ub, wb, *db) = vals
    if da != db:
        if da and db and conv(da[0], db[0]) is not None:      # $12 a month against $120 a year: per the longer period
            big = da[0] if conv(da[0], db[0]) > 1 else db[0]
            va, vb = va * conv(big, da[0]), vb * conv(big, db[0]); da = db = [big]
        else:
            return None
    if conv(ub, ua) is None:
        return None
    vb = vb * conv(ub, ua)
    if va == vb:
        return f'They come out the same: **{fmt(va, ua)}**' + (f' per {da[0]}' if da else '') + ' each.'
    low = m[1] in ('cheaper', 'cheapest', 'less expensive', 'cost less', 'costs less', 'faster', 'quicker', 'quickest', 'fastest', 'shorter', 'less', 'smaller', 'least') \
        or (m[1].startswith(('better', 'best')) and ua == '$')
    if m[1] in ('faster', 'quicker', 'quickest', 'fastest') and ua not in TIME:
        low = False
    win = (la, va, lb, vb) if (va < vb) == low else (lb, vb, la, va)
    suffix = f' per {da[0]}' if da else (f' over {fmt(period[0].v, period[0].u)}' if period else '')
    word = m[1] if not m[1].startswith(('cost', 'best', 'most', 'least')) else {'cost': 'cheaper', 'best': 'the better deal', 'most': 'more', 'least': 'less'}[m[1][:4].strip()]
    work = '; '.join(f'{l}: {w} = {fmt(v, ua)}' for l, v, u, w, *_ in vals if w)
    diff = abs(va - vb)
    return (f'**{win[0][0].upper() + win[0][1:]}** is {word}: {fmt(win[1], ua)} against {fmt(win[3], ua)}{suffix}, '
            f'a difference of **{fmt(diff, ua)}**.' + (f'\n\nWorking: {work}.' if work else ''))


def average(qs, sents, qi):
    if not re.search(r'\b(average|mean)\b', sents[qi], re.I):
        return None
    xs = [x for x in qs if not x.inq]
    if len(xs) < 2 or any(x.d for x in xs) or len({x.u for x in xs if x.u}) > 1:
        return None
    u = next((x.u for x in xs if x.u), None)
    total = sum(x.v for x in xs)
    return f'**{fmt(total / len(xs), u)}** on average ({" + ".join(num(x.v) for x in xs)} = {num(total)}, ÷ {len(xs)}).'


def rectangle(t):
    m = re.search(r'(%s)\s*([a-z]+)?\s*(?:by|x)\s*(%s)\s*([a-z]+)?' % (NUM, NUM), t, re.I)
    q = sentences(t)[-1].lower() if m else ''
    if not m or len(re.findall(NUM, t)) != 2:
        return None
    a, b = F(m[1].replace(',', '')), F(m[3].replace(',', ''))
    u = unit(m[4] or m[2] or '') or None
    if u in STOP:
        u = None
    area = re.search(r'\b(area|square|cover\w*|carpet|turf|tiles?|paint)\b', q)
    peri = re.search(r'\b(perimeter|fenc\w+|around|border|edging|edge|trim|skirting)\b', q)
    if not (area or peri):
        return None
    parts = []
    if area:
        parts.append(f'the area is **{num(a * b)} square {plural(u, 2) if u and u not in ("m", "cm", "km") else (u or "units")}** ({num(a)} × {num(b)})')
    if peri:
        parts.append(f'the distance around is **{fmt(2 * (a + b), u)}** (2 × ({num(a)} + {num(b)}))')
    s = ' and '.join(parts) + '.'
    return s[0].upper() + s[1:]


# ---------------------------------------------------------------- entry points
def solve(text):
    """The worked answer to an arithmetic word problem, or None when it is not one or cannot be solved safely."""
    t = norm(text)
    if not re.search(r'\d', t) or len(t) > 900 or not re.search(WH + r'|\?', t, re.I):
        return None
    if re.search(r'\b(my|his|her|your) (phone number|number|pin|code|password|address|postcode|zip)\b|\b(19|20)\d\d\b', t, re.I):
        return None
    if re.search(r'(?i)\b(?:receive[sd]?|get|gets|got|find|finds|found|buy|buys|bought|lose|loses|lost|give|gives|gave|spend|spends|spent|'
                 r'eat|eats|ate|use|uses|used|sell|sells|sold)\s+(?:away\s+)?(?:some|a few|several|many|a lot|lots|more|a bunch|loads)\b(?!\s+of\s+\d)', t):
        return None                     # "receive some": a change of unknown size, so the total cannot be known
    for fn in (clock, relations, rectangle):
        try:
            r = fn(t)
        except (ZeroDivisionError, ValueError, KeyError, IndexError, TypeError):
            r = None
        if r:
            return r
    if CLOCK.search(t):
        return None
    got = extract(t)
    if not got:
        return None
    qs, sents, qi, qcut = got
    for fn in (lambda: percent(qs, sents[qi], t) if any(x.u == '%' for x in qs) or re.search(r'percent|%', sents[qi], re.I) else None,
               lambda: compare(qs, sents, qi), lambda: average(qs, sents, qi),
               lambda: None if re.search(r'\b(which|who)\b.*\b(cheaper|cheapest|better deal|better value|more expensive|costs? (?:less|more))\b', sents[qi], re.I) else general(qs, sents, qi, qcut)):
        try:
            r = fn()
        except (ZeroDivisionError, ValueError, KeyError, IndexError, TypeError, AttributeError):
            r = None
        if r:
            return r
        if fn is None:
            break
    return None


FOLLOW = re.compile(r"^\s*(?:ok(?:ay)?[,.]?\s+|right[,.]?\s+|thanks[,.!]?\s+)?(?:and|what about|how about|what if|and if|then|now|or)\b", re.I)


def follow_up(messages):
    """"And for 18?" after a solved problem: the same problem with the question's amount replaced."""
    users = [m['content'] for m in messages if m['role'] == 'user']
    last = norm(users[-1])
    nums = re.findall(r'(?<![\w.])[$£€]?%s' % NUM, last)
    if len(users) < 2 or len(last) > 70 or len(nums) != 1 or not (FOLLOW.match(last) or re.fullmatch(r'[^a-z]*%s[^.?!]*[?.!]?' % NUM, last, re.I)):
        return None
    new = nums[0].lstrip('$£€')
    for prev in reversed(users[:-1][-6:]):
        t = norm(prev)
        got = extract(t) if solve(prev) else None
        if not got:
            continue
        qs, sents, qi, _ = got
        query = [x for x in qs if x.inq]
        if re.search(r'%s\s*-?\s*[a-zA-Z]+\s+(?:a|an|per|each|every)\b' % re.escape(nums[0]), last):
            query = [x for x in qs if x.d]         # "and at 100 km an hour?": the rate is what changes
        w = re.search(r'%s\s*-?\s*([a-zA-Z]+)' % re.escape(nums[0]), last)
        named = unit(w[1]) if w and w[1].lower() not in STOP else None
        pick = [x for x in query if named and x.u == named] or (query if len(query) == 1 and (not named or conv(named, query[0].u or '') is None and named not in MEASURE or named == query[0].u) else [])
        if not pick and named:                 # no amount in the question: the stated amount in that unit
            pick = [x for x in qs if not x.inq and x.d is None and x.u == named]
        if len(pick) != 1:
            return None
        x = pick[0]
        qi = x.sent
        s = sents[qi]
        old = re.compile(NUM).match(s, x.pos if not s[x.pos] in '$£€' else x.pos + 1)
        if not old:
            return None
        sents[qi] = s[:old.start()] + new + s[old.end():]
        return solve(' '.join(sents))
    return None


def respond(messages):
    text = messages[-1]['content']
    try:
        reply = solve(text) or follow_up(messages)
    except Exception:
        return None
    if not reply:
        return None
    # money is worked in "$" inside; show the user's own currency when they used only one (2026-11-22, test-informed)
    told = ' '.join(m.get('content', '') for m in messages if m.get('role') == 'user')
    used = {c for c in '$£€' if c in told}
    if len(used) == 1 and used != {'$'}:
        reply = reply.replace('$', used.pop())
    return dict(route='chat/solve-math', response=reply, reasoning=True)
