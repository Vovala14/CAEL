"""Think-first swarm (think.py): readings × exact readers, each proposal checked, then a vote."""
from fractions import Fraction

from cael_unified import think


def run(*turns):
    return think.run([dict(role='user', content=t) for t in turns])


def test_derivation_search_counts_used_numbers():
    nums = [Fraction(50), Fraction(18), Fraction(7)]
    assert think.best_derivation(Fraction(39), nums) == 3
    assert think.best_derivation(Fraction(57), nums) == 2
    assert think.best_derivation(Fraction(1000), nums) == 0


def test_question_types():
    assert think.qtype('How many apples are left?') == 'number'
    assert think.qtype('What time should I take it off?') == 'time'
    assert think.qtype('Which weekday is that?') == 'weekday'
    assert think.qtype('Is B on?') == 'yesno'


def test_story_sum_is_checked_and_answered():
    got = run('I had 50 stickers and gave away 18. Then my friend gave me 7 more. How many stickers do I have now?')
    assert got is not None and got['response'].startswith('**39')
    assert 'all 3 stated numbers' in got['details']


def test_everyday_reader_answers_with_trace():
    got = run('The shop opened on a Monday. The sale starts two weeks and three days later. What weekday is that?')
    assert got['response'].startswith('**Thursday**')
    assert got['think']['question_type'] == 'weekday'


def test_nothing_checked_falls_through():
    assert run('How do I get my sourdough to rise more?') is None
    assert run('Hello there!') is None
