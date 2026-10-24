"""Exact everyday quantities: powers, fractions, unit conversions, speed, prices and simple "times as many" problems.

Each solver reads one explicit kind of question and shows its working, or returns None so other engines can try.
All arithmetic uses exact fractions; answers are shown as readable decimals. No neural model, no web lookup.
"""
from fractions import Fraction
import re

DETAILS = 'Exact arithmetic with fractions; the steps are shown. Written rules, no neural model.'

WORD_NUMBERS = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
                'ten': 10, 'eleven': 11, 'twelve': 12, 'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'hundred': 100,
                'a dozen': 12, 'dozen': 12, 'half a': Fraction(1, 2), 'a': 1, 'an': 1}
NUM = r'(-?\d[\d,]*(?:\.\d+)?|' + '|'.join(sorted((w for w in WORD_NUMBERS if w not in ('a', 'an')), key=len, reverse=True)) + r')'
MONEY = r'(?:[$€£]\s*)?(\d[\d,]*(?:\.\d+)?)(?:\s*(?:dollars?|euros?|pounds?|usd|eur|gbp))?'


def number(text):
    text = text.strip().lower().replace(',', '')
    if text in WORD_NUMBERS:
        return Fraction(WORD_NUMBERS[text])
    try:
        return Fraction(text)
    except (ValueError, ZeroDivisionError):
        return None


def show(value, places=6):
    """Exact value as a readable number: 150, 0.875, 6.213712 (rounded only when it does not terminate)."""
    value = Fraction(value)
    if value.denominator == 1:
        return f'{value.numerator:,}' if abs(value.numerator) >= 10000 else str(value.numerator)
    text = f'{float(value):.{places}f}'.rstrip('0').rstrip('.')
    return text


def money(value):
    value = Fraction(value)
    return f'${float(value):,.2f}'


def out(response, route, steps=None):
    text = response + ('\n\nSteps:\n' + '\n'.join(f'{i}. {s}' for i, s in enumerate(steps, 1)) if steps else '')
    return dict(response=text, route='helper/quantity-' + route, sources=[], details=DETAILS)


def clean(text):
    return re.sub(r'\s+', ' ', text.strip().rstrip('?.!').strip()).lower()


# ---------------------------------------------------------------- powers and fractions

def powers(q):
    m = re.fullmatch(r'(?:what is |what\'s |calculate |compute |work out )?' + NUM + r' (?:to the power of|raised to(?: the power of)?|to the) ' + NUM + r'(?:th|st|nd|rd)?(?: power)?', q)
    if m:
        base, exp = number(m[1]), number(m[2])
        if base is None or exp is None or exp.denominator != 1 or abs(exp) > 64:
            return None
        value = base ** int(exp)
        return out(f'{show(base)} to the power of {show(exp)} = **{show(value)}**', 'power',
                   [f'Multiply {show(base)} by itself {show(exp)} times: {" × ".join([show(base)] * int(exp)) if 0 < exp <= 6 else f"{show(base)}^{show(exp)}"} = {show(value)}.'])
    m = re.fullmatch(r'(?:what is |what\'s |calculate )?' + NUM + r' (squared|cubed)', q)
    if m:
        base = number(m[1])
        if base is None:
            return None
        exp = 2 if m[2] == 'squared' else 3
        value = base ** exp
        return out(f'{show(base)} {m[2]} = **{show(value)}**', 'power', [f'{" × ".join([show(base)] * exp)} = {show(value)}.'])
    return None


def fractions(q):
    m = re.fullmatch(r'(?:what is |what\'s |convert |write |express )?(-?\d+)\s*/\s*(\d+) (?:as|to|into|in) (?:a |an )?(decimal|percent(?:age)?|%)', q)
    if m and int(m[2]) != 0:
        value = Fraction(int(m[1]), int(m[2]))
        if m[3] == 'decimal':
            return out(f'{m[1]}/{m[2]} = **{show(value)}**', 'fraction', [f'Divide {m[1]} by {m[2]}: {m[1]} ÷ {m[2]} = {show(value)}.'])
        return out(f'{m[1]}/{m[2]} = **{show(value * 100)}%**', 'fraction',
                   [f'{m[1]} ÷ {m[2]} = {show(value)}.', f'× 100 = {show(value * 100)}%.'])
    m = re.fullmatch(r'(?:what is |what\'s |convert |write |express )?(-?\d*\.\d+) (?:as|to|into) (?:a )?fraction', q)
    if m:
        value = Fraction(m[1])
        return out(f'{m[1]} = **{value.numerator}/{value.denominator}**', 'fraction',
                   [f'{m[1]} = {Fraction(m[1]).limit_denominator(10 ** 6)} in lowest terms.'])
    m = re.fullmatch(r'(?:what is |what\'s |convert |write |express )?(-?\d+(?:\.\d+)?)\s*% (?:as|to|into) (?:a )?(decimal|fraction)', q)
    if m:
        value = Fraction(m[1]) / 100
        if m[2] == 'decimal':
            return out(f'{m[1]}% = **{show(value)}**', 'fraction', [f'{m[1]} ÷ 100 = {show(value)}.'])
        return out(f'{m[1]}% = **{value.numerator}/{value.denominator}**', 'fraction', [f'{m[1]}/100 in lowest terms = {value}.'])
    return None


