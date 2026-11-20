"""Small everyday sums said in words, worked out exactly (0.4.4, after an outside blind test).

Each solver reads one common shape of question; anything it cannot read exactly is left to the other desks.
  - Comparisons:         "Which is smaller, minus seven or minus three?"
  - Spoken numbers:      "What's three dozen minus five?"
  - Unit conversions:    "How many hours is 150 minutes?", "how many hours 150 minutes is"
  - What is left:        "How many millimetres are left to reach 1 metre if I already have 64 centimetres?"
  - Differences:         "How many more seats does a coach with 52 seats have than one with 37?"
  - Sharing:             "A carton contains eight bottles." + "If they are shared equally by four people, how many each?"
  - Days of the week:    "Yesterday was Monday. What day is tomorrow?"
  - Sorting:             "Put these in ascending order: 11, 2, 20, 5"
  - Membership:          "All the marbles in this bag are glass. This blue marble is in the bag. What is it made of?"
No model is involved.
"""
import re
from fractions import Fraction

ROUTE = 'chat/reason'
UNITS = {
    'mm': ('length', Fraction(1, 1000)), 'millimetre': ('length', Fraction(1, 1000)), 'millimeter': ('length', Fraction(1, 1000)),
    'cm': ('length', Fraction(1, 100)), 'centimetre': ('length', Fraction(1, 100)), 'centimeter': ('length', Fraction(1, 100)),
    'm': ('length', Fraction(1)), 'metre': ('length', Fraction(1)), 'meter': ('length', Fraction(1)),
    'km': ('length', Fraction(1000)), 'kilometre': ('length', Fraction(1000)), 'kilometer': ('length', Fraction(1000)),
    'mile': ('length', Fraction(1609344, 1000)), 'yard': ('length', Fraction(9144, 10000)), 'foot': ('length', Fraction(3048, 10000)),
    'feet': ('length', Fraction(3048, 10000)), 'inch': ('length', Fraction(254, 10000)), 'inche': ('length', Fraction(254, 10000)),
    'second': ('time', Fraction(1)), 'sec': ('time', Fraction(1)), 'minute': ('time', Fraction(60)), 'min': ('time', Fraction(60)),
    'hour': ('time', Fraction(3600)), 'hr': ('time', Fraction(3600)), 'day': ('time', Fraction(86400)), 'week': ('time', Fraction(604800)),
    'g': ('mass', Fraction(1, 1000)), 'gram': ('mass', Fraction(1, 1000)), 'kg': ('mass', Fraction(1)), 'kilogram': ('mass', Fraction(1)),
    'ml': ('volume', Fraction(1, 1000)), 'millilitre': ('volume', Fraction(1, 1000)), 'milliliter': ('volume', Fraction(1, 1000)),
    'l': ('volume', Fraction(1)), 'litre': ('volume', Fraction(1)), 'liter': ('volume', Fraction(1)),
}
ONES = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17,
        'eighteen': 18, 'nineteen': 19, 'a': 1, 'an': 1}
