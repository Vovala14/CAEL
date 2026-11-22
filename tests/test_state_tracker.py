"""state_tracker.py: lists, statuses and values that change over a conversation (2026-11-22). Development problems
written for this tracker."""
import pytest

from cael_unified import state_tracker as S


def head(*turns):
    r = S.respond([dict(role='user', content=t) for t in turns])
    return r and r['response'].split('**')[1].rstrip('.')


@pytest.mark.parametrize('turns,want', [
    (('The playlist starts with the calm song, then the loud one.', 'Add the slow song at the start.', 'Which song is last?'), 'The loud song'),
    (('Tonight we serve the green tea first, then the black one, then the white one.', 'Swap the green and the white.',
      'Which tea is first now?'), 'The white tea'),
    (('I am tracking chores. Washing and ironing are done; cooking is not.', 'Actually I have to redo the ironing.', 'Cooking is finished now.',
      'Which chores are done?'), 'washing and cooking'),
    (('Kim and Lou have paid for the trip, but Max has not.', 'The bus is blue.', 'Lou cancelled and got a refund.', 'Who still has not paid?'),
     'Lou and Max'),
    (("Mia's drink is tea; Leo's is coffee.", 'Mia and Leo swapped drinks.', 'Whose drink is tea now?'), "Leo's"),
])
def test_state(turns, want):
    assert head(*turns) == want


@pytest.mark.parametrize('turns', [
    ('Which song is the best?',),
    ('Ann is not happy and Ben is tired. Who is done?',),
])
def test_silent(turns):
    assert S.respond([dict(role='user', content=t) for t in turns]) is None


@pytest.mark.parametrize('turns,want', [
    (('For the delivery, leave it at the front door.', 'Actually, leave it with my neighbour at number 5.', 'What should I tell the driver?'),
     'Leave it with my neighbour at number 5'),
    (('Feed the cat at 8 am.', 'Use the blue bowl.', 'Change of plan: feed her at 9 am instead. Do not use the blue bowl, it is cracked.',
      'What instructions should I give the sitter?'), 'Feed her at 9 am instead'),
])
def test_latest_instruction(turns, want):
    assert head(*turns) == want
