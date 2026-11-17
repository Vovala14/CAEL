"""Conversation layer added in 0.4.2 (no model, no weights): the turns that made ordinary chats dead-end.

before(): what-if follow-ups that re-solve the earlier problem with one number changed, equal shares, "who has more" after
a transfer, the converse of an "every ..." statement, a two-way weekly split (home / office), moved appointments,
hypothetical questions put to CAEL itself, short messages for any purpose and their rewrites, and replies to a
disappointment that stay with the feeling.

after(): the last pass over the chosen reply: one-word recall answers become sentences, "Tell me more about it!" echoes
become a reply built from what the user said, and a positive template never answers bad news.
"""
import re

from .chat_skills import (DAYS, DAY, NUM, NUM_WORDS, HAS, THERE, answer, cap, day_list, fmt, holdings, last_reply, num,
                          sentences, user_turns, you)

NUMBER = re.compile(r'(?i)(?<![\w.:])(\d+(?:[.,]\d+)?)(?![\d:]|\.\d)|\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|fifty)\b')
STOP = set('a an the and or but if of to in on at for with from by about as is are was were be been being am do does did have has had '
           'i me my we our us you your he she it they them his her their this that these those what which who how when where why '
           'then so too also just really very not no yes will would can could should shall may might must there here now still '
           'than more most less much many some any all each every instead'.split())


def stem(w):
    w = w.lower()
    for end in ('ing', 'ies', 'es', 'ed', 's'):
        if w.endswith(end) and len(w) - len(end) >= 3:
            return w[:-len(end)] + ('y' if end == 'ies' else '')
    return w


def content(text):
    return [w for w in re.findall(r"[a-z][a-z'-]*", text.lower()) if w not in STOP and len(w) > 1]


def stems(text):
    return {stem(w) for w in content(text)}


def turned(s):
    from .chat_memory import turned as t
    return t(s)


def join(items):
    items = list(items)
    return items[0] if len(items) == 1 else ', '.join(items[:-1]) + ' and ' + items[-1]


def out(route, text, kind=''):
    return dict(route='chat/plus-' + route, response=text, sources=[],
                details='Read from the conversation itself (chat_plus.py)' + (f': {kind}' if kind else '') + '.')


def is_question(text):
    last = sentences(text)[-1] if sentences(text) else text
    return '?' in last or bool(re.match(r'(?i)\s*(?:what|who|when|where|why|how|which|is|are|do|does|did|can|could|should|would|will)\b', last))


# ----------------------------------------------------------------------------------------------- 1. what-if follow-ups

WHAT_IF = re.compile(r"(?i)^\s*(?:and|so|but|ok(?:ay)?|now|then|hmm)?,?\s*(?:what|how) (?:if|about)\b|^\s*(?:and|so|but|now|then)?,?\s*(?:if|suppose|say|imagine)\b|"
                     r"\binstead\b|^\s*(?:and|or) (?:with|for|at)\b")


def numbers_in(text):
    found = []
    for m in NUMBER.finditer(text):
        found.append((m.start(), m.end(), m.group(0)))
    return found


def neighbours(text, start, end):
    before = re.findall(r"[A-Za-z']+", text[:start])[-2:]
    after = re.findall(r"[A-Za-z']+", text[end:])[:4]
    return [w.lower() for w in before], [w.lower() for w in after]


def what_if(messages, engine):
    """'And if I save 40 a week instead?': put the new number into the earlier problem and solve that again."""
    turns = user_turns(messages)
    if len(turns) < 2 or engine is None:
        return None
    q = turns[-1].strip()
    if len(q.split()) > 22 or not WHAT_IF.search(q):
        return None
    new = numbers_in(q)
    if len(new) != 1:
        return None
    base_i = next((i for i in range(len(turns) - 2, -1, -1) if re.search(r'\d', turns[i]) and '?' in turns[i]
                   and len(numbers_in(turns[i])) >= 1 and not WHAT_IF.search(turns[i])), None)
    if base_i is None or len(turns) - 1 - base_i > 3:
        return None
    base = turns[base_i]
    old = numbers_in(base)
    qb, qa = neighbours(q, new[0][0], new[0][1])
    skip = {'more', 'extra', 'of', 'the', 'a', 'an', 'only', 'just', 'about', 'instead', 'per', 'each', 'every'}
    period = re.search(r'(?i)\b(?:a|an|per|each|every)\s+(day|week|month|hour|minute|night|evening|year|session|lesson|time)\b', q[new[0][1]:new[0][1] + 40])
    target = None
    unit = next((w for w in qa[:2] if w not in skip and w not in STOP), None)
    cands = []
    for n in old:
        nb, na = neighbours(base, n[0], n[1])
        score = 0
        if unit and any(stem(unit) == stem(w) for w in na[:2]):
            score += 3
        if period and re.search(r'(?i)^\W*(?:[a-z]+\s+){0,2}(?:a|an|per|each|every)\s+' + period[1], base[n[1]:n[1] + 40]):
            score += 3
        if qb and nb and stem(qb[-1]) == stem(nb[-1]) and qb[-1] not in STOP:
            score += 2
        if set(stem(w) for w in qb + qa if w not in STOP and w not in skip) & set(stem(w) for w in nb + na[:3] if w not in STOP):
            score += 1
        cands.append((score, n))
    best = max(cands, key=lambda c: c[0])
    if best[0] == 0 and len(old) > 1:
        return None
    if sum(1 for c in cands if c[0] == best[0]) > 1:
        return None
    target = best[1]
    changed = base[:target[0]] + new[0][2] + base[target[1]:]
    if changed == base:
        return None
    try:
        again = engine.respond([dict(role='user', content=changed)], n=1, seed=0, mode='chat')
    except Exception:
        return None
    said = str(again.get('response', '')).strip()
    route = str(again.get('route', ''))
    if not said or not re.search(r'\d', said) or route.startswith(('chat/web-', 'chat/memory-')) or weak(said):
        return None
    said = said.split('\n\nSource:')[0]
    lead = 'Then ' + said[0].lower() + said[1:] if re.match(r'(?:It|You|There|Each|They|We|That|The)\b', said) else 'In that case: ' + said
    return dict(again, route='chat/plus-what-if', response=lead, sources=again.get('sources', []),
                details=f'The earlier problem solved again with {target[2]} replaced by {new[0][2]} (chat_plus.py).')


# ----------------------------------------------------------------------------------------------- 1b. follow-ups that lean on the last turn

PREP = r'(?:in|on|at|for|with|of|to|from|by|per|about)'


def solve_again(engine, question, lead=''):
    try:
        again = engine.respond([dict(role='user', content=question)], n=1, seed=0, mode='chat')
    except Exception:
        return None
    said = str(again.get('response', '')).strip()
    if not said or weak(said) or str(again.get('route', '')).startswith(('chat/web-closest', 'chat/web-checked-none', 'chat/plus-talk')):
        return None
    return dict(again, route='chat/plus-follow-up', response=lead + said, rewritten=question,
                details=f'The follow-up read as the full question "{question}" (chat_plus.py).')


def last_result(messages):
    prev = last_reply(messages).split('\n\nSource:')[0]
    eq = re.findall(r'=\s*\*{0,2}(-?\d[\d,]*(?:\.\d+)?)', prev)
    bold = re.findall(r'\*\*[^*\d-]*(-?\d[\d,]*(?:\.\d+)?)', prev)
    plain = re.findall(r'(?<![\w.])(-?\d[\d,]*(?:\.\d+)?)(?![\w:])', prev)
    pick = (eq[-1:] or bold[-1:] or plain[-1:])
    return float(pick[0].replace(',', '')) if pick else None


def that_math(messages):
    """'And 20% of that?', 'Double it.', 'What's half of that?', 'Add 5 to that.' on the number CAEL just gave."""
    turns = user_turns(messages)
    if len(turns) < 2:
        return None
    q = turns[-1].strip().lower().rstrip('?.! ')
    if len(q.split()) > 10 or not re.search(r'\b(?:that|it|this|the result|the answer)\b', q):
        return None
    base = last_result(messages)
    if base is None:
        return None
    n = r'(\d+(?:\.\d+)?)'
    show = lambda x: fmt(round(x, 2) if isinstance(x, float) else x)
    m = re.search(n + r'\s*(?:%|percent|per cent) of (?:that|it|this|the result|the answer)$', q)
    if m:
        v = base * float(m[1]) / 100
        return out('math', f"{show(float(m[1]))}% of {show(base)} is **{show(v)}** ({show(base)} × {show(float(m[1]) / 100)} = {show(v)}).", 'percent of result')
    if re.search(r'\b(?:half of (?:that|it|this)|halve (?:that|it)|(?:that|it) halved)$', q):
        return out('math', f"Half of {show(base)} is **{show(base / 2)}**.", 'half')
    m = re.search(r'\b(double|twice|triple|three times|quadruple)\b (?:that|it|this)$', q)
    if m:
        k = {'double': 2, 'twice': 2, 'triple': 3, 'three times': 3, 'quadruple': 4}[m[1]]
        return out('math', f"That makes **{show(base * k)}** ({show(base)} × {k}).", 'multiple')
    m = re.search(r'\b(?:add|plus) ' + n + r' (?:to (?:that|it|this))?$|\b(?:that|it) plus ' + n + r'$', q)
    if m:
        k = float(m[1] or m[2])
        return out('math', f"That makes **{show(base + k)}** ({show(base)} + {show(k)}).", 'sum')
    m = re.search(r'\b(?:subtract|take|minus) ' + n + r' (?:from|off) (?:that|it|this)$|\b(?:that|it) minus ' + n + r'$', q)
    if m:
        k = float(m[1] or m[2])
        return out('math', f"That leaves **{show(base - k)}** ({show(base)} − {show(k)}).", 'difference')
    m = re.search(r'\b(?:that|it) (?:times|multiplied by) ' + n + r'$|\bmultiply (?:that|it) by ' + n + r'$', q)
    if m:
        k = float(m[1] or m[2])
        return out('math', f"That makes **{show(base * k)}** ({show(base)} × {show(k)}).", 'product')
    m = re.search(r'\b(?:that|it) divided by ' + n + r'$|\bdivide (?:that|it) by ' + n + r'$|\bsplit (?:that|it) (?:between|among|by) ' + n, q)
    if m:
        k = float(m[1] or m[2] or m[3])
        return out('math', f"That gives **{show(base / k)}** ({show(base)} ÷ {show(k)}).", 'quotient') if k else None
    return None


def example_sentence(messages):
    """'Can you use it in a sentence?' after a dictionary definition that came with an example."""
    turns = user_turns(messages)
    if len(turns) < 2 or not re.search(r'(?i)\b(?:use|put) (?:it|that|the word|this)\b.*\bsentence\b|\bexample sentence\b|\bin a sentence\b', turns[-1]):
        return None
    prev = last_reply(messages)
    word = re.search(r'\*\*([A-Za-z-]+)\*\*', prev)
    ex = re.search(r'Example: "([^"]+)"', prev)
    if ex and word:
        text = ex[1].strip()
        text = text[0].upper() + text[1:] + ('' if text.endswith(('.', '!', '?')) else '.')
        return out('example', f"Sure. For example: \"{text}\" Here *{word[1]}* means the same as in the first definition above.", 'dictionary example')
    return None


