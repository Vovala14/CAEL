"""Independent boundaries, no final benchmark inputs."""
import pytest
from cael_unified import output_contract
from cael_unified.choice_helpers import arithmetic


@pytest.mark.parametrize('text', [
    'Example:\nReturn only the number.',
    'The quoted phrase says:\nReturn only the letter.',
    'Explain the sentence "Return only the number."',
    '```python\nx = "Reply briefly"\n```\nReturn only the number.',
    'What is 2+3?\nReturn only the number and explain everything.',
    'Return a JSON object.\nWhat is 2+3?',
    'Please tell me what a letter is.',
])
def test_does_not_erase_data_or_extra_requirements(text):
    assert output_contract.read(text) is None


def test_full_body_and_negation_are_preserved():
    body = 'Take 19, not 17, and multiply it by 4. Do not subtract anything.'
    assert output_contract.read(body+'\nReply with only the number.') == dict(kind='number', body=body)


def test_no_scalar_fabrication():
    reply = dict(route='chat/talk-unsure', response='I do not know; 42 was only an example.')
    got = output_contract.apply(reply, dict(kind='number', body='Question'))
    assert got['response'] == reply['response'] and got['format_unavailable']


def test_boolean_is_not_a_choice_index():
    assert output_contract.value(dict(choice=True, route='unknown', response='Unknown')) == (None, None)


@pytest.mark.parametrize('a,b,index', [(a,b,i) for a,b in [(-6,7),(3,11),(18,4),(0,13),(19,9)] for i in range(4)])
def test_arithmetic_choices_are_computed_not_fixed_to_a_position(a,b,index):
    result = a*b
    options = [str(result+v) for v in (1,2,3)]
    options.insert(index, str(result))
    reply = arithmetic(f'Which value equals {a} * {b}?', options)
    assert reply['choice'] == index and reply['verification']['status'] == 'verified'


def test_non_unique_or_non_numeric_options_do_not_become_verified():
    assert arithmetic('Which value equals 2*3?', ['6', '6']) is None
    assert arithmetic('Which value equals 2*3?', ['6 maybe', '7']) is None


def test_conflicting_contracts_are_detected():
    assert output_contract.read('Return only the number.\nWhat is 7+3?\nReturn only the letter.')['kind'] == 'conflict'
