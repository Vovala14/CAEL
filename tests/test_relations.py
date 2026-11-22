"""relations.py: the general relation reader (2026-11-22). Development problems written for this reader, in varied
wording; none are taken from a benchmark set."""
import pytest

from cael_unified import relations as R


def ask(*turns):
    r = R.respond([dict(role='user', content=t) for t in turns])
    return r and r['response']


def head(*turns):
    r = ask(*turns)
    return r and r.split('**')[1].rstrip('.').rstrip(':')


@pytest.mark.parametrize('turns,want', [
    # schedules
    (('Three chores: laundry, dishes and vacuuming. Dishes have to be done before laundry. Vacuuming comes last.',
      'Which chore is first?'), 'dishes'),
    (('I need to do the tasks prime, sand and varnish. Varnish must come directly after sand, and prime has to happen before varnish.',
      'Can prime be the last task?'), 'No'),
    (('I need to do the tasks prime, sand and varnish. Varnish must come directly after sand, and prime has to happen before varnish.',
      'Could sand go first?'), 'No'),
    (('Our meeting has four talks: budget, hiring, roadmap and safety. Safety opens the meeting. Roadmap is followed immediately by budget. '
      'Hiring is not last.', 'What is the order of the talks?'), 'safety, hiring, roadmap, budget'),
    (('Steps: mix, bake, cool and ice. Bake comes right after mix. Cool happens after bake but before ice. Mix is not first.',
      'How many orders are possible?'), '0'),
    (('Steps: mix, bake, cool and ice. Bake comes right after mix. Cool happens after bake but before ice.',
      'How many orders are possible?'), '1'),
    (('We visit the museum, the park and the zoo. The zoo can\'t be first. The park is visited sometime after the museum.',
      'Must the museum be first?'), 'Yes, it has to'),
    (('We visit the museum, the park and the zoo. The zoo cannot be first.',
      'Must the museum be first?'), 'No, not necessarily'),
    # people in a line or a race
    (('Ava, Ben, Cleo and Dan finished a race. Ava beat Dan. Cleo finished right behind Ben. Ben won.',
      'Who came last?'), 'Dan'),
    (('Five people queue: Pia, Quin, Rosa, Sam and Tess. Tess is at the front. Sam is directly behind Pia. Rosa is last. Quin is fourth.',
      'Where is Pia?'), 'Pia is second'),
    (('Lia, Mo and Nell stand in a row. Mo is not next to Lia.', 'Who is in the middle?'), 'Nell'),
    (('Lia, Mo and Nell stand in a row. Lia is to the left of Nell.', 'Who is on the far left?'), "It can't be determined"),
    (('Kai, Lu and Max finished a race. Kai finished before Lu but after Max.', 'Who was second?'), 'Kai'),
    (('Kai, Lu and Max are in a queue. Lu is two places behind Max.', 'Who is in the middle?'), 'Kai'),
    # corrections
    (('Our talks are art, bio and chem. Art is before bio. Chem is last.', 'Actually, bio is before art.', 'Which talk is first?'), 'bio'),
    # hypotheticals
    (('Ivy, Jo, Kim and Lee sit in a row of four seats. Jo sits next to Kim. Ivy is at one end.', 'If Lee is in seat 2, who is in seat 1?'), 'Ivy'),
    # a ring
    (('Ana, Bo, Cy and Di sit at a round table. Ana sits opposite Bo. Cy is next to Ana.', 'Who sits opposite Cy?'), 'Di'),
    (('Ana, Bo, Cy and Di sit at a round table.', 'Ana sits opposite Bo.', 'Is Cy next to Di?'), 'No'),
])
def test_line_and_ring(turns, want):
    assert head(*turns) == want


@pytest.mark.parametrize('turns,want', [
    (('Ann, Ben and Cara each have a different pet: a cat, a dog and a fish. Ann does not have the dog. Ben has the fish.',
      'Who has the cat?'), 'Ann'),
    (('Ann, Ben and Cara each have a different pet: a cat, a dog and a fish. Ann does not have the dog. Ben has the fish.',
      'What pet does Cara have?'), 'dog'),
    (('Three friends, Raj, Sue and Tom, each drink one of tea, coffee and juice. Sue drinks neither tea nor juice. Tom does not drink tea.',
      'What does Raj drink?'), 'tea'),
    (('Three friends, Raj, Sue and Tom, each drink one of tea, coffee and juice. Tom does not drink tea.',
      'Who drinks coffee?'), "It can't be determined"),
])
def test_matching(turns, want):
    assert head(*turns) == want


@pytest.mark.parametrize('turns', [
    ('What is the capital of France?',),
    ('I bought apples, pears and plums. Which is the healthiest?',),
    ('Ann, Ben and Cara went to the park. Ann is taller than Ben. Who is the tallest?',),
    ('My tasks are email, gym and shopping. Gym must be in the morning unless it rains. Which task is first?',),
])
def test_silent(turns):
    assert ask(*turns) is None


from cael_unified import staffing as S


@pytest.mark.parametrize('text,want', [
    ('We need a driver, a cook and a guide for the trip. Sam can only drive. Tia cannot cook. Uri can do any of them. Who is the cook?', 'Uri'),
    ('We need a driver, a cook and a guide for the trip. Sam can only drive. Tia cannot cook. Uri can do any of them. What does Tia do?', 'Tia: guide'),
    ('The shop needs a cashier and a baker on Sunday. Ola can only bake. Pim can do both. Raf is away on Sunday. Who is the cashier?', 'Pim'),
])
def test_staffing(text, want):
    r = S.respond([dict(role='user', content=text)])
    assert r and r['response'].split('**')[1].rstrip('.') == want
