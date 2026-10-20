"""More everyday reasoning: conditionals, comparisons, all/no/some statements, word problems, time and days,
analogies and a small common-sense table.

Each solver reads one kind of problem and answers with its steps, or returns None so other routes can try.
Everything is rule-based: the reading patterns, the inference rules and the common-sense table are written for
CAEL; analogies use the WordNet dictionary (dictionary.py).
"""
from datetime import datetime, timedelta
from fractions import Fraction
import re

DETAILS = 'Rule-based reasoning from your stated facts (no web lookup, no neural model). Steps are shown.'
NUMBER_WORDS = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
                'eleven': 11, 'twelve': 12, 'fifteen': 15, 'twenty': 20, 'thirty': 30, 'a dozen': 12, 'a hundred': 100, 'a': 1, 'an': 1}
FACTORS = {'twice': 2, 'double': 2, 'three times': 3, 'thrice': 3, 'four times': 4, 'five times': 5, 'ten times': 10, 'half': Fraction(1, 2),
           'a third of': Fraction(1, 3), 'a quarter of': Fraction(1, 4)}
DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


def out(response, route, steps=None):
    text = response + ('\n\nSteps:\n' + '\n'.join(f'{i}. {s}' for i, s in enumerate(steps, 1)) if steps else '')
    return dict(response=text, route='chat/reasoning-' + route, sources=[], details=DETAILS)


def number(text):
    text = text.strip().lower()
    if text in NUMBER_WORDS:
        return Fraction(NUMBER_WORDS[text])
    try:
        return Fraction(text.replace(',', ''))
    except (ValueError, ZeroDivisionError):
        return None


def show(value):
    value = Fraction(value)
    if value.denominator == 1:
        return str(value.numerator)
    return f'{float(value):.2f}'.rstrip('0').rstrip('.')


def sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', text.strip()) if s.strip()]


# ---------------------------------------------------------------- conditionals

def norm_clause(clause):
    """'it is raining' / 'it rains' -> 'it rain'; 'the ground gets wet' / 'the ground is wet' -> 'ground wet'."""
    from . import dictionary as dic
    words = re.findall(r"[a-z']+", clause.lower())
    negative = any(w in ("not", "n't", 'never', 'no', "isn't", "doesn't", "don't", "aren't", "won't") or w.endswith("n't") for w in words)
    keep = []
    for w in words:
        if w in ('the', 'a', 'an', 'is', 'are', 'am', 'was', 'were', 'be', 'gets', 'get', 'got', 'becomes', 'become', 'will', 'does',
                 'do', 'did', 'not', 'never', 'no', 'then', 'it', 'its', 'very', 'really', 'also', 'so', 'too', 'still', 'always') or w.endswith("n't"):
            continue
        base = w
        # Inflected forms go to their base (rains, raining -> rain); other dictionary words stay ("ground", not grind).
        for b in (dic.bases(w) if re.search(r'(?:s|ing|ed)$', w) or dic.senses(w)[1] != w else []):
            if b != w and dic.senses(b)[1] == b:
                base = b
                break
        keep.append(base)
    return ' '.join(keep), negative


def conditional(text):
    parts = sentences(text)
    if len(parts) < 2 or not parts[-1].endswith('?'):
        return None
    rules, facts = [], []
    for p in parts[:-1]:
        m = re.match(r'(?i)^(?:if|when|whenever)\s+(.+?),\s*(?:then\s+)?(.+?)[.!]?$', p) or re.match(r'(?i)^(.+?)\s+if\s+(.+?)[.!]?$', p)
        if m:
            cond, result = (m[1], m[2]) if p.lower().startswith(('if', 'when')) else (m[2], m[1])
            rules.append((norm_clause(cond), norm_clause(result), p, cond.strip(), result.strip()))
        else:
            facts.append((norm_clause(p.rstrip('.!')), p))
    if not rules:
        return None
    question = re.sub(r'(?i)^(?:so\s+|then\s+)?', '', parts[-1].rstrip('?'))
    ask = re.match(r'(?i)^(?:is|are|does|do|will|did|was|were|can)\s+(.+)$', question)
    if not ask:
        return None
    goal, _ = norm_clause(ask[1])
    known = {f[0][0]: (not f[0][1], f[1]) for f in facts}       # clause -> (true?, sentence)
    steps = []
    changed = True
    while changed:                                              # chain the rules forward and backward
        changed = False
        for (c, cneg), (r, rneg), sentence, cond_text, result_text in rules:
            if c in known and known[c][0] == (not cneg) and r not in known:
                known[r] = (not rneg, sentence)
                steps.append(f'"{sentence}" and "{known[c][1]}" mean: {result_text}.')
                changed = True
            elif r in known and known[r][0] == rneg and c not in known:   # modus tollens: result false -> condition false
                known[c] = (cneg, sentence)
                steps.append(f'"{sentence}" Since the result did not happen, the condition did not happen either: not "{cond_text}".')
                changed = True
    if goal in known:
        yes = known[goal][0]
        return out('Yes.' if yes else 'No.', 'conditional', steps or [f'You stated it: {known[goal][1]}'])
    for (c, _), (r, _), sentence, *_ in rules:
        if c == goal and r in known and known[r][0]:
            return out('Not necessarily. The rule only says what follows *from* that condition; the result could have another '
                       'cause (this is the mistake called "affirming the consequent").', 'conditional')
    return out('The facts you gave do not settle that.', 'conditional')


