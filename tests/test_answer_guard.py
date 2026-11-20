"""The final answer guard (answer_guard.py, 0.4.4, after an outside blind test: test-informed)."""
from cael_unified import answer_guard


def msgs(*turns):
    return [dict(role='user', content=t) for t in turns]


def test_advice_template_for_a_situation_is_replaced():
    m = msgs('We have jobs called wash, paint and seal. Seal must happen immediately after paint.', 'Could paint be the very first job?')
    got = answer_guard.check(m, dict(route='chat/advice-schema', response='Simple care that usually helps: 1. Rest it and avoid what makes it worse.'))
    assert got['route'] == 'chat/guard-unsure'


def test_unrelated_web_thread_is_replaced():
    m = msgs('The old bridge was built in 1890. The new bridge opened in 1932.', 'How many years apart are they?')
    got = answer_guard.check(m, dict(route='chat/web-single', response='From what I found: I lived in a family which was fairly restrictive.'))
    assert got['route'] == 'chat/guard-unsure'


def test_looked_up_word_not_in_the_situation_is_replaced():
    m = msgs('Three sauces stand in a row: pesto, salsa and aioli. Pesto moved to the end.', 'Which sauce goes in the middle now?')
    got = answer_guard.check(m, dict(route='chat/web-exact', response='**Middle Ages.** Sauces date back to the Middle Ages.'))
    assert got['route'] == 'chat/guard-unsure'


def test_on_topic_and_plain_fact_replies_pass():
    d = dict(route='chat/web-exact', response='The capital of France is **Paris**.')
    assert answer_guard.check(msgs('What is the capital of France?'), d) is d
    d = dict(route='chat/advice', response='To stop a bike chain slipping, check the chain for wear, clean and lube the chain, and adjust the gears.')
    assert answer_guard.check(msgs('How do I stop my bike chain slipping?'), d) is d
    d = dict(route='chat/exact-change', response='**$6.10**: the items come to $13.90.')
    assert answer_guard.check(msgs('3 coffees at $2.50 each. I pay with $20. How much change?'), d) is d


def test_number_for_a_non_number_question_is_replaced():
    m = msgs('The story has two sentences about a race and four about the crowd.', 'What does that phrase tell us, and why does the main event stay the same?')
    got = answer_guard.check(m, dict(route='chat/solve-math', response='**6 sentences**. Working: 2 sentences + 4 sentences = 6 sentences.'))
    assert got['route'] == 'chat/guard-unsure'
