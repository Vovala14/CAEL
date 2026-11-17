"""The Calculator: everyday sums that run over several turns of a conversation.

solve_math.py solves a word problem stated in one message. People rarely talk like that: they ask one thing, then "and
if I split it with two friends?", "the boxes are $28 each, what's the total?", "and over one year?". The Calculator
reads the whole conversation: the numbers the user gave, and the result CAEL gave last (the bold value in its reply).

  split        "split it equally with two friends", "between the three of us", "my flatmate and I"
  area         "3 m by 4 m" with "covers 1.5 square metres" (how many boxes, rounded up) or "$22 per square metre"
  each         "The boxes are $28 each. What's the total cost?" after a count
  paid hours   a shift's length less an unpaid break
  options      two offers with one-off and recurring costs over a period ("which is cheaper over two years?"), and the
               same again for another period ("and over one year?")
  tip          a bill, a tip in percent, shared between people
  instead      "what if it was 6 metres instead of 5?": the earlier problem again with that number changed
  more facts   "I only have 500 g. How many biscuits can I make?": the earlier statements plus the new one

Every reply shows its working. Exact fractions throughout; nothing is answered unless every step is determined.
"""
import math
import re
from fractions import Fraction as F

WORDS = dict(zero=0, a=1, an=1, one=1, two=2, three=3, four=4, five=5, six=6, seven=7, eight=8, nine=9, ten=10, eleven=11, twelve=12,
             thirteen=13, fourteen=14, fifteen=15, sixteen=16, seventeen=17, eighteen=18, nineteen=19, twenty=20, thirty=30, forty=40,
             fifty=50, sixty=60, couple=2, both=2)
N = r'(?:\d[\d,]*(?:\.\d+)?|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty)'
MONEY = r'(?:\$|£|€)\s?\d[\d,]*(?:\.\d+)?'
PERIOD_MONTHS = dict(day=F(12, 365), week=F(12, 52), month=F(1), year=F(12), quarter=F(3))
LEN = r'(?:m|metres?|meters?|ft|feet|foot|cm|centimetres?|centimeters?|yards?|inches)'


def val(text):
    text = text.strip().lower().replace(',', '')
    if text in WORDS:
        return F(WORDS[text])
    try:
        return F(text)
    except (ValueError, ZeroDivisionError):
        return None


def show(v, money=None):
    """12 -> '12', 11.3333 -> '11.33', money -> '$11.33' ('$224' when whole)."""
    v = F(v)
    if money:
        return f'{money}{int(v):,}' if v.denominator == 1 else f'{money}{float(v):,.2f}'
    if v.denominator == 1:
        return f'{int(v):,}'
    return f'{float(v):,.2f}'.rstrip('0').rstrip('.')


def hours_text(h):
    h = F(h)
    whole, minutes = int(h), int(round((h - int(h)) * 60))
    parts = []
    if whole:
        parts.append(f'{whole} hour{"s" if whole != 1 else ""}')
    if minutes:
        parts.append(f'{minutes} minute{"s" if minutes != 1 else ""}')
    return ' '.join(parts) or '0 hours'


def duration(text):
    """Hours in '7 and a half hours', '7.5 hours', '8 hours 30 minutes', '45 minutes', 'an hour and a half'; None if absent."""
    low = text.lower()
    m = re.search(r'\b(' + N + r'|an?) and a half hours?\b', low)
    if m:
        return val(m[1]) + F(1, 2)
    m = re.search(r'\b(' + N + r'|an?) hours? and a half\b', low)
    if m:
        return val(m[1]) + F(1, 2)
    m = re.search(r'\b(' + N + r'|an?)[- ]hours?(?:\s*(?:and\s*)?(' + N + r')[- ]?(?:minutes?|mins?))?', low)
    if m and val(m[1]) is not None:
        return val(m[1]) + (val(m[2]) / 60 if m[2] else 0)
    m = re.search(r'\bhalf an hour\b', low)
    if m:
        return F(1, 2)
    m = re.search(r'\b(' + N + r')[- ]?(?:minutes?|mins?)\b', low)
    if m:
        return val(m[1]) / 60
    return None


def reply(text, working, route='chat/calc'):
    return dict(route=route, response=f'{text}\n\nWorking: {working}', sources=[], reasoning=True,
                details='Worked out by the Calculator from the numbers in the conversation (calc_agent.py).')


def user_turns(messages):
    return [m['content'] for m in messages if m.get('role') == 'user']


def last_result(messages):
    """(value, money sign or None, unit word or None, text) of the bold result in CAEL's previous reply."""
    for m in reversed(messages[:-1]):
        if m.get('role') != 'assistant':
            continue
        hit = re.search(r'\*\*([^*\n]+)\*\*', m.get('content') or '')
        if not hit:
            return None
        text = hit[1].strip(' .')
        money = re.search(r'(\$|£|€)\s?(\d[\d,]*(?:\.\d+)?)', text)
        if money:
            return F(money[2].replace(',', '')), money[1], None, text
        count = re.search(r'\b(\d[\d,]*(?:\.\d+)?)\s*([a-z]+)?', text)
        if count:
            return F(count[1].replace(',', '')), None, count[2], text
        return None
    return None


def people(text):
    """How many share, from 'with two friends' (3), 'between the three of us' (3), 'my flatmate and I' (2)."""
    low = text.lower()
    m = re.search(r'\b(?:between|among|amongst)\s+(?:the\s+)?(' + N + r')\b', low) or re.search(r'\b(' + N + r')\s+ways\b', low) \
        or re.search(r'\b(' + N + r') (?:of us|people|persons)\b', low)
    if m and val(m[1]):
        return int(val(m[1]))
    m = re.search(r'\bwith (?:my |our )?(' + N + r'|a|an|another|one other)\s+(?:other\s+)?(?:[a-z]+\s+)?(?:friends?|flatmates?|housemates?|roommates?|colleagues?|'
                  r'coworkers?|people|persons?|others?|siblings?|brothers?|sisters?|cousins?|mates?|classmates?|teammates?|neighbou?rs?)\b', low)
    if m:
        n = val(m[1]) if m[1] not in ('another', 'one other') else F(1)
        return int(n) + 1 if n else None
    if re.search(r'\bwith (?:my |a |the )?(?:friend|flatmate|housemate|roommate|partner|wife|husband|brother|sister|mum|mom|dad|girlfriend|boyfriend|colleague|'
                 r'neighbou?r|son|daughter|cousin|mate)\b', low):
        return 2
    m = re.search(r"\b(?:my |the )?(" + N + r") (?:friends?|flatmates?|housemates?|roommates?|others?|colleagues?|siblings?|brothers?|sisters?|kids|children) "
                  r"and (?:i|me|myself)\b", low)
    if m and val(m[1]):
        return int(val(m[1])) + 1
    m = re.search(r"\b(?:me|i|myself) and (?:my )?(" + N + r") (?:friends?|flatmates?|housemates?|others?|colleagues?)\b", low)
    if m and val(m[1]):
        return int(val(m[1])) + 1
    if re.search(r"\b(?:my|the) \w+ and (?:i|me)\b|\b(?:me|i) and (?:my|the) \w+\b|\bthe two of us\b|\bboth of us\b|\bin (?:half|two)\b|\bhalves\b|\b50[/-]50\b", low):
        return 2
    m = re.search(r'\b(' + N + r') (?:friends|flatmates|housemates|people|colleagues|siblings|of them) (?:are |were )?(?:split|shar|divid)', low)
    if m and val(m[1]):
        return int(val(m[1]))
    return None


SPLIT = re.compile(r"(?i)\b(?:split|share|divide|divvy|go halves|going halves)\b|\beach of us\b|\bper person\b|\bbetween (?:the )?(?:\w+ )?of us\b")


def split(messages):
    last = user_turns(messages)[-1]
    if not SPLIT.search(last) or re.search(MONEY, last):
        return None
    got = last_result(messages)
    n = people(last)
    if not got or not n or n < 2 or (got[1] is None and got[2] not in (None, 'km', 'miles', 'hours', 'minutes')):
        return None
    value, money, unit_word, _ = got
    each = value / n
    tail = f' {unit_word}' if unit_word and not money else ''
    note = ' (rounded to the cent)' if money and (each * 100).denominator != 1 else ''
    who = f'the {n} of you' if n > 2 else 'the two of you'
    return reply(f'**{show(each, money)}{tail} each**, split equally between {who}{note}.',
                 f'{show(value, money)}{tail} ÷ {n} = {show(each, money)}{tail}.')