# ---------------------------------------------------------------- comparisons

COMPARATIVES = {'taller': 'shorter', 'older': 'younger', 'bigger': 'smaller', 'larger': 'smaller', 'heavier': 'lighter',
                'faster': 'slower', 'richer': 'poorer', 'longer': 'shorter', 'higher': 'lower', 'stronger': 'weaker', 'smarter': None,
                'better': 'worse', 'hotter': 'colder', 'warmer': 'colder', 'cheaper': None, 'louder': 'quieter', 'wider': 'narrower',
                'happier': 'sadder', 'earlier': 'later', 'nicer': None, 'darker': 'lighter', 'deeper': 'shallower', 'busier': None}
SUPERLATIVE = {'tallest': ('taller', 1), 'shortest': ('taller', -1), 'oldest': ('older', 1), 'youngest': ('older', -1), 'biggest': ('bigger', 1),
               'smallest': ('bigger', -1), 'largest': ('larger', 1), 'heaviest': ('heavier', 1), 'lightest': ('heavier', -1),
               'fastest': ('faster', 1), 'slowest': ('faster', -1), 'richest': ('richer', 1), 'poorest': ('richer', -1),
               'longest': ('longer', 1), 'highest': ('higher', 1), 'lowest': ('higher', -1), 'strongest': ('stronger', 1),
               'weakest': ('stronger', -1), 'best': ('better', 1), 'worst': ('better', -1), 'hottest': ('hotter', 1),
               'coldest': ('hotter', -1), 'cheapest': ('cheaper', 1), 'smartest': ('smarter', 1), 'loudest': ('louder', 1)}
OPPOSITE = {}
for _a, _b in COMPARATIVES.items():
    if _b:
        OPPOSITE.setdefault(_b, _a)


def comparison(text):
    parts = sentences(text)
    if len(parts) < 2:
        return None
    edges, dimension, names = {}, None, []
    for p in parts[:-1]:
        for m in re.finditer(r'(?i)\b([A-Z][a-z]+|the \w+)\s+(?:is|are|was|runs|grows)\s+(?:much\s+|a bit\s+|even\s+)?(\w+er|more \w+|less \w+)\s+than\s+([A-Z][a-z]+|the \w+)', p):
            a, comp, b = m[1], m[2].lower(), m[3]
            if comp.startswith('less '):
                comp, a, b = 'more ' + comp[5:], b, a
            if comp in OPPOSITE:                               # "Bob is shorter than Ann" = "Ann is taller than Bob"
                comp, a, b = OPPOSITE[comp], b, a
            if dimension and comp != dimension:
                return None
            dimension = comp
            edges.setdefault(a, set()).add(b)
            names += [a, b]
    if not dimension:
        return None
    names = list(dict.fromkeys(names))

    def above(x):                                              # everyone x is more <dimension> than
        seen, todo = set(), [x]
        while todo:
            for y in edges.get(todo.pop(), ()):
                if y not in seen:
                    seen.add(y)
                    todo.append(y)
        return seen

    if any(n in above(n) for n in names):
        return out('These comparisons contradict each other (someone ends up more than themselves).', 'comparison')
    question = parts[-1].rstrip('?').strip()
    adjective = dimension[:-2] if dimension.endswith('er') else dimension
    sup = re.search(r'(?i)\bwho(?:\'s| is| was)?\s+(?:the\s+)?(\w+est|most \w+|least \w+)\b', question)
    if sup:
        word = sup[1].lower()
        comp, direction = SUPERLATIVE.get(word, (None, 0))
        if word.startswith(('most ', 'least ')):
            comp, direction = 'more ' + word.split()[1], 1 if word.startswith('most') else -1
        if comp != dimension:
            return None
        ranked = [n for n in names if (len(above(n)) == len(names) - 1 if direction > 0 else not above(n) and all(n in above(m) for m in names if m != n))]
        if len(ranked) != 1:
            return out(f'The comparisons do not say who is the {word}.', 'comparison')
        order = sorted(names, key=lambda n: -len(above(n)))
        return out(f'**{ranked[0]}** is the {word}.', 'comparison', [f'From most to least {adjective}: ' + ' > '.join(order) + '.'])
    pair = re.match(r'(?i)^(?:is|are|was)\s+([A-Z][a-z]+|the \w+)\s+(\w+er|more \w+)\s+than\s+([A-Z][a-z]+|the \w+)$', question)
    if pair:
        a, comp, b = pair[1], pair[2].lower(), pair[3]
        if comp in OPPOSITE:
            comp, a, b = OPPOSITE[comp], b, a
        if comp != dimension:
            return None
        if b in above(a):
            return out('Yes.', 'comparison', [f'{a} > {b} follows from the chain: ' + ' > '.join(sorted(names, key=lambda n: -len(above(n)))) + '.'])
        if a in above(b):
            return out('No.', 'comparison', [f'It is the other way round: {b} is {comp} than {a}.'])
        return out('The comparisons do not say.', 'comparison')
    which = re.match(r'(?i)^(?:who|which)(?: one)? is (\w+er|more \w+),?\s+([A-Z][a-z]+|the \w+)\s+or\s+([A-Z][a-z]+|the \w+)$', question)
    if which:
        comp, a, b = which[1].lower(), which[2], which[3]
        flip = comp in OPPOSITE
        dim = OPPOSITE.get(comp, comp)
        if dim != dimension:
            return None
        winner = a if b in above(a) else b if a in above(b) else None
        if winner and flip:
            winner = b if winner == a else a
        return out(f'**{winner}**.' if winner else 'The comparisons do not say.', 'comparison')
    if re.search(r'(?i)\border\b|\brank\b|\bsort\b', question):
        order = sorted(names, key=lambda n: -len(above(n)))
        return out(f'From most to least {adjective}: ' + ' > '.join(order) + '.', 'comparison')
    return None


