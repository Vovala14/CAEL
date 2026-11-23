"""Who can do which job (0.4.4 work after release, 2026-11-22). Non-neural.

Reads a staffing puzzle as facts and tries every way of giving each job to a different person:
- **Jobs:** what is needed ("the stage needs a drummer and a singer", "we need a driver, a cook and a guide").
- **People:** capitalised names.
- **Abilities:** "can only sing", "can do either", "can do any of them", "can drive or cook", "can't cook".
  A job and a verb match by their stem (drummer ~ drum, singer ~ sing, driver ~ drive).
- **Who is out:** "if Ada sits this one out", "Ada is away", "Bo can't come".
- **One job each** unless the text says someone may do two.
The answer comes from what every valid assignment agrees on.
"""
import re
from itertools import permutations

ROUTE = 'chat/staffing'
STOP = {'The', 'A', 'An', 'If', 'We', 'I', 'Our', 'My', 'Nobody', 'No', 'Each', 'Every', 'Who', 'What', 'Which', 'Can', 'Could', 'Both',
        'Either', 'Neither', 'They', 'He', 'She', 'It', 'Is', 'Are', 'And', 'But', 'So', 'Then', 'There', 'This', 'That', 'Tonight', 'Today',
        'Tomorrow', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday', 'For', 'On', 'In', 'At', 'One', 'Two'}
OUT = re.compile(r"(?i)\b([A-Z][a-z]+)\s+(?:sits?\s+(?:this\s+one\s+|it\s+)?out|is\s+(?:away|off|absent|out|busy|unavailable|sick|ill|not\s+(?:there|here|available|coming))|"
                 r"can(?:no|')t\s+(?:come|make\s+it|be\s+there)|won't\s+(?:come|be\s+there)|drops?\s+out|is\s+out\s+sick|has\s+the\s+night\s+off)\b")


def out(text, kind):
    return dict(route=f'{ROUTE}-{kind}', response=text, sources=[], reasoning=True, details=f'{kind} (staffing.py)')


def stem(w):
    w = w.lower()
    for suf in ('ers', 'er', 'ing', 'ist', 'ists', 's', 'e'):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[:-len(suf)]
    return w


def same_job(word, job):
    a, b = stem(word), stem(job)
    return a == b or len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)) or a[:4] == b[:4] and len(a) >= 4 and len(b) >= 4


def jobs_in(text):
    m = re.search(r'(?i)\b(?:needs?|requires?|wants?|is\s+looking\s+for|are\s+looking\s+for|must\s+have|has\s+to\s+have)\s+((?:(?:a|an|one)\s+\w+(?:\s*,\s*|\s+and\s+|\s*,\s*and\s+))+(?:a|an|one)\s+\w+)', text)
    if not m:
        return None
    jobs = re.findall(r'(?i)\b(?:a|an|one)\s+(\w+)', m[1])
    return jobs if 2 <= len(jobs) <= 5 and len(set(jobs)) == len(jobs) else None


def people_in(text, jobs):
    got = []
    for w in re.findall(r'\b([A-Z][a-z]+)\b', text):
        if w in STOP or any(same_job(w, j) for j in jobs) or w in got:
            continue
        got.append(w)
    return got


def abilities(text, people, jobs):
    """{person: set of jobs}; None when a sentence about a person's abilities can't be read."""
    can = {p: set(jobs) for p in people}
    said = set()
    for sent in re.split(r'(?<=[.!?;])\s+|,\s*(?:and\s+|but\s+|while\s+)?(?=[A-Z])', text):
        for p in people:
            m = re.search(r'\b' + p + r"\b\s+(can(?:no|')t|cannot|can\s+only|only|can|is\s+only\s+able\s+to|is\s+able\s+to|knows\s+how\s+to|isn't\s+able\s+to|"
                          r"doesn't|does\s+not|won't|will\s+not|refuses\s+to)\s+(.+?)(?=[.!?;,]|$)", sent)
            if not m:
                continue
            verb, what = m[1].lower(), m[2]
            if re.search(r'(?i)\b(?:either|both|any|all|anything|every|each)\b', what) and not re.search(r"(?i)n't|not|cannot", verb):
                can[p] = set(jobs)
                said.add(p)
                continue
            named = [j for j in jobs if any(same_job(w, j) for w in re.findall(r'[A-Za-z]+', what))]
            if not named:
                return None
            if re.search(r"(?i)n't|not|cannot|refuses", verb):
                can[p] -= set(named)
            elif 'only' in verb:
                can[p] = set(named)
            else:
                can[p] = set(named) if p not in said else can[p] | set(named)
            said.add(p)
    return can


