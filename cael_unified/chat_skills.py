"""Small exact skills read from the conversation itself (no web, no model): word problems with quantities and rates,
clock times with delays, syllogisms, weekly schedules with cancellations, values the user changed, short notes and
their rewrites, multi-part recall, and replies to feelings and plans.

Each skill reads the whole conversation (so follow-ups such as "And if I buy two of them?" or "It's delayed by 20
minutes" re-use the earlier facts) and answers only when it understood every part it needs; otherwise it returns None
and the other routes answer as before.
"""
import math
import re

NUM_WORDS = {'zero': 0, 'one': 1, 'a': 1, 'an': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8,
             'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12, 'fifteen': 15, 'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50,
             'half': 0.5, 'a dozen': 12, 'dozen': 12}
NUM = r'(\d+(?:[.,]\d+)?|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|fifty)'
DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
DAY = r'(?:mon|tues|wednes|thurs|fri|satur|sun)days?'


def num(s):
    s = s.lower().strip()
    if s in NUM_WORDS:
        return NUM_WORDS[s]
    return float(s.replace(',', '.')) if re.search(r'[.,]\d', s) else int(s)


def fmt(x):
    if isinstance(x, float):
        x = round(x, 2)
        return str(int(x)) if x == int(x) else f'{x:g}'
    return str(x)


def user_turns(messages):
    return [m['content'] for m in messages if m.get('role') == 'user' and isinstance(m.get('content'), str)]


def last_reply(messages):
    return next((m.get('content') or '' for m in reversed(messages[:-1]) if m.get('role') == 'assistant'), '')


def you(s):
    swaps = {'i': 'you', 'me': 'you', 'my': 'your', 'mine': 'yours', 'myself': 'yourself', 'am': 'are', "i'm": "you're",
             "i've": "you've", "i'll": "you'll", "i'd": "you'd", 'we': 'you', 'our': 'your', 'us': 'you', "we're": "you're"}
    out = re.sub(r"(?i)\b(i'm|i've|i'll|i'd|we're|i|me|my|mine|myself|am|we|our|us)\b",
                 lambda m: swaps[m[1].lower()], s)
    return re.sub(r'\byou was\b', 'you were', out)


def sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', text) if s.strip()]


def answer(route, text, kind=''):
    return dict(route='chat/skill-' + route, response=text, sources=[],
                details='Exact skill over the conversation (chat_skills.py)' + (f': {kind}' if kind else '') + '.')


# ----------------------------------------------------------------------------------------------- 1. quantities

OWNER = r"((?:box|bag|basket|jar|team|class|shelf|room|bucket|crate|bowl|tank|group|pile) [A-Z0-9]\b|(?-i:[A-Z][a-z]+)|(?-i:[A-Z])(?= |$|\?|,)|I|we|he|she|they|my \w+)"
HAS = re.compile(r"(?i)\b" + OWNER + r" (?:has|have|had|holds|contains|got|owns|keeps|starts with|started with) " + NUM + r"(?: ([a-z]+))?")
THERE = re.compile(r"(?i)\bthere (?:are|were|is) " + NUM + r" ([a-z]+) in (?:the )?" + OWNER)
MOVE = re.compile(r"(?i)\b(?:i |we |you |(?-i:[A-Z][a-z]+) )?(?:move|moves|moved|put|puts|transfer|transfers|transferred|shift|shifts|take|takes|took)"
                  r" " + NUM + r"(?: ([a-z]+))? (?:out )?(?:from|of|out of) (?:the )?" + OWNER + r" (?:to|into|in|and put them in) (?:the )?" + OWNER)
GIVE = re.compile(r"(?i)\b" + OWNER + r" (?:gives|gave|give|hands|handed|passes|passed|sends|sent) " + NUM + r"(?: ([a-z]+))? to " + OWNER +
                  r"|\b" + OWNER + r" (?:gives|gave|give|hands|handed|passes|passed) " + OWNER + r" " + NUM + r"(?: ([a-z]+))?")
LOSE = re.compile(r"(?i)\b" + OWNER + r" (?:eats|ate|eat|loses|lost|lose|sells|sold|sell|uses|used|use|gives away|gave away|spends|spent|"
                  r"drops|dropped|breaks|broke|throws away|threw away|spend|sell|give away) " + NUM + r"(?: of (?:them|its|his|her|their|the) ?(?:[a-z]+)?| ([a-z]+))?")
GAIN = re.compile(r"(?i)\b" + OWNER + r" (?:buys|bought|buy|gets|got|get|finds|found|find|receives|received|picks|picked|adds|added|add|"
                  r"wins|won) " + NUM + r" (?:more|extra|new|additional)?(?: ([a-z]+))?")
ADD_TO = re.compile(r"(?i)\b(?:i |we |you )?(?:add|adds|added|put|puts) " + NUM + r"(?: more)?(?: ([a-z]+))? (?:in|into|to) (?:the )?" + OWNER)


class Holdings:
    def __init__(self):
        self.count, self.label, self.item, self.steps, self.last, self.mixed = {}, {}, None, [], None, False

    def key(self, owner):
        o = owner.strip()
        low = o.lower()
        letter = re.fullmatch(r'(?:box|bag|basket|jar|team|class|shelf|room|bucket|crate|bowl|tank|group|pile) ([a-z0-9])', low)
        if letter:
            return letter[1]
        if re.fullmatch(r'[a-z0-9]', low):
            return low
        if low in ('he', 'she', 'they') and self.last:
            return self.last
        return {'we': 'i', 'my': 'i'}.get(low, low)

    def known(self, owner):
        return self.key(owner) in self.count

    def set(self, owner, n, item):
        k = self.key(owner)
        self.count[k] = n
        if k != 'i':
            self.last = k
        self.label.setdefault(k, owner if owner not in ('I', 'i', 'we', 'We') else 'you')
        if item and item not in ('of', 'and', 'in', 'on', 'at', 'more', 'each', 'left', 'now'):
            if self.item and item.rstrip('s') != self.item.rstrip('s'):
                self.mixed = True        # "2 goldfish and 4 ducks": different things, not one count
            self.item = self.item or item


def holdings(texts):
    """Every quantity the user stated, in order, with transfers applied (the last turn's "if I move 3 ..." included)."""
    h = Holdings()
    for text in texts:
        for s in re.split(r'(?<=[.!?])\s+|,\s*(?:and|then)\s+|\band then\b|;\s*', text):
            ops = []
            for m in HAS.finditer(s):
                ops.append((m.start(), 'set', m[1], num(m[2]), m[3]))
            for m in THERE.finditer(s):
                ops.append((m.start(), 'set', m[3], num(m[1]), m[2]))
            # "box A has 12 apples and box B has 7": a bare count after "and"
            for m in re.finditer(r"(?i)\band " + OWNER + r" (?:has|have|had|holds|contains) " + NUM + r"\b(?! [a-z]+)", s):
                pass
            for m in MOVE.finditer(s):
                ops.append((m.start(), 'move', m[3], m[4], num(m[1])))
            for m in GIVE.finditer(s):
                if m[1]:
                    ops.append((m.start(), 'move', m[1], m[4], num(m[2])))
                else:
                    ops.append((m.start(), 'move', m[5], m[6], num(m[7])))
            for m in ADD_TO.finditer(s):
                ops.append((m.start(), 'add', m[3], num(m[1])))
            for m in LOSE.finditer(s):
                ops.append((m.start(), 'add', m[1], -num(m[2])))
            for m in GAIN.finditer(s):
                if not HAS.match(s, m.start()):
                    ops.append((m.start(), 'add', m[1], num(m[2])))
            seen = set()
            for op in sorted(ops):
                if op[0] in seen:
                    continue
                seen.add(op[0])
                if op[1] == 'set':
                    if re.match(r'(?i)(?:i|we)$', op[2]) and re.search(r'(?i)\bif\b', s) and h.known(op[2]):
                        continue
                    h.set(op[2], op[3], op[4])
                elif op[1] == 'move':
                    src, dst, n = h.key(op[2]), h.key(op[3]), op[4]
                    if src not in h.count:
                        return None
                    h.count[src] -= n
                    h.count[dst] = h.count.get(dst, 0) + n
                    h.label.setdefault(dst, op[3])
                    h.steps.append(f'{h.label[src]}: {fmt(h.count[src] + n)} − {fmt(n)} = {fmt(h.count[src])}; '
                                   f'{h.label[dst]}: {fmt(h.count[dst] - n)} + {fmt(n)} = {fmt(h.count[dst])}')
                elif op[1] == 'add':
                    k = h.key(op[2])
                    if k not in h.count:
                        continue
                    h.count[k] += op[3]
                    sign = '+' if op[3] >= 0 else '−'
                    h.steps.append(f'{h.label[k]}: {fmt(h.count[k] - op[3])} {sign} {fmt(abs(op[3]))} = {fmt(h.count[k])}')
    return h