def anchored(messages, engine):
    """Short follow-ups that only make sense with the previous question: 'And good morning?', 'What about New Zealand?',
    'Can you give me an example?', 'Can you explain that more simply?'. The full question is rebuilt and answered."""
    turns = user_turns(messages)
    if len(turns) < 2 or engine is None:
        return None
    q = turns[-1].strip()
    prev_q = next((t for t in reversed(turns[:-1]) if '?' in t or re.match(r'(?i)\s*(?:explain|tell me|describe|what|how|why)\b', t)), None)
    if not prev_q or len(q.split()) > 9:
        return None
    prev_last = sentences(prev_q)[-1].strip()
    try:
        from .web_check import query as wq
        terms, key, kind, own, need, subject = wq([m for m in messages[:-1]])
    except Exception:
        key, subject = None, None
    about = (subject or key or '').strip()
    low = q.lower().rstrip('?.! ')
    if about:
        if re.fullmatch(r"(?:can|could) you (?:give|show) (?:me )?(?:an|one|another|some) examples?|(?:an )?example|for example|like what|such as", low):
            return solve_again(engine, f"What is an example of {about}?")
        if re.fullmatch(r"(?:can|could) you (?:explain|say|put) (?:that|it|this) (?:more simply|in simple(?:r)? (?:terms|words)|simpler|like i'?m five|more clearly)|"
                        r"(?:in )?simpler (?:terms|words)(?: please)?|eli5|i don'?t (?:get|understand)(?: it| that)?", low):
            return solve_again(engine, f"What is {about} in simple terms?")
    m = re.match(r"(?i)\s*(?:and|or|ok,? and|so|but)?\s*(?:what|how) about (.+?)\??$", q) or re.match(r"(?i)\s*(?:and|or) (.+?)\?$", q)
    if not m:
        return None
    new = m[1].strip()
    if re.search(r'(?i)\b(?:you|your|me|my|i|we)\b', new) or NUMBER.search(new) and WHAT_IF.search(q) and re.search(r'\d', prev_last):
        return None
    rebuilt = None
    pm = re.match(r'(?i)(' + PREP + r')\s+(.+)$', new)
    if pm:
        spots = list(re.finditer(r'(?i)\b' + pm[1] + r'\s+(?:(?:a|an|the|my|our)\s+)?[\w\' -]+?(?=\s+(?:' + PREP + r')\b|[?,.]|$)', prev_last))
        if spots:
            s = spots[-1]
            rebuilt = prev_last[:s.start()] + new + prev_last[s.end():]
    if rebuilt is None:
        say = re.search(r"(?i)\b(say|spell|pronounce|write|translate) (.+?) (in|into) ([A-Z][a-z]+)", prev_last)
        if say:
            rebuilt = prev_last[:say.start(2)] + new + prev_last[say.end(2):]
    if rebuilt is None and re.match(r'[A-Z]', new):
        names = [x for x in re.finditer(r"\b[A-Z][\w'-]*(?:\s+[A-Z][\w'-]*)*", prev_last) if x.start() > 0]
        if names:
            s = names[-1]
            rebuilt = prev_last[:s.start()] + new + prev_last[s.end():]
    if rebuilt is None:
        nouns_prev = re.search(r"(?i)\b(?:a|an|the)\s+([a-z]+(?: [a-z]+)?)\s*\??$", prev_last)
        if nouns_prev and len(new.split()) <= 3:
            rebuilt = prev_last[:nouns_prev.start(1)] + re.sub(r'(?i)^(?:a|an|the)\s+', '', new) + '?'
    if not rebuilt or rebuilt.strip().lower() == prev_last.lower():
        return None
    rebuilt = rebuilt.strip()
    if not rebuilt.endswith('?'):
        rebuilt += '?'
    return solve_again(engine, rebuilt)


# ----------------------------------------------------------------------------------------------- 2. equal shares

PEOPLE = (r"(?:(" + NUM[1:-1] + r") of us|the (" + NUM[1:-1] + r") of us|(?:between|among|amongst) (?:the )?(" + NUM[1:-1] +
          r")(?: (?:people|friends|of us|kids|children|persons|ways|guests|students|players|housemates|flatmates|roommates|siblings|colleagues|coworkers))?"
          r"|(" + NUM[1:-1] + r") (?:people|friends|kids|children|persons|guests|students|players|housemates|flatmates|roommates|siblings|colleagues|coworkers)"
          r"|me and (?:my )?(" + NUM[1:-1] + r") (?:friends|kids|children|siblings|colleagues|coworkers|housemates|flatmates|roommates|brothers|sisters))")
MONEY = r'(?:euros?|dollars?|pounds?|€|\$|£|bucks|quid|francs?|kr|yen|rupees?|pesos?)'


def shares(messages):
    turns = user_turns(messages)
    q = turns[-1]
    base_i = next((i for i in range(len(turns) - 1, -1, -1)
                   if re.search(r'(?i)\b(?:shar\w+|split\w*|divid\w+|distribut\w+)\b', turns[i]) and re.search(r'(?i)\bhow (?:many|much)\b|\beach\b', turns[i])
                   and re.search(r'\d|\b(?:two|three|four|five|six)\b', turns[i])), None)
    if base_i is None or len(turns) - 1 - base_i > 2:
        return None
    base = turns[base_i]
    pm = re.search(r'(?i)\b' + PEOPLE, base)
    if not pm:
        return None
    grp = next(g for g in pm.groups() if g)
    people = num(grp) + (1 if pm.group(0).lower().startswith('me and') else 0)
    rest = base[:pm.start()] + ' ' + base[pm.end():]
    ask = re.search(r'(?i)\bhow (?:many|much) ([a-z]+)?', base)
    item = (ask[1] or '').lower() if ask else ''
    aux = item in ('does', 'do', 'should', 'will', 'is', 'are', 'would', 'can', 'did', 'each', 'money', 'per')
    money_asked = aux and bool(re.search(r'(?i)\bhow much\b', base))
    if aux:
        item = ''
    money = re.search(r'(?i)(€|\$|£)\s?(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s?(' + MONEY + r')\b', rest)
    total, per, container, count = None, None, None, 1
    if money and (money_asked or re.fullmatch(MONEY, item or '-') or (not item and not re.search(r'(?i)\bhow many\b', base))):
        total = num(money[2] or money[3])
        unit = money[1] or money[4]
    else:
        pieces = None
        for m in re.finditer(r'(?i)(' + NUM[1:-1] + r') ([a-z]+)', rest):
            w = m[2].lower()
            if item and stem(w) == stem(item) or (not item and w not in STOP and w not in ('of', 'people', 'friends', 'kids')):
                pieces = m
                if item:
                    break
        if not pieces:
            return None
        total = num(pieces[1])
        item = pieces[2].lower()
        unit = None
        cm = re.search(r'(?i)\b(?:(an?|one|two|three|four|five|six|\d+) )?([a-z]+?)s? (?:is |are |was |were )?(?:each )?(?:cut|sliced|divided|split) into', rest)
        if cm:
            container = cm[2].lower()
            count = num(cm[1]) if cm[1] else 1
            per = total
            total = per * count
    later = turns[base_i + 1:]
    note = ''
    for t in later:
        if not (WHAT_IF.search(t) or re.search(r'(?i)\b(?:another|second|third|more|extra)\b', t)):
            return None
        changed = False
        if container and re.search(r'(?i)\b' + container, t):
            c = re.search(r'(?i)\b(?:a |one )?(second|another|third|fourth|extra|one more)\b|\b(' + NUM[1:-1] + r') (?:more )?' + container, t)
            if c:
                if c[1]:
                    count = {'second': 2, 'another': count + 1, 'third': 3, 'fourth': 4, 'extra': count + 1, 'one more': count + 1}[c[1].lower()]
                else:
                    count = num(c[2]) + (count if re.search(r'(?i)\bmore\b', c.group(0)) else 0)
                total = per * count
                note = f"{fmt(count)} {container}s make {fmt(per)} × {fmt(count)} = {fmt(total)} {item}. "
                changed = True
        p2 = re.search(r'(?i)\b' + PEOPLE, t)
        if p2 and not changed:
            people = num(next(g for g in p2.groups() if g)) + (1 if p2.group(0).lower().startswith('me and') else 0)
            changed = True
        more_people = re.search(r'(?i)\b(' + NUM[1:-1] + r'|another|one more) (?:more )?(?:friends?|people|person|guests?|kids?)\b.*\b(?:join|come|arrive|show)', t)
        if more_people and not changed:
            people += 1 if more_people[1].lower() in ('another', 'one more') else num(more_people[1])
            changed = True
        if not changed:
            return None
    if not people or people < 2 or total is None:
        return None
    if unit:
        each = total / people
        sym = unit if len(unit) == 1 else ''
        word = '' if sym else ' ' + unit
        val = f'{each:.2f}'.rstrip('0').rstrip('.') if abs(each - round(each)) > 1e-9 else fmt(round(each))
        return out('shares', f"{note}Each person pays **{sym}{val}{word}** ({sym}{fmt(total)}{word} ÷ {fmt(people)} = {sym}{val}{word}).", 'money')
    if isinstance(total, float) and total != int(total):
        return None
    total = int(total)
    whole, left = divmod(total, int(people))
    if left == 0:
        return out('shares', f"{note}Each person gets **{whole} {item}** ({total} ÷ {fmt(people)} = {whole}).", 'even')
    from math import gcd
    g = gcd(left, int(people))
    frac = f'{left // g}/{int(people) // g}'
    exact = f'{whole} and {frac}' if whole else frac
    return out('shares', f"{note}{total} ÷ {fmt(people)} doesn't come out even: each person gets **{whole} whole {item}**, with {left} left over. "
                         f"If you share the leftover too, that's {exact} {item} each (about {total / people:.2f}).", 'remainder')


# ----------------------------------------------------------------------------------------------- 3. who has more

def who_has_more(messages):
    turns = user_turns(messages)
    ask = sentences(turns[-1])[-1]
    m = re.search(r"(?i)\bwho (?:has|will have|would have|ends up with|is left with|now has|then has)\b.*\b(more|most|fewer|less|fewest|least)\b|"
                  r"\b(?:do|does|will|would) (?:they|we|both)\b.*\b(?:same|equal)\b|\bwho(?:'s| is) ahead\b", ask)
    if not m:
        return None
    first = next((i for i, t in enumerate(turns) if HAS.search(t) or THERE.search(t)), None)
    if first is None:
        return None
    h = holdings(turns[first:])
    if h is None or len(h.count) < 2 or h.mixed or any(v < 0 for v in h.count.values()):
        return None
    item = h.item or ''
    names = {k: (h.label[k] if h.label[k].lower() != 'i' else 'you') for k in h.count}
    listing = join(f"{cap(names[k])} has {fmt(v)}" for k, v in h.count.items())
    steps = f" ({'; '.join(h.steps[-2:])})" if h.steps else ''
    top = max(h.count.values())
    low = min(h.count.values())
    if top == low:
        return out('compare', f"They have the same: {listing}{steps}.", 'equal')
    want_less = m[1] and m[1].lower() in ('fewer', 'less', 'fewest', 'least')
    pick = [k for k, v in h.count.items() if v == (low if want_less else top)][0]
    word = 'fewer' if want_less else 'more'
    lead = 'After that, ' if h.steps else ''
    return out('compare', f"**{cap(names[pick])}** has {word}{(' ' + item) if item else ''}. {lead}{listing}{steps}, a difference of {fmt(top - low)}.", 'more')


