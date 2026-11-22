"""Tracking what changes over a conversation (0.4.4 work after release, 2026-11-22). Non-neural.

Three kinds of state, each replayed turn by turn:
- **An ordered list:** "the mild sauce first, then the smoky one"; edits such as "add X at the end", "move X to the
  start", "slide X after Y", "put X before Y", "drop X", "swap X and Y". Asked: which is first / last / in the middle /
  second, or the order now.
- **A status per thing:** "Bev and Ali have paid; Sol hasn't", "Dusting and sweeping are done", then "Bev got a refund",
  "reopen dusting". Words such as done, finished, paid, booked, confirmed set the status; hasn't, not, reopen, undo,
  refund, cancel clear it. Asked: which still have it, or which are still outstanding.
- **A value per person:** "Jo's meal is soup; Ren's is pie", then "Jo and Ren have swapped meals". Asked: whose is soup
  now, or what is Jo's now.
Sentences that mention none of the tracked things are ignored, so side remarks ("the spoons are bamboo") don't matter.
"""
import re

ROUTE = 'chat/state'
STOP = {'The', 'A', 'An', 'I', 'We', 'My', 'Our', 'If', 'Then', 'Put', 'Add', 'Move', 'Slide', 'Which', 'What', 'Who', 'Whose', 'Of', 'For', 'Is',
        'Are', 'It', 'They', 'He', 'She', 'And', 'But', 'So', 'Now', 'Also', 'A', 'Please', 'There', 'This', 'That', 'Those', 'These', 'Ok',
        'Okay', 'Actually', 'Sorry', 'Oh', 'Wait', 'Tomorrow', 'Today', 'Tonight', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
        'Saturday', 'Sunday', 'Swap', 'Drop', 'Remove', 'Reopen', 'Undo', 'Mark', 'Tick', 'Bring', 'Shift', 'Place', 'Let', 'Do', 'Did', 'Has',
        'Have', 'Should', 'Could', 'Can', 'Will', 'Would', 'One', 'Two', 'Three', 'Four', 'Five', 'A', 'Of', 'In', 'On', 'At', 'To', 'By'}
POS = re.compile(r"(?i)\b(?:done|finished|finish(?:ed)?|completed?|paid|pays|booked|confirmed|ticked|sorted|arrived|signed\s+up|checked\s+in|"
                 r"handed\s+in|submitted|ready|packed|sent|returned)\b")
NEG = re.compile(r"(?i)\b(?:hasn't|haven't|has\s+not|have\s+not|isn't|aren't|not|no\s+longer|reopen(?:ed)?|undo|undone|un-?tick(?:ed)?|"
                 r"refund(?:ed)?|cancel(?:led|ed)?|re-?do|redone|withdr[ae]w|withdrawn|unpaid|un-?done|pulled\s+out|backed\s+out|still\s+owes?)\b")


def out(text, kind):
    return dict(route=f'{ROUTE}-{kind}', response=text, sources=[], reasoning=True, details=f'{kind} (state_tracker.py)')


def sentences(turns):
    for t in turns:
        for s in re.split(r'(?<=[.!?;])\s+|\n+', t):
            if s.strip():
                yield s.strip()


def ment(e):
    return re.compile(r'(?i)(?<![\w-])' + re.escape(e) + r"(?:'s)?(?![\w-])")


# ------------------------------------------------------------------ ordered list
def order_items(turns, noun):
    """Items named as 'the X <noun>' or 'the X one', in order of first appearance."""
    got = []
    for t in turns:
        for m in re.finditer(r'(?i)\b(?:the|a|an)\s+([a-z][\w-]*)\s+(?:' + re.escape(noun) + r's?|ones?)\b', t):
            w = m[1].lower()
            if w in ('same', 'other', 'next', 'last', 'first', 'second', 'third', 'middle', 'new', 'one', 'final', 'whole', 'tasting'):
                continue
            if w not in got:
                got.append(w)
    return got