# ---------------------------------------------------------------- all / no / some

def category_word(text):
    word = re.sub(r'^(?:a|an|the)\s+', '', text.strip().lower().rstrip('.?!'))
    from . import dictionary as dic
    if word.endswith('s') and not word.endswith('ss'):
        found, base = dic.senses(word)
        if found and base != word:
            return base                                   # "roses" -> rose (a dictionary word), not "ros"
        return word[:-1]
    return word


def categorical(text):
    body = re.sub(r'(?i)^\s*(?:if|suppose|given that)\s+', '', text.strip())
    parts = [p.strip() for p in re.split(r'(?<=[.!?])\s+|,\s*(?:and\s+)?(?=(?:all|no|some|every)\b)|\s+and\s+(?=(?:all|no|some|every)\b)', body) if p.strip()]
    question = parts[-1] if parts[-1].endswith('?') else None
    if not question:
        tail = re.search(r'(?i),\s*((?:is|are|can)\b.+\?)$', body)
        if not tail:
            return None
        question = tail[1]
    premises = [p for p in parts if p != question and not p.endswith('?')]
    if re.search(r'(?i),\s*(?:is|are)\b', parts[-1]) and parts[-1].endswith('?'):
        head, question = re.split(r'(?i),\s*(?=(?:is|are)\b)', parts[-1], maxsplit=1)
        premises.append(head)
    alls, nones, somes, members = [], [], [], []
    for p in premises:
        p = p.rstrip('.!').strip()
        if m := re.match(r'(?i)^(?:all|every|each)\s+(\w+(?: \w+)?)\s+(?:are|is)\s+(?:an?\s+)?(\w+(?: \w+)?)$', p):
            alls.append((category_word(m[1]), category_word(m[2])))
        elif m := re.match(r'(?i)^no\s+(\w+(?: \w+)?)\s+(?:are|is)\s+(?:an?\s+)?(\w+(?: \w+)?)$', p):
            nones.append((category_word(m[1]), category_word(m[2])))
        elif m := re.match(r'(?i)^some\s+(\w+(?: \w+)?)\s+(?:are|is)\s+(?:an?\s+)?(\w+(?: \w+)?)$', p):
            somes.append((category_word(m[1]), category_word(m[2])))
        elif m := re.match(r'(?i)^((?:an?\s+|the\s+)?[A-Za-z]+)\s+is\s+(?:an?\s+)?(\w+(?: \w+)?)$', p):
            members.append((m[1].strip(), category_word(m[2])))
        elif m := re.match(r'(?i)^((?:an?\s+|the\s+)?[A-Za-z]+)\s+is\s+not\s+(?:an?\s+)?(\w+(?: \w+)?)$', p):
            members.append((m[1].strip(), '!' + category_word(m[2])))
        else:
            return None
    if not (alls or nones or somes):
        return None

    def supersets(category):
        seen, todo = {category}, [category]
        while todo:
            c = todo.pop()
            for a, b in alls:
                if a == c and b not in seen:
                    seen.add(b)
                    todo.append(b)
        return seen

    def chain(start, goal):
        paths = {start: [start]}
        todo = [start]
        while todo:
            c = todo.pop(0)
            for a, b in alls:
                if a == c and b not in paths:
                    paths[b] = paths[c] + [b]
                    todo.append(b)
        return paths.get(goal, [start, goal])

    def excluded(category):
        ups = supersets(category)
        return {b for a, b in nones if a in ups} | {a for a, b in nones if b in ups}

    q = question.rstrip('?').strip()
    if m := re.match(r'(?i)^(?:are|is)\s+(all|some|any)\s+(\w+(?: \w+)?)\s+(?:an?\s+)?(\w+(?: \w+)?)$', q):
        quantifier, x, y = m[1].lower(), category_word(m[2]), category_word(m[3])
        if quantifier == 'all':
            if y in supersets(x):
                return out('Yes.', 'categories', [f'Following the "all ... are ..." statements: {" → ".join(chain(x, y))}.'])
            if y in excluded(x):
                return out('No, none of them are.', 'categories')
            if any(a == x and b == y for a, b in somes):
                return out('Not necessarily. You only said *some* are; that does not make all of them so.', 'categories')
            return out('The statements do not say that.', 'categories')
        if y in supersets(x) or any(a == x and b == y for a, b in somes):
            return out('Yes.', 'categories')
        if y in excluded(x):
            return out('No.', 'categories', [f'No {x} is {y}, following the "no ... are ..." statement.'])
        return out('The statements do not say.', 'categories')
    if m := re.match(r'(?i)^(?:is|can)\s+((?:an?\s+|the\s+)?[A-Za-z]+)\s+(?:be\s+)?(?:an?\s+)?(\w+(?: \w+)?)$', q):
        thing, y = m[1].strip(), category_word(m[2])
        found = [c for t, c in members if t.lower() == thing.lower() and not c.startswith('!')]
        if not found:
            return None
        ups = set().union(*(supersets(c) for c in found))
        if y in ups:
            return out('Yes.', 'categories', [f'{thing} is {article(found[0])}, and every {found[0]} is {article(y)}.' if y != found[0] else 'You said so.'])
        if any(y in excluded(c) for c in found):
            c = next(c for c in found if y in excluded(c))
            return out('No.', 'categories', [f'{thing} is a {c}.', f'No {c} is a {y} (from "no ... are ...").'])
        return out('The statements do not say.', 'categories')
    return None


