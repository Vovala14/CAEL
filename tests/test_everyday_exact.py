"""Exact everyday readers (everyday_exact.py, 0.4.4, added after an outside blind test: test-informed). The wording here is the
developer's own (research/dev_probes_20261120/probes2.json), not the blind set."""
import pytest

from cael_unified import everyday_exact, advice_schemas, smalltalk


def ask(*turns):
    return everyday_exact.respond([dict(role='user', content=t) for t in turns])


@pytest.mark.parametrize('turns, want', [
    (['Batteries come only in packs of four at $3 a pack. I need 18 batteries. What\'s the cheapest way to get enough, and what does it cost?'], '**$15**'),
    (['The till had $50 in it this morning. We sold a lamp for $22 and a rug for $35, then paid $7 for tape out of the till. How much is in the till now?'], '**$100**'),
    (['Five of us shared a pizza bill equally. I paid the whole $60.', 'Two friends have already paid me their shares. How much do the others still owe me in total?'], '**$24**'),
    (['A printer makes 12 pages a minute while running. It was on for 20 minutes but jammed for 5 of them. How many pages did it print?'], '**180 pages**'),
    (['I picked 30 apples.', 'Sorry, it was 27. Four of them were bruised and went to the compost. My sister picked 15 more.',
      'If we eat 6 of the good ones, how many good apples are left?'], '**32**'),
    (['I made 70 cookies and kept 6 for myself. The rest go into tins of 12. How many full tins can I fill?'], '**5 full tins**'),
    (['I walked 6 km in 90 minutes including a coffee break. What was my average speed in km per hour?'], '**4 km/h**'),
    (['The parcel weighs 2.4 kg in its box. The empty box weighs 300 g. How many grams is the contents?'], '**2,100 g**'),
    (['The shelf space is 80 cm wide.', 'My vase is 650 mm wide and needs 40 mm of clearance on each side. How many millimetres are left over?'], '**70 mm**'),
    (['The night train leaves at 10:40 pm and arrives at 1:05 am. How many minutes is the journey?'], '**145 minutes**'),
    (['City X is 3 hours behind City Y. A call is set for Monday at 01:30 in City Y. What day and time is that in City X?'], '**Sunday at 22:30**'),
    (['The bread went in at 14:20 for 50 minutes.', 'Then I added another 10 minutes. When does it come out?'], '**15:20**'),
    (["The magazine's spring issue came out in October 2022. The next one is four calendar months later. Which month and year is that?"], '**February 2023**'),
    (['Suppose today is 3 January 2021. I posted the letter the day before yesterday. What date was that?'], '**1 January 2021**'),
    (['Omar was born on 20 May 1990. How old was he on 19 May 2020?'], '**29**'),
    (['The shop opened on a Monday. The sale starts two weeks and three days later. What weekday is that?'], '**Thursday**'),
    (["On my calendar the 5th is a Friday. What's the date of the following Tuesday?"], '**9**'),
    (['Was 1900 a leap year in the Gregorian calendar?'], '**No.**'),
    (['Every guest at the gala wore a badge. This man wore no badge. Could he have been a guest at the gala?'], '**No.**'),
    (['Anna finished before Carl. Beth also finished before Carl. Who finished first, Anna or Beth?'], "**No, it can't be worked out.**"),
    (["Three books on a shelf: the atlas is to the left of the novel, and the dictionary sits between them. Left to right, what's the order?"], '**atlas, dictionary, novel**'),
    (['Exactly one of the two lamps, X and Y, is lit. Lamp X is dark. Is Y lit?'], '**Yes.**'),
    (['Only staff can open the vault. Sam is staff. Does that prove Sam opened the vault?'], '**No.**'),
    (['When the typed list and a handwritten note disagree, go with the typed list.', 'Handwritten note: 12 chairs. Typed list: 15 chairs. How many chairs do we record?'], '**15 chairs**'),
    (['Witness Green said the car was red. Witness Gray said it was blue.', "Green has withdrawn that statement. Which witness's claim still stands, and what is it?"], '**Witness Gray**'),
    (['Sheet A: the train left at 09:14. Sheet B: the train left at 09:30.', 'Correction to Sheet A: it should read 09:41. What time does Sheet A now give?'], '**09:41**'),
    (['Report East says the alarm sounded three times. Report West says four times.', 'West has corrected its entry to three. How many times do the reports now agree it sounded?'], '**Three times**'),
    (["Note 1 says the party is on the roof. Note 2 says it's in the garden. Both are about the same party and neither is more reliable. Where is the party?"], "**They don't establish one.**"),
    (['Post X: I saw 7 deer by the lake. Post Y: Post X saw seven deer. Post Z: I was at the lake and saw 9 deer. How many firsthand counts are there?'], '**Two**'),
    (['I bought a wool hat at the fair.', "It's grey with a red stripe.", 'How much did I say it cost?'], "**You didn't tell me**"),
    (['I borrowed a ladder from my neighbour.', 'He needs it back by Friday. Who needs the ladder back?'], '**Your neighbour**'),
    (['I\'ll call the blue notebook Alpha.', 'No wait, call it Beta. Alpha is for the red one.', "What's the blue notebook called?"], '**Beta**'),
    (['My cousins are Mara and Marla. Mara plays violin; Marla plays drums.', "I'm calling Marla. Which instrument should I ask about?"], '**Drums**'),
    (['My dentist appointment is on Tuesday.', 'They offered me Thursday instead.', 'I said no. Which day is my appointment?'], '**The Tuesday**'),
    (['I rolled a die behind a screen. What number is showing?'], "**There's no way to know**"),
    (["Which sea lies along Austria's coast?"], '**None: Austria is landlocked**'),
    (['The jar held exactly five marbles. I took all five out. What colour is the marble left in the jar?'], "**There isn't one.**"),
    (["I'm thinking of a number from 1 to 10. It's even. Which number is it?"], "**I can't tell exactly**"),
    (['We\'re holding a garden party next August. How many people will come?'], '**Nobody can know that in advance.**'),
])
def test_reads(turns, want):
    got = ask(*turns)
    assert got is not None and got['response'].startswith(want), got


@pytest.mark.parametrize('turns', [
    ['I had 50 stickers and gave away 18. Then my friend gave me 7 more. How many stickers do I have now?'],          # word_math's
    ['Report 1: The bridge is closed. Report 2: The bridge is closed. Report 3 just repeats Report 1. How many independent reports say the bridge is closed?'],
    ['How do I get my sourdough to rise more?'],
    ['A car travels at 60 km/h for 2 hours. How far does it go?'],
    ['Hello there!'],
])
def test_leaves_other_shapes_alone(turns):
    assert ask(*turns) is None


def test_value_questions_get_no_advice_template():
    msgs = [dict(role='user', content='I lined up three jars. The jam is somewhere left of the honey.'),
            dict(role='user', content="The lemon curd is between them. Reading left to right, what's the lineup?")]
    assert advice_schemas.respond(msgs) is None


def test_questions_are_not_small_talk_about_an_activity():
    got = smalltalk.reply([dict(role='user', content="I'm writing to Liana. Which collection should I ask about?")])
    assert got is None or not got['route'].endswith('activity')
