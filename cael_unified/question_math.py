"""Question-guided arithmetic for everyday word problems (non-neural).

Word problems often carry extra numbers. Instead of combining every number, CAEL first reads what the question asks
for (a difference "how many more X than Y", a total, a share "each group", what is left after changes, a product
"N per item times M items", how many times larger) and then picks only the numbers whose own words match the
question's words. It answers only when that choice is unambiguous, and shows the working.
"""
import re
from fractions import Fraction

NUMW = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        'eleven': 11, 'twelve': 12, 'twenty': 20, 'thirty': 30, 'fifty': 50, 'hundred': 100, 'dozen': 12}
STOP = set('''a an the of and or to in on at for from with by is are was were be been has have had do does did will would
can could how many much more less fewer than there their his her its they he she it them that this those these if then
what which who each every per all total altogether some still left now after before same as so but also just only into
had has having were total sum together combined in all'''.split())
MINUS = r'(?:gave|give|gives|giving|ate|eat|eats|sold|sell|sells|lost|lose|loses|spent|spend|spends|used|use|uses|broke|' \
        r'removed|took away|threw|donated|left with|paid|pay|pays|flew away|went away|drank|popped|died|cut|shared|lent)'
PLUS = r'(?:got|get|gets|bought|buy|buys|found|find|finds|received|receive|receives|earned|earn|picked|collected|' \
       r'added|made|won|baked|caught|grew|planted|borrowed|joined|came|arrived)'


def lem(w):
    w = w.lower().strip(".,;:!?'\"")
    if len(w) > 4 and w.endswith('ies'):
        return w[:-3] + 'y'
    if len(w) > 3 and w.endswith('es') and w[:-2].endswith(('ch', 'sh', 'x', 'ss', 'o')):
        return w[:-2]
    if len(w) > 3 and w.endswith('s') and not w.endswith('ss'):
        return w[:-1]
    return w


def words(text):
    return [lem(w) for w in re.findall(r"[A-Za-z]+", text) if w.lower() not in STOP]


class Mention:
    def __init__(self, v, sent, idx, ctx, unit, op):
        self.v, self.sent, self.idx, self.ctx, self.unit, self.op = v, sent, idx, ctx, unit, op

    def __repr__(self):
        return f'{self.v}<{self.unit}|{",".join(sorted(self.ctx))[:40]}|{self.op}>'


def mentions(body):
    """Numbers with the content words of their clause, their unit (the noun after) and a change sign."""
    out = []
    sents = re.split(r'(?<=[.!?])\s+', body.strip())
    for si, s in enumerate(sents):
        clauses = re.split(r'(?i),\s*|\s+and\s+(?=[a-z]*\s*\d)|\s+but\s+|\s+while\s+', s)
        for c in clauses:
            toks = re.findall(r"\d+(?:\.\d+)?|[A-Za-z]+", c.replace(',', ''))
            for i, t in enumerate(toks):
                v = None
                if re.fullmatch(r'\d+(?:\.\d+)?', t):
                    v = Fraction(t)
                elif t.lower() in NUMW and not (t.lower() == 'one' and i + 1 < len(toks) and toks[i + 1].lower() in ('of', 'day')):
                    v = Fraction(NUMW[t.lower()])
                if v is None:
                    continue
                unit = None
                for w in toks[i + 1:i + 4]:
                    if w.lower() not in STOP and not re.fullmatch(r'\d+', w):
                        unit = lem(w)
                        break
                op = 'minus' if re.search(rf'(?i)\b{MINUS}\b', c) else ('plus' if re.search(rf'(?i)\b{PLUS}\b', c) else None)
                out.append(Mention(v, si, len(out), set(words(c)), unit, op))
    return out


def fmt(v):
    return str(v.numerator) if v.denominator == 1 else f'{float(v):g}'


def best(ms, key_words, exclude=()):
    """The mention whose clause shares most words with key_words; None when tied or no overlap."""
    scored = sorted(((len(m.ctx & key_words) + (0.5 if m.unit in key_words else 0), -m.idx, m) for m in ms if m not in exclude),
                    key=lambda x: (x[0], x[1]), reverse=True)
    if not scored or scored[0][0] == 0:
        return None
    if len(scored) > 1 and scored[1][0] == scored[0][0] and scored[1][2].v != scored[0][2].v:
        return None
    return scored[0][2]


