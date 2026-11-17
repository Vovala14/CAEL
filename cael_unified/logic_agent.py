"""The Logician: "all / none / some / every" statements and what follows from them.

"All the books on the top shelf are novels. None of the novels are in French. Is there a French book on the top shelf?"
"Every student in the choir plays an instrument. Lena is in the choir. Does Lena play an instrument?"

Each statement becomes a relation between two sets of things (a set is the group of content words that names it):
all A are B, no A are B, some A are B, x is an A. A question asks whether something of one set can be in another, or
whether a named one has a property. The answer follows the chain of "all" statements; a "none" anywhere on the chain
makes it No. An answer is given only when the chain decides it (Yes or No); otherwise None, and solve_logic.py's
wider reading takes the question.
"""
import re

STOP = set('a an the of is are was were be been am do does did has have had there any some all every each none no not that this these those it its they them '
           'to in on at for by with from as and or but so if then than too very also just only really my your our his her their i you we he she'.split())
GENERIC = {'thing', 'things', 'one', 'ones', 'item', 'items', 'object', 'objects', 'stuff', 'kind', 'type', 'people', 'person', 'student', 'students', 'member',
           'members', 'everyone', 'everybody', 'anyone', 'anybody', 'kid', 'kids', 'child', 'children', 'guy', 'guys', 'fruit', 'food', 'animal', 'animals',
           'plant', 'plants', 'creature', 'creatures', 'vehicle', 'vehicles', 'drink', 'drinks'}
IRREGULAR = {'children': 'child', 'people': 'person', 'men': 'man', 'women': 'woman', 'mice': 'mouse', 'geese': 'goose', 'feet': 'foot', 'teeth': 'tooth',
             'knives': 'knife', 'leaves': 'leaf', 'shelves': 'shelf', 'wolves': 'wolf'}


def stem(w):
    w = w.lower()
    if w in IRREGULAR:
        return IRREGULAR[w]
    for cut, keep in (('ies', 2), ('sses', 3), ('shes', 3), ('ches', 3), ('xes', 2), ('s', 3)):
        if w.endswith(cut) and len(w) - len(cut) >= keep and not w.endswith(('ss', 'us', 'is')):
            return w[:-len(cut)] + ('y' if cut == 'ies' else cut[:-2] if len(cut) > 2 else '')
    return w


def term(text, keep_generic=False):
    ws = [stem(w) for w in re.findall(r"[A-Za-z][A-Za-z'-]*", text) if w.lower() not in STOP]
    core = frozenset(w for w in ws if keep_generic or w not in {stem(g) for g in GENERIC})
    return core or frozenset(ws)


def read(sentences):
    """(all, none, some, members) relations; each with the sentence it came from."""
    alls, nones, somes, members = [], [], [], []
    for s in sentences:
        t = s.strip().rstrip('.!')
        m = re.match(r"(?i)^(?:all|every|each|any)(?: of)?(?: the)? (.+?) (?:is|are) (?:a |an )?(.+)$", t)
        if m:
            alls.append((term(m[1]), term(m[2]), s)); continue
        m = re.match(r"(?i)^(?:no|none of|not one of)(?: the)? (.+?) (?:is|are) (?:a |an )?(.+)$", t)
        if m:
            nones.append((term(m[1]), term(m[2]), s)); continue
        m = re.match(r"(?i)^(?:some|a few|several|many|most)(?: of)?(?: the)? (.+?) (?:is|are) (?:a |an )?(.+)$", t)
        if m:
            somes.append((term(m[1]), term(m[2]), s)); continue
        m = re.match(r"(?i)^(?:all|every|each)(?: of)?(?: the| my| our)? ([a-z]+(?: (?:in|on|at|from|of) (?:the |my |our )?[a-z0-9 ]+?)?) ([a-z]+s|[a-z]+) (.+)$", t)
        if m and (m[2].lower() not in STOP or m[2].lower() in ('has', 'have')):
            alls.append((term(m[1]), term(m[3] if m[2].lower() in ('has', 'have') else m[2] + ' ' + m[3], True), s)); continue
        m = re.match(r"(?i)^(?:no|none of the|none of my) ([a-z]+(?: (?:in|on|at|from|of) (?:the |my |our )?[a-z ]+?)?) ([a-z]+s|[a-z]+) (.+)$", t)
        if m and (m[2].lower() not in STOP or m[2].lower() in ('has', 'have')):
            nones.append((term(m[1]), term(m[3] if m[2].lower() in ('has', 'have') else m[2] + ' ' + m[3], True), s)); continue
        m = re.match(r"(?i)^(?:nobody|no one|no-one|none of those|none of the people|no student|no person) (?:who|that) (.+?) (?:needs? to|has to|have to|must|can|will|is|are|gets?|needs?) (.+)$", t)
        if m:
            nones.append((term(m[1], True), term(m[2], True), s)); continue
        m = re.match(r"^([A-Z][a-z]+|[Mm]y [a-z]+|[Tt]he [a-z]+) (?:is|was) (?:a |an |one of the |in |on |at |part of )?(?:the |my |our )?(.+)$", t)
        if m:
            members.append((m[1].lower(), term(m[2]), s))
    return alls, nones, somes, members