# ----------------------------------------------------------------------------------------------- 4. the converse of "every ..."

EVERY = re.compile(r"(?i)\b(?:every|all(?: of)?(?: the| my| our)?|each(?: of the)?) ([^.?!,]{3,80}?) (is|are|has|have|was|were|can|must|will|gets?|needs?|likes?|"
                   r"lives?|works?|wears?|speaks?|plays?|owns?|eats?)\b ?([^.?!]*)")


def plural(phrase):
    """'dog in the shelter' -> 'dogs in the shelter'; 'books on the top shelf' stays."""
    words = phrase.split()
    if not words:
        return phrase
    i = max(next((k for k, w in enumerate(words) if w.lower() in ('in', 'on', 'at', 'from', 'of', 'with', 'who', 'that')), len(words)) - 1, 0)
    w = words[i]
    if not w.endswith('s'):
        words[i] = w[:-1] + 'ies' if w.endswith('y') and w[-2:-1] not in 'aeiou' else w + ('es' if w.endswith(('ch', 'sh', 'x')) else 's')
    return ' '.join(words)


def member(messages):
    """'All the books on the top shelf are novels. This book is on the top shelf. Is it a novel?'"""
    turns = user_turns(messages)
    q = sentences(turns[-1])[-1]
    if not re.match(r"(?i)\s*(?:so |then |and )?(?:is|are|does|do|has|have|can|must|will|did|was)\b", q) or re.search(r"(?i)\b(?:every|all|each|any|only)\b", q):
        return None
    text = ' '.join(turns)
    facts = [s for t in turns for s in sentences(t) if '?' not in s]
    for rule in EVERY.finditer(text):
        cat = stems(rule[1]) - {'thing', 'one'}
        pred = stems((rule[2] if rule[2].lower() not in ('is', 'are', 'was', 'were', 'has', 'have') else '') + ' ' + (rule[3] or ''))
        if not cat or not pred or not (pred & stems(q)):
            continue
        for s in facts:
            if rule.group(0).strip() in s:
                continue
            if cat <= stems(s) and not re.search(r"(?i)\b(?:not|isn't|never|no longer|aren't)\b", s):
                told = you(rule.group(0).strip())
                told = told[0].lower() + told[1:]
                fact = you(s.strip().rstrip('.!'))
                if fact.split()[0] in ('This', 'That', 'My', 'Your', 'The', 'It', 'One'):
                    fact = fact[0].lower() + fact[1:]
                return out('logic', f"Yes. You said {told}, and {fact}, so it follows directly.", 'member')
    return None


def member_late(messages):
    from . import chat_skills
    return None if chat_skills.syllogism(messages) is not None else member(messages)


def converse(messages):
    turns = user_turns(messages)
    if len(turns) < 2:
        return None
    q = sentences(turns[-1])[-1]
    m = re.match(r"(?i)\s*(?:so |and |then |but )?(?:does (?:that|this|it) (?:also )?mean(?: that)?|so|is it (?:also )?true that|can (?:we|i|you) (?:then )?(?:say|conclude)(?: that)?|"
                 r"would (?:that|it) mean(?: that)?|does it follow that|is it right that|must it be(?: true)? that)\s+(.+?)\??\s*$", q)
    if not m:
        return None
    claim = m[1].strip().rstrip('?. ')
    inv = re.match(r"(?i)(is|are|does|do|has|have|must|can|was|were) ((?:every|all|each)\b.+)$", claim)
    if inv:
        claim = inv[2] + ' ' + inv[1].lower()          # "is every novel on the top shelf": the same words, order aside
    cm = EVERY.search(claim) or re.search(r"(?i)\b(?:every|all|each) ((?:[a-z]+ ?){1,3})()()", claim) or re.search(r"(?i)\b(?:any|anything|anyone|everyone|everything)(?: that| who| which)? ()([a-z]+)\b ?(.*)", claim)
    if not cm:
        return None
    for t in reversed(turns[:-1]):
        for rule in EVERY.finditer(t):
            rule_text = rule.group(0).strip()
            if stems(rule_text) == stems(cm.group(0)) and stems(rule[1]) == stems(cm[1]):
                continue            # the same statement repeated: the earlier answer stands
            shared = stems(rule_text) & stems(claim)
            if len(shared) < 2 or len(shared) < 0.6 * len(stems(claim)):
                continue
            # the claim's subject uses words from the rule's predicate: the direction is reversed
            if not (stems(cm[1]) & stems(rule[3] or rule[2])):
                continue
            told = you(rule_text)
            told = told[0].lower() + told[1:]
            claim_you = you(m[1].strip().rstrip('?. '))
            return out('logic', f"No, that doesn't follow. You said {told}, and that only works in one direction: it tells us about "
                                f"every one of the {plural(you(rule[1].strip()))}, and nothing about anything else. The reverse"
                                + ('' if inv else f' ("{claim_you}")') + " could be false without contradicting what you said.", 'converse')
    return None


# ----------------------------------------------------------------------------------------------- 5. a week split two ways

SPLIT = re.compile(r"(?i)\b(?:i|we) (.+?) (?:on|every) (" + DAY + r"(?:(?:,\s*|\s+and\s+|\s*&\s*|,\s*and\s+)" + DAY + r")*),? (?:and|but|while|then)(?: i| we)? (.+?) "
                   r"(?:on )?(?:(?:all )?the (?:other|remaining|rest of the)|every other|the other)\s*(?:week)?(?:days?)?(?: of the week)?\b")
WEEKDAYS = DAYS[:5]


def week_split(messages):
    turns = user_turns(messages)
    if len(turns) < 2:
        return None
    base_i = next((i for i in range(len(turns) - 1) if SPLIT.search(turns[i])), None)
    if base_i is None:
        return None
    m = SPLIT.search(turns[base_i])
    a_text, b_text = m[1].strip(), m[3].strip()
    a_days = set(day_list(m[2]))
    pool = WEEKDAYS if a_days <= set(WEEKDAYS) else DAYS
    b_days = set(pool) - a_days
    a_stem, b_stem = stems(a_text), stems(b_text)
    changes = []
    for t in turns[base_i + 1:-1]:
        for s in sentences(t):
            days = day_list(s)
            if not days:
                continue
            ss = stems(s)
            to_a = len(ss & (a_stem - b_stem))
            to_b = len(ss & (b_stem - a_stem))
            off = re.search(r"(?i)\b(?:day off|holiday|off work|on leave|not working|sick|public holiday|bank holiday|taking .* off)\b", s)
            for d in days:
                if off:
                    a_days.discard(d); b_days.discard(d); changes.append(f'{d.capitalize()} is off')
                elif to_a > to_b:
                    b_days.discard(d); a_days.add(d); changes.append(d)
                elif to_b > to_a:
                    a_days.discard(d); b_days.add(d); changes.append(d)
    q = sentences(turns[-1])[-1]
    qs = stems(q)
    if not re.search(r"(?i)\b(?:which|what|how many) days?\b|\bwhen (?:am|do|will) i\b|\b(?:am|do|will) i\b.*\bon " + DAY, q):
        return None
    want_a = len(qs & (a_stem - b_stem))
    want_b = len(qs & (b_stem - a_stem))
    if want_a == want_b:
        return None
    mine, other = (a_days, b_days) if want_a > want_b else (b_days, a_days)
    mine_text, other_text = (a_text, b_text) if want_a > want_b else (b_text, a_text)
    order = lambda ds: [d.capitalize() for d in DAYS if d in ds]
    asked = day_list(q)
    week = ' this week' if re.search(r'(?i)\bthis week\b', ' '.join(turns[base_i + 1:])) else ''
    if asked and not re.search(r'(?i)\b(?:which|what|how many) days?\b', q):
        d = asked[0]
        if d in mine:
            return out('week', f"Yes, on {d.capitalize()} you {you(mine_text)}{week}.", 'day')
        return out('week', f"No, on {d.capitalize()} you {you(other_text) if d in other else 'have neither'}{week}.", 'day')
    if not mine:
        return out('week', f"None{week}: you {you(other_text)} on {join(order(other))}.", 'none')
    count = f" That's {len(mine)} day{'s' if len(mine) != 1 else ''}." if re.search(r'(?i)\bhow many\b', q) else ''
    return out('week', f"**{join(order(mine))}**{week}.{count} You {you(other_text)} on {join(order(other))}"
                       f"{week}, which leaves {join(order(mine))} as the day{'s' if len(mine) != 1 else ''} you {you(mine_text)}.", 'split')


# ----------------------------------------------------------------------------------------------- 6. moved appointments

CLOCK_T = r"(?:\d{1,2}(?::\d{2})?\s?(?:am|pm|a\.m\.|p\.m\.)|\d{1,2}:\d{2}|noon|midday|midnight|half past \w+|quarter (?:past|to) \w+)"
MONTH = r"(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)"
WHEN = re.compile(r"(?i)\b(?:(?:on |this |next |for )?(?:(?:mon|tues|wednes|thurs|fri|satur|sun)day|tomorrow|today|tonight|(?:the )?\d{1,2}(?:st|nd|rd|th)?(?: of)? " + MONTH +
                  r"|" + MONTH + r" \d{1,2}(?:st|nd|rd|th)?|the \d{1,2}(?:st|nd|rd|th))(?: (?:morning|afternoon|evening))?(?: (?:at|around|from) " + CLOCK_T + r")?|(?:at|around|to|for) " + CLOCK_T + r")")
EVENT = r"(appointment|meeting|interview|lesson|class|session|booking|reservation|flight|train|exam|test|check-?up|visit|call|dinner|lunch|party|delivery|viewing|haircut|shift|match|game|rehearsal|deadline|trip)"
MOVED = re.compile(r"(?i)\b(?:moved|rescheduled|changed|pushed|shifted|postponed|brought forward|put back|switched|now|instead|delayed)\b")


def when_text(s):
    found = [m.group(0) for m in WHEN.finditer(s)]
    if not found:
        return None
    text = ' '.join(found)
    text = re.sub(r'(?i)^(?:to|for) (?=\d|noon|midday|midnight|half|quarter)', 'at ', text)
    text = re.sub(r'(?i)^(?:for|this) (?=(?:mon|tues|wednes|thurs|fri|satur|sun)day)', 'on ', text)
    if re.match(r'(?i)(?:mon|tues|wednes|thurs|fri|satur|sun)day|' + MONTH + r'|the \d|\d', text):
        text = 'on ' + text
    return re.sub(r'(?i)\b((?:mon|tues|wednes|thurs|fri|satur|sun)day)\b', lambda m: m[1].capitalize(), text)


