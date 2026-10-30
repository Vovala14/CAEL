"""Search for a counted loop: start with a, b = x, y; repeat n times a, b = b, step(a, b, k); return a.

The single-expression search cannot write loops with state, so number sequences such as Fibonacci,
triangular numbers or powers fall outside it. This search tries small starting values and small update
expressions (built from a, b, the step counter k and 1, 2 with + - *), cheapest first, and keeps the first
loop that returns every expected value.
"""
import ast
import functools
import itertools
import operator
import re

SEEDS = (0, 1, 2)
ATOMS = ('a', 'b', 'k', '1', '2')


OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul}


@functools.lru_cache(maxsize=4096)
def step_function(src):
    """A closed, eval-free reading of an update expression: only a, b, k, small integers and + - *.
    Anything else raises ValueError, so no generated text is ever executed natively."""
    def build(node):
        if isinstance(node, ast.Name) and node.id in ('a', 'b', 'k'):
            index = ('a', 'b', 'k').index(node.id)
            return lambda env: env[index]
        if isinstance(node, ast.Constant) and type(node.value) is int:
            value = node.value
            return lambda env: value
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            op, left, right = OPS[type(node.op)], build(node.left), build(node.right)
            return lambda env: op(left(env), right(env))
        raise ValueError('update expression outside the a/b/k +-* grammar')
    tree = ast.parse(src, mode='eval')
    return build(tree.body)


def expressions(depth=2):
    """Update expressions, cheapest first; each is (source, function of a, b, k)."""
    level = [(atom, step_function(atom)) for atom in ATOMS]
    seen = list(level)
    for _ in range(depth - 1):
        grown = []
        for (x, _), (y, _) in itertools.product(level, seen):
            for op in ('+', '-', '*'):
                src = f'{x} {op} {y}'
                grown.append((src, step_function(src)))
        seen += grown
        level = grown
    return seen


def run(seed, step, n):
    """step is an update source string or a function from expressions(); never evaluated natively."""
    fn = step_function(step) if isinstance(step, str) else step
    a, b = seed
    for k in range(1, n + 1):
        a, b = b, fn((a, b, k))
        if abs(a) > 10 ** 30:
            raise OverflowError
    return a


def search(cases, limit=200_000):
    """cases: [((n,), value)] with whole n >= 0. Returns (seed, step source) or None."""
    if not cases or any(len(args) != 1 or not isinstance(args[0], int) or isinstance(args[0], bool) or args[0] < 0
                        or isinstance(value, bool) or not isinstance(value, int) for args, value in cases):
        return None
    tried = 0
    for src, step in expressions():
        for seed in itertools.product(SEEDS, SEEDS):
            tried += 1
            if tried > limit:
                return None
            try:
                if all(run(seed, step, args[0]) == value for args, value in cases):
                    return seed, src
            except (OverflowError, ZeroDivisionError):
                continue
    return None


def render(name, param, seed, step):
    loop = f'for k in range(1, {param} + 1):' if 'k' in step.split() else f'for _ in range({param}):'
    return (f'def {name}({param}):\n'
            f'    a, b = {seed[0]}, {seed[1]}\n'
            f'    {loop}\n'
            f'        a, b = b, {step}\n'
            f'    return a\n')


# A second loop shape: a guard on n, then a test that must hold for every d in a range (or for some d).
GUARDS = ('True', 'n > 1', 'n > 0', 'n >= 0')
RANGES = (('2', 'n'), ('2', 'int(n ** 0.5) + 1'), ('1', 'n'), ('1', 'n + 1'))
TESTS = ('n % d != 0', 'n % d == 0', 'd * d != n', 'n != d')
QUANTIFIERS = ('all', 'any')
NEGATE = {'n > 1': 'n <= 1', 'n > 0': 'n <= 0', 'n >= 0': 'n < 0', 'n % d != 0': 'n % d == 0',
          'n % d == 0': 'n % d != 0', 'd * d != n': 'd * d == n', 'n != d': 'n == d'}


# Fixed tables replace eval of the guard/range/test strings; unknown strings are refused.
GUARD_FN = {'True': lambda n: True, 'n > 1': lambda n: n > 1, 'n > 0': lambda n: n > 0, 'n >= 0': lambda n: n >= 0}
BOUND_FN = {'1': lambda n: 1, '2': lambda n: 2, 'n': lambda n: n, 'n + 1': lambda n: n + 1,
            'int(n ** 0.5) + 1': lambda n: int(n ** 0.5) + 1}
TEST_FN = {'n % d != 0': lambda n, d: n % d != 0, 'n % d == 0': lambda n, d: n % d == 0,
           'd * d != n': lambda n, d: d * d != n, 'n != d': lambda n, d: n != d}


def check_all(guard, lo, hi, test, quantifier, n):
    if guard not in GUARD_FN or lo not in BOUND_FN or hi not in BOUND_FN or test not in TEST_FN:
        raise ValueError('loop shape outside the fixed tables')
    if not GUARD_FN[guard](n):
        return False
    numbers = range(BOUND_FN[lo](n), BOUND_FN[hi](n))
    found = (TEST_FN[test](n, d) for d in numbers)
    return all(found) if quantifier == 'all' else any(found)


def search_all(cases):
    """cases: [((n,), bool)]. Returns (guard, lo, hi, test, quantifier) or None."""
    if not cases or any(len(args) != 1 or not isinstance(args[0], int) or isinstance(args[0], bool) or args[0] < 0
                        or not isinstance(value, bool) for args, value in cases):
        return None
    for guard in GUARDS:
        for lo, hi in RANGES:
            for test in TESTS:
                for quantifier in QUANTIFIERS:
                    if all(check_all(guard, lo, hi, test, quantifier, args[0]) == value for args, value in cases):
                        return guard, lo, hi, test, quantifier
    return None


def render_all(name, param, guard, lo, hi, test, quantifier):
    swap = lambda s: re.sub(r'\bn\b', param, s)
    lines = [f'def {name}({param}):']
    if guard != 'True':
        lines += [f'    if {swap(NEGATE[guard])}:', '        return False']
    if quantifier == 'all':
        lines += [f'    for d in range({swap(lo)}, {swap(hi)}):', f'        if {swap(NEGATE[test])}:', '            return False',
                  '    return True']
    else:
        lines += [f'    for d in range({swap(lo)}, {swap(hi)}):', f'        if {swap(test)}:', '            return True',
                  '    return False']
    return '\n'.join(lines) + '\n'
