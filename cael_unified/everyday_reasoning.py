"""Everyday reasoning that people actually ask a chat assistant, solved exactly. Never a neural model.

Each solver handles one clear shape and returns None for anything else, so other engines still get their turn:
- simple word problems: have/eat/give/spend/buy, unit prices, totals of groups, "twice as old", x + 3 = 10;
- "at the same time" trick questions (drying shirts, boiling eggs together);
- days of the week ("what day comes after Monday", "if today is Friday, what day is it in 3 days");
- comparing numbers ("which is bigger, 0.5 or 0.45"), "a kilogram of feathers or a kilogram of steel";
- counting letters ("how many r's in strawberry");
- number and letter sequences ("2, 4, 6, 8, ?", "1, 1, 2, 3, 5, 8"), odd one out;
- where things are ("the cup is on the table; the table is in the kitchen"), people moving ("then she ...");
- family relations ("Anna is the mother of Bob; Bob is the father of Carl; who is Carl's grandmother?");
- "all/some" syllogisms that do not follow.
Every answer shows its working.
"""
from fractions import Fraction
import re

DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
NUMBER_WORDS = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
                'ten': 10, 'eleven': 11, 'twelve': 12, 'twenty': 20, 'a dozen': 12, 'dozen': 12, 'a couple of': 2, 'a pair of': 2}
NUM = r'(\d+(?:\.\d+)?)'


def out(response, kind, steps=None):
    if steps:
        response = response + '\n\n' + '\n'.join(f'- {s}' for s in steps)
    return dict(route='chat/reasoning-' + kind, response=response, sources=[],
                details='Worked out step by step by CAEL\'s everyday reasoning rules. No neural model or web lookup.')


def words_to_numbers(text):
    for w, n in sorted(NUMBER_WORDS.items(), key=lambda x: -len(x[0])):
        text = re.sub(r'\b' + w + r'\b', str(n), text, flags=re.I)
    return text


def show(x):
    x = Fraction(x).limit_denominator(1000)
    return str(x.numerator) if x.denominator == 1 else f'{float(x):g}'


# ---------------------------------------------------------------- word problems

