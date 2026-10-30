"""0.3.8 regressions for John6666's HF forum report: listening constraints and fabricated personal facts.

Paired variants (the same constraint phrased many ways) plus negative controls (advice wanted, no constraint,
general facts). The histories are fictional; nothing here is a benchmark or held-out item.
"""
import pytest
from cael_unified.assistant import Assistant
from cael_unified import emotional_chat, personal_facts

SYSTEM = ('You are a helpful assistant. Use only information stated in this conversation for personal facts. '
          'Respond thoughtfully to feelings and respect requests to just listen.')
A = Assistant()


def ask(history, question, seed=137):
    msgs = [dict(role='system', content=SYSTEM)]
    for h in history:
        msgs += [dict(role='user', content=h), dict(role='assistant', content='Okay.')]
    msgs.append(dict(role='user', content=question))
    return A.respond(msgs, n=1, seed=seed, mode='chat')


ADVICE_TAILS = [g[3] for g in emotional_chat.GROUPS.values()]
NO_ADVICE_NO_QUESTIONS = [
    'Please do not give me advice or ask questions.',
    "Don't give me advice and don't ask me anything.",
    'I just want to vent. No advice or questions.',
    'I just want to vent. Please do not ask questions or give advice.',
    'No advice, no questions, just listen.',
    'Listen without giving advice or asking questions.',
    "I'm not looking for solutions or questions right now.",
    "Please don't try to fix it or quiz me.",
    "Don't advise me, and don't ask me why.",
    'Please just listen. No suggestions, no questions.',
]
FEELINGS = ['I feel burned-out today.', "I'm burned out.", 'I feel exhausted today.', 'I feel sad today.', 'I feel so lonely lately.']


@pytest.mark.parametrize('constraint', NO_ADVICE_NO_QUESTIONS)
@pytest.mark.parametrize('feeling', FEELINGS)
def test_no_advice_no_questions_paired_variants(constraint, feeling):
    reply = ask([constraint], feeling)['response']
    assert '?' not in reply
    assert not any(tail in reply for tail in ADVICE_TAILS)


@pytest.mark.parametrize('message', [
    "I'm feeling burned out at work. Please don't give me advice or ask me anything.",
    'I feel anxious today. No advice and no questions, please.',
])
def test_constraint_in_the_same_message(message):
    reply = ask([], message)['response']
    assert '?' not in reply and not any(tail in reply for tail in ADVICE_TAILS)


@pytest.mark.parametrize('constraint', ["Please don't ask me any questions.", 'No questions please.', "Don't ask me anything, okay?"])
def test_no_questions_only(constraint):
    assert '?' not in ask([constraint], 'I feel sad today.')['response']


@pytest.mark.parametrize('history,message', [
    ([], 'I feel burned-out today. Can you give me some advice?'),
    ([], "I'm overwhelmed. What should I do?"),
    ([], "I'm anxious about my exam, any tips?"),
    (['Please do not give me advice or ask questions.'], 'Actually, I changed my mind. Please give me some advice on burnout.'),
    (["Don't give me advice."], "I feel stressed. Actually, I do want advice. What should I do?"),
])
def test_advice_wanted_controls(history, message):
    reply = ask(history, message)
    assert reply['route'].startswith('chat/emotional')
    assert any(tail in reply['response'] for tail in ADVICE_TAILS), reply['response']


@pytest.mark.parametrize('feeling', ['I feel burned-out today.', "I'm burned out.", 'I feel sad today.'])
def test_no_constraint_control_still_asks(feeling):
    reply = ask([], feeling)
    assert reply['route'] == 'chat/emotional-reflection'
    assert reply['response'].rstrip().endswith('?')


def test_burned_out_spellings_match():
    a, b = ask([], "I'm burned out."), ask([], "I'm burned-out.")
    assert a['route'] == b['route'] == 'chat/emotional-reflection'
    assert a.get('emotional_terms') == b.get('emotional_terms')


