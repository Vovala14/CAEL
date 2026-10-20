"""Example-guided Python program synthesis by cost-ordered bottom-up search.

CAEL writes a new function body by composing small typed operations (list,
string, number, comparison and comprehension building blocks) and keeps the
cheapest composition whose results equal every given example. Nothing is
looked up from stored solutions: the only learned component is the per-task
operation cost table (see train.py), which decides what to try first.

Only CAEL's own generated expressions are evaluated, on literal example
values, with size guards on every intermediate result.
"""
from collections import defaultdict
from itertools import product
import ast
import math
import re
import time

MAX_LEN = 2000
MAX_INT = 10 ** 30


def kind(value):
    if isinstance(value, bool):
        return 'bool'
    if isinstance(value, (int, float)):
        return 'num'
    for name, cls in (('str', str), ('list', list), ('tuple', tuple), ('dict', dict), ('set', set)):
        if isinstance(value, cls):
            return name
    if value is None:
        return 'none'
    return 'other'


def safe(value):
    """Reject results that are too large or not comparable."""
    if isinstance(value, bool) or value is None:
        return True
    if isinstance(value, int):
        return abs(value) <= MAX_INT
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, (str, list, tuple, dict, set)):
        if len(value) > MAX_LEN:
            return False
        if isinstance(value, (list, tuple, set)):
            return all(safe(v) for v in value) if len(value) <= 200 else True
        return True
    return False


def key_of(values):
    return repr([(type(v).__name__, v) for v in values])


SEQ = {'str', 'list', 'tuple'}
NUM = {'num'}
NUMB = {'num', 'bool'}
ITER = {'str', 'list', 'tuple', 'set', 'dict'}
ANY = None


def _guard_pow(a, b):
    if abs(b) > 64 or abs(a) > 10 ** 6:
        raise ValueError
    return a ** b


def _guard_mul(a, b):
    if isinstance(a, (str, list, tuple)) or isinstance(b, (str, list, tuple)):
        n = b if isinstance(a, (str, list, tuple)) else a
        if not isinstance(n, int) or isinstance(n, bool) or n > 100:
            raise ValueError
    return a * b


def _factorial(n):
    if not isinstance(n, int) or isinstance(n, bool) or not 0 <= n <= 60:
        raise ValueError
    return math.factorial(n)


def _range(a, b):
    if b - a > 5000:
        raise ValueError
    return list(range(a, b))


def _join(sep, items):
    if not all(isinstance(i, str) for i in items):
        raise TypeError
    return sep.join(items)


def _bin(n):
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError
    return bin(n)[2:]


def _int_base(s, b):
    return int(s, b)


def _round_to(x, digits):
    if not isinstance(digits, int) or abs(digits) > 15:
        raise ValueError  # round(x, -10**20) would build an enormous power of ten
    return round(x, digits)


def _prod(items):
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in items):
        raise TypeError
    return math.prod(items)


def _sorted_set(x):
    return sorted(set(x))


def _str_only(fn):
    def call(s, *rest):
        if not isinstance(s, str):
            raise TypeError
        return fn(s, *rest)
    return call


def _no_bool(fn):
    def call(*args):
        if any(isinstance(a, bool) for a in args):
            raise TypeError
        return fn(*args)
    return call