# ---------------------------------------------------------------- units

UNITS = {   # unit -> (dimension, size in the base unit)
    'second': ('time', 1), 'sec': ('time', 1), 's': ('time', 1), 'minute': ('time', 60), 'min': ('time', 60),
    'hour': ('time', 3600), 'hr': ('time', 3600), 'h': ('time', 3600), 'day': ('time', 86400), 'week': ('time', 604800),
    'year': ('time', 31557600),
    'millimetre': ('length', Fraction(1, 1000)), 'millimeter': ('length', Fraction(1, 1000)), 'mm': ('length', Fraction(1, 1000)),
    'centimetre': ('length', Fraction(1, 100)), 'centimeter': ('length', Fraction(1, 100)), 'cm': ('length', Fraction(1, 100)),
    'metre': ('length', 1), 'meter': ('length', 1), 'm': ('length', 1),
    'kilometre': ('length', 1000), 'kilometer': ('length', 1000), 'km': ('length', 1000),
    'inch': ('length', Fraction(254, 10000)), 'in': ('length', Fraction(254, 10000)),
    'foot': ('length', Fraction(3048, 10000)), 'feet': ('length', Fraction(3048, 10000)), 'ft': ('length', Fraction(3048, 10000)),
    'yard': ('length', Fraction(9144, 10000)), 'yd': ('length', Fraction(9144, 10000)),
    'mile': ('length', Fraction(1609344, 1000)), 'mi': ('length', Fraction(1609344, 1000)),
    'milligram': ('mass', Fraction(1, 1000)), 'mg': ('mass', Fraction(1, 1000)), 'gram': ('mass', 1), 'g': ('mass', 1),
    'kilogram': ('mass', 1000), 'kilo': ('mass', 1000), 'kg': ('mass', 1000), 'tonne': ('mass', 1000000),
    'ounce': ('mass', Fraction(28349523125, 1000000000)), 'oz': ('mass', Fraction(28349523125, 1000000000)),
    'pound': ('mass', Fraction(45359237, 100000)), 'lb': ('mass', Fraction(45359237, 100000)), 'lbs': ('mass', Fraction(45359237, 100000)),
    'stone': ('mass', Fraction(635029318, 100000)),
    'millilitre': ('volume', Fraction(1, 1000)), 'milliliter': ('volume', Fraction(1, 1000)), 'ml': ('volume', Fraction(1, 1000)),
    'litre': ('volume', 1), 'liter': ('volume', 1), 'l': ('volume', 1),
    'cup': ('volume', Fraction(2365882365, 10000000000)), 'pint': ('volume', Fraction(473176473, 1000000000)),
    'gallon': ('volume', Fraction(3785411784, 1000000000)), 'teaspoon': ('volume', Fraction(492892159375, 100000000000000)),
    'tablespoon': ('volume', Fraction(1478676478125, 100000000000000)),
}
TEMPERATURE = {'celsius': 'C', 'c': 'C', 'centigrade': 'C', 'fahrenheit': 'F', 'f': 'F', 'kelvin': 'K', 'k': 'K'}


def unit(word):
    word = word.lower().strip('. ')
    word = re.sub(r'^degrees?\s+', '', word)
    if word in UNITS:
        return word
    for ending in ('es', 's'):
        if word.endswith(ending) and word[:-len(ending)] in UNITS:
            return word[:-len(ending)]
    return {'metres': 'metre', 'meters': 'meter', 'kilos': 'kilo', 'inches': 'inch'}.get(word)


def plural(word, value):
    if value == 1:
        return word
    return {'inch': 'inches', 'foot': 'feet', 'h': 'h', 'km': 'km', 'cm': 'cm', 'mm': 'mm', 'm': 'm', 'kg': 'kg', 'g': 'g',
            'mg': 'mg', 'ml': 'ml', 'l': 'l', 'lb': 'lb', 'lbs': 'lb', 'oz': 'oz', 'ft': 'ft', 'mi': 'mi', 'yd': 'yd',
            'stone': 'stone'}.get(word, word + 's')


