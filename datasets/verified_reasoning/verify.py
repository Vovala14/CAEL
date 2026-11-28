"""Conservative, stdlib-only final-answer checker; version 1.2.0.

check(reply, row) keeps the boolean API. judge() distinguishes correct,
incorrect, ambiguous and unparseable. False is not proof of a wrong answer.
Finite answer formats are supported, not arbitrary English or proof checking.
Use an explicit Answer: line (or Output: grid); never eval/exec or model calls.
"""
import calendar
import json
import re
import unicodedata
from collections import Counter
from datetime import date
from fractions import Fraction

VERSION = '1.2.0'
MAX_REPLY_CHARACTERS = 100_000
DAYS = 'monday tuesday wednesday thursday friday saturday sunday'.split()
MONTHS = {s.lower(): i for i, s in enumerate(calendar.month_name) if s}
MONTHS.update({s.lower(): i for i, s in enumerate(calendar.month_abbr) if s})
ORDINALS = dict(zip('first second third fourth fifth sixth seventh'.split(), range(1, 8)))
NUMBER = re.compile(r'(?<![\w.])[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:/\d+)?(?![\w.]|\.\d)')
MARKER = re.compile(r'(?im)^\s*(?:#{1,6}\s*)?(final answer|answer|test output|output|correction)\s*:\s*')
NEGATION = re.compile(r"\bnot\b|\bnever\b|\bno longer\b|n['’]t\b", re.I)
HEDGE = re.compile(r'\b(?:maybe|perhaps|possibly|either|or|if|unless|assuming|approximately|about)\b', re.I)
UNITS = {'g': ('mass', 1), 'gram': ('mass', 1), 'grams': ('mass', 1), 'kg': ('mass', 1000), 'kilogram': ('mass', 1000), 'kilograms': ('mass', 1000),
         'ml': ('volume', 1), 'millilitres': ('volume', 1), 'milliliters': ('volume', 1), 'l': ('volume', 1000), 'litre': ('volume', 1000), 'litres': ('volume', 1000), 'liter': ('volume', 1000), 'liters': ('volume', 1000),
         'h': ('duration', 60), 'hour': ('duration', 60), 'hours': ('duration', 60), 'min': ('duration', 1), 'minute': ('duration', 1), 'minutes': ('duration', 1),
         's': ('duration', Fraction(1, 60)), 'second': ('duration', Fraction(1, 60)), 'seconds': ('duration', Fraction(1, 60)), 'day': ('duration', 1440), 'days': ('duration', 1440)}
UNIT_NAMES = '|'.join(sorted(UNITS, key=len, reverse=True))
UNIT_RX = re.compile(r'(?<![\w])([+-]?\d+(?:\.\d+)?(?:/\d+)?)\s*(' + UNIT_NAMES + r')\b', re.I)
CURRENCIES = {'usd': '$', 'dollar': '$', 'dollars': '$', 'gbp': '£', 'pound': '£', 'pounds': '£', 'eur': '€', 'euro': '€', 'euros': '€'}

def _clean(text):
    text = unicodedata.normalize('NFKC', str(text)).replace('−', '-').replace('–', '-')
    return text.replace('**', '').replace('`', '').strip(' \t\r\n.!"\u201c\u201d')

def _unwrap(text):
    text = _clean(text)
    for _ in range(3):
        other = re.sub(r'(?i)^(?:the (?:final )?(?:answer|result|time|date|name|day|code|remaining source)|it|this)\s+(?:is|would be)\s+', '', text)
        other = re.sub(r'(?i)^(?:at|on)\s+', '', other)
        if other == text: break
        text = other
    return _clean(text)

def _boxed(text):
    values = []
    for m in re.finditer(r'\\boxed\{', text):
        depth, end = 1, m.end()
        while end < len(text) and depth:
            depth += (text[end] == '{') - (text[end] == '}'); end += 1
        if not depth: values.append(text[m.end():end - 1])
    return values

