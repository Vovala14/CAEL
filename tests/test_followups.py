"""followups.py (2026-11-22): corrections, what-if, questions about the last answer, thanks and acknowledgements. Wordings
differ from the development probes they were written on."""
import os
import tempfile
from pathlib import Path

import pytest

from cael_unified import Assistant, followups


def run(turns):
    tmp = Path(tempfile.mkdtemp(prefix='followups_'))
    os.environ.update(CAEL_LTM=str(tmp / 'ltm.json'), CAEL_MEMORY_FILE=str(tmp / 'memory.json'), CAEL_ONLINE='0', CAEL_WEB_SEARCH='0')
    model = Assistant(output_root=tmp / 'outputs')
    history, out = [], []
    for t in turns:
        history.append(dict(role='user', content=t))
        r = model.respond(history, n=1, seed=137, mode='chat')
        history.append(dict(role='assistant', content=r['response']))
        out.append(r['response'])
    return out


@pytest.mark.parametrize('turns,want', [
    (['A cake for 8 people uses 400 g of flour. Flour comes in 250 g bags. How many bags do I need for 12 people?', 'And for 20 people?'], '4 bags'),
    (['What is 30% of 150?', 'And 10%?'], '15'),
    (['I bought 4 mugs at $6 each. How much did I spend?', 'Sorry, it was 6 mugs, not 4.'], '$36'),
    (['My bus leaves at 07:15 and the ride takes 40 minutes. When do I get there?', 'Actually it leaves at 07:45.'], '8:25'),
])
def test_reworked_answers(turns, want):
    assert want in run(turns)[-1]


def test_corrected_statement_is_used_later():
    out = run(["I'm seeing the dentist on Tuesday at 10 am.", 'Sorry, I meant Thursday.', 'When am I seeing the dentist?'])
    assert 'Thursday' in out[1] and 'Thursday' in out[2]


def test_questions_about_the_last_answer():
    out = run(['A jacket costs $80 with 25% off. What do I pay?', 'How did you get that?'])
    assert '$60' in out[1] and '25%' in out[1]
    out = run(['What is 19 × 21?', 'Are you sure?'])
    assert out[1].startswith('Yes') and '399' in out[1]
    out = run(['What was my first question?'])
    assert 'first question was' not in out[0]


def test_chat_recall_of_questions():
    out = run(['What is 9 times 8?', 'What is 100 minus 37?', 'What was my first question?'])
    assert '9 times 8' in out[-1]


def test_thanks_and_acknowledgements():
    assert "welcome" in run(['Thank you, that was really helpful!'])[0].lower()
    out = run(['I live in Bristol and I work as a teacher.'])
    assert out[0].startswith('Got it') and 'Bristol' in out[0]
    out = run(["Hi! I've got a job interview tomorrow."])
    assert 'Good luck' in out[0] and 'interview' in out[0]


def test_feelings_are_not_acknowledged_as_facts():
    out = run(["I'm really worried about my exam."])
    assert not out[0].startswith('Got it')


def test_self_blame_after_a_loss():
    out = run(['My dog died last week.', "I keep thinking it's my fault."])
    assert 'hindsight' in out[1] or 'unfair' in out[1] or 'mattered' in out[1]


def test_lead_ins_are_ignored():
    assert followups.LEAD.sub('', 'By the way, what is 2 + 2?') == 'what is 2 + 2?'


def test_a_new_question_is_not_a_what_if():
    out = run(['A course costs $500 and needs a 20% deposit. How much is the deposit?', 'If they refund 50% of that, how much do I get back?'])
    assert '$50' in out[1]


def test_fixes_after_the_held_out_chat_check():
    # test-informed (2026-11-22): new wordings of five held-out misses
    assert '£' in run(['A lamp is £60 with 20% off. What do I pay?'])[0]
    assert '5:30' in run(['The class is at 4:30 pm.', 'They pushed it back by an hour.', 'What time is the class now?'])[-1]
    out = run(["I'm vegan."])
    assert out[0].startswith('Got it')
    out = run(['My aunt died last month.', 'I wish I had called her more often.'])
    assert 'her' in out[1] and 'illness' not in out[1]
    out = run(["I didn't pass my exam.", 'What should I do now?', 'Thank you.'])
    assert 'easy on yourself' in out[-1]