def track_order(turns, items):
    order = []
    for s in sentences(turns):
        if s.endswith('?'):
            continue
        ms = sorted([(m.start(), it) for it in items for m in ment(it).finditer(s)])
        if not ms:
            continue
        names = [it for _, it in ms]
        low = s.lower()
        if not order and len(names) >= 2 and re.search(r'\b(?:first|then|next|followed\s+by|after\s+that|and\s+then)\b', low) \
                and not re.search(r'\b(?:add|move|slide|put|swap|drop|remove|shift|place|bring)\b', low):
            order = list(dict.fromkeys(names))
            continue
        m = re.search(r'\bswap\b|\bswitch\b|\bexchange\b', low)
        if m and len(names) >= 2:
            a, b = names[0], names[1]
            if a in order and b in order:
                i, j = order.index(a), order.index(b)
                order[i], order[j] = b, a
                continue
            return None
        if re.search(r'\b(?:drop|remove|skip|cut|take\s+out|leave\s+out|scrap)\b', low) and len(names) == 1:
            if names[0] in order:
                order.remove(names[0])
                continue
            return None
        x = names[0]
        rest = names[1:]
        where = None
        if re.search(r'\b(?:at\s+the\s+(?:very\s+)?end|to\s+the\s+end|last|at\s+the\s+back|to\s+the\s+back)\b', low):
            where = ('end',)
        if re.search(r'\b(?:at\s+the\s+(?:very\s+)?(?:start|beginning|front)|to\s+the\s+(?:start|beginning|front)|first)\b', low) and order:
            where = ('start',)
        if rest:
            y = rest[0]
            seg = low[low.find(x.lower()):]
            if re.search(r'\b(?:immediately\s+|right\s+|just\s+|directly\s+)?after\b|\bbehind\b|\bfollowing\b', seg):
                where = ('after', y)
            elif re.search(r'\b(?:immediately\s+|right\s+|just\s+|directly\s+)?before\b|\bahead\s+of\b|\bin\s+front\s+of\b', seg):
                where = ('before', y)
        if where is None:
            if re.search(r'\b(?:add|include|put|move|slide|shift|place|bring)\b', low):
                return None
            continue
        if x in order:
            order.remove(x)
        if where[0] == 'end':
            order.append(x)
        elif where[0] == 'start':
            order.insert(0, x)
        else:
            if where[1] not in order:
                return None
            i = order.index(where[1])
            order.insert(i + 1 if where[0] == 'after' else i, x)
    return order


def ask_order(turns, q):
    m = re.search(r'(?i)\bwhich\s+(\w+)\b|\bwhat\s+(\w+)\s+(?:goes|comes|is)\b', q)
    if not m:
        return None
    noun = (m[1] or m[2]).lower()
    if noun in ('one', 'is', 'goes', 'comes', 'two', 'three', 'of'):
        return None
    if noun.endswith('s') and not noun.endswith('ss'):
        noun = noun[:-1]
    items = order_items(turns, noun)
    if len(items) < 2:
        return None
    order = track_order(turns, items)
    if not order or len(order) < 2:
        return None
    n = len(order)
    low = q.lower()
    k = None
    if re.search(r'\bmiddle\b|\bcentre\b|\bcenter\b', low):
        if n % 2 == 0:
            return out(f'**There is no single middle one**: there are {n} now ({", ".join(order)}).', 'order-middle')
        k = n // 2
    elif re.search(r'\bfirst\b|\bstart\b|\bopen', low):
        k = 0
    elif re.search(r'\blast\b|\bend\b|\bfinal\b|\bclose', low):
        k = n - 1
    elif re.search(r'\bsecond\b', low):
        k = 1
    elif re.search(r'\bthird\b', low):
        k = 2
    elif re.search(r'\border\b', low):
        return out(f'**{", ".join(order)}.**', 'order-all')
    if k is None or k >= n:
        return None
    return out(f'**The {order[k]} {noun}.** The order now is ' + ', '.join(order) + '.', 'order')


