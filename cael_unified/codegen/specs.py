"""Everyday Python tasks CAEL can write without being given examples.

Each task is a description pattern, a function name and parameter names, and test cases that define the
behaviour. When a request matches, the cases go to the program search (synth.synthesize), which writes a
function; the function is then run on held-out checks it never saw, so an expression that only fits the cases
by luck is rejected. The cases are the specification, not the code: no solution is stored here. `facts` are
plain facts a person would state (a conversion factor, a rule); their numbers become search constants.
"""
import math
import re

TASKS = [
    dict(pattern=r'\brevers\w* (?:a |the )?(?:string|text|word)', name='reverse_string', params=['s'],
         cases=[(('abc',), 'cba'), (('hello',), 'olleh'), (('',), ''), (('a',), 'a')], checks=[(('ab cd',), 'dc ba')]),
    dict(pattern=r'\brevers\w* (?:a |the )?list', name='reverse_list', params=['items'],
         cases=[(([1, 2, 3],), [3, 2, 1]), (([],), []), ((['a', 'b'],), ['b', 'a'])], checks=[(([5, 6, 7, 8],), [8, 7, 6, 5])]),
    dict(pattern=r'\bpalindrome', name='is_palindrome', params=['s'],
         cases=[(('racecar',), True), (('hello',), False), (('',), True), (('abba',), True), (('ab',), False)],
         checks=[(('level',), True), (('abca',), False)]),
    dict(pattern=r'\bprime\b', name='is_prime', params=['n'],
         cases=[((2,), True), ((3,), True), ((4,), False), ((9,), False), ((13,), True), ((1,), False), ((0,), False), ((25,), False), ((29,), True)],
         checks=[((6,), False), ((15,), False), ((17,), True), ((21,), False), ((97,), True), ((91,), False)]),
    dict(pattern=r'\bfactorial', name='factorial', params=['n'],
         cases=[((0,), 1), ((1,), 1), ((3,), 6), ((5,), 120), ((6,), 720)], checks=[((4,), 24), ((10,), 3628800)]),
    dict(pattern=r'\bfibonacci|\bfib\b', name='fibonacci', params=['n'],
         cases=[((0,), 0), ((1,), 1), ((2,), 1), ((5,), 5), ((10,), 55), ((7,), 13)], checks=[((3,), 2), ((12,), 144), ((20,), 6765)]),
    dict(pattern=r'\b(?:remov\w*|drop\w*|delet\w*|strip\w*|get rid of) (?:the |all |any )?duplicates?|\bunique (?:items|values|elements)|\bdedup', name='remove_duplicates', params=['items'],
         cases=[(([1, 2, 2, 3],), [1, 2, 3]), (([3, 1, 3, 2, 1],), [3, 1, 2]), (([],), []), ((['a', 'a'],), ['a'])],
         checks=[(([5, 5, 4, 5],), [5, 4]), ((['b', 'a', 'b'],), ['b', 'a'])]),
    dict(pattern=r'\bcount (?:the )?(?:number of )?vowels', name='count_vowels', params=['s'],
         cases=[(('hello',), 2), (('sky',), 0), (('aeiou',), 5), (('',), 0)], checks=[(('banana',), 3)]),
    dict(pattern=r'\bcount (?:the )?(?:number of )?words', name='count_words', params=['text'],
         cases=[(('hello world',), 2), (('one',), 1), (('',), 0), (('a b c d',), 4)], checks=[(('  two  words ',), 2)]),
    dict(pattern=r'\b(?:largest|biggest|maximum|max)\b.*\blist|\blist\b.*\b(?:largest|biggest|maximum|max)\b', name='largest', params=['numbers'],
         cases=[(([1, 5, 3],), 5), (([-2, -9],), -2), (([7],), 7)], checks=[(([3, 8, 8, 1],), 8)]),
    dict(pattern=r'\b(?:smallest|minimum|min)\b.*\blist|\blist\b.*\b(?:smallest|minimum|min)\b', name='smallest', params=['numbers'],
         cases=[(([4, 1, 3],), 1), (([-2, -9],), -9), (([7],), 7)], checks=[(([3, 8, 0, 1],), 0)]),
    dict(pattern=r'\b(?:sum|add up|total)\b.*\b(?:list|numbers)\b', name='total', params=['numbers'],
         cases=[(([1, 2, 3],), 6), (([],), 0), (([-1, 1, 5],), 5)], checks=[(([10, 20],), 30)]),
    dict(pattern=r'\b(?:average|mean)\b', name='average', params=['numbers'],
         cases=[(([1, 2, 3],), 2.0), (([4],), 4.0), (([1, 2],), 1.5)], checks=[(([2, 4, 9],), 5.0)]),
    dict(pattern=r'\bsum (?:of )?(?:the |its )?digits', name='digit_sum', params=['n'],
         cases=[((123,), 6), ((0,), 0), ((9,), 9), ((505,), 10)], checks=[((9999,), 36)]),
    dict(pattern=r'\b(?:celsius|centigrade)\b.*\bfahrenheit|\bc to f\b', name='celsius_to_fahrenheit', params=['c'],
         facts='F = C * 1.8 + 32', cases=[((0,), 32.0), ((100,), 212.0), ((-40,), -40.0), ((10,), 50.0)],
         checks=[((37,), 98.6), ((25,), 77.0)]),
    dict(pattern=r'\bfahrenheit\b.*\b(?:celsius|centigrade)|\bf to c\b', name='fahrenheit_to_celsius', params=['f'],
         facts='C = (F - 32) / 1.8', cases=[((32,), 0.0), ((212,), 100.0), ((-40,), -40.0), ((50,), 10.0)],
         checks=[((77,), 25.0), ((98.6,), 37.0)]),
    dict(pattern=r'\b(?:even|odd)\b.*\bnumber|\bnumber\b.*\b(?:even|odd)\b|\bis (?:even|odd)\b', name='is_even', params=['n'],
         cases=[((2,), True), ((3,), False), ((0,), True), ((-4,), True), ((7,), False), ((10,), True)],
         checks=[((5,), False), ((100,), True), ((11,), False), ((-3,), False)]),
    dict(pattern=r'\buppercase|\bupper case|\bcapitali[sz]e (?:all|every letter)', name='to_upper', params=['s'],
         cases=[(('abc',), 'ABC'), (('Hi there',), 'HI THERE'), (('',), '')], checks=[(('mIx',), 'MIX')]),
    dict(pattern=r'\bcapitali[sz]e (?:each|the first letter of each|every) word|\btitle case', name='title_case', params=['s'],
         cases=[(('hello world',), 'Hello World'), (('a b',), 'A B'), (('',), '')], checks=[(('big red dog',), 'Big Red Dog')]),
    dict(pattern=r'\bsort (?:a |the )?(?:dict(?:ionary)?) by (?:its )?values?', name='sort_by_value', params=['d'],
         cases=[(({'a': 3, 'b': 1, 'c': 2},), {'b': 1, 'c': 2, 'a': 3}), (({},), {}), (({'x': 1},), {'x': 1})],
         checks=[(({'p': 9, 'q': 4},), {'q': 4, 'p': 9}), (({'m': 2, 'n': 5, 'o': 1},), {'o': 1, 'm': 2, 'n': 5})]),
    dict(pattern=r'\bsort (?:a |the )?list', name='sort_list', params=['items'],
         cases=[(([3, 1, 2],), [1, 2, 3]), (([],), []), ((['b', 'a'],), ['a', 'b'])], checks=[(([9, -1, 4],), [-1, 4, 9])]),
    dict(pattern=r'\bsquares?\b.*\blist|\blist\b.*\bsquares?\b', name='squares', params=['numbers'],
         cases=[(([1, 2, 3],), [1, 4, 9]), (([],), []), (([-2],), [4])], checks=[(([5, 10],), [25, 100])]),
    dict(pattern=r'\bcount (?:how many times|occurrences)|\boccurrences of\b', name='count_occurrences', params=['items', 'value'],
         cases=[(([1, 2, 1, 1], 1), 3), (([], 5), 0), ((['a', 'b'], 'b'), 1)], checks=[(([4, 4, 2], 4), 2)]),
    dict(pattern=r'\bflatten', name='flatten', params=['lists'],
         cases=[(([[1, 2], [3]],), [1, 2, 3]), (([],), []), (([[], [4]],), [4]), (([[5, 6], [7, 8]],), [5, 6, 7, 8])],
         checks=[(([[1], [2], [3]],), [1, 2, 3]), (([[9, 8, 7]],), [9, 8, 7])]),
    dict(pattern=r'\bleap year', name='is_leap_year', params=['year'],
         facts='divisible by 4 and not by 100, or divisible by 400',
         cases=[((2000,), True), ((1900,), False), ((2024,), True), ((2023,), False), ((2100,), False), ((1996,), True), ((2400,), True)],
         checks=[((1800,), False), ((2004,), True), ((2001,), False), ((1600,), True), ((1700,), False), ((2028,), True), ((2019,), False), ((1904,), True), ((1792,), True), ((2200,), False)]),
    dict(pattern=r'\banagram', name='is_anagram', params=['a', 'b'],
         cases=[(('listen', 'silent'), True), (('abc', 'abd'), False), (('', ''), True), (('ab', 'ba'), True), (('aab', 'abb'), False)],
         checks=[(('dog', 'god'), True), (('a', 'b'), False), (('abc', 'cab'), True), (('ab', 'abc'), False)]),
    dict(pattern=r'\b(?:gcd|greatest common divisor|highest common factor)\b', name='gcd', params=['a', 'b'],
         cases=[((12, 8), 4), ((7, 3), 1), ((10, 5), 5), ((0, 4), 4)], checks=[((18, 24), 6), ((9, 6), 3)]),
    dict(pattern=r'\bremove (?:all )?(?:the )?(?:spaces|whitespace)', name='remove_spaces', params=['s'],
         cases=[(('a b c',), 'abc'), (('  x ',), 'x'), (('',), '')], checks=[(('hello world',), 'helloworld')]),
    dict(pattern=r'\bfirst (?:letter|character)', name='first_letter', params=['s'],
         cases=[(('hello',), 'h'), (('Abc',), 'A'), (('z',), 'z')], checks=[(('xyz',), 'x')]),
    dict(pattern=r'\bmerge (?:two )?dict', name='merge_dicts', params=['a', 'b'],
         cases=[(({'a': 1}, {'b': 2}), {'a': 1, 'b': 2}), (({'a': 1}, {'a': 3}), {'a': 3}), (({}, {}), {})],
         checks=[(({'x': 1, 'y': 2}, {'y': 5, 'z': 6}), {'x': 1, 'y': 5, 'z': 6})]),
    dict(pattern=r'\b(?:km|kilomet(?:er|re)s?)\b.*\bmiles\b', name='km_to_miles', params=['km'],
         facts='1 mile is 1.609344 km', cases=[((0,), 0.0), ((1.609344,), 1.0), ((16.09344,), 10.0)],
         checks=[((5,), 3.106855961186669), ((42.195,), 26.218757456454306)]),
    dict(pattern=r'\bsquare root', name='square_root', params=['number'],
         cases=[((4,), 2.0), ((9,), 3.0), ((0,), 0.0), ((2.25,), 1.5)], checks=[((16,), 4.0)]),
    dict(pattern=r'\b(?:power|exponent|raises? .* to)\b', name='power', params=['base', 'exponent'],
         cases=[((2, 3), 8), ((5, 0), 1), ((3, 2), 9), ((2, 1), 2)], checks=[((10, 3), 1000), ((4, 2), 16)]),
]