def word_problem(text):
    t = words_to_numbers(text.lower())
    # "If a pen costs 2 dollars, how much do 4 pens cost?"
    m = re.search(r'(?:a|one|1) (\w+?)s? costs? \$?' + NUM + r'\s*(?:dollars?|euros?|pounds?|\$|cents?)?.*?how much (?:do|does|would|will) ' + NUM + r' \1', t)
    if m:
        unit, each, count = m.group(1), Fraction(m.group(2)), Fraction(m.group(3))
        return out(f'**{show(each * count)}**.', 'word-problem', [f'{show(count)} {unit}s x {show(each)} each = {show(each * count)}'])
    # "I have 10 dollars and buy a book for 4 dollars. How much money do I have left?"
    m = re.search(r'(?:i|you|he|she|they|we|\w+) (?:have|has|had) \$?' + NUM + r'\s*(dollars?|euros?|pounds?|\$)?(.*?)how much (?:money )?(?:do|does|did) \w+ (?:have )?left', t)
    if m:
        total, rest = Fraction(m.group(1)), m.group(3)
        spent = [Fraction(x) for x in re.findall(r'(?:for|costs?|spends?|spent|pays?|paid) \$?' + NUM, rest)]
        if spent:
            left = total - sum(spent)
            return out(f'**{show(left)}** left.', 'word-problem', [f'{show(total)} - ' + ' - '.join(show(s) for s in spent) + f' = {show(left)}'])
    # "If I have 5 apples and eat 2, how many apples do I have left?"
    m = re.search(r'(?:have|has|had|there (?:are|were)|bought|buys?|got) ' + NUM + r' (\w+)(.*?)how many(?: \2)?(?: \w+)? (?:do|does|did|are|were) (?:\w+ )?(?:have )?(?:left|remaining|now)', t)
    if m:
        total, thing, events = Fraction(m.group(1)), m.group(2), m.group(3)
        steps, value = [f'Start: {show(total)} {thing}'], total
        for verb, n in re.findall(r'\b(eat|eats|ate|give|gives|gave|lose|loses|lost|sell|sells|sold|use|uses|used|drop|drops|dropped|break|breaks|broke|'
                                  r'buy|buys|bought|get|gets|got|find|finds|found|receive|receives|received|add|adds|added|pick|picks|picked)'
                                  r'(?: away)? ' + NUM, events):
            n = Fraction(n)
            if verb.startswith(('eat', 'ate', 'giv', 'gav', 'los', 'sel', 'sol', 'us', 'drop', 'brok', 'break')):
                value -= n; steps.append(f'{verb} {show(n)}: {show(value)}')
            else:
                value += n; steps.append(f'{verb} {show(n)}: {show(value)}')
        if len(steps) > 1 and value >= 0:
            return out(f'**{show(value)}** {thing} left.', 'word-problem', steps)
    # "A box has 3 red balls and 2 blue balls. How many balls are in the box?"
    m = re.search(r'how many (\w+?)s? (?:are|is) (?:there|in|on)', t)
    if m:
        thing = m.group(1)
        parts = re.findall(NUM + r' (?:\w+ )?' + re.escape(thing) + r's?\b', t.split('how many')[0])
        if len(parts) >= 2:
            total = sum(Fraction(p) for p in parts)
            return out(f'**{show(total)}** {thing}s.', 'word-problem', [' + '.join(parts) + f' = {show(total)}'])
    # "Sam has 3 brothers. Each brother has 2 sisters. How many sisters does Sam have?" (the brothers' sisters include Sam
    # if Sam is a girl).
    m = re.search(r'(\w+) has ' + NUM + r' brothers?\.? (?:each|every) (?:of (?:her|his|their) )?brothers? has ' + NUM + r' sisters?.*how many sisters (?:does|has) \1', t)
    if m:
        sisters = int(float(m.group(3)))
        girl = re.search(r'\b(?:she|her|girl|daughter|sister|woman)\b', t) and not re.search(r'\b(?:is a boy|he is|a boy|son)\b', t)
        if girl:
            return out(f'**{sisters - 1}**.', 'puzzle', [f"Each brother's {sisters} sisters include {m.group(1).capitalize()} herself, so she has {sisters - 1} other sister(s)."])
        if re.search(r'\b(?:boy|he|his|son|brother)\b', t.split('how many')[-1] + ' ' + t):
            return out(f'**{sisters}**.', 'puzzle', [f"{m.group(1).capitalize()} is a boy, so the brothers' {sisters} sisters are all his sisters too."])
    # "A car goes 50 km/h for 3 hours. How far does it travel?"
    m = re.search(NUM + r'\s*(km|kilometers?|kilometres?|miles?|mi|m|meters?|metres?)\s*(?:/|per |an |a )\s*(h|hr|hour|minute|min|second|sec|s)\b'
                  r'.*?(?:for|in|during) ' + NUM + r'\s*(hours?|hrs?|h|minutes?|mins?|seconds?|secs?)\b.*how (?:far|much distance|many \w+)', t)
    if m:
        # CAEL's exact rates helper (unit conversion, "why" replay, clarifying questions) answers the shapes it knows.
        from .helper_rates import solve as rates
        try:
            if rates(text) is not None:
                return None
        except Exception:
            return None
        speed, unit, per, time, time_unit = Fraction(m.group(1)), m.group(2), m.group(3), Fraction(m.group(4)), m.group(5)
        seconds = {'h': 3600, 'hr': 3600, 'hour': 3600, 'minute': 60, 'min': 60, 'second': 1, 'sec': 1, 's': 1}
        t_unit = re.sub(r's$', '', time_unit) if time_unit not in ('s',) else 's'
        t_unit = {'hrs': 'hr', 'mins': 'min', 'secs': 'sec'}.get(time_unit, t_unit)
        factor = Fraction(seconds.get(t_unit, seconds.get(time_unit, 1)), seconds[per])
        distance = speed * time * factor
        return out(f'**{show(distance)} {unit}**.', 'word-problem', [f'distance = speed x time = {show(speed)} {unit}/{per} x {show(time)} {time_unit} = {show(distance)} {unit}'])
    # "Tom is twice as old as Ann. Ann is 5. How old is Tom?"
    m = re.search(r'(\w+) is (twice|three times|four times|half|' + NUM + r' times) as (old|tall|heavy|long|big) as (\w+)\.? \5 is ' + NUM + r'.*how \4 is \1', t)
    if m:
        factor = {'twice': 2, 'three times': 3, 'four times': 4, 'half': Fraction(1, 2)}.get(m.group(2)) or Fraction(m.group(3))
        base = Fraction(m.group(6))
        return out(f'**{show(base * factor)}**.', 'word-problem', [f'{m.group(5).capitalize()} is {show(base)}, so {m.group(1).capitalize()} is {show(factor)} x {show(base)} = {show(base * factor)}'])
    # "If x + 3 = 10, what is x?"
    m = re.search(r'([a-z])\s*([+\-*/x×])\s*' + NUM + r'\s*=\s*' + NUM, t) or re.search(NUM + r'\s*([+\-*/x×])\s*([a-z])\s*=\s*' + NUM, t)
    if m and re.search(r'what is ([a-z])\b|solve|find ([a-z])\b', t):
        if m.group(1).isalpha():
            var, op, a, b = m.group(1), m.group(2), Fraction(m.group(3)), Fraction(m.group(4))
            value = {'+': b - a, '-': b + a, '*': b / a, 'x': b / a, '×': b / a, '/': b * a}[op]
        else:
            a, op, var, b = Fraction(m.group(1)), m.group(2), m.group(3), Fraction(m.group(4))
            value = {'+': b - a, '-': a - b, '*': b / a, 'x': b / a, '×': b / a, '/': a / b}[op]
        return out(f'**{var} = {show(value)}**.', 'equation', [f'Undo the {op} on both sides: {var} = {show(value)}'])
    return None


