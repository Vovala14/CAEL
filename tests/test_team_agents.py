"""The Mr. Meesix team's specialists (calc_agent, schedule_agent, writer_agent, logic_agent, recall_agent, empath, counsel).
All offline: no network is touched."""
import pytest

from cael_unified import calc_agent, counsel, empath, logic_agent, recall_agent, schedule_agent, solve_math, writer_agent


def chat(turns, *modules):
    """Run the turns through the given specialists in order; return the list of replies ('' where none took the turn)."""
    messages, replies = [], []
    for t in turns:
        messages.append(dict(role='user', content=t))
        got = None
        for m in modules:
            got = m.respond(messages)
            if got:
                break
        replies.append(got['response'] if got else '')
        messages.append(dict(role='assistant', content=replies[-1]))
    return replies


@pytest.mark.parametrize('turns, wanted', [
    (["A taxi charges a $4 flat fee plus $2.50 per kilometre. How much is a 12 km ride?", "And if I split it equally with two friends, what does each of us pay?"], ['$34', '$11.33']),
    (["I'm tiling a floor that's 3 m by 4 m. Each box of tiles covers 1.5 square metres. How many boxes do I need?", "The boxes are $28 each. What's the total cost?"], ['8 boxes', '$224']),
    (["A garden bed is 2.5 m by 1.2 m. A bag of compost covers 0.8 square metres. How many bags do I need?"], ['4 bags']),
    (["I want to carpet a room that is 4 metres by 5 metres. Carpet costs $22 per square metre. What will it cost?", "What if the room was 6 metres long instead of 5?"], ['$440', '$528']),
    (["My shift starts at 2:30 pm and it's 7 and a half hours long. When do I finish?", "If I get a 45 minute unpaid break, how many hours am I paid for?"], ['10:00 pm', '6 hours 45 minutes']),
    (["One printer costs $80 and its ink is $30 per cartridge. Another costs $150 and its ink is $12 per cartridge. If I use 5 cartridges a year, which is cheaper after two years?", "And after one year?"],
     ['second is cheaper over 2 years', '$210']),
    (["Phone plan A costs $25 a month with a $120 phone. Plan B costs $18 a month with a $250 phone. Which is cheaper over two years?", "And over one year?"], ['Plan B is cheaper', 'plan A is cheaper']),
    (["Three friends are splitting a $96 restaurant bill and want to add a 15% tip. How much does each person pay?"], ['$36.80']),
    (["A recipe needs 250 g of flour for 12 biscuits. How much flour do I need for 30 biscuits?", "I only have 500 g. How many biscuits can I make?"], ['625 g', '24 biscuits']),
    (["I earn $18 an hour and work 35 hours a week. How much do I earn in a week?", "And in four weeks?"], ['$630', '$2,520']),
    (["I bought 3 notebooks at $4 each and a pen for $2. How much did I spend?", "If I pay with a $20 note, how much change do I get?"], ['$14', '$6']),
])
def test_calculator_over_turns(turns, wanted):
    replies = chat(turns, calc_agent, solve_math)
    for reply, want in zip(replies, wanted):
        assert want.lower() in reply.lower(), (turns, replies)


def test_diary():
    replies = chat(["On Monday I have a team meeting at 9 and the gym at 6. On Wednesday I have lunch with Priya at noon.", "Add a call with the bank on Tuesday at 4.",
                    "What do I have on Tuesday and Wednesday?", "Move the call with the bank to Friday at 10.", "What's on Friday?", "Cancel the gym.", "What's on Monday?"], schedule_agent)
    assert 'team meeting at 9' in replies[0] and 'gym at 6' in replies[0]
    assert 'call with the bank at 4' in replies[2] and 'lunch with Priya at noon' in replies[2]
    assert 'Friday' in replies[3] and 'call with the bank at 10' in replies[4]
    assert 'gym' not in replies[6] and 'team meeting at 9' in replies[6]
    assert schedule_agent.respond([dict(role='user', content="What's the weather on Monday?")]) is None