def respond(messages):
    users = [(m.get('content') or '').strip() for m in messages if m.get('role') == 'user']
    if not users:
        return None
    text = '\n'.join(users[-4:])
    qs = re.findall(r'[^.!?\n]*\?', users[-1])
    if not qs:
        return None
    q = qs[-1]
    jobs = jobs_in(text)
    if not jobs:
        return None
    people = people_in(text, jobs)
    if not 2 <= len(people) <= 6:
        return None
    can = abilities(text, people, jobs)
    if can is None or all(can[p] == set(jobs) for p in people):
        return None
    away = {m[1] for m in OUT.finditer(text) if m[1] in people}
    free = [p for p in people if p not in away]
    two_ok = re.search(r'(?i)\b(?:can|may)\s+(?:do|cover|take)\s+(?:two|both|more\s+than\s+one)\s+(?:jobs|roles|parts)\b', text) and \
        not re.search(r'(?i)\b(?:nobody|no\s+one|no-one)\s+can\b', text)
    sols = []
    pool = [p for p in free for _ in range(2 if two_ok else 1)]
    seen = set()
    for perm in permutations(pool, len(jobs)):
        if perm in seen:
            continue
        seen.add(perm)
        if all(job in can[p] for job, p in zip(jobs, perm)):
            sols.append(dict(zip(jobs, perm)))
    if len(sols) > 1:
        sols = [dict(t) for t in {tuple(sorted(s.items())) for s in sols}]
    gone = (' with ' + ' and '.join(sorted(away)) + ' out') if away else ''
    if not sols:
        return out(f'**Nobody can cover every job**{gone}: no way of giving each job to a different person fits what each person can do.', 'impossible')
    m = re.search(r'(?i)\bwho\s+(?:is|will\s+be|would\s+be|does|plays?|takes?|covers?|gets?)\s+(?:the\s+)?(\w+)', q)
    target = next((j for j in jobs if m and same_job(m[1], j)), None)
    if target:
        who = sorted({s[target] for s in sols})
        if len(who) == 1:
            return out(f'**{who[0]}.** ' + explain(sols, jobs, gone), 'who')
        return out(f"**It can't be determined**: it could be {' or '.join(who)}" + gone + '.', 'who-open')
    m = re.search(r'(?i)\bwhat\s+(?:does|will|would|is)\s+([A-Z][a-z]+)\b', q)
    if m and m[1] in people:
        x = m[1]
        did = sorted({next((j for j, p in s.items() if p == x), 'nothing') for s in sols})
        if len(did) == 1:
            return out(f'**{x}: {did[0]}.** ' + explain(sols, jobs, gone), 'what')
        return out(f"**It can't be determined**: {x} could take " + ' or '.join(did) + '.', 'what-open')
    if re.search(r"(?i)\bwho(?:'s|\s+is|\s+does|\s+will\s+do|\s+would\s+do)?\s+(?:doing\s+)?what\b|\bhow\s+(?:do|should|can|would)\s+(?:we|I|they)\s+(?:split|assign|staff|cover|fill)\b|"
                 r"\bwho\s+(?:covers|takes|does)\s+(?:each|which)\b|\bassign", q):
        if len(sols) == 1:
            s = sols[0]
            return out('**' + '; '.join(f'{s[j]} is the {j}' for j in jobs) + '.** ' + explain(sols, jobs, gone), 'all')
        return out(f"**It can't be fully determined**{gone}: " + ' or '.join('; '.join(f'{s[j]} as {j}' for j in jobs) for s in sols[:3]) + '.', 'all-open')
    return None


def explain(sols, jobs, gone):
    if len(sols) == 1:
        return f'It is the only way to give each job to a different person{gone} that fits what each person can do.'
    return f'{len(sols)} ways fit{gone}, and they all agree on this.'