AREA = re.compile(r'(?i)\b(\d+(?:\.\d+)?)\s*(' + LEN + r')?\s*(?:by|x|×)\s*(\d+(?:\.\d+)?)\s*(' + LEN + r')\b')
UNIT_SHORT = {'metre': 'm', 'metres': 'm', 'meter': 'm', 'meters': 'm', 'm': 'm', 'feet': 'ft', 'foot': 'ft', 'ft': 'ft', 'cm': 'cm',
              'centimetres': 'cm', 'centimeters': 'cm', 'centimetre': 'cm', 'centimeter': 'cm', 'yards': 'yd', 'yard': 'yd', 'inches': 'in'}
SQUARE = r'(?:square\s+(?:metres?|meters?|feet|foot|yards?|cm|centimetres?)|sq\.?\s*(?:m|ft|metres?|meters?|feet)|m2|m²|ft2|ft²)'


def area(text):
    """A rectangle 'A by B' with a coverage ('covers C square metres': how many, rounded up) or a price per square unit."""
    m = AREA.search(text)
    if not m:
        return None
    a, b = F(m[1]), F(m[3])
    u = UNIT_SHORT.get((m[4] or m[2] or 'm').lower(), 'm')
    size = a * b
    first = f'{show(a)} {u} × {show(b)} {u} = {show(size)} {u}²'
    low = text.lower()
    cover = re.search(r'(?i)\b(?:covers?|does|do|is enough for|enough for|coverage of|coats?)\s+(?:about\s+|around\s+|up to\s+)?(\d+(?:\.\d+)?)\s*' + SQUARE, text)
    price = re.search(r'(?i)(' + MONEY + r')\s*(?:(?:per|a|an|each|for each)\b|/)\s*' + SQUARE, text)
    item = re.search(r'(?i)\bhow many ([a-z]+)', text)
    if cover and item:
        c = F(cover[1])
        exact = size / c
        n = math.ceil(exact)
        things = item[1].lower()
        one = things[:-2] if things.endswith(('xes', 'ses', 'shes', 'ches')) else things[:-1] if things.endswith('s') else things
        name = things if n != 1 else one
        up = '' if exact.denominator == 1 else f', rounded up to {n} because you cannot buy part of a {one}'
        each = re.search(r'(?i)(' + MONEY + r')\s*(?:each|per|a|apiece)\b', text)
        if each and re.search(r'(?i)\b(?:cost|total|pay|spend|price|how much)\b', text):
            p = F(each[1][1:].replace(',', '').strip())
            return reply(f'**{n} {name}**, costing **{show(n * p, each[1][0])}** in total.',
                         f'{first}; {show(size)} ÷ {show(c)} = {show(exact)}{up}; {n} × {show(p, each[1][0])} = {show(n * p, each[1][0])}.')
        return reply(f'**{n} {name}**.', f'{first}; {show(size)} ÷ {show(c)} = {show(exact)}{up}.')
    if price and re.search(r'\b(?:cost|how much|price|total|pay|spend)\b', low):
        p = F(price[1][1:].replace(',', '').strip())
        return reply(f'**{show(size * p, price[1][0])}**.', f'{first}; {show(size)} × {show(p, price[1][0])} = {show(size * p, price[1][0])}.')
    if re.search(r'\b(?:what(?:\'s| is) the area|how (?:big|large)|how many square)\b', low):
        return reply(f'**{show(size)} {u}²**.', f'{first}.')
    return None


def each_price(messages):
    """'The boxes are $28 each. What's the total cost?' after CAEL worked out how many boxes."""
    last = user_turns(messages)[-1]
    m = re.search(r'(?i)(' + MONEY + r')\s*(?:each|apiece|a piece|per \w+|a (?:box|tin|roll|pack|bag|can|bottle|ticket|piece|unit))\b', last) \
        or re.search(r'(?i)\b(?:cost|costs|are|is)\s+(' + MONEY + r')\b', last)
    if not m or not re.search(r"(?i)\b(?:total|cost|altogether|in all|how much|what(?:'ll| will) (?:that|it) (?:be|cost|come to))\b", last):
        return None
    got = last_result(messages)
    if not got or got[1] is not None or got[0].denominator != 1 or len(re.findall(MONEY, last)) != 1:
        return None
    n, _, unit_word, _ = got
    p = F(m[1][1:].replace(',', '').strip())
    sign = m[1][0]
    things = f' {unit_word}' if unit_word else ''
    return reply(f'**{show(n * p, sign)}** for the {show(n)}{things}.', f'{show(n)} × {show(p, sign)} = {show(n * p, sign)}.')


def paid_hours(messages):
    turns = user_turns(messages)
    last = turns[-1]
    if not re.search(r'(?i)\bunpaid\b', last) or not re.search(r'(?i)\bhow (?:many hours|long|much time)\b.*\bpaid\b|\bpaid (?:for|hours)\b', last):
        return None
    brk = duration(re.sub(r'(?i)\bhow many hours\b.*', '', last))
    shift = None
    for t in reversed(turns[:-1] + [re.sub(r'(?i)\b\d+[- ]?(?:minutes?|mins?)[- ]unpaid.*', '', last)]):
        clean = re.sub(r'\b\d{1,2}[:.]\d{2}\b', ' ', t)
        m = re.search(r"(?i)\b(?:it'?s|is|lasts?|for|work(?:s|ing)?(?: for)?|shift (?:of|is)|long)\b[^.?!]{0,30}", clean)
        d = duration(clean) if re.search(r'(?i)\b(?:hours?|shift|work)\b', clean) else None
        if d and d > F(1):
            shift = d
            break
    if not brk or not shift or brk >= shift:
        return None
    paid = shift - brk
    dec = f' ({show(paid)} hours)' if paid.denominator != 1 else ''
    return reply(f'**{hours_text(paid)}**{dec} paid.', f'{hours_text(shift)} − {hours_text(brk)} unpaid break = {hours_text(paid)}.')


RECUR = re.compile(r'(?i)(' + MONEY + r')\s*(?:of [a-z]+ |(?!a\b|an\b|per\b|each\b|every\b)[a-z]+ (?=every\b|each\b|per\b))?(?:(?:a|an|per|each|every)\b|/)\s*(day|week|month|year|quarter|[a-z]+)\b|'
                   r'(' + MONEY + r')\s*(monthly|weekly|yearly|annually|daily)')
HORIZON = re.compile(r'(?i)\b(?:over|after|for|in|across|during)\s+(?:the (?:first|next) )?(' + N + r'|a|an)?\s*(days?|weeks?|months?|years?)\b')
ADVERB = dict(monthly='month', weekly='week', yearly='year', annually='year', daily='day', annual='year')


def horizon(text):
    m = None
    for m in HORIZON.finditer(text):
        pass
    if not m:
        return None
    n = val(m[1]) if m[1] else F(1)
    unit = m[2].lower().rstrip('s')
    return (n * PERIOD_MONTHS[unit], f'{show(n)} {unit}s' if n != 1 else f'a {unit}') if n else None


