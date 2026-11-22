"""everyday_choice.py: options, passes, smallest unused numbers and per-batch rounding (2026-11-22). Development problems."""
import pytest

from cael_unified import everyday_choice as C


def head(*turns):
    r = C.respond([dict(role='user', content=t) for t in turns])
    return r and r['response'].split('**')[1].rstrip('.')


@pytest.mark.parametrize('turns,want', [
    (('My bike needs a 26 inch tyre with a tubeless rim fit. The shop has a 26 inch standard tyre, a 28 inch tubeless tyre and a 26 inch tubeless tyre.',
      'Which one fits both requirements?'), 'The 26 inch tubeless tyre'),
    (('I need a charger that is 65 W and USB-C. They sell a 45 W USB-C charger, a 65 W USB-C charger and a 65 W barrel charger.', 'Which one should I buy?'),
     'The 65 W USB-C charger'),
    (('Yoga is £8 per class, or £50 for a monthly pass. I plan to go 5 times this month. Which is cheaper?',), 'Paying each time, by £10'),
    (('Swimming costs $4 per swim or $30 for a monthly pass. I swim 10 times a month. Which is the better deal?',), 'The pass, by $10'),
    (('The deli gives out the smallest free ticket number. Numbers 1, 3 and 4 are in use. Someone hands back 1. Which number do I get?',), '1'),
    (('The deli gives out the smallest free ticket number. Numbers 1, 2 and 3 are in use. Which number do I get?',), '4'),
    (('My printer uses one sheet for every two pages, and each document starts on a fresh sheet. I print a 5-page report and a 7-page essay.',
      'How many sheets do I need?'), '7 sheets'),
])
def test_choice(turns, want):
    assert head(*turns) == want


@pytest.mark.parametrize('turns', [
    ('Which one is the best phone?',),
    ('The cafe has a latte, a mocha and a tea. Which one should I get?',),
])
def test_silent(turns):
    assert C.respond([dict(role='user', content=t) for t in turns]) is None
