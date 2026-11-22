"""Think before answering, with a swarm (0.4.4). Non-neural: readers, a derivation search and fixed rules.

A neural model "thinks" by writing out steps before its answer. CAEL does the same with symbols:

  1. Readings   the question is read several ways: as asked; with all of the user's turns as one message (for readers
                that look only at the last turn); and statements and question split apart (meesix.unfold).
  2. Swarm      every exact reader in CAEL proposes an answer to every reading, in parallel: the everyday readers
                (everyday_exact), story sums (word_math), "where did I ...?" (recall_did), labelled accounts (swarm),
                the general sum and logic solvers (solve_math, solve_logic).
  3. Check      each proposal is checked on its own:
                  - type: a "how many" question needs a number, "what time" a clock time, "which day" a weekday,
                    "is/does/could ..." a yes or no; "can't be known" or "you didn't say" fits any question;
                  - working: a number answer to a word problem must be derivable from the numbers the user gave, and
                    the derivation that uses the most of them is found by search (like the ARC solver's program
                    search). An answer that leaves stated numbers unused, or cannot be derived at all, is marked down.
  4. Vote       proposals are grouped by their answer. Each distinct reader adds its weight once, scaled by its check;
                agreement between independent readers and readings is what makes an answer trusted.
  5. Decide     the best-supported checked answer is given, with the readers that agreed in its details. When two
                checked answers that both use every stated number disagree, CAEL says so instead of picking one.
                When nothing passes the check, CAEL's usual pipeline answers as before.

Turn it off with CAEL_THINK=0.
"""
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, wait
from fractions import Fraction
from itertools import combinations

ROUTE = 'chat/think'
POOL = ThreadPoolExecutor(8)
INSIDE = threading.local()
NUMWORDS = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
            'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18,
            'nineteen': 19, 'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90,
            'hundred': 100, 'dozen': 12, 'once': 1, 'twice': 2, 'half': Fraction(1, 2), 'quarter': Fraction(1, 4)}
WEIGHT = {'relations': 1.0, 'staffing': 1.0, 'time_engine': 1.0, 'state_tracker': 1.0, 'story_math': 1.0, 'number_puzzle': 1.0, 'missing_info': 1.0, 'scoped_facts': 1.0, 'everyday_choice': 1.0, 'consistency': 1.0, 'induced': 1.0, 'everyday_hard': 1.0, 'explain_more': 1.0, 'everyday_exact': 1.0, 'everyday_more': 1.0, 'constraint_logic': 0.95, 'word_math': 0.9, 'recall_did': 0.9, 'swarm': 0.9, 'solve_logic': 0.8, 'solve_math': 0.6}
ABSTAIN = re.compile(r"(?i)\b(?:can'?t (?:be )?(?:tell|know|worked out)|no way to know|didn'?t tell me|haven'?t told me|nobody can know|"
                     r"don'?t establish|not settled|not necessarily|there isn'?t one|can'?t know|isn'?t known|not known|"
                     r"can'?t be answered|contradict\w*|can'?t be determined|nobody can know|didn'?t exist|false premise)\b")
WEAK = re.compile(r'fallback|unknown|clarify|unsupported|insufficient|failed|last-resort|evidence-missing')


# ------------------------------------------------------------------ readings
def readings(messages):
    users = [m for m in messages if m.get('role') == 'user']
    got = [('as asked', messages)]
    if len(users) > 1:
        merged = ' '.join(m['content'].strip() for m in users[-6:])
        got.append(('all turns as one', [dict(role='user', content=merged)]))
    # number words as digits ("seven cards a minute" -> "7 cards a minute"), for readers that only see numerals
    small = {k: v for k, v in NUMWORDS.items() if isinstance(v, int) and 2 <= v <= 90 and k not in ('once', 'twice', 'dozen', 'hundred')}
    pat = re.compile(r'\b(' + '|'.join(sorted(small, key=len, reverse=True)) + r')\b(?!-)', re.I)
    if any(pat.search(m['content']) for m in users):
        digits = [dict(m, content=pat.sub(lambda x: str(small[x[1].lower()]), m['content'])) if m.get('role') == 'user' else m for m in messages]
        got.append(('number words as digits', digits))
    try:
        # rules learned automatically (tools/autofix.py) map wordings the readers miss onto ones they read (2026-11-22)
        from . import learned_rewrites
        base = got[-1][1] if got[-1][0] == 'number words as digits' else messages
        changed = False
        new = []
        for m in base:
            if m.get('role') == 'user':
                t, used = learned_rewrites.rewrite(m['content'])
                changed = changed or bool(used)
                new.append(dict(m, content=t))
            else:
                new.append(m)
        if changed:
            got.append(('learned rewrites', new))
    except Exception:
        pass
    try:
        from . import meesix
        unfolded = meesix.unfold(messages)
        if unfolded:
            got.append(('statements apart', unfolded))
    except Exception:
        pass
    return got


