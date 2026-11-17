"""General small logic over what the user stated (no per-phrasing patterns, no model).

Two engines:
  * orderings ("taller than", "before", "left of") -> a graph, its transitive closure, and the place asked for;
  * statements as implications between terms ("all A are B", "no A are B", "only A can B", "if P then Q", "unless",
    "either/or") plus facts about named things -> forward closure with contrapositives.
The answer is Yes, No, or "not necessarily" with the statements it rests on. None when the question cannot be tied
to the statements, so nothing is guessed.
"""
import re

IRR = dict(p.split(":") for p in """was:be were:be is:be are:be am:be been:be has:have had:have did:do does:do went:go goes:go
gone:go came:come ran:run got:get made:make took:take taken:take knew:know known:know saw:see seen:see won:win lost:lose
left:leave paid:pay said:say told:tell ate:eat eaten:eat flew:fly flies:fly flown:fly spoke:speak spoken:speak wrote:write
written:write children:child people:person men:man women:woman mice:mouse feet:foot teeth:tooth met:meet slept:sleep
kept:keep felt:feel brought:bring bought:buy thought:think sold:sell sat:sit stood:stand drove:drive driven:drive rode:ride
broke:break broken:break chose:choose fell:fall gave:give given:give grew:grow held:hold snowed:snow wet:wet""".split())
DROP = set('''a an the be do have will would can could may might must shall should to of then so that it he she they we i
you this these those there very really also just too my your his her our their its if me him them us always get become
turn stay remain definitely certainly still as at by for in on with from into inside s re m ll ve d today now tonight
currently tomorrow yesterday who which whom whose'''.split())
PRON = r"(?:it|he|she|they|this|that|it's|he's|she's|they're|i|we)"
NOT = re.compile(r"\b(?:not|never|no longer|cannot|can't|won't|isn't|aren't|wasn't|weren't|doesn't|don't|didn't|hasn't|haven't|couldn't|wouldn't)\b|n't\b", re.I)
START = set('if all no some every each only either unless the it this that when whenever none any there my i we they he she and but so then therefore also both neither not nobody everyone anyone a an one two three today tomorrow yesterday now tonight here'.split())


OPPOSITE = dict(closed='open', shut='open', false='true', dead='alive', absent='present', asleep='awake', unlocked='locked',
                dry='wet', empty='full', unhappy='happy', unsafe='safe', illegal='legal', impossible='possible', unavailable='available')


def stem(w):
    w = w.lower().strip("'’")
    if w in IRR:
        return IRR[w]
    if len(w) > 4 and w.endswith('ies'):
        w = w[:-3] + 'y'
    elif len(w) > 4 and w.endswith('ied'):
        w = w[:-3] + 'y'
    elif len(w) > 5 and w.endswith('ing'):
        w = w[:-3]
    elif len(w) > 4 and w.endswith('ed'):
        w = w[:-2]
    elif len(w) > 3 and w.endswith('es') and w[-3] in 'sxzh':
        w = w[:-2]
    elif len(w) > 3 and w.endswith('s') and not w.endswith('ss'):
        w = w[:-1]
    if len(w) > 3 and w.endswith('e'):
        w = w[:-1]
    if len(w) > 3 and w[-1] == w[-2] and w[-1] not in 'aeiou':
        w = w[:-1]
    return w


def words(text):
    return re.findall(r"[A-Za-z][A-Za-z'’]*|\d+", text)


def term(text):
    """(content stems, negated) of a clause or noun phrase."""
    text = re.sub(r"(?i)\b(is|are|was|were|stays?|stayed|turned|switched|left)\s+on\b", r'\1 poweredon', text)
    text = re.sub(r"(?i)\b(is|are|was|were|stays?|stayed|turned|switched|left)\s+off\b", r'\1 not poweredon', text)
    for word, opposite in OPPOSITE.items():
        text = re.sub(r'(?i)\b%s\b' % word, 'not ' + opposite, text)
    neg = len(NOT.findall(text)) % 2 == 1
    text = NOT.sub(' ', text).replace("'", ' ')
    return frozenset(s for s in (stem(w) for w in words(text)) if s not in DROP and s != 'not'), neg


def split_sentences(text):
    text = text.replace('’', "'")
    return [s.strip() for s in re.split(r'(?<=[.!?;])\s+', text) if s.strip()]


