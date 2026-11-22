"""Changing information with scope, corrections and withdrawals (0.4.4 work after release, 2026-11-22). Non-neural.

Statements are read in order, each with the value it gives (a time, a person, a place):
- **Newer replaces older** for the same thing, but only within its scope: "a newer notice says seven, but only for
  school nights", "replaces Leo with Kim for the matinee only".
- **Withdrawn or mistaken statements don't count:** "wrote Kim beside both by mistake and has erased both marks",
  "my diversion text was for the cycling race, not your walking tour".
- **The situation asked about** comes from the question and the facts ("tonight is a non-school night", "for the
  matinee", "our walking group").
The answer is the latest statement that applies to that situation.
"""
import re

ROUTE = 'chat/scoped'
HOURS = r'(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|noon|midnight|\d{1,2}(?::\d{2})?\s*(?:am|pm)?|\d{1,2}:\d{2})'
STOP = {'The', 'A', 'An', 'I', 'We', 'My', 'Our', 'Your', 'If', 'For', 'Another', 'Use', 'Using', 'Which', 'Who', 'What', 'When', 'Tonight', 'Today',
        'Tomorrow', 'It', 'This', 'That', 'There', 'Its', 'His', 'Her', 'Their', 'They', 'He', 'She', 'Both', 'After', 'Before', 'Under', 'Then',
        'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday', 'A', 'An', 'And', 'But', 'Only', 'Now', 'Later', 'Newer'}
WITHDRAW = re.compile(r'(?i)\b(?:by\s+mistake|in\s+error|erased|rubbed\s+out|crossed\s+out|ignore|disregard|withdrawn|retracted|cancel(?:led)?|'
                      r'was\s+wrong|not\s+(?:meant\s+)?for\s+(?:you|your)|was\s+(?:meant\s+)?for\s+(?:the\s+)?[\w\s-]+?,\s*not\s+(?:for\s+)?(?:you|your))\b')


def out(text, kind):
    return dict(route=f'{ROUTE}-{kind}', response=text, sources=[], reasoning=True, details=f'{kind} (scoped_facts.py)')


def values_in(s, kind):
    if kind == 'time':
        return [m[1] for m in re.finditer(r'(?i)\b(?:at|says|say|is|to|until|till|from)\s+(' + HOURS + r')\b', s)] + \
               [m[1] for m in re.finditer(r'(?i)\bsays?\s+(' + HOURS + r')\b', s)]
    got = []
    for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", s):
        w = m[1]
        first = w.split()[0]
        if first in STOP:
            rest = w.split()[1:]
            if not rest or rest[0] in STOP:
                continue
            w = rest[0]
        if w not in got:
            got.append(w)
    return got


def scope_of(s):
    m = re.search(r'(?i)\b(?:but\s+)?(?:only|just)\s+(?:for|on|during|in|at)\s+(?:the\s+)?([a-z][\w\s-]*?)(?:\s+only)?(?:[.,;!]|$)|'
                  r'\bfor\s+(?:the\s+)?([a-z][\w-]*(?:\s+[a-z][\w-]*)?)\s+only\b|\bwas\s+(?:meant\s+)?for\s+(?:the\s+)?([a-z][\w\s-]*?),\s*not\b', s)
    if not m:
        return None
    return (m[1] or m[2] or m[3]).strip().lower()


def matches(scope, situation):
    """Does the situation fall inside the scope? 'school nights' vs 'a non-school night' -> False."""
    words = [w.rstrip('s') for w in re.findall(r'[a-z]+', scope) if w not in ('the', 'a', 'an', 'of', 'performance', 'performances')]
    if not words:
        return None
    sit = situation.lower()
    key = words[0]
    if re.search(r'\b(?:non-?|not\s+(?:a\s+)?)' + re.escape(key), sit):
        return False
    return all(re.search(r'\b' + re.escape(w), sit) for w in words[:2])