def temperature(value, source, target):
    if source == target:
        return value
    celsius = value if source == 'C' else (value - 32) * Fraction(5, 9) if source == 'F' else value - Fraction(27315, 100)
    return celsius if target == 'C' else celsius * Fraction(9, 5) + 32 if target == 'F' else celsius + Fraction(27315, 100)


UNIT_WORD = r'((?:degrees? )?[a-z]+)'


def conversions(q):
    patterns = [r'(?:convert |change |turn )?' + NUM + r' ?' + UNIT_WORD + r' (?:to|into|in) ' + UNIT_WORD,
                r'(?:what is |what\'s |how much is |how many )' + NUM + r' ?' + UNIT_WORD + r' (?:in|to|into|as) ' + UNIT_WORD,
                r'how many ' + UNIT_WORD + r' (?:are there |are |is |make up |make |go )?(?:in|into) (?:a |an )?' + NUM + r'? ?' + UNIT_WORD,
                r'how many ' + UNIT_WORD + r' (?:is|are|does|do) ' + NUM + r' ?' + UNIT_WORD + r'(?: weigh| make| equal)?']
    for index, pattern in enumerate(patterns):
        m = re.fullmatch(pattern, q)
        if not m:
            continue
        if index < 2:
            amount, source, target = m[1], m[2], m[3]
        elif index == 2:
            target, amount, source = m[1], m[2] or '1', m[3]
        else:
            target, amount, source = m[1], m[2], m[3]
        value = number(amount)
        if value is None:
            continue
        s_temp, t_temp = TEMPERATURE.get(re.sub(r'^degrees? ', '', source)), TEMPERATURE.get(re.sub(r'^degrees? ', '', target))
        if s_temp and t_temp:
            result = temperature(value, s_temp, t_temp)
            names = {'C': '°C', 'F': '°F', 'K': 'K'}
            formula = {('C', 'F'): f'× 9/5 + 32', ('F', 'C'): f'− 32, then × 5/9', ('C', 'K'): '+ 273.15', ('K', 'C'): '− 273.15'}
            return out(f'{show(value)}{names[s_temp]} = **{show(result, 2)}{names[t_temp]}**', 'temperature',
                       [f'{show(value)} {formula.get((s_temp, t_temp), "via Celsius")} = {show(result, 2)}.'])
        su, tu = unit(source), unit(target)
        if not su or not tu or UNITS[su][0] != UNITS[tu][0]:
            continue
        result = value * Fraction(UNITS[su][1]) / Fraction(UNITS[tu][1])
        factor = Fraction(UNITS[su][1]) / Fraction(UNITS[tu][1])
        return out(f'{show(value)} {plural(su, value)} = **{show(result, 4)} {plural(tu, result)}**', 'conversion',
                   [f'1 {su} = {show(factor, 6)} {plural(tu, factor)}.', f'{show(value)} × {show(factor, 6)} = {show(result, 4)}.'])
    return None


# ---------------------------------------------------------------- speed, prices and comparisons

DIST = r'(\d+(?:\.\d+)?) ?(km|kilometres?|kilometers?|miles?|mi|m|metres?|meters?)'
TIME = r'(\d+(?:\.\d+)?) ?(hours?|hrs?|h|minutes?|mins?|seconds?|secs?|s)'


def speed(q):
    m = re.search(r'\b(?:travels?|travelled|traveled|drives?|drove|rides?|rode|runs?|ran|walks?|walked|cycles?|cycled|flies|flew|goes|went|covers?|covered|swims?|swam) ' + DIST + r' in ' + TIME, q)
    if m and re.search(r'\b(?:speed|how fast|average)\b', q):
        d, du, t, tu = Fraction(m[1]), m[2], Fraction(m[3]), m[4]
        hours = t * Fraction(UNITS[unit(tu)][1]) / 3600
        if hours == 0:
            return None
        per = 'km/h' if unit(du) in ('km', 'kilometre', 'kilometer') else 'mph' if unit(du) in ('mile', 'mi') else 'm/h'
        value = d / hours
        steps = [] if unit(tu) in ('hour', 'hr', 'h') else [f'Time = {show(t)} {tu} = {show(hours, 4)} hours.']
        return out(f'The average speed is **{show(value, 2)} {per}**.', 'speed',
                   steps + [f'Speed = distance ÷ time = {show(d)} ÷ {show(hours, 4)} h = {show(value, 2)} {per}.'])
    m = re.search(r'\bat (\d+(?:\.\d+)?) ?(km/h|kph|kilometres per hour|kilometers per hour|mph|miles per hour) for ' + TIME, q)
    if m and re.search(r'\b(?:how far|distance|how many (?:km|kilometres|kilometers|miles))\b', q):
        v, vu, t, tu = Fraction(m[1]), m[2], Fraction(m[3]), m[4]
        hours = t * Fraction(UNITS[unit(tu)][1]) / 3600
        d = v * hours
        name = 'km' if 'k' in vu else 'miles'
        return out(f'It goes **{show(d, 2)} {name}**.', 'speed', [f'Distance = speed × time = {show(v)} × {show(hours, 4)} h = {show(d, 2)} {name}.'])
    return None