def cap(s):
    return s[0].upper() + s[1:] if s else s


def quantities(messages):
    turns = user_turns(messages)
    q = turns[-1]
    ask = sentences(q)[-1]
    if not re.search(r'(?i)\bhow (?:many|much)\b', ask) or re.search(r'(?i)\b(?:should|do you think|would you|ideal|good number|recommend)\b', ask):
        return None
    start = max((i for i, t in enumerate(turns) if HAS.search(t) or THERE.search(t)), default=None)
    if start is None:
        return None
    first = min(i for i, t in enumerate(turns) if HAS.search(t) or THERE.search(t))
    if not any(re.search(r'\d|\b(?:one|two|three|four|five|six|seven|eight|nine|ten)\b', t) for t in turns[first:]):
        return None
    h = holdings(turns[first:])
    if h is None or not h.count or h.mixed or any(v < 0 for v in h.count.values()):
        return None
    item = h.item or 'of them'
    item_m = re.search(r'(?i)\bhow (?:many|much) (?:more |fewer |less )?([a-z]+)( and [a-z]+)?', ask)
    if item_m and item_m[1].lower() not in ('more', 'fewer', 'less', 'are', 'is', 'do', 'does', 'in', 'of', 'left', 'each', 'altogether'):
        if item_m[2] or (h.item and item_m[1].lower().rstrip('s') != h.item.lower().rstrip('s')):
            return None          # "brothers and sisters", or a thing the user never counted
        item = item_m[1].lower()
    label = lambda k: h.label[k]
    if re.search(r'(?i)\bhow (?:many|much) (?:more|fewer|less)\b', ask) and len(h.count) >= 2:
        named = [k for k in h.count if re.search(r'(?i)\b(?:' + re.escape(h.label[k]) + r'|' + re.escape(k) + r')\b', ask)]
        a = named[0] if named else max(h.count, key=h.count.get)
        others = [k for k in h.count if k != a]
        b = named[1] if len(named) > 1 else others[0]
        d = h.count[a] - h.count[b]
        more = re.search(r'(?i)\bmore\b', ask)
        if more and d >= 0 or not more and d <= 0:
            word = 'more' if d >= 0 else 'fewer'
            return answer('quantities', f"{cap(label(a))} has **{fmt(abs(d))}** {word} {item} than {label(b)} "
                                        f"({fmt(h.count[a])} − {fmt(h.count[b])} = {fmt(abs(d))})." if more else
                          f"{cap(label(a))} has **{fmt(abs(d))}** fewer {item} than {label(b)} ({fmt(h.count[b])} − {fmt(h.count[a])} = {fmt(abs(d))}).",
                          'difference')
        return answer('quantities', f"Actually {label(a)} has fewer: {fmt(h.count[a])} against {fmt(h.count[b])}, so {label(b)} has "
                                    f"**{fmt(abs(d))}** more.", 'difference')
    if re.search(r'(?i)\b(?:in total|altogether|all together|together|in all|combined|total)\b', ask):
        total = sum(h.count.values())
        parts = ' + '.join(fmt(v) for v in h.count.values())
        return answer('quantities', f"There are **{fmt(total)}** {item} altogether ({parts} = {fmt(total)}).", 'total')
    if re.search(r'(?i)\b(?:in each|each (?:box|bag|one|have|has)|does each|do they each|both)\b', ask) or len(
            [k for k in h.count if re.search(r'(?i)\b' + re.escape(k) + r'\b', ask)]) >= 2:
        listing = ' and '.join(f"{label(k)} has **{fmt(v)}**" for k, v in h.count.items())
        why = f" ({'; '.join(h.steps[-2:])})" if h.steps else ''
        lead = 'After that, ' if h.steps else ''
        return answer('quantities', f"{lead}{listing}{why}. That's still {fmt(sum(h.count.values()))} {item} in total.", 'each')
    for k in h.count:
        if re.search(r'(?i)\b(?:' + re.escape(h.label[k]) + r'|' + (re.escape(k) if len(k) > 1 else 'box ' + re.escape(k)) + r')\b', ask) or (
                k == 'i' and re.search(r'(?i)\b(?:do i|have i|i have|left)\b', ask) and len(h.count) == 1):
            why = f" ({h.steps[-1]})" if h.steps else ''
            who = 'You have' if k == 'i' else f"{cap(label(k))} has"
            return answer('quantities', f"{who} **{fmt(h.count[k])}** {item}{' left' if re.search(r'(?i)left', ask) else ' now' if h.steps else ''}{why}.",
                          'one')
    return None


# ----------------------------------------------------------------------------------------------- 2. rates

PERIOD = r'(day|week|month|hour|minute|night|evening|weekend|session|lesson)'
RATE = re.compile(r'(?i)' + NUM + r' ([a-z]+(?: [a-z]+)?) (?:a|per|each|every) ' + PERIOD + r'\b')
SPEED = re.compile(r'(?i)(?:at |average )?' + NUM + r' ?(km/h|kph|mph|kilometres per hour|kilometers per hour|miles per hour|km an hour|miles an hour)')


def unit_root(u):
    u = u.lower().split()[-1]
    return u[:-1] if u.endswith('s') and not u.endswith('ss') else u