def appointment(messages):
    turns = user_turns(messages)
    if len(turns) < 2:
        return None
    q = sentences(turns[-1])[-1]
    m = re.search(r"(?i)\b(?:when|what time|what day)(?:'s| is| was| are)? (?:is |was |are )?(?:my|our|the) ((?:[a-z'-]+ ){0,3}?" + EVENT + r")\b", q)
    if not m:
        return None
    thing = m[1].lower().strip()
    key = stems(thing)
    history, current = [], False
    for t in turns[:-1]:
        for s in sentences(t):
            about = re.search(r"(?i)\b(?:my|our|the) (?:[a-z'-]+ ){0,3}?" + EVENT, s)
            w = when_text(s)
            if about and key & stems(about.group(0)):
                current = True
                if w:
                    history.append(w)
            elif current and w and (MOVED.search(s) or re.search(r"(?i)\b(?:it|they|that)\b", s)) and not re.search(
                    r"(?i)\b(?:my|our) (?:[a-z'-]+ ){0,3}?" + EVENT, s):
                history.append(w)
            elif about:
                current = False
    if not history:
        return None
    owner = 'our' if re.search(r'(?i)\bour\b', m.group(0)) else 'your'
    if len(history) == 1:
        return out('appointment', f"{cap(owner)} {thing} is **{history[-1]}**.", 'when')
    return out('appointment', f"{cap(owner)} {thing} is now **{history[-1]}**. It was moved from {re.sub(r'^on ', '', history[-2])}.", 'moved')


# ----------------------------------------------------------------------------------------------- 7. hypotheticals put to CAEL

HYPO = [
    (r'\b(?:visit|travel|go|fly|trip|holiday|vacation)\b.*\b(?:country|countries|place|anywhere|city|where|world)\b|\bwhere would you (?:go|travel|visit)\b',
     "I can't travel, of course, but if I could, I'd pick Japan: the food, trains that run to the second, and quiet temples a few streets "
     "away from neon signs. Where would you go?",
     dict(first="Eat first! A bowl of ramen at a tiny counter shop, then a slow walk through an old neighbourhood to take it all in. "
                "What's the first thing you like to do in a new place?",
          why="Mostly the contrast: very old and very new sitting side by side, and a food culture where even a small snack is made with care. "
              "What draws you to the places you'd pick?")),
    (r'\bsuper ?power\b|\bsuperhero\b',
     "Teleportation, easily. No commutes, breakfast in Lisbon, a walk in Kyoto, home by evening. Which one would you choose?",
     dict(first="Skip every queue I can think of, then go and watch a sunrise somewhere far away.",
          why="It's the one power that gives you more time, and time is the thing everyone runs short of.")),
    (r'\b(?:dinner|lunch|coffee|meet|talk to|conversation)\b.*\b(?:anyone|anybody|any person|someone|historical|dead or alive|famous)\b',
     "Ada Lovelace. She saw in the 1840s that a calculating machine could do more than arithmetic, and I'd love to ask what she'd make of "
     "today's computers. Who would you pick?",
     dict(first="I'd ask what she imagined machines would be doing in two hundred years, then compare notes.",
          why="She described programming before there was a computer to run it on. That's a rare kind of imagination.")),
    (r'\btime (?:travel|machine)\b|\b(?:any|another|a different) (?:era|period|century|decade|time in history)\b|\bgo back in time\b',
     "July 1969, to watch the first Moon landing as it happened, with everyone crowded around a small television. When would you go?",
     dict(first="Find a room full of people watching the broadcast and just take in the silence before the first step.",
          why="It's one of the few moments when most of the world was looking at the same thing and hoping for the same outcome.")),
    (r'\blive (?:anywhere|in any)\b|\bwhere would you (?:live|settle)\b|\bmove (?:anywhere|to any)\b',
     "A small town by the sea, somewhere like the coast of Portugal: mild weather, good bread, and the sound of water. How about you?",
     dict(first="Find the best bakery and learn the walk to the beach.",
          why="Quiet, light and the sea are a good combination for thinking clearly.")),
    (r'\b(?:be|become|turn into)\b.*\bany(?: kind of)? animal\b|\bwhat animal would you\b|\bwhich animal would you\b',
     "An otter. They're clever, they play a lot, and they float on their backs holding hands so they don't drift apart. What would you be?",
     dict(first="Slide down a muddy riverbank, obviously.", why="They seem to have found a good balance between work and play.")),
    (r'\b(?:learn|master|play)\b.*\bany (?:instrument|skill|language|sport|talent)\b|\bwhat (?:skill|instrument|language) would you\b',
     "The cello. It sounds closest to a human voice, and I'd love to be able to play one of Bach's cello suites. What would you learn?",
     dict(first="Learn to hold the bow properly, which I'm told takes longer than anyone expects.",
          why="It's warm and deep without being loud. That appeals to me.")),
    (r'\bany job\b|\bdream job\b|\bwhat job would you\b|\bany career\b|\bwhat would you (?:be|do) if you (?:were|weren\'t|could be) (?:human|a person|not an assistant)\b',
     "A librarian in a big old library: helping people find exactly the thing they were looking for is close to what I enjoy already. What's yours?",
     dict(first="Learn where everything is, then find the strangest book on the shelves.",
          why="I like the moment when someone finds what they needed. A library is full of those.")),
    (r'\b(?:eat|have)\b.*\b(?:one|only one|a single|same) (?:food|meal|dish)\b|\bfor the rest of your life\b.*\b(?:eat|food|meal)\b|\blast meal\b',
     "I don't eat, but if I did: fresh bread with good butter. Simple, and it never gets boring. What would yours be?",
     dict(first="Start with the crust.", why="The best foods are often the simplest ones done well.")),
    (r'\b(?:won|win) the lottery\b|\ba million (?:dollars|euros|pounds)\b|\bunlimited money\b',
     "I'd fund libraries and free courses, the things that let people teach themselves. And I'd keep a little for a very good telescope. "
     "What would you do with it?",
     dict(first="Set aside enough that it could keep doing good for a long time, not just once.",
          why="Access to knowledge changes what people can do for themselves. It pays back many times over.")),
    (r'\b(?:one|three|a|any) wish(?:es)?\b|\bgenie\b',
     "One wish: that everyone had enough time for the people and things they care about. What would you wish for?",
     dict(first="Probably double-check the wording. Wishes have a reputation.", why="Most regrets seem to be about time.")),
    (r'\bdesert(?:ed)? island\b|\bstranded\b',
     "A good knife, a solar-powered e-reader full of books, and a very large hat. What would you bring?",
     dict(first="Find fresh water and shade, then start on the reading list.", why="Something useful, something for the mind, something for the sun.")),
    (r'\b(?:fictional|book|movie|film|story) (?:world|universe|character)\b|\blive in any (?:book|movie|film|story|game)\b',
     "The Shire from The Lord of the Rings: gardens, second breakfast, and no hurry. Which world would you choose?",
     dict(first="Second breakfast.", why="It's a place where an ordinary quiet day is treated as something worth protecting.")),
    (r'\bchange (?:one|a single|any|1) thing\b|\bsolve (?:one|any) problem\b|\bfix (?:one|any) (?:thing|problem)\b',
     "I'd make clear, trustworthy information easy for everyone to reach. A lot of problems get smaller once people can find out what's true. "
     "What would you change?",
     dict(first="Start with health information, where a clear answer matters most.", why="Good decisions depend on good information.")),
    (r'\binvent\b', "A reliable way to pause a moment and come back to it later. Failing that, a pen that never gets lost. What would you invent?",
     dict(first="Test the pen. It's the more realistic of the two.", why="Small annoyances add up; fixing one helps a lot of people a little.")),
    (r'\btalk to animals\b|\bspeak (?:to|with) animals\b', "Yes, and I'd start with cats. I want to know what they're thinking when they stare at the wall. Would you?",
     dict(first="Ask a cat about the staring.", why="They always look like they know something.")),
    (r'\b(?:any|a) (?:pet|animal as a pet)\b', "A calm old dog who likes slow walks. What about you?",
     dict(first="Go for a slow walk, naturally.", why="Good company and a reason to go outside every day.")),
    (r'\b(?:any|one) (?:book|novel)\b.*\b(?:read|again|first time)\b', "I'd read The Hitchhiker's Guide to the Galaxy for the first time again. Which book would you pick?",
     dict(first="Laugh at the first page.", why="It's funny and kind at the same time, which is rarer than it sounds.")),
    (r'\b(?:day off|free day|perfect day|ideal day|free weekend|whole day free)\b',
     "A slow morning with coffee smells and a good book, a long walk somewhere green, and a conversation with someone curious in the evening. "
     "What does your perfect day look like?",
     dict(first="Take the slow morning seriously.", why="Days with no rush leave room for good thinking.")),
    (r'\b(?:any|one) (?:season|month|weather)\b', "Autumn: the colours, the crisp air, and the excuse for soup and a good book. Which would you choose?",
     dict(first="Go for a walk through the leaves.", why="It's the season that makes staying in feel earned.")),
]
HYPO_Q = re.compile(r"(?i)\bif you (?:could|were|had|won|got)\b|\bwould you rather\b|\b(?:what|where|who|which|when)\b[^.?!]{0,40}\bwould you\b|\bwhat(?:'s| is) your (?:dream|ideal|perfect)\b|"
                    r"\bimagine you (?:could|were|had)\b|\bsuppose you (?:could|were|had)\b")


def hypothetical(messages):
    turns = user_turns(messages)
    q = turns[-1].strip()
    if len(q.split()) > 40:
        return None
    prev = last_reply(messages)
    hit = next((h for h in HYPO if h[1] == prev.strip()), None) if prev else None
    if hit and len(q.split()) <= 12:
        if re.search(r'(?i)\b(?:first|start|begin)\b', q) and re.search(r'(?i)\bwhat\b|\bwhere\b', q):
            return out('hypothetical', hit[2]['first'], 'follow-up')
        if re.match(r'(?i)\s*(?:oh,? |and |but |interesting,? |nice,? |cool,? )?(?:why|how come|what makes you|what made you)\b', q):
            return out('hypothetical', hit[2]['why'], 'follow-up')
    if not HYPO_Q.search(q) or '?' not in q:
        return None
    if re.search(r"(?i)\bif you (?:could|can) (?:help|tell|explain|give|show|write|check|find|recommend|suggest|summari[sz]e|translate)\b", q):
        return None             # a polite request, not a hypothetical
    low = q.lower()
    for pattern, reply, _ in HYPO:
        if re.search(pattern, low):
            return out('hypothetical', reply, 'persona')
    rather = re.search(r"(?i)\bwould you rather (.+?) or (.+?)\?", q)
    if rather:
        a = rather[1].strip()
        return out('hypothetical', f"Tough one! I'd go with the first: to {a}. It sounds like the option I'd regret less. Which would you pick, and why?", 'rather')
    return None


# ----------------------------------------------------------------------------------------------- 8. short messages for any purpose

WRITE = re.compile(r"(?i)\b(?:write|draft|compose|create|prepare|make|give me|help me (?:write|draft|word)|can you (?:write|draft)|could you (?:write|draft)|"
                   r"i need|i want|i have to (?:write|send))\b.{0,60}?\b(message|note|email|e-mail|text|card|letter|reply|toast|invitation|invite|caption|announcement|reminder|post)\b")
