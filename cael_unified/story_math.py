"""Multi-step word problems as a story of operations (0.4.4 work after release, 2026-11-22). Non-neural.

Each sentence of the problem becomes an operation on a running amount, which carries its unit (money, grams,
millilitres, centimetres, minutes or a plain count):
- **start:** "a tank starts with 14 litres", "a lamp is marked $80", "a 3.2 metre ribbon";
- **build up:** "30 downloads at £4 each", "two 750 ml bottles and half a litre of water", "600 g of oats at £3 per kilo";
- **flows:** "for eight minutes a tap adds 5 litres a minute while a drain lets out two a minute";
- **percent and fractions:** "25% off", "the site takes a quarter", "plus 10% service";
- **charges and amounts taken:** "a $5 handling charge", "keep 200 ml back", "we owe the pianist £18", "draw off 6 litres";
- **pieces:** "cut into four equal lengths", then "each length needs a knot that uses 15 cm", "trim 5 cm off each end";
- **sharing:** "divided evenly between five people", "the rest goes equally to three singers";
- **portions and budgets:** "each guest gets 150 ml" with "how many portions", "a $100 gift card" with "what balance".
Every stated number must be used by some operation; if one is left over, or units don't fit, the reader stays silent.
"""
import math
import re
from fractions import Fraction

ROUTE = 'chat/story-math'
NUMW = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18,
        'nineteen': 19, 'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90,
        'hundred': 100, 'a dozen': 12, 'dozen': 12}
FRACW = {'half': Fraction(1, 2), 'a half': Fraction(1, 2), 'a third': Fraction(1, 3), 'one third': Fraction(1, 3), 'a quarter': Fraction(1, 4),
         'one quarter': Fraction(1, 4), 'three quarters': Fraction(3, 4), 'two thirds': Fraction(2, 3), 'a fifth': Fraction(1, 5),
         'a tenth': Fraction(1, 10), 'one fifth': Fraction(1, 5), 'one tenth': Fraction(1, 10)}
NUMRX = r'(?:\d+(?:\.\d+)?|(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:-(?:one|two|three|four|five|six|seven|eight|nine))?|' + \
        '|'.join(sorted((k for k in NUMW if ' ' not in k), key=len, reverse=True)) + r'|half\s+an?|an?)'
UNITS = {
    'kg': ('g', 1000), 'kilo': ('g', 1000), 'kilos': ('g', 1000), 'kilogram': ('g', 1000), 'kilograms': ('g', 1000), 'g': ('g', 1), 'gram': ('g', 1),
    'grams': ('g', 1), 'l': ('ml', 1000), 'litre': ('ml', 1000), 'litres': ('ml', 1000), 'liter': ('ml', 1000), 'liters': ('ml', 1000),
    'ml': ('ml', 1), 'millilitre': ('ml', 1), 'millilitres': ('ml', 1), 'milliliter': ('ml', 1), 'milliliters': ('ml', 1),
    'm': ('cm', 100), 'metre': ('cm', 100), 'metres': ('cm', 100), 'meter': ('cm', 100), 'meters': ('cm', 100), 'cm': ('cm', 1),
    'centimetre': ('cm', 1), 'centimetres': ('cm', 1), 'centimeter': ('cm', 1), 'centimeters': ('cm', 1), 'mm': ('cm', Fraction(1, 10)),
    'minute': ('min', 1), 'minutes': ('min', 1), 'min': ('min', 1), 'mins': ('min', 1), 'hour': ('min', 60), 'hours': ('min', 60),
}
UNITRX = r'(?:' + '|'.join(sorted(UNITS, key=len, reverse=True)) + r')'
MONEY = r'([£$€])\s?(\d+(?:,\d{3})*(?:\.\d+)?)'
QTY = r'(' + NUMRX + r')\s*(?:-\s*)?(' + UNITRX + r')\b'


class Skip(Exception):
    pass


def out(text, kind):
    return dict(route=f'{ROUTE}-{kind}', response=text, sources=[], reasoning=True, details=f'{kind} (story_math.py)')