def swap(text):
    """The user's words said back: my -> your, I -> you."""
    out = re.sub(r'\bmy\b', 'your', text, flags=re.I)
    out = re.sub(r"\bI'm\b|\bI am\b", 'you are', out)
    out = re.sub(r'\bI\b', 'you', out)
    return re.sub(r'\bme\b', 'you', out, flags=re.I)


def quote(i, sents):
    return '"' + sents[i].rstrip('.!;') + '"'


# ---------------------------------------------------------------- orderings
HI = '''taller older faster heavier bigger larger longer higher richer stronger smarter better pricier hotter warmer quicker
louder brighter wider deeper thicker harder busier happier earlier sooner before ahead above over left front top more
dearer costlier greater'''.split()
LO = '''shorter younger slower lighter smaller lower poorer weaker worse cheaper colder cooler quieter dimmer narrower
shallower thinner softer later after behind below under right back bottom less fewer'''.split()
HIEST = '''tallest oldest fastest heaviest biggest largest longest highest richest strongest smartest best priciest hottest
warmest quickest loudest brightest widest deepest first earliest leftmost top front most winner won greatest'''.split()
LOEST = '''shortest youngest slowest lightest smallest lowest poorest weakest worst cheapest coldest coolest quietest last
latest rightmost bottom back least fewest'''.split()
ORD = dict(first=1, second=2, third=3, fourth=4, fifth=5, sixth=6)
REL = re.compile(r"\b(?:(?:is|was|are|were|stands?|sits?|lives?|finished|came|comes|arrived|arrives|goes|went|ran|runs|scored|placed|ranks?|costs?|weighs?|got|sat|stood)\s+)?"
                 r"(?:(?:much|a bit|a little|slightly|far|just|immediately|directly|right|to the|on the|in)\s+)*"
                 r"(?:(more|less)\s+(\w+)\s+than|(\w+er)\s+than|(before|after|ahead of|behind|above|below|under|left of|right of|front of|on top of))\s+", re.I)
ENT = re.compile(r"\b(?:[A-Za-z]+ [A-Z0-9]\b|[Tt]he\s+[a-z]+(?:\s+(?!is\b|was\b|are\b|were\b|stands?\b|sits?\b|finished\b|came\b|lives?\b|and\b|but\b|or\b|to\b|on\b|in\b)[a-z]+)?|[A-Z][a-z]+)\b")


def entities(s):
    out = []
    for m in ENT.finditer(s):
        name = m[0]
        if name.split()[0].lower() in START and not name.lower().startswith('the '):
            continue
        if re.fullmatch(r'[A-Za-z]+ [A-Z0-9]', name):
            name = name[0].lower() + name[1:]
        out.append((m.start(), m.end(), re.sub(r'^[Tt]he\s+', 'the ', name)))
    return out