def rates(messages):
    turns = user_turns(messages)
    q = turns[-1]
    # the problem: the latest turn that states a rate and asks how long / how many periods / how many per period
    idx = None
    for i in range(len(turns) - 1, -1, -1):
        if RATE.search(turns[i]) or SPEED.search(turns[i]) or re.search(r'(?i)\bhow many \w+ (?:a|per|each) ' + PERIOD, turns[i]):
            if re.search(r'(?i)\bhow (?:many|long|much)\b', turns[i]):
                idx = i
                break
    if idx is None:
        return None
    later = turns[idx + 1:]
    if later and not all(re.search(r'(?i)\b(?:what if|if|instead|and if|what about|how about|now)\b', t) for t in later):
        return None
    if later and not re.search(r'(?i)\b(?:what if|instead|and if|what about|how about)\b', q):
        return None
    base = turns[idx]
    # follow-ups replace the rate or the total ("What if I read 30 pages a day instead?", "and if the book has 400 pages?")
    rate_m = RATE.search(base)
    speed_m = SPEED.search(base)
    if speed_m:
        dist = re.search(r'(?i)' + NUM + r' ?(km|kilometres|kilometers|miles|mi)\b(?!/| per| an)', base)
        speed = num(speed_m[1])
        for t in later:
            s2 = SPEED.search(t) or re.search(r'(?i)' + NUM + r' instead', t)
            if s2:
                speed = num(s2[1])
            d2 = re.search(r'(?i)' + NUM + r' ?(km|kilometres|kilometers|miles|mi)\b(?!/| per| an)', t)
            if d2:
                dist = d2
        if not dist or not speed or not re.search(r'(?i)\bhow long\b|\bhow many hours\b|\bwhen\b', base):
            return None
        hours = num(dist[1]) / speed
        h, m = int(hours), round((hours - int(hours)) * 60)
        if m == 60:
            h, m = h + 1, 0
        span = (f"{h} hour{'s' if h != 1 else ''}" if h else '') + (' and ' if h and m else '') + (f'{m} minutes' if m else '')
        return answer('rates', f"It takes **{span}** ({fmt(num(dist[1]))} {dist[2]} ÷ {fmt(speed)} {speed_m[2]} = {fmt(round(hours, 2))} h).", 'speed')
    if not rate_m:
        return None
    rate, unit, period = num(rate_m[1]), rate_m[2], rate_m[3].lower()
    root = unit_root(unit)
    total_re = re.compile(r'(?i)' + NUM + r'[- ](?:' + re.escape(root) + r's?)\b(?! (?:a|per|each|every) )')
    total = None
    for m in total_re.finditer(base):
        if m.start() != rate_m.start():
            total = num(m[1])
    days_m = re.search(r'(?i)\bin ' + NUM + r' ' + PERIOD + r's?\b', base)
    for t in later:
        r2 = RATE.search(t)
        if r2 and unit_root(r2[2]) == root:
            rate = num(r2[1])
        elif r2:
            rate = num(r2[1])
        t2 = [m for m in total_re.finditer(t) if not (r2 and m.start() == r2.start())]
        if t2:
            total = num(t2[-1][1])
        d2 = re.search(r'(?i)\bin ' + NUM + r' ' + PERIOD + r's?\b', t)
        if d2:
            days_m = d2
        if not r2 and not t2 and not d2:
            return None
    ask = sentences(base)[-1]
    if re.search(r'(?i)\bhow many ' + PERIOD + r's?\b|\bhow long\b', ask) and total:
        periods = total / rate
        whole = math.ceil(periods - 1e-9)
        exact = abs(periods - round(periods)) < 1e-9
        tail = '' if exact else f", so the last {period} is a short one"
        lead = 'Then it' if later else 'It'
        return answer('rates', f"{lead} takes **{whole} {period}{'s' if whole != 1 else ''}** ({fmt(total)} ÷ {fmt(rate)} = "
                               f"{fmt(round(periods, 2))}{tail}).", 'periods')
    if re.search(r'(?i)\bhow many [a-z]+ (?:a|per|each) ' + PERIOD, ask) and total and days_m:
        per = total / num(days_m[1])
        need = math.ceil(per - 1e-9)
        return answer('rates', f"About **{need} {unit}** a {days_m[2]} ({fmt(total)} ÷ {fmt(num(days_m[1]))} = {fmt(round(per, 2))}).", 'per')
    if re.search(r'(?i)\bhow (?:many|much)\b', ask) and days_m:
        got = rate * num(days_m[1])
        return answer('rates', f"**{fmt(got)} {unit}** ({fmt(rate)} × {fmt(num(days_m[1]))}).", 'product')
    return None


# ----------------------------------------------------------------------------------------------- 3. price follow-ups

def multiples(messages):
    """'And if I buy two of them?' after a price answer: the same price times the new count."""
    turns = user_turns(messages)
    if len(turns) < 2:
        return None
    q = turns[-1].strip()
    m = re.match(r'(?i)^(?:and |so |ok,? )?(?:what )?(?:if|about|for|with) (?:i |we )?(?:buy|get|order|take|need|want|have)?\s*' + NUM +
                 r'(?: of (?:them|those|these|it)| (?:more|[a-z]+))?\s*(?:instead)?\s*\??$', q)
    if not m:
        return None
    k = num(m[1])
    prev = last_reply(messages)
    vals = re.findall(r'\*\*([\d.,]+)\*\*', prev)
    if len(vals) != 1 or not re.search(r'(?i)\b(?:costs?|price|pay|euros?|dollars?|pounds?|€|\$|£|per|each)\b', turns[-2]):
        return None
    unit = re.search(r'(?i)(euros?|dollars?|pounds?|€|\$|£|francs?|yen|kr|kronor)', turns[-2])
    unit = (unit[1].lower().rstrip('s') + 's') if unit and len(unit[1]) > 1 else (unit[1] if unit else '')
    one = num(vals[0])
    total = one * k
    money = lambda x: (f'{fmt(x)} {unit}' if unit and len(unit) > 1 else f'{unit}{fmt(x)}')
    return answer('quantities', f"For {fmt(k)} you pay **{money(total)}** ({fmt(k)} × {money(one)}).", 'multiple')


# ----------------------------------------------------------------------------------------------- 4. clock times

CLOCK = r'(\d{1,2})(?::|\.|h)(\d{2})\s*(am|pm|a\.m\.|p\.m\.)?|(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)|\b(noon|midday|midnight)\b'


def clock(m, offset=0):
    g = m.groups()[offset:offset + 6]
    if g[5]:
        return 12 * 60 if g[5].lower() in ('noon', 'midday') else 0
    if g[0]:
        h, mi, ap = int(g[0]), int(g[1]), g[2]
    else:
        h, mi, ap = int(g[3]), 0, g[4]
    if ap:
        ap = ap.lower().replace('.', '')
        h = h % 12 + (12 if ap == 'pm' else 0)
    return h * 60 + mi


def show(t, twelve=False):
    t %= 24 * 60
    h, m = divmod(t, 60)
    if twelve:
        return f"{(h % 12) or 12}:{m:02d} {'pm' if h >= 12 else 'am'}"
    return f'{h:02d}:{m:02d}'


def span(text):
    """'2 hours 35 minutes', '2h35', 'an hour and a half', '90 minutes', '1.5 hours' -> minutes (or None)."""
    t = text.lower()
    m = re.search(r'\b' + NUM + r' ?(?:hours?|hrs?|h)\b(?: and)?(?: ' + NUM + r' ?(?:minutes?|mins?|m)\b)?', t)
    half = re.search(r'\b(?:an?|one) hour and a half\b|\b' + NUM + r' and a half hours\b', t)
    if half:
        return (num(half[1]) if half.lastindex and half[1] else 1) * 60 + 30
    if m:
        return round(num(m[1]) * 60 + (num(m[2]) if m[2] else 0))
    m = re.search(r'\b' + NUM + r' ?(?:minutes?|mins?)\b', t)
    if m:
        return round(num(m[1]))
    if re.search(r'\b(?:an|one) hour\b', t):
        return 60
    if re.search(r'\bhalf an hour\b', t):
        return 30
    return None