def _extract(reply, grid=False):
    text = str(reply).strip().replace('**', '')
    boxed = _boxed(text)
    if boxed: return boxed
    markers = list(MARKER.finditer(text))
    if markers:
        finals = [m for m in markers if m[1].lower() in ('final answer', 'correction')]
        values = []
        for m in finals or markers:
            end = next((n.start() for n in markers if n.start() > m.start()), len(text))
            tail = text[m.end():end].strip()
            lines = [s.strip() for s in tail.splitlines() if s.strip() and not s.strip().startswith('```')]
            values.append(tail if grid else (lines[0] if lines else ''))
        return values
    lines = [s.strip() for s in text.splitlines() if s.strip() and not s.strip().startswith('```')]
    if not lines: return ['']
    if grid:
        if text.lstrip().startswith('['): return [text]
        block = []
        for line in reversed(lines):
            if re.fullmatch(r'[0-9](?:\s+[0-9])*', line): block.append(line)
            elif block: break
            else: return [text]
        return ['\n'.join(reversed(block))] if block else [text]
    return [lines[-1]]

def final_answer(reply):
    """Last extracted span; judge additionally rejects conflicting final spans."""
    return _extract(reply)[-1].strip()

def grid_of(text):
    text = re.sub(r'^```(?:json|text)?\s*\n|\n```\s*$', '', str(text).strip(), flags=re.I).strip()
    if text.startswith('['):
        try: grid = json.loads(text)
        except (ValueError, RecursionError): return None
        if not isinstance(grid, list) or not grid or not all(isinstance(r, list) and r for r in grid): return None
        if not all(type(v) is int and 0 <= v <= 9 for r in grid for v in r): return None
    else:
        lines = [s.strip() for s in text.splitlines() if s.strip()]
        if not lines or not all(re.fullmatch(r'[0-9](?:\s+[0-9])*', s) for s in lines): return None
        grid = [[int(v) for v in s.split()] for s in lines]
    return grid if all(len(r) == len(grid[0]) for r in grid) else None

def numbers(text):
    text = re.sub(r'([+-])\s*([$£€])\s*', r'\2\1', _clean(text))
    values = NUMBER.findall(text)
    if any(sum(c.isdigit() for c in v) > 100 for v in values): return []
    try: return [Fraction(v.replace(',', '')) for v in values]
    except (ValueError, ZeroDivisionError): return []

def clock(text):
    text = _unwrap(text).lower().replace('a.m.', 'am').replace('p.m.', 'pm')
    m = re.fullmatch(r'(?:(' + '|'.join(DAYS) + r')\s+)?(\d{1,2}):(\d{2})\s*(am|pm)?', text)
    if not m: return None
    h, minute = int(m[2]), int(m[3])
    if minute >= 60 or (not m[4] and h >= 24) or (m[4] and not 1 <= h <= 12): return None
    h = h % 12 + (12 if m[4] == 'pm' else 0) if m[4] else h
    return m[1], h * 60 + minute

def _date(text):
    text = re.sub(r'(\d)(?:st|nd|rd|th)\b', r'\1', _unwrap(text).lower().replace(',', ''))
    m = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', text)
    if m: parts = list(map(int, m.groups()))
    else:
        a = re.fullmatch(r'(\d{1,2})\s+([a-z]+)\s+(\d{4})', text)
        b = re.fullmatch(r'([a-z]+)\s+(\d{1,2})\s+(\d{4})', text)
        if a and a[2] in MONTHS: parts = [int(a[3]), MONTHS[a[2]], int(a[1])]
        elif b and b[1] in MONTHS: parts = [int(b[3]), MONTHS[b[1]], int(b[2])]
        else: return None
    try: return date(*parts)
    except ValueError: return None

def _currency(text):
    found = set(re.findall(r'[$£€]', text))
    found.update(CURRENCIES[w] for w in re.findall(r'\b[a-z]+\b', text.lower()) if w in CURRENCIES)
    return found

