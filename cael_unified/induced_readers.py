"""Readers learned from verified examples (0.4.4 fix after release, 2026-11-22). Non-neural.

The readers in induced_readers.json were not written by hand. tools/induce.py learns them from the verified-reasoning
generator (datasets/verified_reasoning):
- each problem becomes a template, with its numbers, amounts, clock times, dates, weekdays and names as slots;
- problems with the same template are grouped;
- for each number in the answer, an exhaustive search finds one calculation over the slots that is right for every
  example in the group;
- a reader is kept only if it is right on every problem of a fresh batch made with a different random seed.

Here a stored reader matches the user's message against its template, computes the answer from the slot values, and
shows the calculation. It is a proposer in the thinking swarm (think.py).
"""
import json
import math
import re
from datetime import date, timedelta
from fractions import Fraction
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).with_name('induced_readers.json')
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
ONES = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen',
        'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen']
TENS = ['twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety']
WORDNUM = r'(?:(?:' + '|'.join(TENS) + r')(?:-(?:' + '|'.join(ONES[1:10]) + r'))?|' + '|'.join(sorted(ONES, key=len, reverse=True)) + r')'
MON = r'(?:' + '|'.join(MONTHS) + r')'

# slot types, in the order they are looked for; each is (name, regex)
SLOTS = [
    ('DATE', r'\b(?:\d{1,2} ' + MON + r' \d{4}|' + MON + r' \d{1,2}, \d{4})\b'),
    ('CLOCK', r'\b\d{1,2}:\d{2}(?: ?[ap]m)?\b'),
    ('MONEY', r'[$€£]\d[\d,]*(?:\.\d+)?'),
    ('PCT', r'\b\d+(?:\.\d+)?%'),
    ('NUM', r'\b\d[\d,]*(?:\.\d+)?\b|\b' + WORDNUM + r'\b'),
    ('WD', r'\b(?:' + '|'.join(DAYS) + r')\b'),
]
SLOT_RE = {k: v for k, v in SLOTS}


def word_value(w):
    w = w.lower()
    if w in ONES:
        return ONES.index(w)
    t, _, o = w.partition('-')
    return (TENS.index(t) + 2) * 10 + (ONES.index(o) if o else 0)


def slot_value(kind, raw):
    """A number for a slot (dates as day numbers, clocks as minutes, weekdays as 0-6), or None for text slots."""
    if kind == 'DATE':
        m = re.match(r'(\d{1,2}) (\w+) (\d{4})', raw) or re.match(r'(\w+) (\d{1,2}), (\d{4})', raw)
        if raw[0].isdigit():
            d, mo, y = int(m[1]), MONTHS.index(m[2]) + 1, int(m[3])
        else:
            mo, d, y = MONTHS.index(m[1]) + 1, int(m[2]), int(m[3])
        return Fraction(date(y, mo, d).toordinal())
    if kind == 'CLOCK':
        m = re.match(r'(\d{1,2}):(\d{2}) ?([ap]m)?', raw)
        h, mi = int(m[1]), int(m[2])
        if m[3]:
            h = h % 12 + (12 if m[3] == 'pm' else 0)
        return Fraction(h * 60 + mi)
    if kind == 'MONEY':
        return Fraction(raw[1:].replace(',', ''))
    if kind == 'PCT':
        return Fraction(raw[:-1])
    if kind == 'NUM':
        return Fraction(raw.replace(',', '')) if raw[0].isdigit() else Fraction(word_value(raw))
    if kind == 'WD':
        return Fraction(DAYS.index(raw))
    return None


# ------------------------------------------------------------------ expressions
def evaluate(expr, env):
    """expr is a nested list: ['slot', i] | ['const', v] | [op, a, b] | [unary, a]."""
    op = expr[0]
    if op == 'slot':
        return env[expr[1]]
    if op == 'const':
        return Fraction(expr[1])
    if op in ('floor', 'ceil'):
        v = evaluate(expr[1], env)
        return Fraction(math.floor(v) if op == 'floor' else math.ceil(v))
    if op == 'span':        # minutes from one clock time to a later one, past midnight if needed
        return (evaluate(expr[2], env) - evaluate(expr[1], env)) % 1440
    a, b = evaluate(expr[1], env), evaluate(expr[2], env)
    if op == '+':
        return a + b
    if op == '-':
        return a - b
    if op == '*':
        return a * b
    if op == '/':
        return a / b
    if op == '%':
        if a.denominator != 1 or b.denominator != 1 or b == 0:
            raise ValueError
        return a % b
    raise ValueError(op)