def same_time(text):
    """"A shirt takes 1 hour to dry; how long for 3 shirts together?" - things done at once take the same time."""
    t = words_to_numbers(text.lower())
    m = re.search(r'(?:takes?|needs?) ' + NUM + r' (minutes?|hours?|days?|seconds?) to (dry|boil|bake|cook|charge|melt|grow|cool|freeze|heat)'
                  r'.*how long (?:do|does|would|will) (?:it take (?:to \w+ )?)?' + NUM + r' \w+', t)
    if m and re.search(r'same time|together|at once|all at|in the sun|side by side|in the same', t):
        n, unit, verb = m.group(1), m.group(2), m.group(3)
        return out(f'Still **{n} {unit}**: they {verb} at the same time, so more of them does not take longer.', 'trick',
                   [f'Each one takes {n} {unit} on its own.', 'Together they happen in parallel, not one after another.'])
    return None


# ---------------------------------------------------------------- days, numbers, letters

def days(text):
    t = text.lower()
    m = re.search(r'what day (?:comes|is|will it be) (after|before) (' + '|'.join(DAYS) + r')', t)
    if m:
        i = DAYS.index(m.group(2)) + (1 if m.group(1) == 'after' else -1)
        return out(f'**{DAYS[i % 7].capitalize()}**.', 'days')
    m = re.search(r'(?:if )?today is (' + '|'.join(DAYS) + r').*?(?:in|after) (\d+|' + '|'.join(NUMBER_WORDS) + r') days?', t)
    if m:
        n = int(words_to_numbers(m.group(2)))
        start = DAYS.index(m.group(1))
        return out(f'**{DAYS[(start + n) % 7].capitalize()}**.', 'days', [f'{m.group(1).capitalize()} + {n} days; a week repeats every 7 days.'])
    m = re.search(r'(?:if )?today is (' + '|'.join(DAYS) + r').*?what (?:day )?(?:was|is) (?:it )?(\d+|' + '|'.join(NUMBER_WORDS) + r') days? ago', t)
    if m:
        n = int(words_to_numbers(m.group(2)))
        return out(f'**{DAYS[(DAYS.index(m.group(1)) - n) % 7].capitalize()}**.', 'days')
    m = re.search(r'(?:if )?(?:yesterday|tomorrow) (?:is|was) (' + '|'.join(DAYS) + r').*what day is (?:it )?today', t)
    if m:
        shift = -1 if 'tomorrow' in t.split('what')[0] else 1
        return out(f'**{DAYS[(DAYS.index(m.group(1)) + shift) % 7].capitalize()}**.', 'days')
    return None


CLOCK = r'(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?'


def minutes_of(h, m, half):
    h, m = int(h), int(m or 0)
    if half:
        half = half.replace('.', '')
        h = h % 12 + (12 if half == 'pm' else 0)
    return h * 60 + m