def num(w):
    w = w.lower().strip()
    if re.fullmatch(r'\d+(?:,\d{3})*(?:\.\d+)?', w):
        return Fraction(w.replace(',', ''))
    if re.fullmatch(r'half\s+an?', w):
        return Fraction(1, 2)
    if w in ('a', 'an'):
        return Fraction(1)
    if w in NUMW:
        return Fraction(NUMW[w])
    t, _, o = w.partition('-')
    if t in NUMW and o in NUMW:
        return Fraction(NUMW[t] + NUMW[o])
    raise Skip


def qty(m_num, m_unit):
    dim, f = UNITS[m_unit.lower()]
    return num(m_num) * f, dim


def money_fmt(v, sym):
    v = Fraction(round(v * 100), 100)
    s = f'{float(v):,.2f}'
    if s.endswith('.00'):
        s = s[:-3]
    return f'{sym}{s}' if v >= 0 else f'-{sym}{s[1:] if s.startswith("-") else s}'


def show(v, dim, sym, want=None):
    if dim == 'money':
        return money_fmt(v, sym)
    v = Fraction(v)
    def n(x):
        x = Fraction(x)
        return str(int(x)) if x.denominator == 1 else f'{float(x):.2f}'.rstrip('0').rstrip('.')
    big = want is None and abs(v) >= 1000 and v % 100 == 0
    if dim == 'ml':
        return f'{n(v / 1000)} litres' if want == 'l' or big else f'{n(v)} ml'
    if dim == 'g':
        return f'{n(v / 1000)} kg' if want == 'kg' or want is None and abs(v) >= 1000 and v % 1000 == 0 else f'{n(v)} g'
    if dim == 'cm':
        return f'{n(v / 100)} m' if want == 'm' or want is None and abs(v) >= 1000 and v % 100 == 0 else f'{n(v)} cm'
    if dim == 'min':
        return f'{n(v)} minutes'
    return n(v)


class Story:
    def __init__(self, text):
        self.text = text
        self.value = None
        self.dim = None
        self.sym = ''
        self.pieces = None
        self.share = None
        self.portion = None
        self.budget = None
        self.used = set()
        self.steps = []
        self.item_price = {}
        self.base = 0

    def use(self, m, *groups):
        for g in groups or (0,):
            if m.start(g) >= 0:
                self.used.add((self.base + m.start(g), self.base + m.end(g)))

    def add(self, v, dim, why):
        if self.value is None:
            self.value, self.dim = v, dim
            self.steps.append(f'{why}: {show(v, dim, self.sym)}')
            return
        if dim != self.dim:
            raise Skip
        self.value += v
        self.steps.append(f'{"+" if v >= 0 else "−"} {show(abs(v), dim, self.sym)} ({why}) = {show(self.value, self.dim, self.sym)}')


SIGN_IN = re.compile(r'(?i)\b(?:adds?|added|fills?|pours?\s+in|flows?\s+in|puts?\s+in|in)\b')
SIGN_OUT = re.compile(r'(?i)\b(?:drains?|leaks?|lets?\s+out|empties|takes?\s+out|loses?|out|evaporates?|removes?|pumps?\s+out|uses?|drinks?|burns?)\b')


def run(text):
    st = Story(text)
    prices = {}         # noun -> (money per base unit, dim)
    for m in re.finditer(MONEY + r'\s*(?:per|a|an|each|/)\s*(' + UNITRX + r')\b', text):
        dim, f = UNITS[m[3].lower()]
        before = text[max(0, m.start() - 80):m.start()]
        noun = re.findall(r'(?i)\b([a-z]+)\b', before)
        st.sym = m[1]
        prices[m.start()] = (Fraction(m[2].replace(',', '')) / f, dim, [w.lower() for w in noun[-8:]])
    pos = 0
    for sent in re.split(r'(?<=[.!?;])\s+|\n+', text):
        st.base = text.find(sent, pos)
        pos = st.base + len(sent)
        if sent.strip().endswith('?'):
            cond = re.match(r'(?i)\s*(?:if|when|assuming|given\s+that|suppose)\s+(.+?),\s*(?:how|what|which|who)\b', sent)
            if not cond:
                continue        # the question itself; only a leading condition is a fact ("If each guest gets 150 ml, how many ...?")
            st.base += cond.start(1)
            sent = cond[1]
        clause(st, sent, prices)
    return st