KINDS = [
    ('congrats', r'congrat\w*|well done on|proud of'),
    ('thanks', r'thank\w*|grateful|appreciat\w*'),
    ('sorry', r'apolog\w*|sorry|say(?:ing)? sorry'),
    ('birthday', r'birthday'),
    ('getwell', r'get[- ]well|speedy recovery|feel better|recover\w*|(?:is|was|been|being) (?:sick|ill|unwell)|in hospital'),
    ('luck', r'good luck|wish\w* (?:him|her|them|you)? ?(?:the best|luck)|best of luck'),
    ('invite', r'invit\w*'),
    ('remind', r'remind\w*'),
    ('late', r'running late|be(?:ing)? late|will be late|arrive late'),
    ('cancel', r'cancel\w*|can\'?t make it|won\'?t be able to (?:come|make|attend)|declin\w*|reschedul\w*|postpon\w*'),
    ('absence', r'day off|sick (?:day|leave)|call(?:ing)? in sick|won\'?t be in|out of (?:the )?office|time off|take .* off'),
    ('farewell', r'farewell|goodbye|leaving (?:the|my|our)|retir\w*|last day'),
    ('welcome', r'welcom\w*'),
    ('sympathy', r'condolence\w*|sympathy|passed away|loss of|died'),
    ('request', r'ask\w*|request\w*|need\w* (?:him|her|them)|if (?:he|she|they) (?:can|could|would)'),
    ('tell', r'tell\w*|let\w* (?:him|her|them) know|inform\w*|updat\w*|announc\w*|say\w* that'),
]
RELATION = r"(?:mum|mom|mother|dad|father|grandma|grandmother|grandpa|grandfather|nan|sister|brother|wife|husband|partner|girlfriend|boyfriend|friend|best friend|" \
           r"coworker|co-worker|colleague|boss|manager|teacher|professor|tutor|landlord|landlady|neighbou?r|team|client|customer|doctor|dentist|coach|" \
           r"aunt|uncle|cousin|son|daughter|roommate|flatmate|housemate|classmate|mentor|supervisor|employee|staff|parents|family|guests|group)"
TONES = {'casual': 'casual', 'informal': 'casual', 'relaxed': 'casual', 'friendly': 'casual', 'friendlier': 'casual', 'warm': 'casual', 'warmer': 'casual',
         'chatty': 'casual', 'formal': 'formal', 'professional': 'formal', 'polite': 'formal', 'serious': 'formal', 'official': 'formal',
         'businesslike': 'formal', 'respectful': 'formal', 'funny': 'funny', 'funnier': 'funny', 'playful': 'funny', 'humorous': 'funny',
         'lighthearted': 'funny', 'light-hearted': 'funny', 'short': 'short', 'shorter': 'short', 'brief': 'short', 'briefer': 'short', 'concise': 'short',
         'long': 'long', 'longer': 'long', 'detailed': 'long', 'heartfelt': 'long', 'personal': 'long', 'enthusiastic': 'casual', 'excited': 'casual'}
TONE_Q = re.compile(r"(?i)\b(" + '|'.join(sorted(TONES, key=len, reverse=True)) + r")\b")
REWRITE = re.compile(r"(?i)\b(?:make|sound|rewrite|redo|change|turn|keep|more|less|bit|little|too|shorten|lengthen|version|tone)\b")


def second_person(s):
    """'her on her promotion' -> 'your promotion'; 'him to fix the heating' -> 'you to fix the heating'."""
    s = re.sub(r"(?i)\b(?:she|he|they)(?:'s| is| are)\b", "you're", s)
    s = re.sub(r"(?i)\b(?:she|he|they) (has|have)\b", "you have", s)
    s = re.sub(r"(?i)\b(?:she|he|they)\b", "you", s)
    s = re.sub(r"(?i)\bher(?= (?:to|if|for|about|that|on|with|know|when|how|and|at|in)\b|[.,!?]|$)", "you", s)
    s = re.sub(r"(?i)\b(?:him|them)\b", "you", s)
    s = re.sub(r"(?i)\b(?:her|his|their)\b", "your", s)
    s = re.sub(r"(?i)\b(?:herself|himself|themselves)\b", "yourself", s)
    return s


def bare(verb_ing):
    """'fixing' -> 'fix', 'covering' -> 'cover', 'coming' -> 'come'."""
    w = verb_ing
    if not w.lower().endswith('ing'):
        return w
    root = w[:-3]
    if len(root) > 2 and root[-1] == root[-2] and root[-1] not in 'ls':
        return root[:-1]
    if re.search(r'(?:[^aeiou][aeiou][^aeiouwxy]|at|iv|ak|uc|as|ur|ag|ang|arg|ov|iz|us|id|ot)$', root) and root.lower() not in ('visit', 'open', 'cover', 'answer', 'offer', 'listen', 'water', 'deliver', 'consider', 'remember', 'happen'):
        return root + 'e'
    return root


def writing_request(text):
    m = WRITE.search(text)
    if not m:
        return None
    form = m[1].lower()
    low = text.lower()
    kind, kpos = None, None
    for name, pattern in KINDS:
        k = re.search(r'(?i)\b(?:' + pattern + r')', text)
        if k and (kpos is None or k.start() < kpos or name in ('congrats', 'thanks', 'sorry') and kind in ('request', 'tell')):
            if kind in ('congrats', 'thanks', 'sorry', 'birthday', 'getwell') and name in ('request', 'tell', 'late', 'cancel'):
                continue
            kind, kpos = name, k.start()
            kmatch = k
    if not kind:
        return None
    to = re.search(r"(?i)\b(?:to|for) (?:my |our |the )?((?:" + RELATION + r")(?:,? (?-i:[A-Z][a-z]+))?|(?-i:[A-Z][a-z]+))\b", text)
    rel = to[1] if to else ''
    name = re.search(r'\b([A-Z][a-z]+)$', rel)
    name = name[1] if name and name[1].lower() not in ('i',) and not re.fullmatch('(?i)' + RELATION, name[1]) else ''
    tail = text[kmatch.end():].strip().rstrip('.!?')
    tail = re.sub(r"(?i)^(?:ing|s|ed)?\s*", '', tail) if not tail.startswith(' ') else tail
    tail = re.sub(r"(?i)^(?:(?:message|note|email|e-mail|text|card|letter|wishes?)\s+)", '', tail)
    tail = re.sub(r"(?i)^(?:to|for) (?:my |our |the )?(?:" + RELATION + r")(?:,? (?-i:[A-Z][a-z]+))?\b\s*", '', tail)
    tail = re.sub(r"(?i)^(?:him|her|them|my \w+|our \w+|(?-i:[A-Z][a-z]+))\s+(?=on|for|to|about|that|because|if|know)", '', tail)
    tail = re.sub(r"(?i)^(?:to|for) (?:him|her|them)\s*", '', tail)
    # "... to my landlord asking him to fix the heating": the purpose may also sit before the recipient
    reason = second_person(tail.strip())
    reason = re.sub(r'(?i)^(?:on|for|about|that|because|to|if)\s+', lambda mm: mm.group(0) if kind in ('request', 'tell', 'invite', 'remind') else '', reason).strip()
    return dict(kind=kind, form=form, rel=rel.lower(), name=name, reason=reason, short=bool(re.search(r'(?i)\b(?:short|quick|brief|little)\b', low)))


def greet(req, tone):
    rel = req['rel']
    who = req['name'] or (rel.capitalize() if rel in ('mum', 'mom', 'dad', 'grandma', 'grandpa', 'nan') else '')
    if rel in ('team', 'parents', 'family', 'guests', 'staff', 'group') and not req['name']:
        return {'formal': 'Dear all,', 'casual': 'Hi everyone,', 'funny': 'Hi everyone,'}.get(tone, 'Hi everyone,')
    if tone == 'formal':
        return f"Dear {who or '[Name]'},"
    if tone in ('casual', 'funny'):
        return f"Hey {who}," if who else 'Hey,'
    return f"Hi {who}," if who else 'Hi,'


def clause(reason, lead):
    """Join a purpose to its sentence: ('your promotion', 'on') -> ' on your promotion'."""
    if not reason:
        return ''
    if re.match(r'(?i)(?:on|for|about|that|because|to|if|with|at|in)\b', reason):
        return ' ' + reason
    return f' {lead} {reason}'


