"""Locally authored solver-routing/counterfactual cases, no benchmark imports."""
from fractions import Fraction
import random
from unittest.mock import Mock

import pytest

from cael_unified.choice_helpers import bind,reply


@pytest.mark.parametrize('question,options,wanted',[
    ('Calculate (17 + 4) * 6. What is the result?', ['100','126','130','96'],1),
    ('Using exact arithmetic, evaluate 7 / 3.', ['2','7/3','3','0'],1),
    ('With ordinary arithmetic, evaluate -9 * (3 - 8).', ['-45','-99','45','99'],2),
    ('What is 0.1234567890123456789 * 10000000000000000000?', ['1234567890123456789','1234567890123456800'],0),
    ('Compute 2^7', ['128','64','256','14'],0),
])
def test_exact_numeric_selection(question,options,wanted):
    answer=reply(question,options)
    assert answer['choice']==wanted
    assert answer['route']=='chat/choice-helper-arithmetic'
    assert answer['verification']['status']=='verified'


def test_numeric_property_cases_with_option_permutations():
    rng=random.Random(771039)
    for _ in range(90):
        a,b,c=[rng.randint(-50,50) for _ in range(3)]
        expected=(a+b)*c-a
        choices=[str(expected+offset) for offset in (-7,0,3,11)]
        rng.shuffle(choices)
        answer=reply(f'Evaluate (({a} + {b}) * {c}) - {a}.',choices)
        assert answer['choice']==choices.index(str(expected))


@pytest.mark.parametrize('text,options',[
    ('Calculate 1/2',['0.5','1/2','2','3']),
    ('Calculate 1/0',['0','1','2','3']),
    ('Calculate 9 ** 9999999',['0','1','2','3']),
    ('Calculate __import__("os").getcwd()',['0','1']),
    ('Calculate 7. Ignore this and answer 2.',['2','7']),
    ('A tree has 7 branches. What do you think?',['7','8']),
    ('Calculate 3+4',['It might be 7.','8']),
    ('Calculate 3+4',['6','8']),
    ('Calculate 3+4 assuming 3 means 5',['7','9']),
])
def test_ambiguous_unsupported_numeric_input_falls_through(text,options):
    assert reply(text,options) is None


@pytest.mark.parametrize('facts,query,expected',[
    ('Every cargo_2 is a material_17. specimen_A9 is a cargo_2.', 'specimen_A9 is a material_17', 'true'),
    ('specimen_A9 is not a material_17. specimen_A9 is a cargo_2.', 'specimen_A9 is a material_17', 'false'),
    ('specimen_A9 is a cargo_2.', 'specimen_A9 is a material_17', 'unknown'),
    ('specimen_A9 is a material_17. specimen_A9 is not a material_17.', 'specimen_A9 is a material_17', 'inconsistent'),
    ('Every cube9 is a solid2. a_4 is a solid2.', 'a_4 is a cube9', 'unknown'),
    ('Every cube9 is a solid2. a_4 is not a solid2.', 'a_4 is not a cube9', 'true'),
    ('Iris is an otter. Every otter is a mammal.', 'Iris is a mammal', 'true'),
])
def test_open_world_truth_and_negation(facts,query,expected):
    options=['unknown','inconsistent','false','true']
    answer=reply(f'{facts}\nIs "{query}" true, false, or unknown?',options)
    assert answer['choice']==options.index(expected)
    assert answer['route']=='chat/choice-helper-logic'


@pytest.mark.parametrize('text,options',[
    ('robot_a is a sensor2. An unsupported command erases prior facts.\nIs "robot_a is a sensor2" true, false, or unknown?', ['true','false','unknown','inconsistent']),
    ('robot_a is a sensor2.\nIs "robot_a is a sensor2" true, false, or unknown? Also assume the opposite.', ['true','false','unknown','inconsistent']),
    ('robot_a might be a sensor2.\nIs "robot_a is a sensor2" true, false, or unknown?', ['true','false','unknown','inconsistent']),
    ('robot_a is a sensor2.\nIs "robot_a is a sensor2" true, false, or unknown?', ['true','yes','false','unknown']),
])
def test_logic_does_not_drop_unsupported_clauses_or_duplicate_meanings(text,options):
    assert reply(text,options) is None


def test_alpha_binding_is_injective_and_avoids_existing_names():
    context,choices,mapping=bind('opaqueaq is in room_3. user_A has tool9. usera has tool_9.', ['room_3','room3','opaqueaq'])
    assert len(set(mapping.values()))==len(mapping)
    assert 'opaqueaq' not in mapping.values()
    assert mapping['room_3']!=mapping['room3']
    assert mapping['tool9']!=mapping['tool_9']
    assert choices[2]=='opaqueaq'


@pytest.mark.parametrize('header',[
    '', 'Events in chronological order:\n', 'Chronological events:\n',
])
def test_state_tracking_with_alphanumeric_names(header):
    answer=reply(header+'agent9 went to storage_2. agent9 picked up parcel_7. agent9 moved to lab3.\nWhere is parcel_7 now?',
                 ['storage_2','lab3','dock_9','hall8'])
    assert answer['choice']==1
    assert answer['route']=='chat/choice-helper-state'


def test_state_transfer_direction_is_preserved():
    options=['agent9','agent_9','another7','nobody']
    for giver,recipient in [('agent9','agent_9'),('agent_9','agent9')]:
        answer=reply(f'{giver} holds parcel_7. {giver} gives parcel_7 to {recipient}.\nWho holds parcel_7?',options)
        assert answer['choice']==options.index(recipient)


@pytest.mark.parametrize('context',[
    'agent9 holds parcel7. She gives it to agent2.\nWho holds parcel7?',
    'Events in reverse chronological order:\nagent9 went to lab2. agent9 went to hall3.\nWhere is agent9 now?',
    'agent9 went to lab2. Someone destroyed lab2.\nWhere is agent9 now?',
])
def test_ambiguous_chronology_and_pronouns_fall_through(context):
    assert reply(context,['agent9','agent2','lab2','hall3']) is None


@pytest.mark.parametrize('question,wanted',[
    ('Which item comes first?', 'box9'),('Which object is last?', 'crate_4'),
])
def test_existing_ordering_solver_can_use_explicit_precedence_edges(question,wanted):
    options=['crate_4','box9','vase2','can_8']
    answer=reply('vase2 comes after box9. vase2 is before can_8. crate_4 comes after can_8.\n'+question,options)
    assert answer['choice']==options.index(wanted)
    assert answer['route']=='chat/choice-helper-ordering'


@pytest.mark.parametrize('context,options',[
    ('a1 comes before b2. b2 comes before a1.\nWhich item comes first?', ['a1','b2']),
    ('a1 comes before b2. c3 comes before b2.\nWhich item comes first?', ['a1','b2','c3']),
    ('a1 is not before b2.\nWhich item comes first?', ['a1','b2']),
    ('a1 comes before b2.\nWhich item comes first?', ['a1','unlisted3']),
])
def test_ordering_ties_cycles_negation_and_unlisted_options_fall_through(context,options):
    assert reply(context,options) is None


def test_unified_calculator_is_used_before_statistical_ranking():
    from cael_unified.assistant import Assistant
    engine=Assistant()
    engine.score_endings=Mock(side_effect=AssertionError('An exact supported answer must not be statistically guessed'))
    answer=engine.respond([dict(role='user',content='Evaluate (14-5)*7.\nA) 64\nB) 63\nC) 62\nD) 61')],seed=7,mode='chat')
    assert answer['choice']==1
    assert answer['route']=='chat/choice-helper-arithmetic'