def find(text):
    """The task a plain request describes, or None."""
    lower = ' '.join(text.lower().split())
    for task in TASKS:
        if re.search(task['pattern'], lower):
            return task
    return None


def same(value, expected):
    """Equal, counting dict and list order and bool versus int; floats to about 9 digits."""
    if isinstance(expected, bool) or isinstance(value, bool):
        return type(value) is type(expected) and value == expected
    if isinstance(expected, float) and isinstance(value, (int, float)):
        return abs(value - expected) < 1e-9 * max(1.0, abs(expected))
    if isinstance(expected, dict):
        return isinstance(value, dict) and list(value) == list(expected) and all(same(value[k], expected[k]) for k in expected)
    if isinstance(expected, (list, tuple)):
        return type(value) is type(expected) and len(value) == len(expected) and all(map(same, value, expected))
    return value == expected


def run(expr, params, args):
    return eval(expr, {'math': math, **dict(zip(params, args))})


def rename(expr, found, params):
    """The search names parameters itself (s, n, items...); use the task's names instead, outside string literals."""
    mapping = dict(zip(found, params))
    parts = re.split(r"""('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")""", expr)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r'\b[A-Za-z_]\w*\b', lambda m: mapping.get(m[0], m[0]), parts[i])
    return ''.join(parts)