# ------------------------------------------------------------------ status
def things(turns):
    names = []
    for t in turns:
        for w in re.findall(r'\b([A-Z][a-z]+)\b', t):
            if w not in STOP and w not in names and not w.lower().endswith('ing'):
                names.append(w)
        for w in re.findall(r'(?i)\b([a-z]+ing)\b', t):
            w = w.lower()
            if w in ('nothing', 'something', 'anything', 'everything', 'morning', 'evening', 'thing', 'king', 'ring', 'during', 'tasting', 'bring',
                     'being', 'going', 'trying', 'making', 'doing', 'having', 'getting', 'putting', 'noting', 'ceiling', 'building', 'spring',
                     'string', 'wedding', 'meeting', 'booking', 'pudding', 'filling', 'outstanding', 'missing', 'remaining', 'waiting', 'starting'):
                continue
            if w not in names:
                names.append(w)
    return names


def track_status(turns, ents):
    st = {}
    for s in sentences(turns):
        if s.endswith('?'):
            continue
        ms = [e for e in ents if ment(e).search(s)]
        if not ms:
            continue
        parts = re.split(r'(?i);\s*|,\s*(?:but|while|whereas)\s+|\s+but\s+', s)
        for part in parts:
            pm = [e for e in ents if ment(e).search(part)]
            if not pm:
                continue
            if NEG.search(part):
                for e in pm:
                    st[e] = False
            elif POS.search(part):
                for e in pm:
                    st[e] = True
    return st


def ask_status(turns, q):
    low = q.lower()
    want_off = re.search(r'\b(?:outstanding|unpaid|still\s+(?:owe|to\s+do|left|open|pending|missing)|not\s+(?:yet\s+)?(?:paid|done|finished)|'
                         r"hasn't|haven't|left\s+to|remaining|still\s+need|yet\s+to)\b", low)
    want_on = re.search(r'\b(?:still\s+have|should\s+(?:still\s+)?have|have\s+(?:a|the)|are\s+(?:done|finished|paid)|has\s+paid|have\s+paid|'
                        r'is\s+paid|done|finished|completed|ticked|marked|dots?|ticks?)\b', low)
    if not (want_off or want_on) or not re.search(r'\b(?:which|whose|who)\b', low):
        return None
    ents = things(turns[:-1] + [re.sub(r'[^.!?\n]*\?', ' ', turns[-1])])
    st = track_status(turns, ents)
    if len(st) < 2 or not any(POS.search(t) for t in turns[:-1] + [re.sub(r'[^.!?\n]*\?', ' ', turns[-1])]):
        return None
    if want_off:
        got = [e for e in st if not st[e]]
    else:
        got = [e for e in st if st[e]]
    nm = re.search(r'\b(?:which|whose|the|what)\s+(two|three|four)\b', low)
    if nm and {'two': 2, 'three': 3, 'four': 4}[nm[1]] != len(got):
        return None
    if not got:
        return out('**None of them.** ' + summary(st), 'status-none')
    return out('**' + ' and '.join(cap(e) for e in got) + '.** ' + summary(st), 'status')


def cap(e):
    return e if e[:1].isupper() else e


def summary(st):
    on = [cap(e) for e in st if st[e]]
    off = [cap(e) for e in st if not st[e]]
    bits = []
    if on:
        bits.append('done or paid now: ' + ', '.join(on))
    if off:
        bits.append('not (or no longer): ' + ', '.join(off))
    return 'Replaying every update in order, ' + '; '.join(bits) + '.'