def relation_answer(body, q):
    """X did N more/fewer than Y: resolve each person's value, then answer a total or one person's value."""
    if not re.search(r'(?i)\b(?:more|fewer|less)\b[^.]*\bthan\b', body):
        return None
    vals = {}
    for s in re.split(r'(?<=[.!?])\s+', body):
        m = re.match(r'(?i)^(?:then |and )?([A-Z][a-z]+)\b.*?\b(\d+(?:\.\d+)?) (more|fewer|less) [\w-]+(?: [\w-]+)? than ([A-Z][a-z]+)', s)
        if m:
            who, n, sign, other = m.group(1).lower(), Fraction(m.group(2)), m.group(3).lower(), m.group(4).lower()
            if other not in vals:
                return None
            vals[who] = vals[other] + (n if sign == 'more' else -n)
            continue
        m = re.match(r'(?i)^([A-Z][a-z]+)\b', s)
        nums = re.findall(r'\b\d+(?:\.\d+)?\b', s)
        if m and len(nums) == 1 and not re.search(r'(?i)\bthan\b', s):
            vals[m.group(1).lower()] = Fraction(nums[0])
    names = [n for n in vals if re.search(rf'(?i)\b{n}\b', q)]
    if len(vals) < 2:
        return None
    if re.search(r'(?i)\b(?:altogether|in all|total|together|combined)\b', q) and len(names) >= 2:
        return sum(vals[n] for n in names), ' + '.join(fmt(vals[n]) for n in names), 'relation-total'
    if len(names) == 1 and not re.search(r'(?i)\b(?:more|fewer|less)\b', q):
        return vals[names[0]], fmt(vals[names[0]]), 'relation-value'
    return None