def passes(expr, params, pairs):
    failed = []
    for args, expected in pairs:
        try:
            ok = same(run(expr, params, args), expected)
        except Exception:
            ok = False
        if not ok:
            failed.append((args, expected))
    return failed


def solve(task, synthesize, costs=None, seconds=8.0):
    """Search for a function meeting the task's cases, then run it on the held-out checks. A failed check
    becomes a case and the search runs again (three rounds at most), so a lucky fit is never shown.
    If no single expression works, a counted loop is searched (recurrence.py) and checked the same way.
    Returns (function source, number of cases it passed), or (None, 0)."""
    from . import recurrence
    from .synth import render
    cases, checks = list(task['cases']), list(task.get('checks', ()))
    description = task['name'].replace('_', ' ') + '. ' + task.get('facts', '')
    params = task['params']
    for _ in range(3):
        expr, found, _stats = synthesize([c[0] for c in cases], [c[1] for c in cases], description,
                                         costs(description) if costs else None, seconds=seconds, inner_cost=10)
        if expr is None:
            break
        expr = rename(expr, found, params)
        failed = passes(expr, params, cases + checks)
        if not failed:
            return render(task['name'], params, expr), len(cases) + len(checks)
        cases += [f for f in failed if f not in cases]
        checks = [c for c in checks if c not in failed]
    everything = list(task['cases']) + list(task.get('checks', ()))
    loop = recurrence.search(task['cases'])
    if loop and all(recurrence.run(loop[0], loop[1], args[0]) == expected for args, expected in everything):
        return recurrence.render(task['name'], params[0], *loop), len(everything)
    test = recurrence.search_all(task['cases'])
    if test and all(recurrence.check_all(*test, args[0]) == expected for args, expected in everything):
        return recurrence.render_all(task['name'], params[0], *test), len(everything)
    return None, 0