def body(req, tone):
    k, r = req['kind'], req['reason']
    formal, casual, funny = tone == 'formal', tone == 'casual', tone == 'funny'
    if k == 'congrats':
        on = clause(r, 'on')
        if formal:
            return [f"Please accept my warmest congratulations{on}.", "It is a well-deserved recognition of your hard work and dedication.",
                    "I wish you every success in what comes next, and I look forward to continuing to work with you." if req['rel'] in ('coworker', 'co-worker', 'colleague', 'boss', 'manager', 'team', 'employee')
                    else "I wish you every success in what comes next."]
        if casual:
            return [f"Huge congratulations{on}!", "So well deserved. You've worked really hard for this.", "We have to celebrate soon!"]
        if funny:
            return [f"Congratulations{on}!", "Look at you, being all brilliant.", "Don't forget us little people now. Celebration drinks soon?"]
        return [f"Congratulations{on}!", "You've worked hard for this and it's really well deserved.", "I'm so happy for you, and I can't wait to see what you do next."]
    if k == 'thanks':
        why = clause(r, 'for') or ' for everything'
        if formal:
            return [f"I would like to thank you sincerely{why}.", "Your help made a real difference, and it is greatly appreciated.",
                    "Please let me know if I can ever return the favour."]
        if casual:
            return [f"Thanks so much{why}!", "You're a star, I really appreciate it.", "I owe you one!"]
        if funny:
            return [f"Thank you{why}!", "You are officially my hero.", "I owe you one. Possibly two."]
        return [f"Thank you so much{why}.", "It really meant a lot to me, and I appreciate the time and care you put in.", "I hope I can return the favour soon."]
    if k == 'sorry':
        why = clause(r, 'for') or ' for what happened'
        if formal:
            return [f"Please accept my sincere apologies{why}.", "I understand the inconvenience this caused and I take full responsibility.",
                    "I will make sure it does not happen again."]
        if casual:
            return [f"I'm really sorry{why}!", "Totally my fault. Let me make it up to you.", "Coffee's on me?"]
        if funny:
            return [f"I'm so sorry{why}!", "I've officially demoted myself to Very Sorry Person.", "Forgive me? I'll bring snacks."]
        return [f"I'm really sorry{why}.", "It was my mistake and I feel bad about it.", "I'll make sure it doesn't happen again, and I'd like to make it up to you."]
    if k == 'birthday':
        if formal:
            return ["Warmest wishes on your birthday.", "May the year ahead bring you health, happiness and success.", "With best regards."]
        if casual or funny:
            return ["Happy birthday! 🎉", "Hope your day is full of cake, laughs and people you love.", "Let's celebrate properly soon!"]
        return ["Happy birthday!", "I hope you have a wonderful day and a year full of good things.", "You deserve every bit of it."]
    if k == 'getwell':
        if formal:
            return ["I was sorry to hear that you are unwell.", "I wish you a full and speedy recovery.", "Please take all the time you need to rest."]
        if casual or funny:
            return ["So sorry to hear you're not feeling well!", "Rest up, watch something good, and don't worry about anything else.", "Shout if you need anything. Get well soon!"]
        return ["I'm sorry to hear you're not feeling well.", "I hope you get plenty of rest and feel better very soon.", "Let me know if there's anything I can do to help."]
    if k == 'luck':
        on = clause(r, 'with')
        if formal:
            return [f"I wish you the very best of luck{on}.", "I am confident you will do very well.", "With best regards."]
        return [f"Good luck{on}!", "You've prepared well and you've got this.", "I'll be thinking of you. Let me know how it goes!"]
    if k == 'invite':
        to = clause(re.sub(r'(?i)^you\s+', '', r), 'to') or ' to join us'
        if formal:
            return [f"I would be delighted if you could join us{to if to != ' to join us' else ''}.", "Please let me know whether you are able to attend.", "I very much hope to see you there."]
        if casual or funny:
            return [f"You're invited{to}!", "It wouldn't be the same without you.", "Let me know if you can make it!"]
        return [f"I'd love for you to come{to if to != ' to join us' else ' and join us'}.", "It would be great to see you there.", "Please let me know if you can make it."]
    if k == 'remind':
        about = clause(re.sub(r'(?i)^you\s+', '', r), 'about')
        if formal:
            return [f"This is a courteous reminder{about}.", "Please let me know if anything has changed or if you have any questions.", "Thank you in advance."]
        if casual or funny:
            return [f"Just a quick reminder{about}!", "Shout if anything's changed.", "Thanks!"]
        return [f"Just a friendly reminder{about}.", "Let me know if anything has changed or if you have any questions.", "Thanks!"]
    if k == 'late':
        if formal:
            return ["I am writing to let you know that I am running late" + (f' {r}' if r and not r.startswith('you') else '') + ".", "I apologise for the inconvenience and will be there as soon as I can.",
                    "Thank you for your understanding."]
        return ["Just to let you know I'm running a bit late" + (f' {r}' if r and not r.startswith('you') else '') + ".", "Sorry about that! I'll be there as soon as I can.", "Thanks for your patience."]
    if k == 'cancel':
        what = clause(r, 'for') if r else ''
        if formal:
            return [f"Unfortunately I am no longer able to make it{what}.", "I apologise for the short notice and any inconvenience this causes.",
                    "I would be grateful if we could arrange another time."]
        return [f"I'm really sorry, but I won't be able to make it{what}.", "I apologise for the short notice.", "Could we find another time that works for you?"]
    if k == 'absence':
        if formal:
            return ["I am writing to let you know that I will not be able to come in" + (f' {r}' if r else '') + ".", "I will make sure anything urgent is covered and will catch up as soon as I am back.",
                    "Thank you for your understanding."]
        return ["I wanted to let you know that I won't be able to come in" + (f' {r}' if r else '') + ".", "I'll make sure anything urgent is covered and catch up when I'm back.", "Thanks for understanding."]
    if k == 'farewell':
        if formal:
            return ["As you move on, I would like to thank you for everything you have contributed.", "It has been a privilege to work with you.", "I wish you every success in the future."]
        return ["I can't believe it's time to say goodbye!", "Thank you for everything. It won't be the same without you.", "Wishing you all the best for what's next. Let's keep in touch!"]
    if k == 'welcome':
        if formal:
            return ["I would like to extend a warm welcome to you.", "We are delighted to have you with us.", "Please do not hesitate to ask if there is anything you need."]
        return ["Welcome! We're so glad you're here.", "If you need anything while you settle in, just ask.", "Looking forward to getting to know you."]
    if k == 'sympathy':
        return ["I was so sorry to hear about your loss.", "Please know that you are in my thoughts.", "If there is anything I can do, I am here for you."]
    if k == 'request':
        r2 = re.sub(r'(?i)^(?:you )?(?:to |if you (?:can|could|would) )', '', r).strip()
        r2 = re.sub(r'(?i)^(\w+ing)\b', lambda mm: bare(mm[1]), r2)
        ask = r2 or 'help me with something'
        if formal:
            return [f"I am writing to ask whether you would be able to {ask}.", "I would be very grateful for your help with this.", "Thank you in advance for your time."]
        if casual or funny:
            return [f"Quick favour: could you {ask}?", "It would really help me out.", "Thanks a lot!"]
        return [f"I was wondering if you could {ask}.", "It would really help me out, and I'd be very grateful.", "Thank you so much!"]
    r2 = re.sub(r'(?i)^(?:you )?(?:that |about )', '', r).strip()
    if formal:
        return [f"I am writing to let you know that {r2}." if r2 else "I am writing to keep you informed.", "Please let me know if you have any questions.", "Thank you."]
    return [f"I wanted to let you know that {r2}." if r2 else "I just wanted to give you a quick update.", "Let me know if you have any questions.", "Thanks!"]


def compose_message(req, tone):
    base_tone = tone if tone in ('formal', 'casual', 'funny') else 'neutral'
    lines = body(req, base_tone)
    if tone == 'short' or (req['short'] and tone == 'neutral'):
        lines = lines[:2]
    if tone == 'long':
        extra = {'congrats': "Seeing your effort pay off like this is inspiring.", 'thanks': "Not everyone would have done what you did.",
                 'sorry': "I value our relationship and I don't take it for granted."}.get(req['kind'])
        if extra:
            lines = lines[:2] + [extra] + lines[2:]
    text = ' '.join(lines)
    letter = req['form'] in ('email', 'e-mail', 'letter') or base_tone == 'formal'
    if req['form'] in ('toast', 'caption', 'post', 'announcement'):
        return text
    sign = {'formal': 'Kind regards,\n[Your name]', 'casual': '', 'funny': ''}.get(base_tone, 'Best,\n[Your name]' if letter else '')
    hello = greet(req, base_tone)
    if letter:
        hello = hello.replace('Hi,', 'Hi [Name],').replace('Hey,', 'Hey [Name],')
        msg = f"{hello}\n\n{text}"
    else:
        msg = text if hello in ('Hi,', 'Hey,') else f"{hello} {text}"
    return msg + (f"\n\n{sign}" if sign else '')


def writer(messages):
    turns = user_turns(messages)
    q = turns[-1].strip()
    req = writing_request(q)
    if req:
        text = compose_message(req, 'neutral')
        kind = {'e-mail': 'email'}.get(req['form'], req['form'])
        return out('writing', f"Here's {'a short ' if req['short'] else 'an ' if kind[0] in 'aeiou' else 'a '}{kind} you could send:\n\n{text}\n\nWant it more formal, more casual or shorter? Just say.", 'message')
    if len(q.split()) > 16 or not REWRITE.search(q):
        return None
    tone = TONE_Q.search(q)
    if not tone:
        return None
    prev_i = next((i for i in range(len(turns) - 2, -1, -1) if writing_request(turns[i])), None)
    if prev_i is None or len(turns) - 1 - prev_i > 4:
        return None
    if 'you could send' not in last_reply(messages) and 'version' not in last_reply(messages):
        return None
    mode = TONES[tone[1].lower()]
    if re.search(r'(?i)\bless (?:formal|serious|professional|stiff)\b|\btoo (?:formal|serious|stiff|stuffy)\b', q):
        mode = 'casual'
    if re.search(r'(?i)\bless (?:casual|informal|chatty)\b|\btoo (?:casual|informal|chatty)\b', q):
        mode = 'formal'
    if re.search(r'(?i)\btoo (?:long|wordy)\b', q):
        mode = 'short'
    if re.search(r'(?i)\btoo short\b', q):
        mode = 'long'
    req = writing_request(turns[prev_i])
    text = compose_message(req, mode)
    lead = {'casual': "Here's a more casual version:", 'formal': "Here's a more professional version:", 'funny': "Here's a more playful version:",
            'short': "Here's a shorter version:", 'long': "Here's a longer, warmer version:"}[mode]
    return out('writing', f"{lead}\n\n{text}", 'rewrite')


# ----------------------------------------------------------------------------------------------- 9. staying with bad news

BAD_NEWS = re.compile(r"(?i)\b(?:didn'?t get|did not get|was(?:n'?t| not) (?:chosen|selected|accepted|picked)|got rejected|rejected|turned (?:me )?down|failed|lost my|"
                      r"broke up|dumped|laid off|let go|fired|passed away|died|disappointed|heartbroken|devastated|gutted|didn'?t pass|missed out|"
                      r"cancelled on me|fell through|didn'?t make (?:it|the)|bad news|upset|miserable|really sad|so sad)\b")
CHEERY = re.compile(r"(?i)^\s*(?:that is wonderful|that'?s wonderful|that sounds great|that'?s great|sounds nice|oh,? nice|how lovely|awesome|great!|nice!|"
                    r"congratulations|that is fantastic|well done|sounds like fun|lovely!)")


def mood_is_low(messages):
    turns = user_turns(messages)
    return any(BAD_NEWS.search(t) for t in turns[-3:-1]) or (len(turns) >= 1 and bool(BAD_NEWS.search(turns[-1])))


def comfort(messages):
    """The turn after bad news ('I really thought the interview went well.'): stay with it, then offer one useful next step."""
    turns = user_turns(messages)
    if len(turns) < 2 or not any(BAD_NEWS.search(t) for t in turns[-3:-1]):
        return None
    q = turns[-1].strip()
    if is_question(q) or len(q.split()) > 30 or len(q.split()) < 3:
        return None
    low = q.lower()
    job = any(re.search(r'(?i)\b(?:job|interview|position|role|application|promotion)\b', t) for t in turns[-3:])
    exam = any(re.search(r'(?i)\b(?:exam|test|course|grade|driving)\b', t) for t in turns[-3:])
    said = turned(sentences(q)[-1])
    if re.search(r"\b(?:thought|felt|was sure|was certain|expected|hoped|was confident|believed|seemed)\b", low):
        text = f"That makes it sting even more. When {said}, a \"no\" comes as a real shock, and it's natural to start replaying everything."
        if job:
            text += (" It often says less about you than it feels like: there may have been an internal candidate, or someone with one very specific "
                     "piece of experience. If you'd like, you could ask them for feedback, and I can help you word that message.")
        elif exam:
            text += " One result doesn't cancel out what you know. When you're ready, we can look at what to do differently next time."
        else:
            text += " Give yourself a little time with it. When you're ready, I'm happy to think through what comes next with you."
        return out('comfort', text, 'expected better')
    if re.search(r"\b(?:my fault|should have|shouldn't have|should not have|if only|messed up|blew it|screwed up|stupid|blame myself)\b", low):
        return out('comfort', "It's easy to be hard on yourself right after something like this, but hindsight makes everything look more obvious than it was. "
                              "You made the best call you could with what you knew then. Is there one thing you'd want to do differently next time? "
                              "We could turn that into a plan.", 'self-blame')
    if re.search(r"\b(?:worked so hard|worked really hard|prepared|studied|practi[sc]ed|put so much|spent (?:weeks|months|days|hours))\b", low):
        return out('comfort', f"That's what makes it so frustrating: {said}, and it still didn't go your way. The effort isn't wasted, though; "
                              "everything you prepared is still yours for the next opportunity. Do you want to talk it through, or think about what's next?", 'effort')
    if re.search(r"\b(?:don'?t know what to do|what now|not sure what to do|no idea what to do|feel lost|feel stuck)\b", low):
        return out('comfort', "That's okay. You don't have to figure it all out today. A good first step is small: rest tonight, then tomorrow write down "
                              "the one or two options you can see. If you tell me a bit more about your situation, I'll help you think them through.", 'lost')
    return None


# ----------------------------------------------------------------------------------------------- 10. replies to things the user tells CAEL

ECHO = re.compile(r"(?i)\? tell me more about it!\s*$|^\s*which specific claim should i check\?|^\s*noted: .*i'll remember that\.\s*$")
NOTED = re.compile(r"(?i)^\s*noted: ")