def options(messages):
    """Two offers, each with one-off and recurring costs, compared over a period."""
    turns = user_turns(messages)
    last = turns[-1]
    problem, period = None, None
    if (len(re.findall(MONEY, last)) >= 3 or len(re.findall(MONEY, last)) == 2 and len(RECUR.findall(last)) == 2) and \
            re.search(r'(?i)\b(?:cheaper|cheapest|costs? (?:less|more)|better (?:deal|value)|more expensive|save|works? out)\b', last):
        problem, period = last, horizon(last.split('?')[0].rsplit('.', 1)[-1]) or horizon(last)
    elif re.match(r"(?i)\s*(?:and|what about|how about|ok(?:ay)?,?|so)?\s*(?:what about |how about )?(?:over|after|for|in)\b[^.]{0,40}\?\s*$", last):
        period = horizon(last)
        for t in reversed(turns[:-1]):
            if (len(re.findall(MONEY, t)) >= 3 or len(re.findall(MONEY, t)) == 2 and len(RECUR.findall(t)) == 2) and \
                    re.search(r'(?i)\b(?:cheaper|cheapest|costs? (?:less|more)|better (?:deal|value)|more expensive|works? out)\b', t):
                problem = t
                break
    if not problem or not period:
        return None
    months, period_text = period
    # two offers in one sentence ("Option A is $600 per year and option B is $52 per month") are two statements
    problem = re.sub(r'(?i),?\s+(?:and|while|but|whereas)\s+(?=(?:option|plan|offer|deal|tariff|another|the other|the second|one)\b)', '. ', problem)
    sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', problem) if s.strip()]
    usage = {}                                  # 'cartridge' -> per month
    for s in sents:
        for m in re.finditer(r'(?i)\b(' + N + r')\s+([a-z]+?)s?\s+(?:a|per|each|every)\s+(day|week|month|year)\b', s):
            if val(m[1]) is not None and not re.search(MONEY + r'\s*$', s[:m.start()]):
                usage[m[2].lower()] = val(m[1]) / PERIOD_MONTHS[m[3].lower()]
    offers = []
    for s in sents:
        if '?' in s and len(re.findall(MONEY, s)) < 2:
            continue
        amounts = list(re.finditer(MONEY, s))
        if not amounts:
            continue
        label = re.match(r"(?i)\s*(?:the |a |an |one |another |my )?((?:phone |mobile )?(?:plan|option|offer|deal|tariff|contract|package|model) [A-Z0-9]\w*|[A-Z][\w']+(?: [A-Z0-9][\w']*)?"
                         r"|first|second|other|[a-z]+)\b", s)
        if re.match(r"(?i)\s*(?:one|another|the other|the first|the second|a)\s+(?!(?:plan|option|offer|deal|tariff|contract|package|model) [A-Z0-9]\b)", s):
            label = None                        # "One plan costs ...", "Another costs ...": the first and the second
        fixed, recurring, steps = F(0), F(0), []
        spans = []
        for m in RECUR.finditer(s):
            money, unit = (m[1], m[2].lower()) if m[1] else (m[3], ADVERB[m[4].lower()])
            amount = F(money[1:].replace(',', '').strip())
            unit = unit.rstrip('s') if unit not in PERIOD_MONTHS else unit
            if unit in PERIOD_MONTHS:
                times = months / PERIOD_MONTHS[unit]
            elif unit in usage:
                times = usage[unit] * months
            else:
                return None
            recurring += amount * times
            steps.append(f'{show(amount, money[0])} × {show(times)}')
            spans.append((m.start(), m.end()))
        for m in amounts:
            if any(a <= m.start() < b for a, b in spans):
                continue
            amount = F(m[0][1:].replace(',', '').strip())
            fixed += amount
            steps.insert(0, show(amount, m[0][0]))
        if not steps:
            continue
        sign = amounts[0][0][0]
        name = label[1] if label else ''
        offers.append((name, fixed + recurring, ' + '.join(steps), sign))
    if len(offers) != 2:
        return None
    names = []
    for i, (name, total, _, _) in enumerate(offers):
        low = name.lower()
        generic = low in ('one', 'another', 'other', 'first', 'second', 'a', 'an', 'the', '') or not re.search(r'[A-Z]|\b(?:plan|option|offer|deal) ', name)
        names.append(('the first' if i == 0 else 'the second') if generic else name[:1].upper() + name[1:])
    (_, t1, w1, sign), (_, t2, w2, _) = offers
    work = f'{names[0]}: {w1} = {show(t1, sign)}; {names[1]}: {w2} = {show(t2, sign)}.'
    if t1 == t2:
        return reply(f'**They cost the same over {period_text}**: {show(t1, sign)} each.', work)
    win, lose, a, b = (names[0], names[1], t1, t2) if t1 < t2 else (names[1], names[0], t2, t1)
    return reply(f'**{win[:1].upper() + win[1:]} is cheaper over {period_text}**: {show(a, sign)} against {show(b, sign)} for {lose}, a difference of {show(b - a, sign)}.', work)


def tip(text):
    low = text.lower()
    bill = re.search(r'(?i)(' + MONEY + r')', text)
    pct = re.search(r'(\d+(?:\.\d+)?)\s*(?:%|percent|per cent)\s*(?:tip|service|gratuity)|(?:tip|service charge|gratuity) of (\d+(?:\.\d+)?)\s*(?:%|percent)', low)
    if not bill or not pct or len(re.findall(MONEY, text)) != 1 or not re.search(r'\b(?:each|per person|split|shar|divid|total|altogether|how much)\b', low):
        return None
    amount, sign = F(bill[1][1:].replace(',', '').strip()), bill[1][0]
    rate = F(pct[1] or pct[2])
    total = amount * (1 + rate / 100)
    n = people(text)
    if n is None:
        m = re.search(r'(?i)\b(' + N + r')\s+(?:friends|people|colleagues|of us|flatmates|diners|guests)\b', text)
        n = int(val(m[1])) if m and val(m[1]) else None
    first = f'{show(amount, sign)} × {show(rate)}% = {show(amount * rate / 100, sign)} tip; {show(amount, sign)} + {show(amount * rate / 100, sign)} = {show(total, sign)}'
    if n and n > 1 and re.search(r'\b(?:each|per person|split|shar|divid)', low):
        return reply(f'**{show(total / n, sign)} each** ({show(total, sign)} in total with the tip).', f'{first}; {show(total, sign)} ÷ {n} = {show(total / n, sign)}.')
    return reply(f'**{show(total, sign)}** with the tip.', first + '.')


def problem_turn(messages):
    """The index and text of the latest earlier user turn that stated a problem with numbers."""
    users = [(i, m['content']) for i, m in enumerate(messages[:-1]) if m.get('role') == 'user']
    for i, t in reversed(users):
        if len(re.findall(r'\d', t)) >= 2 and '?' in t and i + 1 < len(messages) and re.search(r'\*\*', messages[i + 1].get('content') or ''):
            return i, t
    return None


def solve_text(text):
    for solver in (area, tip):
        got = solver(text)
        if got:
            return got
    try:
        from . import solve_math
        return solve_math.respond([dict(role='user', content=text)])
    except Exception:
        return None


def instead(messages):
    """'What if the room was 6 metres long instead of 5?': the earlier problem with that number changed."""
    last = user_turns(messages)[-1]
    m = re.search(r'(?i)\b(' + N + r')\s*([a-z%$]+)?[^.?]{0,25}?\binstead of\s+(?:\$|£|€)?(' + N + r')\b', last) \
        or re.search(r'(?i)\binstead of\s+(?:\$|£|€)?(' + N + r')[^.?]{0,20}?\b(?:it (?:was|is|were)|i (?:had|have|use|used|need|needed))\s+(?:\$|£|€)?(' + N + r')\b', last)
    if not m:
        return None
    new, old = (m[1], m[3]) if 'instead of' in last[m.start(1):m.end()].lower() and m.lastindex == 3 else (m[2], m[1])
    found = problem_turn(messages)
    if not found or val(new) is None or val(old) is None:
        return None
    text = found[1]
    hits = list(re.finditer(r'(?<![\d.])' + re.escape(old) + r'(?![\d.])', text))
    if len(hits) != 1:
        return None
    changed = text[:hits[0].start()] + new + text[hits[0].end():]
    got = solve_text(changed)
    if not got:
        return None
    return dict(got, response=f'With {new} instead of {old}: ' + got['response'], route='chat/calc')


def more_facts(messages):
    """A new fact and a new question on an earlier problem ("I only have 500 g. How many biscuits can I make?")."""
    last = user_turns(messages)[-1]
    if not re.search(r'\d', last) or '?' not in last:
        return None
    found = problem_turn(messages)
    if not found:
        return None
    told = ' '.join(s for s in re.split(r'(?<=[.!?])\s+', found[1]) if not s.strip().endswith('?'))
    if not told:
        return None
    rate = re.search(r'(?i)\b(\d+(?:\.\d+)?)\s*([a-z]+)\b[^.?]*?\bfor\s+(\d+(?:\.\d+)?)\s+([a-z]+)\b', told)
    have = re.search(r'(?i)\b(?:have|got|had|bought|with|using|use)\s+(?:only\s+|just\s+)?(\d+(?:\.\d+)?)\s*([a-z]+)\b', last)
    want = re.search(r'(?i)\bhow many ([a-z]+)\b', last)
    if rate and have and want and have[2].lower() == rate[2].lower() and want[1].lower().rstrip('s') == rate[4].lower().rstrip('s'):
        per = F(rate[1]) / F(rate[3])
        n = F(have[1]) / per
        whole = math.floor(n)
        note = '' if n.denominator == 1 else f', so {whole} whole ones'
        return reply(f'**{whole} {want[1].lower()}**.', f'{rate[1]} {rate[2]} ÷ {rate[3]} = {show(per)} {rate[2]} for each; {have[1]} {have[2]} ÷ {show(per)} = {show(n)}{note}.')
    got = solve_text(told + ' ' + last)
    if got and re.search(r'\d', got.get('response', '')):
        return dict(got, route='chat/calc')
    return None