def clause(st, s, prices):
    low = s.lower()
    orig, orig_base = s, st.base
    # prices per unit are read where they are stated
    for m in re.finditer(MONEY + r'\s*(?:per|a|an|each|/)\s*(' + UNITRX + r')\b', s):
        st.use(m, 1, 2, 3)
    # amounts bought by weight or volume at a stated price per unit: "600 g of those oats"
    bought = list(re.finditer(QTY + r'\s+of\s+(?:the\s+|those\s+|these\s+|that\s+)?([a-z]+)', s, re.I))
    if prices and bought and all(re.search(r'(?i)\b(?:kg|kilos?|kilograms?|g|grams?|l|litres?|liters?|ml|m|metres?|meters?)\b', b[2]) for b in bought):
        for m in bought:
            v, dim = qty(m[1], m[2])
            noun = m[3].lower()
            after = s[m.end():m.end() + 40]
            near = re.match(r'\s*(?:costing|at|priced\s+at|for)\s*' + MONEY + r'\s*(?:per|a|an|each|/)\s*(' + UNITRX + r')', after)
            if near:
                dim2, f = UNITS[near[3].lower()]
                price = Fraction(near[2].replace(',', '')) / f
            else:
                def dist(p):        # how far back the noun is from the price; the nearest wins
                    ws = [w.rstrip('s') for w in p[2]]
                    return len(ws) - max(i for i, w in enumerate(ws) if w == noun.rstrip('s')) if noun.rstrip('s') in ws else None
                cand = sorted((dist(p), i, p) for i, p in enumerate(prices.values()) if dist(p) is not None)
                if not cand or len(cand) > 1 and cand[0][0] == cand[1][0]:
                    raise Skip
                price, dim2, _ = cand[0][2]
            if dim2 != dim:
                raise Skip
            st.use(m, 1, 2)
            st.add(v * price, 'money', f'{show(v, dim, "")} of {noun} at {money_fmt(price * (1000 if dim in ("g", "ml") else 100 if dim == "cm" else 1), st.sym)} per '
                   f'{"kg" if dim == "g" else "litre" if dim == "ml" else "metre" if dim == "cm" else "unit"}')
        return
    # count × price each: "30 downloads at £4 each", "3 tickets for $12 each"
    for m in re.finditer(r'(?i)\b(' + NUMRX + r')\s+([a-z]+(?:\s+[a-z]+)?)\s+(?:at|for|costing|priced\s+at)\s+' + MONEY + r'\s*(?:each|apiece|a\s+piece|per\s+\w+)', s):
        st.sym = m[3]
        st.use(m, 1, 4)
        n = num(m[1])
        st.add(n * Fraction(m[4].replace(',', '')), 'money', f'{show(n, None, "")} {m[2]} at {m[3]}{m[4]} each')
        st.base += m.end()
        s = s[m.end():]
        break
    if not s.strip():
        return
    # a price per item stated first, then a count: "Tickets cost $15 each and we bought 6 tickets"
    for m in re.finditer(r'(?i)\b([a-z]+?)s?\s+(?:cost|costs|are|is|sell\s+for|go\s+for)\s+' + MONEY + r'\s*(?:each|apiece|a\s+piece|per\s+\w+)', s):
        st.item_price[m[1].lower()] = (m[2], Fraction(m[3].replace(',', '')))
        st.sym = m[2]
        st.use(m, 3)
    for noun, (sym, price) in list(st.item_price.items()):
        for m in re.finditer(r'(?i)\b(' + NUMRX + r')\s+(?:\w+\s+)?' + re.escape(noun) + r's?\b', s):
            if (st.base + m.start(1), st.base + m.end(1)) in st.used or m[1].lower() in ('a', 'an'):
                continue
            n = num(m[1])
            st.use(m, 1)
            st.add(n * price, 'money', f'{show(n, None, "")} {noun}s at {sym}{price} each')
    if re.search(MONEY + r'\s*(?:per|a|an|each|/)\s*(' + UNITRX + r')\b', s) and not re.search(r'(?i)\b' + QTY, re.sub(MONEY + r'\s*(?:per|a|an|each|/)\s*(' + UNITRX + r')\b', ' ', s)):
        return      # a sentence that only states prices per unit
    # rates over a time: "for eight minutes a tap adds 5 litres a minute while a drain lets out two a minute"
    dur = re.search(r'(?i)\bfor\s+(' + NUMRX + r')\s+(minutes?|hours?|mins?)\b', s)
    rates = list(re.finditer(r'(?i)\b(' + NUMRX + r')(?:\s+(' + UNITRX + r'))?\s+(?:a|an|per|each)\s+(minute|hour|min)\b', s))
    if dur and rates:
        t = num(dur[1]) * (60 if dur[2].lower().startswith('h') else 1)
        st.use(dur, 1)
        net, unit = Fraction(0), None
        parts = []
        for r in rates:
            if r[2]:
                unit = UNITS[r[2].lower()]
            if unit is None:
                raise Skip
            per = 60 if r[3].lower().startswith('h') else 1
            v = num(r[1]) * unit[1] / per
            ctx = s[max(0, r.start() - 40):r.start()]
            last_in = max((x.end() for x in SIGN_IN.finditer(ctx)), default=-1)
            last_out = max((x.end() for x in SIGN_OUT.finditer(ctx)), default=-1)
            sign = -1 if last_out > last_in else 1
            net += sign * v
            parts.append(('+' if sign > 0 else '−') + r[0].strip())
            st.use(r, 1)
        st.add(net * t, unit[0], f'{dur[0].strip()} at {" ".join(parts)}')
        return
    handled = False
    # a start amount
    if st.value is None:
        m = re.search(MONEY, s)
        q = re.search(r'(?i)\b' + QTY, s)
        mult = re.search(r'(?i)\b(' + NUMRX + r')\s+(' + NUMRX + r')\s*(' + UNITRX + r')\b', s)
        if mult and num(mult[1]) > 1 and mult[1].lower() not in ('a', 'an'):
            v, dim = qty(mult[2], mult[3])
            st.use(mult, 1, 2)
            n = num(mult[1])
            st.add(n * v, dim, f'{show(n, None, "")} × {show(v, dim, "")}')
            rest = s[mult.end():]
            base = st.base
            for m2 in re.finditer(r'(?i)\b(?:and|plus|with)\s+(?:a\s+)?' + QTY, rest):
                v2, d2 = qty(m2[1], m2[2])
                st.used.add((base + mult.end() + m2.start(1), base + mult.end() + m2.end(1)))
                st.add(v2, d2, 'added')
            return
        if m and re.search(r'(?i)\b(?:marked|costs?|priced|price|is|was|sells?\s+for|worth|bill|total|earned|earns|made|makes|raised|collected|'
                           r'took\s+in|received|won|saved|has|have|had|starts?\s+with)\b', s[:m.start()] + ' ') and \
                not re.search(r'(?i)\b(?:gift\s+card|voucher|budget|note|card)\b', s[max(0, m.start() - 30):m.end() + 20]) and \
                not re.search(r'\s*(?:per|a|an|each|/)\s*' + UNITRX + r'\b', s[m.end():m.end() + 12]):
            st.sym = m[1]
            st.use(m, 2)
            st.add(Fraction(m[2].replace(',', '')), 'money', 'start')
            s = s[m.end():]
            st.base += m.end()
            handled = True
        elif q and re.search(r'(?i)\b(?:starts?|start(?:ing)?\s+with|has|have|holds?|contains?|there\s+(?:is|are)|is|was|a|an|cut|bought|buy|mix|mixed|'
                             r'combine|combined|pour|poured|take|took|make|use|using|fill|filled)\b', s[:q.start()] + ' '):
            v, dim = qty(q[1], q[2])
            st.use(q, 1)
            st.add(v, dim, 'start')
            s = s[q.end():]
            st.base += q.end()
            handled = True
    low = s.lower()
    # a budget to pay from
    m = re.search(r'(?i)' + MONEY + r'\s*(?:gift\s+card|voucher|note|budget|in\s+my\s+(?:wallet|account))|\b(?:budget|gift\s+card|voucher)\s+of\s+' + MONEY, s)
    if m:
        sym, amt = (m[1], m[2]) if m[1] else (m[3], m[4])
        st.budget = Fraction(amt.replace(',', ''))
        st.sym = st.sym or sym
        st.use(m, 2, 4)
        return
    # percent or fraction taken off or added
    for m in re.finditer(r'(?i)(\d+(?:\.\d+)?)\s*(?:%|per\s*cent|percent)(?:\s+(off|discount|tax|vat|service|tip|commission|fee|surcharge|more|less|extra)\b)?|'
                         r'\b(?:takes?|keeps?|charges?|loses?|deducts?)\s+(a\s+quarter|a\s+third|a\s+half|half|a\s+fifth|a\s+tenth|one\s+third|two\s+thirds|three\s+quarters)\b', s):
        if st.value is None:
            raise Skip
        if m[1]:
            p = Fraction(m[1]) / 100
            kind = (m[2] or '').lower()
            ctx = s[max(0, m.start() - 40):m.start()].lower()
            if kind in ('tax', 'vat', 'service', 'tip', 'surcharge', 'more', 'extra') or re.search(r'\b(?:plus|add|added|rise|raised|increase)\b', ctx):
                f = 1 + p
            elif kind in ('off', 'discount', 'less', 'commission', 'fee') or re.search(r'\b(?:takes?|discount|off|minus|reduce|reduced|cut|deduct)\b', ctx + ' ' + kind):
                f = 1 - p
            else:
                raise Skip
            st.use(m, 1)
        else:
            f = 1 - FRACW[re.sub(r'\s+', ' ', m[3].lower())]
            st.used.add((st.base + m.start(3), st.base + m.end(3)))
        st.value *= f
        st.steps.append(f'× {float(f):g} ({m[0].strip()}) = {show(st.value, st.dim, st.sym)}')
        handled = True
    # added charges: "a $5 handling charge per lamp"
    for m in re.finditer(r'(?i)(?:an?\s+)?' + MONEY + r'\s+(?:\w+\s+)?(?:charge|fee|surcharge|delivery|postage|deposit|tip)\b|'
                         r'\b(?:plus|add|and)\s+' + MONEY + r'\s+(?:for\s+)?(?:delivery|postage|shipping|handling)', s):
        sym, amt = (m[1], m[2]) if m[1] else (m[3], m[4])
        st.sym = st.sym or sym
        st.use(m, 2, 4)
        st.add(Fraction(amt.replace(',', '')), 'money', m[0].strip())
        handled = True
    # cutting into pieces
    m = re.search(r'(?i)\b(?:cut|divide|split|slice|chop|break|pour|portion)\w*\s+(?:[\w.,-]+\s+){0,5}?(?:equally\s+|evenly\s+)?into\s+(' + NUMRX + r')\s+(?:equal\s+)?(\w+)', orig)
    if m and st.value is not None:
        n = num(m[1])
        st.used.add((orig_base + m.start(1), orig_base + m.end(1)))
        st.pieces, st.piece_word = n, m[2].lower()
        st.value /= n
        st.steps.append(f'÷ {show(n, None, "")} {m[2]} = {show(st.value, st.dim, st.sym)} each')
        handled = True
        s2 = s[m.end():]
    # amounts taken per piece: "each length needs a knot that uses up 15 cm", "trim another 5 cm off each end of each length"
    if st.pieces:
        for m in re.finditer(r'(?i)\b' + QTY, s):
            if (st.base + m.start(1), st.base + m.end(1)) in st.used:
                continue
            ctx = s[max(0, m.start() - 60):m.end() + 40].lower()
            if re.search(r'\beach\b|\bper\b', ctx):
                v, dim = qty(m[1], m[2])
                after = re.split(r'[,;]|\bthen\b|\band\b', s[m.end():])[0]
                k = 2 if re.search(r'(?i)\b(?:each|both)\s+ends?\b', after) else 1
                st.use(m, 1)
                st.add(-k * v, dim, f'{"2 × " if k == 2 else ""}{show(v, dim, "")} per {st.piece_word.rstrip("s")}')
                handled = True
        if handled:
            return
    # amounts taken away
    for m in re.finditer(r'(?i)\b(?:keep|keeps|set\s+aside|save|saves|owe|owes|pay|pays|paid|draw\s+off|drew\s+off|pour\s+off|pours?\s+out|remove|removes|'
                         r'take\s+out|takes\s+out|use|uses|used|spend|spends|spent|give\s+away|gives\s+away|gave\s+away|eat|eats|ate|lose|loses|lost|drink|drinks|'
                         r'drank|sell|sells|sold|donate|donates|donated|withdraw|withdraws|withdrew|subtract)\b(?:\s+(?:the|our|my|a|an|another|back|up|off|out)\b)*'
                         r'(?:\s+\w+){0,2}?\s+(?:' + MONEY + r'|' + QTY + r')', s):
        g = 2 if m[1] else 3
        if (st.base + m.start(g), st.base + m.end(g)) in st.used:
            continue        # already read, e.g. "paid a $3 booking fee"
        if st.value is None:
            raise Skip
        if m[1]:
            v, dim = Fraction(m[2].replace(',', '')), 'money'
            st.use(m, 2)
        else:
            v, dim = qty(m[3], m[4])
            st.use(m, 3)
        st.add(-v, dim, m[0].strip())
        handled = True
    # plain additions after the start: "and half a litre of water"
    for m in re.finditer(r'(?i)\b(?:and|plus|with|add|adds|added|then\s+add)\s+(?:another\s+|a\s+further\s+|a\s+)?' + QTY, s):
        if (st.base + m.start(1), st.base + m.end(1)) in st.used or st.value is None:
            continue
        v, dim = qty(m[1], m[2])
        st.use(m, 1)
        st.add(v, dim, 'added')
        handled = True
    # sharing the rest
    m = re.search(r'(?i)\b(?:divid|split|shar|goes|go|went|distribut)\w*\s+(?:\w+\s+){0,6}?(?:evenly|equally)?\s*(?:between|among|amongst|to|by|across)\s+'
                  r'(?:the\s+)?(' + NUMRX + r')\b(?:\s+(\w+))?', s)
    if m and st.value is not None:
        n = num(m[1])
        st.use(m, 1)
        st.share = (n, (m[2] or 'people').lower())
        st.value /= n
        st.steps.append(f'÷ {show(n, None, "")} = {show(st.value, st.dim, st.sym)} each')
        handled = True
    # portion size: "each guest gets 150 ml"
    m = re.search(r'(?i)\beach\s+(\w+)\s+(?:gets?|has|takes?|needs?|receives?|is\s+given|will\s+get)\s+(?:a\s+)?' + QTY, s) or \
        re.search(r'(?i)\b' + QTY + r'\s+(?:per|for\s+each|a)\s+(guest|person|glass|cup|serving|portion|bottle|jar|child)\b', s)
    if m:
        if m.re.pattern.startswith('(?i)\\beach'):
            v, dim = qty(m[2], m[3])
            st.use(m, 2)
        else:
            v, dim = qty(m[1], m[2])
            st.use(m, 1)
        st.portion = (v, dim)
        handled = True