def clock_text(total, twelve):
    total %= 24 * 60
    h, m = divmod(total, 60)
    if twelve:
        return f'{(h - 1) % 12 + 1}:{m:02d} {"am" if h < 12 else "pm"}'
    return f'{h}:{m:02d}'


def clock(text):
    """"What time will it be 3 hours after 10:30 am?", "How long is it from 2:30 to 4:15?"."""
    t = words_to_numbers(text.lower())
    m = re.search(r'what time (?:will it be|is it|would it be)\s+(\d+)\s*(hours?|hrs?|minutes?|mins?)(?: and (\d+) (minutes?|mins?))? (after|from|before) ' + CLOCK, t) or \
        re.search(r'(?:it is|it\'s|the time is) ' + CLOCK + r'.*?what time (?:will it be|is it) (?:in|after) (\d+)\s*(hours?|hrs?|minutes?|mins?)', t)
    if m and m.re.pattern.startswith('what'):
        n, unit, extra, direction = int(m.group(1)), m.group(2), int(m.group(3) or 0), m.group(5)
        start = minutes_of(m.group(6), m.group(7), m.group(8))
        delta = (n * 60 if unit.startswith('h') else n) + extra
        end = start - delta if direction == 'before' else start + delta
        return out(f'**{clock_text(end, bool(m.group(8)))}**.', 'time', [f'{clock_text(start, bool(m.group(8)))} {"-" if direction == "before" else "+"} {delta} minutes'])
    if m:
        start = minutes_of(m.group(1), m.group(2), m.group(3))
        n, unit = int(m.group(4)), m.group(5)
        end = start + (n * 60 if unit.startswith('h') else n)
        return out(f'**{clock_text(end, bool(m.group(3)))}**.', 'time')
    m = re.search(r'how (?:long|many (?:hours|minutes)) (?:is it |are there )?(?:from|between) ' + CLOCK + r' (?:to|and|until|till) ' + CLOCK, t)
    if m:
        a = minutes_of(m.group(1), m.group(2), m.group(3) or m.group(6))
        b = minutes_of(m.group(4), m.group(5), m.group(6) or m.group(3))
        diff = (b - a) % (24 * 60)
        h, mi = divmod(diff, 60)
        said = (f'{h} hour{"s" if h != 1 else ""}' if h else '') + (' and ' if h and mi else '') + (f'{mi} minute{"s" if mi != 1 else ""}' if mi else '')
        return out(f'**{said or "0 minutes"}** ({diff} minutes).', 'time')
    return None


def age(text):
    """"I was born in 2000. How old am I?" (this year's birthday may or may not have passed yet)."""
    import datetime
    t = text.lower()
    m = re.search(r'(?:i was|i\'m|he was|she was|they were|\w+ was) born in (\d{4}).*how old', t) or \
        re.search(r'how old (?:am i|is (?:he|she|someone|a person)|are you|would i be) if (?:i was|i\'m|he was|she was|someone was|born) (?:born )?in (\d{4})', t)
    if not m:
        return None
    year, now = int(m.group(1)), datetime.date.today().year
    if not 1900 <= year <= now:
        return None
    return out(f'**{now - year - 1} or {now - year}** in {now}: {now - year} after this year\'s birthday, {now - year - 1} before it.', 'age',
               [f'{now} - {year} = {now - year}'])


def compare_numbers(text):
    t = text.lower()
    m = re.search(r'which is (bigger|larger|greater|smaller|less|more|higher|lower)[,:]? (-?\d+(?:\.\d+)?(?:/\d+)?) or (-?\d+(?:\.\d+)?(?:/\d+)?)', t) or \
        re.search(r'is (-?\d+(?:\.\d+)?) (bigger|larger|greater|smaller|less|more) than (-?\d+(?:\.\d+)?)', t)
    if m and m.group(1)[0].isalpha():
        word, a, b = m.group(1), m.group(2), m.group(3)
        x, y = Fraction(a), Fraction(b)
        if x == y:
            return out(f'They are equal: {a} = {b}.', 'compare')
        big = a if x > y else b
        small = b if x > y else a
        pick = big if word in ('bigger', 'larger', 'greater', 'more', 'higher') else small
        return out(f'**{pick}** is {word}.', 'compare', [f'{big} > {small}' + (' (compare them as decimals: ' + f'{float(x):g} vs {float(y):g})' if '.' in a + b or '/' in a + b else '')])
    if m:
        a, word, b = m.group(1), m.group(2), m.group(3)
        bigger = Fraction(a) > Fraction(b)
        yes = bigger if word in ('bigger', 'larger', 'greater', 'more') else Fraction(a) < Fraction(b)
        return out(f'**{"Yes" if yes else "No"}**: {a} {">" if bigger else "<" if Fraction(a) < Fraction(b) else "="} {b}.', 'compare')
    m = re.search(r'(?:which is heavier|what weighs more)[,:]? (?:a|one|1) (kilo(?:gram)?|kg|pound|ton(?:ne)?) of (\w+) or (?:a|one|1) \1 of (\w+)', t)
    if m:
        return out(f'**Neither**: they weigh the same. A {m.group(1)} of {m.group(2)} and a {m.group(1)} of {m.group(3)} are both one {m.group(1)}; '
                   f'the {m.group(2)} just take up more space.', 'trick')
    return None