def times(messages):
    turns = user_turns(messages)
    q = turns[-1]
    start = None
    for i in range(len(turns) - 1, -1, -1):
        if re.search(r'(?i)\b(?:leaves?|leaving|departs?|starts?|begins?|set off|sets off|take off|takes off|board|at)\b', turns[i]) and \
                re.search(CLOCK, turns[i], re.I) and span(re.sub(CLOCK, ' ', turns[i], flags=re.I)) is not None:
            start = i
            break
    if start is None:
        return None
    base = turns[start]
    later = turns[start + 1:]
    if sum(span(re.sub(CLOCK, ' ', s, flags=re.I)) is not None for s in sentences(base)) > 1:
        return None         # chained steps ("bakes 25 minutes; the glaze goes on 10 minutes after"): the reasoning routes
    t0m = re.search(r'(?i)(?:leaves?|leaving|departs?|starts?|begins?|sets? off|takes? off|at)\s+(?:at\s+)?(?:' + CLOCK + ')', base)
    if not t0m:
        return None
    t0 = clock(t0m, 0)
    twelve = bool(re.search(r'(?i)\d\s*(?:am|pm)\b', base))
    rest = base[:t0m.start()] + ' ' + base[t0m.end():]
    dur = span(re.sub(CLOCK, ' ', rest, flags=re.I))
    if dur is None:
        return None
    ask = sentences(q)[-1]
    if not re.search(r'(?i)\b(?:when|what time|arrival|arrive|get there|get in|finish|end|done|over|land)\b', ask):
        return None
    delay, notes = 0, []
    for t in later:
        d = span(t)
        if d is None:
            if not re.search(r'(?i)\bwhen\b|\bwhat time\b|\barrival\b', t):
                return None
            continue
        if re.search(r'(?i)\b(?:delayed|late|later|delay|behind)\b', t):
            delay += d
            notes.append(f'+ {d} min delay')
        elif re.search(r'(?i)\b(?:early|earlier|ahead)\b', t):
            delay -= d
            notes.append(f'− {d} min early')
        elif re.search(r'(?i)\b(?:instead|takes|actually|only)\b', t):
            dur = d
            notes.append('new trip time')
        else:
            return None
    end = t0 + dur + delay
    h, m = divmod(dur, 60)
    trip = (f'{h} h' if h else '') + (f' {m:02d} min' if m and h else f'{m} min' if m else '')
    if not later:
        verb = 'It ends at' if re.search(r'(?i)\b(?:end|finish|over|done)\b', ask) else 'You land at' if re.search(r'(?i)\bland\b', ask) else 'You arrive at'
        return answer('time', f"{verb} **{show(end, twelve)}** ({show(t0, twelve)} + {trip.strip()}).", 'arrival')
    first = t0 + dur
    if delay:
        word = 'delay' if delay > 0 else 'earlier start'
        return answer('time', f"With the {abs(delay)}-minute {word}, the new arrival time is **{show(end, twelve)}** "
                              f"({show(first, twelve)} {'+' if delay > 0 else '−'} {abs(delay)} min).", 'delay')
    return answer('time', f"Then you arrive at **{show(end, twelve)}** ({show(t0, twelve)} + {trip.strip()}).", 'arrival')


# ----------------------------------------------------------------------------------------------- 5. syllogisms

ALL = re.compile(r"(?i)\b(?:all|every|each) (?:of )?(?:my |the |our |your )?([a-z]+(?: (?!(?:in|at|on|from|is|are)\b)[a-z]+)?(?: (?:in|at|on|from) (?:the |my |our )?[a-z]+)?) (live|lives|work|works|are|is|have|has|like|likes|"
                 r"speak|speaks|can|play|plays|go|goes|wear|wears|eat|eats|own|owns|study|studies|drive|drives)\b ([^.?!]*)")
MEMBER = re.compile(r"(?i)\b((?-i:[A-Z][a-z]+)|this \w+|that \w+) is (?:my |a |an |one of (?:my|the) |the |our )?([a-z]+(?: (?!(?:in|at|on|from|is|are)\b)[a-z]+)?(?: (?:in|at|on|from) (?:the |my |our )?[a-z]+)?)\b")
SINGULAR = {'live': 'lives', 'work': 'works', 'are': 'is', 'have': 'has', 'like': 'likes', 'speak': 'speaks', 'can': 'can', 'play': 'plays',
            'go': 'goes', 'wear': 'wears', 'eat': 'eats', 'own': 'owns', 'study': 'studies', 'drive': 'drives', 'is': 'is', 'lives': 'lives',
            'works': 'works', 'has': 'has', 'likes': 'likes'}
BASE = {v: k for k, v in SINGULAR.items() if k != v}


def same_kind(a, b):
    a, b = a.lower(), b.lower()
    sa = a[:-1] if a.endswith('s') else a
    sb = b[:-1] if b.endswith('s') else b
    return sa == sb or sa.rstrip('e') == sb.rstrip('e') or (a.endswith('ies') and a[:-3] + 'y' == b) or (b.endswith('ies') and b[:-3] + 'y' == a)


def syllogism(messages):
    turns = user_turns(messages)
    text = ' '.join(turns)
    rules = [(m[1].lower(), m[2].lower(), m[3].strip()) for m in ALL.finditer(text)]
    said = {m[1].lower(): you(m[0].strip()) for m in ALL.finditer(text)}
    if not rules:
        return None
    q = sentences(turns[-1])[-1]
    owner = lambda s: you(s)
    # converse: "Does everyone who lives in Spain have to be my cousin?"
    conv = re.search(r"(?i)\b(?:does|do|must|is|are|would)\b.*\b(?:everyone|everybody|anyone|anybody|all (?:the )?people|every person|"
                     r"all those|each person|whoever)\b(?: who| that)? (\w+) ?([^?]*?)\b(?:have to be|has to be|need to be|must be|be|is|are)\b"
                     r" (?:my |a |an |one of my )?([a-z]+)", q)
    if conv:
        for cat, verb, obj in rules:
            if same_kind(conv[3], cat) or same_kind(conv[3], cat.split()[-1]):
                clause = said[cat][0].lower() + said[cat][1:]
                who = f"everyone who {SINGULAR.get(BASE.get(verb, verb), verb)} {owner(obj)}".strip()
                return answer('logic', f"No. You said {clause}, but that only works one way: it doesn't mean {who} is your "
                                       f"{cat.rstrip('s') if not cat.endswith('ss') else cat}. Plenty of people {BASE.get(verb, verb)} {owner(obj)} "
                                       f"without being related to you.", 'converse')
    members = [(m[1], m[2].lower(), you(m[0].strip())) for m in MEMBER.finditer(text)]
    for name, kind, told in members:
        for cat, verb, obj in rules:
            if not (same_kind(kind, cat) or same_kind(kind.split()[0], cat.split()[0]) or same_kind(kind.split()[-1], cat.split()[-1])):
                continue
            if name.lower() not in q.lower():
                continue
            sing = SINGULAR.get(BASE.get(verb, verb), verb)
            fact = f"{name} {sing} {owner(obj)}".strip()
            why = f"{said[cat][0].lower() + said[cat][1:]}, and {told}"
            where = re.match(r'(?i)(?:in|at|on|near) (.+)', obj)
            if re.search(r'(?i)^\s*where\b', q) and where:
                return answer('logic', f"{name} {sing} in **{owner(where[1])}**: {why}.", 'member')
            if re.search(r'(?i)^\s*(?:does|is|can|do|has)\b', q):
                return answer('logic', f"Yes: {fact}. That follows because {why}.", 'member')
            if re.search(r'(?i)^\s*what\b', q):
                return answer('logic', f"{fact}: {why}.", 'member')
    return None


# ----------------------------------------------------------------------------------------------- 6. weekly schedule

def day_list(text):
    return [d for d in DAYS if re.search(r'(?i)\b' + d[:-3] + r'days?\b', text) or (d == 'tuesday' and re.search(r'(?i)\btues?\b', text))]