def proposers():
    from . import constraint_logic, everyday_exact, everyday_hard, everyday_more, explain_more, induced_readers, recall_did, relations, solve_logic, staffing, state_tracker, story_math, time_engine, number_puzzle, missing_info, scoped_facts, everyday_choice, consistency, solve_math, swarm, word_math
    return [('relations', relations.respond), ('staffing', staffing.respond), ('time_engine', time_engine.respond), ('state_tracker', state_tracker.respond), ('story_math', story_math.respond), ('number_puzzle', number_puzzle.respond), ('missing_info', missing_info.respond), ('scoped_facts', scoped_facts.respond), ('everyday_choice', everyday_choice.respond), ('consistency', consistency.respond), ('induced', induced_readers.respond), ('everyday_hard', everyday_hard.respond), ('everyday_exact', everyday_exact.respond), ('everyday_more', everyday_more.respond), ('constraint_logic', constraint_logic.respond),
            ('explain_more', explain_more.respond),
            ('word_math', word_math.respond), ('recall_did', recall_did.respond),
            ('swarm', swarm.chat_reply), ('solve_logic', solve_logic.respond), ('solve_math', solve_math.respond)]


# ------------------------------------------------------------------ checking
def question_of(messages):
    last = [m['content'] for m in messages if m.get('role') == 'user'][-1]
    qs = re.findall(r'[^.!?\n]*\?', last)
    return (qs[-1] if qs else last).strip()


def qtype(q):
    q = re.split(r',\s*', q)[-1].strip().lower()
    if re.search(r'\bwhat (?:day and )?time\b|\bwhen (?:should|do|does|will|is|can)\b.*\b(?:take|come out|tune|start|end|leave|arrive)', q):
        return 'time'
    if re.search(r'\b(?:which|what) (?:week)?day\b|\bwhat day of the week\b', q):
        return 'weekday'
    if re.search(r'\bwhat date\b|\bwhich date\b|\bwhich month\b|\bwhat month\b', q):
        return 'date'
    if re.search(r'\bhow (?:many|much)\b|\bwhat(?:\'s| is) the (?:total|sum|average|cost|price)\b|\bhow old\b|\bwhat age\b', q) or \
            (re.search(r'\bwhat(?:\'s| is) the difference\b', q) and re.search(r'\d', q)):
        return 'number'
    if re.match(r'(?:is|are|was|were|does|do|did|can|could|will|would|has|have|should|must)\b', q):
        return 'yesno'
    return 'other'


def key_of(reply):
    text = str(reply.get('response', ''))
    bold = re.search(r'\*\*(.+?)\*\*', text)
    k = (bold[1] if bold else text.split('\n')[0][:80]).lower()
    k = re.sub(r'[£$€,]', '', k)
    k = re.sub(r'(?<=\d)\.0+\b', '', k)
    k = re.sub(r'[^a-z0-9:. ]+', ' ', k)
    k = re.sub(r'\s+', ' ', k).strip(' .')
    num = re.match(r'(-?\d+(?:\.\d+)?)\b', k)
    if num:
        return num[1]
    if ABSTAIN.search(text[:200]):
        return 'unknown'
    return k


def type_ok(t, reply):
    text = str(reply.get('response', ''))
    head = (re.search(r'\*\*(.+?)\*\*', text) or [None, text[:120]])[1]
    if ABSTAIN.search(text[:220]):
        return True
    if t == 'number':
        return bool(re.search(r'\d|\b(?:none|no|zero|one|two|three|four|five|six|seven|eight|nine|ten|once|twice)\b', head.lower()))
    if t == 'time':
        return bool(re.search(r'\d{1,2}:\d{2}|\b\d{1,2}\s*(?:am|pm)\b|\bnoon\b|\bmidnight\b', head.lower()))
    if t == 'weekday':
        return bool(re.search(r'(?i)\b(?:mon|tues|wednes|thurs|fri|satur|sun)day\b', head))
    if t == 'date':
        return bool(re.search(r'(?i)\d|\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b', head))
    if t == 'yesno':
        return bool(re.search(r'(?i)^\s*(?:yes|no|not)\b', head))
    return True


