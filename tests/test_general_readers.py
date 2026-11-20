"""General readers (0.4.4): constraint_logic, everyday_more, explain_more. Developer's own wording
(research/dev_probes_20261120/probes3.json and probes4.json), not a test set."""
import pytest

from cael_unified import constraint_logic, everyday_more, explain_more, think


def msgs(*turns):
    return [dict(role='user', content=t) for t in turns]


@pytest.mark.parametrize('turns, want', [
    (['Five friends stand in a queue. Ana is first. Ben is directly behind Ana. Cleo is last. Dev is not next to Cleo. Where is Eli?'], '**Eli is fourth.**'),
    (['Three people sit in a row: Kim, Lou and Max. Kim is not at either end. Lou is to the right of Max. Who sits on the left end?'], '**Max.**'),
    (['In a queue: Dan is in front of Eva. Fay is behind Eva. Gus is first. Who is last?'], '**Fay.**'),
    (['Liam finished before Mia but after Noah. Olga finished after Mia. Who finished last?'], '**Olga.**'),
    (['Four cars are parked in a row. The red car is at the left end. The blue car is next to the red one. The green car is not at the right end. '
      'Which car is at the right end, if the fourth car is white?'], '**White.**'),
    (['If the alarm goes off, the dog barks. The dog didn\'t bark. Did the alarm go off?'], '**No.**'),
    (['All my mugs are blue. This cup is red. Is it one of my mugs?'], '**No.**'),
])
def test_constraints(turns, want):
    got = constraint_logic.respond(msgs(*turns))
    assert got is not None and got['response'].startswith(want), got


@pytest.mark.parametrize('turns, want', [
    (["I'm trying to work out the bill: 3 coffees at $2.50 each and 2 muffins at $3.20 each. I pay with a $20 note. How much change should I get?"], '**$6.10**'),
    (['Pack A has 500 g of rice for $3.50. Pack B has 750 g for $4.80. Which is cheaper per gram?'], '**Pack B**'),
    (['A shirt is $40. It\'s discounted by 20%, and then I pay 10% sales tax on the discounted price. What\'s the total?'], '**$35.20**'),
    (['We have 3 pizzas cut into 8 slices each. If 5 people each eat 4 slices, how many slices are left?'], '**4**'),
    (["My watering can holds 9 litres. It's two thirds full. How much water is in it?"], '**6 litres**'),
    (['How many days are there from 3 March 2023 to 17 April 2023?'], '**45 days**'),
    (['What day of the week was 1 January 2000?'], '**Saturday.**'),
    (['My gym membership started on 31 January 2023 and lasts 1 month. On what date does it end?'], '**28 February 2023**'),
    (['Work starts at 08:45 and finishes at 17:15 with a 45-minute lunch. How long do I actually work?'], '**7 hours 45 minutes**'),
    (['If someone was born in 2001, how old will they be at the end of 2030?'], '**29**'),
    (['Jon said the bus is number 12. Kate said it\'s number 14. Later Jon admitted he was wrong.', 'Which bus number do we have now?'], '**14**'),
    (['One clock says 4:10 and another says 4:25. I don\'t know which one is right. What time is it?'], "**I can't tell which is right**"),
    (['My seat is 14C.', 'The coffee here is nice.', 'They changed my seat to 22A.', "What's my seat?"], '**22A**'),
    (['The appointment is at 10 am.', 'I need to bring my card.', 'The appointment was moved forward by 30 minutes.', 'When is the appointment?'], '**9:30 am**'),
    (['I have a guitar, a violin and a flute.', 'I sold the violin.', 'I was given a drum.', 'Which instruments do I have now?'], '**guitar, flute and drum.**'),
    (['A plane takes off at 14:00. When does it land?'], "**I can't tell from that**"),
    (['What did Shakespeare post on Twitter?'], '**That rests on a false premise**'),
    (['A cinema ticket is $12, or a 5-film card costs $50. I\'ll see 5 films. Which should I buy?'], '**The 5-film card**'),
    (["The lift's limit is 600 kg. Six people of 85 kg each get in with a 70 kg trolley. Are they over the limit?"], '**No**'),
])
def test_everyday_more(turns, want):
    got = think.run(msgs(*turns))
    assert got is not None and got['response'].startswith(want), got


@pytest.mark.parametrize('q, start', [
    ("What's the difference between affect and effect?", '"Affect"'),
    ('Why does a spoon in a glass of water look bent?', 'Refraction.'),
    ("Why is it called a 'leap' year?", 'In an ordinary year'),
])
def test_explanations(q, start):
    got = explain_more.respond(msgs(q))
    assert got is not None and got['response'].startswith(start)


@pytest.mark.parametrize('q', ['How does salt affect the effect of ice on roads near my house?', 'Why is my car making a noise?', 'Hello!'])
def test_explanations_leave_others(q):
    got = explain_more.respond(msgs(q))
    assert got is None or not got['response'].startswith('"Affect"')
