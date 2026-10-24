"""Authored dependency, routing, provenance and bounded-execution regressions."""
import json
from unittest.mock import patch
import pytest
from cael_unified import orchestrator as o,verify
from cael_unified.helper import calculate

@pytest.fixture(autouse=True)
def no_persistent_stats(monkeypatch):
    original=verify.apply
    monkeypatch.setattr(verify,'apply',lambda text,answer:original(text,answer,record=False))


def code(source):return dict(route='chat/code-composed',response='```python\n'+source+'\n```')

def runner(answers):
    seen=[]
    def answer(text,history):
        seen.append(text)
        return answers[text] if text in answers else calculate(text)
    return answer,seen

@pytest.mark.parametrize('text',[
 'Translate "write a note, then explain it" into French',
 "Translate 'write a note, then explain it' into French",
 'Explain `first(); then run()`',
 'Mary went home, then John left. Where is Mary?',
 'What is it like to live in Japan?',
])
def test_plan_does_not_split_data_or_events(text):assert o.plan(text) is None


def test_real_sequence_outside_a_quote_still_plans():
    assert o.plan('Translate "write it, then run it" into French. Then count the words in it')==[
        'Translate "write it, then run it" into French','count the words in it']
    assert len(o.plan("What's 12*7? Then double it"))==2


def test_function_examples_are_data_even_when_name_is_a_command_word():
    text='Write a function named square\nsquare(2) == 4\nsquare(3) == 9. Then run it on 7'
    steps=o.plan(text)
    assert len(steps)==2 and 'square(2) == 4\nsquare(3) == 9' in steps[0]

@pytest.mark.parametrize('ref',['step 9','the result from step 9','part 2','the answer of part 0'])
def test_invalid_or_future_dependency_never_dispatches(ref):
    answer,seen=runner({})
    b=o.run(['calculate 20','double '+ref],answer)
    assert b.entries[-1].status=='skipped' and len(seen)==1
    assert b.entries[-1].value is None

@pytest.mark.parametrize('reply',[
 dict(route='helper/quantity-clarify',response='I cannot determine the count of 3 groups.'),
 dict(route='helper/undefined',response='Division by zero.'),
 dict(route='chat/reasoning-state',response='Unknown. Based on 1. and 2.',reasoning=dict(answer='unknown')),
 dict(route='chat/reasoning-logic',response='Conflicting.',reasoning=dict(answer='conflicting')),
 dict(route='chat/reasoning-state',response='Maybe.',reasoning=dict(answer='maybe')),
 dict(route='helper/equation',response='x = -2 or x = 2'),
 dict(route='chat/reasoning-several',response='There are 5 and 6.',reasoning=[dict(answer='5'),dict(answer='6')]),
])
def test_unknown_or_multi_result_is_not_replaced_with_an_older_number(reply):
    answer,seen=runner({'find count':reply})
    b=o.run(['calculate 20','find count','double it'],answer)
    assert b.entries[1].status=='uncertain'
    assert b.entries[2].status=='skipped' and len(seen)==2
    assert b.entries[2].dependencies==[2]


def test_explicit_old_value_can_bypass_a_failed_independent_step():
    answer,seen=runner({'find count':dict(route='chat/unsure',response='No answer.')})
    b=o.run(['calculate 20','find count','double the result from step 1'],answer)
    assert b.entries[-1].value=='40' and b.entries[-1].dependencies==[1]
    assert o.report(b)['plan_status']=='partial'


def test_failed_independent_verification_blocks_dependents(monkeypatch):
    monkeypatch.setattr(verify,'apply',lambda text,answer:dict(answer,verification=dict(status='failed',check='Fixture failure')))
    answer,seen=runner({})
    b=o.run(['calculate 20','double it'],answer)
    assert b.entries[0].status=='failed' and b.entries[1].status=='skipped' and len(seen)==1


def test_correction_is_the_value_used_downstream():
    answer,seen=runner({'calculate 2+3':dict(route='helper/arithmetic',response='2+3 = 6')})
    b=o.run(['calculate 2+3','double it'],answer)
    assert [e.value for e in b.entries]==['5','10']
    assert b.entries[0].verification['status']=='corrected'


def test_explanation_is_transparent_for_later_numeric_reference():
    b=o.run(['calculate 20','explain why','double it'],lambda text,history:calculate(text))
    assert b.entries[-1].value=='40' and b.entries[-1].dependencies==[1]
    assert b.entries[1].dependencies==[1]


def test_explain_explicit_step_and_failed_step():
    answer,seen=runner({'find count':dict(route='chat/unsure',response='No single count.')})
    b=o.run(['calculate 20','find count','explain step 1','explain step 2','explain step 9'],answer)
    assert b.entries[2].dependencies==[1]
    assert 'uncertain' in b.entries[3].response
    assert b.entries[-1].status=='skipped' and len(seen)==2


def test_callback_failure_does_not_abort_independent_steps_or_leak_exception_text():
    seen=[]
    def answer(text,history):
        seen.append(text)
        if text=='find count':raise ValueError('Synthetic private error detail')
        return calculate(text)
    b=o.run(['calculate 10','find count','double it','calculate 7','double it'],answer)
    assert [e.status for e in b.entries]==['ok','failed','skipped','ok','ok']
    assert b.entries[-1].value=='14'
    assert 'private error' not in o.report(b)['response']