def stated_numbers(messages):
    """The numbers the user gave, in order (not years, clock times, dates or ordinals)."""
    text = ' '.join(m['content'] for m in messages if m.get('role') == 'user')
    text = re.sub(r'\b\d{1,2}:\d{2}\b', ' ', text)
    text = re.sub(r'(?i)\b\d{1,2}(?:st|nd|rd|th)\b', ' ', text)
    text = re.sub(r'(?i)\b(?:1[5-9]|20)\d{2}\b', ' ', text)
    out = []
    for m in re.finditer(r'(?i)\b\d+(?:\.\d+)?\b|\b(?:' + '|'.join(NUMWORDS) + r')\b', text):
        w = m[0].lower()
        if w in ('one',) and re.match(r'(?i)\s+(?:of|day|another|by)\b', text[m.end():]):
            continue            # "one of them", "one day": not a quantity
        out.append(Fraction(w) if w[0].isdigit() else Fraction(NUMWORDS[w]))
    return out[:7]


def best_derivation(target, nums):
    """The most stated numbers a derivation of `target` can use, with + − × ÷ (exact) and whole-number division up or down.
    0 when it can't be derived; -1 when there is nothing to check."""
    if not nums:
        return -1
    n = len(nums)
    vals = {}
    for i in range(n):
        vals[1 << i] = {nums[i]}
    full = (1 << n) - 1
    for mask in range(1, full + 1):
        if mask in vals and bin(mask).count('1') == 1:
            continue
        acc = set()
        sub = (mask - 1) & mask
        while sub:
            other = mask ^ sub
            if sub < other and sub in vals and other in vals:
                for x in vals[sub]:
                    for y in vals[other]:
                        acc.update((x + y, x - y, y - x, x * y))
                        if y:
                            acc.add(x / y)
                            if x / y != int(x / y):
                                acc.update((Fraction(int(x // y)), Fraction(-int(-x // y))))
                        if x:
                            acc.add(y / x)
                            if y / x != int(y / x):
                                acc.update((Fraction(int(y // x)), Fraction(-int(-y // x))))
                    if len(acc) > 4000:
                        break
            sub = (sub - 1) & mask
        if acc:
            vals[mask] = acc
    best = 0
    for mask, vs in vals.items():
        if target in vs:
            best = max(best, bin(mask).count('1'))
    return best


ARITH = re.compile(r'reason|solve-math|exact-(?:till|owed|rate|bags|tally|packs|change|fraction|area|runs-out)|calc|helper')


def check(reply, messages, t, nums):
    """A score in (0, 1.2] for a proposal, and why."""
    if not reply or not str(reply.get('response', '')).strip():
        return 0, 'empty'
    route = str(reply.get('route', ''))
    if WEAK.search(route):
        return 0, 'not an answer'
    if not type_ok(t, reply):
        return 0, f'not a {t} answer'
    score, why = 1.0, 'right type'
    k = key_of(reply)
    if ARITH.search(route) and re.fullmatch(r'-?\d+(?:\.\d+)?', k) and nums:
        target = Fraction(k)
        used = best_derivation(target, nums)
        if used == 0:
            if target in nums:
                return 0.5, 'a stated number repeated, not worked out'
            return 0.4, 'cannot be worked out from the stated numbers'
        if used == len(nums):
            score, why = 1.2, f'derivable using all {len(nums)} stated numbers'
        else:
            score, why = 0.7 + 0.5 * used / len(nums), f'derivable from {used} of {len(nums)} stated numbers'
    return score, why


# ------------------------------------------------------------------ the swarm
def run(messages):
    """A reply dict when a checked answer is well supported, else None (the usual pipeline answers)."""
    if os.environ.get('CAEL_THINK', '1') == '0' or getattr(INSIDE, 'active', False):
        return None
    users = [m for m in messages if m.get('role') == 'user']
    if not users or len(users[-1]['content']) > 700:
        return None
    q = question_of(messages)
    if not q.endswith('?') and not re.match(r'(?i)(?:how|what|which|who|when|where|is|are|does|do|did|can|could)\b', q):
        return None
    try:        # the sharing, rates and quantity helpers keep their problems (they ask "whole items or fractions?",
        # refuse unsafe input, and their follow-ups depend on their own replies), as in meesix.specialists
        from . import everyday_hard, helper_groups, induced_readers, helper_quantities, helper_rates
        last = users[-1]['content']
        from . import story_math as _sm, state_tracker as _st, time_engine as _te
        if everyday_hard.respond(messages) is not None or induced_readers.respond(messages) is not None or                 (_sm.respond(messages) or {}).get('route') == 'chat/story-math-count' or _st.respond(messages) is not None or _te.respond(messages) is not None:
            raise LookupError       # a harder shape read completely: the swarm decides, not a helper's question (2026-11-22)
        if helper_groups.reply(last, messages) is not None or helper_rates.reply(last, messages) is not None:
            return None
        kept = helper_quantities.reply(last, messages)
        if kept is not None and kept.get('route') == 'helper/quantity':
            return None
    except LookupError:
        pass
    except Exception:
        pass
    t = qtype(q)
    nums = stated_numbers(messages)
    jobs = []
    INSIDE.active = True
    try:
        for rname, msgs in readings(messages):
            for pname, fn in proposers():
                jobs.append((rname, pname, POOL.submit(_call, fn, msgs)))
        done, _ = wait([f for _, _, f in jobs], timeout=6)
    finally:
        INSIDE.active = False
    props = []
    for rname, pname, fut in jobs:
        if fut not in done:
            continue
        reply = fut.result()
        if not reply:
            continue
        score, why = check(reply, messages, t, nums)
        if score <= 0:
            continue
        props.append(dict(reading=rname, reader=pname, reply=reply, key=key_of(reply), score=score, why=why))
    if not props:
        return None
    groups = {}
    for p in props:
        g = groups.setdefault(p['key'], dict(readers={}, readings=set(), best=None))
        prev = g['readers'].get(p['reader'], 0)
        g['readers'][p['reader']] = max(prev, WEIGHT.get(p['reader'], 0.5) * p['score'])
        g['readings'].add(p['reading'])
        if g['best'] is None or (p['reader'] in ('relations', 'staffing', 'time_engine', 'state_tracker', 'story_math', 'number_puzzle', 'missing_info', 'scoped_facts', 'everyday_choice', 'consistency', 'induced', 'everyday_hard', 'everyday_exact', 'everyday_more', 'constraint_logic'), p['score'], p['reading'] == 'as asked') > \
                (g['best']['reader'] in ('relations', 'staffing', 'time_engine', 'state_tracker', 'story_math', 'number_puzzle', 'missing_info', 'scoped_facts', 'everyday_choice', 'consistency', 'induced', 'everyday_hard', 'everyday_exact', 'everyday_more', 'constraint_logic'), g['best']['score'], g['best']['reading'] == 'as asked'):
            g['best'] = p
    for g in groups.values():
        g['support'] = sum(g['readers'].values()) + 0.1 * (len(g['readings']) - 1)
    ranked = sorted(groups.items(), key=lambda kv: -kv[1]['support'])
    key, top = ranked[0]
    best = top['best']
    trusted = best['reader'] in ('relations', 'staffing', 'time_engine', 'state_tracker', 'story_math', 'number_puzzle', 'missing_info', 'scoped_facts', 'everyday_choice', 'consistency', 'induced', 'everyday_hard', 'everyday_exact', 'everyday_more', 'constraint_logic', 'explain_more') or len(top['readers']) >= 2 or (best['score'] >= 1.2 and best['reader'] in ('word_math', 'recall_did', 'swarm'))
    if not trusted:
        return None
    if len(ranked) > 1:
        key2, second = ranked[1]
        rival = second['best']
        if key != 'unknown' and key2 != 'unknown' and best['score'] >= 1.2 and rival['score'] >= 1.2 and second['support'] >= 0.8 * top['support']:
            return dict(route=ROUTE + '-two-readings', sources=[], reasoning=True,
                        response=f'I get two different answers depending on how this is read: **{_head(best["reply"])}** '
                                 f'({best["why"]}) or **{_head(rival["reply"])}** ({rival["why"]}). Could you say which you mean?',
                        think=_trace(ranked, t, nums))
    out = dict(best['reply'])
    out['think'] = _trace(ranked, t, nums)
    out['details'] = (str(out.get('details', '')) + f' | think: {len(top["readers"])} reader(s) agreed '
                      f'({", ".join(sorted(top["readers"]))}) over {len(top["readings"])} reading(s); check: {best["why"]}').strip(' |')
    return out


def _call(fn, msgs):
    INSIDE.active = True
    try:
        return fn(msgs)
    except Exception:
        return None
    finally:
        INSIDE.active = False


def _head(reply):
    text = str(reply.get('response', ''))
    m = re.search(r'\*\*(.+?)\*\*', text)
    return (m[1] if m else text[:60]).strip()


def _trace(ranked, t, nums):
    return dict(question_type=t, stated_numbers=[str(n) for n in nums],
                answers=[dict(answer=k, support=round(g['support'], 2), readers=sorted(g['readers']), readings=sorted(g['readings']),
                              check=g['best']['why']) for k, g in ranked[:4]])