def article(word):
    return ('an ' if word[:1] in 'aeiou' else 'a ') + word


def fallacy(text):
    """'Some cats are black, so all cats are black': a conclusion that does not follow."""
    m = re.search(r'(?i)\bsome\s+(\w+)\s+are\s+(\w+),?\s*(?:so|therefore|thus|hence)\s+all\s+(\w+)\s+are\s+(\w+)', text)
    if m and category_word(m[1]) == category_word(m[3]) and m[2].lower() == m[4].lower():
        return out(f'No, that does not follow. "Some {m[1]} are {m[2]}" says nothing about the rest; other {m[1]} can be '
                   f'different. Going from some to all is called a hasty generalisation.', 'fallacy')
    m = re.search(r'(?i)\ball\s+(\w+)\s+are\s+(\w+),?\s*(?:so|therefore)\s+all\s+(\w+)\s+are\s+(\w+)', text)
    if m and category_word(m[1]) == category_word(m[4]) and category_word(m[2]) == category_word(m[3]):
        return out(f'No. "All {m[1]} are {m[2]}" does not mean all {m[2]} are {m[1]} (all dogs are animals, but not all '
                   'animals are dogs).', 'fallacy')
    return None


# ---------------------------------------------------------------- word problems

def word_problem(text):
    lower = text.lower()
    # "Sam has twice as many sweets as Lee. Lee has 4."
    m = re.search(r'\b([a-z]+)\s+has\s+(twice|double|three times|four times|five times|ten times|half|thrice)\s+as\s+many\s+(\w+)\s+as\s+([a-z]+)', lower)
    if m:
        a, factor, things, b = m[1], FACTORS[m[2]], m[3], m[4]
        given = re.search(r'\b' + b + r'\s+has\s+(\d+|\w+)', lower[m.end():] + ' ' + lower[:m.start()])
        if given and number(given[1]) is not None and re.search(r'how many', lower):
            value = factor * number(given[1])
            return out(f'{a.capitalize()} has **{show(value)}** {things}.', 'word-problem',
                       [f'{b.capitalize()} has {show(number(given[1]))}.', f'{a.capitalize()} has {m[2]} as many: {show(factor)} × {show(number(given[1]))} = {show(value)}.'])
    m = re.search(r'\b([a-z]+)\s+has\s+(\d+|\w+)\s+more\s+(\w+)?\s*than\s+([a-z]+)', lower)
    if m and number(m[2]) is not None:
        given = re.search(r'\b' + m[4] + r'\s+has\s+(\d+)', lower)
        if given and 'how many' in lower:
            value = number(given[1]) + number(m[2])
            return out(f'{m[1].capitalize()} has **{show(value)}**.', 'word-problem', [f'{show(number(given[1]))} + {show(number(m[2]))} = {show(value)}.'])
    # "There are 5 birds on a tree. 2 fly away. How many are left?"
    m = re.search(r'\bthere (?:are|were)\s+(\d+|\w+)\s+(\w+)', lower)
    if m and number(m[1]) is not None and re.search(r'how many', lower):
        total, things, steps = number(m[1]), m[2], [f'Start: {show(number(m[1]))} {m[2]}.']
        for e in re.finditer(r'(\d+|\w+)\s+(?:more\s+)?(?:\w+\s+)?(fly away|flew away|leave|left|go away|went away|are eaten|were eaten|run away|ran away|'
                             r'fall off|fell off|are taken|were taken|die|died|swim away|swam away|join|joined|arrive|arrived|come|came|land|landed)', lower[m.end():]):
            k = number(e[1])
            if k is None:
                continue
            gone = not re.match(r'join|arriv|come|came|land', e[2])
            total += -k if gone else k
            steps.append(f'{show(k)} {e[2]}: {"−" if gone else "+"}{show(k)} → {show(total)}.')
        if len(steps) > 1 and total >= 0:
            return out(f'**{show(total)}** {things} {"are" if total != 1 else "is"} left.', 'word-problem', steps)
    # "A and B cost 1.10 in total. A costs 1.00 more than B. How much is B?"
    m = re.search(r'(?:an?\s+|the\s+)?(\w+) and (?:an?\s+|the\s+)?(\w+) cost\s+\$?(\d+(?:\.\d+)?)\s*(?:\w+\s+)?in total', lower)
    d = re.search(r'(?:the\s+)?(\w+) costs?\s+\$?(\d+(?:\.\d+)?)\s*(?:\w+\s+)?more than (?:the\s+)?(\w+)', lower)
    if m and d:
        total, diff = Fraction(m[3]), Fraction(d[2])
        cheap = (total - diff) / 2
        dear = cheap + diff
        names = {d[3]: cheap, d[1]: dear}
        asked = re.search(r'how much (?:is|does) (?:the\s+)?(\w+)', lower)
        target = asked[1] if asked and asked[1] in names else d[3]
        return out(f'The {target} costs **{show(names[target])}**.', 'word-problem',
                   [f'Call the {d[3]} x. Then the {d[1]} is x + {show(diff)}.', f'x + (x + {show(diff)}) = {show(total)}, so 2x = {show(total - diff)} and x = {show(cheap)}.',
                    f'Check: {show(cheap)} + {show(dear)} = {show(total)}, and {show(dear)} − {show(cheap)} = {show(diff)}.'])
    return None