def numbers(text):
    """Spans of every number the reader must account for (not clock times, dates or labels)."""
    spans = []
    for m in re.finditer(r'(?i)(?<![\w.:])(\d+(?:,\d{3})*(?:\.\d+)?)(?![\w:])|\b(' + '|'.join(sorted((k for k in NUMW if ' ' not in k and k not in ('dozen',)), key=len, reverse=True)) +
                         r'|half|a\s+quarter|a\s+third)\b', text):
        g = 1 if m[1] else 2
        if re.search(r'(?i)\b(?:ticket|number|room|stand|platform|gate|page|no\.?|#)\s*$', text[max(0, m.start() - 12):m.start()]):
            continue
        spans.append((m.start(g), m.end(g), m[g]))
    return spans


CNT = r'(\d+|' + '|'.join(sorted((k for k in NUMW if ' ' not in k and k not in ('hundred', 'dozen')), key=len, reverse=True)) + r')'
TAKE = r'(?:used(?:\s+up)?|use|uses|ate|eaten|eat|eats|lost|lose|loses|sold|sell|sells|gave\s+away|give\s+away|broke|broken|breaks?|smash(?:es|ed)?|crush(?:es|ed)?|drop(?:s|ped)|tore|tears|ruin(?:s|ed)|bruis(?:es|ed)|wilt(?:s|ed)|' \
       r'crack(?:s|ed)?|chip(?:s|ped)?|spill(?:s|ed)?|spoil(?:s|ed|t)?|damag(?:es|ed)|threw\s+away|thrown\s+away|' \
       r'took\s+out|taken|took|spent|removed|dropped|went\s+missing|got\s+used(?:\s+up)?|were\s+used(?:\s+up)?|were\s+eaten|were\s+lost|were\s+sold|got\s+lost|got\s+eaten)'


