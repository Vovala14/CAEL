"""Advice library, subject checks (John6666's contrast cases, Hugging Face forum, 2026-11-15) and the Listener. Offline."""
import pytest

from cael_unified import advice_library, applicability, empath, recall_agent, writer_agent, calc_agent, logic_agent


def chat(turns, module):
    messages, replies = [], []
    for t in turns:
        messages.append(dict(role='user', content=t))
        got = module.respond(messages) if hasattr(module, 'respond') else module.reply(messages)
        replies.append(got['response'] if got else '')
        messages.append(dict(role='assistant', content=replies[-1]))
    return replies


def test_piano_is_not_given_guitar_advice():
    piano = chat(["I'm learning the piano.", "My fingers get tired quickly when I play the piano. Is that normal?"], advice_library)[1]
    guitar = chat(["I'm learning the guitar.", "My fingertips hurt when I play the guitar. Is that normal?"], advice_library)[1]
    assert 'piano' in piano and 'guitar' not in piano and 'calluses' not in piano
    assert 'guitar' in guitar and 'calluses' in guitar


def test_conflict_detects_a_different_member_of_a_group():
    assert applicability.conflict('I play the piano and my fingers ache', 'Calluses form on guitar strings') == ('guitar', 'piano')
    assert applicability.conflict('I play the guitar', 'Calluses form on guitar strings') is None
    assert applicability.conflict('How do I cook rice?', 'Use a guitar') is None


@pytest.mark.parametrize('said, start', [
    ("The interview went well but I was rejected.", "That must sting"),
    ("I didn't get the job.", "I'm sorry"),
    ("I did not get the job.", "I'm sorry"),
    ("The interview went well; I don't know the result yet.", "Fingers crossed"),
    ("The interview went well and I got the job.", "Congratulations"),
])
def test_outcome_before_tone(said, start):
    assert empath.respond([dict(role='user', content=said)])['response'].startswith(start)


def test_moving_together_is_not_someone_leaving():
    reply = empath.respond([dict(role='user', content="My partner Theo and I are moving to a new flat next month.")])['response']
    assert 'sad to see them go' not in reply


def test_generalised_topics():
    def ask(*turns):
        return chat(list(turns), advice_library)[-1]
    assert 'Water your monstera' in ask("I just bought a monstera.", "How often should I water it?")
    assert 'cacti' in ask("I've got a cactus on my windowsill. How often should I water it?")
    assert 'sighthounds' in ask("I've adopted a greyhound called Biscuit.", "How much exercise does a greyhound need?")
    assert 'C, A minor, F and G' in ask("I'm learning the ukulele.", "Which chords should I learn first?")
    assert 'adult cats' in ask("My cat is 12. How much should I feed him?")
    assert 'Kittens' in ask("I've got a kitten called Miso.", "How often should I feed her?")
    assert ask("Who painted the Mona Lisa?") == ''


def test_recall_name_kind_and_value():
    assert 'Gerald' in chat(["I just bought my first houseplant, a monstera. I've named it Gerald.", "What did I name my plant again, and what kind is it?"],
                            recall_agent)[1]
    assert 'third floor' in chat(["We're moving to a new flat. It's on the third floor with no lift.", "Remind me, which floor did I say the flat is on?"],
                                 recall_agent)[1]


def test_poem_first_and_two_lines():
    replies = chat(["Could you write a short poem about autumn leaves?", "Nice! Can you do a shorter version, just two lines that rhyme?"], writer_agent)
    assert replies[0].count('\n') >= 5 and len([x for x in replies[1].split('\n') if x.endswith(('.', ',', ';')) and not x.startswith('Here')]) == 2


@pytest.mark.parametrize('turns, want', [
    (["A car park charges $3 for the first hour and $1.50 for each hour after that. How much is it for 5 hours?"], '$9'),
    (["My flight departs at 6:40 am and takes 2 hours 50 minutes. What time do I land?",
      "If I need to be at the airport 2 hours before departure, when should I get there?"], '4:40 am'),
])
def test_calculator_extras(turns, want):
    from cael_unified import solve_math
    messages = []
    for t in turns:
        messages.append(dict(role='user', content=t))
        got = calc_agent.respond(messages) or solve_math.respond(messages)
        messages.append(dict(role='assistant', content=got['response']))
    assert want in messages[-1]['content']


def test_nobody_who():
    got = logic_agent.respond([dict(role='user', content="All the students in room 4 passed the exam. Nobody who passed needs to resit. "
                                                         "Does anyone in room 4 need to resit?")])
    assert got['response'].startswith('**No.**')
