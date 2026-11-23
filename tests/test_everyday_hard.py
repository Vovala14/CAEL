"""everyday_hard.py and the 2026-11-22 fixes (test-informed). The wordings here are not the hard-check items: they check
that each reader reads its shape in other words, and that it stays silent on look-alike questions."""
import re

from cael_unified import constraint_logic, everyday_exact, everyday_hard as eh, explain_more


def ask(*turns):
    return eh.respond([dict(role='user', content=t) for t in turns])


def head(reply):
    assert reply is not None
    m = re.search(r'\*\*(.+?)\*\*', reply['response'])
    return (m[1] if m else reply['response']).strip()


def test_sums():
    assert head(ask('A scanner does 30 pages per minute and rests for 1 minute after every 90 pages. How long for a 200-page batch?')) == '8.67 minutes' or \
        head(ask('A scanner does 30 pages per minute and rests for 1 minute after every 90 pages. How long for a 200-page batch?')).startswith('8.6')
    assert head(ask('Seats are $20 each plus a $3 service charge per booking. I booked 2 seats, then made another booking for 1 more. How much did I spend?')) == '$66'
    assert head(ask('There are 4 bags of 15 sweets and 3 loose sweets. I share them equally among 6 kids, as many each as possible. How many are left over?')) == '3'
    assert head(ask('A cake for 8 people uses 400 g of flour. I am baking for 12, and flour is sold in 250 g bags. How many bags do I need?')) == '3 bags'
    assert head(ask('Tap A fills the bath in 10 minutes and tap B in 15 minutes. How long with both together?')) == '6 minutes'
    assert head(ask('Five of us shared a £50 cab. Zoe got out halfway. First half split five ways, second half four ways. How much does Zoe pay?')) == '£5'


def test_calendar():
    assert head(ask('Yoga is every Monday and Thursday, starting Monday 6 January 2025, for 4 sessions. What is the date of the last session?')) == 'Thursday 16 January 2025'
    assert head(ask('A train leaves Lisbon at 09:00 (UTC+0) and the journey takes 3 hours. Madrid is on UTC+1. What time is it in Madrid when it arrives?')) == '13:00'
    assert head(ask('How many working days are there from Monday 1 December 2025 to Friday 12 December 2025, counting both ends?')) == '10'
    assert head(ask('My shift runs from 23:00 to 07:00 with a 60-minute unpaid break, paid $20 an hour. How much is the shift worth?')) == '$140'
    got = ask('The meeting is at 09:00 Tokyo time. My partner is in Sydney, two hours ahead of Tokyo. What time is it for my partner?')
    assert got and '11:00' in got['response']


def test_puzzles():
    assert head(ask('Ann, Bea and Cal each wear one different hat: red, blue and green. Ann wears neither the red nor the blue. Cal wears the red. Who wears the blue?')) == 'Bea.'
    assert head(ask('With a 2-litre jug and a 7-litre jug, what is the fewest number of steps to measure exactly 3 litres in the 7-litre jug?')).endswith('steps')
    assert head(ask('A two-digit number has digits that add up to 9, and the tens digit is twice the units digit. What is the number?')) == '63'
    race = constraint_logic.respond([dict(role='user', content='Four horses ran. Bolt won. Comet finished last. Dash beat Echo. Who came second?')])
    assert race and 'Dash' in race['response']


def test_memory():
    assert head(ask('Order: Ian wants pizza, Jo wants pasta.', 'Jo switched; she will have pizza too.', 'How many pizzas and how many pastas?')) == '2 pizzas and 0 pastas'
    assert head(ask('To-do list: laundry, dishes, emails.', 'I did the dishes, so cross them off. Add groceries.', "What's left?")).lower() == 'laundry, emails and groceries'
    assert head(ask('My bike lock code is 1200.', 'I changed it: the number is 34 higher.', "What's my bike lock code now?")) == '1234'
    assert head(ask('We booked table 4 for 8 pm.', 'They moved us to table 9.', 'Then they pushed the time back by an hour.', 'What table and time do we have?')) == 'Table 9 at 9:00 pm'
    assert head(ask('I lent Kai $50.', 'Kai paid back $20.', 'How much does Kai owe?')) == '$30'
    assert head(ask('The match is the Saturday after next.', 'Today is Sunday 2 March 2025. What is the date of the match?')) == 'Saturday 15 March 2025'
    assert head(ask('Week 1 is Ana, week 2 is Ben.', 'We swapped week 1 and week 2.', 'Who is on in week 1?')) == 'Ben'


def test_sources_and_tricks():
    assert head(ask('The leaflet says the shop opens at 09:00. A notice says from this week it opens at 10:00 on Sundays only. Today is a Sunday. When does it open?')).strip() == '10:00'
    assert head(ask('I picked a whole number between 1 and 6. Is it prime?')) == "It can't be determined"
    assert head(ask('A circle has a radius of 2 cm. What is its area?')).startswith('About 12.57')
    assert head(ask('I left at some point this afternoon and the drive lasted 3 hours. When did I arrive?')) == "It can't be determined"


def test_everyday_limits():
    assert head(ask('The boat takes 6 people or 500 kg. Six adults averaging 80 kg want to go with a 30 kg cool box. Can they all go together?')) == 'No'
    assert head(ask('Socks: 8 grey and 5 navy and 3 brown in a drawer. How many must I take to be sure of a matching pair?')) == '4'
    assert head(ask("Soap is £1 each, buy 1 get 1 free. I want 5 bars. How much do I pay?")) == '£3'


def test_silent_on_look_alikes():
    assert ask('How many minutes are in a day?') is None
    assert ask('What is the capital of France?') is None
    assert ask('My password is hunter2. Is that a strong password?') is None
    assert ask('Why is the sky blue?') is None
    assert ask('I have 3 boxes. How many do I have?') is None


def test_rate_reader_not_for_time_questions():
    msgs = [dict(role='user', content='A printer prints 10 pages a minute and pauses for 2 minutes. How many minutes does it take?')]
    got = everyday_exact.respond(msgs)
    assert not got or 'pages**' not in got['response']


def test_new_explanations():
    for q in ('What does double-blind mean in a drug trial?', 'Why is looking up a key in a hash table so fast?'):
        assert explain_more.respond([dict(role='user', content=q)]) is not None
    assert explain_more.respond([dict(role='user', content='What is a dictionary?')]) is None