def respond(messages):
    users = [(m.get('content') or '').strip() for m in messages if m.get('role') == 'user']
    if len(users) < 1:
        return None
    qs = re.findall(r'[^.!?\n]*\?', users[-1])
    if not qs:
        return None
    q = qs[-1]
    if re.search(r'(?i)\bwhen\b|\bwhat\s+time\b', q):
        kind = 'time'
    elif re.search(r'(?i)\bwho\b|\bwhich\s+(?:entrance|door|gate|route|way|road|street|room|platform|exit|path)\b|\bwhat\s+(?:entrance|route|door|gate)\b', q):
        kind = 'name'
    else:
        return None
    text = '\n'.join(users[-6:])
    sents = [s.strip() for s in re.split(r'(?<=[.!?;])\s+|\n+', text) if s.strip()]
    facts = [s for s in sents if not s.endswith('?')]
    if not any(re.search(r'(?i)\b(?:newer|later|update[sd]?|now|another\s+message|replaces?|instead|actually|correction|changed?)\b', s) for s in facts):
        return None
    situation = ' '.join(s for s in sents if re.search(r'(?i)\b(?:tonight|today|this\s+(?:evening|week)|our|we|for\s+the|explicitly)\b', s)
                         and not values_in(s, kind) and not WITHDRAW.search(s) and not s.endswith('?')) + ' ' + q
    # read statements in order
    stmts = []      # (values, scope, void)
    for s in facts:
        vals = values_in(s, kind)
        if WITHDRAW.search(s):
            if re.search(r'(?i)\b(?:by\s+mistake|in\s+error|erased|rubbed\s+out|crossed\s+out)\b', s) and vals:
                continue        # a mistaken mark that was removed adds nothing
            sc = scope_of(s)
            if stmts:
                target = next((i for i in range(len(stmts) - 1, -1, -1) if stmts[i][3] == 'update'), len(stmts) - 1)
                v, _, _, tag = stmts[target]
                stmts[target] = (v, sc or '__nothing__', False, tag)
            continue
        if re.search(r'(?i)\b(?:is|are)\s+(?:current|right|correct|still\s+(?:valid|current|right))\b|\bstill\s+(?:stands|applies)\b', s) and stmts:
            base = next((x for x in stmts if x[3] == 'base'), None)
            if base:
                stmts.append((base[0], None, False, 'reaffirmed'))      # "your map is current"
            continue
        if not vals:
            continue
        if re.search(r'(?i)\b(?:is|are|was)\s+(?:taped\s+off|closed|shut|blocked|out\s+of\s+use|unavailable|not\s+available|off\s+limits)\b', s) and stmts:
            continue            # a reason given for the change, not a new value
        rep = re.search(r'\b[Rr]eplac\w*\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+with\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', s)
        if rep and kind == 'name':
            vals = [rep[2]]
        elif kind == 'name' and re.search(r'(?i)\buse\s+', s):
            m = re.search(r'\b[Uu]se\s+(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', s)
            if m:
                vals = [m[1]]
        elif kind == 'time' and len(set(vals)) > 1:
            vals = vals[-1:]
        tag = 'base' if not stmts else 'update'
        stmts.append((vals, scope_of(s), False, tag))
    if len(stmts) < 2 or all(sc is None for _, sc, _, _ in stmts):
        return None         # a plain newer-replaces-older update is left to the other readers
    answer, why = None, None
    for vals, sc, void, tag in stmts:
        if void:
            continue
        if sc is None:
            answer, why = vals[0], 'it applies everywhere'
        elif sc == '__nothing__':
            continue
        else:
            ok = matches(sc, situation)
            if ok is None:
                return None
            if ok:
                answer, why = vals[0], f'its scope ({sc}) covers this case'
    if not answer:
        return None
    others = [v[0][0] for v in stmts if v[0] and v[0][0] != answer]
    if others and why == 'it applies everywhere':
        why = 'the change to ' + ', '.join(dict.fromkeys(others)) + " doesn't cover this case (it was limited or withdrawn), so this still holds"
        return out(f'**{answer[0].upper() + answer[1:] if kind == "name" else answer}.** {why[0].upper() + why[1:]}.', kind)
    return out(f'**{answer[0].upper() + answer[1:] if kind == "name" else answer}.** That is the latest statement that applies here: {why}.'
               + (f' The other value ({", ".join(dict.fromkeys(others))}) doesn\'t apply to this case.' if others else ''), kind)