# ------------------------------------------------------------------ values per person, with swaps
def ask_values(turns, q):
    vals = {}
    attr = None
    for s in sentences(turns):
        if s.endswith('?'):
            continue
        for m in re.finditer(r"\b([A-Z][a-z]+)'s\s+(?:(\w+)\s+)?(?:is|was|will\s+be)\s+(?:the\s+|a\s+|an\s+)?([a-z][\w-]*)", s):
            vals[m[1]] = m[3].lower()
            attr = attr or m[2]
        m = re.search(r'\b([A-Z][a-z]+)\s+and\s+([A-Z][a-z]+)\s+(?:have\s+|had\s+)?(?:swapped|switched|traded|exchanged)\b', s)
        if m and m[1] in vals and m[2] in vals:
            vals[m[1]], vals[m[2]] = vals[m[2]], vals[m[1]]
        m = re.search(r"\b([A-Z][a-z]+)\s+(?:now\s+)?(?:wants|is\s+having|has\s+switched\s+to|changed\s+to|switched\s+to)\s+(?:the\s+)?([a-z][\w-]*)", s)
        if m and m[1] in vals:
            vals[m[1]] = m[2].lower()
    if len(vals) < 2:
        return None
    m = re.search(r'(?i)\bwhose\b.*?\b(' + '|'.join(map(re.escape, set(vals.values()))) + r')\b', q)
    if m:
        v = m[1].lower()
        who = [p for p, x in vals.items() if x == v]
        if len(who) == 1:
            return out(f'**{who[0]}\'s.** After the changes: ' + '; '.join(f'{p} has {x}' for p, x in vals.items()) + '.', 'values-whose')
        return None
    m = re.search(r'\bwhat\s+(?:is|does|will)\s+([A-Z][a-z]+)', q)
    if m and m[1] in vals:
        return out(f'**{vals[m[1]].capitalize()}.** After the changes: ' + '; '.join(f'{p} has {x}' for p, x in vals.items()) + '.', 'values-what')
    return None


LEAD = r"(?:(?:for|on|when|at|with|about)\s+[^,:]{1,30},\s*|[^,:]{1,25}:\s*)?"
IMPERATIVE = re.compile(r"(?i)^" + LEAD + r"(?:please\s+|so\s+|then\s+|just\s+|instead,?\s+|ok(?:ay)?,?\s+|actually,?\s+|and\s+)*"
                        r"(leave|ring|knock|call|phone|text|put|use|bring|take|drop|meet|park|send|go|come|wait|deliver|press|buzz|hand|give|set|"
                        r"add|book|tell|ask|pick|collect|turn|lock|feed|water|walk)\b")


def ask_instruction(turns, q):
    """'What instruction should I give the courier now?' -> the latest instruction, plus any later don'ts."""
    if not re.search(r"(?i)\b(?:instruction|instructions|what\s+should\s+(?:i\s+tell|the\s+\w+\s+do|they\s+do)|what\s+do\s+i\s+tell|what\s+(?:should|do)\s+i\s+(?:say|write))\b", q):
        return None
    sents = [s for s in sentences(turns) if not s.endswith('?')]
    imps = [(i, s) for i, s in enumerate(sents) if IMPERATIVE.match(s) or re.search(r'(?i)\binstead\b', s) and re.search(r'(?i)\b(?:knock|ring|call|leave|use|text|meet)\b', s)]
    if len(imps) < 2:
        return None
    i, last = imps[-1]
    donts = [s for s in sents[i + 1:] if re.match(r"(?i)(?:please\s+)?(?:don't|do\s+not|never|avoid)\b", s)]
    first = imps[0][1]
    text = re.sub(r'(?i)^' + LEAD + r'(?:please\s+|so\s+|then\s+|just\s+|okay,?\s+|ok,?\s+|actually,?\s+|and\s+)*', '', last).rstrip('.;, ')
    first = re.sub(r'(?i)^(?:please\s+|so\s+|then\s+|just\s+|actually,?\s+)+', '', first)
    text = text[0].upper() + text[1:]
    reason = [s for s in sents[imps[0][0] + 1:i + 1] if re.search(r"(?i)\b(?:sticks|broken|doesn't\s+work|wakes|out\s+of\s+order|isn't\s+working|jams)\b", s)]
    return out(f'**{text}.**' + (' ' + ' '.join(d.rstrip('.') + '.' for d in donts) if donts else '') +
               f' This replaces the earlier "{first.rstrip(".")}"' + (f', because {reason[0][0].lower() + reason[0][1:].rstrip(".")}' if reason else '') + '.', 'instruction')