def clock(text):
    lower = text.lower()
    m = re.search(r'\b(?:leaves?|starts?|begins?|departs?|left|started)\s+at\s+(\d{1,2})(?::(\d\d))?\s*(am|pm|a\.m\.|p\.m\.)?', lower)
    d = re.search(r'\b(?:takes?|lasts?|took|lasted|for)\s+(\d+(?:\.\d+)?|\w+)\s+(hours?|minutes?|mins?)(?:\s+and\s+(\d+)\s+minutes?)?', lower)
    if not (m and d and re.search(r'\b(?:when|what time)\b', lower)):
        return None
    hour, minute = int(m[1]), int(m[2] or 0)
    half = (m[3] or '').replace('.', '')
    if half == 'pm' and hour != 12:
        hour += 12
    if half == 'am' and hour == 12:
        hour = 0
    amount = number(d[1])
    if amount is None:
        return None
    minutes = int(amount * 60) if d[2].startswith('hour') else int(amount)
    minutes += int(d[3] or 0)
    start = datetime(2000, 1, 1, hour, minute)
    end = start + timedelta(minutes=minutes)
    fmt = (lambda t: t.strftime('%I:%M %p').lstrip('0')) if half else (lambda t: t.strftime('%H:%M'))
    nextday = ' the next day' if end.day != start.day else ''
    verb = re.search(r'(?i)\bwhen (?:does|will|did) (?:it|the \w+|they|we|he|she) (\w+)', text)
    verb = verb[1].lower() if verb else 'arrive'
    said = {'end': 'ends', 'finish': 'finishes', 'stop': 'stops', 'arrive': 'arrives', 'get': 'gets there', 'land': 'lands',
            'close': 'closes'}.get(verb, verb + 's')
    return out(f'It {said} at **{fmt(end)}**{nextday}.', 'time', [f'{fmt(start)} + {minutes // 60} h {minutes % 60:02d} min = {fmt(end)}{nextday}.'])


