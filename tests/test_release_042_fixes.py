"""CAEL 0.4.2 release checks: the four faults found in the release comparison, each on new wording, plus the Supporter,
coherence and story behaviour added in this version."""
import os
import re
import tempfile
from pathlib import Path

import pytest

from cael_unified import Assistant, calc_agent, chat_memory, story_agent, support, writer_agent


def run(turns):
    tmp = Path(tempfile.mkdtemp(prefix='rel042_'))
    os.environ.update(CAEL_LTM=str(tmp / 'ltm.json'), CAEL_MEMORY_FILE=str(tmp / 'memory.json'))
    model = Assistant(output_root=tmp / 'outputs')
    history, out = [], []
    for t in turns:
        history.append(dict(role='user', content=t))
        r = model.respond(history, n=1, seed=137, mode='chat')
        history.append(dict(role='assistant', content=r['response']))
        out.append(r)
    return out


def test_an_appointment_moved_by_text_gives_the_new_time():
    r = run(["The plumber is booked for Monday at 9 am.", "She just texted to say she'll come on Wednesday at 2 pm instead.",
             "When is the plumber coming?"])[-1]
    assert 'Wednesday at 2 pm' in r['response']


def test_a_discount_on_the_full_price_after_a_deposit():
    m = [dict(role='user', content='A fridge costs $900 and they want a 10% deposit. How much is the deposit?'),
         dict(role='assistant', content='**$90**.'),
         dict(role='user', content='If they take 20% off the full price, how much is it then?')]
    assert '**$720**' in calc_agent.respond(m)['response']


def test_a_note_thanking_someone_is_a_note():
    req = writer_agent.thank_parse("Could you write a quick message to my friend thanking him for feeding my cat last weekend?")
    assert req and req['role'] == 'friend' and 'feeding my cat' in req['why']


def test_symptom_follow_ups_are_about_the_body():
    from cael_unified import advice_schemas
    turns = ["I've been getting headaches every afternoon at work.", "Could it be my screen?"]
    assert advice_schemas.best_class([], turns) == 'body'


@pytest.mark.parametrize('turns,want', [
    (["I've been feeling really lonely since I moved here.", "What could I do about it?"], r'regular contact|club|class|volunteer'),
    (["My son didn't make the football team and he's really upset.", "How do I help him?"], r'(?i)listen|effort|feeling'),
    (["Our dog died last week.", "Is it normal to feel this sad about a pet?"], r'(?i)^Yes'),
])
def test_supporter_answers_the_follow_up(turns, want):
    users = []
    msgs = []
    for t in turns:
        msgs.append(dict(role='user', content=t))
        r = support.respond(msgs)
        msgs.append(dict(role='assistant', content=(r or {}).get('response', 'ok')))
    assert r and re.search(want, r['response'])


def test_supporter_respects_no_advice():
    m = [dict(role='user', content="I feel so lonely lately."), dict(role='assistant', content='...'),
         dict(role='user', content="Please just listen. No advice.")]
    assert support.respond(m) is None


def test_a_funnier_ending_changes_the_ending():
    first = [dict(role='user', content='Write a short story about a goat who keeps eating the washing.')]
    a = story_agent.respond(first)['response']
    b = story_agent.respond(first + [dict(role='assistant', content=a), dict(role='user', content='Can you make it funnier?')])['response']
    assert a.split('\n\n')[-1] not in b and 'kept eating' in a


def test_recall_without_update_still_reads_back():
    m = [dict(role='user', content='My sister is visiting on Friday at 6 pm.'), dict(role='assistant', content='Noted.'),
         dict(role='user', content='When is my sister visiting?')]
    assert 'Friday at 6 pm' in chat_memory.situation_recall(m)['response']
