"""Exact arithmetic for short grade-school word problems (authored rules, no learning, no network).

"Sam had 43 rubber bands. A friend gave Sam 19 more. Afterward, Sam had" -> 62.

Several small solvers each recognise one kind of problem (running totals with
add/subtract cues, comparisons, equal groups and sharing, area and perimeter, unit
conversion, money, clock time, number patterns, fractions of an amount, data
totals, differences). Each returns an exact answer or None. `match` only commits
when the solvers that answered agree and exactly one option states that answer,
so unfamiliar wording falls back to other evidence instead of a guess.
"""
from fractions import Fraction
import re

WORD_NUMBERS = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
                'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16,
                'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50,
                'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90, 'dozen': 12}
MULTIPLIERS = {'twice': 2, 'double': 2, 'triple': 3, 'half': Fraction(1, 2)}
NUM = r'(?:\d+(?:,\d{3})*(?:\.\d+)?|' + '|'.join(sorted(WORD_NUMBERS, key=len, reverse=True)) + r')'
NUMBER = re.compile(r'(?<![\w.:/$])(' + NUM + r')(?![\w:/])', re.I)

ADD_WORDS = ('more', 'another', 'found', 'finds', 'bought', 'buys', 'got', 'gets', 'received', 'receives', 'added', 'adds',
             'picked', 'picks', 'collected', 'collects', 'caught', 'won', 'earned', 'joined', 'arrived', 'came', 'grew',
             'plus', 'extra', 'baked', 'made', 'planted', 'brought', 'gained', 'saved', 'gave', 'gives', 'boarded')
SUB_WORDS = ('lost', 'loses', 'ate', 'eats', 'spent', 'spends', 'sold', 'sells', 'used', 'uses', 'broke', 'breaks', 'popped',
             'took', 'takes', 'left', 'away', 'melted', 'minus', 'removed', 'removes', 'dropped', 'donated', 'threw',
             'mailed', 'sent', 'returned', 'paid', 'lent', 'burst', 'flew', 'ran', 'fell', 'missed', 'cut', 'cuts', 'drank', 'trimmed', 'trims',
             'shared', 'handed', 'passed', 'traded')
# "gave X to someone" subtracts from the giver; "someone gave the subject X" adds. Resolved in nearest_cue.

UNITS = {  # conversion factors to a base unit per dimension
    'length': {'millimeters': Fraction(1, 10), 'millimeter': Fraction(1, 10), 'mm': Fraction(1, 10),
               'centimeters': 1, 'centimeter': 1, 'cm': 1, 'meters': 100, 'meter': 100, 'm': 100,
               'kilometers': 100000, 'kilometer': 100000, 'km': 100000},
    'imperial': {'inches': 1, 'inch': 1, 'feet': 12, 'foot': 12, 'yards': 36, 'yard': 36},
    'mass': {'grams': 1, 'gram': 1, 'g': 1, 'kilograms': 1000, 'kilogram': 1000, 'kg': 1000},
    'volume': {'milliliters': 1, 'milliliter': 1, 'ml': 1, 'liters': 1000, 'liter': 1000, 'l': 1000},
    'time': {'seconds': 1, 'second': 1, 'minutes': 60, 'minute': 60, 'hours': 3600, 'hour': 3600, 'days': 86400,
             'day': 86400, 'weeks': 604800, 'week': 604800},
    'weight': {'ounces': 1, 'ounce': 1, 'pounds': 16, 'pound': 16},
}
COINS = {'pennies': 1, 'penny': 1, 'nickels': 5, 'nickel': 5, 'dimes': 10, 'dime': 10, 'quarters': 25, 'quarter': 25}


def value(token):
    token = token.lower().replace(',', '')
    return Fraction(WORD_NUMBERS[token]) if token in WORD_NUMBERS else Fraction(token)


def numbers(text):
    found = []
    for m in NUMBER.finditer(text):
        token = m.group(1).lower()
        if token in WORD_NUMBERS and re.search(r'\b(?:the|these|those|both|all|first|last)\s+$', text[max(0, m.start() - 12):m.start()].lower()):
            continue          # "over the two days" names something already counted, not a new quantity
        found.append((m.start(), m.end(), value(m.group(1))))
    return found