def schedule(messages):
    turns = user_turns(messages)
    q = sentences(turns[-1])[-1]
    if not re.search(r"(?i)\b(?:which|what) days? (?:do|am|have|will) i\b|\bwhat (?:do i have|have i got)\b|\bam i (?:free|busy)\b|"
                     r"\bmy (?:schedule|week|plans)\b|\bdo i have (?:anything|something)\b", q):
        return None
    plan = {}       # day -> {activity: 'on'|'cancelled'|'moved'}
    seen = False
    for t in turns[:-1]:
        for s in re.split(r'(?<=[.!?])\s+', t):
            low = s.lower()
            if re.search(r'\b(?:cancel+ed|called off|not happening|off this week|skipping|won\'t go|no )\b', low):
                for d in day_list(s):
                    for act in list(plan.get(d, {})):
                        if act in low or not re.search(r'[a-z]+ on ' + d[:-3], low):
                            plan[d][act] = 'cancelled'
                continue
            mv = re.search(r'(?i)\b(?:moved|moving|move|shifted|changed|rescheduled)\b.*?\bto (' + DAY + r')', s)
            if mv:
                to = day_list(mv[1])[0]
                for d in day_list(s[:mv.start(1)]):
                    for act in list(plan.get(d, {})):
                        if act in low:
                            plan[d][act] = 'moved'
                            plan.setdefault(to, {})[act] = 'on'
                continue
            for m in re.finditer(r"(?i)\b([a-z][a-z' -]{1,30}?) (?:class(?:es)? |lessons? |practice |training )?(?:on|every) (" + DAY +
                                 r"(?:(?:,\s*|\s+and\s+|\s*&\s*)" + DAY + r")*)", s):
                act = re.sub(r"(?i)^(?:i (?:have|do|go to|go|got|play|attend)|and|also|then|plus|i've got|there's|there is|my) ", '', m[1].strip()).strip()
                act = re.sub(r'(?i)^(?:a|an|the) ', '', act)
                if not act or len(act.split()) > 4 or act.lower() in ('i', 'and', 'it', 'is', 'cancelled'):
                    continue
                for d in day_list(m[2]):
                    plan.setdefault(d, {})[act.lower()] = 'on'
                    seen = True
    if not seen:
        return None
    busy = [(d, [a for a, st in plan[d].items() if st == 'on']) for d in DAYS if d in plan]
    busy = [(d, acts) for d, acts in busy if acts]
    gone = [(d, a) for d in DAYS for a, st in plan.get(d, {}).items() if st == 'cancelled']
    moved = [(d, a) for d in DAYS for a, st in plan.get(d, {}).items() if st == 'moved']
    note = ''
    if gone:
        note = ' ' + ' '.join(f"{d.capitalize()}'s {a} is cancelled" + ('.' if i == len(gone) - 1 else ';') for i, (d, a) in enumerate(gone))
        note = note.replace(';', ',')
        if not re.search(r'(?i)\bcancel', note.split(',')[-1]):
            note += '.'
    if moved:
        note += ' ' + ', '.join(f"{a} moved away from {d.capitalize()}" for d, a in moved) + '.'
    asked_day = day_list(q)
    if asked_day:
        d = asked_day[0]
        acts = dict(busy).get(d, [])
        if acts:
            return answer('schedule', f"On {d.capitalize()} you have {', '.join(acts)}.", 'day')
        why = next((f" ({a} is cancelled)" for dd, a in gone if dd == d), '')
        return answer('schedule', f"Nothing on {d.capitalize()}{why}: you're free.", 'day')
    if re.search(r'(?i)\bfree\b', q):
        free = [d.capitalize() for d in DAYS if d not in dict(busy)]
        return answer('schedule', f"You're free on {', '.join(free[:-1]) + ' and ' + free[-1] if len(free) > 1 else free[0]}.{note}", 'free')
    parts = [f"**{d.capitalize()}** ({' and '.join(a)})" for d, a in busy]
    listing = parts[0] if len(parts) == 1 else ', '.join(parts[:-1]) + ' and ' + parts[-1]
    return answer('schedule', f"This week you have something on {listing}.{note}", 'week')


# ----------------------------------------------------------------------------------------------- 7. values the user changed

SLOT = re.compile(r"(?i)\bmy ([a-z]+(?: [a-z]+){0,2}?) (?:is|was|are) ([A-Z0-9][\w-]*)\b")
CHANGE = re.compile(r"(?i)\b(?:i (?:just |have )?(?:changed|updated|reset|switched) (?:it|that|them|my ([a-z]+(?: [a-z]+)?)) to|it'?s now|"
                    r"it is now|now it'?s|the new one is|new one is|now it is|my new ([a-z]+(?: [a-z]+)?) is) ([A-Z0-9][\w-]*)")


def changed_value(messages):
    turns = user_turns(messages)
    q = sentences(turns[-1])[-1]
    m = re.search(r"(?i)\bwhat(?:'s| is| was) (?:my|the) ([a-z]+(?: [a-z]+){0,2}?)(?: now| again| currently| at the moment)?\s*\??$", q)
    if not m:
        return None
    asked = m[1].lower()
    slots, last_slot = {}, None
    for t in turns[:-1]:
        for s in re.split(r'(?<=[.!?])\s+', t):
            for x in SLOT.finditer(s):
                slots.setdefault(x[1].lower(), []).append((x[2], s))
                last_slot = x[1].lower()
            for x in CHANGE.finditer(s):
                name = (x[1] or x[2] or last_slot or '').lower()
                if name:
                    slots.setdefault(name, []).append((x[3], s))
                    last_slot = name
    key = next((k for k in slots if k == asked or k.split()[-1] == asked.split()[-1]), None)
    if not key or len(slots[key]) < 2:
        return None
    vals = slots[key]
    if re.search(r'(?i)\b(?:before|old|previous|originally|used to)\b', q):
        return answer('memory', f"Before you changed it, your {key} was **{vals[-2][0]}**. Now it's {vals[-1][0]}.", 'old')
    when = re.search(r'(?i)\b(this morning|today|yesterday|last night|earlier|this week)\b', vals[-1][1])
    return answer('memory', f"Your {key} is now **{vals[-1][0]}**. You changed it from {vals[-2][0]}{' ' + when[1] if when else ''}.", 'current')


# ----------------------------------------------------------------------------------------------- 8. short notes

NOTE = re.compile(r"(?i)\b(?:write|draft|compose|make|give me|can you write|help me write)\b.*?\b(?:(one|two|three|four|1|2|3|4)[- ]line |short |quick |little |brief )?"
                  r"(thank[- ]?you|thanks|apology|sorry|birthday|congratulations?|congrats|get[- ]well|good[- ]luck|farewell|goodbye|welcome|invitation)?"
                  r"\s*(?:note|message|card|text|email|e-mail|letter)\b(?:\s+(?:to|for) (?:my |our |the )?([A-Za-z][\w' -]*?))?"
                  r"(?:\s+(?:for|about|on|because|after) (.+?))?\s*[.!?]?$")
TONE = re.compile(r"(?i)\b(?:make it|make that|can you make it|now make it|could you make it|a bit|bit more|more|less|sound)\b.*?\b("
                  r"casual|informal|relaxed|friendly|friendlier|warm|warmer|formal|professional|polite|short|shorter|brief|long|longer|funny|funnier|"
                  r"playful|serious|simple|simpler)\b")

