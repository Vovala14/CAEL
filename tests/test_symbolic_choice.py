"""Authored state/role counterfactuals and conservative fallback checks."""
import pytest
from cael_unified.symbolic_choice import reply


@pytest.mark.parametrize('premises,question,endings,expected',[
    ('Mira picked up the compass. Mira gave the compass to Leon.', 'Who holds the compass?', ['Mira','Leon'],1),
    ('Leon picked up the compass. Leon gave the compass to Mira.', 'Who holds the compass?', ['Mira','Leon'],0),
    ('Mira holds the compass. Leon receives the compass from Mira.', 'Who gave the compass to Leon?', ['Mira','Leon'],0),
    ('Leon holds the compass. Mira receives the compass from Leon.', 'Who received the compass?', ['Mira','Leon'],0),
    ('Mira went to the hall. Mira picked up the compass. Mira moved to the attic.', 'Where is the compass?', ['hall','attic'],1),
    ('Mira went to the attic. Mira picked up the compass. Mira moved to the hall.', 'Where is the compass?', ['hall','attic'],0),
    ('Mira holds the compass. Mira hands the compass to Leon. Leon dropped the compass.', 'Who holds the compass?', ['Mira','Leon'],None),
    ('All turtles are animals. All animals are living. Orla is a turtle.', 'Which statement follows?', ['Orla is living.','Orla is not living.'],0),
    ('All turtles are animals. Orla is a turtle.', 'Which statement must be true?', ['Orla is an animal.','Leon is a turtle.'],0),
    ('All turtles are animals. Orla is a turtle. Orla is not an animal.', 'Which statement follows?', ['Orla is an animal.','Orla is not an animal.'],None),
])
def test_explicit_proofs_and_counterfactuals(premises,question,endings,expected):
    answer=reply('Facts: '+premises+' '+question,endings)
    assert (answer['choice'] if answer else None)==expected


@pytest.mark.parametrize('context,endings',[
    ('Mira holds the compass. She gives it to Leon. Who holds the compass?', ['Mira','Leon']),
    ('Mira holds the compass. Leon holds the key. She gave the compass to him. Who holds the compass?', ['Mira','Leon']),
    ('Mira holds the compass. If Mira gives the compass to Leon, who holds the compass?', ['Mira','Leon']),
    ('Mira holds the compass. Maybe Mira gave the compass to Leon. Who holds the compass?', ['Mira','Leon']),
    ('Mira holds the compass. Leon gave the compass to Orla. Who holds the compass?', ['Mira','Orla']),
    ('Mira holds the compass. Mira gave the compass to Mira. Who holds the compass?', ['Mira','Orla']),
    ('Mira picked up the compass. Who holds the compass?', ['Mira','Mira']),
    ('Mira picked up the compass. Who holds the compass?', ['Mira and Leon','Nobody but Leon']),
    ('Mira picked up the compass. Who holds the compass?', ['Mira holds the compass and breaks it.','Leon']),
    ('Mira picked up the compass. A storm destroyed it. Who holds the compass?', ['Mira','Leon']),
    ('A man sits on a roof. He', ['stands up.','takes off his hat.']),
    ('Mira holds the compass. Choose the most likely continuation.', ['Mira gives the compass to Leon.','Mira moves to the hall.']),
    ('Facts: Orla is a turtle. Which statement follows?', ['Orla is a turtle.','Orla is a turtle.']),
    ('Facts: Orla is a turtle. Which statement follows?', ['Leon is a turtle.','Leon is not a turtle.']),
])
def test_unknown_ambiguous_or_future_statements_fall_through(context,endings):
    assert reply(context,endings) is None


def test_full_proposition_is_matched_without_extra_claims():
    answer=reply('Mira holds the compass. Mira gives the compass to Leon. Who holds the compass?',
                 ['Mira holds the compass.','Leon holds the compass.'])
    assert answer['choice']==1
    assert answer['reasoning']['support']


def test_unified_unknown_scenario_preserves_the_existing_chooser():
    from threading import RLock
    from unittest.mock import Mock,patch
    from cael_unified.assistant import Assistant
    assistant=Assistant.__new__(Assistant)
    assistant._lock=RLock()
    assistant.manifest={}
    assistant._reasoning=None
    assistant._evidence=object()
    assistant._arc_evidence=None
    assistant.vynly_reply=lambda *args:None
    assistant.choice_settings=lambda:dict(weight=2,short_limit=25,arc_weight=0)
    scores=[dict(sum_lnp=-4,tokens=1,chars=6),dict(sum_lnp=-2,tokens=1,chars=5)]
    assistant.score_endings=Mock(return_value=scores)
    prompt='Mira holds the compass. She gives it away. Who holds the compass?\nA) Mira\nB) Leon'
    with patch('cael_unified.choice.choose',return_value=(1,dict(route='fallback-sentinel'))) as chooser:
        answer=assistant._respond([dict(role='user',content=prompt)],seed=7,mode='chat')
    assert answer['route']=='chat/choice-count'
    assert answer['choice']==1
    assert answer['continuation_scores'] is scores
    assert chooser.call_args.args[2] is scores
    assistant.score_endings.assert_called_once()


def test_unified_proof_precedes_the_count_chooser():
    from threading import RLock
    from unittest.mock import Mock
    from cael_unified.assistant import Assistant
    assistant=Assistant.__new__(Assistant)
    assistant._lock=RLock()
    assistant.manifest={}
    assistant._reasoning=None
    assistant.vynly_reply=lambda *args:None
    assistant.score_endings=Mock(side_effect=AssertionError('Do not guess a proved answer'))
    prompt='Mira holds the compass. Mira hands the compass to Leon. Who holds the compass?\nA) Mira\nB) Leon'
    answer=assistant._respond([dict(role='user',content=prompt)],seed=7,mode='chat')
    assert answer['route']=='chat/choice-symbolic'
    assert answer['choice']==1
    assistant.score_endings.assert_not_called()