CN = r'(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty)'
CNV = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12,
       'fifteen': 15, 'twenty': 20}
PLACE = (r'(?:the|my|our|a)\s+([a-z][a-z0-9-]*(?:\s+(?:shelf|drawer|box|bin|room|floor|table|rack|bay|bag|tray|cupboard|cabinet|shed|pile|basket|'
         r'counter|desk|fridge|freezer|cart|crate|pen|field|tank|pool|jar|bowl|account|wallet|pocket|stack|row|level|deck))?)')


def cnum(w):
    return int(w) if w.isdigit() else CNV[w.lower()]


def named_places(text, names):
    """'Bay A', 'Shelf 3', 'Room 12' -> 'the bay-a' so they read like 'the counter'; names keeps the way back."""
    def sub(m):
        key = f'{m[1].lower()}-{m[2].lower()}'
        names[key] = f'{m[1]} {m[2]}'
        return f'the {key}'
    return re.sub(r'\b(?:the\s+)?([A-Z][a-z]+)\s+([A-Z]|\d{1,3})\b(?![\w-])', sub, text)


def ask_locations(turns, q):
    """'14 apples in the basket and 6 on the counter; moved 4 from the counter into the basket; ate 3 from the basket.'"""
    names = {}
    turns = [named_places(t, names) for t in turns]
    q = named_places(q, names)
    asked = re.findall(r'(?i)\b(?:in|on|at|inside)\s+' + PLACE, q) + re.findall(r'(?i)\band\s+' + PLACE, q)
    if not asked or not re.search(r'(?i)\bhow\s+many\b', q):
        return None
    got = _locations(turns, q, asked)
    if got and names:
        for k, v in names.items():
            got['response'] = re.sub(r'\b(?:the\s+)?' + re.escape(k) + r'\b', v, got['response'])
    return got


