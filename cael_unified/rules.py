"""Self-learning rules: propose, test, keep.

A rule here is a small function found by CAEL's program search (codegen/synth.py, codegen/recurrence.py).
Learning one works like a careful scientist:

1. Hypotheses: search for a function using all examples but one, several times, each time hiding a different
   example (leave-one-out).
2. Test: each hypothesis must predict the example it never saw. Fitting what it was shown proves little;
   predicting what it was not shown is evidence.
3. Keep: only a function that passes the held-out tests and every example is stored in long-term memory
   (ltm.py), with the number of checks it passed. Later requests can reuse it by name or description, and
   people's "that's wrong" lowers its confidence until it is forgotten.

Number sequences ("what comes next: 2, 6, 12, 20?") use the same loop: hide the last term, find a rule that
predicts it, then use the rule for the next term.
"""
import re

from . import ltm
from .codegen import recurrence, specs
from .codegen.synth import render, synthesize

LEARNED_MARK = 'learned rule `{}`'


def hypotheses(cases, description, costs=None, seconds=4.0, folds=3):
    """Leave-one-out search. Returns [(code, params, held_out_passed, folds_tried)] best first."""
    n = len(cases)
    order = [n - 1, 0, n // 2][:max(0, min(folds, n - 2))] if n >= 3 else []
    found = {}
    for hidden in dict.fromkeys(order):
        shown = [c for i, c in enumerate(cases) if i != hidden]
        for code, params, check in candidates(shown, description, costs, seconds):
            entry = found.setdefault(code, [params, check, 0, 0])
            entry[3] += 1
            entry[2] += bool(check([cases[hidden]]))
    # A function found from all examples is also a hypothesis; its held-out record is whatever it earned above.
    for code, params, check in candidates(cases, description, costs, seconds):
        found.setdefault(code, [params, check, 0, 0])
    ranked = []
    for code, (params, check, passed, tried) in found.items():
        if check(cases):
            ranked.append((code, params, passed, max(tried, len(order))))
    ranked.sort(key=lambda h: (-h[2], len(h[0])))
    return ranked


def candidates(cases, description, costs, seconds):
    """Functions that fit the given cases: one expression from the search, or a counted loop."""
    out = []
    if len({len(c[0]) for c in cases}) != 1:
        return out
    expr, params, _stats = synthesize([c[0] for c in cases], [c[1] for c in cases], description,
                                      costs(description) if costs else None, seconds=seconds, inner_cost=10)
    if expr is not None:
        out.append((expr, params, lambda pairs, e=expr, p=params: not specs.passes(e, p, pairs)))
    if len(cases[0][0]) == 1:
        loop = recurrence.search(cases)
        if loop:
            out.append((('loop', loop), ['n'], lambda pairs, l=loop: all(
                isinstance(a[0], int) and a[0] >= 0 and recurrence.run(l[0], l[1], a[0]) == v for a, v in pairs)))
        test = recurrence.search_all(cases)
        if test:
            out.append((('all', test), ['n'], lambda pairs, t=test: all(
                isinstance(a[0], int) and a[0] >= 0 and recurrence.check_all(*t, a[0]) == v for a, v in pairs)))
    return out


def source(name, code, params):
    if isinstance(code, tuple) and code[0] == 'loop':
        return recurrence.render(name, params[0], *code[1])
    if isinstance(code, tuple) and code[0] == 'all':
        return recurrence.render_all(name, params[0], *code[1])
    return render(name, params, code)


def learn(name, cases, description='', costs=None, store=True):
    """Learn a rule from examples. Returns dict(code, checks, held_out, tried, stored) or None if nothing fits."""
    ranked = hypotheses(cases, description, costs)
    if not ranked:
        return None
    code, params, passed, tried = ranked[0]
    text = source(name, code, params)
    validated = tried > 0 and passed == tried
    stored = None
    if store and validated:
        stored = ltm.memory().add_rule(name, params, text, description, len(cases) + passed, cases)
    return dict(code=text, checks=len(cases) + passed, held_out=passed, tried=tried, validated=validated,
                stored=bool(stored), storage_scope=ltm.memory().lifetime if stored else None, hypotheses=len(ranked))


def run_rule(rule, args):
    from .codegen.python_vm import run_cases
    result = run_cases(rule['code'], [dict(name=rule['name'], args=list(args))])
    if result['status'] != 'ok' or len(result.get('cases', [])) != 1 or result['cases'][0]['status'] != 'value':
        raise ValueError('The learned rule is outside the bounded interpreter or failed its call')
    return result['cases'][0]['value']


# Sequences --------------------------------------------------------------------------------------
SEQUENCE = re.compile(r'(?i)(?:what(?:\'s| is| comes)? next|next (?:number|term)|continue|complete|what follows|extend)\D{0,40}?'
                      r'((?:-?\d+\s*,\s*){3,}-?\d+)|((?:-?\d+\s*,\s*){3,}-?\d+)\s*,?\s*(?:\.\.\.|…|\?|_+)\s*(?:what comes next)?\s*\??\s*$')


def differences(numbers, depth=4):
    """Finite differences: if some level becomes constant, extend it back up. Returns (next, level) or None."""
    rows = [list(numbers)]
    while len(rows) <= depth and len(rows[-1]) >= 2:
        last = rows[-1]
        if len(set(last)) == 1 and len(rows) > 1:
            break
        rows.append([b - a for a, b in zip(last, last[1:])])
    if len(set(rows[-1])) != 1 or len(rows[-1]) < 2:
        return None
    value = rows[-1][-1]
    for row in reversed(rows[:-1]):
        value = row[-1] + value
    return value, len(rows) - 1


def next_term(numbers):
    """(next value, rule code, explanation) or None. The rule must predict the last given term from the others."""
    # Hypothesis 0: a constant factor, read from all but the last number and checked on the last ("2, 4, 8, 16").
    if len(numbers) >= 4 and all(numbers[:-1]):
        ratios = {numbers[i + 1] / numbers[i] for i in range(len(numbers) - 2)}
        if len(ratios) == 1:
            ratio = ratios.pop()
            if numbers[-2] * ratio == numbers[-1] and float(ratio).is_integer():
                return int(numbers[-1] * ratio), f'{", ".join(map(str, numbers))}\n# each number is {int(ratio)} times the one before\n'
    # Hypothesis 1: a polynomial pattern, found by finite differences on all but the last number.
    shown = differences(numbers[:-1])
    if shown and shown[0] == numbers[-1]:
        value, level = differences(numbers)
        rows, row = [], list(numbers)
        for _ in range(level):
            row = [b - a for a, b in zip(row, row[1:])]
            rows.append(', '.join(map(str, row)))
        explained = '\n'.join(f'{"   " * i}differences: {r}' for i, r in enumerate(rows))
        return value, f'{", ".join(map(str, numbers))}\n{explained}\n# the last row is constant, so extend it back up\n'
    cases = [((i,), v) for i, v in enumerate(numbers)]
    shown, hidden = cases[:-1], cases[-1]
    for code, params, check in candidates(shown, 'sequence term number n', None, 3.0):
        if check([hidden]) and check(cases):
            text = source('term', code, params)
            rule = dict(name='term', code=text)
            try:
                value = run_rule(rule, (len(numbers),))
            except Exception:
                continue
            return value, text
    return None


def sequence_reply(text):
    match = SEQUENCE.search(text)
    if not match:
        return None
    numbers = [int(x) for x in re.findall(r'-?\d+', match[1] or match[2])]
    if len(numbers) > 30:
        return None
    found = next_term(numbers)
    if found is None:
        return dict(route='chat/rules-sequence', sources=[], details=DETAILS,
                    response='I could not find a rule that predicts these numbers. I test every candidate rule by hiding the '
                             'last number and checking that the rule predicts it, and none passed.')
    value, code = found
    shown = (f'The rule I found (term number n, starting at 0):\n\n```python\n{code}```' if code.startswith('def ') else
             f'How I found it:\n\n```\n{code}```')
    return dict(route='chat/rules-sequence', sources=[], details=DETAILS,
                response=f'The next number is **{value}**.\n\n{shown}\n'
                         f'I found it from the first {len(numbers) - 1} numbers only, and it correctly predicted the last one '
                         f'({numbers[-1]}) before I used it.')


DETAILS = ('Rule learning by hypothesis testing: candidate rules come from CAEL\'s non-neural program search and must predict '
           'examples they were not shown. Only rules that pass are kept in long-term memory (rules and counters only, '
           'never what people type).')


# Chat -------------------------------------------------------------------------------------------
LIST_ASK = re.compile(r'(?i)^\s*(?:what|which) (?:rules|functions) have you learn(?:ed|t)|^\s*(?:show|list) (?:me )?(?:your |the )?(?:learned |learnt )?(?:rules|memory)'
                      r'|^\s*what do you remember(?: long[- ]term)?\s*\??\s*$|^\s*how (?:reliable|confident) are (?:you|your engines)')
USE = re.compile(r'(?i)\b(?:run|use|apply|call|compute|what is|what\'s)\s+(?:the\s+)?(?:rule\s+|function\s+)?`?([a-z_][a-z0-9_]*)`?\s*(?:\(\s*(.*?)\s*\)|\s+(?:on|with|for|of)\s+(.+?))\s*\??\s*$')
FEEDBACK_BAD = re.compile(r'(?i)^\s*(?:that(?:\'s| is) (?:wrong|not right|incorrect|not correct)|wrong(?: answer)?|incorrect|no,? that(?:\'s| is) wrong|this is wrong)[.!]*\s*$')
FEEDBACK_GOOD = re.compile(r'(?i)^\s*(?:that(?:\'s| is) (?:right|correct)|correct|it works|that works|perfect|exactly)[.!]*\s*$')


def list_reply():
    data = ltm.memory().summary()
    lines = []
    if data['rules']:
        lines.append('**Rules I have learned** (name, checks passed, confidence, times used):')
        lines += [f'- `{name}`: {checks} checks, {conf:.0%}, used {uses}×' for name, checks, conf, uses in data['rules'][:20]]
    else:
        lines.append('I have not learned any rules yet. Give me a few examples of a function, for example '
                     '`area(2, 3) == 6`, `area(4, 5) == 20`, `area(1, 7) == 7`, and I will try to learn it.')
    rated = [(name, stats, conf) for name, stats, conf in data['engines'] if stats.get('verified', 0) + stats.get('failed', 0)]
    if rated:
        lines.append('\n**How often my engines\' answers passed independent checks:**')
        lines += [f'- {name}: {stats.get("verified", 0)} passed, {stats.get("failed", 0)} failed, '
                  f'{stats.get("corrected", 0)} corrected ({conf:.0%})' for name, stats, conf in rated[:10]]
    scope = ltm.memory().lifetime
    lines.append('\nThese rules and counters belong to '+
                 ('this request only.' if scope == 'request' else 'the explicitly supplied learning session.'))
    return dict(route='chat/rules-memory', response='\n'.join(lines), sources=[], details=DETAILS)


def use_reply(text):
    match = USE.search(text)
    if not match:
        return None
    rule = ltm.memory().rule(match[1])
    if rule is None:
        return None
    raw = match[2] if match[2] is not None else match[3]
    try:
        import ast
        args = ast.literal_eval('(' + raw.replace(' and ', ', ') + ',)')
        if any(isinstance(a, int) and not isinstance(a, bool) and abs(a) > 100_000 for a in args):
            raise ValueError
        value = run_rule(rule, args)
    except Exception:
        return None
    ltm.memory().used(rule['name'])
    call = f'{rule["name"]}({", ".join(map(repr, args))})'
    return dict(route='chat/rules-use', sources=[], details=DETAILS,
                response=f'`{call}` = **{value!r}**, using my {LEARNED_MARK.format(rule["name"])} '
                         f'({rule["checks"]} checks passed, confidence {ltm.confidence(rule):.0%}).\n\n```python\n{rule["code"]}```')


def feedback_reply(text, messages):
    """'that's wrong' / 'that's right' right after a reply that used a learned rule adjusts its confidence."""
    good = bool(FEEDBACK_GOOD.match(text))
    if not good and not FEEDBACK_BAD.match(text):
        return None
    previous = messages[-2]['content'] if len(messages) >= 2 and messages[-2].get('role') == 'assistant' else ''
    used = re.search(r'learned rule `([a-z_][a-z0-9_]*)`', previous)
    kind = 'chat/code' if '```python' in previous else 'helper/arithmetic' if re.search(r'^[^\n]* = -?\d', previous) else \
        'chat/reasoning' if 'Based on:' in previous or 'Worked out in steps' in previous else None
    if kind and not good:
        ltm.memory().record(kind, 'wrong', 'marked wrong by a person')
    if not used:
        return None
    rule = ltm.memory().rule_feedback(used[1], good)
    if good:
        return dict(route='chat/rules-feedback', sources=[], details=DETAILS,
                    response=f'Thanks! That raises my confidence in the rule `{used[1]}`.')
    still = rule is not None and used[1] in ltm.memory().data['rules']
    return dict(route='chat/rules-feedback', sources=[], details=DETAILS,
                response=(f'Thanks for telling me. I lowered my confidence in the rule `{used[1]}`.' if still else
                          f'Thanks for telling me. The rule `{used[1]}` has been marked wrong too often, so I have forgotten it.')
                + ' Examples showing the correct result would help me learn a better one.')


def reply(text, messages=()):
    if LIST_ASK.search(text):
        return list_reply()
    answer = feedback_reply(text, list(messages)) if messages else None
    if answer:
        return answer
    return sequence_reply(text) or use_reply(text)