def _direction(text):
    text = text.lower(); found = set()
    if re.search(r'\b(?:short|deficit|shortfall|more needed)\b', text): found.add('short')
    if re.search(r'\b(?:left over|leftover|to spare|surplus|remaining)\b', text): found.add('surplus')
    if re.search(r'\brefund(?:ed)?\b|\breturned to (?:me|you)\b', text): found.add('refund')
    if re.search(r'\b(?:due|owe|owed|owing|payable)\b', text): found.add('due')
    return found

def _quantity(text):
    text = _unwrap(text).lower()
    if NEGATION.search(text) or HEDGE.search(text): return None
    if re.search(r'\b(?:wrong|incorrect|false|unknown|undetermined|indeterminate)\b', text): return None
    text = re.sub(r'([+-])\s*([$£€])\s*', r'\2\1', text)
    text = re.sub(r'(\d)(' + UNIT_NAMES + r')\b', r'\1 \2', text)
    for m in re.finditer(r'\b\d+([a-z_]+)\b', text):
        if m[1] not in UNITS: return None
    vals = numbers(text)
    if not vals: return None
    units = list(UNIT_RX.finditer(text))
    if units:
        if len(units) != len(vals): return None
        dimensions = {UNITS[m[2]][0] for m in units}
        if len(dimensions) != 1: return None
        dimension = dimensions.pop()
        if len(vals) > 1 and dimension != 'duration': return None
        vals = [sum(Fraction(m[1]) * UNITS[m[2]][1] for m in units)]
    else: dimension = None
    containers = set(re.findall(r'\b(?:trays?|bags?|box(?:es)?|tins?|jars?|crates?|baskets?)\b', text))
    containers = {'box' if x == 'boxes' else x.rstrip('s') for x in containers}
    return vals, dimension, _currency(text), _direction(text), containers

def _special(pred, gold):
    a = _unwrap(pred).lower()
    if gold == 'cannot be determined':
        patterns = [r'(?:we |i |you |it )?(?:cannot|can[’\']?t|could not|couldn[’\']?t) (?:be )?(?:determine[dt]?|tell|know|say|work it out)(?: (?:from|with|given) (?:the )?(?:information|data|facts|details)(?: (?:given|provided|available))?)?',
                    r'(?:there is |there[’\']?s )?(?:not enough|insufficient) (?:information|data|evidence)(?: to (?:determine|tell|know|answer)(?: (?:it|that|the answer))?)?',
                    r'(?:it is |the (?:answer|result) is )?(?:unknown|undetermined|indeterminate|not determinable|not known)', r'it depends',
                    r'(?:it is )?(?:impossible|not possible) to (?:determine|tell|know)(?: from (?:the )?(?:given )?information)?']
    elif gold == 'contradictory premise':
        patterns = [r'contradictory premise', r'(?:the |these )?(?:premise|premises|statements|facts|conditions) (?:are|is) (?:contradictory|inconsistent)', r'(?:there is |there[’\']?s |this is )?(?:a )?contradiction', r'(?:both |the )?statements cannot both be true']
    elif gold == 'there is none':
        patterns = [r'(?:there (?:is|are) )?(?:none|nothing)(?: (?:left|remaining))?', r'(?:the (?:box|drawer|container) is )?empty', r'no (?:\w+ )?(?:is |are )?left']
    else:
        patterns = [r'(?:you )?(?:did not|didn[’\']?t|never) (?:say|said|tell me|told me|mention(?:ed)?)(?: (?:it|that|the price|the amount|a price|how much))?', r'(?:it was |the price was )?not (?:said|mentioned|provided|given)', r'no price was (?:said|mentioned|provided|given)']
    if any(re.fullmatch(p, a) for p in patterns): return 'correct', 'Supported affirmative abstention/absence statement.'
    if re.search(r'\bnot unknown\b|\bnot contradictory\b|\bnot inconsistent\b|\bnot empty\b|\b(?:answer|result) is known\b|\bcan be determined\b', a): return 'incorrect', 'The claim negates the expected uncertainty/absence.'
    return 'unparseable', 'No supported unambiguous statement of the expected uncertainty/absence.'

