"""Locally authored development fixtures, independent of the Qwen comparison."""
import ast
import re

import pytest
import sympy as sp

from cael_unified import helper_math
from cael_unified.codegen import contracts


@pytest.mark.parametrize('prompt,expected', [
    ('calculate sqrt(196)', '14'), ('factorial of 7', '5040'),
    ('gcd of 54 and 90', '18'), ('lcm of 14 and 35', '70'),
    ('what is sin(pi/2)', '1'), ('evaluate abs(-17)', '17'),
    ('mean of 3, 8, 10', '7'), ('median of 2, 8, 10, 20', '9'),
    ('average of 1, 2', '1.5'), ('range of -3, 6, 11', '14'),
    ('3/5 of 45', '27'), ('convert -40 celsius to fahrenheit', '-40'),
    ('convert 95 fahrenheit to celsius', '35'),
    ('if 4 pens cost $10, how much do 6 pens cost?', '15'),
    ('split 140 in the ratio 2:5', '40 and 100'),
    ('A coat costs $125 with 20% off and 8% tax. What is the final price?', '108'),
    ('Find the area of a rectangle with length 9 and width 4.', '36'),
    ('What is the perimeter of a square with side 7?', '28'),
    ('Calculate the area of a triangle with base 8 and height 5.', '20'),
    ('Find the area of a rectangle 2 meters by 30 centimeters.', '0.6'),
    ('A train travels at 72 km/h for 2.5 hours. How far does it travel?', '180'),
])
def test_exact_authored_math(prompt, expected):
    result = helper_math.reply(prompt)
    assert result is not None, prompt
    assert expected in result['response']
    assert result['exact'] and not result['sources']


def test_symbolic_equations_and_algebra():
    assert 'x = 3' in helper_math.reply('Solve x^2 - 5*x + 6 = 0')['response']
    assert 'x = 2' in helper_math.reply('Solve x^2 - 5*x + 6 = 0')['response']
    assert helper_math.reply('Solve x+y=11 and x-y=3')['response'] == 'x = 7, y = 4'
    assert 'no solution' in helper_math.reply('Solve x+y=1 and x+y=2')['response']
    assert 'infinitely' in helper_math.reply('Solve x+y=1 and 2*x+2*y=2')['response']
    assert helper_math.reply('differentiate 3*x^3 - 2*x')['response'] == '9*x^2 - 2'
    assert '(x - 4)' in helper_math.reply('factor x^2 - 16')['response']


@pytest.mark.parametrize('text', [
    "__import__('os').system('echo unsafe')", 'calculate 9**9**9',
    'solve sin(x)=x', 'What is Python?', 'write a story about algebra',
    'factorial of 100000', 'Find the area and perimeter of a rectangle 3 by 5',
    'Find the area of a triangle with sides 3 and 5',
    'Find the area of a circle of size 7', 'x+2',
])
def test_math_abstains(text):
    assert helper_math.reply(text) is None


def generated(prompt):
    response = contracts.reply(prompt)
    assert response is not None, prompt
    code = re.search(r'```python\n(.*?)```', response['response'], re.S)[1]
    tree = ast.parse(code)
    name = next(node.name for node in tree.body if isinstance(node, ast.FunctionDef))
    scope = {}
    exec(compile(tree, '<authored-generated-test>', 'exec'), scope)
    return scope[name]


@pytest.mark.parametrize('prompt,args,expected', [
    ('Write a Python function to sum positive even numbers in a list', ([-4, -3, 0, 2, 5, 8],), 10),
    ('Write a function to count negative numbers in a list', ([-2, 0, -4, 9],), 2),
    ('Write a Python function to return the squares of odd numbers in a list', ([0, 1, 2, 3, -5],), [1, 9, 25]),
    ('Create a Python function to remove negative numbers from a list', ([-2, 0, 3],), [0, 3]),
    ('Write a function to sort the unique numbers in descending order', ([3, 1, 3, 8],), [8, 3, 1]),
    ('Write a Python function to count word frequencies ignoring case', ('Tea tea WATER',), {'tea': 2, 'water': 1}),
    ('Write a Python function for character frequencies', ('abac',), {'a': 2, 'b': 1, 'c': 1}),
    ('Write a Python function for balanced brackets', ('{a[()]}',), True),
    ('Write a Python function for balanced brackets', ('([)]',), False),
    ('Write a Python function for binary search', ([1, 2, 2, 8], 2), 1),
    ('Write a Python function for binary search', ([], 2), -1),
    ('Write a Python function to check whether a number is odd', (6,), False),
    ('Write a Python function to check whether a number is odd', (-7,), True),
    ('Write a Python function to determine whether a number is prime', (91,), False),
    ('Write a Python function to determine whether a number is prime', (97,), True),
    ('Write a Python function for two sum returning indices', ([8, 3, 8, 2], 16), [0, 2]),
    ('Write a Python function for two sum returning indices', ([1, 2], 9), None),
    ('Write a Python function for a palindrome ignoring case and punctuation', ('A man, a plan, a canal: Panama!',), True),
    ('Write a Python function to flatten a list recursively', ([[1, [2]], [], 'abc'],), [1, 2, 'abc']),
    ('Write a Python function to split a list into chunks of 3', ([1, 2, 3, 4, 5],), [[1, 2, 3], [4, 5]]),
    ('Write a Python function to rotate a list left by 2', ([1, 2, 3, 4, 5],), [3, 4, 5, 1, 2]),
    ('Write a Python function to rotate an array right', ([1, 2, 3], -1), [2, 3, 1]),
    ('Write a Python function to sort a dictionary by values descending', ({'x': 1, 'a': 7},), {'a': 7, 'x': 1}),
    ('Write a Python function for the second largest distinct number', ([3, 7, 7, 2],), 3),
    ('Write a Python function for the second largest including duplicates', ([3, 7, 7, 2],), 7),
    ('Write a Python function to average positive numbers in a list', ([-3, 2, 8, 5],), 5),
])
def test_composed_code(prompt, args, expected):
    assert generated(prompt)(*args) == expected


def test_respects_function_name_and_empty_input_contracts():
    fn = generated('Write a Python function called my_mean to average positive numbers in a list')
    assert fn.__name__ == 'my_mean'
    with pytest.raises(ValueError):
        fn([])
    with pytest.raises(ValueError):
        generated('Write a function for the second largest distinct number')([3, 3])
    with pytest.raises(ValueError):
        generated('Write a function to split a list into chunks')([1, 2], 0)


def test_unrecognised_or_ambiguous_constraints_are_not_invented():
    assert contracts.reply('Write a Python function to solve my entire application') is None
    assert contracts.reply('Write a Python function to sort a list in-place') is None
    assert contracts.reply('Write a story about binary search') is None
    assert contracts.reply('Write a Python function for the second largest number')['route'] == 'chat/code-clarify'
    from cael_unified.codegen.chat import reply
    assert reply('Write a Python function to sort a list in-place')['route'] == 'chat/code-clarify'
    assert reply('Write a Python function to sort a list without using sorted')['route'] == 'chat/code-clarify'
