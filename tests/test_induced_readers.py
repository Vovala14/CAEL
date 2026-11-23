"""induced_readers.py: readers learned by tools/induce.py from verified examples (2026-11-22). The problems here use new
numbers and names, in wordings the generator uses."""
import pytest

from cael_unified import induced_readers as IR


def ask(text):
    r = IR.respond([dict(role='user', content=text)])
    return r and r['response'].split('**')[1].rstrip('.')


def test_rules_load():
    assert len(IR.readers()) >= 20


@pytest.mark.parametrize('text,want', [
    ('I worked from 08:15 to 16:45 with an unpaid 30-minute break. I am paid £20.00 per hour. How much did I earn?', '£160'),
    ('My shift runs from 07:40 to 15:10 with a 30-minute break. How long do I actually work?', '7 h 0 min'),
    ('A recipe for 4 people needs 200 g of oats. How much oats for 6 people?', '300 g'),
    ('Which weekday is March 3, 2021?', 'Wednesday'),
])
def test_learned_answers(text, want):
    assert ask(text) == want


def test_silent_on_other_questions():
    assert IR.respond([dict(role='user', content='What is the capital of France?')]) is None
    assert IR.respond([dict(role='user', content='I worked hard today. How are you?')]) is None