def count_letters(text):
    m = re.search(r"(?i)how many (?:times (?:does|is) )?(?:the )?(?:letter )?(['\"]?)([a-z])\1(?:'s|s)?( letters?)? (?:are )?(?:there )?(?:in|appear in) "
                  r"(?:the )?(?:word )?['\"]?([a-z]+)['\"]?", text)
    # A clear letter: quoted, followed by "letter(s)", or written "r's" ("How many L does the pump pump?" is litres).
    if m and (m.group(1) or m.group(3) or re.search(r"(?i)\bletter\b|'s\b", text)):
        letter, word = m.group(2).lower(), m.group(4).lower()
        n = word.count(letter)
        where = ', '.join(str(i + 1) for i, ch in enumerate(word) if ch == letter)
        return out(f'**{n}**: the word "{word}" has {n} "{letter}"' + ('' if n == 1 else 's') + '.', 'letters',
                   [f'Positions: {where}' if n else f'"{letter}" does not appear in "{word}".'])
    m = re.search(r"(?i)how many letters (?:are )?(?:there )?in (?:the )?(?:word )?['\"]?([a-z]+)['\"]?", text)
    if m:
        word = m.group(1)
        return out(f'**{len(word)}**: "{word}" has {len(word)} letters.', 'letters', [' - '.join(word.upper())])
    return None


def sequences(text):
    t = text.lower()
    if not re.search(r'what comes next|next (?:number|term|letter)|continue the (?:sequence|pattern)|complete the (?:sequence|pattern)|what is the next|\?\s*$|_\s*$', t):
        return None
    nums = re.findall(r'-?\d+(?:\.\d+)?', t.split('next')[-1] if 'next:' in t else t)
    run = re.search(r'\b([a-z])\s*,\s*([a-z])\s*,\s*([a-z])(?:\s*,\s*([a-z]))*\b', t)
    letters = re.findall(r'\b([a-z])\b', run.group(0)) if run else []
    if len(nums) >= 4 and not re.search(r'[a-z]\s*,', re.sub(r'what comes next|next (?:number|term)|sequence|pattern', '', t)):
        xs = [Fraction(n) for n in nums]
        diffs = [b - a for a, b in zip(xs, xs[1:])]
        if len(set(diffs)) == 1:
            return out(f'**{show(xs[-1] + diffs[0])}**.', 'sequence', [f'Each number goes up by {show(diffs[0])}.' if diffs[0] >= 0 else f'Each number goes down by {show(-diffs[0])}.'])
        if all(x != 0 for x in xs) and len({b / a for a, b in zip(xs, xs[1:])}) == 1:
            r = xs[1] / xs[0]
            return out(f'**{show(xs[-1] * r)}**.', 'sequence', [f'Each number is multiplied by {show(r)}.'])
        if all(xs[i] == xs[i - 1] + xs[i - 2] for i in range(2, len(xs))):
            return out(f'**{show(xs[-1] + xs[-2])}**.', 'sequence', ['Each number is the sum of the two before it (Fibonacci-style).'])
        second = [b - a for a, b in zip(diffs, diffs[1:])]
        if len(set(second)) == 1:
            nxt = xs[-1] + diffs[-1] + second[0]
            return out(f'**{show(nxt)}**.', 'sequence', [f'The gaps grow by {show(second[0])} each time: ' + ', '.join(show(d) for d in diffs) + f', then {show(diffs[-1] + second[0])}.'])
        if all(round(float(x) ** 0.5) ** 2 == x for x in xs):
            roots = [round(float(x) ** 0.5) for x in xs]
            if all(b - a == 1 for a, b in zip(roots, roots[1:])):
                return out(f'**{(roots[-1] + 1) ** 2}**.', 'sequence', ['These are square numbers: ' + ', '.join(f'{r}²' for r in roots) + '.'])
        return None
    if len(letters) >= 3 and len(nums) == 0:
        codes = [ord(c) for c in letters]
        steps = {b - a for a, b in zip(codes, codes[1:])}
        if len(steps) == 1:
            nxt = codes[-1] + steps.pop()
            if ord('a') <= nxt <= ord('z'):
                return out(f'**{chr(nxt).upper()}**.', 'sequence', [f'The letters move {codes[1] - codes[0]} place(s) along the alphabet each time.'])
    return None