def _locations(turns, q, asked):
    where, steps, item = {}, [], None
    for s in sentences(turns):
        if s.endswith('?'):
            continue
        for c in re.split(r'(?i),\s*(?:and\s+)?then\s+|\s+and\s+then\s+|,\s*then\s+|;\s*|\bthen\b', s):
            low = c.lower()
            m = re.search(r'(?i)\b(?:mov(?:e|es|ed|ing)|took|takes?|carried|carr(?:y|ies)|transferr(?:ed|s)|transfers?|shift(?:s|ed)?|put|puts|brings?|brought)\s+' + CN + r'\s+(?:(\w+)\s+)?(?:of\s+them\s+)?from\s+' + PLACE + r'\s+(?:in)?(?:to|into|onto|on)\s+' + PLACE, c)
            if m:
                n, a, b = cnum(m[1]), m[3].lower(), m[4].lower()
                if a not in where:
                    return None
                where[a] -= n
                where[b] = where.get(b, 0) + n
                steps.append(f'{n} from the {a} to the {b}')
                continue
            m = re.search(r'(?i)\b(?:mov(?:e|es|ed|ing)|carried|carr(?:y|ies)|transferr(?:ed|s)|transfers?|shift(?:s|ed)?|brings?|brought)\s+' + CN +
                          r'\s+(?:\w+\s+){0,2}?(?:of\s+them\s+)?(?:in)?(?:to|into|onto)\s+' + PLACE, c)
            if m and where:         # "moves 7 fiction books to the bottom shelf": from the only other place (2026-11-23)
                n, b = cnum(m[1]), m[2].lower()
                others = [p for p in where if p != b]
                if len(others) != 1:
                    return None
                a = others[0]
                where[a] -= n
                where[b] = where.get(b, 0) + n
                steps.append(f'{n} from the {a} to the {b}')
                continue
            m = re.search(r'(?i)\b(?:ate|eats?|eaten|remov(?:e|es|ed)|checks?\s+out|checked\s+out|borrows?|borrowed|withdr(?:aws?|ew)|took\s+out|takes?\s+out|took\s+away|gave\s+away|gives?\s+away|threw\s+away|sold|sells?|used|uses?|lost|loses?|'
                          r'dropped|drops?|loads?|loaded|ships?|shipped|unloads?|unloaded|picks?\s+up|picked\s+up|collects?|collected)\s+' + CN + r'\s+(?:(\w+)\s+)?(?:from|out\s+of|off)\s+' + PLACE, c)
            if m:
                n, a = cnum(m[1]), m[m.re.groups].lower()
                if a not in where:
                    return None
                where[a] -= n
                steps.append(f'{n} taken from the {a}')
                continue
            m = re.search(r'(?i)\b(?:added|add|adds|put\s+another|bought)\s+' + CN + r'\s+(?:more\s+)?(?:(\w+)\s+)?(?:to|in|into|on|onto)\s+' + PLACE, c)
            if m and where:
                n, a = cnum(m[1]), m[3].lower()
                where[a] = where.get(a, 0) + n
                steps.append(f'{n} added to the {a}')
                continue
            got = list(re.finditer(r'(?i)\b' + CN + r'\s+(?:\w+\s+)?(?:(\w+)\s+)?(?:are\s+|were\s+)?(?:in|on|at|inside)\s+' + PLACE, c))
            if got and re.search(r'(?i)\b(?:put|placed|have|has|had|there\s+(?:are|were)|keep|kept|left|set|stored|are|were|is|starts?|started|holds?|held|contains?|begins?|began)\b', c) and not where.keys() & {g[3].lower() for g in got}:
                for g in got:
                    where[g[3].lower()] = cnum(g[1])
                    item = item or g[2]
                steps.append('start: ' + ', '.join(f'{cnum(g[1])} {re.search(r"(?i)\b(in|on|at|inside)\s+\S+\s+" + g[3] + r"\b", g[0])[1].lower()} the {g[3].lower()}' for g in got))
                continue
            if re.search(r'(?i)\b(?:moved?|ate|took|added|removed|gave)\b', c) and re.search(r'\d|\b(?:one|two|three|four|five|six|seven|eight|nine|ten)\b', low):
                return None     # a change we can't read
    if len(where) < 2 or len(steps) < 2:
        return None
    want = [p.lower() for p in asked if p.lower() in where]
    if not want or any(v < 0 for v in where.values()):
        return None
    thing = (item or 'item').lower()
    told = ' '.join(turns) + ' ' + q
    def prep(p):
        m = re.search(r'(?i)\b(in|on|at|inside)\s+(?:the|my|our|a)\s+' + re.escape(p) + r'\b', told)
        return m[1].lower() if m else 'in'
    ans = ' and '.join(f'{where[p]} {prep(p)} the {p}' for p in dict.fromkeys(want))
    return out(f'**{ans[0].upper() + ans[1:]}.** Replaying the moves: ' + '; '.join(steps) + '.', 'locations')