# name, tag (matches train.tags_in_code), argument kinds, function, template, base cost
OPS = [
    ('len', 'len', (ITER,), len, 'len({0})', 2),
    ('sum', 'sum', ({'list', 'tuple', 'set'},), sum, 'sum({0})', 2),
    ('max', 'max', ({'list', 'tuple', 'str', 'set'},), max, 'max({0})', 2),
    ('min', 'min', ({'list', 'tuple', 'str', 'set'},), min, 'min({0})', 2),
    ('sorted', 'sorted', (ITER,), sorted, 'sorted({0})', 2),
    ('sorted_rev', 'sorted', (ITER,), lambda x: sorted(x, reverse=True), 'sorted({0}, reverse=True)', 3),
    ('reverse', 'reverse', (SEQ,), lambda x: x[::-1], '{0}[::-1]', 2),
    ('set', 'set', ({'list', 'tuple', 'str'},), set, 'set({0})', 2),
    ('sorted_set', 'set', ({'list', 'tuple', 'str'},), _sorted_set, 'sorted(set({0}))', 3),
    ('list', 'list', ({'str', 'tuple', 'set', 'dict'},), list, 'list({0})', 2),
    ('tuple', 'tuple', ({'list', 'str', 'set'},), tuple, 'tuple({0})', 2),
    ('first', 'index', (SEQ,), lambda x: x[0], '{0}[0]', 2),
    ('last', 'index', (SEQ,), lambda x: x[-1], '{0}[-1]', 2),
    ('tail', 'slice', (SEQ,), lambda x: x[1:], '{0}[1:]', 2),
    ('init', 'slice', (SEQ,), lambda x: x[:-1], '{0}[:-1]', 2),
    ('str', 'str', ({'num', 'list', 'tuple'},), str, 'str({0})', 2),
    ('int', 'int', ({'str', 'num'},), _no_bool(int), 'int({0})', 2),
    ('float', 'float', ({'str', 'num'},), float, 'float({0})', 3),
    ('abs', 'abs', (NUM,), abs, 'abs({0})', 2),
    ('neg', 'neg', (NUM,), lambda x: -x, '-{0}', 2),
    ('not', 'not', ({'bool'},), lambda x: not x, 'not {0}', 2),
    ('bool', 'bool', ({'num', 'str', 'list'},), bool, 'bool({0})', 3),
    ('square', 'pow', (NUM,), _no_bool(lambda x: x * x), '{0} ** 2', 2),
    ('cube', 'pow', (NUM,), _no_bool(lambda x: x * x * x), '{0} ** 3', 3),
    ('sqrt', 'sqrt', (NUM,), math.sqrt, 'math.sqrt({0})', 3),
    ('floor', 'floor', (NUM,), math.floor, 'math.floor({0})', 3),
    ('ceil', 'ceil', (NUM,), math.ceil, 'math.ceil({0})', 3),
    ('factorial', 'factorial', (NUM,), _factorial, 'math.factorial({0})', 3),
    ('round', 'round', (NUM,), round, 'round({0})', 3),
    ('prod', 'prod', ({'list', 'tuple'},), _prod, 'math.prod({0})', 3),
    ('upper', 'upper', ({'str'},), str.upper, '{0}.upper()', 2),
    ('lower', 'lower', ({'str'},), str.lower, '{0}.lower()', 2),
    ('title', 'title', ({'str'},), str.title, '{0}.title()', 3),
    ('capitalize', 'capitalize', ({'str'},), str.capitalize, '{0}.capitalize()', 3),
    ('swapcase', 'swapcase', ({'str'},), str.swapcase, '{0}.swapcase()', 3),
    ('strip', 'strip', ({'str'},), str.strip, '{0}.strip()', 3),
    ('split', 'split', ({'str'},), str.split, '{0}.split()', 2),
    ('isdigit', 'isdigit', ({'str'},), str.isdigit, '{0}.isdigit()', 3),
    ('isalpha', 'isalpha', ({'str'},), str.isalpha, '{0}.isalpha()', 3),
    ('isupper', 'isupper', ({'str'},), str.isupper, '{0}.isupper()', 3),
    ('islower', 'islower', ({'str'},), str.islower, '{0}.islower()', 3),
    ('isspace', 'isspace', ({'str'},), str.isspace, '{0}.isspace()', 3),
    ('ord', 'ord', ({'str'},), ord, 'ord({0})', 3),
    ('chr', 'chr', (NUM,), _no_bool(chr), 'chr({0})', 3),
    ('bin', 'bin', (NUM,), _bin, 'bin({0})[2:]', 3),
    ('wrap', 'list', (ANY,), lambda x: [x], '[{0}]', 3),
    ('items', 'items', ({'dict'},), lambda d: list(d.items()), 'list({0}.items())', 3),
    ('keys', 'keys', ({'dict'},), lambda d: list(d), 'list({0})', 3),
    ('values', 'values', ({'dict'},), lambda d: list(d.values()), 'list({0}.values())', 3),
    ('unique', 'set', ({'list', 'tuple', 'str'},), lambda x: list(dict.fromkeys(x)), 'list(dict.fromkeys({0}))', 3),
    ('dict', 'dict', ({'list'},), dict, 'dict({0})', 3),
    ('concat', 'sum', ({'list'},), lambda x: sum(x, []), 'sum({0}, [])', 3),
    ('join_empty', 'join', ({'list', 'tuple'},), lambda x: _join('', x), "''.join({0})", 2),
    ('join_space', 'join', ({'list', 'tuple'},), lambda x: _join(' ', x), "' '.join({0})", 3),

    ('add', 'add', ({'num', 'str', 'list', 'tuple'}, {'num', 'str', 'list', 'tuple'}), lambda a, b: a + b, '({0} + {1})', 2),
    ('sub', 'sub', ({'num', 'set'}, {'num', 'set'}), lambda a, b: a - b, '({0} - {1})', 2),
    ('mul', 'mul', ({'num', 'str', 'list'}, {'num', 'str', 'list'}), _guard_mul, '({0} * {1})', 2),
    ('div', 'div', (NUM, NUM), lambda a, b: a / b, '({0} / {1})', 2),
    ('floordiv', 'floordiv', (NUM, NUM), lambda a, b: a // b, '({0} // {1})', 2),
    ('mod', 'mod', (NUM, NUM), _no_bool(lambda a, b: a % b), '({0} % {1})', 2),
    ('pow', 'pow', (NUM, NUM), _no_bool(_guard_pow), '({0} ** {1})', 3),
    ('max2', 'max', (NUMB | {'str'}, NUMB | {'str'}), max, 'max({0}, {1})', 3),
    ('min2', 'min', (NUMB | {'str'}, NUMB | {'str'}), min, 'min({0}, {1})', 3),
    ('eq', 'eq', (ANY, ANY), lambda a, b: a == b, '({0} == {1})', 2),
    ('ne', 'ne', (ANY, ANY), lambda a, b: a != b, '({0} != {1})', 3),
    ('lt', 'lt', (NUMB | {'str'}, NUMB | {'str'}), lambda a, b: a < b, '({0} < {1})', 2),
    ('le', 'le', (NUMB | {'str'}, NUMB | {'str'}), lambda a, b: a <= b, '({0} <= {1})', 3),
    ('gt', 'gt', (NUMB | {'str'}, NUMB | {'str'}), lambda a, b: a > b, '({0} > {1})', 2),
    ('ge', 'ge', (NUMB | {'str'}, NUMB | {'str'}), lambda a, b: a >= b, '({0} >= {1})', 3),
    ('and', 'and', ({'bool'}, {'bool'}), lambda a, b: a and b, '({0} and {1})', 2),
    ('or', 'or', ({'bool'}, {'bool'}), lambda a, b: a or b, '({0} or {1})', 2),
    ('in', 'in', (ANY, ITER), lambda a, b: a in b, '({0} in {1})', 2),
    ('count', 'count', ({'str', 'list', 'tuple'}, ANY), lambda x, y: x.count(y), '{0}.count({1})', 2),
    ('at', 'index', (SEQ, {'num'}), lambda x, i: x[i], '{0}[{1}]', 2),
    ('get', 'index', ({'dict'}, ANY), lambda d, k: d[k], '{0}[{1}]', 3),
    ('take', 'slice', (SEQ, {'num'}), lambda x, i: x[:i], '{0}[:{1}]', 2),
    ('drop', 'slice', (SEQ, {'num'}), lambda x, i: x[i:], '{0}[{1}:]', 2),
    ('step', 'slice', (SEQ, {'num'}), lambda x, i: x[::i], '{0}[::{1}]', 3),
    ('split_on', 'split', ({'str'}, {'str'}), _str_only(lambda s, sep: s.split(sep)), '{0}.split({1})', 3),
    ('join_on', 'join', ({'str'}, {'list', 'tuple'}), _join, '{0}.join({1})', 3),
    ('startswith', 'startswith', ({'str'}, {'str'}), _str_only(str.startswith), '{0}.startswith({1})', 3),
    ('endswith', 'endswith', ({'str'}, {'str'}), _str_only(str.endswith), '{0}.endswith({1})', 3),
    ('find', 'find', ({'str'}, {'str'}), _str_only(str.find), '{0}.find({1})', 3),
    ('index_of', 'index', ({'list', 'tuple', 'str'}, ANY), lambda x, y: x.index(y), '{0}.index({1})', 3),
    ('round_to', 'round', (NUM, NUM), _no_bool(_round_to), 'round({0}, {1})', 3),
    ('gcd', 'gcd', (NUM, NUM), _no_bool(math.gcd), 'math.gcd({0}, {1})', 3),
    ('lcm', 'lcm', (NUM, NUM), _no_bool(math.lcm), 'math.lcm({0}, {1})', 3),
    ('range', 'range', (NUM, NUM), _no_bool(_range), 'list(range({0}, {1}))', 3),
    ('zip', 'zip', ({'list', 'tuple', 'str'}, {'list', 'tuple', 'str'}), lambda a, b: list(zip(a, b)), 'list(zip({0}, {1}))', 3),
    ('merge', 'dict', ({'dict'}, {'dict'}), lambda a, b: {**a, **b}, '{{**{0}, **{1}}}', 3),
    ('pair', 'tuple', (ANY, ANY), lambda a, b: (a, b), '({0}, {1})', 3),
    ('int_base', 'int', ({'str'}, NUM), _no_bool(_int_base), 'int({0}, {1})', 3),

    ('ifelse', 'cond', ({'bool'}, ANY, ANY), lambda c, a, b: a if c else b, '({1} if {0} else {2})', 3),
    ('replace', 'replace', ({'str'}, {'str'}, {'str'}), _str_only(str.replace), '{0}.replace({1}, {2})', 3),
    ('slice2', 'slice', (SEQ, {'num'}, {'num'}), lambda x, i, j: x[i:j], '{0}[{1}:{2}]', 3),
]

# Comprehension forms: name, tag, uses body, uses condition, aggregate, template, base cost
HIGHER = [
    ('map', 'comp', True, False, lambda els, body, cond: [b for b in body], '[{body} for {v} in {it}]', 2),
    ('filter', 'filter', False, True, lambda els, body, cond: [e for e, c in zip(els, cond) if c], '[{v} for {v} in {it} if {cond}]', 2),
    ('map_filter', 'filter', True, True, lambda els, body, cond: [b for b, c in zip(body, cond) if c], '[{body} for {v} in {it} if {cond}]', 3),
    ('sum_of', 'sum', True, False, lambda els, body, cond: sum(body), 'sum({body} for {v} in {it})', 2),
    ('count_if', 'sum', False, True, lambda els, body, cond: sum(1 for c in cond if c), 'sum(1 for {v} in {it} if {cond})', 2),
    ('any', 'any', False, True, lambda els, body, cond: any(cond), 'any({cond} for {v} in {it})', 2),
    ('all', 'all', False, True, lambda els, body, cond: all(cond), 'all({cond} for {v} in {it})', 2),
    ('join_map', 'join', True, False, lambda els, body, cond: _join('', body), "''.join({body} for {v} in {it})", 2),
    ('join_filter', 'join', False, True, lambda els, body, cond: _join('', [e for e, c in zip(els, cond) if c]), "''.join({v} for {v} in {it} if {cond})", 2),
    ('max_of', 'max', True, False, lambda els, body, cond: max(body), 'max({body} for {v} in {it})', 3),
    ('min_of', 'min', True, False, lambda els, body, cond: min(body), 'min({body} for {v} in {it})', 3),
    ('sorted_by', 'sortkey', True, False, lambda els, body, cond: [e for _, _, e in sorted(zip(body, range(len(els)), els))], 'sorted({it}, key=lambda {v}: {body})', 3),
    ('max_by', 'maxkey', True, False, lambda els, body, cond: els[max(range(len(els)), key=lambda i: body[i])], 'max({it}, key=lambda {v}: {body})', 3),
    ('min_by', 'minkey', True, False, lambda els, body, cond: els[min(range(len(els)), key=lambda i: body[i])], 'min({it}, key=lambda {v}: {body})', 3),
]

OP_TAGS = sorted({op[1] for op in OPS} | {h[1] for h in HIGHER})


class Bank:
    """Expressions found so far, by cost, deduplicated by their values."""

    def __init__(self):
        self.by_cost = defaultdict(list)
        self.seen = set()
        self.size = 0

    def add(self, cost, src, values, parts=(), token=None):
        k = key_of(values)
        if k in self.seen:
            return None
        self.seen.add(k)
        kinds = {kind(v) for v in values}
        entry = (src, values, kinds.pop() if len(kinds) == 1 else 'mixed', tokens_of(parts, token))
        self.by_cost[cost].append(entry)
        self.size += 1
        return entry

    def at(self, cost, kinds):
        entries = self.by_cost.get(cost, ())
        if kinds is None:
            return entries
        return [e for e in entries if e[2] in kinds]


class Budget:
    def __init__(self, seconds, expressions):
        self.deadline = time.monotonic() + seconds
        self.left = expressions

    def spend(self):
        self.left -= 1
        if self.left <= 0 or (self.left % 256 == 0 and time.monotonic() > self.deadline):
            raise TimeoutError


def tokens_of(parts, token=None):
    """Which operations, constants and loop sources an expression is built from.
    Self-training (train.py) learns from these tokens of CAEL's own solutions."""
    found = frozenset().union(*(p[3] for p in parts if p))
    return found | {token} if token else found


def compositions(total, parts):
    if parts == 1:
        if total >= 1:
            yield (total,)
        return
    for first in range(1, total - parts + 2):
        for rest in compositions(total - first, parts - 1):
            yield (first,) + rest


def grow(bank, cost, costs, budget, on_new=None):
    """Add every expression of exactly this cost built from cheaper ones."""
    for name, tag, arg_kinds, fn, template, _ in OPS:
        op_cost = costs[name]
        remaining = cost - op_cost
        arity = len(arg_kinds)
        if remaining < arity:
            continue
        for split in compositions(remaining, arity):
            pools = [bank.at(c, k) for c, k in zip(split, arg_kinds)]
            if not all(pools):
                continue
            for args in product(*pools):
                budget.spend()
                try:
                    values = tuple(fn(*vals) for vals in zip(*(a[1] for a in args)))
                except Exception:
                    continue
                if not all(safe(v) for v in values):
                    continue
                src = template.format(*(a[0] for a in args))
                if on_new:
                    on_new(src, values, args, name)
                bank.add(cost, src, values, args, name)


class Iterable:
    def __init__(self, src, cost, per_example, var, token=None):
        self.src, self.cost, self.var, self.token = src, cost, var, token
        self.part = (None, None, None, frozenset({token} if token else ()))  # its token, shaped like a bank entry
        self.elements = per_example                     # list of element lists, one per example
        self.owner = [e for e, els in enumerate(per_example) for _ in els]
        self.flat = [x for els in per_example for x in els]
        self.groups = [[p for p, owner in enumerate(self.owner) if owner == e] for e in range(len(per_example))]


def iterables(params, inputs):
    """What comprehensions may loop over: parameters and their index ranges."""
    found = []
    for i, name in enumerate(params):
        column = [ex[i] for ex in inputs]
        kinds = {kind(v) for v in column}
        if len(kinds) != 1:
            continue
        k = kinds.pop()
        if k in ('list', 'tuple', 'str', 'set'):
            found.append((name, 1, [list(v) for v in column], 'iter:each'))
            found.append((f'range(len({name}))', 2, [list(range(len(v))) for v in column], 'iter:positions'))
            if k == 'str':
                found.append((f'{name}.split()', 2, [v.split() for v in column], 'iter:words'))
        elif k == 'dict':
            found.append((f'{name}.items()', 2, [list(v.items()) for v in column], 'iter:items'))
            found.append((name, 1, [list(v) for v in column], 'iter:each'))
        elif k == 'num' and all(isinstance(v, int) and 0 <= v <= 2000 for v in column):
            found.append((f'range({name})', 2, [list(range(v)) for v in column], 'iter:range'))
            found.append((f'range(1, {name} + 1)', 2, [list(range(1, v + 1)) for v in column], 'iter:range1'))
            found.append((f'str({name})', 2, [list(str(v)) for v in column], 'iter:digits'))
    return found


# Constants a search may use. With hand=True their costs are the 0.3.8 hand-set
# prior (HAND_CONSTANTS plus keyword rules); with hand=False every pool constant
# costs the same unless a learned cost table (train.py, keyed by token) says otherwise.
CONSTANT_POOL = [0, 1, 2, -1, 3, 10, '', ' ', True, False, 'aeiou', 'math.pi']
# The 0.3.8 literal also listed True: 4 and False: 4, but True == 1 and False == 0
# as dict keys, so they only raised 1 and 0 to cost 4 and booleans were never
# offered. These are the costs that search actually used.
HAND_CONSTANTS = {0: 4, 1: 4, 2: 3, -1: 4, 3: 4, 10: 4, '': 3, ' ': 3}
PI_WORDS = r'(?i)\b(?:circle|circular|cylinder|sphere|cone|radius|diameter|circumference|arc|sector|pi)\b'


def const_token(value):
    return 'const:' + repr(value)


def constants(description, inputs, costs=None, hand=True):
    """Small literals as {(type, value): (value, cost, token)}. Arbitrary numbers are
    expensive so a program cannot just memorise an example; numbers and quoted
    text from the description are cheap."""
    costs = costs or {}
    found = {}

    def put(value, cost, token):
        found[(type(value).__name__, value)] = (value, cost, token)

    for value in CONSTANT_POOL:
        token = const_token(value)
        default = HAND_CONSTANTS.get(value) if hand and not isinstance(value, bool) else None if hand else 3
        if token in costs:
            put(value, costs[token], token)
        elif default is not None:
            put(value, default, token)
    text = description.lower()
    for number in re.findall(r'(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])', description):
        put(float(number) if '.' in number else int(number), costs.get('const:number', 1), 'const:number')
    for quoted in re.findall(r"'([^']{1,12})'|\"([^\"]{1,12})\"", description):
        put(quoted[0] or quoted[1], costs.get('const:quoted', 1), 'const:quoted')
    if hand:
        if 'vowel' in text:
            put('aeiou', 2, const_token('aeiou'))
        if re.search(r'\b(?:even|odd|binary|bit|half|double|twice|pair)', text):
            put(2, 2, const_token(2))
        if re.search(PI_WORDS, description):
            put('math.pi', 2, const_token('math.pi'))
    return found


def param_names(inputs):
    pools = dict(str=['s', 't', 'u'], list=['items', 'other', 'third'], tuple=['tup', 'tup2', 'tup3'], dict=['d', 'd2'],
                 num=['n', 'm', 'k', 'p'], set=['group', 'group2'], bool=['flag', 'flag2'])
    used, names = defaultdict(int), []
    for i in range(len(inputs[0])):
        kinds = {kind(ex[i]) for ex in inputs}
        k = kinds.pop() if len(kinds) == 1 else 'value'
        pool = pools.get(k, ['value', 'value2', 'value3'])
        index = used[k]
        used[k] += 1
        names.append(pool[index] if index < len(pool) else f'{pool[0]}{index + 1}')
    return names


def matches(values, outputs):
    """Equal on every example; a yes/no answer must be a bool and vice versa (0 == False in Python)."""
    try:
        return all(isinstance(v, bool) == isinstance(o, bool) and v == o and (not isinstance(o, dict) or list(v) == list(o))
                   for v, o in zip(values, outputs))
    except Exception:
        return False


def uniform_costs(cost=2):
    """Every operation and comprehension form at one cost: the search with nothing
    learned or hand-tuned (use with hand=False)."""
    return {name: cost for name, *_ in OPS + HIGHER}


def synthesize(inputs, outputs, description='', costs=None, seconds=3.0, max_expressions=600_000, max_cost=16, inner_cost=8,
               rank=None, window=2, hand=True, collect=0, max_candidates=400):
    """Return (expression source, parameter names, stats) or (None, names, stats).

    The cheapest expression matching every example wins, except that one which
    ignores a parameter only wins if no expression using all parameters is found
    within two more cost levels (an ignored input usually means a coincidence).

    costs maps operation names, and optionally 'const:...' and 'iter:...' tokens,
    to search costs; missing operations keep their hand-set base cost. hand=False
    drops the hand-set constant costs and keyword rules (see constants()).

    collect=k keeps searching k cost levels past the first fit that uses every
    parameter and records all fits in stats['candidates'] (cost, uses all, source,
    tokens); rank(candidate) -> score then picks among them, lowest first.
    """
    costs = dict(costs or {})
    for name, *_, base in OPS:
        costs.setdefault(name, base)
    for name, *_, base in HIGHER:
        costs.setdefault(name, base)
    params = param_names(inputs)
    budget = Budget(seconds, max_expressions)
    bank = Bank()
    found = []                                      # (cost, uses every parameter, source, tokens)
    stats = dict(expressions=0, cost=None, timed_out=False)
    level = [0]

    def uses_all(src):
        return all(re.search(r'\b' + re.escape(name) + r'\b', src) for name in params)

    first_complete = []

    def check(src, values, parts=(), token=None):
        if matches(values, outputs):
            complete = uses_all(src)
            found.append((level[0], complete, src, tokens_of(parts, token)))
            if complete and not collect:
                raise StopIteration
            if complete and not first_complete:
                first_complete.append(level[0])
            if len(found) >= max_candidates:
                raise StopIteration

    literals = list(constants(description, inputs, costs, hand).values())
    try:
        for i, name in enumerate(params):
            values = tuple(ex[i] for ex in inputs)
            check(name, values)
            bank.add(1, name, values)
        for value, cost, token in literals:
            actual = math.pi if value == 'math.pi' else value
            src = 'math.pi' if value == 'math.pi' else repr(value)
            values = tuple(actual for _ in inputs)
            check(src, values, (), token)
            bank.add(cost, src, values, (), token)

        # Inner banks: expressions over one loop element, for comprehension bodies.
        inner = []
        for src, it_cost, per_example, token in iterables(params, inputs):
            it = Iterable(src, costs.get(token, it_cost), per_example, 'x', token)
            if not it.flat or len(it.flat) > 600:
                continue
            ib = Bank()
            ib.add(1, 'x', tuple(it.flat))
            for i, name in enumerate(params):
                ib.add(2, name, tuple(inputs[e][i] for e in it.owner))
            for value, cost, token in literals:
                actual = math.pi if value == 'math.pi' else value
                ib.add(cost, 'math.pi' if value == 'math.pi' else repr(value), tuple(actual for _ in it.flat), (), token)
            inner_budget = Budget(seconds / 8, max_expressions // 10)
            try:
                for c in range(2, inner_cost + 1):
                    grow(ib, c, costs, inner_budget)
            except TimeoutError:
                pass
            inner.append((it, ib))

        for cost in range(2, max_cost + 1):
            if found and cost > found[0][0] + (window if rank else 2) and not first_complete:
                break
            if first_complete and cost > first_complete[0] + collect:
                break
            level[0] = stats['cost'] = cost
            grow(bank, cost, costs, budget, check)
            for name, tag, has_body, has_cond, aggregate, template, _ in HIGHER:
                rest = cost - costs[name]
                for it, ib in inner:
                    parts = rest - it.cost
                    slots = int(has_body) + int(has_cond)
                    if parts < slots:
                        continue
                    for split in compositions(parts, slots):
                        body_pool = ib.at(split[0], None) if has_body else [None]
                        cond_pool = ib.at(split[-1], {'bool'}) if has_cond else [None]
                        for body, cond in product(body_pool, cond_pool):
                            budget.spend()
                            values = []
                            try:
                                for els, idx in zip(it.elements, it.groups):
                                    b = [body[1][p] for p in idx] if body else None
                                    c = [cond[1][p] for p in idx] if cond else None
                                    values.append(aggregate(els, b, c))
                            except Exception:
                                continue
                            values = tuple(values)
                            if not all(safe(v) for v in values):
                                continue
                            src = template.format(body=body[0] if body else '', cond=cond[0] if cond else '', v='x', it=it.src)
                            parts = (body, cond, it.part)
                            check(src, values, parts, name)
                            bank.add(cost, src, values, parts, name)
    except StopIteration:
        pass
    except TimeoutError:
        stats['timed_out'] = True
    stats['expressions'] = bank.size
    if not found:
        return None, params, stats
    if collect:
        stats['candidates'] = [(c, complete, tidy(src), sorted(tokens)) for c, complete, src, tokens in found]
    if rank is None:
        best = next((f for f in found if f[1]), found[0])
    else:
        pool = [f for f in found if f[1]] or found
        best = min(pool, key=rank)
    stats['uses_all_parameters'] = best[1]
    stats['tokens'] = sorted(best[3])
    return tidy(best[2]), params, stats


def tidy(src):
    try:
        return ast.unparse(ast.parse(src, mode='eval'))
    except SyntaxError:
        return src


def render(function_name, params, expression):
    imports = 'import math\n\n\n' if 'math.' in expression else ''
    return f'{imports}def {function_name}({", ".join(params)}):\n    return {expression}\n'
