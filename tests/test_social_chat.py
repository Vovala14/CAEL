"""Authored small-talk controls, follow-ups and route boundaries."""
import pytest
from cael_unified import social_chat, smalltalk, chat_extra


def turns(*text):
    return [dict(role='user' if i%2==0 else 'assistant',content=t) for i,t in enumerate(text)]


@pytest.mark.parametrize('text', ["Let's chat",'Can we talk?','Keep me company','I just want to chat',
    'Talk to me','What should we talk about?',"I'm just here to chat",'Start a conversation'])
def test_invites(text):
    answer=smalltalk.reply(turns(text),seed=3)
    assert answer['route']=='chat/smalltalk-invite'
    assert social_chat.MENU in answer['response']


@pytest.mark.parametrize('text,key', [('I love jazz','music'),('I enjoy hiking','outdoors'),
    ('I like reading novels','books'),('I am into board games','games'),('I love cooking','food'),
    ("Let's talk about movies",'movies'),('Can we talk about music?','music'),
    ('I would like to talk about games','games')])
def test_specific_interests_get_related_questions(text,key):
    result=social_chat.reply(turns(text),seed=4)
    assert any(result['response'].endswith(q) for q in social_chat.TOPICS[key][1])
    assert 'lookup' in result['details']
    assert result['sources']==[]


def test_invitation_topic_and_followup_keep_context_without_repetition():
    messages=turns("Let's chat")
    first=social_chat.reply(messages,7)
    messages += [dict(role='assistant',content=first['response']),dict(role='user',content='music')]
    second=social_chat.reply(messages,7)
    assert social_chat.context(messages+[dict(role='assistant',content=second['response']),dict(role='user',content='jazz')])=='music'
    messages += [dict(role='assistant',content=second['response']),dict(role='user',content='jazz')]
    third=social_chat.reply(messages,7)
    assert third['response'] != second['response']
    assert any(third['response'].endswith(q) for q in social_chat.TOPICS['music'][1])
    assert social_chat.reply(messages,7)==third


def test_declining_changes_topic_and_stops_previous_question():
    question=social_chat.TOPICS['music'][1][0]
    answer=social_chat.reply(turns('I like music',question,"I don't want to talk about it"),1)
    assert 'switch topics' in answer['response']
    assert not any(answer['response'].endswith(q) for q in social_chat.TOPICS['music'][1])


def test_reciprocal_does_not_invent_personal_experiences():
    answer=social_chat.reply(turns('I enjoy books',social_chat.TOPICS['books'][1][0],'and you?'),2)
    assert "don't have personal experiences" in answer['response']


def test_fun_question_and_choice_response():
    answer=social_chat.reply(turns('Ask me a fun question'),2)
    assert answer['response'] in social_chat.FUN
    pick=social_chat.FUN_CHOICES[social_chat.FUN.index(answer['response'])][0]
    follow=social_chat.reply(turns('Ask me a fun question',answer['response'],pick),2)
    assert follow['route']=='chat/smalltalk-fun-followup'


def test_unrelated_game_choice_is_clarified_and_declining_stops_game():
    previous=social_chat.FUN[0]
    answer=social_chat.reply(turns('Ask me a fun question',previous,'a board game'),2)
    assert answer['route']=='chat/smalltalk-fun-clarify'
    declined=social_chat.reply(turns('Ask me a fun question',previous,'no thanks'),2)
    assert declined['route']=='chat/smalltalk-change-topic'
    assert declined['response'].endswith(social_chat.MENU)


def test_game_followup_can_continue_or_stop_without_losing_context():
    result=social_chat.reply(turns('forest',social_chat.FUN_WHY,'I enjoy being outdoors'),2)
    assert result['response'].endswith(social_chat.FUN_MORE)
    again=social_chat.reply(turns('I enjoy being outdoors',result['response'],'yes please'),2)
    assert again['response'] in social_chat.FUN
    stopped=social_chat.reply(turns('I enjoy being outdoors',result['response'],'no'),2)
    assert stopped['response'].endswith(social_chat.MENU)


@pytest.mark.parametrize('text', ["I don't want to talk anymore",'Stop asking me questions','no more questions',"that's enough"])
def test_request_to_stop_does_not_ask_another_question(text):
    result=social_chat.reply(turns('I like music',social_chat.TOPICS['music'][1][0],text),1)
    assert result['route']=='chat/smalltalk-pause'
    assert '?' not in result['response']


def test_negated_game_choice_is_not_treated_as_a_positive_preference():
    result=social_chat.reply(turns('Ask me a fun question',social_chat.FUN[0],'not the forest'),1)
    assert result['route']=='chat/smalltalk-fun-clarify'


def test_dislike_does_not_get_congratulations():
    response=social_chat.reply(turns("I don't like music"),1)
    assert response['route']=='chat/smalltalk-preference'
    assert 'Fair enough' in response['response']


@pytest.mark.parametrize('text', ['When was Metallica formed?','What is jazz','Calculate 7*8',
    'Write a Python function','Fix my grammar','Tell me about the latest music news',
    'Read my file','delete all files','help me','Who wrote that book?',
    "Let's talk about the latest music news",'I like music but can you explain jazz',
    'I like music. What is 2+2?', 'I like music but I am sad'])
def test_tasks_and_mixed_messages_never_become_smalltalk(text):
    history=turns('I like music',social_chat.TOPICS['music'][1][0],text)
    assert social_chat.reply(history,1) is None


@pytest.mark.parametrize('text', ['Thanks','Hello','Goodbye','My name is Mila',"I'm tired",'My dog died'])
def test_social_acts_and_distress_are_left_to_existing_handlers(text):
    history=turns('I like music',social_chat.TOPICS['music'][1][0],text)
    assert social_chat.reply(history,1) is None


def test_context_does_not_leak_or_survive_an_unrelated_answer():
    assert social_chat.reply(turns('jazz'),1) is None
    assert social_chat.reply(turns('no'),1) is None
    assert social_chat.reply(turns('Calculate 2+2','4','and you?'),1) is None
    assert social_chat.reply(turns('I like music',social_chat.TOPICS['music'][1][0],
        'Calculate 2+2','4','jazz'),1) is None


def test_chat_extra_routes_interest_before_generic_conversation():
    history=turns('hello','Hello! How are you today?','I like jazz')
    response=chat_extra.reply(history[-1]['content'],history,1)
    assert response['route']=='chat/smalltalk-topic'


def test_day_reply_is_honest_about_the_assistant():
    response=social_chat.reply(turns('How was your day?'),1)
    assert "don't have a day like a person" in response['response']
    assert 'chatting with people' not in response['response']