def normalise_phrases(text):
    """Phrasal verbs as single cue words: 'got off' removes, 'got on' adds, 'saws off' removes."""
    text = re.sub(r'\b(?:got|get|gets|stepped|climbed|hopped|jumped)\s+(?:off|out)\b', 'left', text)
    text = re.sub(r'\b(?:got|get|gets|stepped|climbed|hopped|jumped)\s+(?:on|in)\b', 'boarded', text)
    text = re.sub(r'\b[a-z]+s?\s+(?:off|away)\b', 'removed', text)
    return text


def cents(text):
    """Money amounts in cents, in order: $3.50 -> 350, 75 cents -> 75."""
    out = []
    for m in re.finditer(r'\$\s?(\d+(?:\.\d{1,2})?)|(\d+)\s*(?:cents?\b|¢)', text, re.I):
        out.append((m.start(), Fraction(m.group(1)) * 100 if m.group(1) else Fraction(m.group(2))))
    return out


# ---------------------------------------------------------------- answers in options

def read_answer(ending):
    """The value an option states: ('time', minutes), ('money', cents), ('fraction', F) or ('number', F)."""
    text = ending.strip()
    clock = re.match(r'(\d{1,2}):(\d{2})\s*([ap]\.?m\.?)?', text, re.I)
    if clock:
        hours, minutes = int(clock.group(1)), int(clock.group(2))
        return ('time', (hours % 12) * 60 + minutes)
    money = re.match(r'\$\s?(\d+(?:\.\d{1,2})?)', text)
    if money:
        return ('money', Fraction(money.group(1)) * 100)
    fraction = re.match(r'(\d+)\s*/\s*(\d+)(?!\d)', text)
    if fraction and int(fraction.group(2)):
        return ('fraction', Fraction(int(fraction.group(1)), int(fraction.group(2))))
    found = NUMBER.search(text)
    if found and found.start() <= 12:
        amount = value(found.group(1))
        if re.match(r'\s*(?:cents?\b|¢)', text[found.end():], re.I):   # whole word: not 'centimeters'
            return ('money', amount)
        return ('number', amount)
    return None


def same(answer, stated):
    if answer is None or stated is None:
        return False
    kind, amount = answer
    stated_kind, stated_amount = stated
    if kind == 'number' and stated_kind in ('number', 'fraction'):
        return Fraction(amount) == stated_amount
    if kind == 'money' and stated_kind in ('money', 'number'):
        # "$3.50" options compare in cents; a bare number option means cents only if it says cents.
        return Fraction(amount) == stated_amount if stated_kind == 'money' else False
    if kind == 'fraction' and stated_kind == 'fraction':
        return Fraction(amount) == stated_amount
    if kind == 'time' and stated_kind == 'time':
        return amount % 720 == stated_amount % 720
    return False


# ---------------------------------------------------------------- solvers

def nearest_cue(text, start, end):
    """'add' or 'sub' from the cue word closest to a quantity (looking mostly back, a little ahead)."""
    best = None
    for m in re.finditer(r'[a-z]+', text):
        word = m.group(0)
        kind = 'add' if word in ADD_WORDS else 'sub' if word in SUB_WORDS else None
        if kind is None:
            continue
        if word in ('gave', 'gives'):
            # "A friend gave Sam 19" adds to Sam; "Sam gave 5 to a friend" / "gave away" subtracts.
            tail = text[m.end():m.end() + 40]
            kind = 'sub' if re.match(r'\s+(?:away|\d+|\w+\s+\d+\s+\w+\s+to\b|\d+\s+\w+\s+to\b)', tail) and re.search(r'\bto\b|\baway\b', tail) else 'add'
        if m.end() <= start:
            distance = start - m.end()
        elif m.start() >= end:
            distance = (m.start() - end) * 2          # cues after a number ("19 more") count, at a small penalty
        else:
            continue
        if distance <= 45 and (best is None or distance < best[0]):
            best = (distance, kind)
    return best[1] if best else None


def running_total(text):
    text = normalise_phrases(text)
    found = numbers(text)
    if len(found) < 2:
        return None
    total = found[0][2]
    for (start, end, amount) in found[1:]:
        after = text[end:end + 30]
        compare = re.match(r'\s+(?:\w+\s+){0,2}?(fewer|less|more|shorter|longer|taller|older|younger|heavier|lighter)\s+(?:\w+\s+){0,3}?than\b', after)
        times = re.match(r'\s+times\s+(?:as\s+)?(?:many|much|long|tall)', after)
        if compare:
            word = compare.group(1)
            total = total - amount if word in ('fewer', 'less', 'shorter', 'younger', 'lighter') else total + amount
            continue
        if times:
            total = total * amount
            continue
        cue = nearest_cue(text, start, end)
        if cue is None:
            if re.search(r'\b(?:together|altogether|in all|combined|in total|total|both)\b', text):
                cue = 'add'          # "A has 5. B has 3. Together they have" sums the quantities
            else:
                return None
        total = total + amount if cue == 'add' else total - amount
    return ('number', total) if total >= 0 else None