TYPED = {
    'email': (r'\b(?:e-?mail|email\s+address)\b', r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+'),
    'web address': (r'\b(?:website|web\s+address|url|link|site|homepage)\b', r'\bhttps?://\S+|\bwww\.[\w.-]+\.\w+\S*'),
    'phone number': (r'\b(?:phone|mobile|cell|telephone)(?:\s+number)?\b', r'\+?\d[\d\s().-]{6,}\d'),
}


def ask_typed_value(turns, q):
    """'What is my backup contact email?' -> the latest email the user gave, whatever words announced the change."""
    if not re.search(r"(?i)\bwhat(?:'s|\s+is|\s+was)\s+(?:my|our|the)\b|\bwhich\s+\w+\s+(?:is|should)\b", q):
        return None
    for kind, (ask, val) in TYPED.items():
        if not re.search('(?i)' + ask, q):
            continue
        seen = []
        for t in turns[:-1] + [re.sub(r'[^.!?\n]*\?', ' ', turns[-1])]:
            for m in re.finditer(val, t):
                v = m[0].rstrip('.,;:)')
                if re.search(r"(?i)\b(?:not|isn't|wrong|old|no\s+longer|instead\s+of)\s+(?:\w+\s+){0,2}$", t[max(0, m.start() - 30):m.start()]):
                    continue        # "not alex@old.com"
                if v in seen:
                    seen.remove(v)
                seen.append(v)
        if not seen:
            return None
        before = [v for v in seen[:-1]]
        return out(f'**{seen[-1]}.**' + (f' That is the latest {kind} you gave; it replaced {", ".join(before)}.' if before else ''), 'typed-value')
    return None


def ask_possession(turns, q):
    """'Dan gave Maya his spare laptop because hers wouldn't boot' -> Maya has the working one; Maya's own is broken."""
    if not re.search(r'(?i)\bwho\s+has\b|\bwhose\b', q):
        return None
    text = ' '.join(turns)
    m = re.search(r"\b([A-Z][a-z]+)\s+(?:gave|lent|loaned|handed|passed)\s+([A-Z][a-z]+)\s+(?:his|her|their)\s+(?:(spare|old|extra|second|backup|new)\s+)?(\w+)"
                  r"(?:\s+because\s+(hers|his|theirs|her\s+own|his\s+own|their\s+own)\s+(?:wouldn't|won't|didn't|doesn't|wasn't|isn't|had|broke|was\s+broken|died|stopped|"
                  r"crashed|cracked|failed|snapped|split|fell|got|ran\s+out|tore|ripped|leaked|bent)([^.]*))?", text)
    if m and m[5]:
        giver, taker, kind, thing = m[1], m[2], m[3], m[4].lower()
    else:       # "Leo lent his charger to Sara because hers snapped in half"
        m = re.search(r"\b([A-Z][a-z]+)\s+(?:gave|lent|loaned|handed|passed)\s+(?:his|her|their)\s+(?:(spare|old|extra|second|backup|new)\s+)?(\w+)\s+to\s+([A-Z][a-z]+)"
                      r"\s+because\s+(hers|his|theirs|her\s+own|his\s+own|their\s+own)\s+(?:wouldn't|won't|didn't|doesn't|wasn't|isn't|had|broke|was\s+broken|died|"
                      r"stopped|crashed|cracked|failed|snapped|split|fell|got)([^.]*)", text)
        if not m:
            return None
        giver, kind, thing, taker = m[1], m[2], m[3].lower(), m[4]
    if thing not in q.lower():
        return None
    why = re.sub(r'\s+', ' ', m[0].split('because', 1)[1]).strip().rstrip('.')
    verb = re.search(r'\b(gave|lent|loaned|handed|passed)\b', m[0])[1]
    good = re.search(r'(?i)\b(?:has|holds|got)\s+(?:a|the)\s+([a-z-]+)\s+' + re.escape(thing), q)
    bad = re.search(r'(?i)\b' + re.escape(thing) + r'\s+(?:is|was)\s+([a-z-]+)', q)
    good = good[1].lower() if good and good[1].lower() not in ('own', 'other') else 'working'
    bad = bad[1].lower() if bad and bad[1].lower() not in ('the', 'a') else 'broken'
    return out(f'**{taker} has the {good} {thing}** ({giver}\'s {kind + " " if kind else ""}{thing}), and **{taker}\'s own {thing} is the {bad} one**: '
               f'{giver} {verb} it because {why}.', 'possession')


def respond(messages):
    turns = [(m.get('content') or '').strip() for m in messages if m.get('role') == 'user']
    if len(turns) < 1:
        return None
    qs = re.findall(r'[^.!?\n]*\?', turns[-1])
    if not qs:
        return None
    q = qs[-1]
    turns = turns[-8:]
    for fn in (ask_typed_value, ask_locations, ask_possession, ask_instruction, ask_values, ask_order, ask_status):
        try:
            got = fn(turns, q)
        except (ValueError, IndexError):
            got = None
        if got:
            return got
    return None
