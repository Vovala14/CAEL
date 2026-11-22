"""number_puzzle.py: number and code puzzles by trying every candidate (2026-11-22). Development problems."""
import pytest

from cael_unified import number_puzzle as P


def head(*turns):
    r = P.respond([dict(role='user', content=t) for t in turns])
    return r and r['response'].split('**')[1].rstrip('.')


@pytest.mark.parametrize('turns,want', [
    (('My locker has a two-digit code. The digits are different and add up to nine. The first digit is twice the second. What code fits?',), '63'),
    (('I am thinking of a whole number. It is greater than 20 and less than 30. It is a multiple of 9. What number is it?',), '27'),
    (('I picked an integer. It is more than 12. It is less than 10. Which integer did I pick?',), 'None'),
    (('A three-digit number has all digits the same, and the sum of its digits is 12. What number is it?',), '444'),
    (('My number is odd and between 10 and 16. What number could it be?',), "It can't be pinned down"),
])
def test_puzzles(turns, want):
    assert head(*turns) == want


def test_silent():
    assert P.respond([dict(role='user', content='What number should I call for a taxi?')]) is None