def ordering(sents, question):
    pairs, used, known_rel = [], set(), set()
    for i, s in enumerate(sents):
        ents = entities(s)
        if not ents:
            continue
        for m in REL.finditer(s):
            word = (m[2] and ('more' if m[1].lower() == 'more' else 'less')) or (m[3] or m[4]).lower().split()[0]
            adj = stem(m[2]) if m[2] else stem(m[3] or m[4])
            left = [e for e in ents if e[1] <= m.start()]
            right = [e for e in ents if e[0] >= m.end() - 1]
            if not right:
                continue
            a = (left[-1] if left and not re.search(r'\b(and|but|,)\s*$', s[left[-1][1]:m.start()] + ' ') or left and len(left) == 1 else ents[0])[2]
            if left and re.search(r'\b(but|and)\b', s[left[-1][1]:m.start()]):
                a = ents[0][2]                    # "Cy finished after Bo but before Di": the subject carries over
            b = right[0][2]
            if a == b:
                continue
            if word in LO:
                a, b = b, a
            elif word not in HI and not m[3]:
                continue
            pairs.append((a, b)); used.add(i); known_rel.add(adj)
    if len(pairs) < 2 and not (pairs and re.search(r'\b(who|which)\b', question, re.I)):
        return None
    names = sorted({x for p in pairs for x in p})
    above = {n: set() for n in names}
    for a, b in pairs:
        above[a].add(b)
    for _ in names:
        for n in names:
            for x in list(above[n]):
                above[n] |= above[x]
    if any(n in above[n] for n in names):
        return 'Those statements contradict each other, so there is no consistent order.'
    order = sorted(names, key=lambda n: -len(above[n]))
    total = all(order[i + 1] in above[order[i]] for i in range(len(order) - 1))
    ql = question.lower()
    ql = re.sub(r'\b(?:furthest|farthest|most|far|very)\s+(?:to the\s+|on the\s+)?(left|right)\b', r'\1most', ql)
    ql = re.sub(r'\bat the (front|back|top|bottom)\b', r'\1', ql)
    show = ', '.join(order)
    basis = ' (' + '; '.join(s.rstrip('.') for i, s in enumerate(sents) if i in used) + ')'

    def cap(n):
        return n[0].upper() + n[1:]
    # "Is A taller than C?"
    m = REL.search(question)
    q_ents = entities(question)
    if m and len(q_ents) >= 2 and re.match(r'\s*(is|was|are|did|does|will|would)\b', ql):
        a, b = q_ents[0][2], q_ents[1][2]
        word = (m[2] and m[1].lower()) or (m[3] or m[4]).lower().split()[0]
        if a not in above or b not in above:
            return None
        if word in LO:
            a, b = b, a
        if b in above[a]:
            return f'**Yes.** In order: {show}.'
        if a in above[b]:
            return f'**No**, it is the other way round. In order: {show}.'
        return '**That is not settled** by what you said: nothing links those two.'
    if not re.search(r'\b(who|which|what|whose|where)\b', ql):
        return None
    mid = re.search(r'\b(middle|centre|center|in between|between the other)\b', ql)
    ordn = re.search(r'\b(%s)\b(?:[- ](last|from last|to last))?' % '|'.join(ORD), ql)
    sup = re.search(r'\b(%s)\b' % '|'.join(HIEST + LOEST), ql) or re.search(r'\b(\w{3,}est)\b', ql)
    pick = why = None
    if mid:
        if total and len(order) % 2:
            pick, why = order[len(order) // 2], 'in the middle'
    elif ordn and not (sup and sup[1] in ('first', 'last') and ordn[1] == sup[1]) or (ordn and ordn[1] != 'first'):
        k = ORD[ordn[1]]
        lo_end = ordn[2] or (sup and sup[1] in LOEST and sup[1] not in ('first',))
        if total and k <= len(order):
            pick = order[-k] if lo_end else order[k - 1]
            why = ordn[0] + (f' {sup[1]}' if sup and sup[1] not in ORD and sup[1] not in ordn[0] else '')
    elif sup:
        w = sup[1]
        if w in HIEST or (w not in LOEST and stem(w[:-3]) in {k[:len(stem(w[:-3]))] for k in known_rel}):
            tops = [n for n in names if len(above[n]) == len(names) - 1]
            pick, why = (tops[0] if tops else None), w
        elif w in LOEST:
            lows = [n for n in names if all(n in above[x] for x in names if x != n)]
            pick, why = (lows[0] if lows else None), w
        else:
            return None
    if pick is None:
        if mid or ordn or sup:
            return f'**That is not settled** by what you said: the statements leave more than one order possible{basis}.'
        return None
    verb = 'is' if not re.search(r'\b(came|finished|arrived|won|placed|was|were|did)\b', ql) else ('came' if re.search(r'\b(came|finished|arrived|placed)\b', ql) else 'was')
    article = '' if why in ORD or why.split()[0] in ORD and verb == 'came' or why == 'in the middle' else 'the '
    if why in ('first', 'last') and verb == 'came':
        article = ''
    return f'**{cap(pick)}** {verb} {article}{why}. In order: {show}.'


# ---------------------------------------------------------------- statements and facts
AUX = r"(?:are|is|was|were|can|cannot|can't|could|have|has|had|must|will|won't|do|does|did|don't|doesn't|didn't|aren't|isn't|may|might|should|get|gets)"


def cut(body, singular=False):
    """Subject and predicate of 'doctors in the clinic speak French' (no tagger: first auxiliary, else first verb-like word)."""
    m = re.search(r'\s+(%s)\s+' % AUX, ' ' + body + ' ', re.I)
    if m:
        return body[:max(m.start() - 1, 0)].strip(), body[m.start():].strip()
    ws = body.split()
    if singular:
        for i in range(1, len(ws)):
            if ws[i].endswith('s') and not ws[i].endswith('ss'):
                return ' '.join(ws[:i]), ' '.join(ws[i:])
    if len(ws) >= 2:
        return ws[0], ' '.join(ws[1:])
    return body, ''


class World:
    def __init__(self):
        self.rules = []         # (A, signA, B, signB, sentence index)
        self.facts = {}         # name -> list of (term, sign, sentence index, pronoun subject)
        self.vocab = set()
        self.either = []        # (P text, Q text, P term, Q term)
        self.loose = set()      # one-word terms ("grow", "rain"): the subject was a pronoun or left out
        self.last = None
        self.phrases = []       # subject and predicate wordings already read ("electric cars"), to split later sentences at

    def rule(self, a, sa, b, sb, i):
        if a and b:
            if len(a) == 1:
                self.loose.add(a)
            if len(b) == 1:
                self.loose.add(b)
            self.rules.append((a, sa, b, sb, i)); self.vocab |= {a, b}

    def fact(self, who, t, sign, i, pron=False):
        if t:
            self.facts.setdefault(who, []).append((t, sign, i, pron)); self.vocab.add(t)

    def match(self, who, t, sign, pron=False):
        """Sentence indices behind 'who has t with this sign', or None."""
        fs = self.facts.get(who, [])
        if who == '*':
            for ft, fsign, i, fpron in fs:
                if fsign == sign and (ft == t or ((pron or fpron or t in self.loose) and (ft < t or t < ft))):
                    return {i} if i >= 0 else set(self.why.get((ft, fsign), ()))
            return None
        if sign:
            bag, src = set(), set()
            for ft, fsign, i, _ in fs:
                if fsign:
                    bag |= ft; src |= ({i} if i >= 0 else set(self.why.get((who, ft, fsign), ())))
            return src if t <= bag else None
        for ft, fsign, i, _ in fs:
            if not fsign and ft <= t:
                return {i} if i >= 0 else set(self.why.get((who, ft, fsign), ()))
        return None

    def close(self):
        self.why = {}
        for _ in range(12):
            new = False
            for who in list(self.facts):
                for a, sa, b, sb, i in self.rules:
                    for (x, sx, y, sy) in ((a, sa, b, sb), (b, not sb, a, not sa)):
                        src = self.match(who, x, sx)
                        if src is not None and self.match(who, y, sy) is None:
                            key = (y, sy) if who == '*' else (who, y, sy)
                            self.why[key] = sorted(set(src) | {i})
                            self.facts[who].append((y, sy, -1, False)); new = True
            if not new:
                break

    def ask(self, who, t, pron=False):
        """('yes'|'no'|'open', sentence indices)."""
        yes = self.match(who, t, True, pron)
        if yes is not None:
            return 'yes', sorted(yes)
        no = self.match(who, t, False, pron)
        if no is not None:
            return 'no', sorted(no)
        if who != '*':                       # not (red and box), and it is a box -> not red
            bag = set().union(*[ft for ft, s, _, _ in self.facts.get(who, []) if s]) if self.facts.get(who) else set()
            for ft, fsign, i, _ in self.facts.get(who, []):
                if not fsign and t < ft and (ft - t) <= bag:
                    return 'no', sorted({i} if i >= 0 else set(self.why.get((who, ft, fsign), ())))
        return 'open', []


def read(sents):
    w = World()
    for i, s in enumerate(sents):
        body = s.rstrip('.!;').strip()
        low = body.lower()
        m = re.match(r"(?:but |and |so |then |also )?if (.+?)(?:,\s*(?:then\s+)?|\s+then\s+)(.+)$", body, re.I)
        if m:
            (p, pn), (q, qn) = term(m[1]), term(m[2]); w.rule(p, not pn, q, not qn, i); continue
        m = re.match(r"(?:when|whenever|every time|any time|once) (.+?),\s*(.+)$", body, re.I)
        if m:
            (p, pn), (q, qn) = term(m[1]), term(m[2]); w.rule(p, not pn, q, not qn, i); continue
        m = re.match(r"unless (.+?),\s*(.+)$", body, re.I) or (re.match(r"(.+?),?\s+unless\s+(.+)$", body, re.I) and re.match(r"(?P<q>.+?),?\s+unless\s+(?P<p>.+)$", body, re.I))
        if m:
            p_text, q_text = (m['p'], m['q']) if 'p' in m.groupdict() else (m[1], m[2])
            (p, pn), (q, qn) = term(p_text), term(q_text); w.rule(p, pn, q, not qn, i); continue
        m = re.match(r"(.+?)\s+only if\s+(.+)$", body, re.I)
        if m:
            (p, pn), (q, qn) = term(m[1]), term(m[2]); w.rule(p, not pn, q, not qn, i); continue
        m = re.match(r"(.+?)\s+(?:if|whenever|when|as long as|provided)\s+(.+)$", body, re.I)
        if m and not low.startswith(('all ', 'every ', 'no ', 'some ', 'only ')):
            (q, qn), (p, pn) = term(m[1]), term(m[2]); w.rule(p, not pn, q, not qn, i); continue
        m = re.match(r"(.+?\s+(?:is|are|was|were|will be|must be))\s+either\s+(.+?),?\s+or\s+(.+)$", body, re.I)
        if m:
            p_text, q_text = f'{m[1]} {m[2]}', f'{m[1]} {m[3]}'
            (p, _), (q, _) = term(p_text), term(q_text)
            w.rule(p, False, q, True, i); w.either.append((p_text, q_text, p, q)); continue
        m = re.match(r"(?:either\s+)?(.+?),?\s+or\s+(?:else\s+)?(.+)$", body, re.I)
        if m and (low.startswith('either') or not re.match(r'(all|every|no|some|only)\b', low)):
            (p, pn), (q, qn) = term(m[1]), term(m[2])
            if p and q and not pn and not qn:
                w.rule(p, False, q, True, i); w.either.append((m[1], m[2], p, q)); continue
        m = re.match(r"(all of the|all the|all of|all|every one of the|each of the|every|each|any|none of the|none of|no)\s+(.+)$", body, re.I)
        if m:
            rel = re.match(r"(\w+)\s+(?:who|that|which)\s+(\w+)\s+(.+)$", m[2], re.I)
            said = next((k for k in sorted(w.phrases, key=len, reverse=True) if re.match(re.escape(k) + r"\s+\S", m[2], re.I)), None)
            if said and re.search(r'\s(%s)\s' % AUX, ' ' + m[2] + ' ', re.I):
                said = None                 # "lop-eared rabbits are under a year old": the auxiliary marks the split, not the phrase
            if rel:
                subj, pred = rel[2], rel[3]
            elif said:
                subj, pred = m[2][:len(said)], m[2][len(said):].strip()      # "No electric cars use petrol" after "... are electric cars"
            else:
                subj, pred = cut(m[2], singular=m[1].lower() in ('every', 'each', 'any'))
            w.phrases += [re.sub(r'(?i)^(?:are|is|were|was)\s+(?:a |an )?', '', x.strip()) for x in (subj, pred) if x and len(x.split()) <= 5]
            (a, _), (b, bn) = term(subj), term(pred)
            # "the lop-eared rabbits" after "all the rabbits ... are lop-eared" is the group already described: the adjective
            # term plus words of the earlier subject
            for A, _, B, _, _ in list(w.rules):
                if a and B and B < a and (a - B) <= A:
                    a = B
                    break
            neg = m[1].lower().startswith('no')
            w.rule(a, True, b, not (bn ^ neg) if not neg else bn, i); continue
        m = re.match(r"only\s+(.+)$", body, re.I)
        if m:
            subj, pred = cut(m[1])
            (a, _), (b, _) = term(subj), term(pred); w.rule(b, True, a, True, i); continue
        m = re.match(r"(?:some|a few|several|many|most|certain)\s+(.+)$", body, re.I)
        if m:
            subj, pred = cut(m[1])
            (a, _), (b, bn) = term(subj), term(pred)
            who = f'some {subj}'
            w.fact(who, a, True, i)
            w.fact(who, b, not bn, i); w.vocab |= {a, b}; continue
        m = re.match(r"an?\s+(\w+)\s+is\s+(?:an?|a kind of|a type of)\s+(.+)$", body, re.I)
        if m:
            (a, _), (b, _) = term(m[1]), term(m[2]); w.rule(a, True, b, True, i); continue
        m = re.match(r"(this|that)\s+(\w+)\s+(?:is|was|has|can|does)\s+(.+)$", body, re.I)
        if m:
            who = f'{m[1].lower()} {m[2].lower()}'
            (cls, _), (t, n) = term(m[2]), term(m[3])
            w.fact(who, cls, True, i); w.fact(who, t, not n, i); w.last = who; continue
        m = re.match(r"([A-Z][a-z]+)\s+(.+)$", body)
        if m and m[1].lower() not in START:
            # a plural class said without "all": "Penguins are birds", "Squares have four sides"
            t, n = term(m[2])
            if m[1].endswith('s') and re.match(r"(are|have|can|cannot|can't|don't|do not|aren't)\b", m[2], re.I) and frozenset({stem(m[1])}) != t:
                w.rule(frozenset({stem(m[1])}), True, t, not n, i); continue
            w.fact(m[1], t, not n, i); w.last = m[1]; continue
        m = re.match(r"(?:but |and |so )?(it|he|she|they)(?:'s|'re)?\s+(.+)$", body, re.I)
        if m and w.last and w.last != '*':
            t, n = term(m[2]); w.fact(w.last, t, not n, i); continue
        t, n = term(body)
        pron = bool(re.match(r"(?:but |and |so )?%s\b" % PRON, low))
        w.fact('*', t, not n, i, pron); w.last = '*'
    w.close()
    return w


WRAP = re.compile(r"^(?:so|then|therefore|and|now|ok(?:ay)?)?[,\s]*(?:(?:can|could|may|should|must|do|does|is|would) (?:we|i|you|it|that|this)\s+)?"
                  r"(?:(?:be )?(?:conclude|concluded|say|infer|inferred|assume|know|sure|certain|follow|mean|true|valid|correct|right|safe to say|fair to say|necessarily follow|necessarily true)\s+)+(?:that\s+|for sure\s+|from this\s+)*", re.I)


def statements(sents, question):
    if not re.search(r"\b(all|every|each|no|none|some|only|if|unless|either|or|whenever|when)\b", ' '.join(sents), re.I):
        return None
    w = read(sents)
    if not w.rules and not any(k.startswith('some ') for k in w.facts):
        return None

    def partial(bag):
        """A rule that shares words with what is known without matching: too close to call, so no answer."""
        return any(x & bag and not (x <= bag) for a, _, b, _, _ in w.rules for x in (a,))
    q = question.rstrip('?').strip()
    inner = WRAP.sub('', q)
    wrapped = inner != q and len(inner) > 2
    body = inner if wrapped else q

    def cite(src):
        src = [i for i in src if 0 <= i < len(sents)]
        return ' and '.join(quote(i, sents) for i in src[:3])

    def verdict(state, src, negq=False, note=''):
        if state == 'open':
            return '**Not necessarily.** What you said does not settle it either way' + (': ' + note if note else '.')
        yes = (state == 'yes') ^ negq
        if wrapped and negq:
            yes = state == 'no'
        return ('**Yes.**' if yes else '**No.**') + (' That follows from ' + cite(src) + '.' if cite(src) else '')
    # "Where is it?" after either/or
    if re.match(r"(?:so |then )?(where|which|what|who|when)\b", q, re.I) and w.either:
        for p_text, q_text, p, t in w.either:
            for mine, text, other_text in ((t, q_text, p_text), (p, p_text, q_text)):
                if w.match('*', mine, True, True) is not None and w.match('*', (p if mine is t else t), False, True) is not None:
                    place = re.sub(r"^(?:it(?:'s| is)|he(?:'s| is)|she(?:'s| is)|they(?:'re| are)|the \w+ is|\w+ is)\s+", '', swap(text.strip()), flags=re.I)
                    return f'**{place[0].upper() + place[1:]}.** It is one or the other, and the first is ruled out, so that is the only one left.' if mine is t else \
                        f'**{place[0].upper() + place[1:]}.** It is one or the other, and the second is ruled out, so that is the only one left.'
        return None
    m = re.match(r"(?:is|are|was|were|does|do|did|can|could|will|would|must|has|have|should)\s+(.+)$", body, re.I)
    core = m[1] if m and not wrapped else body
    quant = re.match(r"(any|some|all|every|each|no)\s+(.+)$", core, re.I)
    ws = (quant[2] if quant else core).split()
    names = {n for n in w.facts if n != '*' and not n.startswith('some ')}
    # a named thing, or "it"
    who = next((n for n in names if re.match(re.escape(n) + r'\b', quant[2] if quant else core, re.I)), None)
    if who is None and re.match(r"(it|he|she|they)\b", core, re.I) and w.last and w.last != '*' and not quant:
        who = w.last; rest = core.split(None, 1)[1] if ' ' in core else ''
    elif who:
        rest = (quant[2] if quant else core)[len(who):]
    if who:
        t, n = term(rest)
        if not t or not any(t <= v or v <= t for v in w.vocab):
            return None
        state, src = w.ask(who, t)
        if state == 'open':
            bag = set().union(*[ft for ft, sg, _, _ in w.facts.get(who, []) if sg])
            if partial(bag):
                return None
            some = [i for i, x in enumerate(sents) if re.match(r'(some|a few|several|many|most)\b', x, re.I) and t <= term(x)[0]]
            return verdict(state, src, n, (quote(some[0], sents) + f' is about some of them, which may or may not include {who}.') if some else '')
        return verdict(state, src, n)
    # a class: "are any snakes mammals", "do squares have four sides", "some cats are pets"
    for k in range(min(len(ws) - 1, 7), 0, -1):         # "rabbits at the rescue centre" is five words
        subj, _ = term(' '.join(ws[:k]))
        if subj in w.vocab:
            pred, n = term(' '.join(ws[k:]))
            if not pred or not any(pred <= v or v <= pred for v in w.vocab):
                return None
            w.facts['?'] = [(subj, True, -2, False)]
            w.close()
            state, src = w.ask('?', pred)
            kind = quant[1].lower() if quant else 'all'
            if state == 'open' and kind in ('any', 'some'):
                for other in [x for x in w.facts if x.startswith('some ')]:
                    if w.match(other, subj, True) is not None and w.match(other, pred, True) is not None:
                        return verdict('yes', w.match(other, pred, True), n)
                some = [i for i, s in enumerate(sents) if re.match(r'(some|a few|several|many|most)\b', s, re.I)]
                note = (quote(some[0], sents) + ' does not say whether those are the ones in question.') if some else ''
                return verdict('open', [], n, note)
            if state == 'open':
                some = [i for i, s in enumerate(sents) if re.match(r'(some|a few|several|many|most)\b', s, re.I)]
                note = (quote(some[0], sents) + ' is about some of them, not all, so it cannot be applied to every case.') if some else ''
                return verdict('open', [], n, note)
            if kind == 'no':
                state = {'yes': 'no', 'no': 'yes'}[state]
            return verdict(state, src, n)
    # a plain statement: "did it rain", "does the shop open"
    t, n = term(core)
    pron = bool(re.match(PRON + r'\b', core, re.I))
    if not t or not any(t <= v or v <= t for v in w.vocab):
        return None
    state, src = w.ask('*', t, pron or len(t) == 1)
    note = ''
    if state == 'open':
        for ft, _, _, fpron in w.facts.get('*', []):
            if not fpron and any(x & ft and x != ft and x not in w.loose for a, _, b, _, _ in w.rules for x in (a, b)) and \
                    not any(x == ft or (x in w.loose and x < ft) for a, _, b, _, _ in w.rules for x in (a, b)):
                return None
        for a, sa, b, sb, i in w.rules:
            if (a == t or (pron and (a < t or t < a))) and (w.match('*', b, sb, True) is not None or (b in w.loose and any(b < ft and fs == sb for ft, fs, _, _ in w.facts.get('*', [])))):
                note = quote(i, sents) + ' only runs one way: the result can happen for other reasons too.'
            elif (b == t or (pron and (b < t or t < b))) and w.match('*', a, not sa, True) is not None:
                note = quote(i, sents) + ' says what happens when the condition holds, not what happens when it does not.'
    return verdict(state, src, n, note)


def plural(word):
    w = word.lower()
    if w.endswith('fe'):
        return word[:-2] + 'ves'
    if w.endswith(('s', 'x', 'ch', 'sh')):
        return word + 'es'
    if w.endswith('y') and len(w) > 2 and w[-2] not in 'aeiou':
        return word[:-1] + 'ies'
    return word + 's'


def existential(q):
    """'Is there a knife in the drawer that is safe for children?' and 'Is any knife ... safe?' -> 'Are any knives ... safe ...?',
    the plural 'any' form the statement reader answers."""
    m = re.match(r"(?i)^\s*(?:is|are) there (?:a|an|any|one)\s+(\w+)(.*?)\s+(?:that|which|who)\s+(?:is|are|can be|could be)\s+(.+?)\?\s*$", q)
    if m:
        return f'Are any {plural(m[1]) if not m[1].endswith("s") else m[1]}{m[2]} {m[3]}?'
    # "Is there a soup in the freezer that contains meat?" -> "Do any soups in the freezer contain meat?"
    m = re.match(r"(?i)^\s*(?:is|are) there (?:a|an|any|one)\s+(\w+)(.*?)\s+(?:that|which|who)\s+([a-z]+)\b(.*?)\?\s*$", q)
    if m and m[3].lower() not in ('i', 'we', 'you', 'they'):
        verb = base_verb(m[3])
        if verb.lower() in ('can', 'could', 'will', 'would', 'should', 'must', 'might'):
            return f'Can any {plural(m[1]) if not m[1].endswith("s") else m[1]}{m[2]}{m[4]}?'
        return f'Do any {plural(m[1]) if not m[1].endswith("s") else m[1]}{m[2]} {verb}{m[4]}?'
    m = re.match(r"(?i)^\s*(?:is|are) there (?:a|an|any|one)\s+(\w+)\b(.*?)\?\s*$", q)
    if m and not re.search(r"(?i)\b(?:that|which|who)\b", m[2]):
        return f'Are any {plural(m[1]) if not m[1].endswith("s") else m[1]}{m[2]}?'
    # "Do any of the cars in the car park use petrol?" -> "Do any cars in the car park use petrol?"
    q = re.sub(r"(?i)^(\s*(?:do|does|are|is|can|could|will) any) of (?:the|those|these|my|our) ", r"\1 ", q)
    return q


def base_verb(v):
    """contains -> contain, has -> have, goes -> go, flies -> fly, uses -> use."""
    low = v.lower()
    irregular = {'has': 'have', 'does': 'do', 'goes': 'go', 'is': 'are', 'was': 'were'}
    if low in irregular:
        return irregular[low]
    if low.endswith('ies') and len(low) > 4:
        return v[:-3] + 'y'
    if re.search(r'(?:ss|sh|ch|x|zz|o)es$', low):
        return v[:-2]
    if low.endswith('s') and not low.endswith('ss'):
        return v[:-1]
    return v


def premises(text):
    """'Every one of the X is one of the Y' and 'Each of the X is a Y' -> 'All the X are Y', the form the statement reader takes."""
    text = re.sub(r"(?i)\bevery one of the ([a-z][a-z -]+?) is one of the ([a-z][a-z -]+?)([.!])", r"All the \1 are \2\3", text)
    text = re.sub(r"(?i)\beach of the ([a-z][a-z -]+?) is (?:a|an|one of the) ([a-z][a-z -]+?)([.!])", lambda m: f"All the {m[1]} are {m[2]}{m[3]}", text)
    return text
    m = re.match(r"(?i)^\s*is (?:any|a single)\s+(\w+)\b(.*\?)\s*$", q)
    if m:
        return f'Are any {plural(m[1])}{m[2]}'
    return q


def solve(text):
    text = premises(text)
    text = re.sub(r'\b(Mr|Mrs|Ms|Dr|Prof)\.?\s+(?=[A-Z])', '', text)
    one = re.match(r"(?is)^\s*(?:if|given that|given|suppose|supposing|assuming|say)\s+(.+?),\s*(?:then\s+)?((?:is|are|does|do|did|can|will|was|were|who|which|what|where)\b[^.?!]*\?)\s*$", text)
    if one:                                     # "If all cats are animals and Tom is a cat, is Tom an animal?"
        text = '. '.join(x.strip()[0].upper() + x.strip()[1:] for x in re.split(r",?\s+and\s+|;\s*", one[1]) if x.strip()) + '. ' + one[2][0].upper() + one[2][1:]
    sents = split_sentences(text)
    qs = [s for s in sents if s.endswith('?')]
    facts = [s for s in sents if not s.endswith('?')]
    if len(qs) != 1 or not facts or len(text) > 700 or sents[-1] != qs[0]:
        return None
    asked = existential(qs[0])
    for fn in (ordering, statements):
        try:
            r = fn(facts, asked)
        except Exception:
            r = None
        if r:
            return r
    return None


def respond(messages):
    reply = solve(messages[-1]['content'])
    if not reply:
        return None
    return dict(route='chat/solve-logic', response=reply, reasoning=True)
