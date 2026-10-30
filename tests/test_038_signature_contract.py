"""Independent semantic/negative boundaries; generated code stays in the VM."""
import ast
import re

import pytest

from cael_unified.codegen import signature_contract as contract
from cael_unified.codegen.python_vm import run_cases


def stub(signature, doc):
    return 'Complete the Python function:\n```python\ndef '+signature+':\n    """'+doc.replace('\n', '\n    ')+'\n    """\n    pass\n```'


def source(answer):
    assert answer['route'] == 'chat/code-signature-built', answer
    return re.search(r'```python\n(.*?)```', answer['response'], re.S)[1]


def run(signature, doc, cases):
    code = source(contract.reply(stub(signature, doc)))
    fn = ast.parse(code).body[0]
    expected = ast.parse('def '+signature+':\n    pass').body[0]
    assert fn.name == expected.name and ast.dump(fn.args) == ast.dump(expected.args)
    results = run_cases(code, [dict(name=fn.name, args=a, kwargs=k) for a, k, _ in cases])
    assert results['status'] == 'ok'
    for row, (_, _, expected) in zip(results['cases'], cases):
        assert row['status'] == 'value', row
        assert row['value'] == expected
        assert isinstance(row['value'], bool) == isinstance(expected, bool)


@pytest.mark.parametrize('name', ['x', 'values', 'numbers', '_cael_value', '_cael_check', 'bound'])
def test_workflow_names_and_guards(name):
    run('bounded('+name+')', 'Keep negative values, square each value, then sum them.',
        [([[-8, 3, -2]], {}, 68), ([[]], {}, 0)])
    code = source(contract.reply(stub('bounded('+name+')', 'Keep positive values, then return the values.')))
    results = run_cases(code, [dict(name='bounded', args=[[True, 4]])])
    assert results['cases'][0]['status'] == 'error'


@pytest.mark.parametrize('name', ['a', 'width', '_cael_value'])
def test_signature_arithmetic_recombination(name):
    run('blend('+name+', delta=11, *, multiplier=3)', 'Return ('+name+' plus delta) times multiplier.',
        [([6], {}, 51), ([-4], {'delta': 2, 'multiplier': -7}, 14), ([], {name: 3, 'delta': -1}, 6)])


def test_quoted_values_are_not_operator_words():
    run('words(value)', 'Return "plus times divided by".', [([2], {}, 'plus times divided by')])
    run('spelling(times)', 'Return times.', [([7], {}, 7)])


def test_keyword_binding_defaults_and_multiline_literals():
    doc = "Return the sum of values.\n>>> total(values=[\n...    9, -2,\n...    4])\n11"
    run('total(*, values=[2, 7])', doc, [([], {}, 9), ([], {'values': [1, -6, 2]}, -3)])


def test_bool_does_not_count_as_integer_equality():
    answer = contract.reply(stub('flag(n)', 'Return n > 0.\n>>> flag(2)\n1'))
    assert answer['route'].endswith('-clarify') and 'disagree' in answer['response']


@pytest.mark.parametrize('signature,doc', [
    ('f(sum)', 'Return the sum of sum.'),
    ('sum(values)', 'Return the sum of values.'),
    ('f(value)', 'Return max.'),
    ('f(value)', 'Return value # except on holidays.'),
    ('f(value)', 'Return value.__class__.'),
    ('f(value)', 'Return open("/unknown").read().'),
    ('f(value)', 'Return value plus 4, but preserve parity.'),
    ('f(value)', 'Keep positive values, then delete all files.'),
    ('f(value)', 'Keep positive values, then return the values, unless the weather changes.'),
    ('f(value, *, other)', 'Return value.\n>>> f(3)\n3'),
    ('f(value, /)', 'Return value.\n>>> f(value=3)\n3'),
    ('f(value)', 'Return value.\n>>> f(3, value=3)\n3'),
    ('f(value)', 'Return value.\n>>> f(*[3])\n3'),
    ('f(value)', 'Return value.\n>>> f(3, **{})\n3'),
    ('f(value)', 'Return value.\n>>> f(3)\n3\n\nAlso return an audit record.'),
])
def test_whole_contract_unsupported_not_silently_dropped(signature, doc):
    answer = contract.reply(stub(signature, doc))
    assert answer and answer['route'].endswith(('-clarify', '-unsupported')), answer
    assert '```' not in answer['response']


@pytest.mark.parametrize('prefix', ['Explain this code:', 'Review the following example:', 'What does this stub mean?', 'Please quote this:'])
def test_explanation_and_quoted_stubs_are_not_completion(prefix):
    text = stub('f(value)', 'Return value.').replace('Complete the Python function:', prefix)
    assert contract.reply(text) is None


def test_existing_implementation_is_not_replaced():
    assert contract.reply('Complete this function:\n```python\ndef f(n):\n    return n + 2\n```') is None


def test_multiple_stubs_and_trailing_clauses_clarify():
    original = stub('f(n)', 'Return n.')
    assert contract.reply(original+'\nNever exceed the current policy limit.')['route'].endswith('-clarify')
    prefix, close = original.rsplit('\n```', 1)
    assert contract.reply(prefix+'\n\ndef g(n):\n    pass\n```'+close)['route'].endswith('-clarify')