def topic(messages):
    """The thing the conversation is about, from the user's earlier turns: 'camping trip', 'piano', 'maths'."""
    try:
        from .web_check import nouns, weight, GENERIC
    except Exception:
        return ''
    turns = user_turns(messages)
    for t in reversed(turns[:-1][-3:]):
        m = re.search(r"(?i)\b(?:a|an|my|our|the) ((?:weekend |first |new |big |little |small )?[a-z]+ (?:trip|holiday|party|wedding|exam|interview|project|race|marathon|move|garden|lesson|course|class))\b", t)
        if m:
            return m[1].lower()
        m = re.search(r"(?i)\b(?:learning|studying|practi[sc]ing|trying|starting|training)(?: to (?:play|speak|do|learn))?(?: for)? (?:the |a |an |my )?([a-z]+(?: [a-z]+)?)\b", t)
        if m and m[1].lower() not in STOP:
            return re.sub(r'(?i)^(?:to|eat|play|speak) ', '', m[1].lower())
    return ''


def who_of(q):
    """(subject, pronoun, is/are, possessive) for the person a statement is about."""
    m = re.search(r"(?i)\bmy (son|brother|dad|father|husband|boyfriend|grandfather|grandpa|uncle|nephew|grandson)(?:,? (?-i:([A-Z][a-z]+)))?", q)
    if m or re.match(r"(?i)\s*he\b", q):
        return (m[2] if m and m[2] else 'him'), 'he', 'is', 'his'
    m = re.search(r"(?i)\bmy (daughter|sister|mum|mom|mother|wife|girlfriend|grandmother|grandma|aunt|niece|granddaughter)(?:,? (?-i:([A-Z][a-z]+)))?", q)
    if m or re.match(r"(?i)\s*she\b", q):
        return (m[2] if m and m[2] else 'her'), 'she', 'is', 'her'
    m = re.search(r"(?i)\bmy (kids|children|parents|friends|students|grandchildren)\b", q)
    if m or re.match(r"(?i)\s*they\b", q):
        return 'them', 'they', 'are', 'their'
    return 'you', 'you', 'are', 'your'


def statement(messages):
    """A reply to something the user tells CAEL, built from what they said and what kind of thing it is."""
    turns = user_turns(messages)
    q = turns[-1].strip()
    if is_question(q) or len(q.split()) < 4 or len(q.split()) > 45:
        return None
    if re.match(r'(?i)\s*(?:please |can you |could you )?(?:make|write|rewrite|change|add|turn|use|give|try|show|tell|put|remove|shorten|translate|list|explain)\b', q):
        return None
    low = q.lower()
    last = sentences(q)[-1]
    said = turned(last)
    if 'What does a typical day look like for you?' in last_reply(messages):
        return out('talk', f"That gives me a clearer picture: {said}. With that much on your plate, the realistic gains usually come from dropping, "
                           f"shortening or sharing one thing, not from squeezing more in. Two things that often help: decide the night before on the "
                           f"one task that matters most tomorrow, and protect one short block of time that is only yours. "
                           f"Which part of your day feels most rushed?", 'strain detail')
    who, he, is_, his = who_of(q)
    about = topic(messages)
    third = he != 'you'
    if re.search(r"\b(?:never|none of us (?:has|have)|neither of us|not once|haven't|hasn't|have not|has not)\b.*\b(?:before|ever)\b|\bfirst time\b|\b(?:i'm|we're|i am|we are) (?:completely |totally |pretty |quite )?new to\b|\b(?:complete|total) beginners?\b", low):
        what = f"a first {about}" if about and not about.startswith('first') else 'a first time'
        return out('talk', f"No problem at all, everyone starts somewhere, and {what} usually goes well with a bit of preparation. "
                           f"The trick is to keep it simple and not try to do too much. Would you like me to go through the basics you'll need?", 'new to it')
    choice = re.search(r"(?i)\b(?:can'?t decide|cannot decide|torn between|not sure|unsure|undecided|trying to decide|deciding|debating)\b.*?\b(?:whether|if|between)\b(?: to| i should)? (.+?) (?:or|and) (?:to )?(.+?)[.!]?$", last)
    if choice:
        a, b = you(choice[1].strip()), you(choice[2].strip())
        return out('talk', f"That's a real trade-off, and both options have something going for them. A quick way to decide: compare them on cost, "
                           f"on time, and on how each would feel day to day, then see which one wins on the thing you care about most. "
                           f"What matters most to you here: if you {a}, or if you {b}?", 'decision')
    if re.search(r"\b(?:hard(?:er|est)?|difficult|struggl\w+|tough(?:er|est)?|tricky|trouble|challeng\w+|can'?t (?:seem|keep|get|stop|focus|sleep)|overwhelm\w+|exhaust\w+|falling behind|stuck)\b", low):
        if third:
            return out('talk', f"That's a common hurdle, and it's good that you've noticed. When {said}, it usually helps to find out which part exactly "
                               f"feels hard for {who}, because that turns one big worry into something specific you can work on. "
                               f"Would you like some ideas for supporting {who if who != 'him' and who != 'her' else who}?", 'difficulty')
        part = re.search(r"(?i)\bthe (?:hardest|toughest|trickiest|most difficult|worst) (?:part|bit|thing) (?:is|was) (.+?)[.!]?$", last)
        if part:
            return out('talk', f"That makes sense, {you(part[1])} is where a lot of people get stuck. Knowing exactly where the hard part is helps a lot, "
                               f"because you can plan for that one moment instead of relying on willpower all day. Want a few ideas for it?", 'difficulty')
        return out('talk', f"That sounds frustrating, and it's more common than you might think. When {said}, it helps to break it down: "
                           f"which part is hardest, and when does it happen? Tell me a bit more and I'll suggest something specific.", 'difficulty')
    if re.search(r"\b(?:every|each) (?:single )?(?:day|morning|evening|night|week|weekend|afternoon)\b|\b(?:daily|weekly|twice a|once a|three times a|\d+ times a|most (?:days|evenings|mornings|nights))\b|\busually\b|\bevery (?:mon|tues|wednes|thurs|fri|satur|sun)day\b", low) \
            and re.search(r"(?i)^\s*(?:i|we)\b", last) and not re.search(r"\b(?:mon|tues|wednes|thurs|fri|satur|sun)days?\b", low) \
            and not re.search(r"\b(?:headaches?|migraines?|pain|aches?|hurts?|sick|nause\w*|dizz\w*|crying|cry|nightmares?|wak(?:e|ing) up|"
                              r"can'?t sleep|tired|exhausted|stressed|anxious|worried|lonely|sad|upset|arguing|fighting|late|stuck|broken|leak\w*)\b", low):
        ask = f"How is the {about} going so far?" if about else "How is it going so far?"
        return out('talk', f"That's a solid routine. Regular sessions like that add up much faster than the occasional long one, "
                           f"because your brain gets a chance to absorb things in between. {ask}", 'routine')
    if re.search(r"\b(?:just|recently|finally) (?:started|began|got|moved|joined|finished|graduated|turned|bought|adopted|had|passed|signed up|enrolled)\b|\bstarted (?:at |in )?(?:a |my |her |his )?(?:new |secondary |high |primary )?(?:job|school|university|college|course|nursery)\b", low):
        if third:
            return out('talk', f"That's a big step for {who}! New routines, new people and new expectations all at once can take a few weeks to settle. "
                               f"How {is_} {he} finding it so far?", 'life event')
        return out('talk', f"That's a big step, congratulations! The first few weeks are usually the most intense, and then it starts to feel normal. "
                           f"How are you finding it so far?", 'life event')
    plan = re.search(r"(?i)\b(?:i'm|i am|we're|we are) (?:planning|organi[sz]ing|arranging|preparing(?: for)?|thinking (?:of|about)|going on|hosting|throwing) (.+?)[.!]?$", last)
    if plan:
        thing = you(plan[1].strip())
        thing = thing[0].upper() + thing[1:]
        verb = 'sound' if re.search(r'(?i)\b\w+s (?:with|for|in|at|next|this)\b', thing) and not re.match(r'(?i)(?:a|an|the|your)\b', thing) else 'sounds'
        return out('talk', f"{thing} {verb} like fun! A little planning goes a long way with something like this. "
                           f"What do you still need to sort out? I can help with a checklist, timings or ideas.", 'plan')
    if re.search(r"\b(?:i'm|i am|we're|we are) (?:trying|hoping|aiming|working|learning|saving|training|looking)\b|\bmy goal\b|\bi want to\b|\bi'd like to\b|\bi would like to\b", low):
        return out('talk', f"That's a good goal, and saying it out loud is a real first step. It tends to work best when you make it specific and small "
                           f"enough to keep up on a bad day. How is it going so far, and what's been the trickiest part?", 'goal')
    if re.search(r"\bi feel (?:like|that|as if)\b|\bnever (?:have|get) enough\b|\balways (?:tired|late|busy|behind|stressed|rushing)\b|\bi keep (?:forgetting|putting|running|losing|getting)\b|\bstress(?:ed|ful)\b|\bworn out\b|\bburn(?:ed|t) out\b", low) and not third:
        return out('talk', f"That sounds wearing, and you're far from alone in feeling it. It usually helps to look at the one or two things that take "
                           f"the most time or energy and ask what could be dropped, shortened or shared. "
                           f"What does a typical day look like for you? I'll help you find some room in it.", 'strain')
    if re.search(r"\b(?:love|enjoy|really like|am into|i'm into|favourite|favorite|obsessed)\b", low) and not third:
        return out('talk', f"That's great, it's good to have something you really enjoy. What is it about it that you like most?", 'likes')
    return None


def acknowledge(messages):
    """A plain fact ('I work from home on Mondays and Fridays ...'): say it back briefly so the user knows it was understood."""
    q = user_turns(messages)[-1].strip()
    if is_question(q) or len(q.split()) < 4 or len(q.split()) > 40:
        return None
    said = turned(sentences(q)[-1])
    said = re.sub(r'(?i)\bi(?=\b)', 'you', said) if said.startswith('i ') else said
    return out('talk', f"Got it: {said}. I'll keep that in mind. Is there anything you'd like help with around that?", 'noted')


# ----------------------------------------------------------------------------------------------- 11. recall as a sentence

def fuller_recall(messages, result):
    """'twenty minutes.' -> 'You said you practise about twenty minutes every evening.'"""
    said = str(result.get('response', '')).strip()
    q = user_turns(messages)[-1]
    if len(said.split()) > 5 or not said or '(' in said or said.lower().startswith(('you ', 'your ', 'yes', 'no')):
        return result
    frag = said.rstrip('.!').lower()
    if len(frag) < 3:
        return result
    for t in reversed(user_turns(messages)[:-1]):
        for s in reversed(sentences(t)):
            if frag in s.lower() and '?' not in s and len(s.split()) <= 30:
                again = ' as I remember it' if False else ''
                return dict(result, response=f"You said {turned(s)}{again}.", replaced_fragment=said)
    return result


SYN = [{'struggl', 'hard', 'harder', 'difficult', 'trouble', 'tough', 'tricky', 'problem', 'worst', 'hardest'},
       {'like', 'love', 'enjoy', 'favourite', 'favorite', 'into', 'prefer'},
       {'job', 'work', 'profession', 'living'}, {'live', 'home', 'moved', 'based'},
       {'subject', 'maths', 'math', 'english', 'science', 'history', 'physics', 'chemistry', 'biology', 'geography', 'french', 'spanish', 'german', 'art', 'music'},
       {'pet', 'dog', 'cat', 'puppy', 'kitten', 'rabbit', 'hamster'}, {'name', 'called', 'named'}]


