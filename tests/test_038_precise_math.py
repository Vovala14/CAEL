"""Independent authored boundary probes for the new adapters/checkers."""
from fractions import Fraction
import pytest
from cael_unified import precise_math, verify
from cael_unified.codegen import request_contract


@pytest.mark.parametrize('a,b,solution', [(a, b, n) for a in (-8, -2, 1, 3, 11) for b in (-5, 0, 7) for n in (-4, 0, 9)])
def test_affine_coefficients(a, b, solution):
    question = f'Solve {a}*z + ({b}) = {a*solution+b}.'
    answer = precise_math.reply(question)
    assert answer['response'] == f'z = {solution}'
    assert verify.check_equation(question, answer)['status'] == 'verified'


@pytest.mark.parametrize('question', [
    'What does x = y mean in Python?', 'if n is prime, solve n + 2 = 9',
    'solve x+1=3 without fractions', 'solve x+1=3 and send an email',
    'let table = 3 in this script', 'solve open("x")=1',
    'Tell a story about the median of a kingdom',
])
def test_math_does_not_drop_unknown_requirements(question):
    assert precise_math.reply(question) is None


def test_checker_whole_polynomial_and_all_roots():
    okay = dict(route='helper/equation', response='x = 2 or x = 5')
    assert verify.check_equation('Solve x^2 - 7*x + 10 = 0.', okay)['status'] == 'verified'
    bad = dict(okay, response='x = 2 or x = 6')
    assert verify.check_equation('Solve x^2 - 7*x + 10 = 0.', bad)['status'] == 'failed'
    with pytest.raises(verify.Unchecked):
        verify.check_equation('Explain a story in which x + 2 = 7.', dict(response='x = 5'))


def test_code_checker_uses_interpreter_and_literal_tests():
    source = dict(route='chat/code-composed', response='```python\ndef f(x):\n    return x*3\n```')
    assert verify.check_code('f(2) == 6\nf(-3) == -9', source)['status'] == 'verified'
    assert verify.check_code('f(2) == 7\nf(-3) == -9', source)['status'] == 'failed'
    with pytest.raises(verify.Unchecked):
        verify.sandbox_function('def f(x):\n    return x')


def test_vm_limit_is_unchecked():
    code = dict(route='chat/code-composed', response='```python\ndef f(x):\n    import os\n    return x\n```')
    with pytest.raises(verify.Unchecked):
        verify.check_code('f(2) == 2', code)


@pytest.mark.parametrize('name', ['ok', 'thx', 'greet_u', 'calclate_value', 'f_42'])
def test_names_are_protected_without_rewriting(name):
    text = 'Build a Python function named '+name+' that tests whether a number is even.'
    assert request_contract.protected(text)
    assert 'def '+name+'(' in request_contract.named_reply(text)['response']


def test_assignment_explanation_does_not_execute_source():
    result = request_contract.explanation('What does alpha = beta mean in Python?')
    assert 'beta' in result['response'] and 'alpha' in result['response'] and 'NameError' in result['response']
    assert request_contract.explanation('What does alpha = dangerous() mean in Python?') is None
