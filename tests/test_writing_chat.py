"""Authored grammar/conversation cases; no external data or benchmark rows."""
import pytest

from cael_unified import grammar, smalltalk, writing_chat


@pytest.mark.parametrize('source,expected', [
    ('She could goes home.', 'She could go home.'),
    ("They didn't ate breakfast.", "They didn't eat breakfast."),
    ('Does she have a map?', 'Does she have a map?'),
    ('Has he eaten lunch?', 'Has he eaten lunch?'),
    ('Have they wrote back?', 'Have they written back?'),
    ('We have ran today.', 'We have run today.'),
    ("You wasn't there.", "You weren't there."),
    ("I isn't ready.", 'I am not ready.'),
    ('He can saw wood.', 'He can saw wood.'),
    ('She could found a company.', 'She could found a company.'),
    ('He has rose bushes.', 'He has rose bushes.'),
    ('She has works of art.', 'She has works of art.'),
    ('I have saw blades.', 'I have saw blades.'),
    ('I have a cat. she have a dog.', 'I have a cat. She has a dog.'),
    ('She can go.\n\nWe must works.', 'She can go.\n\nWe must work.'),
    ('If he were ready, they would leave.', 'If he were ready, they would leave.'),
    ('I wish she were here.', 'I wish she were here.'),
    ("If she weren't here, we would wait.", "If she weren't here, we would wait."),
    ("He didn't claim she saw nothing.", "He didn't claim she saw nothing."),
    ('It is not unhelpful.', 'It is not unhelpful.'),
    ("It's Wednesday.", "It's Wednesday."),
    ("It's dinner time.", "It's dinner time."),
    ('CAEL uses tool_42.', 'CAEL uses tool_42.'),
    ('The cost is €18.75.', 'The cost is €18.75.'),
    ('Email team@example.net.', 'Email team@example.net.'),
    ('Open https://example.net/docs?v=2.', 'Open https://example.net/docs?v=2.'),
    ('The value is `account_id`.', 'The value is `account_id`.'),
    ("The label says 'ready'.", "The label says 'ready'."),
    ('The status says “ready”.', 'The status says “ready”.'),
    ('Renée uses café_menu.', 'Renée uses café_menu.'),
    ('Visit São Paulo.', 'Visit São Paulo.'),
    (r'Open C:\Projects\report.txt.', r'Open C:\Projects\report.txt.'),
    ('Use CAEL v0.3.', 'Use CAEL v0.3.'),
])
def test_corrections_and_preservation(source, expected):
    assert grammar.correct(source)[0] == expected


@pytest.mark.parametrize('text,target', [
    ('Can you fix my grammar?', ''),
    ('check my grammar, please?', ''),
    ('fix my grammar for me', ''),
    ('fix my grammar.', ''),
    ('Please correct this sentence: she can goes home', 'she can goes home'),
    ('Hi, could you check the grammar in this sentence: he have a map', 'he have a map'),
    ('Correct my spelling and grammar: I have went', 'I have went'),
    ('fix: he can goes', 'he can goes'),
    ('proofread my paragraph:\nwe is ready', 'we is ready'),
    ('fix grammar this is my book', 'this is my book'),
    ('fix grammar: this is my book', 'this is my book'),
    ('fix grammar in this sentence: this is my book', 'this is my book'),
])
def test_explicit_request_parsing(text,target):
    assert writing_chat.request(text) == (True,target)


@pytest.mark.parametrize('text', [
    'What is grammar?', 'What is the weather?', 'Check whether 17 is prime',
    'Write a Python grammar parser', 'Fix this Python code', 'Check the car engine',
    'The grammar checker is broken', 'Please improve the image prompt',
])
def test_other_tasks_are_not_edit_requests(text):
    assert writing_chat.reply(text,[dict(role='user',content=text)]) is None


def dialogue(*turns):
    return [dict(role='user' if i%2==0 else 'assistant', content=t) for i,t in enumerate(turns)]