def test_writer():
    replies = chat(["Can you write a short text to my landlord saying the kitchen tap is leaking and asking when someone can come to fix it?", "Thanks. Can you make it a bit more formal?"], writer_agent)
    assert 'The kitchen tap is leaking.' in replies[0] and 'when someone can come to fix it?' in replies[0]
    assert 'Dear' in replies[1] and 'Kind regards' in replies[1] and 'the kitchen tap is leaking' in replies[1]
    reply = chat(["Write a quick note to my neighbour telling her that a parcel was left at my door for her and asking when she can pick it up."], writer_agent)[0]
    assert 'for you' in reply and 'when you can pick it up' in reply and ' her ' not in reply
    poem = chat(["Can you write me a short poem about a lighthouse in winter?", "Lovely. Could you make it rhyme and keep it to four lines?"], writer_agent)[1]
    lines = [x for x in poem.split('\n') if x.endswith((',', ';', '.')) and not x.startswith(('Here', '('))]
    assert len(lines) == 4 and 'lighthouse in winter' in poem


@pytest.mark.parametrize('text, start', [
    ("All the books on the top shelf are novels. None of the novels are in French. Is there a French book on the top shelf?", '**No.**'),
    ("All the mugs in the cupboard are blue. None of the blue things are chipped. Is there a chipped mug in the cupboard?", '**No.**'),
    ("Every student in the choir plays an instrument. Lena is in the choir. Does Lena play an instrument?", '**Yes.**'),
    ("No reptiles have fur. All snakes are reptiles. Is there a snake with fur?", '**No.**'),
    ("All of my cousins live in Leeds. Maya is my cousin. Does Maya live in Leeds?", '**Yes.**'),
])
def test_logician(text, start):
    assert logic_agent.respond([dict(role='user', content=text)])['response'].startswith(start)


def test_logician_does_not_guess():
    assert logic_agent.respond([dict(role='user', content="All the mugs are blue. None of the blue plates are chipped. Is there a chipped mug?")]) is None


def test_rememberer():
    assert 'Biscuit' in chat(["I've just adopted a rescue greyhound called Biscuit. He's four years old.", "What was my dog's name again, and how old is he?"], recall_agent)[1]
    assert '**9**' in chat(["I'm planning a camping trip with my two kids, Mila and Jonas. Mila is 9 and Jonas is 6.", "Remind me, how old did I say Mila is?"], recall_agent)[1]
    assert chat(["I'm planning a hiking weekend with my friends Dana and Olek. Dana is vegetarian.", "Remind me, which of my friends is vegetarian?"], recall_agent)[1].startswith('**Dana**')
    assert recall_agent.respond([dict(role='user', content='Hello'), dict(role='assistant', content='Hi'), dict(role='user', content="What's my dog's name?")]) is None


def test_listener_never_repeats_the_user():
    told = "They gave it to someone who joined eight months ago. I don't even know if I want to stay now."
    reply = empath.respond([dict(role='user', content=told)])['response']
    assert 'eight months' not in reply and reply.rstrip().endswith('?')
    assert empath.respond([dict(role='user', content='How do vaccines work?')]) is None


def test_counsellor_shapes():
    def ask(*turns):
        messages = []
        for t in turns:
            messages += [dict(role='user', content=t), dict(role='assistant', content='ok')]
        got = counsel.reply(messages[:-1])
        return got['response'] if got else None
    assert ask("Morning! I just got back from my first ever yoga class.", "I couldn't touch my toes. Is that normal for a beginner?").startswith("Yes, that's completely normal")
    assert 'a vet' in ask("I've just got a kitten called Miso.", "She hides under the bed a lot. Should I be worried?")
    assert 'respectable' in ask("Hey! I just finished my first 5k run.", "My time was 34 minutes. Is that okay for a first one?")
    assert ask("Who wrote Dracula?") is None