def change(messages):
    """'If I pay with a $20 note, how much change do I get?' after a total."""
    last = user_turns(messages)[-1]
    if not re.search(r'(?i)\bchange\b', last) or not re.search(r'(?i)\b(?:pay|paid|give|gave|hand|handed)\b', last):
        return None
    paid = re.findall(MONEY, last)
    got = last_result(messages)
    if len(paid) != 1 or not got or not got[1]:
        return None
    amount = F(paid[0][1:].replace(',', '').strip())
    if amount < got[0]:
        return reply(f'**{show(amount, got[1])} is not enough**: you are {show(got[0] - amount, got[1])} short.',
                     f'{show(got[0], got[1])} − {show(amount, got[1])} = {show(got[0] - amount, got[1])}.')
    return reply(f'**{show(amount - got[0], got[1])}** change.', f'{show(amount, got[1])} − {show(got[0], got[1])} = {show(amount - got[0], got[1])}.')


def scale(messages):
    """'And in four weeks?' after an amount for one week: the same again for that many."""
    turns = user_turns(messages)
    m = re.match(r"(?i)\s*(?:and|so|ok(?:ay)?,?|what about|how about|and what about)?\s*(?:in|for|over|after|across)\s+(" + N + r"|a|an)\s+(hours?|days?|weeks?|months?|years?)\s*\??\s*$",
                 turns[-1])
    got = last_result(messages)
    if not m or not got or len(turns) < 2:
        return None
    n, unit = val(m[1]), m[2].lower().rstrip('s')
    prev = turns[-2].lower()
    if n is None or not re.search(r"\b(?:in|per|a|each|every|for) (?:a |one |1 )?" + unit + r"\b", prev):
        return None
    value, money, unit_word, _ = got
    tail = f' {unit_word}' if unit_word and not money else ''
    return reply(f'**{show(value * n, money)}{tail}** in {show(n)} {unit}{"s" if n != 1 else ""}.',
                 f'{show(value, money)}{tail} per {unit} × {show(n)} = {show(value * n, money)}{tail}.')


def tiered(text):
    """'$3 for the first hour and $1.50 for each hour after that. How much for 5 hours?'"""
    m = re.search(r'(?i)(' + MONEY + r')\s*(?:for|per)?\s*the first (' + N + r')?\s*(hour|day|week|month|km|mile|night|item)s?\b.*?(' + MONEY + r')\s*'
                  r'(?:for |per )?(?:each|every|a|per|an)\s+(?:additional |extra |further |subsequent )?(?:hour|day|week|month|km|mile|night|item)\b', text)
    want = re.search(r'(?i)\bfor (' + N + r')\s*(hour|day|week|month|km|mile|night|item)s?\b(?![^.?]*\bafter\b)', text.split('?')[0].rsplit('.', 1)[-1]) \
        or re.search(r'(?i)(' + N + r')[- ](hour|day|week|month|km|mile|night)s?\b(?=[^.]*\?)', text)
    if not m or not want or want[2].lower() != m[3].lower():
        return None
    first_n = val(m[2]) if m[2] else F(1)
    a, b = F(m[1][1:].replace(',', '').strip()), F(m[4][1:].replace(',', '').strip())
    n = val(want[1])
    if n is None or first_n is None:
        return None
    sign = m[1][0]
    unit = m[3].lower()
    if n <= first_n:
        return reply(f'**{show(a, sign)}**.', f'{show(n)} {unit}{"s" if n != 1 else ""} is within the first {show(first_n)}, so just {show(a, sign)}.')
    rest = n - first_n
    total = a + b * rest
    return reply(f'**{show(total, sign)}**.', f'first {show(first_n)} {unit}: {show(a, sign)}; the other {show(rest)} {unit}s: {show(rest)} × {show(b, sign)} = '
                                               f'{show(b * rest, sign)}; {show(a, sign)} + {show(b * rest, sign)} = {show(total, sign)}.')


CLOCK = re.compile(r'(?i)\b(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)')


def before_start(messages):
    """'If I need to be at the airport 2 hours before departure, when should I get there?' after a departure time."""
    turns = user_turns(messages)
    last = turns[-1]
    m = re.search(r'(?i)\b(' + N + r'|an?|half an?)\s*(?:and a half\s*)?(hours?|minutes?|mins?)\b(?:\s*and\s*(' + N + r')\s*minutes?)?\s*(?:before|ahead of|prior to)\s+'
                  r'(?:the |my |our )?(departure|it (?:leaves|departs|starts|takes off)|take-?off|the flight|kick-?off|it begins|the start|boarding|the train)', last)
    if not m:
        return None
    clock = None
    for t in reversed(turns[:-1] + [last]):
        c = CLOCK.search(re.sub(r'(?i)\b\d+\s*(?:hours?|minutes?)\b', '', t))
        if c and re.search(r'(?i)\b(?:depart|leav|start|take[s]? off|flight|train|kick|begin)', t):
            clock = c
            break
    if not clock:
        return None
    if m[1].lower().startswith('half'):
        amount = F(30) if m[2].lower().startswith('h') else F(0)
    else:
        n = val(m[1]) if m[1].lower() not in ('a', 'an') else F(1)
        amount = n * (60 if m[2].lower().startswith('h') else 1)
        if re.search(r'(?i)and a half', last[m.start():m.end()]) and m[2].lower().startswith('h'):
            amount += 30
        if m[3]:
            amount += val(m[3])
    h, mi = int(clock[1]), int(clock[2] or 0)
    pm = clock[3].lower().startswith('p')
    start = (h % 12 + (12 if pm else 0)) * 60 + mi
    t = (start - int(amount)) % (24 * 60)
    hh, mm = divmod(t, 60)
    shown = f'{(hh % 12) or 12}:{mm:02d} {"am" if hh < 12 else "pm"}'
    start_shown = f'{h}:{mi:02d} {clock[3].lower().replace(".", "")}'
    return reply(f'**{shown}** at the latest.', f'{start_shown} − {hours_text(amount / 60)} = {shown}.')


IN_MONTHS = dict(day=F(12, 365), week=F(12, 52), month=F(1), year=F(12))


def convert(messages):
    """'And roughly how many years is that?' after **80 months**."""
    last = user_turns(messages)[-1]
    m = re.search(r'(?i)\bhow many (days|weeks|months|years|hours|minutes)\b.*\b(?:is that|that is|would that be|does that make)\b|\bin (days|weeks|months|years)\b\s*\??\s*$', last)
    got = last_result(messages)
    if not m or not got or not got[2]:
        return None
    to = (m[1] or m[2]).lower().rstrip('s')
    frm = got[2].lower().rstrip('s')
    value = got[0]
    if frm in IN_MONTHS and to in IN_MONTHS:
        out = value * IN_MONTHS[frm] / IN_MONTHS[to]
    elif frm in ('hour', 'minute') and to in ('hour', 'minute'):
        out = value * (60 if frm == 'hour' else 1) / (60 if to == 'hour' else 1)
    else:
        return None
    whole = math.floor(out)
    extra = ''
    if frm == 'month' and to == 'year' and out.denominator != 1:
        extra = f" ({whole} year{'s' if whole != 1 else ''} and {int(value - whole * 12)} months)"
    return reply(f"About **{show(round(float(out), 1)) if out.denominator != 1 else show(out)} {to}s**{extra}.",
                 f"{show(value)} {frm}s ÷ {show(IN_MONTHS[to] / IN_MONTHS[frm]) if frm in IN_MONTHS else 60} = {show(round(float(out), 2))} {to}s.")