def solve(text):
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    q = parts[-1]
    if '?' not in q and not re.match(r'(?i)^(how|what|find)', q):
        return None
    body = ' '.join(parts[:-1])
    ms = mentions(body)
    qnums = mentions(q)
    if not ms:
        return None
    ql = q.lower()
    qw = set(words(q))
    tu = re.search(r'(?i)how (?:many|much) (?:more |fewer |less )?([a-z]+)', q)
    target = lem(tu.group(1)) if tu else None
    if target in ('did', 'doe', 'do', 'will', 'would', 'can', 'could', 'should', 'wa', 'were', 'is', 'are', 'ha', 'have', 'had', 'money'):
        target = None   # "how much did they make": no unit named
    # relations: "X did N more/fewer than Y"
    r = relation_answer(body, q)
    if r:
        return r
    # "each C holds N U" with M of one of them given
    each = re.search(r'(?i)\beach (\w+)(?: \w+){0,3}? (?:has|have|holds?|contains?|can hold|needs?|gets?|takes?|carr(?:y|ies)) (\d+) (\w+)', body)
    if each and target:
        c_unit, n, u = lem(each.group(1)), Fraction(each.group(2)), lem(each.group(3))
        others = [x for x in ms if not (x.v == n and x.unit == u)]
        if target == c_unit and len(others) == 1 and others[0].unit == u and n:
            return others[0].v / n, f'{fmt(others[0].v)} ÷ {fmt(n)}', 'each-count'
        if target == u and len(others) == 1 and others[0].unit == c_unit:
            return others[0].v * n, f'{fmt(others[0].v)} × {fmt(n)}', 'each-total'
    ms_all = list(ms)
    if re.search(r"(?i)not|n't", q):
        return None   # negated questions ("how many were not hiding") need the complement, not handled here
    if re.search(r'(?i)\b(?:so that|in order to|need to|needs to|have to|has to)\b', q):
        return None   # a goal to reach ("buy how many so that she has 140"): an inverse problem, not handled here
    # "5 students in each grade": of all such phrases, the one about what the question asks for
    m2 = next((mm for mm in re.finditer(r'(?i)(\d+) (\w+) (?:in|for|per) (?:each|every|one|a) (\w+)', body)
               if target in (lem(mm.group(2)), lem(mm.group(3)))), None)
    if m2 and target:
        n, u, c = Fraction(m2.group(1)), lem(m2.group(2)), lem(m2.group(3))
        others = [x for x in ms if not (x.v == n and x.unit == u)]
        if target == c and len(others) == 1 and others[0].unit == u and n:
            return others[0].v / n, f'{fmt(others[0].v)} ÷ {fmt(n)}', 'each-count'
        if target == u and len(others) == 1 and others[0].unit == c:
            return others[0].v * n, f'{fmt(others[0].v)} × {fmt(n)}', 'each-total'
    # the question names what it counts: only those numbers are candidates
    same = [x for x in ms if target and x.unit == target]
    if 1 <= len(same) < len(ms):
        ms = same
    # how many more / fewer X than Y: the two sides of "than"
    m = re.search(r'(?i)how (?:many|much) (?:more|fewer|less)\b(.*?)\bthan\b(.*)', q)
    if m and not qnums:
        a = best(ms, set(words(m.group(1))) | (qw - set(words(m.group(2)))))
        b = best(ms, set(words(m.group(2))), exclude=(a,))
        if a and b and a is not b:
            return abs(a.v - b.v), f'{fmt(max(a.v, b.v))} - {fmt(min(a.v, b.v))}', 'difference'
        return None
    # how many times as many
    if re.search(r'(?i)how many times\b', q):
        m = re.search(r'(?i)how many times (?:more|as many|bigger|larger|greater)?(.*?)(?:\bthan\b|\bas\b)(.*)', q)
        if m:
            a = best(ms, set(words(m.group(1))))
            b = best(ms, set(words(m.group(2))), exclude=(a,))
            if a and b and b.v:
                return a.v / b.v, f'{fmt(a.v)} ÷ {fmt(b.v)}', 'ratio'
        return None
    # each group / per item: a total split into groups
    if re.search(r'(?i)\b(?:each|every|per|one)\s+(?:group|box|bag|basket|row|shelf|team|friend|student|person|day|week|child|kid|plate|table|pack)\b|\bin each\b|how big is each', q):
        if re.search(r'(?i)\bhow many (?:\w+ )?(?:groups|boxes|bags|baskets|rows|shelves|teams|days|weeks|packs|plates|tables)\b', q):
            pass
        else:
            groups = [x for x in ms if x.unit and re.match(r'(?i)(group|box|bag|basket|row|shelf|team|friend|student|person|people|day|week|child|kid|plate|table|pack)', x.unit)]
            g = best(groups, qw) if len(groups) > 1 else (groups[0] if groups else None)
            tot = best([x for x in ms if x is not g], qw)
            if g and tot and g.v:
                return tot.v / g.v, f'{fmt(tot.v)} ÷ {fmt(g.v)}', 'share'
            return None
    # how many groups: total divided by the size of one group
    m = re.search(r'(?i)how many (groups|boxes|bags|baskets|rows|shelves|teams|days|weeks|packs|plates|tables|trips)\b', q)
    if m:
        size = [x for x in ms if re.search(r'(?i)\b(?:each|every|per|in a|in one)\b', ' '.join(x.ctx) + ' ') or 'each' in body.lower()]
        nums = sorted(ms, key=lambda x: -x.v)
        if len(ms) == 2 and ms[1].v and ms[0].v % ms[1].v == 0 or len(ms) == 2 and ms[0].v and ms[1].v % ms[0].v == 0:
            big, small = (ms[0], ms[1]) if ms[0].v >= ms[1].v else (ms[1], ms[0])
            return big.v / small.v, f'{fmt(big.v)} ÷ {fmt(small.v)}', 'groups'
        return None
    # product: N per item times M items ("each X has N Y")
    if re.search(r'(?i)\beach\b|\bper\b|\bevery\b', body) and re.search(r'(?i)\bin all\b|\btotal\b|\baltogether\b|how many \w+ (?:does|did|do|are|were|will)', q):
        per = [x for x in ms if re.search(r'(?i)\b(?:each|per|every)\b', ' '.join(sorted(x.ctx)) + ' ' + body)]
        rel = [x for x in ms if x.ctx & qw or x.unit in qw]
        if len(rel) == 2 and not qnums:
            a, b = rel
            # product only when the body says "each"/"per" in the clause of one of them
            cl = re.split(r'(?<=[.!?])\s+', body)
            if any(re.search(r'(?i)\b(?:each|per|every)\b', cl[x.sent]) for x in rel):
                return a.v * b.v, f'{fmt(a.v)} × {fmt(b.v)}', 'product'
    # total / altogether: add the matching quantities
    if re.search(r'(?i)\b(?:in all|in total|total|altogether|together|combined|sum)\b', q):
        # numbers about the question's own subject: their clause shares a content word with the question beyond the unit
        topic = qw - {target}
        # only words that tell the numbers apart ("rowing" vs "hiking"), not words every clause shares ("went")
        topic = {w for w in topic if 0 < sum(w in x.ctx for x in ms) < len(ms)}
        rel = [x for x in ms if x.ctx & topic] if topic else []
        rel = rel if len(rel) >= 2 else ms
        unit0 = rel[0].unit if rel else None
        if target is None and any(x.unit != unit0 for x in rel):
            rel = [x for x in rel if x.unit == unit0]          # "how much in all": one kind of quantity
        if 2 <= len(rel) <= 4 and not any(x.op == 'minus' for x in rel):
            return sum(x.v for x in rel), ' + '.join(fmt(x.v) for x in rel), 'total'
        return None
    # how many left / now / remain: start, then changes
    if re.search(r'(?i)\b(?:left|remain|remaining|still|now|have)\b', q) and len(ms_all) + len(qnums) in (2, 3, 4):
        allm = ms_all + qnums
        money = bool(re.search(r'(?i)\$|\bmoney\b|\bdollars?\b', text))
        for x in allm:
            sent = re.split(r'(?<=[.!?])\s+', body)[min(x.sent, len(re.split(r'(?<=[.!?])\s+', body)) - 1)] if x in ms_all else q
            if money and re.search(r'(?i)\b(?:bought|buy|buys|paid|pay|spent)\b', sent):
                x.op = 'minus'                    # buying costs money
            if re.search(r'(?i)\bpicked\b[^.]*\bfrom\b', sent):
                x.op = 'minus'                    # picked from the tree: taken away from it
        start = allm[0]
        if start.op is None or len(allm) == 1:
            v = start.v
            expr = fmt(v)
            for x in allm[1:]:
                if x.op == 'minus':
                    v -= x.v
                    expr += f' - {fmt(x.v)}'
                elif x.op == 'plus':
                    v += x.v
                    expr += f' + {fmt(x.v)}'
                else:
                    return None
            if v >= 0 and len(allm) > 1:
                return v, expr, 'change'
        return None
    return None


# Pattern kinds allowed to answer in chat: those that were right at least ~85% of the time on the SVAMP train split.
# 'product', 'total' and 'change' were not (2/17, 17/8, 13/6) and stay silent.
# 'each-total' (N per group x M groups) is left to the existing groups helper (helper_groups), which explains it better.
ENABLED = {'difference', 'each-count', 'share', 'groups', 'relation-value', 'relation-total'}


def reply(text, messages=None):
    if len(text) > 600 or not re.search(r'(?i)\bhow (?:many|much)\b', text) or not re.search(r'\d', text):
        return None
    try:
        r = solve(text)
    except Exception:
        return None
    if r is None or r[0] < 0 or (ENABLED is not None and r[2] not in ENABLED):
        return None
    v, expr, kind = r
    if v.denominator != 1 and not re.search(r'(?i)\b(?:dollars?|\$|hours?|miles?|kg|pounds?|liters?|cups?)\b', text):
        return None
    return {'response': f'**{fmt(v)}**\n\nWorking: {expr} = {fmt(v)}', 'route': 'chat/question-math', 'confidence': 0.7, 'kind': kind}