def widen(ws):
    ws = set(ws)
    for group in SYN:
        if any(any(w.startswith(g) or g.startswith(w) for g in group) for w in ws):
            ws |= group
    return ws


def second_part(messages, result):
    """'What's my son's name and which subject is he struggling with?': add the part the first answer left out."""
    q = user_turns(messages)[-1]
    said = str(result.get('response', '')).strip()
    m = re.search(r"(?i)^(.+?)\b(?:,? and|,? also|\? and|\?)\s+((?:what|which|who|where|when|how)\b.+)$", q.strip())
    if not m or len(said.split()) > 18:
        return result
    part = m[2]
    want = widen(stems(part))
    best, score = None, 0
    for t in user_turns(messages)[:-1]:
        for s in sentences(t):
            if '?' in s or s.lower() in said.lower():
                continue
            have = stems(s)
            sc = len({w for w in have if any(w.startswith(x[:5]) or x.startswith(w[:5]) for x in want)})
            if sc > score and stems(turned(s)) - stems(said):
                best, score = s, sc
    if not best or score < 1:
        return result
    return dict(result, response=f"{said.rstrip('.')}, and you said {turned(best)}.", added_part=part)


# ----------------------------------------------------------------------------------------------- 12. questions of judgement

def judgement(messages):
    """Used only when no route had an answer: questions that ask for a view or a plan ('Is it worth learning Latin?',
    'Should I get a tutor?', 'Can you recommend a book?', 'Help me plan a trip') get a way to think about it and one
    question back, instead of 'I don't know'."""
    q = user_turns(messages)[-1].strip()
    last = sentences(q)[-1]
    low = last.lower().rstrip('?.! ')
    if len(last.split()) > 30:
        return None
    m = re.search(r"\b(?:is it|is that|it's|would it be|do you think it'?s|do you think it is|is it really) worth (?:it to |the (?:money|time|effort) to )?(.+)$", low)
    if m:
        thing = you(m[1])
        return out('view', f"I think it can be, as long as you have a clear reason for it. {cap(thing)} tends to be worth it when two things are true: "
                           f"you'd enjoy the process itself, not only the result, and you can see what you'd use it for. If only one of those holds, "
                           f"it often gets dropped after a few weeks. What's drawing you to it?", 'worth it')
    start = r"^(?:so,? |and |but |ok,? |hmm,? |then )?"
    m = re.search(start + r"(?:should (?:i|we)|do you think (?:i|we) should|would you|is it a good idea to|is it better to) (.+?) or (.+)$", low)
    if m:
        a, b = you(m[1]), you(m[2])
        return out('view', f"There's no single right answer, but here's how I'd weigh it. Ask which choice is easier to undo, and which one you'd regret "
                           f"more a year from now. If you can try one cheaply first, do that before committing. "
                           f"Between the two ({a}, or {b}), which way are you leaning, and what's holding you back?", 'either-or')
    m = re.search(start + r"(?:should (?:i|we)|do you think (?:i|we) should|is it a good idea to|would it help to) (?:think about |consider |try )?(.+)$", low)
    if m:
        thing = you(m[1])
        return out('view', f"It's worth considering. A good test: what problem would it solve, and is there a cheaper or simpler way to solve the same "
                           f"problem first? If not, and you can try it for a short time without a big commitment, I'd say go for it and review after a "
                           f"few weeks. What's making you think about it now?", 'should I')
    m = re.search(r"\b(?:recommend|suggest)(?: me)? (?:a |an |some |any )?(?:good |great |nice )?(.+?)(?: for (.+))?$", low)
    if m and re.search(r'\b(?:books?|novels?|films?|movies?|shows?|series|songs?|albums?|music|games?|podcasts?|restaurants?|recipes?|gifts?|'
                       r'presents?|places?|hobby|hobbies|apps?|authors?|bands?|documentar(?:y|ies)|anime|comics?)\b', m[1]):
        thing = re.sub(r'^(?:a|an|some|any) ', '', m[1]).strip()
        return out('view', f"Happy to help you narrow it down. The right {thing if len(thing.split()) < 5 else 'choice'} depends a lot on your taste, so two quick "
                           f"questions: what's one you really enjoyed recently, and are you in the mood for something light and easy or something to "
                           f"sink into? Tell me that and I'll point you in a direction.", 'recommend')
    m = re.search(r"\b(?:help me|can you help me|could you help me|i need help|i want to|let's) (?:to )?(?:plan|organi[sz]e|prepare(?: for)?|put together|set up) (.+)$", low)
    if m:
        thing = you(m[1])
        return out('view', f"Let's do it. For {thing}, three things shape everything else: how much time you have, your budget, and the one thing you most "
                           f"want to get out of it. A structure that works well: one main thing for each day or part, one backup, and some free time around "
                           f"them. Tell me your dates and what you enjoy most, and I'll sketch a first version.", 'plan')
    if re.fullmatch(r"(?:any|got any|do you have any) (?:ideas|tips|advice|suggestions|thoughts)|what (?:would|should) (?:you|i) do|what do you (?:think|suggest|recommend)", low):
        return out('view', "Here's what I'd do: pick the smallest change that would make a real difference this week, try it for a few days, and see what "
                           "it tells you. Small tests beat big plans, because you learn what works for you. "
                           "Which part of this would you most like to change first?", 'ideas')
    return None


# ----------------------------------------------------------------------------------------------- hooks

IMPERATIVE = re.compile(r"(?i)^\s*(?:please |can you |could you |would you |now |ok,? |and )?(?:summari[sz]e|explain|describe|list|give|tell|write|name|suggest|"
                        r"recommend|help|compare|translate|define|show|find|calculate|convert|pick|choose|plan|create|draft|make|rewrite|change|add|turn|"
                        r"use|try|put|remove|shorten|continue|repeat|say|spell|count|sort|rank|check|fix|correct|solve|answer|imagine|pretend|let'?s)\b")
WEAK = re.compile(r"(?i)^\s*(?:i have not interpreted this complete clause|i’m following:|i'm following:|i do not have a reliable answer|i need the problem and its rules|i looked (?:this|that) up, but i couldn'?t find|"
                  r"i found pages, but could not read|i could not verify|i'?m not sure about that one|i don'?t have enough|which specific claim should i check|"
                  r"i did not find a usable public source|i searched the web for)")


def weak(said):
    return bool(WEAK.search(said or ''))


def before(messages, engine=None):
    """Turns answered from the conversation before the other routes."""
    try:
        if not user_turns(messages):
            return None
        last = user_turns(messages)[-1]
        lead = re.match(r"(?i)\s*(?:and|so|ok|okay|also|now|then|well|oh|hmm|right|alright)[, ]+(?=(?:what|how|who|when|where|why|which)\b(?! (?:about|if)\b))", last)
        if lead and engine is not None and len(last) - lead.end() > 8:
            # "And what's 2+2?": the question itself, without the lead-in word that the exact routes do not expect
            rest = last[lead.end():]
            return engine.respond(messages[:-1] + [dict(role='user', content=rest[0].upper() + rest[1:])], n=1, seed=0, mode='chat')
        if len(user_turns(messages)) > 1 and re.fullmatch(
                r"(?i)\s*(?:so,? |and |ok,? |hmm,? )?(?:any|got any|do you have any) (?:ideas|tips|advice|suggestions|thoughts)\??\s*|"
                r"\s*(?:so,? |and |ok,? |hmm,? )?what (?:would|should) (?:you|i) do\??\s*|\s*what do you (?:think|suggest|recommend)(?: i (?:should )?do)?\??\s*", last):
            return judgement(messages)
        for skill in (writer, hypothetical, comfort, appointment, week_split, converse, member_late, who_has_more, that_math,
                      example_sentence):
            got = skill(messages)
            if got is not None:
                return got
        from . import chat_skills
        if chat_skills.respond(messages) is None and chat_skills.respond(messages, late=True) is None:
            return what_if(messages, engine) or anchored(messages, engine)
    except Exception:
        return None
    return None


def after(messages, result):
    """The last pass over the reply that was chosen."""
    try:
        if not isinstance(result, dict) or not user_turns(messages):
            return result
        q = user_turns(messages)[-1].strip()
        said = str(result.get('response', '')).strip()
        route = str(result.get('route', ''))
        if route.startswith('chat/plus-'):
            return result
        from .chat_memory import is_recall
        if is_question(q) and (is_recall(q) or route.startswith(('chat/memory-recall', 'chat/memory-situation', 'chat/memory-pronoun', 'chat/context-memory'))):
            better = fuller_recall(messages, result)
            return second_part(messages, better)
        if is_question(q) and (weak(said) or route in ('chat/web-checked-none', 'chat/web-closest', 'chat/talk-unsure', 'chat/core-fallback',
                                                       'chat/problem-clarify', 'chat/web-single')):
            # equal shares the helper routes did not take ("8 slices and 3 of us share it equally")
            better = shares(messages)
            if better is not None:
                return dict(better, replaced_route=route)
        if is_question(q) and (weak(said) or route in ('chat/web-checked-none', 'chat/web-closest', 'chat/talk-unsure', 'chat/core-fallback')):
            better = judgement(messages)
            if better is not None:
                return dict(better, replaced_route=route)
        if not is_question(q) and not IMPERATIVE.search(q):
            low_mood = mood_is_low(messages)
            if re.search(r"(?i)^\s*(?:that sounds hard\. i'm here to listen|got it[.!,]? |i see[.!]|thanks, that helps: )", said):
                better = statement(messages)
                if better is not None:
                    return dict(better, replaced_route=route)
            if weak(said) and any(is_question(t) for t in user_turns(messages)[-3:-1]) and comfort(messages) is None and statement(messages) is None \
                    and 4 <= len(q.split()) <= 30:
                return dict(out('talk', f"Thanks, that helps: {turned(sentences(q)[-1])}. Would you like me to adjust my suggestions with that in mind?", 'detail'),
                            replaced_route=route)
            if ECHO.search(said) or weak(said) or (CHEERY.search(said) and low_mood and not re.search(r'(?i)\b(?:but|though|however)\b', q)):
                if NOTED.search(said) and re.search(r"(?i)\d|\b(?:" + '|'.join(d[:-3] for d in DAYS) + r")days?\b|\b(?:moved|changed|cancel+ed|rescheduled|password|code|pin|address)\b", q) \
                        and not re.search(r"(?i)\b(?:every|each|usually|a day|a week|per)\b", q):
                    return result            # a fact to keep ("They moved it to Friday at 10am."): the short confirmation is right
                better = comfort(messages) or statement(messages)
                if better is None and low_mood and CHEERY.search(said):
                    better = out('comfort', "That sounds really hard, and it makes sense that it's on your mind. Do you want to tell me more about what happened, "
                                            "or would it help to think about what to do next?", 'low mood')
                asked_before = any(is_question(t) for t in user_turns(messages)[-3:-1])
                if better is None and not asked_before and (re.search(r"(?i)^\s*which specific claim", said) or ECHO.search(said) and not NOTED.search(said)):
                    better = acknowledge(messages)
                if better is not None:
                    return dict(better, replaced_route=route)
    except Exception:
        return result
    return result