def time_zone(messages):
    """'If the place I'm landing is 9 hours ahead, what's the local time when I land?' after a clock-time result."""
    last = user_turns(messages)[-1]
    m = re.search(r'(?i)\b(' + N + r')\s*(?:and a half\s*)?hours?\s+(ahead|behind|later|earlier)\b', last)
    if not m or not re.search(r'(?i)\blocal time|\bwhat time\b|\btime there\b', last):
        return None
    prev = next((x.get('content') or '' for x in reversed(messages[:-1]) if x.get('role') == 'assistant'), '')
    c = re.search(r'\*\*(\d{1,2}):(\d{2})\s*(am|pm)\*\*', prev)
    if not c or val(m[1]) is None:
        return None
    shift = int(val(m[1]) * 60) + (30 if 'and a half' in last[m.start():m.end()].lower() else 0)
    if m[2].lower() in ('behind', 'earlier'):
        shift = -shift
    h, mi = int(c[1]) % 12 + (12 if c[3] == 'pm' else 0), int(c[2])
    t = h * 60 + mi + shift
    day = '' if 0 <= t < 1440 else (' the next day' if t >= 1440 else ' the day before')
    t %= 1440
    hh, mm = divmod(t, 60)
    shown = f'{(hh % 12) or 12}:{mm:02d} {"am" if hh < 12 else "pm"}'
    sign = '+' if shift >= 0 else '−'
    return reply(f'**{shown}** local time{day}.', f'{c[1]}:{c[2]} {c[3]} {sign} {abs(shift) // 60} hours = {shown}.')


PER_YEAR = dict(day=F(365), week=F(52), month=F(12), year=F(1))
RATE = re.compile(r'(?i)(' + MONEY + r')\s*(?:of [a-z ]{1,20}?\s)?(?:(?:a|an|per|each|every)\s+|/)(day|week|month|year)\b|(' + MONEY + r')\s+(weekly|monthly|daily|yearly)\b')
PCT = re.compile(r'(?i)\b(\d+(?:\.\d+)?)\s*(?:%|percent|per cent)')


def ratio(frm, to):
    """How many `frm` periods in one `to` period, only where the answer is exact or conventional (52 weeks a year)."""
    if frm == to:
        return F(1)
    if {frm, to} == {'week', 'month'}:
        return None
    if frm == 'day' and to == 'week':
        return F(7)
    if frm == 'week' and to == 'day':
        return F(1, 7)
    return PER_YEAR[frm] / PER_YEAR[to]


def a_rate(text):
    """(amount, sign, period, share as a fraction or None, verb) from '$5 a week pocket money and saves 60% of it'."""
    rates = list(RATE.finditer(text))
    if not rates:
        # "Our weekly shop is $80", "the monthly bill comes to $45": the period said before the thing
        pre = list(re.finditer(r'(?i)\b(weekly|monthly|daily|yearly|annual)\s+(?:[a-z]+\s+){1,3}?(?:is|are|costs?|comes? to|of|was|runs? at|totals?)\s+(?:about |around |roughly )?(' + MONEY + r')', text))
        if len(pre) != 1 or len(re.findall(MONEY, text)) != 1:
            return None
        money, period = pre[0][2], ADVERB.get(pre[0][1].lower(), 'year')
    elif len(rates) != 1:
        return None
    else:
        r = rates[0]
        money, period = (r[1], r[2].lower()) if r[1] else (r[3], ADVERB[r[4].lower()])
    amount = F(money[1:].replace(',', '').strip())
    pct = re.search(r'(?i)\b(sav\w*|spend\w*|spent|puts?|putting|keeps?|keeping|gives?|giving|invest\w*|set\w* aside|tak\w+ home|pays?|paying)\b[^.?!]{0,25}?'
                    r'(\d+(?:\.\d+)?)\s*(?:%|percent|per cent)|(\d+(?:\.\d+)?)\s*(?:%|percent|per cent)\s+(?:of (?:it|that|this|them|the money|his|her|their|my)\b[^.?!]{0,15}?)?'
                    r'(?:is |are |goes |go )?(?:sav|spen|put|kept|keep|giv|invest)', text)
    share = F(pct[2] or pct[3]) / 100 if pct else None
    verb = (pct[1] or '').lower() if pct else ''
    cut = re.search(r'(?i)\b(?:cut|cuts|cutting|reduce|reduced|reducing|lower|lowered|lowering|trim|trimmed|trimming|bring (?:it |that )?down|bringing (?:it |that )?down|'
                    r'drop|dropped|dropping|slash|slashed|slashing)\b(?:\s+(?:it|that|this|them|the \w+|our \w+|my \w+))?'
                    r'\s+by\s+(\d+(?:\.\d+)?)\s*(?:%|percent|per cent)', text)
    if share is None and cut:
        share, verb = F(cut[1]) / 100, 'cut'
    return amount, money[0], period, share, verb


def rate_share(text):
    """'My son gets $5 a week and saves 60% of it. How much does he save in a year?'"""
    if len(re.findall(MONEY, text)) != 1 or '?' not in text:
        return None
    got = a_rate(text)
    if not got:
        return None
    amount, sign, period, share, verb = got
    q = text[text.rfind('.', 0, text.rfind('?')) + 1:]
    if not re.search(r'(?i)\bhow much\b', q):
        return None
    if verb == 'cut' and not re.search(r'(?i)\bsav(?:e|ed|ing)\b', q):
        share = 1 - share                   # "cut it by 15%, how much would we spend": 85% of it is left
        verb = 'left'
    h = re.search(r'(?i)\b(?:in|per|a|an|each|every|over|after|for|across)\s+(?:the next\s+|the first\s+)?(' + N + r'|a|an|one)?\s*(day|week|month|year)s?\b', q)
    if not h:
        return None
    n = val(h[1]) if h[1] and h[1].lower() not in ('a', 'an') else F(1)
    to = h[2].lower()
    k = ratio(period, to)
    if k is None or n is None or (share is None and to == period and n == 1):
        return None
    each = amount * share if share is not None else amount
    steps = []
    if share is not None:
        what = ' saved' if verb == 'cut' else ' left after the cut' if verb == 'left' else ''
        steps.append(f'{show(share * 100)}% of {show(amount, sign)} = {show(each, sign)} a {period}{what}')
    times = k * n
    total = each * times
    span = f'{show(n)} {to}s' if n != 1 else f'a {to}'
    if times != 1:
        steps.append(f'{show(each, sign)} × {show(times)} {period}s{" (" + span + ")" if times != n else ""} = {show(total, sign)}')
    return reply(f'**{show(total, sign)}** in {span}.', '; '.join(steps) + '.')


def after_cut(messages):
    """'And how much would we be spending each week then?' after '$140 a week ... cut it by 15%'."""
    turns = user_turns(messages)
    last = turns[-1]
    if re.findall(MONEY, last) or not re.search(r'(?i)\bhow much\b|\bwhat (?:would|will|do|does|should) (?:we|i|it|that) (?:spend|pay|cost|be)', last) or \
            not re.search(r'(?i)\b(?:spend|spending|cost|costing|pay|paying|left|be)\b', last):
        return None
    h = re.search(r'(?i)\b(?:a|per|each|every|in a|over a)\s+(day|week|month|year)\b', last)
    for t in reversed(turns[:-1]):
        got = a_rate(t)
        if got and got[4] == 'cut':
            amount, sign, period, share, _ = got
            to = h[1].lower() if h else period
            k = ratio(period, to)
            if k is None:
                return None
            left = amount * (1 - share) * k
            return reply(f'**{show(left, sign)}** a {to}.', f'{show(amount, sign)} − {show(share * 100)}% ({show(amount * share, sign)}) = {show(amount * (1 - share), sign)} a {period}'
                         + (f'; × {show(k)} = {show(left, sign)} a {to}' if k != 1 else '') + '.')
    return None


