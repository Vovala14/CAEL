"""Presentation, negative routing, and safe 2..8-label controller boundaries."""
import pytest

from cael_unified import choice_helpers, task_context
from cael_unified.assistant import Assistant


@pytest.mark.parametrize('count', range(2, 9))
@pytest.mark.parametrize('layout', ['line', 'paren', 'bracket', 'inline'])
def test_all_positions_exact_helper_and_labels(count, layout):
    for correct in range(count):
        labels = 'ABCDEFGH'[:count]
        options = [str(81+i) for i in range(count)]
        options[correct] = '72'
        render = lambda label, value: {'line':label+') '+value, 'paren':'('+label+') '+value,
                                       'bracket':'['+label+'] '+value, 'inline':label+'. '+value}[layout]
        question = 'Which number equals 18 * 4?'+ (' ' if layout=='inline' else '\n') + (' ' if layout=='inline' else '\n').join(render(label, value) for label, value in zip(labels, options))
        parsed = task_context.read(question)
        assert parsed['kind'] == 'choice'
        assert parsed['options'] == options
        answer = choice_helpers.reply(parsed['context'], options)
        assert answer['choice'] == correct
        assert answer['response'] == labels[correct]+'. 72'


@pytest.mark.parametrize('text', [
    'Quote this question: Which is correct? A) red B) blue',
    'Write a prompt where someone chooses which sign to paint:\nA) spring\nB) winter',
    'Make an image prompt. Which layout is in the picture?\nA) sunrise\nB) sunset',
    'Explain the examples: Which case?\nA) first\nB) last',
    'What does this source mean?\n```python\ntext = "A) red B) blue"\n```',
    'Please translate "Which is correct? A) red B) blue" into French.',
    'What does "A) red B) blue" mean?',
])
def test_code_quotes_and_other_purposes_remain_owned_by_their_routes(text):
    assert task_context.read(text) is None


@pytest.mark.parametrize('labels', [('A','C'), ('B','C'), ('A','B','B'), tuple('ABCDEFGHI')])
def test_broken_label_sequence_not_accepted(labels):
    text = 'Which is correct?\n'+'\n'.join(label+') '+str(i) for i, label in enumerate(labels))
    value = task_context.read(text)
    # A ninth unknown label must not be silently ignored as an answer suffix.
    assert value is None or value['kind'] == 'invalid'


def test_every_semantic_clause_and_option_is_preserved():
    context = 'Facts: Support is before Image. Image is before Paint. Which item comes last?'
    options = ['Support', 'Image', 'Paint']
    value = task_context.read(context+'\nA) Support\nB) Image\nC) Paint')
    assert value['context'] == context and value['options'] == options
    answer = choice_helpers.reply(context, options)
    assert answer['choice'] == 2


def test_duplicate_options_have_no_unique_label():
    value = task_context.read('Which value?\nA) RED\nB) red')
    assert value['kind'] == 'invalid' and 'same' in value['message']


def test_more_than_four_never_call_protected_four_choice_controllers(monkeypatch):
    from cael_unified import symbolic_choice
    monkeypatch.setattr(choice_helpers, 'reply', lambda *a, **k: None)
    def forbidden(*args, **kwargs):
        raise AssertionError('A-D-only controller called for extra labels')
    monkeypatch.setattr(symbolic_choice, 'reply', forbidden)
    assistant = object.__new__(Assistant)
    assistant._reasoning = object()
    assistant.score_endings = lambda context, endings: [dict(sum_lnp=i, tokens=1) for i in range(len(endings))]
    assistant.choice_settings = forbidden
    answer = assistant._context_choice('Question with unfamiliar options?', list('abcdefgh'))
    assert answer['choice'] == 7 and answer['response'] == 'H. h'
    assert 'Statistical' in answer['details']


def test_unrecognized_question_does_not_delete_unfamiliar_words():
    context = 'Which report is the wistful image that supports a painter according to a local custom?'
    parsed = task_context.read(context+'\nA) frosty\nB) warm')
    assert parsed['context'] == context
    assert choice_helpers.reply(context, parsed['options']) is None