def equal_groups(text):
    found = numbers(text)
    if len(found) != 2:
        return None
    x, y = found[0][2], found[1][2]
    if (re.search(r'\b(?:shared|split|divided|divides|shares|splits|share|split)\b', text) and re.search(r'\b(?:equally|evenly|among|between|into)\b', text)) \
            or re.search(r'\b(?:equally|evenly)\s+(?:into|among|between)\b', text):
        return ('number', x / y) if y else None
    if re.search(r'\b(?:into|in)\s+(?:bags|boxes|groups|rows|packs|teams|piles|stacks|jars|baskets)\s+of\s+' + NUM, text) or \
            re.search(r'\beach\s+(?:bag|box|group|row|pack|team|pile|stack|jar|basket)\s+(?:holds|has|gets|can hold)\b', text) and re.search(r'\bhow many\b|\bneeded\b|\bmade\b|\bfilled\b', text):
        return ('number', x / y) if y else None
    if re.search(r'\b(?:in|into|on|to)\s+each\s+of\b', text) or re.search(r'\bwith\s+' + NUM + r'\s+(?:\w+\s+){0,2}each\b', text) \
            or re.search(r'\b(?:each|every)\s+(?:of\s+)?(?:the\s+)?' + NUM + r'\b', text) or re.search(r'\b(?:rows|groups|bags|boxes|packs|stacks|teams)\s+of\s+' + NUM, text) \
            or re.search(r'\b' + NUM + r'\s+(?:\w+\s+){0,2}(?:each|apiece)\b', text) or re.search(r'\beach\s+(?:\w+\s+){0,3}(?:has|had|holds|held|costs|cost|gets|got|weighs)\b', text):
        return ('number', x * y)
    return None


def geometry(text):
    found = [n for _, _, n in numbers(text)]
    if not re.search(r'\b(?:rectangle|rectangular|square|triangle|garden|room|field|rug|board|yard|floor|tile|park|patio|poster|frame|fence|border|sides?)\b', text):
        return None
    side_square = re.search(r'\bsquare\b', text) and len(found) == 1
    asks_area = re.search(r'\barea\b|\bsquare (?:units|feet|meters|centimeters|inches|yards)\b|\bcover(?:s|ed)?\b', text)
    asks_perimeter = re.search(r'\bperimeter\b|\baround\b|\bfence\b|\bborder\b|\btrim\b|\bedge\b', text)
    if asks_area and not asks_perimeter:
        if side_square:
            return ('number', found[0] * found[0])
        if len(found) == 2:
            return ('number', found[0] * found[1])
    if asks_perimeter and not asks_area:
        if side_square:
            return ('number', 4 * found[0])
        if re.search(r'\btriangle\b', text) and len(found) == 3:
            return ('number', sum(found))
        if len(found) == 2:
            return ('number', 2 * (found[0] + found[1]))
        if len(found) >= 3:
            return ('number', sum(found))
    return None


def conversion(text, endings=()):
    """'3 meters is the same as ... centimeters' style questions with one quantity (target unit may be in the options)."""
    found = numbers(text)
    if len(found) != 1:
        return None
    _, end, amount = found[0]
    unit = re.match(r'\s*([a-z]+)', text[end:])
    if not unit:
        return None
    unit = unit.group(1)
    for table in UNITS.values():
        if unit in table:
            targets = [u for u in re.findall(r'[a-z]+', text[end + len(unit):]) if u in table and table[u] != table[unit]]
            if not targets and re.search(r'\b(?:same as|equal to|equals|converted|in all|how many|that is|which is|that makes)\b|\bis\s*$|\bare\s*$', text):
                option_units = {w for e in endings for w in re.findall(r'[a-z]+', e.lower()) if w in table and table[w] != table[unit]}
                targets = sorted(option_units)[:1] if len(option_units) == 1 else []
            if targets:
                return ('number', amount * table[unit] / table[targets[-1]])
    return None