def weekday(text):
    lower = text.lower()
    m = re.search(r'\b(?:today is|if today is|it is)\s+(' + '|'.join(DAYS) + r')\b', lower)
    n = re.search(r'\b(?:in|after)\s+(\d+|\w+)\s+days?\b|\b(\d+|\w+)\s+days?\s+(?:from now|later|ago|before)\b|\b(tomorrow|yesterday|the day after tomorrow|the day before yesterday)\b', lower[m.end():] if m else '')
    if not (m and n):
        return None
    start = DAYS.index(m[1])
    if n[3]:
        shift = {'tomorrow': 1, 'yesterday': -1, 'the day after tomorrow': 2, 'the day before yesterday': -2}[n[3]]
    else:
        amount = number(n[1] or n[2])
        if amount is None:
            return None
        shift = int(amount) * (-1 if re.search(r'\bago\b|\bbefore\b', n[0]) else 1)
    day = DAYS[(start + shift) % 7]
    return out(f'It is **{day.capitalize()}**.', 'time', [f'{m[1].capitalize()} {"+" if shift >= 0 else "−"} {abs(shift)} days; '
                                                          f'every 7 days the week repeats, so count {abs(shift) % 7} day(s) {"forward" if shift >= 0 else "back"}.'])


def equation(text):
    """'If x + 4 = 10, what is x?' -> the linear-equation helper."""
    m = re.search(r'(?i)\b(?:if|given|suppose)\s+([\d\sa-z+*/().\-]*=[\d\sa-z+*/().\-]+?)\s*,?\s*(?:what is|find|solve for|then what is)\s+([a-z])\b', text)
    if not m or len(set(re.findall(r'[a-z]', m[1]))) != 1:
        return None
    from .helper_chat import linear
    answer = linear(m[1], explain=True)
    return answer if answer and answer['route'] == 'helper/equation' else None


# ---------------------------------------------------------------- analogies and common sense

def analogy(text):
    m = re.match(r'(?i)^\s*(?:an?\s+)?(\w+)\s+is\s+to\s+(?:an?\s+)?(\w+)\s+as\s+(?:an?\s+)?(\w+)\s+is\s+to\s+(?:what|\?|_+|which word)\s*\??\s*$', text)
    if not m:
        return None
    from . import dictionary as dic
    a, b, c = m[1].lower(), m[2].lower(), m[3].lower()

    def opposite(word):
        found, base = dic.senses(word)
        return [y for row in found for x, y in row[4] if x.lower() == base]

    if b in opposite(a):
        options = opposite(c)
        if options:
            return out(f'**{options[0]}**: {b} is the opposite of {a}, and {options[0]} is the opposite of {c}.', 'analogy')
    if b == dic.plural(a)['response'].split('**')[3]:
        return out(f'**{dic.plural(c)["response"].split("**")[3]}**: {b} is the plural of {a}.', 'analogy')
    if a in dic.IRREGULAR and b in dic.IRREGULAR[a][0]:
        if c in dic.IRREGULAR:
            return out(f'**{dic.IRREGULAR[c][0]}**: {b} is the past tense of {a}.', 'analogy')
    # Specific relations first (young animals, homes), then the general "is a kind of".
    YOUNG = {'dog': 'puppy', 'cat': 'kitten', 'cow': 'calf', 'horse': 'foal', 'sheep': 'lamb', 'pig': 'piglet', 'duck': 'duckling',
             'goat': 'kid', 'bear': 'cub', 'lion': 'cub', 'frog': 'tadpole', 'chicken': 'chick', 'hen': 'chick', 'deer': 'fawn', 'swan': 'cygnet'}
    if YOUNG.get(a) == b and c in YOUNG:
        return out(f'**{YOUNG[c]}**: a young {a} is a {b}, and a young {c} is a {YOUNG[c]}.', 'analogy')
    grown = {v: k for k, v in YOUNG.items()}
    if grown.get(a) == b and c in grown:
        return out(f'**{grown[c]}**: a {a} grows up to be a {b}, and a {c} grows up to be a {grown[c]}.', 'analogy')
    HOME = {'bird': 'nest', 'bee': 'hive', 'dog': 'kennel', 'horse': 'stable', 'pig': 'sty', 'rabbit': 'burrow', 'spider': 'web',
            'fish': 'water', 'lion': 'den', 'cow': 'barn', 'person': 'house', 'ant': 'anthill', 'fox': 'den'}
    if HOME.get(a) == b and c in HOME:
        return out(f'**{HOME[c]}**: a {a} lives in a {b}, and a {c} lives in a {HOME[c]}.', 'analogy')
    found_a, _ = dic.senses(a, 'noun')
    if found_a and any(b in [w.lower() for w in row[5]] for row in found_a[:3]):
        found_c, _ = dic.senses(c, 'noun')
        if found_c and found_c[0][5]:
            return out(f'**{found_c[0][5][0]}**: a {a} is a kind of {b}, and a {c} is a kind of {found_c[0][5][0]}.', 'analogy')
    return None


