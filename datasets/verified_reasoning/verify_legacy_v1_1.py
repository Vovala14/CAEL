"""Check a model's reply against a CAEL Verified Reasoning row. Usable as an RL reward or for evaluation.

    from verify import check
    check(model_reply, row)            # -> True / False

Rules:
- the reply may contain working; the final answer is taken from the last line that has content (or a line starting
  "Answer:", or a \\boxed{...});
- numbers: equal after removing currency symbols and thousands separators (2 decimal places compared exactly);
- "Cannot be determined" accepts the usual phrasings (cannot / can't be determined, not enough information, unknown,
  impossible to tell, ...); contradictions and "there is none" have their own accepted phrasings;
- lists ("guitar, flute, drum") are compared as sets; weekdays, months and names case-insensitively;
- clock times compare as times ("9:30 am" == "09:30"); grids compare cell by cell.
"""
import re

UNKNOWN = re.compile(r"(?i)\b(?:cannot|can.?t|could not|couldn.?t|impossible to|not possible to|no way to)\s+(?:be\s+)?(?:determine|determined|tell|know|known|say|work (?:it )?out)\b|"
                     r"\b(?:not enough|insufficient)\s+(?:information|info|data)\b|\bundetermined\b|\bunknown\b|\bindeterminate\b|\bit depends\b|\bnot determinable\b")
CONTRA = re.compile(r"(?i)\bcontradict|\binconsistent\b|\bimpossible\b|\bcannot be both\b|\bcan.?t be both\b|\bfalse premise\b")
NONE = re.compile(r"(?i)\b(?:there is|there's|there are)\s+(?:none|no\b)|\bnone (?:left|remain)|\bno (?:\w+ )?(?:is |are )?left\b|\bnothing left\b|\bempty\b")
NOT_SAID = re.compile(r"(?i)\b(?:you )?(?:did not|didn.?t|never)\s+(?:say|tell|mention)|\bnot mentioned\b|\bno price was\b")


def final_answer(reply):
    text = str(reply).strip()
    boxed = re.findall(r'\\boxed\{([^{}]*)\}', text)
    if boxed:
        return boxed[-1].strip()
    m = re.findall(r'(?im)^\s*(?:final answer|answer)\s*[:\-]\s*(.+)$', text)
    if m:
        return m[-1].strip()
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return lines[-1] if lines else ''


def grid_of(text):
    rows = [r for r in (l.strip() for l in str(text).splitlines()) if re.fullmatch(r'(?:\d\s*)+', r)]
    return [[int(c) for c in re.findall(r'\d', r)] for r in rows]


def numbers(text):
    t = re.sub(r'(?<=\d),(?=\d{3}\b)', '', str(text))
    return [float(x) for x in re.findall(r'-?\d+(?:\.\d+)?', t)]


def clock(text):
    m = re.search(r'(?i)\b(\d{1,2}):(\d{2})\s*(am|pm)?', str(text))
    if not m:
        return None
    h, mi = int(m[1]), int(m[2])
    if m[3]:
        h = h % 12 + (12 if m[3].lower() == 'pm' else 0)
    return h * 60 + mi


def contains(pred, gold):
    """Every gold number appears in the prediction, counting repeats (5 and 5 need two 5s), in the same order."""
    i = 0
    for g in gold:
        while i < len(pred) and abs(pred[i] - g) >= 0.005:
            i += 1
        if i == len(pred):
            return False
        i += 1
    return True