TENS = {'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90}
GROUPS = {'dozen': 12, 'score': 20, 'hundred': 100, 'thousand': 1000, 'half a dozen': 6}
NUMBER = (r"(?:minus\s+|negative\s+)?(?:\d+(?:\.\d+)?|(?:(?:" + '|'.join(TENS) + r")(?:[\s-](?:" + '|'.join(k for k in ONES if len(k) > 2) +
          r"))?|" + '|'.join(sorted((k for k in ONES if len(k) > 2), key=len, reverse=True)) + r"|an?)(?:\s+(?:dozen|score|hundred|thousand))?"
          r"(?:\s+and\s+a\s+(?:half|quarter))?)")
STRICT = NUMBER.replace("|an?)(?:", ")(?:")          # no "a"/"an": "a coach" is not the number one
DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


def out(text, kind, details):
    return dict(route=ROUTE + '-' + kind, response=text, sources=[], reasoning=True, details=details + ' (word_math.py)')


def value(words):
    """'three dozen' -> 36, 'minus seven' -> -7, '64' -> 64, 'twenty-one' -> 21."""
    t = words.casefold().strip()
    sign = -1 if re.match(r'(?:minus|negative)\s+', t) else 1
    t = re.sub(r'^(?:minus|negative)\s+', '', t)
    part = re.search(r'\s+and\s+a\s+(half|quarter)$', t)
    if part:
        # "three and a half" -> 3.5
        return sign * (value(t[:part.start()]) + Fraction(1, 2 if part[1] == 'half' else 4))
    m = re.fullmatch(r'(.+?)\s+(dozen|score|hundred|thousand)', t)
    times = 1
    if m:
        t, times = m[1], GROUPS[m[2]]
    if re.fullmatch(r'\d+(?:\.\d+)?', t):
        n = Fraction(t)
    else:
        parts = re.split(r'[\s-]+', t)
        n = 0
        for p in parts:
            if p in TENS:
                n += TENS[p]
            elif p in ONES:
                n += ONES[p]
            else:
                raise ValueError(p)
        n = Fraction(n)
    return sign * n * times


def fmt(x):
    x = Fraction(x)
    if x.denominator == 1:
        return f'{x.numerator:,}'
    return f'{float(x):,.4f}'.rstrip('0').rstrip('.')


def unit(word):
    w = word.casefold().rstrip('.')
    for cand in (w, w[:-1] if w.endswith('s') else w, w[:-2] if w.endswith('es') else w):
        if cand in UNITS:
            return cand
    return None


def shown(name, amount):
    one = {'feet': 'foot', 'inche': 'inch'}.get(name, name)
    if amount == 1 or len(one) <= 2:
        return one
    return {'foot': 'feet', 'inch': 'inches'}.get(one, one + 's')


# ------------------------------------------------------------------ comparisons
def compare(text):
    m = re.search(r'(?i)\bwhich (?:one )?is (smaller|bigger|larger|greater|less|lower|higher|more)\b[,:]?\s*(' + NUMBER + r')\s+or\s+(' + NUMBER + r')\s*\??\s*$', text)
    if not m:
        return None
    a, b = value(m[2]), value(m[3])
    if a == b:
        return out(f'They are equal: both are **{fmt(a)}**.', 'compare', 'Compared two numbers')
    small = m[1].lower() in ('smaller', 'less', 'lower')
    pick, other = (m[2], m[3]) if (a < b) == small else (m[3], m[2])
    pv = value(pick)
    words = 'smaller' if small else 'larger'
    note = ' On the number line, the one further below zero is the smaller.' if a < 0 and b < 0 else ''
    return out(f'**{pick.strip()}** ({fmt(pv)}) is {words} than {other.strip()} ({fmt(value(other))}).{note}', 'compare', 'Compared two numbers')


# ------------------------------------------------------------------ spoken arithmetic
OP = {'plus': '+', 'add': '+', 'added to': '+', 'minus': '−', 'take away': '−', 'less': '−', 'times': '×', 'multiplied by': '×',
      'divided by': '÷', 'over': '÷'}


def spoken(text):
    m = re.search(r"(?i)\b(?:what(?:'s| is)|calculate|work out|how much is)\s+(" + NUMBER + r")\s+(plus|minus|times|multiplied by|divided by|"
                  r"take away|less)\s+(" + NUMBER + r")\s*\??\s*$", text)
    if not m or (re.fullmatch(r'\d+(?:\.\d+)?', m[1].strip()) and re.fullmatch(r'\d+(?:\.\d+)?', m[3].strip())):
        return None                                  # plain digits are the other solvers' job
    a, b, op = value(m[1]), value(m[3]), OP[m[2].lower()]
    if op == '÷' and b == 0:
        return None
    r = {'+': a + b, '−': a - b, '×': a * b, '÷': a / b if b else 0}[op]
    return out(f'**{fmt(r)}** ({m[1].strip()} = {fmt(a)}; {fmt(a)} {op} {fmt(b)} = {fmt(r)}).', 'arith', 'Arithmetic said in words')


# ------------------------------------------------------------------ conversions
def convert(text):
    m = (re.search(r'(?i)\bhow many ([a-z]+)\s+(?:(?:is|are)\s+(?:there\s+)?in|is|are|in|make|equals?)\s+(' + NUMBER + r')\s*([a-z]+)\b', text) or
         re.search(r'(?i)\bhow many ([a-z]+)\s+(' + NUMBER + r')\s*([a-z]+)\s+(?:is|are|makes?|equals?)\b', text) or
         re.search(r'(?i)\b(?:convert|turn)\s+(' + NUMBER + r')\s*([a-z]+)\s+(?:in)?to\s+([a-z]+)\b', text))
    if not m:
        return None
    if m.re.pattern.startswith('(?i)\\b(?:convert'):
        amount, src, dst = m[1], m[2], m[3]
    else:
        dst, amount, src = m[1], m[2], m[3]
    us, ud = unit(src), unit(dst)
    if not us or not ud or UNITS[us][0] != UNITS[ud][0] or re.search(r'(?i)\b(?:left|more|remain|need|reach)\b', text):
        return None
    n = value(amount)
    r = n * UNITS[us][1] / UNITS[ud][1]
    extra = ''
    if UNITS[us][0] == 'time' and ud == 'hour' and r.denominator != 1:
        h = int(r)
        extra = f' ({h} h {fmt((r - h) * 60)} min)'
    return out(f'**{fmt(r)} {shown(ud, r)}**{extra} ({fmt(n)} {shown(us, n)} = {fmt(r)} {shown(ud, r)}).', 'convert', 'Unit conversion')


def remaining(text):
    m = re.search(r'(?i)\bhow (?:many|much)\s+(?:more\s+)?([a-z]+)\s+(?:are|is|do i need|do we need|would i need|are needed|is needed)?\s*'
                  r'(?:left|still|more|needed)?\s*(?:left\s+)?to\s+(?:reach|get to|make|hit)\s+(' + STRICT + r')\s*([a-z]+)\b.*?\bif\b[^0-9]*?'
                  r'(' + STRICT + r')\s*([a-z]+)\b', text)
    if not m:
        return None
    want, target, tu, have, hu = m[1], value(m[2]), unit(m[3]), value(m[4]), unit(m[5])
    wu = unit(want)
    if not (wu and tu and hu) or len({UNITS[wu][0], UNITS[tu][0], UNITS[hu][0]}) != 1:
        return None
    left = (target * UNITS[tu][1] - have * UNITS[hu][1]) / UNITS[wu][1]
    return out(f'**{fmt(left)} {shown(wu, left)}** ({fmt(target)} {shown(tu, target)} = {fmt(target * UNITS[tu][1] / UNITS[wu][1])} {shown(wu, 2)}; '
               f'{fmt(have)} {shown(hu, have)} = {fmt(have * UNITS[hu][1] / UNITS[wu][1])} {shown(wu, 2)}; the difference is {fmt(left)}).',
               'left', 'What is left to reach a target, in one unit')


def difference(text):
    m = re.search(r'(?i)\bhow many (?:more|fewer|less)\s+([a-z]+)\b.*?\b(' + STRICT + r')\b.*?\bthan\b(.*)$', text)
    if not m:
        return None
    # after "than", the amount is the last number: "than one with 37" compares with 37, not with "one"
    tail = [x for x in re.findall(r'(?i)\b(' + STRICT + r')\b', m[3]) if x.strip()]
    if not tail:
        return None
    a, b = value(m[2]), value(tail[-1])
    d = abs(a - b)
    return out(f'**{fmt(d)} {m[1]}** ({fmt(max(a, b))} − {fmt(min(a, b))} = {fmt(d)}).', 'difference', 'Difference of two amounts')


def share(text):
    asked = re.search(r'(?i)\bhow many ([a-z]+)', text)
    noun = re.escape(asked[1]) if asked else r'[a-z]+'
    m = re.search(r'(?i)\b(' + STRICT + r')\s+(' + noun + r')\b.*?\b(?:shared|split|divided)\s+(?:out\s+)?(?:equally\s+)?(?:by|between|among|amongst)\s+(' +
                  STRICT + r')\s+([a-z]+)\b.*\bhow many\b', text)
    if not m:
        return None
    n, k = value(m[1]), value(m[3])
    if k == 0:
        return None
    each = n / k
    tail = '' if each.denominator == 1 else f' ({fmt(n % k)} left over if they can\'t be split)'
    return out(f'**{fmt(each)} {m[2] if each != 1 else m[2].rstrip("s")}** each ({fmt(n)} ÷ {fmt(k)} = {fmt(each)}){tail}.', 'share', 'Shared equally')


# ------------------------------------------------------------------ days of the week
def weekday_offset(text):
    """'If today is Saturday, what day will it be in three days?' -> Tuesday; also '... 10 days ago?'."""
    t = text.casefold()
    known = re.search(r'\b(yesterday|today|tomorrow)\s+(?:was|is|will be)\s+(' + '|'.join(DAYS) + r')\b', t)
    m = re.search(r'\bwhat day\b.*?\b(?:in|after)\s+(' + STRICT + r')\s+days?(?:\s+(?:from now|from today|time))?\b|'
                  r'\bwhat day\b.*?\b(' + STRICT + r')\s+days?\s+(from now|from today|later|ago|earlier|before)\b', t)
    if not known or not m:
        return None
    n = int(value(m[1] or m[2]))
    back = bool(m[3] and m[3] in ('ago', 'earlier', 'before'))
    base = {'yesterday': 1, 'today': 0, 'tomorrow': -1}[known[1]]
    today = (DAYS.index(known[2]) + base) % 7
    day = (today + (-n if back else n)) % 7
    return out(f'**{DAYS[day].capitalize()}** (today is {DAYS[today].capitalize()}; {"back" if back else "on"} {n} '
               f'day{"s" if n != 1 else ""}).', 'weekday', 'Days of the week counted on')


MONTHS = dict(january=31, february=28, march=31, april=30, may=31, june=30, july=31, august=31, september=30, october=31,
              november=30, december=31)


def calendar(text):
    """Fixed calendar facts: days in a month or a year, months with 31 days, weeks in a year."""
    t = text.casefold()
    m = re.search(r'\bhow many days\s+(?:are there\s+|are\s+|does\s+)?(?:in\s+)?(' + '|'.join(MONTHS) + r')\b(?:\s+have)?(.*)$', t)
    if m:
        month = m[1]
        if month == 'february':
            if re.search(r'\bleap\b', m[2]) and not re.search(r'\b(?:non-?leap|common|normal|not a leap)\b', m[2]):
                return out('**29** days: February has 29 days in a leap year.', 'calendar', 'A fixed calendar fact')
            if re.search(r'\b(?:non-?leap|common|normal|not a leap)\b', m[2]):
                return out('**28** days in a common year.', 'calendar', 'A fixed calendar fact')
            return out('**28** days, or **29** in a leap year.', 'calendar', 'A fixed calendar fact')
        return out(f'**{MONTHS[month]}** days.', 'calendar', 'A fixed calendar fact')
    m = re.search(r'\bhow many months\s+(?:of the year\s+|in a year\s+|in the year\s+|are there\s+)?(?:have|has|are|with)\s+(?:got\s+)?(28|29|30|31|thirty-one|thirty one|thirty)\s+days\b', t)
    if m:
        n = {'thirty-one': '31', 'thirty one': '31', 'thirty': '30'}.get(m[1], m[1])
        if n == '31':
            return out('**7** months have 31 days: January, March, May, July, August, October and December.', 'calendar', 'A fixed calendar fact')
        if n == '30':
            return out('**4** months have exactly 30 days: April, June, September and November (and 11 months have at least 30).',
                       'calendar', 'A fixed calendar fact')
        return out('**All 12** months have at least 28 days; only February has 28 (29 in a leap year).', 'calendar', 'A fixed calendar fact')
    if re.search(r'\bhow many days\s+(?:are\s+)?(?:there\s+)?in\s+a\s+leap\s+year\b', t):
        return out('**366** days.', 'calendar', 'A fixed calendar fact')
    if re.search(r'\bhow many days\s+(?:are\s+)?(?:there\s+)?in\s+a\s+(?:normal |common |non-leap )?year\b', t):
        return out('**365** days (366 in a leap year).', 'calendar', 'A fixed calendar fact')
    if re.search(r'\bhow many weeks\s+(?:are\s+)?(?:there\s+)?in\s+a\s+year\b', t):
        return out('**52** weeks, plus one day (two in a leap year).', 'calendar', 'A fixed calendar fact')
    return None


# ------------------------------------------------------------------ amounts that change over the conversation
GAIN = r'got|get|bought|buy|received|receive|found|find|earned|earn|won|win|was given|picked up|collected|made|added'
LOSS = (r'gave away|gave|give away|give|lost|lose|used up|used|use|ate|eat|sold|sell|spent|spend|broke|dropped|threw away|cut off|cut|removed|'
        r'drank|poured out|took out|took away|lent|cooked|baked|burned|burnt|boiled|fried|served|wasted|donated|posted|sent')


def running_count(users):
    """'I have 12 stickers.' + 'I gave 5 to my brother.' + 'How many stickers do I have left?' -> 7; also 'A rope is 10 metres long.
    I cut off 3.5 metres. How long is the rest?' -> 6.5 metres. Statements may be spread over several messages."""
    text = ' '.join(users)
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    if not sentences or not sentences[-1].endswith('?'):
        return None
    question = sentences[-1]
    asks = re.search(r'(?i)\bhow (?:many|much|long|tall|heavy|far)\b(?:\s+([a-z]+))?.*\b(?:left|remain|remaining|now|rest|have|got|is there|are there|'
                     r'(?:is|are) (?:still )?(?:in|inside))\b', question)
    if not asks:
        return None
    total, noun, steps, unit_name = None, None, [], None
    clauses = []
    for s in sentences[:-1]:
        # "I spent 7 dollars and then got 4" is two steps; a clause with no subject keeps the speaker's
        parts = [p.strip() for p in re.split(r'(?i)\s*(?:,\s*(?:and\s+then\s+|and\s+|then\s+)?|\s+and then\s+|\s+then\s+|\s+and\s+|;\s*)', s) if p.strip()]
        for i, p in enumerate(parts):
            if i and not re.match(r'(?i)(?:i|we|he|she|they|the|a|an|my|our|then|later|another)\b|\d|(?:' + STRICT + r')\s+[a-z]+\s+(?:of\s+[a-z]+\s+)?(?:was|were|leaked|drained|spilled|evaporated)\b', p):
                p = 'I ' + p
            clauses.append(p.rstrip('.!'))
    for s in clauses:
        before = len(steps)
        m = re.match(r'(?i)^\s*(?:i|we)\s+(?:have|had|own|started with|got|bought|was given|were given)\s+(' + STRICT + r')\s+([a-z]+)\b', s) or \
            re.match(r'(?i)^\s*(?:the|a|an|my|our)\s+(?:[a-z]+\s+)?([a-z]+)\s+(?:is|was|measures|weighs|holds|had|has|contains|contained)\s+(' + STRICT + r')\s*([a-z]+)\b', s)
        if m and re.search(r'\d|\b(?:' + '|'.join(k for k in ONES if len(k) > 2) + r')\b', s[m.end():].lower()):
            return None                           # more numbers in the same clause than were read: refuse rather than miscount
        if m and total is None:
            if m.re.pattern.startswith('(?i)^\\s*(?:i|we)'):
                total, noun = value(m[1]), m[2]
            else:
                total, unit_name, noun = value(m[2]), m[3], m[1]
            steps.append(f'{fmt(total)}')
            continue
        m = re.match(r'(?i)^\s*(?:then\s+|later\s+|after that\s+)?(?:i|we)\s+(?:have\s+|had\s+|just\s+)?(' + GAIN + '|' + LOSS + r')\s+(?:away\s+)?(' + STRICT +
                     r')\s*([a-z]+)?\b', s)
        if not m and total is not None:
            # "my friend gave me 7 more" (a gain); "35 litres leaked out", "60 litres were added" (the amount comes first);
            # "I bought a book for 8 dollars" (money spent)
            g = re.match(r'(?i)^\s*(?:then\s+|later\s+)?(?:my|a|an|the|his|her|their|our)?\s*[a-z]+(?:\s+[a-z]+)?\s+(?:gave|handed|sent|lent|paid)\s+(?:me|us)\s+'
                         r'(?:another\s+)?(' + STRICT + r')\s*([a-z]+)?(?:\s+more)?\s*$', s)
            a = re.match(r'(?i)^\s*(?:then\s+|later\s+)?(?:another\s+)?(' + STRICT + r')\s*([a-z]+)?\s+(?:of\s+[a-z]+\s+)?(?:(?:was|were)\s+)?'
                         r'(leaked(?: out)?|drained(?: out)?|spilled|spilt|evaporated|ran out|poured out|taken out|removed|used|eaten|sold|lost|'
                         r'added|poured in|put in|topped up|bought|collected)\s*$', s)
            b = re.match(r'(?i)^\s*(?:then\s+|later\s+)?(?:i|we)\s+(?:bought|paid for|got)\s+(?:a|an|some|the|one)\s+[a-z]+(?:\s+[a-z]+)?\s+for\s+'
                         r'(?:£|\$|€)?(' + STRICT + r')\s*([a-z]+)?\s*$', s)
            if g or a or b:
                hit = g or a or b
                amount, word = value(hit[1]), (hit[2] or '').lower()
                if word and unit_name and unit(word) and unit(unit_name) and unit(word) != unit(unit_name):
                    return None
                if b and not (word.rstrip('s') in ('dollar', 'pound', 'euro', 'cent', 'pence', 'p') or not word):
                    return None
                down = bool(b) or bool(a and not re.match(r'(?i)added|poured in|put in|topped up|bought|collected', a[3]))
                total = total - amount if down else total + amount
                steps.append(f'{"−" if down else "+"} {fmt(amount)}')
                continue
        if m and re.search(r'\d|\b(?:' + '|'.join(k for k in ONES if len(k) > 2) + r')\b', s[m.end():].lower()):
            return None
        if m and total is not None:
            amount = value(m[2])
            word = (m[3] or '').lower()
            if word and unit_name and unit(word) and unit(unit_name) and unit(word) != unit(unit_name):
                return None                       # different units: leave it to the conversion solvers
            if re.fullmatch(LOSS, m[1].lower()):
                total -= amount
                steps.append(f'− {fmt(amount)}')
            else:
                total += amount
                steps.append(f'+ {fmt(amount)}')
            continue
        if total is not None and len(steps) == before and re.search(r'\d|\b(?:' + '|'.join(k for k in ONES if len(k) > 2) + r')\b', s.lower()):
            return None                           # a step with a number that was not read: refuse rather than miscount
        if total is not None and len(steps) == before and re.search(r'(?i)\b(?:' + GAIN + '|' + LOSS + r'|receive[sd]?|finds?)\b', s):
            return None                           # "receive some": a change of unknown size, so the total is unknown
    if total is None or len(steps) < 2:
        return None
    asked = (asks[1] or '').lower()
    if asked == 'money' and noun and noun.lower().rstrip('s') in ('dollar', 'pound', 'euro', 'cent', 'pence', 'rupee', 'yen', 'franc'):
        asked = ''
    if asked and noun and asked not in ('more', 'much', 'long', 'are', 'is', 'do', 'does', 'have', 'has', 'did', 'was', 'were', 'of', 'left') \
            and asked.rstrip('s') != noun.lower().rstrip('s') \
            and not re.search(r'(?i)\bof\s+' + re.escape(asked.rstrip('s')), ' '.join(sentences[:-1])):    # "2 kilograms of rice"
        if not (unit_name and unit(asks[1]) and unit(asks[1]) == unit(unit_name)):
            return None
    shown_unit = f' {unit_name}' if unit_name else (f' {noun}' if noun else '')
    return out(f'**{fmt(total)}{shown_unit}** ({" ".join(steps)} = {fmt(total)}).', 'count', 'An amount followed through the conversation')


def weekday(text):
    t = text.casefold()
    known = re.search(r'\b(the day after tomorrow|the day before yesterday|yesterday|today|tomorrow)\s+(?:was|is|will be)\s+(' + '|'.join(DAYS) + r')\b', t)
    asked = re.search(r'\bwhat day\s+(?:is|was|will)\s+(?:it\s+)?(the day after tomorrow|the day before yesterday|yesterday|today|tomorrow)\b', t)
    if not known or not asked:
        return None
    offset = {'the day before yesterday': -2, 'yesterday': -1, 'today': 0, 'tomorrow': 1, 'the day after tomorrow': 2}
    day = (DAYS.index(known[2]) - offset[known[1]] + offset[asked[1]]) % 7
    return out(f'**{DAYS[day].capitalize()}** ({known[1]} was {known[2].capitalize()}, so today is '
               f'{DAYS[(DAYS.index(known[2]) - offset[known[1]]) % 7].capitalize()}).', 'weekday', 'Days of the week counted on')


# ------------------------------------------------------------------ sorting
def sort_numbers(text):
    m = re.search(r'(?i)\b(?:put|sort|order|arrange|list)\b.*?\b(ascending|descending|increasing|decreasing|smallest to (?:largest|biggest)|'
                  r'largest to smallest|biggest to smallest|lowest to highest|highest to lowest)\b.*?:\s*((?:-?\d+(?:\.\d+)?\s*,\s*)+(?:and\s+)?-?\d+(?:\.\d+)?)\s*[?.!]*\s*$', text)
    if not m:
        return None
    nums = [Fraction(x) for x in re.findall(r'-?\d+(?:\.\d+)?', m[2])]
    down = re.match(r'(?i)descending|decreasing|largest|biggest|highest', m[1])
    nums.sort(reverse=bool(down))
    return out('**' + ', '.join(fmt(x) for x in nums) + '**' + (' (largest first).' if down else ' (smallest first).'), 'sort', 'Numbers sorted')


# ------------------------------------------------------------------ membership
def membership(text):
    m = re.search(r'(?i)\b(?:all|every one of) (?:the )?([a-z]+?)s?\s+(?:in|on|inside) (?:this|the|that|my) ([a-z]+)\s+(?:are|is) (?:made of |made from )?([a-z]+)\b', text)
    if not m:
        return None
    thing, place, made = m[1], m[2], m[3]
    inside = re.search(r'(?i)\b(?:this|the|that|my)\s+(?:[a-z]+\s+){0,2}' + re.escape(thing) + r'\b\s+(?:is|was)\s+(?:in|on|inside) (?:this|the|that|my) ' + re.escape(place), text)
    asks = re.search(r'(?i)\bwhat is it made (?:of|from)\b|\bwhat (?:is|\'s) it\b|\bis it ' + re.escape(made) + r'\b', text)
    if not inside or not asks:
        return None
    return out(f'**{made.capitalize()}.** Every {thing} in the {place} is {made}, and this {thing} is in the {place}.', 'member',
               'A rule about everything in a group applied to one member')


# ------------------------------------------------------------------ shapes
SHAPES = {'triangle': (3, 3, 3), 'square': (4, 4, 4), 'rectangle': (4, 4, 4), 'rhombus': (4, 4, 4), 'parallelogram': (4, 4, 4),
          'trapezium': (4, 4, 4), 'trapezoid': (4, 4, 4), 'quadrilateral': (4, 4, 4), 'kite': (4, 4, 4), 'pentagon': (5, 5, 5),
          'hexagon': (6, 6, 6), 'heptagon': (7, 7, 7), 'octagon': (8, 8, 8), 'nonagon': (9, 9, 9), 'decagon': (10, 10, 10),
          'hendecagon': (11, 11, 11), 'dodecagon': (12, 12, 12)}
SOLIDS = {'cube': dict(faces=6, edges=12, vertices=8, corners=8), 'cuboid': dict(faces=6, edges=12, vertices=8, corners=8),
          'tetrahedron': dict(faces=4, edges=6, vertices=4, corners=4), 'octahedron': dict(faces=8, edges=12, vertices=6, corners=6),
          'square-based pyramid': dict(faces=5, edges=8, vertices=5, corners=5), 'triangular prism': dict(faces=5, edges=9, vertices=6, corners=6)}


def shape(text):
    m = re.search(r'(?i)\bhow many (sides|corners|vertices|edges|angles|faces)\s+(?:does|do|has|have|is there on|are there on|are there in|'
                  r'(?=an?\s|the\s|one\s))\s*(?:(?:a|an|the|one)\s+)?(?:regular\s+)?([a-z-]+(?: (?!have\b|has\b|got\b)[a-z-]+)?)\s*(?:have|has|got)?'
                  r'\s*[?.!]*\s*$', text)
    if not m:
        return None
    what, name = m[1].lower(), m[2].lower().rstrip('s')
    if name in SHAPES:
        n = SHAPES[name][{'sides': 0, 'edges': 0, 'corners': 1, 'vertices': 1, 'angles': 2}.get(what, 9)] if what != 'faces' else None
        if n is None:
            return None
        return out(f'**{n}.** {"An" if name[0] in "aeiou" else "A"} {name} has {n} {what}.', 'shape', 'Counted from a fixed table of shapes')
    if name in SOLIDS and what in SOLIDS[name]:
        n = SOLIDS[name][what]
        return out(f'**{n}.** {"An" if name[0] in "aeiou" else "A"} {name} has {n} {what}.', 'shape', 'Counted from a fixed table of solids')
    return None


# ------------------------------------------------------------------ a general parser for sums said in words
SCALES = {'hundred': 100, 'thousand': 1000, 'million': 1000000}
WORD_OPS = [  # longest first; (words, token)
    ('to the power of', '^'), ('raised to the power of', '^'), ('multiplied by', '*'), ('divided by', '/'), ('added to', '+'),
    ('take away', '-'), ('square root of', 'sqrt'), ('the square root of', 'sqrt'), ('percent of', '%of'), ('per cent of', '%of'),
    ('% of', '%of'), ('half of', 'half'), ('a half of', 'half'), ('a third of', 'third'), ('a quarter of', 'quarter'),
    ('plus', '+'), ('add', '+'), ('and', '+'), ('minus', '-'), ('less', '-'), ('times', '*'), ('x', '*'), ('over', '/'),
    ('squared', 'sq'), ('cubed', 'cube'), ('double', 'double'), ('twice', 'double'), ('triple', 'triple'), ('negative', 'neg'),
]
PREC = {'+': 1, '-': 1, '*': 2, '/': 2, '%of': 2, '^': 4}
ASK_SUM = re.compile(r"(?i)\b(?:what(?:'s| is| does)|calculate|compute|work out|how much is|evaluate|tell me|what do you get (?:for|from|if you))\s+"
                     r"(.+?)(?:\s+(?:is|equal|equals|make|makes|come to|comes to|give|gives))?\s*\??\s*$")


def words_to_tokens(text):
    """'7 squared minus 9' -> [7, 'sq', '-', 9]; None when a word is not part of a sum."""
    t = text.casefold().replace(',', ' ').replace('×', ' x ').replace('÷', ' / ').replace('−', ' - ')
    t = re.sub(r'(\d)\s*%(?!\s*of)', r'\1 percent', t)
    t = re.sub(r'([+*/^()-])', r' \1 ', t)
    words = t.split()
    out, i, current = [], 0, None

    def flush():
        nonlocal current
        if current is not None:
            out.append(current)
            current = None
    while i < len(words):
        w = words[i]
        matched = False
        for phrase, tok in WORD_OPS:
            p = phrase.split()
            if words[i:i + len(p)] == p:
                if tok == '+' and phrase == 'and' and current is not None and i + 1 < len(words) and words[i + 1] in ONES and \
                        out and out[-1] in SCALES.values():
                    break                           # "one hundred and five": a number, not a sum
                flush()
                out.append(tok)
                i += len(p)
                matched = True
                break
        if matched:
            continue
        if w in ('+', '-', '*', '/', '^', '(', ')'):
            flush()
            out.append(w)
        elif re.fullmatch(r'\d+(?:\.\d+)?', w):
            flush()
            current = Fraction(w)
        elif w in ONES and w not in ('a', 'an'):
            current = (current or 0) + ONES[w] if current is not None and current % 100 >= 20 and ONES[w] < 10 else (
                ONES[w] if current is None else None)
            if current is None:
                return None
            current = Fraction(current)
        elif w in TENS:
            current = Fraction(TENS[w]) if current is None else current + TENS[w]
        elif w in ('dozen', 'score', 'hundred', 'thousand', 'million'):
            current = (current or Fraction(1)) * {'dozen': 12, 'score': 20, **SCALES}[w]
        elif w in ('a', 'an') and i + 1 < len(words) and words[i + 1] in ('dozen', 'hundred', 'thousand', 'score', 'million'):
            current = Fraction(1)
        elif w == 'percent':
            flush()
            out.append('pct')
        elif w in ('the', 'of', 'by', 'is', 'equals', 'please'):
            pass
        else:
            return None
        i += 1
    flush()
    return out


def evaluate(tokens):
    """Shunting-yard over the tokens, with unary minus and the word operators; exact fractions where possible."""
    output, stack, prev = [], [], None
    prefix = {'sqrt', 'half', 'third', 'quarter', 'double', 'triple', 'neg'}
    for tok in tokens:
        if isinstance(tok, Fraction):
            output.append(tok)
        elif tok in ('sq', 'cube', 'pct'):
            output.append(tok)                      # postfix: applies to the value just read
        elif tok in prefix or (tok == '-' and (prev is None or (not isinstance(prev, Fraction) and prev not in ('sq', 'cube', 'pct', ')')))):
            stack.append('neg' if tok == '-' else tok)
        elif tok == '(':
            stack.append(tok)
        elif tok == ')':
            while stack and stack[-1] != '(':
                output.append(stack.pop())
            if not stack:
                raise ValueError('unbalanced')
            stack.pop()
        elif tok in PREC:
            while stack and stack[-1] != '(' and (stack[-1] in prefix or PREC.get(stack[-1], 0) > PREC[tok] or
                                                 (PREC.get(stack[-1], 0) == PREC[tok] and tok != '^')):
                output.append(stack.pop())
            stack.append(tok)
        else:
            raise ValueError(tok)
        prev = tok
    while stack:
        if stack[-1] == '(':
            raise ValueError('unbalanced')
        output.append(stack.pop())
    values = []
    for tok in output:
        if isinstance(tok, Fraction):
            values.append(tok)
        elif tok in ('sq', 'cube', 'pct', 'sqrt', 'half', 'third', 'quarter', 'double', 'triple', 'neg'):
            a = values.pop()
            if tok == 'sqrt':
                if a < 0:
                    raise ValueError('negative root')
                r = Fraction(round(float(a) ** 0.5 * 10 ** 9), 10 ** 9)
                values.append(Fraction(int(round(float(a) ** 0.5))) if int(round(float(a) ** 0.5)) ** 2 == a else r)
            else:
                values.append({'sq': a * a, 'cube': a * a * a, 'pct': a / 100, 'half': a / 2, 'third': a / 3, 'quarter': a / 4,
                               'double': 2 * a, 'triple': 3 * a, 'neg': -a}[tok])
        else:
            b, a = values.pop(), values.pop()
            if tok == '/' and b == 0:
                raise ZeroDivisionError
            if tok == '^' and (b.denominator != 1 or abs(b) > 64):
                raise ValueError('power')
            values.append({'+': a + b, '-': a - b, '*': a * b, '/': a / b if b else 0, '%of': a / 100 * b, '^': a ** int(b)}[tok])
    if len(values) != 1:
        raise ValueError('incomplete')
    return values[0]


def expression(text):
    """'What is 7 squared minus 9?', 'could you tell me what three dozen minus five is?' -> the value, with the sum shown."""
    asks = [s for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip().endswith('?')] or [text.strip()]
    m = ASK_SUM.search(asks[-1])
    if not m:
        return None
    span = re.sub(r'(?i)^(?:(?:what(?:\'s| is)?|how much(?: is)?)\s+)?(?:the (?:answer|result|value) (?:of|to)\s+|is\s+)?', '', m[1]).strip()
    span = re.sub(r'(?i)\s+(?:is|equals|makes|comes to)$', '', span.rstrip('.!? ')).strip()
    tokens = words_to_tokens(span)
    if not tokens or not any(not isinstance(t, Fraction) for t in tokens) or not any(isinstance(t, Fraction) for t in tokens):
        return None
    if tokens == [t for t in tokens if t in ('+',)] or sum(isinstance(t, Fraction) for t in tokens) < 1:
        return None
    if all(isinstance(t, Fraction) or t in ('+', '-', '*', '/') for t in tokens) and re.fullmatch(r'[\d\s.+\-*/()x×÷]+', span):
        return None                                 # plain digit sums are the older solvers' job
    value = evaluate(tokens)
    return out(f'**{fmt(value)}** ({span} = {fmt(value)}).', 'expr', 'A sum said in words, parsed with operator precedence')


# ------------------------------------------------------------------ prices of several items
PRICE = re.compile(r"(?i)\b(?:an?|one|the|each)?\s*([a-z]+(?: [a-z]+)?)\s+costs?\s+(?:£|\$|€)?(\d+(?:\.\d+)?)\s*(pounds?|dollars?|euros?|p|pence|cents?|shekels?)?"
                   r"(?:\s+each|\s+apiece|\s+a piece)?\b")
SYMBOL = {'pound': '£', 'dollar': '$', 'euro': '€'}


def basket(text):
    """'A ticket costs 8 pounds and popcorn costs 3 pounds. How much do two tickets and one popcorn cost?' -> 19 pounds."""
    q = re.search(r'(?i)\b(?:how much|what) (?:do|does|would|will|did)\s+(.+?)\s+cost(?:\s+(?:altogether|in total|together))?\s*\?|'
                  r'\bwhat (?:is|would be|\'s) the (?:total )?(?:cost|price) of\s+(.+?)\s*\?', text)
    if not q:
        return None
    prices, currency = {}, None
    for m in PRICE.finditer(text[:q.start()]):
        name = re.sub(r'^(?:a|an|one|the|each)\s+', '', m[1].lower())
        prices[name.split()[-1].rstrip('s')] = Fraction(m[2])
        currency = currency or (m[3] or '').lower().rstrip('s')
    wanted = q[1] or q[2]
    items = re.findall(r'(?i)(' + STRICT + r'|an?|one)\s+([a-z]+(?: (?!and\b|plus\b)[a-z]+)?)', wanted)
    if not prices or not items:
        return None
    total, parts = Fraction(0), []
    for n, name in items:
        key = name.lower().split()[-1].rstrip('s')
        if key.endswith('ie'):
            key = key[:-2] + 'y'
        if key not in prices:
            return None                           # an item without a price: leave it to the other solvers
        k = Fraction(1) if n.lower() in ('a', 'an', 'one') else value(n)
        total += k * prices[key]
        parts.append(f'{fmt(k)} × {fmt(prices[key])}')
    if len(items) < 1 or re.sub(r'(?i)\b(?:and|,|plus)\b|\s+', '', re.sub(r'(?i)(' + STRICT + r'|an?|one)\s+[a-z]+(?: (?!and\b|plus\b)[a-z]+)?', '', wanted)):
        return None                           # something in the question was not an item
    unit_text = f' {currency}s' if currency in ('pound', 'dollar', 'euro', 'cent', 'shekel') and total != 1 else (f' {currency}' if currency else '')
    shown_total = f'{float(total):.2f}' if re.search(r'\d\.\d\d\b', text[:q.start()]) and total.denominator != 1 else fmt(total)
    return out(f'**{shown_total}{unit_text}** ({" + ".join(parts)} = {shown_total}).', 'basket', 'Prices of several items added up')


# ------------------------------------------------------------------ steps given as instructions
STEP_OPS = [(r'(?:add|plus)\s+(' + STRICT + r')(?:\s+to\s+(?:it|that|the result|this))?', '+'),
            (r'(?:subtract|take away|minus|take)\s+(' + STRICT + r')(?:\s+from\s+(?:it|that|the result|this))?', '-'),
            (r'(?:multiply|times)\s+(?:it|that|the result|this)?\s*by\s+(' + STRICT + r')', '*'), (r'(?:times|multiplied by)\s+(' + STRICT + r')', '*'),
            (r'(?:divide|divided)\s+(?:it|that|the result|this)?\s*by\s+(' + STRICT + r')', '/'), (r'(?:double|triple|halve|square)\s+(?:it|that|the result|this)', 'word')]


def instructions(text):
    """'What do you get if you divide 96 by 8 and then add 5?' -> 17: the first step, then each later step applied in order."""
    m = re.search(r'(?i)\b(?:if you|when you)\s+(?:first\s+)?(?:take\s+(' + STRICT + r')\s+and\s+|start with\s+(' + STRICT + r'),?\s+(?:and\s+)?)?(.+?)\s*\??\s*$', text)
    if not m or not re.search(r'(?i)\bwhat (?:do|would|will) you get\b|\bwhat(?:\'s| is) the (?:result|answer)\b|\bwhat number\b', text):
        return None
    rest = m[3]
    first = re.match(r'(?i)(?:divide|multiply|add|subtract)\s+(' + STRICT + r')\s+(by|to|from)\s+(' + STRICT + r')', rest)
    if m[1] or m[2]:
        total, rest = value(m[1] or m[2]), rest
    elif first:
        a, how, b = value(first[1]), first[2].lower(), value(first[3])
        verb = rest.split()[0].lower()
        total = {'divide': a / b if b else None, 'multiply': a * b, 'add': b + a, 'subtract': b - a}[verb]
        if total is None:
            return None
        rest = rest[first.end():]
    else:
        return None
    shown = [fmt(total)]
    for step in [s for s in re.split(r'(?i)\s*(?:,\s*)?(?:\band then\b|\bthen\b|\band\b|,)\s*', rest) if s.strip()]:
        for pattern, op in STEP_OPS:
            s = re.fullmatch(r'(?i)\s*' + pattern + r'\s*', step)
            if s:
                if op == 'word':
                    w = step.split()[0].lower()
                    total = {'double': total * 2, 'triple': total * 3, 'halve': total / 2, 'square': total * total}[w]
                    shown.append(w)
                else:
                    v = value(s[1])
                    if op == '/' and v == 0:
                        return None
                    total = {'+': total + v, '-': total - v, '*': total * v, '/': total / v}[op]
                    shown.append(f'{op} {fmt(v)}')
                break
        else:
            return None                       # a step that was not read: refuse rather than guess
    return out(f'**{fmt(total)}** ({" ".join(shown)} = {fmt(total)}).', 'steps', 'Steps applied in order')


# ------------------------------------------------------------------ "if … then …" with a stated fact
AUX = {'is', 'are', 'was', 'were', 'be', 'been', 'does', 'do', 'did', 'will', 'the', 'a', 'an', 'it', 'its', 'then', 'gets', 'get', 'got',
       'becomes', 'become', 'became', 'goes', 'go', 'went', 'turns', 'turn', 'turned'}


def lemma(w):
    w = w.lower()
    for end, rep in (('ies', 'y'), ('ied', 'y'), ('ing', ''), ('ed', ''), ('es', ''), ('s', '')):
        if w.endswith(end) and len(w) - len(end) >= 3:
            return w[:-len(end)] + rep
    return w


def clause_key(text):
    """('rain',), negated?) for 'it rains' / 'it did not rain'; ignores small helper words."""
    words = re.findall(r"[a-z']+", text.lower())
    neg = any(w in ('not', "didn't", "doesn't", "isn't", "wasn't", "aren't", "weren't", 'no', 'never', "won't") for w in words)
    keep = tuple(lemma(w) for w in words if w not in AUX and w not in ('not', "didn't", "doesn't", "isn't", "wasn't", "aren't", "weren't", 'never', "won't"))
    return keep, neg


def conditional(text):
    """'If the alarm rings, the dog barks. The dog did not bark. Did the alarm ring?' -> No (the contrapositive)."""
    m = re.search(r'(?i)\bif\s+([^,.]+?)(?:,\s*(?:then\s+)?|\s+then\s+)([^.?]+)\.\s*([^.?]+)\.\s*((?:did|does|is|was|will|has|do)\b[^?]+)\?', text)
    if not m:
        return None
    a, b, fact, q = clause_key(m[1]), clause_key(m[2]), clause_key(m[3]), clause_key(re.sub(r'(?i)^(did|does|is|was|will|has|do)\s+', '', m[4]))
    if a[1] or b[1]:
        return None
    rule = f'"if {m[1].strip()}, {m[2].strip()}"'
    if fact[0] == b[0] and fact[1] and q[0] == a[0]:
        return out(f'**No.** The rule is {rule}, and here the second part did not happen, so the first cannot have happened either.', 'if',
                   'If-then with the result denied (contrapositive)')
    if fact[0] == a[0] and not fact[1] and q[0] == b[0]:
        return out(f'**Yes.** The rule is {rule}, and the first part happened.', 'if', 'If-then with the condition given')
    if fact[0] == b[0] and not fact[1] and q[0] == a[0]:
        return out(f'**Not necessarily.** The rule is {rule}, but the second part could have happened for another reason.', 'if',
                   'If-then: the result alone proves nothing')
    if fact[0] == a[0] and fact[1] and q[0] == b[0]:
        return out(f'**Not necessarily.** The rule is {rule}; it says nothing about what happens otherwise.', 'if',
                   'If-then: a denied condition proves nothing')
    return None


# ------------------------------------------------------------------ rules about everything in a place
def place_rule(text):
    """'No birds in this aviary can swim. A finch lives in this aviary. Can the finch swim?' -> No."""
    m = re.search(r'(?i)\b(all|every|no|none of the)\s+(?:the\s+)?([a-z]+?)s?\s+(?:in|on|at|inside)\s+(?:this|the|that|my|our)\s+([a-z]+)\s+'
                  r'(?:can|are|is|have|has)\s+(?:not\s+)?([a-z]+)', text)
    if not m:
        return None
    kind, place, prop = m[2].lower(), m[3].lower(), m[4].lower()
    member = re.search(r'(?:\b(?:[Aa]n?|[Tt]he|[Tt]his|[Tt]hat|[Oo]ur|[Mm]y)\s+([a-z]+)|\b([A-Z][a-z]+))\s+(?:lives|is|sits|stays|was|lies|rests|sleeps)\s+'
                       r'(?:in|on|at|inside)\s+(?:this|the|that|my|our)\s+' + re.escape(place) + r'\b', text)
    asked = re.search(r'(?i)\b(?:can|is|does|has)\s+(?:the|this|that|it|a|an)?\s*([a-z]+)?\s*' + re.escape(prop) + r'\b', text[m.end():])
    if not member or not asked:
        return None
    negative = m[1].lower().startswith('no')
    who = ('the ' + member[1]) if member[1] else member[2]
    if negative:
        return out(f'**No.** Nothing that is a {kind} in the {place} can {prop}, and {who} is in the {place}.', 'place',
                   'A rule about everything in a place applied to one member')
    return out(f'**Yes.** Every {kind} in the {place} can {prop}, and {who} is in the {place}.', 'place',
               'A rule about everything in a place applied to one member')


# ------------------------------------------------------------------ a few fixed constants that web passages often garble
SCALES = {'celsius': 'C', 'centigrade': 'C', 'fahrenheit': 'F', 'kelvin': 'K', 'c': 'C', 'f': 'F', 'k': 'K'}
WATER = {'boil': {'C': '100 °C', 'F': '212 °F', 'K': '373.15 K'}, 'freez': {'C': '0 °C', 'F': '32 °F', 'K': '273.15 K'}}


def constants(text):
    """'What is the boiling point of water in Celsius?' -> 100 °C (at sea-level pressure)."""
    t = text.casefold()
    m = re.search(r'\b(boil|freez|melt)(?:ing)?\s+(?:point|temperature)\s+of\s+(?:pure\s+|fresh\s+)?(water|ice)\b(.*)$', t) or \
        re.search(r'\bat what temperature (?:does|do) (?:pure\s+|fresh\s+)?(water|ice) (boil|freeze|melt)\b(.*)$', t)
    if m:
        if m.re.pattern.startswith(r'\bat'):
            thing, kind, rest = m[1], m[2], m[3]
        else:
            kind, thing, rest = m[1], m[2], m[3]
        kind = 'boil' if kind.startswith('boil') else 'freez'
        scale = re.search(r'\b(celsius|centigrade|fahrenheit|kelvin)\b|°\s*([cfk])\b|\bdegrees\s+([cfk])\b', rest)
        want = SCALES[(scale[1] or scale[2] or scale[3])] if scale else None
        name = 'boils' if kind == 'boil' else 'freezes'
        if want:
            return out(f'**{WATER[kind][want]}.** Pure water {name} at {WATER[kind]["C"]} ({WATER[kind]["F"]}, {WATER[kind]["K"]}) at standard '
                       'sea-level pressure; the point is lower at altitude.' if kind == 'boil' else
                       f'**{WATER[kind][want]}.** Pure water {name} at {WATER[kind]["C"]} ({WATER[kind]["F"]}, {WATER[kind]["K"]}) at standard pressure.',
                       'constant', 'A fixed physical constant')
        return out(f'**{WATER[kind]["C"]}** ({WATER[kind]["F"]}, {WATER[kind]["K"]}) for pure water at standard sea-level pressure.',
                   'constant', 'A fixed physical constant')
    if re.search(r'\b(?:what is|what\'s)\s+absolute zero\b|\babsolute zero\s+in\s+(?:celsius|kelvin|fahrenheit)\b', t):
        return out('**0 K**, which is −273.15 °C (−459.67 °F).', 'constant', 'A fixed physical constant')
    if re.search(r'\b(?:what is|what\'s|how fast is)\s+the\s+speed\s+of\s+light\b(?!.*\b(?:in|through)\s+(?:water|glass|a fibre|fiber))', t):
        return out('**299,792,458 metres per second** in a vacuum (about 300,000 km/s).', 'constant', 'A fixed physical constant')
    return None


# ------------------------------------------------------------------ equal groups, averages, money shared, weeks ahead, orderings
def groups(text):
    """'There are 6 boxes with 12 eggs in each box. How many eggs are there altogether?' -> 72."""
    m = re.search(r'(?i)\b(' + STRICT + r')\s+([a-z]+?)s?\s+(?:with|containing|holding|of|that (?:each )?(?:hold|have|contain))\s+(' + STRICT + r')\s+([a-z]+)'
                  r'(?:\s+(?:in|on)\s+(?:each|every)(?:\s+[a-z]+)?|\s+each)?\s*[.,]\s*how many\s+([a-z]+)\s+(?:are there\s+)?(?:altogether|in total|'
                  r'in all|total|are there(?:\s+altogether|\s+in total)?)\s*\?\s*$', text)
    if not m or re.search(r'(?i)\b(?:left|lost|gave|ate|broke|sold|more|fewer|except|but)\b', text):
        return None
    if stem_word(m[5]) != stem_word(m[4]):
        return None
    try:            # the established groups helper keeps the problems it solves itself (and their follow-ups)
        from . import helper_groups
        own = helper_groups.reply(text, [dict(role='user', content=text)])
        if own is not None and 'clarify' not in str(own.get('route')):
            return None
    except Exception:
        pass
    k, n = value(m[1]), value(m[3])
    return out(f'**{fmt(k * n)} {m[4]}** ({fmt(k)} × {fmt(n)} = {fmt(k * n)}).', 'groups', 'Equal groups multiplied')


def stem_word(w):
    w = w.lower()
    return w[:-3] + 'y' if w.endswith('ies') else w[:-2] if w.endswith(('ches', 'shes', 'xes', 'sses')) else w[:-1] if w.endswith('s') else w


def average(text):
    """'What's the average of 4, 8 and 12?' -> 8."""
    m = re.search(r'(?i)\b(?:average|mean)\s+(?:of\s+)?(?:the\s+numbers\s+)?((?:-?\d+(?:\.\d+)?\s*,\s*)*-?\d+(?:\.\d+)?\s*,?\s*(?:and)\s+-?\d+(?:\.\d+)?)\s*\??\s*$', text)
    if not m:
        return None
    nums = [Fraction(x) for x in re.findall(r'-?\d+(?:\.\d+)?', m[1])]
    mean = sum(nums) / len(nums)
    return out(f'**{fmt(mean)}** ({" + ".join(fmt(x) for x in nums)} = {fmt(sum(nums))}, ÷ {len(nums)} = {fmt(mean)}).', 'average', 'The mean of the numbers')


def money_share(text):
    """'If I split 84 dollars equally between 4 people, how much does each person get?' -> 21 dollars."""
    m = re.search(r'(?i)\b(?:split|share|shared|divide|divided)\s+(?:£|\$|€)?(' + STRICT + r')\s*(dollars?|pounds?|euros?|cents?)?\s+(?:equally\s+|evenly\s+)?'
                  r'(?:between|among|amongst|by)\s+(' + STRICT + r')\s+(?:people|friends|children|kids|of us|of them|persons|players|workers)\b.*\bhow much\b.*\beach\b', text)
    if not m or not (m[2] or re.search(r'[£$€]', text)):
        return None
    total, k = value(m[1]), value(m[3])
    if k == 0:
        return None
    sym = re.search(r'[£$€]', text)
    cur = (m[2] or '').lower()
    each = total / k
    shown_each = (sym[0] if sym and not cur else '') + (f'{float(each):.2f}' if each.denominator != 1 else fmt(each)) + (f' {cur if cur.endswith("s") else cur + "s"}' if cur and each != 1 else (f' {cur}' if cur else ''))
    return out(f'**{shown_each}** each ({fmt(total)} ÷ {fmt(k)} = {fmt(each)}).', 'share', 'An amount of money shared equally')


def weekday_weeks(text):
    """'If today is Saturday, what day will it be in two weeks?' -> Saturday."""
    t = text.casefold()
    known = re.search(r'\b(yesterday|today|tomorrow)\s+(?:was|is|will be)\s+(' + '|'.join(DAYS) + r')\b', t)
    m = re.search(r'\bwhat day\b.*?\b(?:in|after)\s+(' + STRICT + r'|a)\s+weeks?(?:\s+and\s+(' + STRICT + r')\s+days?)?(?:\s+(?:from now|from today|time))?\b|'
                  r'\bwhat day\b.*?\b(' + STRICT + r'|a)\s+weeks?\s+(ago|from now|later|before)\b', t)
    if not known or not m:
        return None
    weeks = int(value(m[1] or m[3]))
    days = int(value(m[2])) if m[2] else 0
    back = m[4] in ('ago', 'before')
    base = {'yesterday': 1, 'today': 0, 'tomorrow': -1}[known[1]]
    today = (DAYS.index(known[2]) + base) % 7
    n = weeks * 7 + days
    day = (today + (-n if back else n)) % 7
    return out(f'**{DAYS[day].capitalize()}** (today is {DAYS[today].capitalize()}; {weeks} week{"s" if weeks != 1 else ""}'
               f'{f" and {days} day" + ("s" if days != 1 else "") if days else ""} is {n} days{", back" if back else ""}).', 'weekday', 'Days of the week counted on')


ORDER_WORDS = {'heavier': 'lighter', 'lighter': 'heavier', 'taller': 'shorter', 'shorter': 'taller', 'older': 'younger', 'younger': 'older',
               'faster': 'slower', 'slower': 'faster', 'bigger': 'smaller', 'smaller': 'bigger', 'longer': 'shorter', 'larger': 'smaller',
               'richer': 'poorer', 'cheaper': 'dearer', 'higher': 'lower', 'lower': 'higher', 'warmer': 'colder', 'colder': 'warmer',
               'stronger': 'weaker', 'weaker': 'stronger', 'wider': 'narrower', 'louder': 'quieter', 'quieter': 'louder'}


def ordering(text):
    """'A box is heavier than a bag. The bag is heavier than a hat. Is the hat heavier than the box?' -> No."""
    def name(x):
        return re.sub(r'(?i)^(?:the|a|an|my|our|this|that)\s+', '', x.strip()).lower()
    q = re.search(r'(?i)(?:^|[.!?]\s+)(?:is|are|was|were|does|do)\s+((?:the |a |an |my )?[a-z]+)\s+(?:run\s+|swim\s+)?([a-z]+er)\s+than\s+((?:the |a |an |my )?[a-z]+)\s*\?\s*$', text)
    if not q or q[2].lower() not in ORDER_WORDS:
        return None
    word = q[2].lower()
    facts = re.findall(r'(?i)(?:^|(?<=[.!?])\s+)((?:the |a |an |my )?[a-z]+)\s+(?:is|are|was|were|runs|swims|grows)\s+(?:much\s+|a bit\s+)?([a-z]+er)\s+than\s+((?:the |a |an |my )?[a-z]+)\s*(?=[.])',
                       text[:q.start() + 1])
    above = set()
    for a, w, b in facts:
        w = w.lower()
        if w == word:
            above.add((name(a), name(b)))
        elif ORDER_WORDS.get(w) == word:
            above.add((name(b), name(a)))
        else:
            return None
    if len(facts) < 1:
        return None
    changed = True
    while changed:
        changed = False
        for a, b in list(above):
            for c, d in list(above):
                if b == c and (a, d) not in above:
                    above.add((a, d)); changed = True
    x, y = name(q[1]), name(q[3])
    things = {t for pair in above for t in pair}
    if x not in things or y not in things:
        return None
    if (x, y) in above:
        return out(f'**Yes.** The {x} is {word} than the {y}, from what you said.', 'order', 'An ordering followed through')
    if (y, x) in above:
        return out(f'**No.** The {y} is {word} than the {x}, so the {x} is {ORDER_WORDS[word]}.', 'order', 'An ordering followed through')
    return out(f'**Not known.** What you said doesn\'t link the {x} and the {y}, so it could be either way.', 'order', 'An ordering followed through')


SOLVERS = (constants, calendar, shape, compare, sort_numbers, weekday_weeks, weekday_offset, weekday, membership, place_rule, conditional, ordering, basket,
           instructions, groups, average, money_share, remaining, difference, convert, expression, spoken)


def respond(messages):
    users = [m.get('content') or '' for m in messages if m.get('role') == 'user']
    if not users:
        return None
    last = users[-1].strip()
    if not last or len(last) > 400:
        return None
    for solver in SOLVERS:
        try:
            got = solver(last)
        except (ValueError, KeyError, ZeroDivisionError, IndexError):
            got = None
        if got is not None:
            return got
    # sharing can need the amount from the turn before: "A carton contains eight bottles." + "shared equally by four..."
    try:
        got = share(last) or (share(' '.join(users[-2:])) if len(users) > 1 and re.search(r'(?i)\b(?:they|them|these|those)\b', last) else None)
    except (ValueError, KeyError, ZeroDivisionError, IndexError):
        got = None
    if got is None:
        try:
            got = running_count(users[-6:])
        except (ValueError, KeyError, ZeroDivisionError, IndexError):
            got = None
    return got