ABILITIES = {  # thing: (can, cannot)
    'fish': ('swim, breathe underwater with gills', 'climb trees, walk, fly, breathe air for long'),
    'bird': ('fly (most kinds), lay eggs, sing', 'swim underwater for long (most kinds)'),
    'penguin': ('swim very well, dive', 'fly'), 'ostrich': ('run very fast', 'fly'), 'chicken': ('flap and hop short distances', 'fly far'),
    'dog': ('run, swim, bark, smell very well', 'climb trees, fly, talk'), 'cat': ('climb trees, jump high, see in dim light', 'fly'),
    'elephant': ('swim, remember well, use its trunk', 'jump'), 'snake': ('swim, climb', 'walk, hear the way we do'),
    'human': ('walk, run, swim, climb, talk', 'fly unaided, breathe underwater'), 'person': ('walk, run, swim, climb, talk', 'fly unaided, breathe underwater'),
    'monkey': ('climb trees, swing', 'fly'), 'horse': ('run fast, sleep standing up', 'vomit, climb trees'), 'cow': ('walk upstairs', 'walk down stairs easily'),
    'frog': ('jump, swim, breathe through its skin', 'fly'), 'bat': ('fly, find things by echo', 'see colours well'),
    'whale': ('swim, hold its breath for a long time', 'breathe underwater, walk'), 'dolphin': ('swim, use echolocation', 'breathe underwater'),
    'kangaroo': ('hop, jump far', 'walk backwards'), 'turtle': ('swim, hide in its shell', 'run fast'), 'rabbit': ('hop, dig', 'climb trees'),
    'squirrel': ('climb trees, jump between branches', 'fly'), 'spider': ('spin webs, climb walls', 'fly'),
    'car': ('drive on roads', 'fly, float'), 'plane': ('fly', 'float for long'), 'boat': ('float, sail', 'fly'),
}
CAUSES = [
    (r'\bdrop(?:ped|s)?\b.*\bglass\b.*\b(?:hard|stone|tile|concrete)?\s*floor|\bglass\b.*\bdrop', 'It will most likely break or shatter: glass is brittle, so a hard impact cracks it instead of bending it.'),
    (r'\bdrop(?:ped|s)?\b.*\begg\b', 'The egg will most likely crack and break: its shell is thin and brittle.'),
    (r'\bice\b.*\b(?:sun|warm|heat|hot)\b|\bleave ice\b', 'The ice melts into water, because warmth raises it above 0 °C (its melting point).'),
    (r'\bwater\b.*\b(?:freez|below zero|0 ?°?c)\b|\bput water in the freezer\b', 'The water freezes into ice below 0 °C (32 °F).'),
    (r'\bboil(?:ing)? water\b|\bwater\b.*\b100\b', 'Water boils at 100 °C at sea level and turns into steam.'),
    (r'\bplant\b.*\b(?:no|without)\b.*\b(?:water|light|sun)', 'It will wilt and eventually die: plants need water and light to make food (photosynthesis).'),
    (r'\bdon\'?t sleep\b|\bwithout sleep\b|\bno sleep\b', 'You get tired, slower and less focused; the body and brain need sleep to recover.'),
    (r'\bmix\b.*\bred\b.*\bblue\b|\bred and blue\b.*\bmix', 'Red and blue make purple.'),
    (r'\bmix\b.*\bblue\b.*\byellow\b|\byellow and blue\b|\bblue and yellow\b', 'Blue and yellow make green.'),
    (r'\bmix\b.*\bred\b.*\byellow\b|\bred and yellow\b', 'Red and yellow make orange.'),
    (r'\bwhy do we wear coats\b|\bwhy wear (?:a )?coat\b|\bcoats? in winter\b', 'To stay warm: winter air is cold, and a coat traps a layer of warm air next to the body so we lose heat more slowly.'),
    (r'\bwhy (?:do|does) (?:it|ice) (?:float|floats)\b|\bwhy does ice float\b', 'Ice is less dense than liquid water (water expands when it freezes), so it floats.'),
    (r'\bwhy is the sea salty\b|\bwhy is the ocean salty\b', 'Rivers carry dissolved minerals from rocks into the sea; when sea water evaporates the salt stays behind, so it builds up.'),
    (r'\bwhy do (?:we|people) sweat\b', 'To cool down: sweat evaporates from the skin and takes heat with it.'),
    (r'\bwhy do leaves (?:change colou?r|turn)\b|\bleaves .*\bautumn\b', 'In autumn trees stop making green chlorophyll, so the yellow and orange colours already in the leaves show through.'),
    (r'\bwhy do we need (?:to )?(?:eat|food)\b', 'Food gives the body energy and the materials it needs to grow and repair itself.'),
    (r'\bwhy do (?:we|people) need water\b|\bwhy drink water\b', 'Our bodies are mostly water; we need it to carry nutrients, keep our temperature steady and remove waste.'),
    (r'\bwhy (?:do|does) (?:things|objects|an apple|apples) fall\b', 'Gravity: the Earth pulls everything towards its centre.'),
    (r'\bwhy is (?:it|the sky) dark at night\b', 'At night your side of the Earth faces away from the Sun, so no sunlight reaches you.'),
    (r'\bwhy do we have seasons\b', 'The Earth\'s axis is tilted, so through the year each half of the planet leans towards or away from the Sun.'),
    (r'\bwhat happens (?:if|when) you (?:touch|put your hand on) (?:a )?(?:hot )?(?:stove|fire)\b', 'You get burned, so you pull your hand away quickly: it is far hotter than skin can stand.'),
    (r'\bwhy do (?:we|people) brush (?:our|their) teeth\b', 'To remove food and bacteria that cause tooth decay and gum disease.'),
    (r'\bwhy do birds migrate\b', 'To find food and better weather: many birds fly to warmer places when winter makes food scarce.'),
]
TRICKS = [
    (r'\b(?:a |one )?(kilo|kilogram|pound|ton|tonne|gram|kg|lb)s? of (\w+)\b.*\bor\b.*\b(?:a |one )?\1s? of (\w+)', lambda m: (
        f'They weigh the same: a {m[1]} of {m[2]} and a {m[1]} of {m[3]} are both one {m[1]}. The {m[2]} just take{"" if m[2].endswith("s") else "s"} up more room.')),
    (r'\bhow many months have 28 days\b', lambda m: 'All 12 of them: every month has at least 28 days.'),
    (r'\bwhat weighs more\b.*\b(?:pound|kilo)\b.*\b(?:pound|kilo)\b', lambda m: 'They weigh the same: the amounts are equal.'),
]