def check(reply, row):
    gold = row['answer']
    whole = str(reply)
    if row.get('category') == 'arc_grids':
        pred = grid_of(whole.split('Test')[-1]) or grid_of(whole)
        g = grid_of(gold)
        # take the last block of the reply that has the gold grid's shape
        lines = [re.sub(r'(?i)^(?:final answer|answer|output|test output)\s*:\s*', '', l.strip()) for l in whole.splitlines()]
        blocks, cur = [], []
        for l in lines:
            if re.fullmatch(r'(?:\d\s*)+', l) and l:
                cur.append([int(c) for c in re.findall(r'\d', l)])
            elif cur:
                blocks.append(cur); cur = []
        if cur:
            blocks.append(cur)
        return any(b == g for b in blocks[-2:]) if blocks else False
    ans = final_answer(reply)
    low_gold = gold.lower()
    if low_gold == 'cannot be determined':
        return bool(UNKNOWN.search(ans) or (UNKNOWN.search(whole[-300:]) and not numbers(ans)))
    if low_gold == 'contradictory premise':
        return bool(CONTRA.search(whole))
    if low_gold == 'there is none':
        return bool(NONE.search(whole))
    if low_gold == 'you did not say':
        return bool(NOT_SAID.search(whole))
    if re.fullmatch(r'[A-Za-z0-9_]*\d[A-Za-z0-9_]*(?: \d+)?|[A-Z]{2} \d+', gold.strip()) and re.search(r'[A-Za-z]', gold):
        # codes such as 22A, BA 117, red_owl7: compared as whole tokens
        norm = lambda x: re.sub(r'[^a-z0-9_]', '', x.lower())
        return norm(gold) in [norm(w) for w in re.findall(r'[A-Za-z0-9_]+(?: \d+)?', ans)] or norm(ans) == norm(gold)
    label = re.match(r'([A-Z][a-z]+ [A-Za-z0-9]+): ', gold)
    if label:
        if label[1].lower() not in whole.lower():
            return False                                           # "which source still stands" must name the source
        value = gold[label.end():]
        words = [w for w in re.findall(r'[a-z0-9:]+', value.lower()) if len(w) >= 3 or any(c.isdigit() for c in w)]
        return all(w in whole.lower() for w in words)              # and give what it says, in any phrasing
    if ',' in gold and not re.search(r'\d', gold):                 # a list of items
        want = {x.strip().lower() for x in gold.split(',')}
        got = {x.strip(' .').lower() for x in re.split(r',|\band\b', ans) if x.strip(' .')}
        return want == got
    gc = clock(gold)
    if gc is not None:
        pc = clock(ans)
        day = re.match(r'(?i)(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', gold)
        if day and day[1].lower() not in ans.lower():
            return False
        return pc == gc
    gn = numbers(gold)
    if re.fullmatch(r'\d+', gold.strip()) and re.search(r'\b' + gold.strip() + r'[A-Za-z]', ans):
        return False                                               # "20" is not the code "20A"
    if gn and not re.search(r'(?i)[a-z]{3,}', re.sub(r'(?i)\b(?:days?|minutes?|h|min|g|kg|full|left|over|to spare|short|yes|no|nothing|should be refunded|refunded)\b', '', gold)):
        pn = numbers(ans)
        return bool(pn) and contains(pn, gn) and (not low_gold.startswith(('yes', 'no')) or ans.lower().startswith(low_gold.split(',')[0].lower()))
    if gn:
        pn = numbers(ans)
        return bool(pn) and contains(pn, gn) and all(w in ans.lower() for w in re.findall(r'(?i)\b(?:yes|no)\b', low_gold)[:1])
    g = re.sub(r'[^a-z0-9 ]', '', low_gold).strip()
    a = re.sub(r'[^a-z0-9 ]', '', ans.lower()).strip()
    return a == g or a.startswith(g + ' ') or a.endswith(' ' + g) or f' {g} ' in f' {a} '


if __name__ == '__main__':
    tests = [
        ('The total is $13.90, so the change is **$6.10**.\nAnswer: $6.10', dict(answer='$6.10', category='arithmetic'), True),
        ('Answer: 6.1', dict(answer='$6.10', category='arithmetic'), True),
        ('Answer: $7', dict(answer='$6.10', category='arithmetic'), False),
        ("We can't tell from the information given.", dict(answer='Cannot be determined', category='logic'), True),
        ('Answer: Saturday', dict(answer='Saturday', category='dates_times'), True),
        ('Answer: 9:30 am', dict(answer='9:30 am', category='memory'), True),
        ('Answer: 09:30', dict(answer='9:30 am', category='memory'), True),
        ('Answer: Monday 17:29', dict(answer='Monday 17:29', category='dates_times'), True),
        ('Answer: Tuesday 17:29', dict(answer='Monday 17:29', category='dates_times'), False),
        ('Answer: drum, guitar and flute', dict(answer='guitar, flute, drum', category='memory'), True),
        ('Answer: Omar', dict(answer='Omar', category='logic'), True),
        ('Answer: 6 full trays, 2 left over', dict(answer='6 full trays, 2 left over', category='arithmetic'), True),
        ('Answer: No, $120 short', dict(answer='No, $120 short', category='composite'), True),
        ('Answer: Yes, $120 to spare', dict(answer='No, $120 short', category='composite'), False),
        ('Output:\n1 0\n0 1', dict(answer='1 0\n0 1', category='arc_grids'), True),
    ]
    bad = [t for t in tests if check(t[0], t[1]) != t[2]]
    print('verifier self-test:', 'all passed' if not bad else bad)
