from cael_unified import question_math as Q


def ans(text):
    r = Q.reply(text)
    return r and r['response'].split('**')[1]


def test_difference_ignores_extra_numbers():
    t = ('There are 41 bird families near the mountain. 35 bird families flew away to asia and 62 bird families flew '
         'away to africa. How many more bird families flew away to africa than those that flew away to asia?')
    assert ans(t) == '27'


def test_each_count_and_total():
    assert ans('Each seat can hold 9 people. If 18 people can ride the wheel at the same time. How many seats are there?') == '2'
    assert ans('There are 270 students in a school with 5 students in each grade. How many grades are there?') == '54'


def test_relation_total():
    t = 'Zachary did 44 push-ups. David did 58 more push-ups than Zachary. How many push-ups did Zachary and David do altogether?'
    assert ans(t) == '146'


def test_stays_silent_on_unreliable_or_inverse_shapes():
    assert Q.reply('Kelly has 22 games. How many does she need to buy so that she will have 140 games?') is None
    assert Q.reply('79 animals were in the cage. 24 snakes and 51 alligators were hiding. How many animals were not hiding?') is None
    assert Q.reply('How many days are in a week?') is None