def money(text):
    amounts = cents(text)
    coins = [(m.start(), value(m.group(1)) * COINS[m.group(2).lower()])
             for m in re.finditer(r'(' + NUM + r')\s+(pennies|penny|nickels|nickel|dimes|dime|quarters|quarter)\b', text, re.I)]
    if coins and not amounts:
        return ('money', sum(c for _, c in coins))
    if not amounts:
        return None
    stripped = re.sub(r'\$\s?\d+(?:\.\d{1,2})?|\d+\s*(?:cents?\b|¢)', ' ', text)
    stripped = re.sub(r'(?i)\b(?:one|a|an|each)\s+(?=\w+\s+(?:costs?|is|sells))', ' ', stripped)   # unit price wording
    count = [n for _, _, n in numbers(stripped)]
    if len(amounts) == 1 and len(count) == 1 and re.search(r'\beach\b|\bper\b|\bapiece\b|\bfor one\b|\bcosts?\b', text):
        return ('money', amounts[0][1] * count[0])
    if len(amounts) == 2 and not count:
        first, second = amounts[0][1], amounts[1][1]
        between = text[amounts[0][0]:amounts[1][0] + 1]
        after = text[amounts[1][0]:]
        if re.search(r'\b(?:change|left|spent|spends|paid|pays|costs?|bought|buys)\b', between + after) and not re.search(r'\b(?:more|earned|saved|found|got|received|gave her|gave him)\b', between):
            if re.search(r'\bchange\b|\bleft\b|\bremain', after + between) or first > second:
                return ('money', first - second) if first >= second else None
        if re.search(r'\b(?:more|earned|saved|found|got|received|another|plus)\b', between + after) or re.search(r'\btogether\b|\bin all\b|\btotal\b', text):
            return ('money', first + second)
    return None


def clock(text):
    times = [(m, int(m.group(1)), int(m.group(2))) for m in re.finditer(r'(\d{1,2}):(\d{2})\s*(?:[ap]\.?m\.?)?', text, re.I)]
    rest = re.sub(r'\d{1,2}:\d{2}\s*(?:[ap]\.?m\.?)?', ' ', text, flags=re.I)
    if len(times) == 1:
        _, hours, minutes = times[0]
        start = (hours % 12) * 60 + minutes
        offset = 0
        for m in re.finditer(r'(' + NUM + r')\s+(hours?|minutes?)\b', rest):
            offset += value(m.group(1)) * (60 if m.group(2).startswith('hour') else 1)
        if offset == 0:
            return None
        before = re.search(r'\b(?:before|earlier|ago)\b', rest)
        return ('time', int(start - offset if before else start + offset))
    if len(times) == 2:
        a = (times[0][1] % 12) * 60 + times[0][2]
        b = (times[1][1] % 12) * 60 + times[1][2]
        return ('number', Fraction((b - a) % 720))      # elapsed minutes
    return None