FACTORS = {'twice': 2, 'double': 2, 'half': Fraction(1, 2), 'a third of': Fraction(1, 3), 'a quarter of': Fraction(1, 4), 'triple': 3, 'thrice': 3}


def times_as_many(q):
    m = re.search(r'\b([a-z]+) (?:has|have|had|owns?|collected|scored|got|earns?|earned) (twice|half|triple|thrice|(\d+(?:\.\d+)?|' + '|'.join(w for w in WORD_NUMBERS if len(w) > 2) + r') times) as (many|much) ([a-z]+ )?as ([a-z]+)\b', q)
    if not m:
        return None
    a, b = m[1], m[6]
    factor = FACTORS.get(m[2]) if m[3] is None else number(m[3])
    given = re.search(r'\b' + b + r' (?:has|have|had|owns?|collected|scored|got|earns?|earned) ' + NUM + r'\b', q)
    if factor is None or not given or not re.search(r'\bhow (?:many|much)\b', q):
        return None
    base = number(given[1])
    if base is None:
        return None
    value = factor * base
    things = (m[5] or '').strip()
    return out(f'{a.capitalize()} has **{show(value)}**{" " + things if things else ""}.', 'times',
               [f'{b.capitalize()} has {show(base)}.', f'{a.capitalize()} has {m[2]} as {m[4]}: {show(factor)} × {show(base)} = {show(value)}.'])


def shopping(q):
    items = re.search(r'\b(?:buy|bought|purchase|purchased|get|got|order|ordered)s? ' + NUM + r' ([a-z]+(?: [a-z]+)?) (?:at|for|costing) ' + MONEY + r' each', q)
    if not items:
        return None
    count, what, price = number(items[1]), items[2], Fraction(items[3].replace(',', ''))
    if count is None:
        return None
    total = count * price
    steps = [f'{show(count)} × {money(price)} = {money(total)}.']
    paid = re.search(r'\b(?:pay|paid|hand over|give|gave) (?:with |using )?(?:a |an )?' + MONEY + r'(?: note| bill| banknote)?', q)
    if paid and re.search(r'\bchange\b', q):
        cash = Fraction(paid[1].replace(',', ''))
        if cash < total:
            return out(f'{money(cash)} is not enough: the {what} cost {money(total)}.', 'shopping', steps)
        steps.append(f'{money(cash)} − {money(total)} = {money(cash - total)}.')
        return out(f'You get **{money(cash - total)}** in change.', 'shopping', steps)
    if re.search(r'\b(?:how much|total|cost|pay|spend)\b', q):
        return out(f'You pay **{money(total)}** in total.', 'shopping', steps)
    return None


def percent_off(q):
    m = re.fullmatch(r'(?:what is |what\'s |calculate )?(\d+(?:\.\d+)?)\s*(?:%|percent) off (?:of )?' + MONEY, q)
    if not m:
        m2 = re.search(r'(?:costs?|priced at|is) ' + MONEY + r'.*?\b(\d+(?:\.\d+)?)\s*(?:%|percent) (?:off|discount)', q)
        if not m2 or not re.search(r'\b(?:sale price|new price|price now|how much|final price|cost now|pay)\b', q):
            return None
        price, pct = Fraction(m2[1].replace(',', '')), Fraction(m2[2])
    else:
        pct, price = Fraction(m[1]), Fraction(m[2].replace(',', ''))
    cut = price * pct / 100
    final = price - cut
    is_money = '$' in q or '€' in q or '£' in q
    fmt = money if is_money else show
    return out(f'The sale price is **{fmt(final)}**.', 'discount',
               [f'{show(pct)}% of {fmt(price)} = {fmt(cut)}.', f'{fmt(price)} − {fmt(cut)} = {fmt(final)}.'])


SOLVERS = (powers, fractions, conversions, speed, times_as_many, shopping, percent_off)


def reply(text):
    if len(text) > 600 or '```' in text:
        return None
    q = clean(text)
    q = re.sub(r'^(?:please |can you |could you |tell me |so )+', '', q)
    for solver in SOLVERS:
        try:
            answer = solver(q)
        except (ValueError, ZeroDivisionError, KeyError, OverflowError):
            answer = None
        if answer:
            return answer
    return None