def split_part(messages):
    """'If I split the lessons with my sister, how much do I pay in total?' after '$65 ukulele and lessons $18 each, 6 lessons':
    only the part named is shared."""
    turns = user_turns(messages)
    last = turns[-1]
    if not SPLIT.search(last) or re.search(MONEY, last):
        return None
    part = re.search(r'(?i)\b(?:split|share|divide|go halves on)\s+(?:the|our|my)\s+([a-z]+)', last)
    n = people(last)
    if not part or not n or n < 2:
        return None
    word = part[1].lower()
    for t in reversed(turns[:-1]):
        if len(re.findall(MONEY, t)) < 2:
            continue
        unit = re.search(r'(?i)\b' + word.rstrip('s') + r's?\s+(?:are|is|cost|costs|at)\s+(' + MONEY + r')\s*(?:each|apiece|a (?:\w+)|per \w+)?', t) \
            or re.search(r'(?i)(' + MONEY + r')\s*(?:each|a|per)\s+' + word.rstrip('s') + r'\b', t)
        count = re.search(r'(?i)\b(' + N + r')\s+' + word.rstrip('s') + r's?\b', t)
        if not unit:
            return None
        price = F(unit[1][1:].replace(',', '').strip())
        sign = unit[1][0]
        k = val(count[1]) if count else F(1)
        shared = price * k
        total_all = sum(F(m[1:].replace(',', '').strip()) for m in re.findall(MONEY, t)) - price + shared
        mine = total_all - shared + shared / n
        return reply(f'**{show(mine, sign)}** in total.', f'{word}: {show(k)} × {show(price, sign)} = {show(shared, sign)}, your share {show(shared, sign)} ÷ {n} = '
                                                        f'{show(shared / n, sign)}; the rest ({show(total_all - shared, sign)}) is yours alone; '
                                                        f'{show(total_all - shared, sign)} + {show(shared / n, sign)} = {show(mine, sign)}.')
    return None


def save_for(messages):
    """'He wants a game that costs $78. How many weeks will it take him to save for it?' after a saving rate."""
    turns = user_turns(messages)
    last = turns[-1]
    ask = re.search(r'(?i)\bhow (?:many|long)\s*(days|weeks|months|years)?\b', last)
    target = re.findall(MONEY, last)
    if not ask or not re.search(r'(?i)\b(?:save|saving|afford|put by|put aside|reach|pay (?:for|off|back)|buy)\b', last):
        return None
    rate = None
    for t in reversed(turns):
        rate = a_rate(t)
        if rate:
            break
    if not rate:
        return None
    amount, sign, period, share, _ = rate
    per = amount * share if share is not None else amount
    goal = [m for m in target if not RATE.search(last) or m not in RATE.search(last)[0]]
    if len(goal) != 1 or per <= 0:
        return None
    g = F(goal[0][1:].replace(',', '').strip())
    unit = (ask[1] or period + 's').lower().rstrip('s')
    k = ratio(period, unit)
    if k is None:
        return None
    per_unit = per * k
    exact = g / per_unit
    n = math.ceil(exact)
    note = '' if exact.denominator == 1 else f' = {show(exact)}, rounded up to {n}'
    first = f'{show(per, sign)} a {period}' + (f' ({show(share * 100)}% of {show(amount, sign)})' if share is not None else '')
    return reply(f'**{n} {unit}{"s" if n != 1 else ""}**.', f'{first}; {show(g, sign)} ÷ {show(per_unit, sign)} a {unit}{note if note else " = " + str(n)}.')


def discount(messages):
    """'If I get a 10% discount for paying upfront, what's the total?' after a total; also a rise or tax added."""
    last = user_turns(messages)[-1]
    p = PCT.search(last)
    if not p or re.findall(MONEY, last) or not re.search(r"(?i)\b(?:total|cost|pay|price|how much|what(?:'s| is| would| will) (?:it|that|the)|come to|bill)\b", last):
        return None
    down = re.search(r'(?i)\b(?:discount|off|reduc\w*|cheaper|less|sale|lower|cut|knock\w*)\b', last)
    up = re.search(r'(?i)\b(?:tax|vat|increase|rise|raise|more|surcharge|fee|on top|extra|higher|goes up)\b', last)
    if bool(down) == bool(up):
        return None
    got = last_result(messages)
    if not got or not got[1]:
        return None
    base, sign = got[0], got[1]
    if re.search(r'(?i)\b(?:full|original|whole|total|list|normal|usual) (?:price|cost|amount)\b', last):
        # "10% off the full price" after a deposit was worked out: the price the user first gave, not the last result
        first = next((re.findall(MONEY, t)[0] for t in user_turns(messages)[:-1] if re.search(MONEY, t)), None)
        if first:
            base, sign = val(re.sub(r'[^\d.,]', '', first)), first.strip()[0]
    rate = F(p[1]) / 100
    part = base * rate
    total = base - part if down else base + part
    op = '−' if down else '+'
    return reply(f'**{show(total, sign)}**.', f'{show(rate * 100)}% of {show(base, sign)} = {show(part, sign)}; {show(base, sign)} {op} {show(part, sign)} = {show(total, sign)}.')


DOWN = r'(?:discount|off|reduc\w*|cheaper|less|lower|lowered|down|cut|cuts|drop\w*|fall\w*|fell|decreas\w*|sale)'
UP = r'(?:higher|more|up|increase\w*|rise\w*|rose|raise\w*|dearer|extra|on top|surcharge|tax|vat)'


def percent_change(text):
    """One amount and a percentage it goes up or down by, in any wording: 'was $620 and the quote is 12% higher', 'costs $360 a year;
    next year it's going down by 8%', '$45 with 20% off'. The new amount; the change itself when that is what is asked."""
    amounts = re.findall(MONEY, text)
    p = PCT.search(text)
    if len(amounts) != 1 or not p or '?' not in text:
        return None
    after = text[p.end():p.end() + 25]
    before = text[max(0, p.start() - 30):p.start()]
    down = re.search(r'(?i)\b' + DOWN + r'\b', after + ' ' + before)
    up = re.search(r'(?i)\b' + UP + r'\b', after + ' ' + before)
    if bool(down) == bool(up):
        return None
    if re.search(r'(?i)\b(?:of it|of that|of (?:his|her|my|our|their)|saves?|spends?|puts?|keeps?|gives?)\b', before + after) and not re.search(
            r'(?i)\b(?:price|cost|quote|bill|premium|rent|fee|fare|charge)s?\b', text):
        return None                         # a share of an amount ("saves 60% of it") is another sum (rate_share)
    q = text[text.rfind('.', 0, text.rfind('?')) + 1:]
    if not re.search(r"(?i)\bhow much|what(?:'s| is| will| would)\b|\bnew (?:price|cost|total)\b", q):
        return None
    if RATE.search(text) and re.search(r'(?i)\b(?:in|over|per|a|each|every) (?:year|month|week|day)s?\b', q):
        return None                         # "$90 a month ... cut by 20%, how much in a year?" is a rate over time (rate_share)
    base = F(amounts[0][1:].replace(',', '').strip())
    sign = amounts[0][0]
    count_note = ''
    per = re.search(r'(?i)' + re.escape(amounts[0]) + r'\s*(?:a|an|per|each|every|for each)\s+([a-z]+?)s?\b', text)
    if per:
        many = re.search(r'(?i)\b(' + N + r')\s+' + re.escape(per[1]) + r's?\b', text)
        if many and val(many[1]) and val(many[1]) > 1:
            count_note = f'{show(val(many[1]))} × {show(base, sign)} = {show(base * val(many[1]), sign)}; '
            base = base * val(many[1])             # "$120 a night for 5 nights, plus 10% tax": the tax is on the whole stay
    rate = F(p[1]) / 100
    part = base * rate
    new = base - part if down else base + part
    op = '−' if down else '+'
    work = count_note + f'{show(rate * 100)}% of {show(base, sign)} = {show(part, sign)}; {show(base, sign)} {op} {show(part, sign)} = {show(new, sign)}.'
    if re.search(r'(?i)\bhow much (?:more|less|extra|cheaper|would (?:i|we) save|do (?:i|we) save)\b|\bthe difference\b|\bsave\b', q):
        return reply(f'**{show(part, sign)}** {"more" if up else "less"}.', work)
    return reply(f'**{show(new, sign)}**.', work)


