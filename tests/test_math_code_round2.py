"""New locally authored development fixtures; no original comparison cases."""
import pytest

from cael_unified.helper_math_frames import solve
from cael_unified.codegen.trace import output
from cael_unified.codegen.chat import reply


@pytest.mark.parametrize('question,expected',[
    ('18 is what percent of 72?',25),
    ('What percentage of 80 is 12?',15),
    ('24 is 30 percent of what number?',80),
    ('What is two thirds of 51?',34),
    ('Find the difference between -4 and 9',13),
    ('Calculate the product of 1.5 and 8',12),
    ('Compute 9 choose 2',36),
    ('$200 at 10% compounded annually for 2 years',242),
    ('Probability of exactly 2 heads in 3 fair coin flips',3/8),
    ('Probability of at least 1 head in 4 fair coin tosses',15/16),
    ('Probability of a sum of 7 with two fair six-sided dice',1/6),
    ('A car travels 135 km in 3 hours. What is its average speed?',45),
    ('At 75 km/h how long does it take to travel 150 km?',2),
    ('The average of 4 numbers is 8. The first 3 numbers are 3 7 and 10. What is the last number?',12),
])
def test_explicit_exact_frames(question,expected):
    result=solve(question)
    assert result is not None
    assert float(result[0])==pytest.approx(expected)


@pytest.mark.parametrize('question',[
    'Probability of a sum of 7 with two loaded dice',
    'What is the value of $200 earning interest?',
    'At 75 mph how long does it take to travel 150 km?',
    'Probability of exactly 2 heads in 99 fair coin flips',
    '0 is 0 percent of what number?',
])
def test_missing_or_inconsistent_assumptions_refused(question):
    assert solve(question) is None


@pytest.mark.parametrize('source,expected',[
    ('s = 0\nfor i in range(5):\n    s += i\nprint(s)','10'),
    ('values=[]\nfor i in range(4):\n    if i % 2 == 0:\n        values.append(i*i)\nprint(values)','[0, 4]'),
    ('def f(n):\n    if n < 2:\n        return n\n    return f(n-1)+f(n-2)\nprint(f(7))','13'),
    ('n=3\nwhile n>0:\n    print(n)\n    n -= 1','3\n2\n1'),
    ('x=[1,2]\ny=x\ny.append(3)\nprint(x)','[1, 2, 3]'),
    ('x=[i*i for i in range(6) if i%2]\nprint(x)','[1, 9, 25]'),
    ('print(2 < 3 < 4, 0 or 5, 3 and 4)','True 5 4'),
    ('print("abc"[::-1])','cba'),
])
def test_checked_python_traces(source,expected):
    assert output(source)==expected


@pytest.mark.parametrize('source',[
    'import os\nprint(os.getcwd())',
    'print(open("private.txt").read())',
    'print((1).__class__)',
    'while True:\n    pass',
    'print(list(range(1000000000)))',
    'print("x" * 1000000000)',
    'print("%999999999s" % "x")',
    'print(9**9**9)',
    'print = 3\nprint(1)',
    'def f(n):\n    return n+1\nprint(f)',
])
def test_trace_refuses_unsafe_or_large_code(source):
    assert output(source) is None


def test_full_code_frontend_reports_checked_prints():
    answer=reply('What is the output of this Python code?\n```python\ntotal=0\nfor x in [2,4,6]:\n    total += x\nprint(total)\n```')
    assert answer['route']=='chat/code-explained'
    assert 'Checked output:\n```text\n12\n```' in answer['response']
