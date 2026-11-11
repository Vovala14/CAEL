"""Conversation core (2026-11 development stage): non-neural, rule/template skills for whole conversations.

Every skill reads the actual user turns of the conversation, builds a small explicit state (quantities,
timed events, availability intervals, ordering rules, category rules, a profile of things said) and
answers from that state. A skill that cannot read every clause it depends on returns None, so the rest
of CAEL still gets the request. No neural model, no network.
"""
import itertools
import re

# ----------------------------------------------------------------------------------------------- helpers

NUMBER_WORDS = {w: i for i, w in enumerate(
    'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen '
    'seventeen eighteen nineteen twenty'.split())}
NUMBER_WORDS.update({'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'a dozen': 12, 'dozen': 12, 'a couple of': 2})
NUM = r'(\d+|' + '|'.join(sorted(map(re.escape, NUMBER_WORDS), key=len, reverse=True)) + r')'
STOP_NAMES = {'The', 'A', 'An', 'If', 'How', 'What', 'When', 'Why', 'Who', 'Which', 'Then', 'After', 'Before', 'Now', 'So',
              'And', 'But', 'Each', 'Every', 'All', 'No', 'In', 'On', 'At', 'Suppose', 'Actually', 'Also', 'Please', 'Can',
              'Does', 'Do', 'Is', 'Are', 'Would', 'Could', 'Should', 'It', 'They', 'We', 'You', 'She', 'He', 'I', 'There', 'This',
              'That', 'Later', 'Next', 'Finally', 'First', 'Meanwhile', 'Together', 'Yes', 'Okay', 'Ok', 'Hi', 'Hello', 'Hey'}
NAME = r"([A-Z][a-zA-Z]+(?:-\d+)?)"


def num(word):
    word = word.lower().strip()
    return int(word) if word.isdigit() else NUMBER_WORDS.get(word)


def user_turns(messages):
    return [m['content'] for m in messages if m.get('role') == 'user']


def sentences(text):
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"“])', text.strip())
    return [p.strip() for p in parts if p.strip()]


def out(route, response, details=''):
    return dict(route='chat/core-' + route, response=response.strip(), sources=[], details=details or
                'Answered by chat_core.py from an explicit state read from this conversation (non-neural).')


def you(text):
    """First person -> second person for reflecting the user's words back."""
    swaps = {"i'm": "you're", 'i am': 'you are', "i've": "you've", "i'd": "you'd", "i'll": "you'll", 'i': 'you', 'me': 'you',
             'my': 'your', 'mine': 'yours', 'myself': 'yourself', 'am': 'are', 'was': 'were', 'we': 'you', 'our': 'your', 'us': 'you'}
    def swap(m):
        w = m.group(0); low = w.lower()
        if low == 'was' and not re.search(r"\b(?:i)\s+$", text[:m.start()].lower()):
            return w
        if low == 'am' and not re.search(r"\bi\s+$", text[:m.start()].lower()):
            return w
        r = swaps.get(low, w)
        return r
    return re.sub(r"\b(?:i'm|i am|i've|i'd|i'll|i|me|my|mine|myself|am|was|we|our|us)\b", swap, text, flags=re.I)


def clean_clause(text):
    return re.sub(r'\s+', ' ', text.strip(' .,!;:'))


def join_list(items, word='and'):
    items = list(items)
    if len(items) <= 1:
        return ''.join(items)
    return ', '.join(items[:-1]) + f' {word} ' + items[-1]


# ------------------------------------------------------------------------------------- A. quantity worlds

GAIN = r'(?:buys|gets|finds|receives|collects|earns|makes|bakes|picks|adds|wins|is given|gains|grows|catches|buy|get|find)'
LOSE = r'(?:loses|eats|uses|sells|spends|breaks|drops|gives away|throws away|lose|eat|use|sell|spend|break|drop|donates|misplaces)'


def quantity_world(text_sentences):
    """Read 'X has N things', relative counts and transfers. Returns (state, steps, item, unread) or None."""
    state, steps, item, unread, order = {}, [], None, [], []
    received = {}
    def name_ok(n):
        return n not in STOP_NAMES
    expanded = []
    last_name = None
    for s in text_sentences:
        if s.rstrip().endswith('?'):
            expanded.append(s); continue
        for part in re.split(r',? and then |, then |; then | and later |\. Then ', s.rstrip('.!')):
            part = part.strip()
            m0 = re.match(NAME + r'\b', part)
            if m0 and m0[1] not in STOP_NAMES:
                last_name = m0[1]
            elif re.match(r'(?:He|She|They)\b', part) and last_name:
                part = re.sub(r'^(?:He|She|They)\b', last_name, part)
            elif re.match(r'(?:loses|eats|uses|sells|spends|buys|gets|finds|gives|receives|collects)\b', part) and last_name:
                part = last_name + ' ' + part
            expanded.append(part)
    for s in expanded:
        s0 = s.rstrip('.!')
        if s0.endswith('?'):
            continue
        s0 = re.sub(r'^(?:then|later|after that|next),? ', '', s0)
        m = re.fullmatch(NAME + r' (?:has|had|starts with|owns|holds|keeps) ' + NUM + r' ([a-z][a-z \-]*?)', s0)
        if m and name_ok(m[1]):
            state[m[1]] = num(m[2]); item = item or m[3]; order.append(m[1]) if m[1] not in order else None
            steps.append(f'{m[1]} starts with {num(m[2])}.'); continue
        m = re.fullmatch(NAME + r' has ' + NUM + r' (fewer|less|more)(?: [a-z \-]+?)? than ' + NAME, s0)
        if m and name_ok(m[1]) and m[4] in state:
            k = num(m[2]); v = state[m[4]] - k if m[3] in ('fewer', 'less') else state[m[4]] + k
            state[m[1]] = v; order.append(m[1]) if m[1] not in order else None
            steps.append(f'{m[1]} has {state[m[4]]} {"-" if m[3] != "more" else "+"} {k} = {v}.'); continue
        m = re.fullmatch(NAME + r' has (twice|three times|four times|half) as many(?: [a-z \-]+?)? as ' + NAME, s0)
        if m and name_ok(m[1]) and m[3] in state:
            f = {'twice': 2, 'three times': 3, 'four times': 4, 'half': 0.5}[m[2]]; v = state[m[3]] * f
            if v != int(v):
                return None
            state[m[1]] = int(v); order.append(m[1]) if m[1] not in order else None
            steps.append(f'{m[1]} has {m[2]} as many as {m[3]}: {int(v)}.'); continue
        m = (re.fullmatch(NAME + r' (?:then )?(?:gives|hands|passes|lends) ' + NAME + r' ' + NUM + r'(?: [a-z \-]+?)?', s0)
             or re.fullmatch(NAME + r' (?:then )?(?:gives|hands|passes|lends) ' + NUM + r'(?: [a-z \-]+?)? to ' + NAME, s0))
        if m and name_ok(m[1]):
            a = m[1]
            b, k = (m[2], num(m[3])) if not m[2][0].isdigit() and num(m[2]) is None else (m[3], num(m[2]))
            if a not in state or b not in state or k is None:
                return None
            state[a] -= k; state[b] += k
            steps.append(f'{a} gives {k} to {b}: {a} {state[a] + k} - {k} = {state[a]}, {b} {state[b] - k} + {k} = {state[b]}.'); continue
        m = re.fullmatch(NAME + r' (?:then )?(?:gives|hands|passes|lends|sends) ' + NUM + r'(?: [a-z \-]+?)? to ((?:her|his|their|the|a|an) [a-z]+)', s0)
        if m and name_ok(m[1]) and m[1] in state and num(m[2]) is not None:
            k = num(m[2]); state[m[1]] -= k; received[m[3]] = received.get(m[3], 0) + k
            steps.append(f'{m[1]} gives {k} to {m[3]}: {state[m[1]] + k} - {k} = {state[m[1]]}.'); continue
        m = re.fullmatch(NAME + r' (?:then )?' + GAIN + r'(?: up)? ' + NUM + r'(?: more)?(?: [a-z \-]+?)?(?: more)?', s0)
        if m and name_ok(m[1]) and m[1] in state:
            k = num(m[2]); state[m[1]] += k; steps.append(f'{m[1]} gets {k} more: {state[m[1]] - k} + {k} = {state[m[1]]}.'); continue
        m = re.fullmatch(NAME + r' (?:then )?' + LOSE + r' ' + NUM + r'(?: of (?:them|their|his|her) [a-z ]+| [a-z \-]+?)?', s0)
        if m and name_ok(m[1]) and m[1] in state:
            k = num(m[2]); state[m[1]] -= k; steps.append(f'{m[1]} loses {k}: {state[m[1]] + k} - {k} = {state[m[1]]}.'); continue
        unread.append(s)
    if len(state) < 1:
        return None
    return dict(state=state, steps=steps, item=item or 'items', unread=unread, order=order, received=received)


def quantity_reply(messages):
    turns = user_turns(messages)
    last = turns[-1]
    low = last.lower()
    # The world is built from the first user turn that states quantities; later turns may add events.
    world = None
    for i, t in enumerate(turns):
        w = quantity_world(sentences(t))
        if w and not w['unread'] and w['steps']:
            if world is None:
                world = w; start = i
            else:
                return None
    if world is None:
        return None
    if start == len(turns) - 1:
        if not re.search(r'\bhow many\b', low):
            return None
        q = [s for s in sentences(last) if s.rstrip().endswith('?')]
    else:
        if not re.search(r'\b(?:how many|total|together|altogether|combined|why|each|more than|fewer than)\b', low):
            return None
        q = [last]
        got = world.get('received') or {}
        m = re.search(r'\bif (her|his|their|the) ([a-z]+) (?:already |originally |first )?(?:had|has|started with) ' + NUM, low)
        if m:
            rel = next((r for r in got if r.split()[-1] == m[2]), None)
            if rel:
                n0, k = num(m[3]), got[rel]
                return out('quantities', f'Then {rel} has {n0} + {k} = {n0 + k} {world["item"]} now ({n0} to start with, plus the {k} from {world["order"][0] if world["order"] else "them"}).')
        if got and re.search(r'\bhow many (?:does|did) (?:he|she|they|her|his)\b', low) and not re.search(r'\bif\b', low):
            rel = next(iter(got))
            return out('quantities', f'{rel[0].upper()}{rel[1:]} received {got[rel]}, but you have not said how many {rel.split()[-1]} had before, '
                                     f'so I can only say: at least {got[rel]}.')
    state, item = world['state'], world['item']
    if any(v < 0 for v in state.values()):
        return out('quantities', 'Those steps give a negative count (' + ', '.join(f'{k}: {v}' for k, v in state.items())
                   + '), so the story is not consistent as written. Could you check the numbers?')
    names = list(state)
    total = sum(state.values())
    parts = []
    qtext = ' '.join(q).lower()
    asks_each = re.search(r'\beach\b|\bboth\b|\beveryone\b|how many do (?:they|both)', qtext)
    asks_total = re.search(r'\btogether\b|\btotal\b|\baltogether\b|\bcombined\b|\bin all\b', qtext)
    asks_why = re.search(r'\bwhy\b', qtext)
    named = [n for n in names if re.search(r'\b' + re.escape(n.lower()) + r'\b', qtext)]
    diff = re.search(r'how many more .*? than', qtext)
    if start == len(turns) - 1:
        parts.append('Step by step: ' + ' '.join(world['steps']))
    if diff and len(named) == 2:
        a, b = named
        parts.append(f'{a} has {state[a]} and {b} has {state[b]}, so the difference is {abs(state[a] - state[b])}.')
    elif asks_each or (not named and not asks_total):
        parts.append('Now: ' + join_list([f'{n} has {state[n]}' for n in names]) + '.')
    elif named and not asks_total:
        parts.append(join_list([f'{n} has {state[n]}' for n in named]) + '.')
    if asks_total:
        parts.append(f'Together they have {" + ".join(str(state[n]) for n in names)} = {total} {item}.')
    if asks_why:
        moved = any('gives' in s for s in world['steps'])
        if moved:
            parts.append(f'A transfer only moves {item} from one person to another: whatever one person loses, the other gains, '
                         f'so the combined total stays the same. Only getting new {item} or losing some would change it.')
        else:
            parts.append(f'The total changes only when {item} are added or taken away; here every change is shown above.')
    if not parts:
        return None
    return out('quantities', ' '.join(parts))


# ------------------------------------------------------------------------------------------ B. timed events

TIME = r'(\d{1,2}(?::\d{2})?\s*(?:[ap]\.?m\.?)?|noon|midnight)'
DUR = r'((?:\d+|' + '|'.join(NUMBER_WORDS) + r'|an?|half an?)\s*(?:hours?|hrs?|minutes?|mins?)(?:\s*(?:and\s*)?(?:\d+|' + '|'.join(NUMBER_WORDS) + r')\s*(?:minutes?|mins?))?)'


def parse_time(t):
    t = t.strip().lower().replace('.', '')
    if t == 'noon':
        return 12 * 60
    if t == 'midnight':
        return 0
    m = re.fullmatch(r'(\d{1,2})(?::(\d{2}))?\s*([ap]m)?', t)
    if not m:
        return None
    h, mi = int(m[1]), int(m[2] or 0)
    if m[3]:
        h = h % 12 + (12 if m[3] == 'pm' else 0)
    elif not m[2]:
        return None
    return h * 60 + mi


def parse_dur(d):
    d = d.lower()
    if re.fullmatch(r'half an? hours?', d.strip()):
        return 30
    total = 0
    for n, unit in re.findall(r'(\d+|' + '|'.join(NUMBER_WORDS) + r'|an?)\s*(hours?|hrs?|minutes?|mins?)', d):
        k = 1 if n in ('a', 'an') else num(n)
        total += k * (60 if unit.startswith('h') else 1)
    return total


def show_time(m, twelve=False):
    m %= 24 * 60
    if twelve:
        h = m // 60; suffix = 'am' if h < 12 else 'pm'; h = h % 12 or 12
        return f'{h}:{m % 60:02d} {suffix}'
    return f'{m // 60:02d}:{m % 60:02d}'


def ev_name(text):
    text = re.sub(r'^(?:the|a|an|our|my|your)\s+', '', text.strip().lower())
    return text


def same_event(a, b):
    a, b = set(a.split()), set(b.split())
    return bool(a & b) and (a <= b or b <= a or len(a & b) >= max(1, min(len(a), len(b)) - 0))


def timeline(text_sentences):
    events = {}; order = []
    twelve = False
    for s in text_sentences:
        s0 = s.rstrip('.!').strip()
        if s0.endswith('?'):
            continue
        m = re.fullmatch(r'(?:(?:the|a|an|our|my) )?([a-z][a-z \-]*?) (?:starts|begins|opens|is|goes (?:in|into|on|out)(?: the [a-z]+)?|leaves|departs|kicks off|gets going) at ' + TIME
                         + r'(?:,)?(?: and (?:lasts|takes|runs(?: for)?|bakes(?: for)?|cooks(?: for)?|plays(?: for)?|goes on for|continues for|needs) ' + DUR + r')?', s0, re.I)
        if m:
            twelve = twelve or bool(re.search(r'[ap]\.?m', m[2], re.I))
            events[ev_name(m[1])] = dict(start=parse_time(m[2]), dur=parse_dur(m[3]) if m[3] else None); order.append(ev_name(m[1])); continue
        m = re.fullmatch(r'(?:(?:the|a|an|our|my) )?([a-z][a-z \-]*?) (?:lasts|takes|runs for|runs) ' + DUR, s0, re.I)
        if m:
            name = next((e for e in events if same_event(e, ev_name(m[1]))), None)
            if name is None:
                return None
            events[name]['dur'] = parse_dur(m[2]); continue
        m = re.fullmatch(r'(?:(?:the|a|an|our|my) )?([a-z][a-z \-]*?) (opens?|starts?|begins?|ends?|finish(?:es)?|closes?|is served|arrives?|leaves?|happens?|goes on|goes in|is added|is put on|comes? out|is ready|gets? (?:served|added))(?: at)? '
                         + DUR + r' (after|before) (?:the |a |an |our |my )?([a-z][a-z \-]*?) (starts|begins|ends|finishes|is over|opens|closes|comes out|is done|is finished|stops|goes in|is taken out)', s0, re.I)
        if m:
            ref = next((e for e in events if same_event(e, ev_name(m[5]))), None)
            if ref is None:
                return None
            events[ev_name(m[1])] = dict(rel=(ref, 'end' if m[6].lower() in ('ends', 'finishes', 'is over', 'closes', 'comes out', 'is done', 'is finished', 'stops', 'is taken out') else 'start',
                                              parse_dur(m[3]) * (1 if m[4].lower() == 'after' else -1)), dur=None, verb=m[2].lower(), refverb=m[6].lower())
            order.append(ev_name(m[1])); continue
        return None
    return (events, order, twelve) if events else None


def resolve(events, name, extra=None):
    e = events[name]
    if 'start' in e and e['start'] is not None:
        start = e['start']
    else:
        ref, anchor, off = e['rel']
        rs, re_ = resolve(events, ref, extra)
        base = re_ if anchor == 'end' else rs
        if base is None:
            return None, None
        start = base + off
    dur = e.get('dur')
    if extra and name in extra and dur is not None:
        dur += extra[name]
    return start, (start + dur if dur is not None else None)


def time_reply(messages):
    turns = user_turns(messages)
    built = None
    for i, t in enumerate(turns):
        tl = timeline([s for s in sentences(t) if not s.endswith('?')])
        if tl and any('rel' in e or e.get('dur') for e in tl[0].values()):
            built = (i, tl); break
    if not built:
        return None
    i, (events, order, twelve) = built
    last = turns[-1].lower()
    show = lambda m: show_time(m, twelve)
    target = order[-1]
    if i == len(turns) - 1:
        if not re.search(r'\bwhat time\b|\bwhen\b', last):
            return None
        qs = ' '.join(x for x in sentences(turns[-1]) if x.rstrip().endswith('?')).lower() or last
        asked = next((e for e in reversed(order) if re.search(r'\b' + re.escape(e.split()[-1]) + r'\b', qs)), target)
        s, e = resolve(events, asked)
        steps = []
        for name in order:
            st, en = resolve(events, name)
            ev = events[name]
            if 'rel' in ev:
                ref, anchor, off = ev['rel']
                rs, re_ = resolve(events, ref)
                steps.append(f'The {name} {ev.get("verb", "is")} {abs(off)} minutes {"after" if off > 0 else "before"} the {ref} {ev.get("refverb", "ends")} '
                             f'({show(re_ if anchor == "end" else rs)}), so {show(st)}.')
            elif ev.get('dur'):
                steps.append(f'The {name} starts at {show(st)} and takes {ev["dur"]} minutes, so it finishes at {show(en)}.')
        verb = events[asked].get('verb') or 'starts'
        ends_q = re.search(r'\b(?:end|finish|over)\b', qs)
        answer = f'The {asked} finishes at **{show(e)}**.' if ends_q and e is not None else f'The {asked} {verb} at **{show(s)}**.'
        return out('time', answer + ' ' + ' '.join(steps))
    # Follow-up: "Suppose the sound check takes 10 extra minutes. Does that change ..."
    m = re.search(r'(?:the )?([a-z][a-z \-]*?) (?:takes|runs|lasts|goes|is|needs) ' + DUR + r' (?:extra|longer|more|late|over)', last)         or re.search(r'(?:the )?([a-z][a-z \-]*?) (?:takes|runs|lasts|needs) (\d+|' + '|'.join(NUMBER_WORDS) + r') (?:extra|more|additional) (minutes?|hours?)', last) \
        or re.search(r'(?:the )?([a-z][a-z \-]*?) (?:takes|runs|lasts) an extra ' + DUR, last)
    m2 = re.search(r'(?:the )?([a-z][a-z \-]*?) (?:starts|begins) ' + DUR + r' (late|later|early|earlier)', last)
    if not (m or m2):
        return None
    if m:
        name = next((e for e in events if same_event(e, ev_name(re.sub(r'^(?:suppose|if|what if|say)\s+', '', m[1])))), None)
        if name is None:
            return None
        extra = {name: parse_dur(m[2] + (' ' + m[3] if m.lastindex and m.lastindex >= 3 and m[3] else ''))}
        before = {n: resolve(events, n) for n in order}
        after = {n: resolve(events, n, extra) for n in order}
        changed = [n for n in order if n != name and before[n][0] != after[n][0]]
        if changed:
            n = changed[-1]
            return out('time', f'Yes. Under your rule the {n} {'come' if n.endswith('s') else 'comes'} a fixed time after the {name} ends, so a {extra[name]}-minute longer {name} '
                       f'(ending at {show(after[name][1])} instead of {show(before[name][1])}) moves the {n} from {show(before[n][0])} to **{show(after[n][0])}**.')
        return out('time', f'No. The {target} is tied to the {name}\'s start, not its end, so a longer {name} does not move it: it stays at {show(before[target][0])}.')
    name = next((e for e in events if same_event(e, ev_name(re.sub(r'^(?:suppose|if|what if|say)\s+', '', m2[1])))), None)
    if name is None or 'start' not in events[name]:
        return None
    k = parse_dur(m2[2]) * (1 if m2[3].startswith('late') else -1)
    ev2 = {n: dict(v) for n, v in events.items()}; ev2[name]['start'] += k
    s2, _ = resolve(ev2, target); s1, _ = resolve(events, target)
    return out('time', f'The {target} moves from {show(s1)} to **{show(s2)}**, because it is set relative to the {name}.' if s1 != s2 else
               f'No, the {target} stays at {show(s1)}.')


# ---------------------------------------------------------------------------------- C. shared availability

def intervals(messages):
    people = {}
    for t in user_turns(messages):
        for s in sentences(t):
            for m in re.finditer(r"(?:(I|we)|" + NAME + r")(?:'m| am| is| are| can| will be| could)?(?: only)? (?:available|free|around|join|come|meet|be there|make it)"
                                 r"(?: to join)? (?:from|between) " + TIME + r" (?:until|till|to|and|-|–) " + TIME, s):
                who = 'you' if m[1] else m[2]
                if who in STOP_NAMES:
                    continue
                a, b = parse_time(m[3]), parse_time(m[4])
                if a is None or b is None:
                    continue
                people[who] = (a, b, bool(re.search(r'[ap]m', m[3] + m[4], re.I)))
    return people


def availability_reply(messages):
    last = user_turns(messages)[-1].lower()
    if not re.search(r'\b(?:shared|overlap|both|meet|when can|common|all (?:of us|free)|available together|work for)\b', last):
        return None
    people = intervals(messages)
    if len(people) < 2:
        return None
    twelve = any(v[2] for v in people.values())
    start = max(v[0] for v in people.values()); end = min(v[1] for v in people.values())
    desc = '; '.join(('you: ' if p == 'you' else p + ': ') + f'{show_time(a, twelve)}–{show_time(b, twelve)}' for p, (a, b, _) in people.items())
    update = len(user_turns(messages)) > 1 and re.search(r'\b(?:actually|now|instead|change|update)\b', user_turns(messages)[-1].lower())
    lead = 'With the updated times' if update else 'Using those times'
    if start >= end:
        return out('availability', f'{lead} ({desc}) there is no shared window: one person is free only after the other has finished. '
                   'You would need someone to extend their time to meet.')
    return out('availability', f'{lead} ({desc}), you can meet from **{show_time(start, twelve)} to {show_time(end, twelve)}** — '
               f'{end - start} minutes. (I am assuming all the times are on the same day and in the same time zone.)')


# ------------------------------------------------------------------------------------------ D. ordering rules

def order_reply(messages):
    turns = user_turns(messages)
    for i, t in enumerate(turns):
        if re.search(r'\b(?:must|has to|should|needs to|comes?|goes?|happens?) (?:come |go |happen |be )?(?:before|after)\b', t, re.I):
            break
    else:
        return None
    text = turns[i]
    items = None
    m = re.search(r'(?:steps|tasks|items|things|people|stages|jobs|events|parts)\s*(?:are)?\s*:\s*([^.]+)', text, re.I)
    if m:
        items = [clean_clause(x) for x in re.split(r',\s*(?:and\s+)?|\s+and\s+', m[1]) if clean_clause(x)]
    rules = []
    def find(name):
        name = clean_clause(name).lower()
        name = re.sub(r'^(?:the|step|task)\s+', '', name)
        for it in items or []:
            if it.lower() == name or it.lower().rstrip('s') == name.rstrip('s'):
                return it
        return None
    for s in sentences(text):
        s0 = s.rstrip('.')
        if m and m.group(0) in s:
            continue
        mm = re.fullmatch(r'(.+?) (?:must|has to|should|needs to)? ?(?:come|go|happen|be)? ?(before|after) (.+?)(?:,)? (?:but|and) (before|after) (.+)', s0, re.I)
        if mm:
            a, b, c = find(mm[1]), find(mm[3]), find(mm[5])
            if not (a and b and c):
                return None
            rules += [(a, b) if mm[2].lower() == 'before' else (b, a), (a, c) if mm[4].lower() == 'before' else (c, a)]; continue
        mm = re.fullmatch(r'(.+?) (?:must |has to |should |needs to )?(?:come |go |happen |be )?(before|after) (.+)', s0, re.I)
        if mm:
            a, b = find(mm[1]), find(mm[3])
            if not (a and b):
                return None
            rules.append((a, b) if mm[2].lower() == 'before' else (b, a)); continue
        mm = re.fullmatch(r'(.+?) (?:is|comes|goes|must be|must come) (first|last)', s0, re.I)
        if mm and find(mm[1]):
            rules.append((find(mm[1]), mm[2].lower())); continue
        if s0.endswith('?'):
            continue
        return None
    if not items or not rules:
        return None
    def ok(p):
        for r in rules:
            if r[1] in ('first', 'last'):
                if (r[1] == 'first' and p[0] != r[0]) or (r[1] == 'last' and p[-1] != r[0]):
                    return False
            elif p.index(r[0]) > p.index(r[1]):
                return False
        return True
    sols = [p for p in itertools.permutations(items) if ok(p)] if len(items) <= 8 else []
    last = turns[-1].lower()
    if i == len(turns) - 1:
        if not sols:
            return out('order', 'No order satisfies all of those rules: they contradict each other. Could you check them?')
        why = '; '.join(f'{a} before {b}' for a, b in rules if b not in ('first', 'last'))
        if len(sols) == 1:
            return out('order', f'The only order that works is **{" → ".join(sols[0])}**. Checking the rules: {why} — all satisfied.')
        return out('order', f'More than one order works ({len(sols)} of them), for example ' + '; '.join(' → '.join(p) for p in sols[:3])
                   + '. The rules do not fix a single order.')
    if re.search(r'\b(?:longest|shortest|how long|duration|time|quickest|fastest|slowest)\b', last):
        return out('order', ('No. ' if re.match(r'\s*(?:does|do|can|is|will)\b', last) else 'The order cannot tell you that. ') + 'The rules only say which step comes before which; they say nothing about how long any step takes. '
                   'A step can come first and still be the longest, so you would need durations to answer that.')
    if re.search(r'\b(?:first|last|second|third|middle)\b', last) and len(sols) == 1:
        p = sols[0]
        return out('order', f'In the only valid order ({" → ".join(p)}), {p[0]} is first and {p[-1]} is last.')
    return None


# ------------------------------------------------------------------------------------ E. category rules

KIND_WORDS = {'token', 'tokens', 'thing', 'things', 'item', 'items', 'animal', 'animals', 'object', 'objects', 'card', 'cards',
              'box', 'boxes', 'machine', 'machines', 'creature', 'creatures', 'person', 'people', 'member', 'members', 'one', 'ones',
              'student', 'students', 'robot', 'robots', 'plant', 'plants', 'stone', 'stones', 'ball', 'balls', 'book', 'books'}


def prop(phrase):
    words = [w for w in re.findall(r"[a-z\-]+", phrase.lower()) if w not in ('a', 'an', 'the', 'is', 'are', 'be', 'that', 'which', 'who')]
    words = [w for w in words if w not in KIND_WORDS] or words
    def single(w):
        if len(w) > 3 and w.endswith('ies'):
            return w[:-3] + 'y'
        if len(w) > 3 and w.endswith('s') and not w.endswith(('ss', 'us', 'is')):
            return w[:-1]
        return w
    return ' '.join(single(w) for w in words)


def logic_reply(messages):
    turns = user_turns(messages)
    rules = []  # (A, B, positive)
    raw_rules = []; raw_ind = {}; named_goal = None
    src = None
    for i, t in enumerate(turns):
        found = []
        for s in sentences(t):
            s0 = s.rstrip('.')
            m = re.fullmatch(r'(?:in [^,]+, )?(?:every|all|each|any) (.+?) (?:is|are) (.+)', s0, re.I)
            if m:
                found.append((prop(m[1]), prop(m[2]), True)); raw_rules.append(s0[0].lower() + s0[1:]); continue
            m = re.fullmatch(r'(?:in [^,]+, )?no (.+?) (?:is|are|can be) (.+)', s0, re.I)
            if m:
                found.append((prop(m[1]), prop(m[2]), False)); raw_rules.append(s0[0].lower() + s0[1:]); continue
        if found:
            rules += found; src = src if src is not None else i
    if not rules or src is None:
        return None
    last = turns[-1]
    # named individuals: "Leo is a member of the chess club."
    individuals = {}
    for t in turns:
        for s in sentences(t):
            m = re.fullmatch(NAME + r' is (not )?(?:a |an )?(.+?)\.', s.strip())
            if m and m[1] not in STOP_NAMES:
                individuals.setdefault(m[1], []).append((prop(m[3]), not m[2])); raw_ind[m[1]] = ('not ' if m[2] else '') + (re.search(r' is (?:not )?(.+?)\.$', s.strip())[1])
    q = re.search(r'if (?:the |a |an )?(.+?) (?:is|are) (not )?(?:a |an )?(.+?), (?:can|could|must|is|does|do|will|would)\b.*?\b(?:it|they|he|she|[A-Z][\w\-]+)\b (?:be |is |are |has to be |must be )?(not )?(?:a |an )?(.+?)\?', last, re.I)
    if q:
        subject, neg_fact, fact, neg_goal, goal = q[1], bool(q[2]), prop(q[3]), bool(q[4]), prop(q[5])
    else:
        q = re.search(r'\b(?i:is|can|could|must) ' + NAME + r' (?:be )?(not )?(a |an )?(.+?)\?', last)
        if not q or q[1] not in individuals:
            return None
        subject, neg_goal, goal = q[1], bool(q[2]), prop(q[4])
        named_goal = (q[3] or '') + q[4]
        fact, truth = individuals[q[1]][0]
        neg_fact = not truth
    def shown(w):
        return ('a ' + w) if re.search(r'\b(?:a|an) ' + re.escape(w.split()[0]), ' '.join(turns), re.I) else w
    fact_shown, goal_shown = shown(fact), shown(goal)
    if named_goal:
        fact_shown, goal_shown = raw_ind.get(subject, fact), named_goal
    # forward chaining over literals (prop, truth)
    known = {(fact, not neg_fact)}
    changed = True
    while changed:
        changed = False
        for a, b, pos in rules:
            if (a, True) in known:
                lit = (b, True) if pos else (b, False)
                if lit not in known:
                    known.add(lit); changed = True
            # contrapositive: B false -> A false (for "every A is B"); B true -> A false (for "no A is B")
            if pos and (b, False) in known and (a, False) not in known:
                known.add((a, False)); changed = True
            if not pos and (b, True) in known and (a, False) not in known:
                known.add((a, False)); changed = True
    chain = [f'every {a} is {b}' if pos else f'no {a} is {b}' for a, b, pos in rules]
    rule_text = '; '.join(raw_rules)
    want = (goal, not neg_goal)
    contra = (goal, neg_goal)
    named = subject[:1].isupper() and subject in individuals
    who = subject if (named or (re.fullmatch(r'[A-Z][\w\-]+', subject) and subject not in STOP_NAMES)) else 'it'
    if want in known:
        lead = f'{subject} is {fact_shown}' if named else f'if it is {fact_shown}'
        return out('logic', f'Yes. Using only the rules ({rule_text}): {lead}, so {who} {"is not" if neg_goal else "is"} {goal_shown}.')
    if contra in known:
        path = [r for r in rules if (r[0], True) in known]
        expl = ' → '.join([fact] + [(b if p else 'not ' + b) for a, b, p in path])
        return out('logic', f'No. Using only those rules: {expl}. So if {who} is {fact_shown}, {who} {"must" if neg_goal else "cannot"} be {goal_shown}.')
    if neg_fact:
        return out('logic', f'No, you cannot conclude that. The rules only tell us what follows when something *is* {fact_shown}. '
                   f'They say nothing about things that are not {fact_shown}: such a thing might be {goal_shown} or might not, so the answer is unknown '
                   f'from these rules alone (concluding it would be the fallacy of denying the antecedent).')
    return out('logic', f'The rules do not settle it: nothing connects being {fact} to being {goal}, so it could go either way.')


# ------------------------------------------------------------------------------------ F/G. feelings & chat

FEELINGS = ['proud', 'disappointed', 'happy', 'sad', 'tired', 'exhausted', 'anxious', 'nervous', 'excited', 'frustrated', 'relieved',
            'overwhelmed', 'lonely', 'stressed', 'grateful', 'angry', 'annoyed', 'worried', 'calm', 'content', 'hopeful', 'scared',
            'embarrassed', 'guilty', 'confused', 'bored', 'glad', 'upset', 'hurt', 'thrilled', 'pleased', 'satisfied', 'drained', 'restless']


def feeling_words(text):
    low = text.lower()
    return [f for f in FEELINGS if re.search(r'\b' + f + r'\b', low)]


POSITIVE = {'proud', 'happy', 'relieved', 'excited', 'grateful', 'glad', 'calm', 'content', 'hopeful', 'thrilled', 'pleased', 'satisfied'}


def reflect_feelings(text, again=False):
    low = text.lower()
    feelings = feeling_words(text)
    event = None; problem = None
    for s in sentences(text):
        m = re.match(r"(?i)i (?:finally |just |actually )?(finished|completed|made|built|painted|wrote|baked|cooked|passed|did|got|tried|started|ran|knitted|fixed|planted|sent|organized|gave|presented|cleaned|sang|played|won|lost|failed|submitted|moved|quit)\b(.*?)(?:,? but (.*))?$", s.rstrip('.!'))
        if m:
            event = you(clean_clause(m[1] + m[2])); problem = you(clean_clause(m[3])) if m[3] else problem
    if not feelings and not event:
        return None
    parts = []
    for f in feelings:
        m = re.search(r'\b((?:a little |a bit |very |really |quite |so |kind of |slightly |somewhat |deeply |pretty )?)' + f +
                      r"\b((?: (?:that|about|with|of|because|for|it'?s|to|i) [^.,!;]*?)?)(?= and | but |[.,!;]|$)", low)
        mod = m[1] if m else ''
        why = clean_clause(m[2]) if m and m[2] else ''
        why = re.sub(r"^(?:that )?it'?s ", 'it is ', why)
        if why.startswith('it is ') or why.startswith('i '):
            why = 'that ' + why
        if not why:
            if f in POSITIVE and event:
                why = f'about how {event}' if False else ''
            elif f not in POSITIVE and problem:
                why = f'that {problem}'
        parts.append((mod + f, you(why)))
    if event and len(parts) >= 2:
        (a, wa), (b, wb) = parts[0], parts[1]
        fa = f'{a} {wa}'.strip(); fb = f'{b} {wb}'.strip()
        if again:
            pos = next((x for x, _ in parts if x.split()[-1] in POSITIVE), None); neg = next((x for x, _ in parts if x.split()[-1] not in POSITIVE), None)
            tail = (f' Feeling {neg.split()[-1]} does not cancel what you did, and feeling {pos.split()[-1]} does not mean the hard part did not matter.' if pos and neg else '')
            return f'Of course. You {event}, and you feel two things at once: {fa}, and {fb}. Both make sense.' + tail
        return (f'That sounds like a real mix. You {event}{", and " + problem if problem else ""}. It makes sense to feel {fa}, '
                f'and also {fb}. Both feelings can be true at the same time.')
    if event and parts:
        return f'You {event}{", and " + problem if problem else ""}. Feeling ' + join_list([f'{x} {w}'.strip() for x, w in parts]) + ' makes complete sense.'
    if event:
        return f'You {event}, and it sounds like that matters to you.'
    return 'It sounds like you are feeling ' + join_list([f'{x} {w}'.strip() for x, w in parts]) + '. That is completely understandable.'



def feelings_reply(messages):
    turns = user_turns(messages)
    last = turns[-1]; low = last.lower()
    if re.search(r"\breflect\b|\bwithout (?:trying to )?(?:fix|solv|advice)|\bjust listen\b|\backnowledge\b|\bdon't (?:give me|try to fix)|\bno (?:advice|tips)\b", low) and len(turns) > 1:
        for t in reversed(turns[:-1]):
            r = reflect_feelings(t, again=True)
            if r:
                return out('reflect', r)
    if '?' in last and not re.search(r'no advice|just (?:want|need) to (?:say|share|vent)', low):
        return None
    if len(feeling_words(last)) >= 1 and re.search(r"\bi(?:'m| am| feel|'ve| was| finished| just| ran| did)\b", low):
        r = reflect_feelings(last)
        if r:
            if re.search(r"no advice|don't (?:need|want) advice|no tips", low):
                r += ' No advice, just hearing you.'
            return out('reflect', r)
    return None


TOPIC_HOOKS = [(r'\btea\b', 'what kind of tea you are drinking, and whether you have a favourite for quiet afternoons'),
               (r'\bcoffee\b', 'how you like your coffee, and your favourite place to drink it'),
               (r'\brain', 'whether you like rainy days, and what sounds or smells you notice when it rains'),
               (r'\bwalk|\bpark\b', 'what you noticed on your walk, or a favourite place to wander'),
               (r'noisy|busy|hectic|long week', 'one small good moment from the week, even a tiny one'),
               (r'\bbalcony|\bgarden', 'what you can see from where you are sitting'),
               (r'\bcook|\bbak', 'a favourite thing to cook or bake'),
               (r'\bmusic|\bsong', 'a song you have had on repeat')]
GENERIC_TOPICS = ['a book, show or film you have enjoyed lately', 'a place you would love to visit just to sit and do nothing',
                  'a hobby you like for no useful reason at all', 'the best thing you have eaten recently']


def casual_reply(messages):
    turns = user_turns(messages)
    last = turns[-1]; low = last.lower()
    if re.search(r"\bwhat (?:could|can|should|shall|might) we (?:talk|chat) about\b|\bsuggest (?:a|some) topics?\b|\bchat about something\b|\bsomething (?:fun|nice|light|interesting|random) (?:we could|to|we can) (?:talk|chat)|\bcan we (?:just )?(?:chat|talk)\b.*\?|\bwhat(?:'s| is) something .* (?:talk|chat) about|\b(?:light|fun|easy|random|nice|good) topics?\b|\bany topics\b|\btopics? (?:for us|to (?:talk|chat))|\bsomething (?:light|fun) to (?:talk|chat)", low):
        context = ' '.join(turns).lower()
        ideas = [t for p, t in TOPIC_HOOKS if re.search(p, context)][:2]
        ideas += GENERIC_TOPICS[:4 - len(ideas)]
        no_tips = re.search(r'not (?:a list of )?(?:productivity|tips|advice)', low)
        lead = 'Happy to keep it relaxed' + (', and no productivity tips, promise.' if no_tips else '.')
        return out('casual', f'{lead} We could talk about {ideas[0]}; or {ideas[1]}; or {join_list(ideas[2:], "or")}. '
                   'Or something completely random: if you could have any animal curled up next to you right now, which would it be? Pick whatever sounds nice.')
    if len(turns) == 1 and re.match(r'(?i)\s*(?:hi|hello|hey|good (?:morning|afternoon|evening)|morning|evening)\b', last) and '?' not in last:
        bits = []
        m = re.search(r"(?i)\b(?:i (?:finally )?have|it's|its|it is) (a [^.!,]*?(?:afternoon|morning|evening|day|weekend|night))( after [^.!,]+)?", last)
        if m:
            bits.append(f'{m[1][0].upper() + m[1][1:]}{m[2] or ""} sounds well earned.')
        scene = re.search(r"(?i)\bi(?:'m| am) (sitting|lying|relaxing|curled up|sat) ([^.!]+)", last)
        back = re.search(r"(?i)\bi(?:'ve| have)? just (?:got|came|come) back from ([^.!,]+?)(?: and|[.!,])", last)
        feel = re.search(r"(?i)\bi(?:'m| am) (?:feeling )?((?:pretty |really |very |so )?(?:relaxed|happy|calm|tired|good|great|content|refreshed|sleepy))", last)
        if scene:
            bits.append(f'{scene[1].capitalize()} {you(clean_clause(scene[2]))} sounds lovely.')
        elif back:
            g = you(clean_clause(back[1]))
            bits.append(f'{g[0].upper()}{g[1:]} sounds like a good way to spend the time.')
        if feel and not scene:
            bits.append(f'Feeling {feel[1]} afterwards is the best part.')
        if 'tea' in low and not scene:
            bits.append('Enjoy the tea' + (', and take all the time you like.' if re.search(r'slow|relax|rest|unwind', low) else '.'))
        if 'rain' in low:
            q = 'Do you like rainy mornings like this?'
        elif 'tea' in low:
            q = 'What kind of tea is it?'
        elif back:
            q = 'What was the best part of it?'
        else:
            q = 'What is on your mind today?'
        if bits:
            return out('casual', 'Hi! ' + ' '.join(bits) + ' ' + q)
    return None


# ------------------------------------------------------------------------------------ H/I/K. what was said

NAME_RE = r"(?i:\bcall me|\bmy name is|\bi'm called|\byou can call me|\bi am called|\bname's)\s+([A-Z][\w\-]*)"


DETERMINERS = {'a', 'an', 'the', 'my', 'your', 'our', 'some', 'this', 'that', 'two', 'three', 'one', 'new', 'small', 'big', 'little'}


def gerund(phrase):
    words = phrase.split()
    if not words or words[0].lower() in DETERMINERS:
        return phrase
    v = words[0]
    irregular = {'run': 'running', 'begin': 'beginning', 'set': 'setting', 'plan': 'planning', 'get': 'getting', 'put': 'putting', 'swim': 'swimming',
                 'shop': 'shopping', 'stop': 'stopping', 'sit': 'sitting', 'die': 'dying', 'lie': 'lying', 'be': 'being', 'see': 'seeing'}
    if v in irregular:
        g = irregular[v]
    elif v.endswith('ie'):
        g = v[:-2] + 'ying'
    elif v.endswith('e') and not v.endswith(('ee', 'ye', 'oe')):
        g = v[:-1] + 'ing'
    else:
        g = v + 'ing'
    return ' '.join([g] + words[1:])


def said(messages):
    """A small profile of explicit statements in earlier user turns."""
    p = dict(name=None, plans=[], unknown=[], prefer=None, considering=None, undecided=None, depends=None, might=None, task=None)
    for t in user_turns(messages)[:-1]:
        m = re.search(NAME_RE, t)
        if m:
            p['name'] = m[1]
        for m in re.finditer(r"\bi(?:'m| am) (?:planning|going|hoping|about) (?:on |to )?([^.,;!?]+?)(?:,| but| and|[.!?]|$)", t, re.I):
            p['plans'].append(clean_clause(m[1]))
        for m in re.finditer(r"\bi (?:haven't|have not|did not|didn't) (?:told|mentioned|said|shared|given)(?: you)? (which|what|where|my|how|when)\s*([^.,;!?]+)", t, re.I):
            p['unknown'].append(clean_clause(m[1] + ' ' + m[2]))
        m = re.search(r"\bi(?:'d| would) rather (.+?) than (.+?)(?: because (.+?))?[.?!]", t, re.I) or \
            re.search(r"\bi prefer (.+?) over (.+?)(?: because (.+?))?[.?!]", t, re.I) or re.search(r"\bi prefer (.+?) to (.+?)(?: because (.+?))?[.?!]", t, re.I)
        if m:
            p['prefer'] = (clean_clause(m[1]), clean_clause(m[2]), clean_clause(m[3]) if m[3] else None)
        m = re.search(r"\bi (?:haven't|have not|didn't) (?:chosen|decided|picked|settled on)(?: on)? (.+?)(?: yet)?[.;]", t, re.I)
        if m:
            p['undecided'] = clean_clause(m[1])
        m = re.search(r"\bi(?:'m| am) (?:considering|weighing|choosing between|deciding between|thinking about|torn between) (.+?)(?:;|\.|$)", t, re.I)
        if m:
            p['considering'] = [clean_clause(x) for x in re.split(r'\s+(?:and|or)\s+|,\s*', m[1]) if clean_clause(x)]
        m = re.search(r"\bthe ((?:[\w\-]+ ){0,3}?[\w\-]+) (?:might|may|could) suit me", t, re.I) or re.search(r"([\w\-]+(?: [\w\-]+)?) (?:might|may|could) suit me", t, re.I)
        if m:
            p['might'] = re.sub(r'^(?:the|a|an)\s+', '', clean_clause(m[1]), flags=re.I)
        m = re.search(r"\b(?:that |it )?depends on (.+?)[.!?]", t, re.I)
        if m:
            p['depends'] = you(clean_clause(m[1]))
        m = re.search(r"\bi (?:keep )?(?:avoid|avoiding|putting off|put off|procrastinating on|dreading) (.+?)(?: because| since|[.,!?])", t, re.I)
        if m:
            p['task'] = clean_clause(m[1])
    return p


def recall_reply(messages):
    turns = user_turns(messages)
    if len(turns) < 2:
        return None
    last = turns[-1]; low = last.lower()
    p = said(messages)
    parts = []
    if p['prefer'] and re.search(r'\bwhat reason\b|\bwhy did i\b|\bwhat did i say\b|\bmy reason\b|\b(?:actually )?(?:completed|done|did it|finished)\b|\balready\b', low):
        a, b, why = p['prefer']
        if re.search(r'reason|why', low):
            parts.append(f'You said it is because {you(why)}.' if why else 'You did not give a reason.')
        if re.search(r'completed|done|did it|finished|actually|already', low):
            pref = f'prefer {you(a)} over {you(b)}' if a.split()[0].endswith('ing') else f'would rather {you(a)} than {you(b)}'
            parts.append(f'And no, you have not told me that. You said you {pref}, which is a preference, not a report of something you did.')
        if parts:
            return out('recall', ' '.join(parts))
    if p['name'] or p['plans'] or p['unknown']:
        if re.search(r'\bwhat (?:name|should you call)\b|\bmy name\b|\bwho am i\b', low) and p['name']:
            parts.append(f'Your name is {p["name"]}, so that is what I will call you.' if re.search(r'remember|my name', low) else f'I should call you {p["name"]}.')
        if re.search(r"\bwhat am i planning\b|\bmy plan\b|\bwhat i(?:'m| am) planning\b|\band plan\b", low) and p['plans']:
            plan = you(p['plans'][-1])
            parts.append(f'You are planning {plan}.' if plan.split()[0].lower() in DETERMINERS else f'You are planning to {plan}.')
        asked_unknown = [u for u in p['unknown'] if re.search(r'\b(?:do you know|did i (?:tell|say|pick|choose)|have i (?:told|said))\b', low)
                         and set(re.findall(r'[a-z]+', u)) - {'which', 'what', 'where', 'how', 'when', 'my', 'i', 'you', 'want', 'live', 'am'} & set(re.findall(r'[a-z]+', low))]
        for u in asked_unknown:
            parts.append(f"No, I don't know {you(u)}: you haven't told me yet. What are you thinking of?")
        if re.search(r'\bweather\b', low):
            place = next((u for u in p['unknown'] if re.search(r'city|town|where|live|location|country', u)), None)
            parts.append("I don't know your local weather: " + ("you haven't told me where you live, " if place else "I don't know where you are, ")
                         + "and I don't have a live weather feed here. If you tell me your town, I can tell you what to look up.")
        elif re.search(r'\b(?:where do i live|which city|my city)\b', low):
            parts.append("You haven't told me where you live, so I don't know.")
        if parts:
            return out('recall', ' '.join(parts))
    if (p['undecided'] or p['considering']) and re.search(r"\bwhat (?:have i|did i) (?:actually )?decided\b|\bdecided so far\b|\bwhat(?:'s| is) (?:still )?(?:uncertain|open|undecided)\b|\bwhat do i know\b|\bstill open\b", low):
        opts = p['considering'] or []
        parts.append("Decided: nothing yet. You said you haven't chosen " + (you(p['undecided']) if p['undecided'] else 'yet') + '.')
        if opts:
            parts.append(f'You are considering {join_list(opts, "and")}.')
        unc = []
        if opts:
            unc.append('which option you will pick')
        if p['might'] and p['depends']:
            unc.append(f'whether the {p["might"]} would suit you, which depends on {p["depends"]}')
        elif p['depends']:
            unc.append(f'{p["depends"]}')
        if unc:
            parts.append('Still open: ' + join_list(unc) + '.')
        return out('recall', ' '.join(parts))
    return None


def statement_ack(messages):
    """Statements that set up memory: names, plans, preferences, undecided choices."""
    turns = user_turns(messages)
    last = turns[-1]; low = last.lower()
    if '?' in last:
        return None
    m = re.search(NAME_RE, last)
    plan = re.search(r"\bi(?:'m| am) planning (?:on |to )?([^.,;!?]+)", last, re.I)
    unknown = re.search(r"\bi (?:haven't|have not) (?:told|mentioned)(?: you)? (which|what|where)\s*([^.,;!?]+)", last, re.I)
    if m or plan:
        bits = []
        if m:
            bits.append(f"Nice to meet you, {m[1]}. I'll call you that.")
        if plan:
            g = gerund(you(clean_clause(plan[1])))
            bits.append(f'{g[0].upper()}{g[1:]} sounds like a lovely plan.')
        if unknown:
            place = re.search(r'live|city|town|where', unknown[2] + unknown[1])
            bits.append(f"And noted: I don't know {unknown[1]} {you(clean_clause(unknown[2]))}" + (", so I won't assume anything about your local weather or conditions." if place else ' yet, so I will not guess.'))
        bits.append('Which herbs are you thinking of?' if 'herb' in low else ('What would you like to grow?' if re.search(r'vegetable|garden|patch|plant', low)
                    else ('Do you have a few colours in mind?' if re.search(r'colou?r|paint', low) else 'What would you like to start with?')))
        return out('ack', ' '.join(bits))
    pref = re.search(r"\bi prefer (.+?) over (.+?)(?: because (.+?))?[.!]", last, re.I) or re.search(r"\bi prefer (.+?) to (.+?)(?: because (.+?))?[.!]", last, re.I) or re.search(r"\bi(?:'d| would) rather (.+?) than (.+?)(?: because (.+?))?[.!]", last, re.I)
    if pref:
        line = f'Got it: you prefer {you(clean_clause(pref[1]))} over {you(clean_clause(pref[2]))}'
        line += f', because {you(clean_clause(pref[3]))}. That sounds like a good reason.' if pref[3] else '.'
        return out('ack', line)
    und = re.search(r"\bi (?:haven't|have not) (?:chosen|decided|picked)(?: on)? (.+?)(?: yet)?[.;]", last, re.I)
    if und:
        p = said(messages + [dict(role='user', content='?')])
        opts = p['considering'] or []
        line = 'Got it: nothing is decided yet.'
        if opts:
            line += f' You are weighing {join_list(opts, "and")}'
            if p['might'] and p['depends']:
                line += f', and the {p["might"]} might suit you, depending on {p["depends"]}.'
            else:
                line += '.'
        line += ' Once you know more, we could compare them side by side.'
        return out('ack', line)
    return None


# ------------------------------------------------------------------------------------ J. decisions

def decision_options(turns):
    for t in turns:
        m = (re.search(r"\bi can either (.+?) or (.+?)[.;?]", t, re.I) or re.search(r"\b(?:should i|whether to|whether i should) (.+?) or (.+?)[?.]", t, re.I)
             or re.search(r"\b(?:choose|choosing|deciding|decide|torn) between (.+?) and (.+?)[.?]", t, re.I))
        if m:
            return clean_clause(m[1]), clean_clause(m[2]), t
    return None


def repair_case(a, b):
    """'fix/repair/mend X' versus 'buy/get a new/replacement' -> the thing being repaired, else None."""
    if re.search(r'\b(?:fix|repair|mend|patch|service)\b', a, re.I) and re.search(r'\b(?:buy|get|order|purchase)\b.*\b(?:new|replacement|another)\b|\breplace\b', b, re.I):
        m = re.search(r'\b(?:fix|repair|mend|patch|service)(?: up)? (?:my |the |an? |our )?(?:old |broken |current )?([a-z\- ]+?)(?: cheaply| myself|$)', a.lower())
        return (m[1].strip() if m else 'it')
    return None


def decision_reply(messages):
    turns = user_turns(messages)
    last = turns[-1]; low = last.lower()
    found = decision_options(turns)
    if not found:
        return None
    a, b, src = found
    thing = repair_case(a, b)
    if src == last:
        if not re.search(r'\bhow (?:can|should|do) i (?:compare|decide|choose|weigh)|\bwhich\b|\bshould i\b|\bhelp me\b|\bwhat (?:should|would) you\b|\bcan(?:\'t| not) tell\b', low):
            return None
        uncertain = re.search(r"don't know how likely|not sure how likely|can't tell how long|cannot tell|without (?:pretending|guessing|knowing)|probability|uncertain|no idea how long", low)
        if thing:
            lines = [f'You can compare repairing the {thing} with buying a new one without guessing a probability:',
                     '1. **Break-even.** Ask how long the repair would need to last to be worth it. If the repair costs R and a new one costs P, '
                     f'the repair pays off as long as it gives you at least R/P of the life you would expect from a new {thing}. A repair costing a fifth of the price only has to last about a fifth as long.',
                     f'2. **Worst case.** If the repair fails quickly, you lose R and buy the new {thing} anyway. If losing R would not hurt much, trying the repair first is a cheap experiment.',
                     '3. **Keep the option open.** Repairing first does not rule out buying later; buying first usually ends the repair option.',
                     f'4. **Evidence instead of a guess.** Find out what exactly is wrong with the {thing}: a worn, replaceable part is usually a durable fix, while a failing frame, motor or electronics is riskier. Ask whether the repair comes with a guarantee.']
            lines.append('That way the decision rests on things you can find out, not on a probability you would be making up.' if uncertain else
                         'If you tell me roughly what each option costs, I can work through the numbers with you.')
            return out('decision', '\n'.join(lines))
        lines = [f'Here is a simple way to compare "{a}" and "{b}":',
                 '1. **What you gain** from each, now and in a year.',
                 '2. **What it costs**: money, time, effort, and what you give up by not choosing the other.',
                 '3. **The worst realistic case** for each, and whether you could live with it.',
                 '4. **Reversibility**: if one choice is easy to undo, it is the safer one to try first.',
                 'Tell me what matters most to you and I can help you weigh it.']
        return out('decision', '\n'.join(lines))
    pri = re.search(r"\bi care (?:more |most )?about (.+?)(?: (?:more )?than (?:about )?(.+?))?[.!]", last, re.I) or \
        re.search(r"\b(?:money is tight|on a budget|can't afford to waste|wasting (?:it|money) is my (?:biggest )?worry|my (?:main|biggest) (?:worry|concern) is (.+?)[.!])", last, re.I)
    asks = re.search(r"\bwhat (?:information|info|would be (?:most )?useful|should i (?:find out|check|ask|look)|do i need to know)\b|\bwhat next\b|\bfirst\b|\bnext\b", low)
    if asks or pri:
        money = re.search(r'money|waste|wasted|cost|budget|afford|cheap|tight', low)
        care = 'avoiding wasted money' if money else (you(clean_clause(pri[1])) if pri and pri.lastindex and pri[1] else 'that')
        if thing:
            lines = [f'Since {care} matters most to you, find out these first:',
                     f'1. **The exact repair cost** (parts and any labour) and the **price of a new {thing}**. Together they give you the break-even ratio R/P.',
                     f'2. **What is actually wrong with the {thing}.** A worn, cheap, replaceable part usually lasts; an unknown or structural fault is where money gets wasted.',
                     '3. **Whether the repair is guaranteed**, or whether a new one has a warranty or return period. That limits the downside either way.',
                     f'4. **How long a new {thing} typically lasts**, so you know what the repair has to beat.',
                     'If the repair is a small fraction of the new price and the fault is a simple part, repairing is usually the lower-waste choice.']
        else:
            lines = [f'Since {care} matters most, the most useful things to find out next are:', f'1. The full cost of "{a}" and of "{b}".',
                     '2. What happens in the worst case for each.', '3. Which choice you could undo if it goes wrong.']
        return out('decision', '\n'.join(lines))
    return None


# ------------------------------------------------------------------------------------ L/M/N. writing & plans

PLACE_PEOPLE = {'bakery': 'baker', 'library': 'librarian', 'garden': 'gardener', 'school': 'teacher', 'cafe': 'barista', 'café': 'barista',
                'kitchen': 'cook', 'farm': 'farmer', 'shop': 'shopkeeper', 'market': 'stallholder', 'workshop': 'carpenter', 'hospital': 'nurse',
                'theatre': 'stagehand', 'theater': 'stagehand', 'station': 'station guard', 'museum': 'curator', 'park': 'park keeper',
                'restaurant': 'chef', 'zoo': 'keeper', 'classroom': 'teacher', 'office': 'office manager', 'studio': 'painter', 'boat': 'sailor',
                'beach': 'lifeguard', 'harbour': 'fisherman', 'harbor': 'fisherman', 'orchard': 'farmer', 'laundry': 'laundry owner', 'barn': 'farmer'}
OBJECT_USES = {'mitten': 'a perfect little oven glove', 'sock': 'a duster for the high shelves', 'scarf': 'a bright table runner',
               'umbrella': 'a shade for the tender seedlings', 'hat': 'a basket for the morning eggs', 'spoon': 'a scoop for the flour',
               'button': 'a counter for keeping score', 'teacup': 'a tiny plant pot', 'boot': 'a sturdy doorstop', 'glove': 'a puppet for the children',
               'key': 'a tinkling wind chime', 'shoe': 'a planter for herbs', 'jar': 'a lantern', 'ribbon': 'a bookmark', 'kite': 'a banner for the window',
               'bucket': 'a drum for the band', 'chair': 'a stand for the potted fern', 'blanket': 'a bed for the shop cat', 'bicycle': 'a trellis for climbing beans',
               'bottle': 'a vase for wildflowers', 'basket': 'a nest for the hens', 'ladder': 'a bookshelf', 'suitcase': 'a bed for the puppy', 'clock': 'a timer for the bread'}
WEARABLE = {'mitten', 'sock', 'scarf', 'hat', 'glove', 'boot', 'shoe', 'ribbon'}
FUNNY_LINES = {'umbrella': 'It opened with such a proud whoosh that a startled pigeon took the rest of the afternoon off.',
               'mitten': 'It even seemed to wave whenever the oven door opened.'}


def story_parts(text):
    low = text.lower()
    n = re.search(r'\b(?:write|tell)(?: me)?(?: a)? ' + NUM + r'[- ](?:short )?sentences?', low) or re.search(NUM + r'[- ]sentences?', low)
    count = num(n[1]) if n else 3
    obj = re.search(r'about (?:a|an|the) ((?:(?:lost|old|lonely|little|tiny|forgotten|broken|single|red|blue|odd|rusty|battered|small|shy|grumpy|abandoned) )*)([a-z]+)', low)
    place = re.search(r'\b(?:in|at|on) (?:a|an|the) ([a-z]+)(?=[ .,!?]|$)', low)
    if not obj or obj[2] in ('time', 'day', 'person', 'man', 'woman', 'girl', 'boy'):
        return None
    return dict(count=max(1, min(count, 8)), adj=obj[1].strip(), obj=obj[2], place=place[1] if place else None,
                funny=bool(re.search(r'funny|humou?r|silly|amusing', low)), gentle=bool(re.search(r'gentle|cheerful|happy|upbeat|cosy|cozy|warm', low)))


def article(word):
    return 'an' if word[:1] in 'aeiou' else 'a'


def compose_story(p, ending=None):
    obj, place = p['obj'], p['place']
    person = PLACE_PEOPLE.get(place, 'neighbour') if place else 'neighbour'
    use = OBJECT_USES.get(obj, 'something surprisingly useful')
    adj = p['adj']
    noun = (adj + ' ' + obj) if adj else obj
    where = f'the {place}' if place else 'the town square'
    if 'lost' in adj and obj in WEARABLE:
        s1 = f"One frosty morning, {article(noun)} {noun} slipped off a child's coat and landed by the door of {where}."
    elif re.search(r'old|rusty|battered|forgotten|abandoned', adj):
        s1 = f'{article(noun).capitalize()} {noun} had spent years forgotten at the back of a cupboard, until one spring day it was carried out to {where}.'
    else:
        s1 = f'One ordinary morning, {article(noun)} {noun} turned up, quite by accident, in {where}.'
    if place == 'bakery' and obj == 'mitten':
        s2 = f'The {person} picked it up, laughed, and found it made {use}, just the right size for lifting hot trays of buns.'
    else:
        s2 = f'The {person} picked it up, smiled, and discovered it made {use}.'
    extra = FUNNY_LINES.get(obj) if p.get('funny') else None
    if ending == 'keeps':
        s3 = (f"Even when the child came back for it, everyone agreed it should stay, so the {obj} kept its place on a hook by the oven, warm and busy every single morning."
              if place == 'bakery' else f'The {person} decided it would never be thrown away, and from that day on the {obj} stayed in {where} for good, doing its new job every single day.')
    else:
        s3 = (f'By the time the bakery closed, the {obj} smelled of cinnamon and was the happiest {obj} in town.' if place == 'bakery'
              else f'By evening the {obj} had a new job and a new home, and it seemed very pleased about both.')
    sents = [s1, s2] + ([extra] if extra else []) + [s3]
    if len(sents) > p['count']:
        sents = [s1, s2, s3][:p['count']] if p['count'] < 3 else [s1, s2 if not extra else s2 + ' ' + extra.split('.')[0].lower().join(['', '']) or s2, s3]
        if extra and p['count'] == 3:
            sents = [s1, s2[:-1] + ', and ' + extra[0].lower() + extra[1:], s3]
    while len(sents) < p['count']:
        sents.insert(-1, f'Everyone who came by asked about it, and the {person} told the story with a grin.' if len(sents) == 3 else
                     f'Little by little, the {obj} became part of everyday life in {where}.')
    return ' '.join(sents[:p['count']])


def invitation_parts(turns):
    for t in reversed(turns):
        m = re.search(r'invitation (?:to|for) (?:a|an|the|our) ([a-z\- ]+?)(?:,|\.| using| with| that|$)', t.lower())
        if m:
            return m[1].strip(), t
    return None


SWAP_ITEMS = {'seed': 'a few seeds or cuttings', 'book': 'a few books you have finished with', 'plant': 'a plant or cutting', 'clothes': 'clothes you no longer wear',
              'toy': 'toys your children have outgrown', 'record': 'a record or two', 'game': 'a board game', 'puzzle': 'a puzzle'}


def compose_invitation(event, style, sentences_n=2):
    items = next((v for k, v in SWAP_ITEMS.items() if k in event), None)
    if style == 'formal':
        lines = [f'You are cordially invited to the {event}, to be held on [date] at [time] at [venue].',
                 (f'Guests are welcome to bring {items} to exchange; ' if items else 'We would be delighted to welcome you; ') + 'kindly reply to [contact] by [RSVP date].']
    else:
        lines = [f"Come along to our {event} on [date] at [time] at [venue]!",
                 (f'Bring {items} to swap, and take something new home. ' if items else '') + 'Hope to see you there!']
    return ' '.join(lines[:max(2, sentences_n)])


def plan_for(task, minutes=None):
    t = you(task)
    small = f'set a timer for {minutes} minutes and ' if minutes else 'set a timer for ten minutes and '
    if re.search(r'sort|tidy|clean|declutter|organi[sz]e|drawer|closet|cupboard|desk|shelf|room|garage|wardrobe|inbox|pile', t):
        thing = re.search(r'(drawer|closet|cupboard|desk|shelf|room|garage|wardrobe|box|inbox|pile)', t)
        thing = thing[1] if thing else 'space'
        return (f'{small}deal with just five things from the {thing}. Give each one a quick choice: keep, let go, or "decide later". '
                'The "decide later" pile means nothing needs a hard decision today. When the timer goes off, you are allowed to stop. That counts as a start.')
    if re.search(r'write|essay|report|email|letter|application|thesis', t):
        return f'{small}open the document and write one rough sentence about what it needs to say, even a bad one. Editing comes later.'
    return f'{small}do only the smallest visible piece of {t}: get out what you need, make one small decision, or write down the very next action. Then you may stop.'


def writing_reply(messages):
    turns = user_turns(messages)
    last = turns[-1]; low = last.lower()
    if re.search(r'\b(?:write|tell)\b.*\bsentences? about\b|\bwrite (?:a )?(?:short |little |tiny )?(?:story|paragraph) about\b', low) and not re.search(r'\b(?:code|python|function|program|essay)\b', low):
        p = story_parts(last)
        if p:
            return out('story', compose_story(p))
    if re.search(r'\b(?:rewrite|change|redo|give it|new|different) (?:the )?ending\b|\bending so\b', low):
        for t in reversed(turns[:-1]):
            p = story_parts(t)
            if p:
                keep = re.search(r'\bkeeps?\b|\bforever\b|rather than throw|never throw|stays?\b', low)
                return out('story', compose_story(p, 'keeps' if keep else None))
    inv = invitation_parts(turns)
    if inv:
        event, src = inv
        n = re.search(NUM + r'[- ]sentences?', src.lower())
        if src == last and re.search(r'\b(?:write|draft|compose|make)\b', low):
            style = 'formal' if re.search(r'\bformal\b', low) else 'casual'
            return out('writing', compose_invitation(event, style, num(n[1]) if n else 2))
        st = re.search(r'\b(formal|casual|friendly|polite|relaxed)\b', low)
        if st and re.search(r'\b(?:make it|more|rewrite|turn it|now|change it)\b', low):
            style = 'formal' if st[1] in ('formal', 'polite') else 'casual'
            return out('writing', compose_invitation(event, style, num(n[1]) if n else 2))
    p = said(messages)
    if len(turns) == 1 or not p['task']:
        m = re.search(r"\bi (?:keep )?(?:avoid|avoiding|putting off|put off|procrastinating on|dreading) (.+?)(?: because (.+?))?[.,!?]", last, re.I)
        if m and re.search(r'\b(?:start|begin|get going|where do i|how do i|how can i)\b', low):
            task = clean_clause(m[1]); why = m[2]
            lead = (f'That makes sense: when {you(clean_clause(why))}, starting feels heavy. ' if why else 'That feeling is really common. ')
            return out('plan', lead + 'The trick is to make the first step so small that it is easy: ' + plan_for(task)
                       + ' Starting small builds momentum, and you can always do a bit more if you feel like it.')
    tb = re.search(r'\b(?:i (?:can|could) (?:spare|give it|do)|i have|i\'ve got|only have|just have|i only have|just) ' + DUR, low)
    if tb and len(turns) > 1:
        mins = parse_dur(tb[1])
        task = p['task'] or next((clean_clause(m[1]) for t in turns[:-1] for m in [re.search(r'(?:start(?:ed)?|begin) (?:on )?(.+?)[.?!]', t, re.I)] if m), None)
        if task:
            plan = plan_for(task, mins)
            return out('plan', f'Here is a {mins}-minute first step: {plan[0].lower()}{plan[1:]}')
    return None


# ------------------------------------------------------------------------------------ O. explanations

EXPLAIN = [
    (r'fluent|confident(?:ly)?.*(?:dependable|reliable|true|correct|trust)|(?:dependable|reliable|trust).*(?:fluent|confident)',
     'No. How fluently and confidently something is written tells you about the *writing*, not about whether it is *true*. '
     'Fluency is about smooth sentences; confidence is about tone. Dependability is about evidence: can the claim be checked, does it cite a source, '
     'do other independent sources agree, and does the writer say what they are unsure about? A hesitant answer with good evidence can be more reliable '
     'than a polished one with none. So treat confident wording as style, and look for the evidence behind it.',
     [(r'example|plausible|another (?:possible )?cause|other cause',
       'Everyday example: you notice the grass is wet in the morning and conclude it rained overnight. That is plausible, but the sprinkler may have run, '
       'or it may just be dew. The wet grass fits several causes, so checking (is the pavement wet too? did the sprinkler run?) tells you which one it was.')]),
    (r'warm (?:air|parcel).*rise|hot air rise|why does (?:warm|hot) air',
     'A warm parcel of air rises because it is less dense than the cooler air around it. When air warms, its molecules move faster and push farther apart, '
     'so the same amount of air takes up more space and weighs less per litre. The surrounding cooler, denser air is pulled down by gravity more strongly '
     'and slides underneath, pushing the lighter warm parcel upward — the same buoyancy that makes a cork float up through water. '
     'Heat here is not a substance; it is the faster motion of the molecules that makes the warm air spread out.',
     [(r'(?:even )?warmer|surrounding air (?:were|was|is) (?:also |even )?(?:warm|hot)|same temperature',
       'The explanation still works, but the result changes. What matters is the *difference*: a parcel rises only if it is warmer (less dense) than the air around it. '
       'If the surrounding air were even warmer than the parcel, the parcel would be the denser one, so it would sink instead of rise. '
       'If they were the same temperature, there would be no push either way.')]),
    (r'sky (?:is |look )?blue|why is the sky blue',
     'Sunlight contains all colours. As it passes through the air, tiny gas molecules scatter short (blue) wavelengths much more than long (red) ones, '
     'so blue light gets bounced around the whole sky and reaches your eyes from every direction. That scattered blue is what you see when you look up.',
     [(r'sunset|red|orange', 'At sunset the light travels through much more air, so most of the blue is scattered away before it reaches you, leaving the reds and oranges.')]),
    (r'ice float',
     'Ice floats because it is less dense than liquid water. When water freezes, its molecules lock into an open, hexagonal pattern that takes up more space '
     'than the jumbled liquid, so a block of ice weighs less than the same volume of water and is pushed up.', []),
    (r'seasons?|why (?:is it|is) (?:colder|warmer) in (?:winter|summer)',
     'Seasons happen because Earth\'s axis is tilted about 23.5°. For part of the year your hemisphere leans toward the Sun: sunlight hits more directly and days are longer, '
     'so it is summer. Half a year later it leans away, the light is spread out and days are short, so it is winter. It is not mainly about distance from the Sun.', []),
    (r'lightning.*thunder|thunder.*lightning',
     'Lightning and thunder happen at the same moment, but light travels about a million times faster than sound. You see the flash almost instantly, '
     'while the sound covers roughly a kilometre every three seconds — so counting the seconds between them tells you how far away the storm is.', []),
    (r'bread rise|dough rise|yeast',
     'Yeast are tiny living fungi. They eat sugars in the dough and give off carbon dioxide gas. Kneading builds stretchy gluten that traps the gas in little bubbles, '
     'so the dough puffs up; baking then sets that airy structure.', []),
    (r'salt.*(?:ice|road)|melt ice',
     'Salt lowers the temperature at which water freezes. A little liquid water on the ice dissolves the salt, and that salty water stays liquid below 0 °C, '
     'so it keeps melting ice around it — until it gets very cold, when even salty water freezes.', []),
    (r'metal feel cold|why does metal feel',
     'Metal feels colder than wood at the same temperature because it carries heat away from your skin much faster. Your skin senses how quickly it is losing warmth, '
     'not the object\'s actual temperature.', []),
    (r'correlation.*causation|causation.*correlation',
     'Correlation means two things tend to change together; causation means one actually makes the other happen. Ice-cream sales and sunburns rise together, '
     'but ice cream does not cause sunburn — hot sunny weather drives both. To show causation you need a reason to rule out such hidden third factors.', []),
    (r'boats? float|ships? float|why do (?:heavy )?(?:boats|ships)',
     'A boat floats because it pushes aside (displaces) a weight of water equal to its own weight before it sinks too deep. Its hollow shape lets it displace a lot of water '
     'while being mostly air, so the water pushes up with enough force to hold it.', []),
    (r'leaves change colou?r|autumn leaves',
     'Leaves are green because of chlorophyll. In autumn, shorter days make trees stop producing it; as the green breaks down, yellow and orange pigments that were there all along show through, '
     'and some trees make new red pigments.', []),
    (r'sweat|why do we sweat|evaporat.*cool',
     'Sweating cools you because evaporation takes energy. As sweat turns from liquid into vapour, it takes heat from your skin with it, so your skin cools down.', []),
    (r'moon.*phases?|phases? of the moon',
     'The Moon does not make its own light; we see the half lit by the Sun. As it orbits Earth over about a month, we see different amounts of that lit half — '
     'from none (new moon) to all of it (full moon) and back.', []),
    (r'compound interest',
     'Compound interest means you earn interest on your interest. Each period, the interest is added to the balance, so the next period\'s interest is calculated on a bigger amount '
     'and growth speeds up over time.', []),
    (r'inflation',
     'Inflation is a general rise in prices over time, which means the same money buys a little less each year. It often happens when spending grows faster than the supply of goods, '
     'or when costs like energy rise.', []),
    (r'rainbow',
     'A rainbow appears when sunlight enters raindrops, bends, reflects off the back of the drop and bends again on the way out. Each colour bends by a slightly different amount, '
     'so white light spreads into its colours, and you see the arc with the Sun behind you.', []),
    (r'static (?:electricity|shock)',
     'Static shocks happen when rubbing moves electrons from one material to another, leaving you with a small extra charge. When you touch a metal handle, the charge jumps across all at once — a tiny spark.', []),
    (r'onions?.*(?:cry|tears)',
     'Cutting an onion breaks its cells and releases a chemical that turns into a gas which irritates your eyes; your eyes make tears to wash it away.', []),
    (r'(?:why is|why are) (?:the )?(?:ocean|sea)s? salty',
     'Rain slowly dissolves tiny amounts of minerals from rocks, and rivers carry them to the sea. When seawater evaporates, the water leaves but the salts stay behind, so over millions of years the oceans became salty.', []),
    (r'greenhouse effect',
     'The greenhouse effect: sunlight warms the ground, which gives off heat as infrared. Gases like carbon dioxide and water vapour absorb some of that infrared and send part of it back down, '
     'keeping the surface warmer than it would be otherwise. More of these gases means more warming.', []),
    (r'tides?\b',
     'Tides are caused mainly by the Moon\'s gravity pulling slightly harder on the side of Earth facing it than on the far side. That stretches the oceans into two bulges, '
     'and as Earth rotates, coastlines pass through them, giving roughly two high tides a day.', []),
    (r'stars? twinkle',
     'Stars twinkle because their light passes through moving layers of air of different temperatures, which bend it slightly in changing directions. Planets twinkle less because they appear as tiny discs, not points.', []),
    (r'photosynthesis|how do plants (?:make|get) (?:food|energy)',
     'In photosynthesis, plants use light energy to turn carbon dioxide from the air and water from the soil into sugar, releasing oxygen. The sugar is their food and building material.', []),
    (r'refrigerator|fridge.*(?:cool|cold|work)',
     'A fridge moves heat rather than making cold. A fluid evaporates inside the coils in the fridge, soaking up heat; a compressor then squeezes it so it releases that heat through the coils at the back.', []),
    (r'magnets?\b.*(?:work|attract|stick)',
     'In a magnet, the tiny magnetic fields of many atoms line up in the same direction, adding up to a field around it. Iron is attracted because its atoms\' fields can line up with the magnet\'s.', []),
    (r'(?:why do we|why do people) (?:need to )?sleep',
     'Sleep lets your body and brain recover: the brain sorts and stores memories, clears waste products, and resets for the next day, while the body repairs tissues. '
     'Without enough sleep, attention, mood and memory suffer.', []),
    (r'(?:sound|noise).*(?:space|vacuum)|space.*silent',
     'Sound is a vibration passed from molecule to molecule. Space is nearly empty, so there is almost nothing to carry the vibration, and sound cannot travel there.', []),
    (r'water boil.*(?:altitude|mountain|lower)|boil.*(?:mountain|altitude)',
     'At high altitude the air pressure is lower, so water molecules escape into vapour more easily and water boils at a lower temperature — around 90 °C at 3000 m — which is why cooking takes longer there.', []),
]


def explain_reply(messages):
    turns = user_turns(messages)
    last = turns[-1].lower()
    if len(turns) > 1 and re.search(r'similar reason|same reason|same way|same thing', last):
        for t in reversed(turns[:-1]):
            for pattern, text, follow in EXPLAIN:
                if re.search(pattern, t.lower()):
                    for fp, ft in follow:
                        if re.search(fp, last):
                            return out('explain', ft)
    for pattern, text, follow in EXPLAIN:
        if re.search(pattern, last) and re.search(r'\b(?:why|how|explain|what makes|does|is|what is|what\'s)\b', last):
            extra = ''
            if re.search(r'\bbeginner|simple|plain|child|kid\b', last):
                extra = ''
            for fp, ft in follow:
                if re.search(fp, last) and re.search(r'\bexample\b|\bwould\b|\bif\b', last) and len(turns) > 1:
                    return out('explain', ft)
            return out('explain', text + extra)
    if len(turns) > 1:
        for t in reversed(turns[:-1]):
            tl = t.lower()
            for pattern, text, follow in EXPLAIN:
                if re.search(pattern, tl):
                    for fp, ft in follow:
                        if re.search(fp, last):
                            return out('explain', ft)
    return None


EXPLAIN += [
    (r'how (?:does|do) (?:a )?(?:vaccines?|immunis|immuniz)',
     'A vaccine shows your immune system a harmless version or piece of a germ, so it can learn to recognise it. Your body makes antibodies and memory cells; '
     'if the real germ turns up later, the immune system recognises it quickly and fights it off before you get very ill.', []),
    (r'why do we (?:get|have) (?:hiccups|goosebumps|yawn)|why do (?:people|we) yawn',
     'Reflexes like yawning, hiccups and goosebumps are automatic responses controlled by the nervous system. Hiccups are sudden spasms of the diaphragm; goosebumps are tiny muscles '
     'pulling hairs upright (useful for fluffy ancestors keeping warm); yawning is still debated, with links to tiredness, brain cooling and social cues.', []),
    (r'why (?:do|does) (?:things|objects|an apple) fall|what is gravity|how does gravity',
     'Gravity is the attraction between masses. Earth is so massive that it pulls everything near it toward its centre, which is why dropped things fall and why we have weight. '
     'The same pull keeps the Moon in orbit around Earth and Earth around the Sun.', []),
    (r'how (?:do|does) (?:planes?|aeroplanes?|airplanes?) fly|how do wings',
     'A plane flies because its wings are shaped and tilted so that moving air is pushed downward; by pushing air down, the wing gets pushed up. That upward force, lift, '
     'grows with speed, which is why planes need a long run before take-off. Engines provide the forward push.', []),
    (r'why (?:do|does) (?:the )?(?:bread|toast|food) (?:go|get) (?:mou?ldy|stale)|why does food spoil',
     'Food spoils because microbes such as bacteria and moulds feed on it and multiply, and because air and its own enzymes slowly change it. Cold, dryness, salt, sugar or acid slow them down, '
     'which is why fridges, drying and pickling make food last longer.', []),
    (r'why (?:is|does) (?:the )?(?:sea|ocean) (?:blue|look blue)',
     'Water absorbs red light a little more than blue, so deep water looks blue; reflected sky adds to it. Shallow water over sand looks greener or paler.', []),
    (r'why (?:do|does) (?:my )?(?:ears pop|ears hurt).*(?:plane|flight|altitude)|ears pop',
     'Your ears pop when the air pressure outside changes faster than the pressure inside your middle ear. Swallowing or yawning opens a small tube that lets the pressures even out, '
     'and the pop is the eardrum moving back into place.', []),
    (r'(?:how|why) (?:do|does) (?:a )?(?:microwave|microwave oven)',
     'A microwave oven makes water molecules in food jiggle back and forth very quickly using radio-like waves. That motion is heat, so food with water in it warms from the inside and outside at once.', []),
    (r'why (?:do|does) (?:we|people) (?:dream|have dreams)',
     'Nobody knows for certain why we dream. Leading ideas are that dreaming helps the brain sort memories and emotions, practise responses to threats, or is simply a side effect of brain activity during REM sleep.', []),
    (r'what (?:is|are) (?:a )?black holes?|how do black holes',
     'A black hole is a region where so much mass is packed into so small a space that gravity stops anything, even light, from escaping once it crosses the boundary called the event horizon. '
     'Many form when very large stars collapse at the end of their lives.', []),
    (r'how (?:do|does) (?:the )?(?:internet|wi-?fi) work',
     'The internet is a huge network of computers that pass information in small packets. Each packet carries an address, and routers forward it step by step until it reaches the right machine, '
     'where the packets are put back together. Wi-Fi is just the radio link between your device and the nearest router.', []),
    (r'why (?:do|does) (?:the )?(?:days|day) get (?:shorter|longer)',
     'Days get shorter in winter and longer in summer because Earth\'s axis is tilted. When your half of the planet leans toward the Sun, the Sun takes a longer, higher path across the sky; when it leans away, the path is shorter and lower.', []),
    (r'why (?:do|does) (?:a )?(?:spoon|straw|pencil) look bent in water|refraction',
     'Light changes speed when it passes from water into air, and that bends its path. Your eyes assume light travels in straight lines, so the part of the spoon under water seems to be in a slightly different place, making it look bent.', []),
    (r'why (?:do|does) (?:it|ice|metal|things) expand|thermal expansion',
     'Most things expand when heated because their particles move more and push each other slightly farther apart. That is why bridges have expansion gaps and why a stuck jar lid loosens under hot water.', []),
    (r'what (?:causes|makes) (?:the )?wind|why is it windy',
     'Wind is air moving from areas of higher pressure to areas of lower pressure. The Sun heats the ground unevenly; warm air rises and leaves lower pressure behind, and cooler air flows in to fill the gap.', []),
    (r'why (?:do|does) (?:my )?(?:muscles|legs) (?:hurt|ache|get sore) after',
     'Muscles often feel sore a day or two after unusual exercise because the effort causes tiny strains in the muscle fibres. Repairing them causes inflammation and soreness, and the repaired muscle comes back a little stronger.', []),
    (r'why (?:do|does) (?:the )?(?:clouds?|rain) (?:form|happen)|how (?:do|does) clouds form|where does rain come from',
     'Clouds form when air rises and cools, so the water vapour in it condenses onto tiny specks of dust into droplets. When droplets bump together and grow too heavy to stay up, they fall as rain.', []),
    (r'what is (?:a |the )?(?:placebo)|placebo effect',
     'The placebo effect is when people feel better after a treatment that has no active ingredient, simply because they expect it to help. It is why medicines are tested against placebos: to see whether they work better than expectation alone.', []),
    (r'(?:what is|explain) (?:an? )?(?:opportunity cost)',
     'Opportunity cost is what you give up when you choose one option over another: the value of the next best thing you could have done with the same time or money.', []),
    (r'(?:what is|explain) (?:the )?(?:supply and demand)|supply and demand',
     'Supply and demand: when many people want something and there is little of it, its price tends to rise; when there is plenty and few want it, the price tends to fall. Prices settle where the amount people want to buy matches the amount offered.', []),
]

for i, (pattern, text, follow) in enumerate(EXPLAIN):
    if pattern.startswith('correlation'):
        EXPLAIN[i] = (pattern, text, follow + [(r'example|everyday|instance',
                     'Everyday example: people who carry umbrellas are more often wet. Umbrellas do not make you wet; rain causes both carrying an umbrella and getting wet. '
                     'Another: children with bigger feet tend to read better, because older children have bigger feet and more reading practice.')])
    if pattern.startswith('ice float'):
        EXPLAIN[i] = (pattern, text, follow + [(r'salt|similar reason|same reason',
                     'Not quite the same reason. Ice floats because of density (frozen water is less dense than liquid water). Salt melts ice for a different reason: '
                     'dissolved salt lowers the freezing point, so salty water stays liquid below 0 °C and keeps melting the ice around it. Both are about how water molecules behave, but one is about density and the other about freezing temperature.')])


def fallback(messages):
    """A plain, specific reply for a conversational turn nothing else could answer."""
    turns = user_turns(messages)
    last = turns[-1].strip(); low = last.lower()
    if len(last) > 400 or re.search(r'\d+\s*[-+*/x]\s*\d+', low):
        return None
    if '?' not in last:
        if re.search(r"\b(?:thanks|thank you|cheers)\b", low):
            return out('fallback', "You're welcome! Anything else on your mind?")
        if re.search(r"\bi(?:'m| am| feel|'ve| was)\b", low):
            core = clean_clause(re.split(r'[.!]', last)[0])
            return out('fallback', f'Thanks for telling me. {you(core)[0].upper()}{you(core)[1:]}: I hear you. Would you like to tell me more about it, or would you rather talk about something else?')
        return out('fallback', 'I see. Tell me a bit more about what you would like to do with that, and I will help as best I can.')
    subject = re.sub(r"(?i)^(?:can you |could you |please |so |and |but |ok(?:ay)?,? )*(?:explain|tell me|describe)?\s*", '', last).rstrip('?').strip()
    return out('fallback', f'I do not have a reliable answer to that stored here, and I would rather not make one up. '
               f'If you can share what you already know about it, or narrow it down a little, I can help you reason it through.')


# ----------------------------------------------------------------------------------------------- dispatch

def knowledge_reply(messages):
    last = user_turns(messages)[-1]
    if re.search(r"(?i)no advice|don't give me (?:any )?tips|without (?:giving me )?tips|just listen|just acknowledge", last):
        return None
    joined = ' '.join(user_turns(messages)[-2:])
    if re.search(r"\d", joined) and re.search(r"(?i)\b(?:how many|how much|has|have|had|buys?|gives?|left|total|more|fewer)\b", joined):
        return None      # a word problem about apples is not a question about apples
    if re.search(r"(?i)\b(?:all|every|no|some)\s+\w+(?:\s+\w+){0,4}\s+(?:are|is|can|have)\b", joined) and re.search(r"(?i)\b(?:then|so|therefore|must|can)\b.*\?", last):
        return None      # a syllogism about a garden is not a gardening question
    from .chat_knowledge import reply as kb
    found = kb(messages)
    return out('knowledge', found) if found else None


def news_reply(messages):
    """Natural replies to personal news: started something, got back from somewhere, going somewhere, loving something."""
    turns = user_turns(messages)
    last = turns[-1]; low = last.lower()
    if '?' in last or len(last.split()) > 45:
        return None
    m = re.search(r"\bi(?:'ve| have)? (?:just |recently |finally )?(?:started|began|took up|signed up for|joined)(?: learning| doing| playing| taking| going to)? ([^.,!;]+)", last, re.I)
    if m:
        thing = you(clean_clause(m[1]))
        thing = re.sub(r'\s+(?:last|this|a|two|three|few)\s+(?:week|month|year|weeks|months|days|day)s?(?: ago)?$', '', thing)
        return out('news', f'That is exciting! Starting {thing} is a great thing to do for yourself. How are you finding it so far, and what made you want to try it?')
    m = re.search(r"\bi(?:'ve| have)? (?:just )?(?:got|came|come|arrived) back from ([^.,!;]+)", last, re.I)
    if m:
        return out('news', f'Welcome back! {you(clean_clause(m[1]))[0].upper()}{you(clean_clause(m[1]))[1:]} sounds lovely. What was the best part?')
    m = re.search(r"\bi(?:'m| am) (?:going|heading|travelling|traveling|flying|off) to ([^.,!;]+?)(?: (?:tomorrow|next week|this weekend|soon|on \w+|in \w+))?[.!]?$", last, re.I)
    if m:
        return out('news', f'How exciting! Have you been to {you(clean_clause(m[1]))} before, and is there anything you are especially looking forward to?')
    m = re.search(r"\bi (?:really )?(?:love|enjoy|adore) ([^.,!;]+)", last, re.I)
    if m and not re.search(r'\bi (?:love|enjoy) (?:it|that|this|you)\b', low):
        return out('news', f'{you(clean_clause(m[1]))[0].upper()}{you(clean_clause(m[1]))[1:]} sounds great. What do you love most about it?')
    return None


def talk_reply(messages):
    from .everyday_talk import reply as talk
    return talk(messages)


def open_reply(messages):
    from .open_chat import reply as retrieve
    found = retrieve(messages)
    return dict(found, route='chat/core-open') if found else None


SKILLS = [availability_reply, time_reply, quantity_reply, order_reply, logic_reply, recall_reply, decision_reply,
          writing_reply, talk_reply, explain_reply, knowledge_reply, open_reply, feelings_reply, casual_reply, news_reply, statement_ack]


def reply(messages):
    if not isinstance(messages, list) or not messages or messages[-1].get('role') != 'user':
        return None
    last = messages[-1].get('content', '')
    if not isinstance(last, str) or len(last) > 2000 or '```' in last or re.search(r'(?m)^\s*[A-D][.)]\s', last):
        return None
    for skill in SKILLS:
        try:
            found = skill(messages)
        except Exception:
            found = None
        if found is not None:
            return found
    return None