def per_period(messages):
    """'And how much is that per month?' after a yearly amount: the same amount split over the months (or weeks)."""
    turns = user_turns(messages)
    last = turns[-1]
    m = re.search(r'(?i)\b(?:per|a|each|every)\s+(month|week|day)\b|\b(monthly|weekly|daily)\b|\bover (12|twelve) months\b|\beach (?:month|payment)\b', last)
    if not m or re.findall(MONEY, last) or len(turns) < 2:
        return None
    to = (m[1] or {'monthly': 'month', 'weekly': 'week', 'daily': 'day'}.get((m[2] or '').lower(), 'month')).lower()
    got = last_result(messages)
    if not got or not got[1]:
        return None
    prev = ' '.join(turns[-3:-1]).lower()
    frm = 'year' if re.search(r'\b(?:a year|per year|each year|yearly|annual|annually|last year|next year|this year|renewal)\b', prev) or not re.search(
        r'\b(?:a|per|each) (?:month|week|day)\b', prev) else None
    if frm is None:
        return None
    k = {'month': 12, 'week': 52, 'day': 365}[to]
    each = got[0] / k
    return reply(f'**{show(each, got[1])}** a {to}.', f'{show(got[0], got[1])} a year ÷ {k} = {show(each, got[1])}.')


def clock_text(t):
    t %= 1440
    hh, mm = divmod(t, 60)
    return f'{(hh % 12) or 12}:{mm:02d} {"am" if hh < 12 else "pm"}'


def each_clock(text):
    """'A chess game starts at 9:40 am and each player has 45 minutes on their clock. What's the latest it can finish?'"""
    c = CLOCK.search(text)
    many = re.search(r'(?i)\beach of (?:the )?(' + N + r'|both)\s+\w+|\b(both|two|' + N + r')\s+(?:players|sides|teams|speakers|halves)\b[^.?!]{0,30}\beach\b|'
                     r'\beach (player|side|team|half|speaker)\b|\bboth (players|sides|teams|speakers)\b', text)
    if not c or not many or not re.search(r'(?i)\b(?:finish|end|over|done|latest|stop|wrap up)\b', text):
        return None
    count = val(many[1] or many[2]) if (many[1] or many[2]) and (many[1] or many[2]).lower() not in ('both',) else F(2)
    rest = text[:c.start()] + text[c.end():]
    d = duration(rest)
    if not d or not count or count < 2:
        return None
    h, mi = int(c[1]), int(c[2] or 0)
    start = (h % 12 + (12 if c[3].lower().startswith('p') else 0)) * 60 + mi
    total = int(d * 60 * count)
    end = start + total
    return reply(f'**{clock_text(end)}** at the latest.',
                 f'{show(count)} × {hours_text(d)} = {hours_text(F(total, 60))} of clock time; {clock_text(start)} + {hours_text(F(total, 60))} = {clock_text(end)}.')


def add_delay(messages):
    """'If there's a 15-minute break in the middle, when is the latest it can finish?' after a clock-time result."""
    last = user_turns(messages)[-1]
    if CLOCK.search(last) or not re.search(r'(?i)\b(?:when|what time|finish|end|arrive|get (?:there|home)|be (?:done|ready)|over|eat|leave|start|then|what if|add|another)\b', last):
        return None
    # any length of time added on after a clock-time answer: a break, a delay, cooling, "another 15 minutes"
    if re.search(r'(?i)\b(?:earlier|less|sooner|shorter|before)\b', last):
        return None
    d = duration(last)
    if not d:
        return None
    minutes = int(d * 60)
    prev = next((x.get('content') or '' for x in reversed(messages[:-1]) if x.get('role') == 'assistant'), '')
    c = re.search(r'\*\*(\d{1,2}):(\d{2})\s*(am|pm)\*\*', prev)
    if not c:
        return None
    t = (int(c[1]) % 12 + (12 if c[3] == 'pm' else 0)) * 60 + int(c[2])
    # extra time before something that has a fixed time ("when should we leave?") moves the start earlier, not later
    earlier = re.search(r'(?i)\bwhen (?:should|do|must|would) (?:we|i|you) (?:leave|set off|go|start|head off|get up|wake)\b|\bleave (?:home|the house)\b', last) \
        or (re.search(r'(?i)\b(?:before|need to be|have to be|must be)\b', ' '.join(user_turns(messages)[-3:-1])) and re.search(r'(?i)\b(?:leave|set off|go)\b', last))
    latest = ' at the latest' if re.search(r'(?i)\blatest\b', last) or earlier else ''
    if earlier:
        return reply(f'**{clock_text(t - minutes)}**{latest}.', f'{c[1]}:{c[2]} {c[3]} − {hours_text(F(minutes, 60))} = {clock_text(t - minutes)}.')
    return reply(f'**{clock_text(t + minutes)}**{latest}.', f'{c[1]}:{c[2]} {c[3]} + {hours_text(F(minutes, 60))} = {clock_text(t + minutes)}.')


LASTS = re.compile(r'(?i)(?:(?:the|a|an|one|another|my)\s+)?((?:[a-z]+\s){0,2}?[a-z]+)\s+(?:costs?|is|for)\s+(' + MONEY + r')[^.?!]{0,40}?\b(?:lasts?|will last|should last|is good for|keeps going)\s+'
                   r'(?:for\s+)?(?:about\s+|around\s+|roughly\s+|up to\s+)?(' + N + r')\s+(years?|months?)')


def lifetimes(text):
    return [(m[1].strip().lower(), F(m[2][1:].replace(',', '').strip()), m[2][0], val(m[3]), m[4].lower().rstrip('s')) for m in LASTS.finditer(text)]


def per_year(messages):
    """'One whetstone costs $35 and lasts about 5 years. An electric sharpener costs $80 and lasts about 8 years. Which is
    cheaper per year?' and 'And if the whetstone only lasts 3 years?'"""
    turns = user_turns(messages)
    last = turns[-1]
    items = lifetimes(last)
    if len(items) != 2:
        follow = re.search(r'(?i)\bif (?:the |my |a )?((?:[a-z]+\s){0,2}?[a-z]+)\s+(?:only\s+|just\s+)?(?:lasts?|lasted|last)\s+(?:for\s+)?(?:about\s+)?(' + N + r')\s+(years?|months?)', last)
        if not follow:
            return None
        for t in reversed(turns[:-1]):
            items = lifetimes(t)
            if len(items) == 2:
                break
        else:
            return None
        name = follow[1].lower()
        hit = [i for i, it in enumerate(items) if it[0] == name] or [i for i, it in enumerate(items) if it[0].split()[-1] == name.split()[-1]]
        if len(hit) != 1 or val(follow[2]) is None:
            return None
        i = hit[0]
        items[i] = items[i][:3] + (val(follow[2]), follow[3].lower().rstrip('s'))
    elif not re.search(r'(?i)\b(?:cheaper|better value|better deal|costs? less|more expensive|per year|a year|each year|per month)\b', last):
        return None
    rows = []
    for name, cost, sign, n, unit in items:
        if not n:
            return None
        years = n if unit == 'year' else n / 12
        rows.append((name, cost / years, cost, n, unit, sign))
    (a, pa, ca, na, ua, sign), (b, pb, cb, nb, ub, _) = rows
    work = (f'the {a}: {show(ca, sign)} ÷ {show(na)} {ua}s = {show(pa, sign)} a year; '
            f'the {b}: {show(cb, sign)} ÷ {show(nb)} {ub}s = {show(pb, sign)} a year.')
    if pa == pb:
        return reply(f'**They cost the same per year**: {show(pa, sign)} each.', work)
    win, lose, x, y = (a, b, pa, pb) if pa < pb else (b, a, pb, pa)
    return reply(f'**The {win} is cheaper per year**: {show(x, sign)} a year against {show(y, sign)} for the {lose}.', work)


DUR = re.compile(r'(?i)\b(?:(' + N + r'|an?)\s*(?:and a half\s*)?hours?(?:\s*(?:and\s*)?(' + N + r')\s*(?:minutes?|mins?))?|(' + N + r')[- ]?(?:minutes?|mins?)|'
                 r'(half an hour)|(an hour and a half))\b')


def durations_all(text):
    """Every length of time in a text, in minutes: '1 hour 45 minutes', '35 minutes', 'half an hour', '2 hours'."""
    out = []
    for m in DUR.finditer(text):
        if m[4]:
            out.append(30)
        elif m[5]:
            out.append(90)
        elif m[1]:
            h = val(m[1]) if m[1].lower() not in ('a', 'an') else F(1)
            extra = 30 if re.search(r'(?i)and a half', m[0]) else 0
            out.append(int(h * 60) + extra + (int(val(m[2])) if m[2] else 0))
        elif m[3] and val(m[3]) is not None:
            out.append(int(val(m[3])))
    return out