def test_pending_target_plain_and_explanation_followups():
    first=writing_chat.reply('fix my grammar',dialogue('fix my grammar'))
    assert first['route']=='chat/grammar-ask'
    turns=['fix my grammar',first['response'],'we has a map']
    fixed=writing_chat.reply(turns[-1],dialogue(*turns))
    assert 'We have a map.' in fixed['response']
    turns += [fixed['response'],'just the corrected sentence']
    plain=writing_chat.reply(turns[-1],dialogue(*turns))
    assert plain['response']=='We have a map.'
    turns += [plain['response'],'why?']
    why=writing_chat.reply(turns[-1],dialogue(*turns))
    assert why['route']=='chat/grammar-explain'
    assert 'have' in why['response']


def test_new_edit_and_its_followup_keep_the_new_target():
    old='correct: he go home'
    first=writing_chat.reply(old,dialogue(old))
    again='and this: we has a car'
    next_result=writing_chat.reply(again,dialogue(old,first['response'],again))
    plain='only the corrected text'
    answer=writing_chat.reply(plain,dialogue(old,first['response'],again,next_result['response'],plain))
    assert answer['response']=='We have a car.'


@pytest.mark.parametrize('task', ['What is 2+2?', 'Calculate 3*4', 'Who is Ada Lovelace?', 'Write a Python helper', 'cancel'])
def test_pending_edit_does_not_consume_a_new_task(task):
    turns=dialogue('fix my grammar',writing_chat.ASK,task)
    assert writing_chat.reply(task,turns) is None


def test_unrelated_turn_and_separate_conversation_end_context():
    request='correct: she go home'
    answer=writing_chat.reply(request,dialogue(request))
    assert writing_chat.reply('why?',dialogue('why?')) is None
    assert writing_chat.reply('why?',dialogue(request,answer['response'],'What is 2+2?','4','why?')) is None
    assert writing_chat.reply('only the corrected text',dialogue('only the corrected text')) is None
    interrupted=[dict(role='user',content=request),dict(role='system',content='unrelated state'),
                 dict(role='assistant',content=answer['response']),dict(role='user',content='why?')]
    assert writing_chat.reply('why?',interrupted) is None


def test_limits_and_code_are_not_silently_edited():
    target='fix my grammar: '+ 'a'*2001
    assert writing_chat.reply(target,dialogue(target))['route']=='chat/grammar-limit'
    target='fix my grammar: def add(x): return x + 1'
    assert writing_chat.reply(target,dialogue(target)) is None


def test_repeated_smalltalk_varies_but_same_history_seed_is_stable():
    history=dialogue('hello')
    first=smalltalk.reply(history,seed=7)
    history += [dict(role='assistant',content=first['response']),dict(role='user',content='hello')]
    assert smalltalk.reply(history,seed=7)['response'] != first['response']
    assert smalltalk.reply(history,seed=7) == smalltalk.reply(history,seed=7)


def test_editor_preserves_input_before_typo_interpretation():
    target='correct: Zyphrax uses CAEL.'
    assert writing_chat.protect_input(target,dialogue(target))
    assert writing_chat.protect_input('she has went',dialogue('fix my grammar',writing_chat.ASK,'she has went'))
    assert not writing_chat.protect_input('Calculate 2+2',dialogue('fix my grammar',writing_chat.ASK,'Calculate 2+2'))


@pytest.mark.parametrize('text,kind', [('Hello','greeting'),('Thanks','thanks'),('Goodbye','goodbye'),('My name is Mila','name')])
def test_generic_conversation_does_not_swallow_explicit_social_act(text,kind):
    from cael_unified import chat_extra
    messages=dialogue('hello','Hi! How are you today?',text)
    answer=chat_extra.reply(text,messages,seed=7)
    assert answer['route']=='chat/smalltalk-'+kind