def same(a, b):
    """Two set names mean the same set: equal, or differing only by a generic class word ("student in the choir" / "the choir")."""
    if a == b:
        return True
    generic = {stem(g) for g in GENERIC}
    return bool(a & b) and (a - b) <= generic and (b - a) <= generic


def closure(start, alls):
    """Every set that 'start' is inside, with the statements used."""
    seen, used, frontier = [start], [], [start]
    while frontier:
        x = frontier.pop()
        for a, b, s in alls:
            if same(a, x) and not any(same(b, y) for y in seen):
                seen.append(b); used.append(s); frontier.append(b)
    return seen, used


def quote(sents):
    return ' and '.join(f'"{s.strip().rstrip(".")}"' for s in dict.fromkeys(sents))


def out(text):
    return dict(route='chat/solve-logic', response=text, sources=[], reasoning=True, details='Followed from the all/none/some statements given (logic_agent.py).')


def solve(text):
    sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]
    qs = [s for s in sents if s.endswith('?')]
    if len(qs) != 1 or len(sents) < 2:
        return None
    q = qs[0].rstrip('?')
    alls, nones, somes, members = read([s for s in sents if not s.endswith('?')])
    if not (alls or nones):
        return None
    # "Is there a French book on the top shelf?" / "Are any of the mugs in the cupboard chipped?" / "Can a novel be in French?"
    m = re.match(r"(?i)^(?:so,? |then,? |ok(?:ay)?,? )?(?:is there|are there|could there be|can there be)(?: a| an| any| some)? (.+)$", q)
    m2 = re.match(r"(?i)^(?:so,? |then,? )?(?:are|is) (?:any|some)(?: of)?(?: the)? (.+?) (?:a |an )?([a-z]+(?: [a-z]+)?)$", q) if not m else None
    m3 = re.match(r"(?i)^(?:so,? |then,? )?(?:can|could) (?:a|an|any) (.+?) be (?:a |an )?(.+)$", q) if not (m or m2) else None
    m4 = re.match(r"(?i)^(?:so,? |then,? )?(?:does|do|is|are|can|will|could|would) (?:anyone|anybody|someone|any(?: of the)? [a-z]+) (?:in|from|on|at|of) (.+?) "
                  r"(?:need(?:s)? to|have to|has to|need|be|get) (.+)$", q) if not (m or m2 or m3) else None
    if m4:
        group, prop = term(m4[1]), term(m4[2], True)
        ups, used = closure(group, alls)
        for a, b, s in nones:
            for up in ups[1:]:
                if (same(a, up) or (a and a <= up)) and (same(b, prop) or b == prop):
                    return out(f"**No.** You said {quote(used + [s])}, so nobody there does.")
        return None
    whole = term(m[1]) if m else (term(m2[1]) | term(m2[2])) if m2 else (term(m3[1]) | term(m3[2])) if m3 else None
    if whole:
        subjects = [a for a, _, _ in alls + nones]
        for subject in sorted(subjects, key=len, reverse=True):
            if not subject <= whole and not any(same(subject, whole - extra) for extra in [whole - subject]):
                continue
            prop = whole - subject
            if not prop:
                continue
            ups, used = closure(subject, alls)
            for a, b, s in nones:
                for up in ups:
                    if (same(a, up) and same(b, prop)) or (same(b, up) and same(a, prop)):
                        return out(f"**No.** You said {quote(used + [s])}. Put together, nothing in the first group can be in the second, so there is none.")
            if any(same(up, prop) for up in ups[1:]):
                return out(f"**Yes**, if there are any at all: you said {quote(used)}, so every one of them is.")
        return None
    # "Does Lena play an instrument?" / "Is Lena a musician?"
    m = re.match(r"(?i)^(?:so,? |then,? )?(?:does|did|do|is|was|can) ([A-Z][a-z]+|my [a-z]+|the [a-z]+) (?:a |an |the )?(.+)$", q)
    if m:
        who, prop = m[1].lower(), term(m[2], True)
        for name, group, s in members:
            if name != who:
                continue
            ups, used = closure(group, alls)
            if any(same(up, prop) or {stem(w) for w in up} == {stem(w) for w in prop} for up in ups[1:]):
                return out(f"**Yes.** You said {quote(used + [s])}, so it applies to {m[1]}.")
            for a, b, s2 in nones:
                for up in ups:
                    if same(a, up) and (same(b, prop) or {stem(w) for w in b} == {stem(w) for w in prop}):
                        return out(f"**No.** You said {quote(used + [s, s2])}, so that rules it out for {m[1]}.")
    return None


def respond(messages):
    if not messages or messages[-1].get('role') != 'user':
        return None
    last = messages[-1]['content']
    last = re.sub(r"(?i)^\s*(?:ok(?:ay)?|right|next|another one|and|now|here'?s another)[,.:!]?\s+", '', last)
    try:
        return solve(last)
    except Exception:
        return None