TEMPLATES = {
    'thanks': {
        'neutral': ["{hi}, thank you so much for {reason}.", "It was really kind of you, and I truly appreciate it.",
                    "Please let me know if I can ever return the favour."],
        'casual': ["Hey {name}, thanks a million for {reason}!", "You're a star. I owe you one!", "Coffee's on me next time."],
        'formal': ["Dear {name}, I would like to thank you sincerely for {reason}.", "Your kindness is greatly appreciated.",
                   "Please do not hesitate to let me know if I can ever return the favour."],
        'funny': ["{hi}, thanks for {reason}!", "You're officially my hero (and the plants' too).", "I owe you one, maybe two."],
    },
    'sorry': {
        'neutral': ["{hi}, I'm really sorry {reason}.", "I feel bad about it, and I'll make sure it doesn't happen again.",
                    "Thank you for your patience."],
        'casual': ["Hey {name}, so sorry {reason}!", "My bad, totally. Let me make it up to you soon.", "Drinks on me?"],
        'formal': ["Dear {name}, please accept my sincere apologies {reason}.", "I regret any inconvenience this has caused.",
                   "I will take care that it does not happen again."],
        'funny': ["{hi}, I'm sorry {reason}!", "I've officially been demoted to Very Sorry Person.", "Please forgive me?"],
    },
    'birthday': {
        'neutral': ["Happy birthday, {name}!", "Wishing you a wonderful day and a year full of good things.", "Enjoy every minute of it."],
        'casual': ["Happy birthday, {name}! 🎉", "Hope it's a great one. Have a slice (or three) of cake for me!", "Let's celebrate soon."],
        'formal': ["Dear {name}, warmest wishes on your birthday.", "May the year ahead bring you health, happiness and success.",
                   "With best regards."],
        'funny': ["Happy birthday, {name}!", "Don't worry, you don't look a day over fabulous.", "Eat all the cake."],
    },
    'congrats': {
        'neutral': ["Congratulations, {name}{on}!", "You worked hard for this, and it's so well deserved.", "I'm really happy for you."],
        'casual': ["Congrats, {name}{on}! 🎉", "So well deserved. Let's celebrate soon!", "Proud of you."],
        'formal': ["Dear {name}, my warmest congratulations{on}.", "It is a well-deserved achievement.", "I wish you every success."],
        'funny': ["Congrats, {name}{on}!", "Look at you, being all brilliant.", "Can I have your autograph?"],
    },
    'getwell': {
        'neutral': ["{hi}, I'm sorry to hear you're unwell.", "Wishing you a speedy recovery. Take all the rest you need.",
                    "Thinking of you."],
        'casual': ["Hey {name}, get well soon!", "Rest up, binge some shows, and let me know if you need anything.", "Take care."],
        'formal': ["Dear {name}, I was sorry to hear that you are unwell.", "I wish you a full and speedy recovery.", "Kind regards."],
        'funny': ["{hi}, get well soon!", "Doctor's orders: blankets, tea and zero guilt about napping.", "Take care."],
    },
    'luck': {
        'neutral': ["Good luck{on}, {name}!", "You've prepared well, and I know you'll do great.", "Rooting for you."],
        'casual': ["Good luck{on}, {name}!", "You've totally got this.", "Let me know how it goes!"],
        'formal': ["Dear {name}, I wish you the very best of luck{on}.", "I am confident you will do very well.", "Kind regards."],
        'funny': ["Good luck{on}, {name}!", "Go and show them how it's done.", "(No pressure.)"],
    },
}
KIND = {'thank-you': 'thanks', 'thankyou': 'thanks', 'thank you': 'thanks', 'thanks': 'thanks', 'apology': 'sorry', 'sorry': 'sorry',
        'birthday': 'birthday', 'congratulations': 'congrats', 'congratulation': 'congrats', 'congrats': 'congrats',
        'get-well': 'getwell', 'get well': 'getwell', 'good-luck': 'luck', 'good luck': 'luck'}
LINES = {'one': 1, 'two': 2, 'three': 3, 'four': 4, '1': 1, '2': 2, '3': 3, '4': 4}


def note_request(text):
    m = NOTE.search(text.strip())
    if not m:
        return None
    kind = KIND.get((m[2] or '').lower().replace('-', ' ').replace('thank you', 'thank you'), None) or KIND.get((m[2] or '').lower())
    reason = (m[4] or '').strip().rstrip('.!')
    to = (m[3] or '').strip()
    if not kind:
        if re.search(r'(?i)\bthank', text):
            kind = 'thanks'
        elif re.search(r'(?i)\bsorry|apolog', text):
            kind = 'sorry'
        else:
            return None
    return dict(kind=kind, to=to, reason=reason, lines=LINES.get((m[1] or '').lower()), short=bool(re.search(r'(?i)\b(?:short|quick|brief)\b', text)))


def compose(req, tone):
    to = req['to']
    rel = to.lower()
    caps = re.findall(r'\b[A-Z][a-z]+\b', to)
    name = caps[-1] if caps else (rel if rel else 'there')
    if rel in ('mum', 'mom', 'dad', 'grandma', 'grandpa', 'nan', 'boss', 'neighbour', 'neighbor', 'teacher'):
        name = rel
    hi = f'Hi {name}' if tone != 'formal' else f'Dear {name}'
    reason = req['reason']
    if req['kind'] == 'thanks':
        reason = reason or 'everything'
        reason = re.sub(r'(?i)^(?:for )', '', reason)
    if req['kind'] == 'sorry':
        reason = ('for ' + reason) if reason and not re.match(r'(?i)(?:for|about|that|i)\b', reason) else reason
        reason = reason or 'about what happened'
        if tone == 'formal' and not reason.startswith(('for', 'about')):
            reason = 'that ' + reason
    on = (' on ' + reason) if reason and req['kind'] in ('congrats', 'luck') else ''
    lines = TEMPLATES[req['kind']][tone]
    n = req['lines'] or (2 if req['short'] or tone in ('short',) else 3)
    out = [l.format(name=name, hi=hi, reason=reason, on=on) for l in lines]
    if 'plants' not in reason and req['kind'] == 'thanks' and tone == 'funny':
        out[1] = "You're officially my hero."
    if n == 1:
        return out[0]
    if n == 2:
        return out[0] + '\n' + out[1]
    return '\n'.join(out[:n])


def notes(messages):
    turns = user_turns(messages)
    q = turns[-1].strip()
    req = note_request(q)
    if req:
        text = compose(req, 'neutral')
        return answer('writing', f"Here's a {('two-line ' if req['lines'] == 2 else '')}note you could use:\n\n{text}", 'note')
    tone = TONE.search(q)
    if not tone or len(q.split()) > 12:
        return None
    prev = next((note_request(t) for t in reversed(turns[:-1]) if note_request(t)), None)
    if not prev:
        return None
    word = tone[1].lower()
    mode = {'casual': 'casual', 'informal': 'casual', 'relaxed': 'casual', 'friendly': 'casual', 'friendlier': 'casual', 'warm': 'casual',
            'warmer': 'casual', 'formal': 'formal', 'professional': 'formal', 'polite': 'formal', 'serious': 'formal', 'funny': 'funny',
            'funnier': 'funny', 'playful': 'funny'}.get(word)
    if re.search(r'(?i)\bless (?:formal|serious)\b', q):
        mode = 'casual'
    if re.search(r'(?i)\bless (?:casual|informal)\b', q):
        mode = 'formal'
    if word in ('short', 'shorter', 'brief', 'simple', 'simpler'):
        prev = dict(prev, lines=max(1, (prev['lines'] or 3) - 1))
        mode = 'neutral'
    if word in ('long', 'longer'):
        prev = dict(prev, lines=min(3, (prev['lines'] or 2) + 1))
        mode = 'neutral'
    if not mode:
        return None
    text = compose(prev, mode)
    lead = {'casual': "Here's a more casual version:", 'formal': "Here's a more formal version:", 'funny': "Here's a more playful version:",
            'neutral': "Here's a revised version:"}[mode]
    return answer('writing', f"{lead}\n\n{text}", 'rewrite')


