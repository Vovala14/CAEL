"""Is a set of statements consistent? (0.4.4 work after release, 2026-11-22). Non-neural.

Reads a rule about every member of a group ("All servers in rack B are offline", "Every door on floor 2 is locked",
"None of the shops on Main Street are open") and a statement about one member ("Server B-4 is in rack B and is serving
traffic"). The member's state is compared with the rule through a table of opposite states (offline / online, serving
traffic, running; locked / unlocked, open; empty / full...). The reply says whether they clash, and why.
"""
import re

ROUTE = 'chat/consistency'
OPPOSITE = [
    ({'offline', 'down', 'off', 'unplugged', 'powered off', 'switched off', 'shut down', 'stopped'},
     {'online', 'up', 'on', 'running', 'serving traffic', 'serving requests', 'working', 'live', 'active', 'powered on', 'responding'}),
    ({'locked', 'shut', 'closed', 'sealed', 'covered', 'lidded', 'capped'}, {'unlocked', 'open', 'opened', 'ajar', 'wide open', 'unsealed', 'uncovered', 'uncapped'}),
    ({'fragile', 'delicate', 'breakable'}, {'sturdy', 'robust', 'unbreakable', 'non-fragile'}),
    ({'dry'}, {'wet', 'damp', 'soaked'}),
    ({'cold', 'frozen', 'chilled'}, {'hot', 'warm', 'thawed'}),
    ({'paid'}, {'unpaid', 'overdue', 'outstanding'}),
    ({'clean'}, {'dirty'}),
    ({'new'}, {'used', 'second-hand'}),
    ({'empty'}, {'full', 'occupied', 'in use', 'taken'}),
    ({'asleep', 'sleeping'}, {'awake'}),
    ({'absent', 'away', 'out'}, {'present', 'here', 'in', 'at home'}),
    ({'sold out', 'out of stock', 'unavailable'}, {'available', 'in stock', 'for sale'}),
    ({'broken', 'faulty'}, {'working', 'fine'}),
    ({'red'}, {'blue', 'green', 'yellow', 'white', 'black'}),
]


def out(text, kind):
    return dict(route=f'{ROUTE}-{kind}', response=text, sources=[], reasoning=True, details=f'{kind} (consistency.py)')


def state_of(phrase):
    p = re.sub(r'(?i)\b(?:currently|now|still|right\s+now|definitely|all)\b', ' ', phrase.lower())
    p = re.sub(r'\s+', ' ', p).strip(' .,')
    for i, (neg, pos) in enumerate(OPPOSITE):
        for side, words in ((0, neg), (1, pos)):
            for w in sorted(words, key=len, reverse=True):
                if re.search(r'\b' + re.escape(w) + r'\b', p):
                    return i, side, w
    return None


def word_state(rest, rule, noun, group, neg_rule, w):
    """The rule's state is a plain word; the member says it, or says its negation (non-w, un-w, not w)."""
    member = re.search(r'(?i)\b([\w-]+(?:\s+[\w-]+)?)\s+is\s+' + re.escape(group) + r'\b(.*?)(?:[.;]|$)', rest)
    if not member:
        return None
    name, tail = member[1], member[2].lower()
    negated = re.search(r'\b(?:non-?|un)' + re.escape(w) + r'\b|\bnot\s+(?:\w+\s+)?' + re.escape(w) + r'\b|\bisn\'t\s+(?:\w+\s+)?' + re.escape(w) + r'\b', tail)
    plain = re.search(r'(?<![\w-])' + re.escape(w) + r'\b', tail)
    if not negated and not plain:
        return None
    member_has = not negated
    rule_has = not neg_rule
    rule_text = rule[0].strip().rstrip('.')
    said = re.search(r'\b(?:marked|labelled|labeled|listed|tagged)\s+(?:as\s+)?', tail)
    how = f'{"marked " if said else ""}{"not " if not member_has else ""}{w}'
    if member_has != rule_has:
        return out(f'**No, it isn\'t consistent.** "{rule_text}" means every {noun} {group} is {"" if rule_has else "not "}{w}. {name} is {group}, '
                   f'yet it is {how}. At least one of the statements (or the label) is wrong or out of date.', 'clash')
    return out(f'**Yes, that\'s consistent.** {name} is {group} and is {how}, which fits "{rule_text}".', 'fits')


def respond(messages):
    users = [(m.get('content') or '').strip() for m in messages if m.get('role') == 'user']
    if not users:
        return None
    text = '\n'.join(users[-3:])
    q = (re.findall(r'[^.!?\n]*\?', users[-1]) or [''])[-1]
    if not re.search(r'(?i)\b(?:consistent|contradict\w*|possible|make\s+sense|add\s+up|can\s+(?:both|this|that)\s+be\s+true|conflict)\b', q):
        return None
    rule = re.search(r'(?i)\b(all|every|each|none\s+of\s+the|no)\s+(\w+?)s?\s+((?:in|on|at|of)\s+[\w\s-]+?)\s+(?:are|is)\s+(not\s+)?([a-z][\w\s-]*?)\s*(?:[.;]|$)', text)
    if not rule:
        return None
    noun, group, neg_rule, state = rule[2].lower(), rule[3].strip(), bool(rule[4]) or rule[1].lower().startswith(('none', 'no')), rule[5]
    rs = state_of(state)
    if not rs:
        # any state word: "fragile" against "non-fragile", "unsealed", "not fragile" (2026-11-23)
        w = re.sub(r'(?i)^(?:all\s+|now\s+|still\s+)', '', state.strip().lower())
        if not re.fullmatch(r'[a-z][a-z-]*', w) or w.startswith(('non-', 'un')):
            return None
        rs = ('word', w)
    if rs[0] == 'word':
        return word_state(text[rule.end():], rule, noun, group, neg_rule, rs[1])
    rest = text[rule.end():]
    member = re.search(r'(?i)\b([\w-]+(?:\s+[\w-]+)?)\s+is\s+' + re.escape(group) + r'\b(.*?)(?:[.;]|$)', rest)
    if not member:
        return None
    name, tail = member[1], member[2]
    ms = state_of(tail)
    if not ms:
        return None
    if ms[0] != rs[0]:
        return None
    member_neg = bool(re.search(r"(?i)\b(?:not|isn't|no\s+longer)\b", tail))
    rule_side = rs[1] if not neg_rule else 1 - rs[1]
    member_side = ms[1] if not member_neg else 1 - ms[1]
    rule_text = rule[0].strip().rstrip('.')
    if rule_side != member_side:
        return out(f'**No, it isn\'t consistent.** "{rule_text}" means every {noun} {group} is {rs[2] if not neg_rule else "not " + rs[2]}. '
                   f'{name} is {group}, yet it is {ms[2]}, which is the opposite. At least one statement is wrong or out of date '
                   f'(for example the "all" may be stale, or {name} may be in a different place).', 'clash')
    return out(f'**Yes, that\'s consistent.** {name} is {group}, and being {ms[2]} fits "{rule_text}".', 'fits')