def _claim(text):
    text = _clean(text).lower()
    patterns = [('gate', r'(?:the )?gate (?:opened|opens|open)(?: at)? (.+)'), ('delivery', r'(?:the )?delivery (?:came|arrived)(?: at)? (.+)'), ('room', r'(?:the )?meeting (?:is |was )?(?:in )?room (.+)'), ('visitors', r'(?:the )?visitor count (?:is|was) (.+)'), ('bell', r'(?:the )?bell (?:rang|rings) (.+)')]
    for kind, pattern in patterns:
        m = re.fullmatch(pattern, text)
        if m: return kind, m[1]
    return None

def _compare(pred, gold, row):
    a, g = _unwrap(pred), _clean(gold)
    if a.casefold() == g.casefold(): return 'correct', 'Exact normalized final answer.'
    if g.lower() in {'cannot be determined', 'contradictory premise', 'there is none', 'you did not say'}: return _special(a, g.lower())
    if row.get('category') == 'arc_grids':
        pg, gg = grid_of(pred), grid_of(gold)
        if pg is None: return 'unparseable', 'Expected a rectangular 2-D grid with integer colours 0-9.'
        return ('correct', 'Exact grid shape and cells.') if pg == gg else ('incorrect', 'Grid shape or cells differ.')
    source = re.fullmatch(r'((?:Report|Log|Witness|Note|Sheet)\s+[A-Za-z0-9]+):\s*(.+)', g, re.I)
    if source:
        found = re.fullmatch(r'((?:Report|Log|Witness|Note|Sheet)\s+[A-Za-z0-9]+)(?::| says| states| reports)\s*(.+)', a, re.I)
        if not found: return 'unparseable', 'Expected one explicit source and its attributed claim.'
        if found[1].casefold() != source[1].casefold(): return 'incorrect', 'Wrong source attribution.'
        if re.search(r'\b(?:Report|Log|Witness|Note|Sheet)\s+[A-Za-z0-9]+\s*:', found[2], re.I): return 'ambiguous', 'Multiple competing source attributions.'
        gc, pc = _claim(source[2]), _claim(found[2])
        if gc and pc:
            if gc[0] != pc[0]: return 'incorrect', 'The attributed event/relation differs.'
            return _compare(pc[1], gc[1], {})
        return _compare(found[2], gc[1] if gc else source[2], {})
    decision = re.fullmatch(r'(yes|no)(?:[,;:]\s*(.+))?', g, re.I)
    if decision:
        found = re.match(r'^(yes|no)\b(?:[,;:.]\s*|\s+)?(.*)$', a, re.I)
        if not found: return 'unparseable', 'No explicit unambiguous yes/no decision.'
        if found[1].lower() != decision[1].lower(): return 'incorrect', 'Opposite yes/no decision.'
        if re.match(r'(?i)^(?:if|unless|assuming|maybe|perhaps)\b', found[2]): return 'ambiguous', 'Conditional or hedged yes/no decision.'
        if re.match(r'(?i)^(?:actually[, ]+)?(?:yes|no)\b', found[2]) or re.search(r'(?i)\b(?:but|however)[, ]+(?:yes|no)\b', found[2]): return 'ambiguous', 'Conflicting yes/no decisions.'
        if decision[2]: return _compare(found[2], decision[2], row)
        if re.search(r'(?i)cannot be determined|\bunknown\b', found[2]): return 'ambiguous', 'Definite decision combined with uncertainty.'
        return 'correct', 'Explicit final yes/no decision; explanation is not verified.'
    gc = clock(g)
    if gc is not None:
        pc = clock(a)
        if pc is None: return 'unparseable', 'Invalid/ambiguous clock time or extra final claims.'
        return ('correct', 'Same time and required weekday.') if pc[1] == gc[1] and (gc[0] is None or gc[0] == pc[0]) else ('incorrect', 'Clock time or weekday differs.')
    gd = _date(g)
    if gd is not None:
        pd = _date(a)
        if pd is None: return 'unparseable', 'No supported complete calendar date.'
        return ('correct', 'Same calendar date.') if pd == gd else ('incorrect', 'Calendar date differs.')
    code = re.fullmatch(r'(?:[A-Za-z_]\w*\d\w*|\d+[A-Za-z_]\w*|[A-Za-z]+ \d+)', g)
    if code and not re.fullmatch(r'\d+(?:' + UNIT_NAMES + r')', g, re.I):
        norm = lambda x: re.sub(r'[\s-]', '', x).casefold()
        return ('correct', 'Whole identifier matches.') if norm(a) == norm(g) else ('incorrect', 'Identifier differs; no substring matching.')
    if re.search(r'\d', g):
        gq, pq = _quantity(g), _quantity(a)
        if pq is None or gq is None: return 'unparseable', 'No supported unambiguous numerical final claim.'
        gv, gu, gc, gp, gb = gq; pv, pu, pc, pp, pb = pq
        if gc and pc and gc != pc: return 'incorrect', 'Explicit currency differs.'
        if pu is not None and gu is None: return 'unparseable', 'Unexpected physical unit for a scalar reference.'
        if gu is not None and pu is not None and gu != pu: return 'incorrect', 'Physical unit dimension differs.'
        if gv != pv: return 'incorrect', 'Signed numerical values, order or count differ.'
        if pp and gp != pp: return 'incorrect', 'Remainder/budget/refund/amount-due direction differs.'
        if gp and not pp: return 'unparseable', 'Required semantic direction is missing.'
        if gb and pb and gb != pb: return 'incorrect', 'Explicit container unit differs.'
        return 'correct', 'Value, sign and stated qualifiers agree.'
    if ',' in g:
        split = lambda t: [_clean(x).casefold() for x in re.split(r',|\band\b', t) if _clean(x)]
        return ('correct', 'Same unordered list with multiplicities.') if Counter(split(a)) == Counter(split(g)) else ('incorrect', 'List members or multiplicities differ.')
    if g.lower() in ORDINALS and re.fullmatch(str(ORDINALS[g.lower()]) + r'(?:st|nd|rd|th)', a.lower()): return 'correct', 'Same ordinal position.'
    if NEGATION.search(a): return 'incorrect', 'Negated text is not the affirmative reference.'
    if HEDGE.search(a): return 'ambiguous', 'Alternative or hedged final answer.'
    return 'unparseable', 'No exact supported final label/name; no substring reward.'