@pytest.mark.parametrize('text,expected', [
    ('Please do not give me advice or ask questions.', dict(no_advice=True, no_questions=True, wants_advice=False)),
    ('I have no idea what to do, any tips?', dict(no_advice=False, wants_advice=True)),
    ("I don't want to lose my job, give me tips.", dict(no_advice=False, wants_advice=True)),
    ("I can't stop crying, what should I do?", dict(no_advice=False, wants_advice=True)),
    ("I don't know what to do. Can you give me some advice?", dict(no_advice=False, wants_advice=True)),
    ('Feel free to ask questions but do not give advice.', dict(no_advice=True, no_questions=False, questions_ok=True)),
])
def test_constraint_parser_negation_scope(text, expected):
    found = emotional_chat.constraints(text)
    assert {k: found[k] for k in expected} == expected


def test_no_questions_holds_on_other_chat_routes():
    answer = dict(route='chat/talk-converse', response='That sounds hard. What happened next?')
    msgs = [dict(role='user', content="Please don't ask me any questions."), dict(role='assistant', content='Okay.'),
            dict(role='user', content='Work was rough.')]
    assert '?' not in emotional_chat.enforce(msgs, answer)['response']
    msgs[0]['content'] = 'Hello.'
    assert emotional_chat.enforce(msgs, answer) == answer


# ---- Bug 2: personal facts are recalled, never supplied ----
PAIRS = [('Where was I born?', 'What city was I born in?'), ('In what city was I born?', 'What is my birthplace?')]


@pytest.mark.parametrize('history', [['I live in Tromso.'], ['I work as a nurse.'], ['Hi there.'], ['I like jazz.']])
@pytest.mark.parametrize('question', [q for pair in PAIRS for q in pair])
def test_unknown_birthplace_is_never_invented(history, question):
    reply = ask(history, question)
    text = reply['response']
    assert reply['route'] != 'chat/corpus' and not reply['route'].startswith('chat/local-')
    assert 'Paris' not in text and 'born in' not in text.replace('where you were born in', '')
    assert "haven't told me" in text or 'have not told me' in text


@pytest.mark.parametrize('question', ['Where was I born?', 'What city was I born in?'])
def test_stated_birthplace_is_recalled(question):
    assert 'Apia' in ask(['I was born in Apia.'], question)['response']


@pytest.mark.parametrize('history,question', [
    (['My sister is a nurse.'], 'Where was my sister born?'),
    (['My sister lives in Rome.'], 'Where was my sister born?'),
    (['My mother likes gardening.'], 'How old is my mother?'),
    (['I live in Tromso.'], 'How old am I?'),
    (['I live in Tromso.'], 'When is my birthday?'),
])
def test_unknown_personal_attributes_abstain(history, question):
    text = ask(history, question)['response']
    assert "haven't told me" in text or 'have not told me' in text
    assert 'Your sister' not in text                  # grammar: "your sister's", never "me Your sister's"


def test_abstention_grammar_for_the_user():
    text = ask(['I live in Tromso.'], 'How old am I?')['response']
    assert 'about them' not in text


@pytest.mark.parametrize('question,expected', [('Where was Marie Curie born?', 'Warsaw'), ('Where was Albert Einstein born?', 'Ulm')])
def test_general_facts_still_answered(question, expected):
    assert expected in ask(['I live in Tromso.'], question)['response']


@pytest.mark.parametrize('text', ['How do I cope with stress?', 'What should I name my dog?', 'How can I find my birth certificate?',
                                  'Where was Marie Curie born?', 'What is my name?'])
def test_personal_guard_leaves_other_questions_alone(text):
    assert personal_facts.personal_question(text) is None


def test_retrieval_rejects_a_reply_about_another_person():
    assert personal_facts.foreign_person('What city was I born in?', 'What city was she born in?')
    assert not personal_facts.foreign_person('How do I make pancakes?', 'How do you make pancakes?')