def show(expr, raws):
    op = expr[0]
    if op == 'slot':
        return raws[expr[1]]
    if op == 'const':
        return str(Fraction(expr[1]))
    if op in ('floor', 'ceil'):
        return f'{op}({show(expr[1], raws)})'
    if op == 'span':
        return f'({show(expr[1], raws)} to {show(expr[2], raws)})'
    return f'({show(expr[1], raws)} {"×" if op == "*" else "÷" if op == "/" else "mod" if op == "%" else op} {show(expr[2], raws)})'


def fmt_hole(kind, v, sym=''):
    if kind == 'money':
        v = Fraction(math.floor(Fraction(v) * 100 + Fraction(1, 2)), 100)        # to cents, half up
        s = f'{int(v)}.{int(v * 100) % 100:02d}' if v.denominator != 1 else str(int(v))
        whole, _, cents = s.partition('.')
        return f'{sym}{int(whole):,}' + (f'.{cents}' if cents else '')
    if kind in ('clock24', 'clock12'):
        m = int(v) % 1440
        h, mi = divmod(m, 60)
        if kind == 'clock24':
            return f'{h:02d}:{mi:02d}'
        return f'{(h - 1) % 12 + 1}:{mi:02d} {"am" if h < 12 else "pm"}'
    if kind == 'weekday':
        return DAYS[int(v) % 7]
    if kind == 'date':
        d = date.fromordinal(int(v))
        return f'{d.day} {MONTHS[d.month - 1]} {d.year}'
    if kind == 'date_us':
        d = date.fromordinal(int(v))
        return f'{MONTHS[d.month - 1]} {d.day}, {d.year}'
    v = Fraction(v)
    if v.denominator == 1:
        return f'{int(v):,}' if abs(v) >= 10000 else str(int(v))
    return f'{float(v):.2f}'.rstrip('0').rstrip('.')


# ------------------------------------------------------------------ the readers
@lru_cache(maxsize=1)
def readers():
    try:
        data = json.loads(PATH.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return ()
    out = []
    for r in data.get('readers', []):
        try:
            out.append((re.compile(r['regex'], re.I), r))
        except re.error:
            continue
    return tuple(out)


def apply(reader, text):
    """The answer text and the shown working, or None when the template doesn't match."""
    pat, r = reader
    m = pat.search(text)
    if not m:
        return None
    raws = list(m.groups())
    kinds = r['slots']
    env = []
    for k, raw in zip(kinds, raws):
        try:
            env.append(slot_value(k, raw) if k in SLOT_RE else None)
        except (ValueError, AttributeError):
            return None
    sym = next((raw[0] for k, raw in zip(kinds, raws) if k == 'MONEY'), '')
    parts, works = [], []
    for piece in r['answer']:
        if piece[0] == 'lit':
            parts.append(piece[1])
        elif piece[0] == 'ref':
            parts.append(raws[piece[1]])
        else:
            _, kind, expr = piece
            try:
                v = evaluate(expr, env)
            except (ValueError, ZeroDivisionError, TypeError, OverflowError):
                return None
            if kind == 'money' and v < 0 or kind in ('number',) and v < 0 and not r.get('negative_ok'):
                return None
            parts.append(fmt_hole(kind, v, sym))
            if kind in ('money', 'number'):     # date and weekday arithmetic means nothing to a reader
                works.append(show(expr, raws))
    return ''.join(parts), works


def respond(messages):
    users = [(m.get('content') or '') for m in messages if m.get('role') == 'user']
    if not users or len(users) > 1 and not users[-1].strip():
        return None
    text = users[-1]
    best = None
    for reader in readers():
        got = apply(reader, text)
        if got and (best is None or reader[1]['support'] > best[2]['support']):
            best = (got[0], got[1], reader[1])
    if not best:
        return None
    answer, works, r = best
    how = '; '.join(works)
    return dict(route='chat/induced-' + r['task'], sources=[], reasoning=True,
                response=f'**{answer}**. Worked out as {how}.' if how else f'**{answer}.**',
                details=f'induced reader {r["id"]} ({r["support"]} training examples, {r["checked"]} fresh checks) (induced_readers.py)')


def reload():
    readers.cache_clear()