def test_explicit_code_and_argument_references_choose_the_right_producers():
    answer,seen=runner({'write square':code('def square(n):\n    return n*n'),
                        'write triple':code('def triple(n):\n    return n*3')})
    b=o.run(['write square','write triple','calculate 7',
             'run the function from step 1 on the result from step 3'],answer)
    assert b.entries[-1].value==49 and b.entries[-1].dependencies==[1,3]
    assert b.entries[-1].resolved_request=='run the function on 7'
    assert len(seen)==3


def test_code_call_no_longer_searches_past_latest_incompatible_result():
    answer,seen=runner({'write square':code('def square(n):\n    return n*n')})
    b=o.run(['write square','calculate 5','run it on 3'],answer)
    assert b.entries[-1].status=='skipped' and len(seen)==2

@pytest.mark.parametrize('prompt,expected',[
 ('run it on "bread and butter"','bread and butter'),
 ('run it on ["one and two", 3]',['one and two',3]),
 ('run it on {"x": [1, 2]}',{'x':[1,2]}),
 ('run it on x="a and b"','a and b'),
 ('run it on None',None),
 ('run it on False',False),
])
def test_literal_arguments_are_not_rewritten(prompt,expected):
    answer,seen=runner({'write echo':code('def echo(x):\n    return x')})
    b=o.run(['write echo',prompt],answer)
    assert b.entries[-1].status=='ok' and b.entries[-1].value==expected
    json.dumps(o.report(b))


def test_multiple_arguments_and_keywords():
    answer,seen=runner({'write add':code('def add(a,b=1):\n    return a+b')})
    b=o.run(['write add','run it on 3 and 4','run the function from step 1 on 3, b=7'],answer)
    assert [e.value for e in b.entries[1:]]==[7,10]


def test_literal_result_can_feed_a_later_code_tool():
    answer,seen=runner({'write echo':code('def echo(x):\n    return x'),
                        'write length':code('def length(x):\n    return len(x)')})
    b=o.run(['write echo','run it on [1,2,3]','write length',
             'run the function from step 3 on the result from step 2'],answer)
    assert b.entries[-1].value==3 and b.entries[1].kind=='literal'


def test_string_result_is_quoted_when_used_as_a_code_argument():
    answer,seen=runner({'write echo':code('def echo(x):\n    return x'),
                       'reverse the word banana':dict(route='chat/reasoning-words',response='**banana** backwards is **ananab**.')})
    b=o.run(['write echo','reverse the word banana','run the function from step 1 on the result from step 2'],answer)
    assert b.entries[-1].value=='ananab' and b.entries[-1].dependencies==[1,2]


def test_word_count_result_is_a_number_not_the_input_word():
    answer,seen=runner({'count letters':dict(route='chat/reasoning-words',response='**luma** has **4** letters.')})
    b=o.run(['count letters','double it'],answer)
    assert [e.value for e in b.entries]==['4','8']


def test_failed_code_verification_is_not_overridden_by_the_plan():
    reply=code('def echo(x):\n    return x')
    reply['verification']=dict(status='failed',check='Fixture code failure')
    answer,seen=runner({'write echo':reply})
    b=o.run(['write echo','run it on 1'],answer)
    assert b.entries[0].status=='failed' and b.entries[1].status=='skipped' and len(seen)==1

@pytest.mark.parametrize('source',[
 'import math\ndef f(x):\n    return math.sqrt(x)',
 'def f(x):\n    while True:\n        pass',
 'def f(x):\n    return 10**100000',
])
def test_no_native_execution_fallback_after_unsupported_or_limit(source):
    answer,seen=runner({'write function':code(source)})
    with patch('builtins.exec',side_effect=AssertionError('Native execution forbidden')) as native:
        b=o.run(['write function','run it on 4','double it'],answer)
    assert native.call_count==0
    assert b.entries[1].status=='failed' and b.entries[2].status=='skipped'


def test_python_exception_blocks_only_dependents():
    answer,seen=runner({'write function':code('def f(x):\n    return 1/x')})
    b=o.run(['write function','run it on 0','double it','calculate 9'],answer)
    assert b.entries[1].status=='failed' and 'ZeroDivisionError' in b.entries[1].response
    assert b.entries[2].status=='skipped' and b.entries[3].value=='9'


def test_protected_references_and_fresh_literal_words():
    board=o.Board();board.add(o.Entry(1,'calculate 20','helper/arithmetic','','number','20'))
    assert o.resolve('Translate "it and the result from step 9" into French',board)[0]=='Translate "it and the result from step 9" into French'
    assert o.resolve('Spell the word banana backwards',board)[0]=='Spell the word banana backwards'
    assert o.resolve('Is it raining?',board)[0]=='Is it raining?'
    assert o.resolve('Translate this: hello',board)[0]=='Translate this: hello'


def test_conversion_passes_converted_value_not_source_value():
    b=o.run(['convert 2 m to cm','halve it'],lambda text,history:calculate(text))
    assert [e.value for e in b.entries]==['200','100']


def test_sources_are_preserved_per_step_and_deduplicated_in_report():
    source=dict(title='Authored fixture',url='https://example.test/fact')
    answer,seen=runner({'find fact':dict(route='chat/web-wikidata-faq',response='The capital of France is Paris.',sources=[source])})
    b=o.run(['find fact','explain why'],answer);report=o.report(b)
    assert report['sources']==[source]
    assert all(step['sources']==[source] for step in report['plan'])
    assert report['plan_status']=='complete' and report['execution_summary']['ok']==2

@pytest.mark.parametrize('steps',[[],['calculate 1']*7])
def test_run_bound_is_enforced(steps):
    with pytest.raises(ValueError):o.run(steps,lambda text,history:calculate(text))