def count_story(text, q):
    """Whole things in groups: '3 boxes with 12 bolts each, used 9' or 'three 12-bolt boxes, nine bolts got used up'."""
    item = re.search(r'(?i)\bhow\s+many\s+(\w+)|\bremaining\s+(?:count|number|amount|total)|\b(?:count|number)\s+(?:left|remaining)|\bhow\s+much\s+is\s+left\b', q)
    if not item:
        return None
    facts = re.sub(r'[^.!?\n]*\?', ' ', text)
    total, steps, used = None, [], []
    m = re.search(r'(?i)\b' + CNT + r'\s+(\w+?)s?\s+(?:with|of|containing|holding|that\s+(?:each\s+)?holds?|each\s+(?:with|holding|containing))\s+' + CNT + r'\s+(?:[a-z]+\s+)?(\w+?)s?(?:\s+each|\s+in\s+each|\s+apiece)\b', facts) or \
        re.search(r'(?i)\b' + CNT + r'\s+(\w+?)s?\s+(?:with|of|containing|holding|that\s+(?:each\s+)?holds?|each\s+(?:with|holding|containing))\s+' + CNT + r'\s+(\w+?)s?(?:\s+each|\s+in\s+each|\s+apiece)?\b', facts) or \
        re.search(r'(?i)\b' + CNT + r'\s+' + CNT + r'-(\w+?)s?\s+(\w+?)s?\b', facts)
    if not m:
        return None
    if m.re.pattern.find('-(') > 0 and '-' in m[0]:
        groups, per, thing, box = num(m[1]), num(m[2]), m[3].lower(), m[4].lower()
    else:
        groups, box, per, thing = num(m[1]), m[2].lower(), num(m[3]), m[4].lower()
    total = groups * per
    used.append((m.start(1), m.end(1)))
    used.append((m.start(2) if '-' in m[0] else m.start(3), m.end(2) if '-' in m[0] else m.end(3)))
    steps.append(f'{show(groups, None, "")} {box}s × {show(per, None, "")} {thing}s = {show(total, None, "")}')
    rest = facts[m.end():]
    off = m.end()
    for t in re.finditer(r'(?i)\b(?:' + TAKE + r')\s+(?:\w+\s+){0,2}?' + CNT + r'(?:\s+(?:of\s+(?:the|them)\s+)?(\w+))?|\b' + CNT + r'\s+(?:of\s+(?:the|them)\s+)?(?:(\w+)\s+)?(?:' + TAKE + r')\b', rest):
        n = t[1] or t[3]
        noun = (t[2] or t[4] or thing).lower()
        if noun.rstrip('s') != thing.rstrip('s') and noun not in ('of', 'them'):
            if not noun.startswith(thing[:4]):
                continue
        v = num(n)
        total -= v
        g = 1 if t[1] else 3
        used.append((off + t.start(g), off + t.end(g)))
        steps.append(f'− {show(v, None, "")} ({t[0].strip()}) = {show(total, None, "")}')
    for t in re.finditer(r'(?i)\b(?:bought|got|found|received|added|add|plus)\s+(?:another\s+)?' + CNT + r'\s+(?:more\s+)?(\w+)', rest):
        if t[2].lower().rstrip('s') != thing.rstrip('s'):
            continue
        v = num(t[1])
        total += v
        used.append((off + t.start(1), off + t.end(1)))
        steps.append(f'+ {show(v, None, "")} ({t[0].strip()}) = {show(total, None, "")}')
    for s, e, w in numbers(facts):
        if not any(a <= s and e <= b for a, b in used):
            return None
    if total < 0 or len(steps) < 2:
        return None
    return out(f'**{show(total, None, "")} {thing}s left.** ' + '; '.join(steps) + '.', 'count')