def clock_sum(text):
    """'If I start at 10:20 am, it proves for 1 hour 45 minutes and bakes for 35 minutes, when is it ready?': the start time plus
    every length of time told, in whatever order they come ("40 minutes of adverts before it" is still time that passes)."""
    clocks = list(CLOCK.finditer(text))
    if len(clocks) != 1 or not re.search(r'(?i)\b(?:when|what time)\b', text):
        return None
    if re.search(r'(?i)\b(?:need to (?:be|leave|get)|have to (?:be|leave)|must (?:be|leave)|latest (?:i|we) can leave|be there by|arrive by|by \d|'
                 r'before (?:departure|it leaves|the flight|take-?off|kick-?off|boarding))\b', text):
        return None                         # working backwards from a deadline is another sum (before_start)
    c = clocks[0]
    rest = text[:c.start()] + ' ' + text[c.end():]
    mins = durations_all(rest)
    if len(mins) < 2 or sum(mins) <= 0:
        return None
    h, mi = int(c[1]), int(c[2] or 0)
    start = (h % 12 + (12 if c[3].lower().startswith('p') else 0)) * 60 + mi
    end = start + sum(mins)
    parts = ' + '.join(hours_text(F(x, 60)) for x in mins)
    return reply(f'**{clock_text(end)}**.', f'{clock_text(start)} + {parts} = {clock_text(end)}.')


def recipe_scale(messages):
    """'And how many eggs if the recipe uses 2 eggs for 12 pancakes?' after '... for 20 pancakes': the same scaling for the new
    ingredient (2 x 20 / 12)."""
    turns = user_turns(messages)
    last = turns[-1]
    # "uses 2 eggs for 12 pancakes", "uses 250 g of oats for 12 bars", "125 g of butter makes 12 bars"
    m = re.search(r'(?i)\b(?:uses?|needs?|takes?|has|with|calls for|is)?\s*(' + N + r'(?:\.\d+)?)\s*([a-z]+)\s+(?:of\s+([a-z]+(?:\s[a-z]+)?)\s+)?'
                  r'(?:for|to make|per|makes?)\s+(' + N + r')\s+([a-z]+)', last)
    if not m or not re.search(r'(?i)\bhow (?:many|much)\b', last):
        return None
    a, unit, b, item = val(m[1]), m[2].lower(), val(m[4]), m[5].lower().rstrip('s')
    if m[3]:
        unit = f'{unit} of {m[3].lower()}'
    target = None
    rest = last[m.end():]
    tm = re.search(r'(?i)\b(?:for|make|makes|making)\s+(' + N + r')\s+' + re.escape(item) + r's?\b', rest)
    if tm and val(tm[1]) and val(tm[1]) != b:
        target = val(tm[1])
    for t in ([] if target else reversed(turns[:-1])):
        # the count asked for: in the question sentence first ("How many grams of oats for 30 bars?"), any other count of
        # the same item next, never the recipe's own count
        asked = [x for x in re.split(r'(?<=[.!?])\s+', t) if x.strip().endswith('?')]
        for part in asked + [t]:
            for x in re.findall(r'(?i)\b(?:for\s+)?(' + N + r')\s+' + re.escape(item) + r's?\b', part):
                if val(x) and val(x) != b:
                    target = val(x)
                    break
            if target:
                break
        if target:
            break
    if not a or not b or not target:
        return None
    if not m[3]:
        what = re.search(r'(?i)\bhow (?:many|much)\s+(?:grams of |g of |ml of |cups of )?([a-z]+)', last)
        if what and what[1].lower() not in ('more', 'of', 'do', 'does', 'is', 'will', 'would', 'should', 'if', unit) and not what[1].lower().startswith(item):
            unit = f'{unit} of {what[1].lower()}'
    need = a * target / b
    up = math.ceil(need) if need.denominator != 1 and unit in ('egg', 'eggs', 'bananas', 'banana', 'onions', 'onion', 'lemons', 'lemon') else None
    shown = f'{show(need)} {unit}' + (f', so {up} {unit}' if up else '')
    return reply(f'**{shown}** for {show(target)} {item}s.', f'{show(a)} {unit} ÷ {show(b)} × {show(target)} = {show(need)}.')


PCT_OF = r'(\d+(?:\.\d+)?)\s*(?:%|per ?cent)'
KEEP_VERB = r'(?:kept|keeps|keep|withheld|withholds|deducted|deducts|took|takes|charged|charges)'


def percent_of(messages):
    """A share of an amount: 'quoted $8,400 and we paid 75% upfront. How much have we paid?' (75% of $8,400); 'If he refunds
    40% of what we paid, how much do we get back?' (40% of the last result); 'the landlord kept 25%. How much should we get
    back?' (what is left, 75%); 'return 90% of the full deposit' (the amount named earlier)."""
    turns = user_turns(messages)
    last = turns[-1]
    if not re.search(r'(?i)\bhow much\b', last) or re.search(r'(?i)\b(?:off|discount|increase|rise|rises|rose|went up|go up|tip|interest|vat|tax)\b', last):
        return None
    pm = re.search(PCT_OF, last, re.I)
    if not pm:
        return None
    p = F(pm[1]) / 100
    base, money, how = None, None, ''
    after = last[pm.end():]
    if re.match(r'(?i)\s*of (?:what (?:we|i|you|they) (?:paid|spent|put down|gave)|that|it|this)\b', after):
        prev = last_result(messages)
        if prev and prev[1]:
            base, money, how = prev[0], prev[1], 'of what was paid'
    if base is None:
        named = re.match(r'(?i)\s*of (?:the |our |my )?(?:full |whole |original |total )?([a-z]+)', after)
        here = re.findall(MONEY, last)
        if here:
            base = val(re.sub(r'[^\d.,]', '', here[0]))
            money = here[0].strip()[0]
        elif named:
            for t in reversed(turns[:-1]):
                for sent in re.split(r'(?<=[.!?])\s+', t):
                    if re.search(r'(?i)\b' + re.escape(named[1].rstrip('s')), sent) and re.search(MONEY, sent):
                        found = re.findall(MONEY, sent)[0]
                        base, money = val(re.sub(r'[^\d.,]', '', found)), found.strip()[0]
                        break
                if base is not None:
                    break
            if base is None and re.match(r'(?i)\s*of (?:the |our |my )?(?:full|whole|original|total)\b', after):
                # "the full price" after "Our holiday cost $2,000": the first amount of the conversation
                first = next((re.findall(MONEY, t)[0] for t in turns[:-1] if re.search(MONEY, t)), None)
                if first:
                    base, money = val(re.sub(r'[^\d.,]', '', first)), first.strip()[0]
    if not base:
        return None
    left = bool(re.search(r'(?i)\b' + KEEP_VERB + r'\b', last[:pm.start() + 30])) and re.search(r'(?i)\b(?:back|left|get|remain|return)', last)
    if left:
        part = base * (1 - p)
        return reply(f'**{show(part, money)}** back.', f'{show(base, money)} − {pm[1]}% ({show(base * p, money)}) = {show(part, money)}.')
    part = base * p
    return reply(f'**{show(part, money)}**.', f'{pm[1]}% of {show(base, money)} = {show(base, money)} × {show(p)} = {show(part, money)}.')


def respond(messages):
    """A dict reply, or None when the last turn is not one of these sums."""
    if not messages or messages[-1].get('role') != 'user':
        return None
    last = messages[-1]['content']
    for solver in (lambda: per_year(messages), lambda: each_clock(last), lambda: clock_sum(last), lambda: recipe_scale(messages), lambda: add_delay(messages), lambda: after_cut(messages), lambda: percent_change(last), lambda: per_period(messages), lambda: rate_share(last), lambda: split_part(messages), lambda: save_for(messages), lambda: discount(messages), lambda: percent_of(messages), lambda: time_zone(messages),lambda: convert(messages), lambda: before_start(messages), lambda: tiered(last), lambda: area(last), lambda: tip(last), lambda: options(messages), lambda: split(messages), lambda: each_price(messages),
                   lambda: paid_hours(messages), lambda: change(messages), lambda: scale(messages), lambda: instead(messages), lambda: more_facts(messages)):
        try:
            got = solver()
        except Exception:
            got = None
        if got:
            return got
    return None