def judge(reply, row):
    """Return status, reason, extracted answer and verifier_version as a dict."""
    if not isinstance(row, dict) or not isinstance(row.get('answer'), str) or not row['answer'].strip(): raise ValueError('row must contain a nonempty string answer')
    text = str(reply)
    if len(text) > MAX_REPLY_CHARACTERS: return {'status':'unparseable','reason':'Reply exceeds parser bound.','answer':'','verifier_version':VERSION}
    if len(MARKER.findall(text)) > 32 or len(re.findall(r'\\boxed\{', text)) > 32: return {'status':'ambiguous','reason':'Too many explicit final claims.','answer':'','verifier_version':VERSION}
    spans = _extract(text, grid=row.get('category') == 'arc_grids')
    outcomes = [_compare(span, row['answer'], row) for span in spans]
    if len(spans)>1 and not all(_clean(s).casefold()==_clean(spans[0]).casefold() for s in spans):
        status, reason = ('correct','Equivalent explicit final answers.') if all(s=='correct' for s,_ in outcomes) else ('ambiguous','Conflicting explicit final answers; no gold-based selection.')
    else: status, reason = outcomes[-1]
    return {'status':status,'reason':reason,'answer':spans[-1],'verifier_version':VERSION}

def check(reply, row):
    """True only for a supported correct final answer; inspect judge() on False."""
    return judge(reply,row)['status']=='correct'

if __name__ == '__main__':
    assert check('Answer: 6.1',{'answer':'$6.10'})
    assert not check('Answer: 6 full trays, 2 short',{'answer':'6 full trays, 2 left over'})
    assert not check('Answer: This is not unknown; the result is known',{'answer':'Cannot be determined'})
    print('verifier self-test: all passed; run test_verify.py for the full regression suite')