def respond(messages):
    users = [(m.get('content') or '').strip() for m in messages if m.get('role') == 'user']
    if not users:
        return None
    last = users[-1]
    qs = re.findall(r'[^.!?\n]*\?', last)
    if not qs:
        return None
    q = qs[-1].strip()
    if not re.search(r'(?i)\bhow\s+(?:much|many|long|heavy)\b|\bwhat\s+length\b|\bremaining\s+(?:count|number|amount|total)\b|\b(?:count|number)\s+(?:left|remaining)\b|\bwhat\s+(?:balance|is\s+(?:left|the\s+total)|amount|total)\b|\bwhat\'?s\s+(?:one|each|the)\b.*\b(?:cut|share|cost|total)\b|'
                     r'\bwhat\s+(?:will|would|does|did)\b.*\b(?:cost|left|remain|balance)\b|\bwhat\s+balance\b', q):
        return None
    text = ' '.join(users[-4:])
    if re.search(r'\d{1,2}:\d{2}', text):
        return None
    try:
        got = count_story(text, q)
    except (Skip, KeyError, ValueError):
        got = None
    if got:
        return got
    try:
        st = run(text)
    except (Skip, KeyError, ZeroDivisionError, ValueError):
        return None
    if st.value is None or len(st.steps) < 2 and st.steps[0].startswith('start'):
        return None
    # every number must be accounted for, except counts the question repeats ("across all four")
    qstart = text.rfind(q)
    for s, e, w in numbers(text):
        if any(a <= s and e <= b for a, b in st.used):
            continue
        if qstart >= 0 and s >= qstart:
            try:
                v = num(w)
            except Skip:
                return None
            if st.pieces and v == st.pieces or st.share and v == st.share[0] or v == 1 and w.lower() == 'one':
                continue
        return None
    ql = q.lower()
    want = 'l' if re.search(r'\blitres?\b|\bliters?\b', ql) else 'kg' if re.search(r'\bkilo', ql) else 'm' if re.search(r'\bmetres?\b|\bmeters?\b', ql) and \
        not re.search(r'centi', ql) else 'cm' if re.search(r'\bcentimet|\bcm\b', ql) else 'ml' if re.search(r'\bml\b|millilit', ql) else \
        'g' if re.search(r'\bgrams?\b', ql) else None
    value, dim = st.value, st.dim
    steps = list(st.steps)
    kind = 'value'
    if st.portion and re.search(r'\bhow\s+many\b', ql):
        pv, pd = st.portion
        if pd != dim or pv <= 0:
            return None
        n = math.floor(value / pv)
        rest = value - n * pv
        steps.append(f'{show(value, dim, st.sym)} ÷ {show(pv, pd, st.sym)} = {n}' + (f' with {show(rest, dim, st.sym)} over' if rest else ''))
        return out(f'**{n}.** ' + '; '.join(steps) + '.', 'portions')
    if st.budget is not None and re.search(r'\b(?:balance|left|remain|change|still\s+have)\b', ql):
        if dim != 'money':
            return None
        left = st.budget - value
        steps.append(f'{money_fmt(st.budget, st.sym)} − {money_fmt(value, st.sym)} = {money_fmt(left, st.sym)}')
        return out(f'**{money_fmt(left, st.sym)}.** ' + '; '.join(steps) + '.', 'balance')
    if st.pieces and re.search(r'\b(?:across|altogether|in\s+total|total|all\s+(?:of\s+)?(?:the\s+)?(?:' + NUMRX + r'))\b', ql):
        value = value * st.pieces
        steps.append(f'× {show(st.pieces, None, "")} = {show(value, dim, st.sym, want)}')
        kind = 'pieces-total'
    elif st.pieces and not re.search(r'\beach\b|\bper\b|\bone\b', ql):
        return None
    if value < 0:
        return None
    return out(f'**{show(value, dim, st.sym, want)}.** ' + '; '.join(steps) + '.', kind)