# ----------------------------------------------------------------------------------------------- 9. persona follow-up

WHY = {'season': 'the colours, the crisp air and the excuse for soup and a good book',
       'colour': 'it reminds me of the sea and the night sky', 'color': 'it reminds me of the sea and the night sky',
       'book': 'it is a cosy adventure with a lot of heart', 'novel': 'it is a cosy adventure with a lot of heart',
       'film': 'the animation is beautiful and the story is so imaginative', 'movie': 'the animation is beautiful and the story is so imaginative',
       'food': 'everyone can make it their own', 'drink': "it's comforting at any time of day",
       'animal': 'octopuses solve puzzles, open jars and change colour in a blink', 'game': 'there is always something new to learn in it',
       'city': 'the light, the hills and the old trams', 'country': 'the mix of old traditions and new ideas', 'planet': 'the rings are stunning',
       'subject': 'it makes you feel how big and surprising the universe is', 'music': 'it surprises you every time',
       'song': 'it is pure optimism in three minutes', 'band': 'they kept reinventing themselves', 'number': 'it turns up everywhere, from weekdays to colours of the rainbow',
       'flower': 'they turn to follow the sun', 'sport': 'the drama of a close match', 'place': 'the sound of the waves'}


def persona_why(messages):
    q = user_turns(messages)[-1].strip()
    if not re.match(r"(?i)^(?:and |so |oh,? )?(?:why(?: that one| that| is that| do you like (?:it|that))?|how come|what do you like about (?:it|that)|"
                    r"why do you like (?:it|that)(?: one)?)\s*\??$", q):
        return None
    prev = last_reply(messages)
    m = re.search(r"(?i)my favourite ([\w -]+?)(?: again)?\? I'd say (.+?)\. ", prev)
    if not m:
        return None
    thing, pick = m[1].lower(), m[2]
    why = WHY.get(thing) or WHY.get(thing.split()[-1])
    if not why:
        return None
    return dict(route='chat/persona-why', response=f"Mostly because of {why}. {cap(pick)} just has a mood I really like. "
                                                   f"What about you, which one do you like best?", sources=[],
                details='CAEL persona reason (chat_skills.py), consistent with the favourite given before.')


# ----------------------------------------------------------------------------------------------- 10. recall of a person's details

INTEREST = r"(?:obsessed with|crazy about|mad about|into|loves?|likes?|enjoys?|a (?:big |huge )?fan of|passionate about)"


def person_recall(messages):
    turns = user_turns(messages)
    q = turns[-1]
    m = re.search(r"(?i)\bwhat(?:'s| is) my (\w+)'s name and what (?:is|does) (?:she|he|they) (?:into|like|love|enjoy)", q) or \
        re.search(r"(?i)\bwhat (?:is|does) my (\w+) (?:into|like|love)", q)
    if not m:
        return None
    rel = m[1].lower()
    name, interest, extra = None, None, []
    for t in turns[:-1]:
        n = re.search(r"(?i)\bmy " + rel + r",? ((?-i:[A-Z][a-z]+))", t) or re.search(r"((?-i:[A-Z][a-z]+)) is my " + rel, t)
        if n:
            name = n[1]
        i = re.search(r"(?i)\b(?:she|he|they|" + rel + r"|" + (re.escape(name) if name else 'zzz') + r")(?:'s| is| are|'re)? " + INTEREST + r" ([^.!?]+)", t)
        if i:
            interest = i[1].strip()
        a = re.search(r"(?i)\bturns (\w+)\b([^.!?]*)", t)
        if a:
            extra.append(f"turns {a[1]}{a[2].rstrip()}")
    if not name and not interest:
        return None
    parts = []
    if name:
        parts.append(f"Your {rel} is called **{name}**")
    if interest:
        parts.append(f"{'she' if rel in ('daughter', 'sister', 'mum', 'mom', 'wife', 'girlfriend', 'niece', 'granddaughter') else 'he' if rel in ('son', 'brother', 'dad', 'husband', 'boyfriend', 'nephew', 'grandson') else 'they'}'s really into **{interest}**")
    text = ', and '.join(parts) + '.'
    if extra and name:
        text += f" (And {name} {extra[-1]}.)"
    return dict(route='chat/memory-recall-person', response=text, sources=[], details='Recalled from what the user said (chat_skills.py).')


# ----------------------------------------------------------------------------------------------- 11. feelings and plans

FEEL = re.compile(r"(?i)\b(?:i(?:'m| am| feel| have been|'ve been) (?:really |so |very |quite |a bit |kind of |pretty )?"
                  r"(sad|down|upset|heartbroken|devastated|lonely|anxious|nervous|worried|stressed|scared|gutted|miserable|depressed|"
                  r"overwhelmed|homesick|hurt)|makes me (sad|cry|anxious)|i (?:miss|will miss|'ll miss) )")
SITUATIONS = [
    (r'\b(?:moving|moved|move|relocating|leaving) (?:abroad|away|overseas|to another (?:country|city))\b|\bmoving abroad\b|\bleaving the country\b',
     "I'm sorry. Watching someone close move far away is a real loss, even when you're happy for them, so it makes sense to feel sad.",
     "You still have some time together: you could plan a few things you both love before they go, and talk about how you'll stay in "
     "touch (a regular video call, a shared photo album, a first visit to look forward to). How are you feeling about it today?"),
    (r'\b(?:broke up|break-?up|dumped|split up|divorce|left me)\b',
     "I'm really sorry. A break-up hurts, and it's normal for it to feel heavy for a while.",
     "Be gentle with yourself: lean on friends, keep some routine, and give it time. Do you want to talk about what happened?"),
    (r'\b(?:died|passed away|lost my|death|put down)\b',
     "I'm so sorry for your loss. Grief can be really hard, and there's no right way to feel.",
     "If you'd like to share a favourite memory, I'm here to listen. Is there someone close you can lean on right now?"),
    (r'\b(?:exam|test|interview|presentation|deadline)\b',
     "That sounds stressful, and feeling nervous before something important is completely normal.",
     "Breaking it into small steps and getting a good night's sleep often helps a lot. What part worries you most?"),
    (r'\b(?:lost (?:my )?job|laid off|fired|redundan)\w*',
     "I'm sorry, losing a job is a real shock, and it's okay to feel upset about it.",
     "Take a moment to breathe first. When you're ready, we could think through next steps together. How are you holding up?"),
]
LONG_TIES = re.compile(r"(?i)\b(?:since (?:primary|elementary|high|secondary|middle|nursery) school|since (?:we were|childhood|kids|forever)|"
                       r"for (?:\d+|ten|twenty|thirty|many|so many) years|our whole li(?:fe|ves)|known (?:each other|her|him|them) (?:for|since))")


def feelings(messages):
    turns = user_turns(messages)
    q = turns[-1].strip()
    if '?' in q:
        return None
    if FEEL.search(q):
        for pat, first, second in SITUATIONS:
            if re.search(pat, q, re.I):
                return dict(route='chat/talk-feelings', response=f"{first} {second}", sources=[],
                            details='Feelings named by the user, with the situation they described (chat_skills.py).')
        return None
    # a follow-up detail in an emotional conversation: "We've been friends since primary school."
    earlier = turns[-3:-1]
    sad = next((t for t in reversed(earlier) if FEEL.search(t)), None)
    if sad and len(q.split()) <= 25:
        if LONG_TIES.search(q):
            span = LONG_TIES.search(q)[0]
            return dict(route='chat/talk-feelings', response=f"That's a friendship that goes back a long way ({you(span)}), so of course this "
                                                             f"hits hard. A bond like that doesn't disappear with distance, though: friends who've "
                                                             f"known each other that long usually pick up right where they left off. What do you think "
                                                             f"you'll miss most?", sources=[], details='Follow-up in an emotional conversation (chat_skills.py).')
        return dict(route='chat/talk-feelings', response=f"Thank you for telling me that. It makes sense that {you(turned(q))} makes this "
                                                         f"feel even bigger. I'm here if you want to talk it through. How are you coping?",
                    sources=[], details='Follow-up in an emotional conversation (chat_skills.py).')
    return None