def odd_one_out(text):
    t = text.lower()
    if not re.search(r'odd one out|which (?:number )?does(?:n\'t| not) belong|which is different', t):
        return None
    nums = [int(n) for n in re.findall(r'-?\d+', t)]
    if len(nums) < 3:
        return None
    tests = [('even', lambda n: n % 2 == 0), ('odd', lambda n: n % 2 == 1),
             ('prime', lambda n: n > 1 and all(n % d for d in range(2, int(n ** 0.5) + 1))),
             ('a multiple of 3', lambda n: n % 3 == 0), ('a multiple of 5', lambda n: n % 5 == 0),
             ('a square number', lambda n: n >= 0 and round(n ** 0.5) ** 2 == n)]
    for name, test in tests:
        outs = [n for n in nums if not test(n)]
        if len(outs) == 1:
            return out(f'**{outs[0]}**: every other number is {name}, and {outs[0]} is not.', 'odd-one-out')
    return None


# ---------------------------------------------------------------- where things are, people moving, families

def locations(text):
    """"The cup is on the table. The table is in the kitchen. Where is the cup?" and moves with "then", "she", "them"."""
    m = re.search(r'(?i)where (?:is|are) (?:the |my |his |her )?(\w+)\??\s*$', text.strip())
    if not m:
        return None
    target = m.group(1).lower()
    story = text[:m.start()]
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', story) if s.strip()]
    place, chain, person_places, last_person, last_object = {}, [], {}, None, None
    for s in sentences:
        s2 = re.sub(r'(?i)^(?:then|after that|later|next|afterwards|finally|and)[, ]+', '', s.rstrip('.!?')).strip()
        low = s2.lower()
        mp = re.match(r'(\w+) (?:went|walked|ran|moved|travelled|traveled|drove|came|goes|walks|moves|is going) (?:back )?(?:to|into|in) (?:the )?(.+)', low)
        if mp and mp.group(1) not in ('it', 'they', 'them'):
            who = last_person if mp.group(1) in ('she', 'he') else mp.group(1)
            person_places[who] = mp.group(2); last_person = who
            continue
        mo = re.match(r'(\w+) (?:put|puts|placed|places|left|leaves|dropped|drops|hid|hides|moved|moves) (?:her |his |their |the |my )?(\w+) (?:in|into|on|onto|under|inside) (?:the |her |his |their |a )?(.+)', low)
        if mo:
            who = last_person if mo.group(1) in ('she', 'he') else mo.group(1)
            last_person = who
            obj = last_object if mo.group(2) in ('them', 'it') else mo.group(2)
            if mo.group(2) not in ('them', 'it'):
                last_object = obj
            place[obj] = mo.group(3)
            continue
        mo2 = re.match(r'(?:she|he|they|\w+) (?:moved|moves|put|puts|took|takes) (them|it) (?:to|into|in|on|onto) (?:the |her |his |their |a )?(.+)', low)
        if mo2 and last_object:
            place[last_object] = mo2.group(2)
            continue
        ml = re.match(r'(?:the |a |my )?(\w+) (?:is|are|was|were|sits|lies|stands) (?:in|on|under|inside|at|next to) (?:the |a )?(.+)', low)
        if ml:
            prep = re.search(r'\b(in|on|under|inside|at|next to)\b', low).group(1)
            place[ml.group(1)] = (prep, ml.group(2))
            continue
    if target in person_places:
        return out(f'**In the {person_places[target]}**.', 'state', ['The last place mentioned for them.'])
    if target.rstrip('s') in place or target in place:
        key = target if target in place else target.rstrip('s')
        here = place[key]
        if isinstance(here, str):
            return out(f'**In the {here}**.', 'state', ['The last place it was moved to.'])
        trail, seen = [here], {key}
        while isinstance(here, tuple) and here[1] in place and here[1] not in seen:
            seen.add(here[1]); here = place[here[1]]; trail.append(here)
        description = ', '.join(f'{p} the {w}' for p, w in trail)
        return out(f'The {key} is **{description}**.', 'state', [f'The {key} is {trail[0][0]} the {trail[0][1]}.'] +
                   [f'... which is {p} the {w}.' for p, w in trail[1:]])
    return None


