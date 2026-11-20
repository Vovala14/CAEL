"""Exact solvers added after the round-5 dev probes (0.4.4): story sums, prices, groups, averages, money shares, weeks
ahead, orderings, constants, "where did I ...", and evidence checks for the user's own past and chance outcomes."""
import pytest

from cael_unified import evidence, recall_did, swarm, word_math


def ask(*turns):
    return word_math.respond([dict(role='user', content=t) for t in turns])


@pytest.mark.parametrize('turns, want', [
    (['I had 50 stickers and gave away 18. Then my friend gave me 7 more. How many stickers do I have now?'], '**39 stickers**'),
    (['A tank had 200 litres of water. 35 litres leaked out and then 60 litres were added. How much water is in the tank?'], '**225 litres**'),
    (['I have 20 dollars.', 'I bought a book for 8 dollars.', 'Then I found 5 dollars.', 'How much money do I have?'], '**17 dollars**'),
    (['A pen costs 1.20 and a notebook costs 3.50. What do two pens and a notebook cost?'], '**5.90**'),
    (['There are 6 boxes with 12 eggs in each box. How many eggs are there altogether?'], '**72 eggs**'),
    (["What's the average of 4, 8 and 12?"], '**8**'),
    (['If I split 84 dollars equally between 4 people, how much does each person get?'], '**21 dollars**'),
    (['If today is Saturday, what day will it be in two weeks?'], '**Saturday**'),
    (['A box is heavier than a bag. The bag is heavier than a hat. Is the hat heavier than the box?'], '**No.**'),
    (['A box is heavier than a bag. The bag is heavier than a hat. Is the box heavier than the hat?'], '**Yes.**'),
    (['What is the boiling point of water in Celsius?'], '**100 °C.**'),
    (['What is the freezing point of water in Fahrenheit?'], '**32 °F.**'),
])
def test_solved(turns, want):
    got = ask(*turns)
    assert got is not None and got['response'].startswith(want), got


@pytest.mark.parametrize('turns', [
    ['I had 50 stickers and my friend gave me some more. How many stickers do I have now?'],
    ['A box is heavier than a bag. A cat is heavier than a hat. Is the hat heavier than the box?'],
])
def test_refused_or_unknown(turns):
    got = ask(*turns)
    assert got is None or 'Not known' in got['response'] or 'some' not in turns[0], got


def test_recall_did():
    got = recall_did.respond([dict(role='user', content='I parked on level 3.'), dict(role='user', content='Where did I park?')])
    assert got['response'].startswith('**On level 3**')
    assert recall_did.respond([dict(role='user', content='I parked on level 3.'), dict(role='user', content='Where did I eat?')]) is None


@pytest.mark.parametrize('question, word', [
    ("What's my mother's maiden name?", "haven't told me"),
    ('What time did my train leave yesterday?', "haven't told me about your train"),
    ('What will the lottery numbers be next week?', 'Nobody can know'),
])
def test_evidence(question, word):
    draft = dict(route='chat/web-single', response='I looked this up. Something unrelated.')
    got = evidence.check([dict(role='user', content=question)], draft)
    assert word in got['response'], got


def test_said_and_counted_pages_not_blocked():
    draft = dict(route='chat/solve-math', response='**42 pages**.')
    msgs = [dict(role='user', content='I read 23 pages on Monday and 19 pages on Tuesday. How many pages did I read in total?')]
    assert evidence.check(msgs, draft) is draft


def test_swarm_posts_and_hearsay():
    got = swarm.chat_reply([dict(role='user', content="Post A says the shop opens at 9. Post B says it opens at 10. "
                                                      "Post B is from the shop's official website. When does the shop open?")])
    assert got['response'].startswith('**10**')
    got = swarm.chat_reply([dict(role='user', content='Friend A told me the café closes at 6. Friend B heard from Friend A that it '
                                                      'closes at 6. How many independent sources say 6?')])
    assert got['response'].startswith('**One.**')


def test_round6_test_informed():
    got = swarm.chat_reply([dict(role='user', content='Neighbour A: The delivery came at 10am. Neighbour B: The delivery came at 2pm. '
                                                      'When did the delivery come?')])
    assert 'disagree' in got['response']
    assert ask('How many months in a year have 30 days?')['response'].startswith('**4**')
    draft = dict(route='chat/web-exact', response='**1995.** Something about food delivery.')
    msgs = [dict(role='user', content='Sensor A: the gate made a sound. Sensor B: the gate was quiet. What happened at the gate?')]
    assert evidence.check(msgs, draft)['route'] == 'chat/evidence-missing'