def turned(s):
    s = re.sub(r'^(?:so|well|anyway|actually|also|and|but|oh|ok|okay|yeah|by the way)[,.:!— -]+', '', s.strip(), flags=re.I).rstrip(' .!')
    return s[0].lower() + s[1:] if s and not re.match(r"[A-Z][a-z]+ [A-Z]|I\b", s) else s


def hours_between(a, b):
    """'9 to 7' -> 10 (a working day)."""
    a, b = int(a), int(b)
    return (b + 12 - a) if b <= a else b - a


def plans(messages):
    """A detail the user gives about a plan or a person ("The race is in October in Berlin.", "She's obsessed with dinosaurs.",
    "I also work long hours, usually 9 to 7."): a reply tied to what the conversation is about, instead of "Got it"."""
    turns = user_turns(messages)
    q = turns[-1].strip()
    if '?' in q or len(q.split()) > 30 or re.match(r'(?i)^(?:thanks|thank you|ok|okay|cool|great|bye|good night|yes|no)\b', q):
        return None
    low = q.lower()
    m = re.search(r"(?i)\bmy (daughter|son|niece|nephew|granddaughter|grandson|little sister|little brother|sister|brother),? "
                  r"((?-i:[A-Z][a-z]+)) (?:turns|is turning|will be) (\w+)(?: (next \w+|this \w+|tomorrow|on \w+|in \w+ \w+))?", q)
    if m:
        rel, name, age, when = m[1], m[2], m[3], m[4]
        return talk(f"Happy early birthday to {name}! {cap(age)} is such a fun age. Are you planning a party{' for ' + when if when else ''}, "
                    f"or something smaller?", 'birthday')
    m = re.search(r"(?i)^(?:she|he|they)(?:'s|'re| is| are) (?:totally |completely |really |so |absolutely )?" + INTEREST + r" ([^.!?]+)", q)
    if m:
        thing = m[1].strip()
        party = any(re.search(r'(?i)\b(?:birthday|turns|party)\b', t) for t in turns[:-1])
        if party:
            return talk(f"A {thing.rstrip('s') if thing.endswith('s') and not thing.endswith('ss') else thing} fan! That makes the theme easy: "
                        f"decorations, a cake and a couple of games built around {thing} will make the day feel really special. "
                        f"Would you like some game ideas?", 'interest')
        return talk(f"{cap(thing)}, nice! It's lovely when kids find something they're that excited about. Do you want ideas built around {thing}?", 'interest')
    hours = re.search(r'(?i)\b(?:work|working|job|shift)\b.*?\b(\d{1,2})(?::\d\d)?\s*(?:am)?\s*(?:to|-|until|till)\s*(\d{1,2})(?::\d\d)?', q)
    goal = next((t for t in reversed(turns[:-1]) if re.search(r"(?i)\b(?:thinking (?:of|about)|planning|want to|going to|would like to|considering) "
                                                                 r"(?:adopting|getting|buying|starting|moving|learning|training|doing|taking)\b", t)), None)
    goal_m = re.search(r"(?i)\b(?:thinking (?:of|about)|planning(?: on)?|considering) ((?:adopting|getting|buying|starting|moving|learning|"
                       r"training|doing|taking)[^.!?,]*)", goal) if goal else None
    if hours:
        n = hours_between(hours[1], hours[2])
        tail = f" That's worth keeping in mind for {you(goal_m[1])}." if goal_m else ''
        return talk(f"That's a long day, about {n} hours away from home.{tail} What would you like to know first?", 'hours')
    m = re.search(r"(?i)\b(?:the (race|marathon|wedding|trip|party|concert|exam|interview|match|game|holiday|conference|move)|it) (?:is|'s|will be) "
                  r"(?:on|in|at) ([^.!?]+)", q)
    if m and len(turns) > 1:
        what = m[1] or 'it'
        lead = f"{cap(m[2].strip())}, lovely" if what != 'it' else 'Good to know'
        return talk(f"{lead}! That gives you something to plan around. How are the preparations for the {what} going so far?", 'event')
    m = re.search(r"(?i)\bi(?:'m| am) thinking (?:of|about) ((?:adopting|getting|buying|starting|learning|moving)[^.!?]+)", q)
    if m:
        detail = sentences(q)[1:] if len(sentences(q)) > 1 else []
        noted = f" Good to know that {you(turned(detail[0]))}." if detail else ''
        return talk(f"{cap(you(m[1].strip()))}, exciting!{noted} What would you like to know first?", 'plan')
    return None


def talk(text, kind):
    return dict(route='chat/memory-talk-' + kind, response=text, sources=[],
                details="Reply built from what the user just said and the conversation's topic (chat_skills.py).")


# ----------------------------------------------------------------------------------------------- 12. "I don't have X"

def without(messages):
    """'I don't have any lemon at home.' after advice: the same advice without the missing thing."""
    turns = user_turns(messages)
    if len(turns) < 2:
        return None
    q = turns[-1].strip()
    m = re.search(r"(?i)\b(?:i (?:don't|do not|didn't) have (?:any |a |an )?|i(?:'m| am) out of |i(?:'ve| have) run out of |there(?:'s| is) no |"
                  r"no |i can't (?:use|eat|have) )([a-z]+(?: juice)?)", q)
    if not m or '?' in q or len(q.split()) > 15:
        return None
    thing = m[1].lower().removesuffix(' juice')
    root = thing.rstrip('s')
    prev = last_reply(messages)
    if root not in prev.lower():
        return None
    keep = []
    for part in re.split(r'\n+', prev):
        part = re.sub(r'(?i)(?:,? or |,? and |, )(?:fresh )?' + root + r's?(?: juice)?\b', '', part)
        part = re.sub(r'(?i)\b(?:fresh )?' + root + r's?(?: juice)?(?: or |, | and )', '', part)
        bits = [s for s in re.split(r'(?<=[.!?])\s+', part) if s.strip()]
        bits = [s for s in bits if root not in s.lower()]
        line = ' '.join(bits).strip()
        if line and not re.match(r'(?i)^(?:source|checked|there are (?:two|\d) methods)\b', line):
            keep.append(line[0].upper() + line[1:])
    rest = '\n\n'.join(keep).strip()
    if len(rest.split()) < 8:
        return None
    return dict(route='chat/skill-without', response=f"No problem, you don't need {thing} for this.\n\n{rest}", sources=[],
                details='The previous advice without the item the user does not have (chat_skills.py).')


# ----------------------------------------------------------------------------------------------- hook

# Narrow skills answer before every other route; the general ones (quantities, rates, syllogisms, schedules) only when
# the main routes did not answer from the conversation's own state (CAEL's context reasoner comes first).
EARLY = (multiples, times, changed_value, notes, persona_why, person_recall, feelings, without, plans)
LATE = (rates, quantities, syllogism, schedule)


def respond(messages, late=False):
    try:
        turns = user_turns(messages)
        if not turns:
            return None
        for skill in (LATE if late else EARLY):
            try:
                out = skill(messages)
            except Exception:
                out = None
            if out:
                return out
    except Exception:
        return None
    return None