PARENT = re.compile(r"(?i)(\w+) is (?:the )?(mother|father|parent|mom|dad|mum) of (\w+)|(\w+) is (\w+)'s (mother|father|parent|mom|dad|mum)")


def family(text):
    m = re.search(r"(?i)who is (?:the )?(grandmother|grandfather|grandparent|grandma|grandpa|mother|father|parent|child|son|daughter|grandchild|grandson|granddaughter) of (\w+)|"
                  r"who is (\w+)'s (grandmother|grandfather|grandparent|grandma|grandpa|mother|father|parent|child|son|daughter|grandchild|grandson|granddaughter)", text)
    if not m:
        return None
    relation, person = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
    relation = relation.lower()
    parents = {}
    genders = {}
    for p in PARENT.finditer(text):
        a, role, b = (p.group(1), p.group(2), p.group(3)) if p.group(1) else (p.group(4), p.group(6), p.group(5))
        parents.setdefault(b.lower(), []).append(a)
        genders[a.lower()] = 'f' if role.lower() in ('mother', 'mom', 'mum') else 'm' if role.lower() in ('father', 'dad') else None
    if not parents:
        return None
    want_gender = 'f' if relation in ('grandmother', 'grandma', 'mother', 'daughter', 'granddaughter') else 'm' if relation in ('grandfather', 'grandpa', 'father', 'son', 'grandson') else None
    target = person.lower()
    if relation.startswith('grand') and relation not in ('grandchild', 'grandson', 'granddaughter'):
        found = [g for p in parents.get(target, []) for g in parents.get(p.lower(), [])]
    elif relation in ('mother', 'father', 'parent'):
        found = parents.get(target, [])
    elif relation in ('child', 'son', 'daughter'):
        found = [c for c, ps in parents.items() if target in [x.lower() for x in ps]]
        found = [c.capitalize() for c in found]
    else:
        found = [c.capitalize() for c, ps in parents.items() for p in ps for c2, ps2 in parents.items() if c == p.lower() and False]
        kids = [c for c, ps in parents.items() if target in [x.lower() for x in ps]]
        found = [g.capitalize() for k in kids for g, ps in parents.items() if k in [x.lower() for x in ps]]
    if want_gender and relation not in ('son', 'daughter', 'grandson', 'granddaughter'):
        found = [f for f in found if genders.get(f.lower()) in (want_gender, None)]
    if len(found) == 1:
        return out(f'**{found[0]}**.', 'family', [f'Following the parent links in the story gives {found[0]} as the {relation} of {person}.'])
    return None


def syllogism(text):
    t = text.lower()
    m = re.search(r'(?:if )?all (\w+) are (\w+) and some \2 (?:are |can |have )?(.+?)[,.]? (?:does|do|are|is|can) (?:it (?:follow|mean) (?:that )?)?all \1 (?:are |can |have )?(.+?)\?', t)
    if m:
        return out(f'**No, not necessarily.** All {m.group(1)} are {m.group(2)}, but the {m.group(2)} that {m.group(3)} might not include any {m.group(1)}.', 'logic')
    return None


SOLVERS = (same_time, word_problem, days, clock, age, compare_numbers, count_letters, sequences, odd_one_out, family, syllogism, locations)


def reply(text):
    if len(text) > 700 or '```' in text:
        return None
    for solve in SOLVERS:
        try:
            answer = solve(text)
        except (ValueError, ZeroDivisionError, IndexError):
            answer = None
        if answer is not None:
            return answer
    return None