def pattern(text):
    seq = re.search(r'((?:\d+\s*,\s*){2,}\d+)', text)
    if not seq:
        return None
    values = [int(v) for v in re.findall(r'\d+', seq.group(1))]
    steps = {b - a for a, b in zip(values, values[1:])}
    if len(steps) == 1:
        return ('number', Fraction(values[-1] + steps.pop()))
    if all(a and b % a == 0 for a, b in zip(values, values[1:])):
        ratios = {b // a for a, b in zip(values, values[1:])}
        if len(ratios) == 1:
            return ('number', Fraction(values[-1] * ratios.pop()))
    return None


def fraction_of(text):
    """'1/3 of 12 marbles' -> 4; 'cut into 8 equal slices ... ate 3' -> fraction 3/8 (or 5/8 left)."""
    part = re.search(r'(\d+)\s*/\s*(\d+)\s+of\s+(?:the\s+|her\s+|his\s+|their\s+)?(\d+)', text)
    if part and int(part.group(2)):
        return ('number', Fraction(int(part.group(1)), int(part.group(2))) * int(part.group(3)))
    back = re.search(r'(\d+)\s*/\s*(\d+)\s+of\s+(?:them|those|these|it|the\s+\w+)\b', text)
    earlier = [n for s0, _, n in numbers(text) if back and s0 < back.start()]
    if back and int(back.group(2)) and earlier:
        return ('number', Fraction(int(back.group(1)), int(back.group(2))) * earlier[0])
    word_part = re.search(r'\b(half|a third|one third|a quarter|one quarter|a fourth|one fourth)\s+of\s+(?:the\s+|her\s+|his\s+|their\s+)?(\d+)', text)
    if word_part:
        share = {'half': Fraction(1, 2), 'a third': Fraction(1, 3), 'one third': Fraction(1, 3), 'a quarter': Fraction(1, 4),
                 'one quarter': Fraction(1, 4), 'a fourth': Fraction(1, 4), 'one fourth': Fraction(1, 4)}[word_part.group(1)]
        return ('number', share * int(word_part.group(2)))
    whole = re.search(r'\b(?:into|in|has|have|had|with)\s+(' + NUM + r')\s+(?:equal\s+)?(?:parts|pieces|slices|sections|squares|shares)', text)
    if whole:
        total = value(whole.group(1))
        rest = numbers(text[whole.end():])
        if len(rest) == 1 and total:
            taken = rest[0][2]
            if re.search(r'\b(?:left|remain|not eaten|uneaten|still)\b', text[whole.end():]):
                return ('fraction', (total - taken) / total)
            return ('fraction', taken / total)
    return None


def data_total(text):
    """Tables and lists: 'Monday: 5, Tuesday: 7, Wednesday: 3' with total / difference questions."""
    pairs = re.findall(r'([A-Z][a-z]+)\s*(?::|had|has|read|sold|scored|got|=)\s*(\d+)', text)
    if len(pairs) < 2:
        return None
    values = [int(v) for _, v in pairs]
    if re.search(r'\b(?:total|altogether|in all|combined|together|all)\b', text, re.I):
        return ('number', Fraction(sum(values)))
    return None


def difference(text, endings):
    """'Ana had 45. Ben had 28. Ana had' + options '17 more than Ben' -> 17."""
    found = numbers(text)
    if len(found) != 2 or not endings:
        return None
    if not all(re.search(r'\b(?:more|fewer|less|longer|shorter|taller|older|younger|heavier|lighter)\b', e) for e in endings):
        if not re.search(r'\bhow many more\b|\bhow much more\b|\bdifference\b|\bhow many fewer\b', text):
            return None
    return ('number', abs(found[0][2] - found[1][2]))


def answers(context, endings):
    """All solver answers for a problem (deduplicated)."""
    text = ' '.join(context.split())
    if len(text) > 700:
        return []
    lower = text.lower()
    out = []
    multiplier = re.search(r'\b(twice|double|triple|half)\s+as\s+(?:many|much|long|tall|old)\b', lower)
    found = numbers(lower)
    if multiplier and len(found) == 1:
        out.append(('number', found[0][2] * MULTIPLIERS[multiplier.group(1)]))
    for solver in (pattern, clock, money, fraction_of, geometry, lambda t: conversion(t, endings), data_total):
        result = solver(text if solver in (data_total, money) else lower)
        if result is not None:
            out.append(result)
    if not out:
        for solver in (lambda t: difference(t, [e.lower() for e in endings]), equal_groups, running_total):
            result = solver(lower)
            if result is not None:
                out.append(result)
                break
    unique = []
    for a in out:
        if a not in unique:
            unique.append(a)
    return unique


def solve(context):
    """The single quantity a word problem asks for, as a Fraction, or None (kept for callers needing a number)."""
    found = [a for a in answers(context, []) if a[0] == 'number']
    return found[0][1] if len(found) == 1 else None


def solve_with_multiplier(context):
    lower = ' '.join(context.split()).lower()
    found = numbers(lower)
    multiplier = re.search(r'\b(twice|double|triple|half)\s+as\s+(?:many|much)\b', lower)
    if len(found) == 1 and multiplier:
        return found[0][2] * MULTIPLIERS[multiplier.group(1)]
    return None


def ending_number(ending):
    found = numbers(ending)
    return found[0][2] if found else None


def match(context, endings):
    """Index of the single option that states the solved answer; None if no solver is sure or they disagree."""
    candidates = answers(context, endings)
    if not candidates:
        return None
    stated = [read_answer(e) for e in endings]
    picks = set()
    for answer in candidates:
        hits = [i for i, s in enumerate(stated) if same(answer, s)]
        if len(hits) == 1:
            picks.add(hits[0])
    return picks.pop() if len(picks) == 1 else None