def common_sense(text):
    lower = text.lower().strip()
    for pattern, answer in TRICKS:
        m = re.search(pattern, lower)
        if m:
            return out(answer(m), 'common-sense')
    for pattern, answer in CAUSES:
        if re.search(pattern, lower):
            return out(answer, 'common-sense')
    m = re.match(r'(?i)^can\s+((?:a|an|the)\s+)?(\w+?)(s?)\s+(\w+)(\s+.+?)?\s*\??$', lower)
    if m and m[2] in ABILITIES:
        thing, verb, rest = m[2], m[4], (m[5] or '').strip()
        subject = f'{(m[1] or "").strip() or "a"} {thing}' if not m[3] else f'{thing}s'
        subject = subject[0].upper() + subject[1:]
        action = f'{verb} {rest}'.strip()
        can, cannot = ABILITIES[thing]
        if re.search(r'\b' + verb + r'\b', cannot):
            return out(f'No. {subject} cannot {action}. {article(thing).capitalize()} can {can}.', 'common-sense')
        if re.search(r'\b' + verb + r'\b', can):
            return out(f'Yes. {subject} can {action}.', 'common-sense')
    return None


def sequence_short(text):
    """'2, 4, 8, 16': constant ratio or difference, checked on every step before predicting the next number."""
    m = re.search(r'((?:-?\d+\s*,\s*){2,}-?\d+)', text)
    if not m or not re.search(r'(?i)next|comes|continue|follows|\?|\.\.\.|…', text):
        return None
    numbers = [Fraction(x) for x in re.findall(r'-?\d+', m[1])]
    if len(numbers) < 3:
        return None
    diffs = [b - a for a, b in zip(numbers, numbers[1:])]
    if len(set(diffs)) == 1:
        return out(f'The next number is **{show(numbers[-1] + diffs[0])}**.', 'sequence', [f'Each number is {show(diffs[0])} more than the one before.'])
    if all(n != 0 for n in numbers[:-1]):
        ratios = [b / a for a, b in zip(numbers, numbers[1:])]
        if len(set(ratios)) == 1:
            return out(f'The next number is **{show(numbers[-1] * ratios[0])}**.', 'sequence', [f'Each number is {show(ratios[0])} times the one before.'])
    return None


def reply(text):
    if len(text) > 1500:
        return None
    for solver in (fallacy, categorical, comparison, conditional, equation, word_problem, clock, weekday, analogy, common_sense):
        try:
            answer = solver(text)
        except (ValueError, ZeroDivisionError, IndexError, KeyError):
            answer = None
        if answer:
            return answer
    return None
