"""story_math.py: multi-step word problems read as a story of operations (2026-11-22). Development problems written for
this reader; none comes from a benchmark."""
import pytest

from cael_unified import story_math as M


def head(*turns):
    r = M.respond([dict(role='user', content=t) for t in turns])
    return r and r['response'].split('**')[1].rstrip('.')


@pytest.mark.parametrize('turns,want', [
    (('A bucket holds 3 litres. For five minutes a hose adds 2 litres a minute while a crack leaks half a litre a minute. How many litres are in the bucket now?',), '10.5 litres'),
    (('A jacket is marked £120. There is 30% off, then a £4 delivery charge. How much do I pay?',), '£88'),
    (('A coat costs $90. It has 20% off and then a $6 delivery fee.', 'I have a $100 gift card. What balance is left?'), '$22'),
    (('Our club sold 40 raffle tickets at £2 each. The venue takes a quarter. We split the rest equally between four volunteers. How much does each volunteer get?',), '£15'),
    (('I mix 2 litres of lemonade with 500 ml of syrup and keep back 300 ml. Each glass gets 200 ml. How many glasses can I pour?',), '11'),
    (('Rice costs £2 per kilo and beans cost £6 per kilo. I bought 1.5 kg of rice and 500 g of beans. How much did I spend?',), '£6'),
    (('A 2 metre plank is cut into four equal pieces. I sand 2 cm off each end of each piece. How many centimetres of wood are left across all four?',), '184 cm'),
    (('A shop sells 12 mugs at $5 each and then gives away $10 in refunds. How much money did it take in total?',), '$50'),
    (('A pool has 500 litres in it. For 20 minutes a pump removes 8 litres a minute. How many litres remain?',), '340 litres'),
    (('We bought 6 tickets at $15 each and paid a $3 booking fee. I paid with a $100 note. How much change do I get?',), '$7'),
    (('Tickets cost $15 each and we bought 6 tickets. How much did we pay?',), '$90'),
    (('A band earned £600 from a gig. The agent takes 10%. The rest is shared equally among 3 members. How much does each member get?',), '£180'),
    (('Cheese costs £12 per kilo and ham costs £18 per kilo. I buy 250 g of cheese and 200 g of ham. How much do I pay?',), '£6.60'),
    (('I make soup with three 400 ml cans of stock and 300 ml of milk. I set aside 100 ml. If each bowl gets 250 ml, how many bowls can I fill?',), '5'),
    (('A tank has 60 litres. A leak loses 2 litres an hour for 5 hours. How much is left?',), '50 litres'),
])
def test_story(turns, want):
    assert head(*turns) == want


@pytest.mark.parametrize('turns', [
    ('A train leaves at 09:10 and takes 2 hours. When does it arrive? How much later is that?',),
    ('I have 3 cats and 2 dogs and my house is 40 years old. How much do the pets eat?',),
    ('What is 5 + 5?',),
    ('A class of 30 pupils goes on a trip. How much does it cost?',),
    ('I have £20 and buy 3 pens. How much change?',),
])
def test_silent(turns):
    assert M.respond([dict(role='user', content=t) for t in turns]) is None
