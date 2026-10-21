"""Authored specifications: emitted tools checked independently with CPython."""
import ast
import copy
import random
import re

import pytest

from cael_unified.codegen import task_tools as tools
from cael_unified.codegen.chat import reply


def prompt(steps,source='',use=None,name='process'):
    text='Build a Python tool named '+name+' for integer lists.\n'
    if source:text+='```python\n'+source+'\n```\n'
    text+='Steps:\n'+'\n'.join(steps)
    if use is not None:text+='\nUse it on '+repr(use)
    return text


def prefixes(xs):
    total=0;result=[]
    for x in xs:total+=x;result.append(total)
    return result


OPERATIONS=[
    (['keep positive values','square each value','return the sum'],lambda xs:sum(x*x for x in xs if x>0)),
    (['square each value','keep positive values','return the sum'],lambda xs:sum(x*x for x in xs if x*x>0)),
    (['map x*3+2','keep where x % 2 == 0','take the last 2 values'],lambda xs:[x*3+2 for x in xs if (x*3+2)%2==0][-2:]),
    (['sum each full window of size 3','reverse','take the first 2 values'],lambda xs:[sum(xs[i:i+3]) for i in range(len(xs)-2)][::-1][:2]),
    (['running totals','remove duplicates preserving order','sort descending'],lambda xs:sorted(set(prefixes(xs)),reverse=True)),
    (['map abs(x)','remove duplicates','return the count'],lambda xs:len(set(abs(x) for x in xs))),
    (['scan max(state,x) starting at -5','return the values'],lambda xs:[max([-5,*xs[:i+1]]) for i in range(len(xs))]),
    (['reduce state + x*x starting at 3'],lambda xs:3+sum(x*x for x in xs)),
    (['take the last 0 values','return the sum'],lambda xs:0),
    (['keep above 2','map x if x < 5 else 5','product'],lambda xs:__import__('math').prod(min(x,5) for x in xs if x>2)),
    (['keep odd values','take the first 4 values','prefix sums'],lambda xs:prefixes([x for x in xs if x%2][:4])),
    (['map x**2','keep at least 4','return the minimum'],lambda xs:min(x*x for x in xs if x*x>=4)),
]


@pytest.mark.parametrize('steps,reference',OPERATIONS)
def test_composed_tools_match_independent_references_and_do_not_mutate_inputs(steps,reference):
    parsed=tools.parse(prompt(steps));built=tools.build(parsed)
    assert built['status']=='built',built
    # Native exec only executes this file's authored tool fixtures.
    scope={};exec(built['source'],scope);function=scope['process']
    rng=random.Random(3517)
    for xs in [[],[0],[-3,-2,4,1,4],*[rng.choices(range(-5,7),k=rng.randrange(15)) for _ in range(15)]]:
        snapshot=copy.deepcopy(xs)
        try:expected=reference(xs)
        except ValueError:
            with pytest.raises(ValueError):function(xs)
        else:assert function(xs)==expected
        assert xs==snapshot


def test_custom_code_is_reused_by_signature_not_function_name():
    source='def invented(x):\n    return x*x-2\ndef unrelated(acc,item):\n    return max(acc+item,0)'
    answer=reply(prompt(['map using invented','scan using unrelated starting at 1','return the sum'],source,[2,-3,0]))
    assert answer['route']=='chat/code-task-tool-built',answer
    assert 'invented(x)' in answer['response'] and 'unrelated(state, x)' in answer['response']
    assert 'Used on [2, -3, 0]:\n```text\n21\n```' in answer['response'],answer


def test_helper_calls_can_reference_another_supplied_function():
    source='def delta(x):\n    return x*2\ndef weight(x):\n    return delta(x)+3'
    answer=reply(prompt(['map using weight','sum'],source,[1,3]))
    assert answer['route']=='chat/code-task-tool-built' and '\n14\n' in answer['response'],answer


def test_filter_helper_and_explicit_reducer():
    source='def accept(x):\n    return x > 1\ndef combine(total,x):\n    return total*2+x'
    answer=reply(prompt(['keep using accept','reduce using combine starting at 0'],source,[0,2,3]))
    assert answer['route']=='chat/code-task-tool-built' and '\n7\n' in answer['response'],answer


def test_contradictory_example_prevents_emitting_code():
    answer=reply(prompt(['keep positive values','sum'])+'\nprocess([-2,3]) == 1')
    assert answer['route']=='chat/code-task-tool-contradiction',answer
    assert '```python' not in answer['response']


def test_empty_min_is_an_error_not_a_successful_task_result():
    answer=reply(prompt(['minimum'],use=[]))
    assert answer['route']=='chat/code-task-tool-execution-error' and 'ValueError' in answer['response'],answer
    assert '```python' not in answer['response']


def test_multi_turn_use_rebuilds_active_specification_including_helpers():
    request=prompt(['map using mystery','prefix sums'],'def mystery(x):\n    return x+3')
    first=reply(request);history=[dict(role='user',content=request),dict(role='assistant',content=first['response'])]
    for use,expected in [([1,2],[4,9]),([-3,1],[0,4])]:
        text='Use it on '+repr(use);history.append(dict(role='user',content=text))
        result=reply(text,messages=history)
        assert result['route']=='chat/code-task-tool-used' and '\n'+repr(expected)+'\n' in result['response'],result
        history.append(dict(role='assistant',content=result['response']))
    # There is no global installed tool or cross-session source cache.
    assert tools.reply('Use it on [1,2]') is None


@pytest.mark.parametrize('steps',[
    ['sum','square each value'],['sum','return the sum'],
    ['keep positive values except 3','sum'],['rolling sums of size 3'],
    ['sort descending except the first value'],['map open(x)'],
    ['map x.__class__'],['map x**99'],['map x+101'],
    ['sum each full window of size 0'],['keep last 99 values'],
    ['reduce state+x'],['scan using f'],['filter x>0 or x=="a"'],
    ['map using f','sum'],['remove duplicates and sort'],
])
def test_ambiguous_unsupported_and_ill_typed_steps_never_emit_claimed_success(steps):
    answer=reply(prompt(steps))
    assert answer['route']=='chat/code-task-tool-clarify',answer
    assert '```python' not in answer['response']


@pytest.mark.parametrize('source,steps',[
    ('def f(x,y):\n    return x+y',['map using f']),
    ('def f(x,cache=[]):\n    cache.append(x)\n    return x',['map using f']),
    ('import os\ndef f(x): return x',['map using f']),
    ('def f(x): return open("never_open_this_file").read()',['map using f']),
    ('def f(x):\n    while True: pass',['map using f']),
    ('def sum(x): return x',['map using sum']),
])
def test_unsafe_or_unsupported_helpers_are_not_run_natively_or_installed(source,steps):
    answer=reply(prompt(steps,source,[1,2]))
    assert answer['route'] in {'chat/code-task-tool-clarify','chat/code-task-tool-unsupported'},answer
    assert '```python' not in answer['response']


@pytest.mark.parametrize('use',[[True],['x'],list(range(41)),[1000001]])
def test_invalid_data_is_declined(use):
    answer=reply(prompt(['sum'],use=use))
    assert answer['route']=='chat/code-task-tool-clarify',answer


@pytest.mark.parametrize('heading',['Build a Python tool without loops.','Build a Python tool for strings.','Build a Python tool using pandas.'])
def test_heading_constraints_are_not_silently_dropped(heading):
    answer=reply(heading+'\nSteps:\nsum')
    assert answer['route']=='chat/code-task-tool-clarify',answer


def test_unrelated_explanation_and_existing_helper_requests_are_not_hijacked():
    assert tools.reply('Explain this Python code:\n```python\ndef steps(x): return x+1\n```') is None
    assert tools.reply('Create a Python helper.\nf([1]) == 1\nf([2]) == 2') is None


def test_automatic_planner_reuses_unfamiliar_code_to_build_and_use_new_tool():
    request='Build a Python tool named invented_task from these examples.\n```python\ndef unknown(x):\n    return x*x+3\n```\n'
    arrays=[[],[0],[1],[-2,3],[0,1,2],[-1,-3,2,2]]
    request+='\n'.join('invented_task('+repr(xs)+') == '+str(sum(x*x+3 for x in xs)) for xs in arrays)
    request+='\nUse it on [3,-1]'
    answer=reply(request)
    assert answer['route']=='chat/code-task-tool-built',answer
    assert 'unknown(x)' in answer['response'] and '\n16\n' in answer['response'],answer
    code=re.search(r'```python\n(.*?)```',answer['response'],re.S)[1]
    scope={};exec(code,scope)
    assert scope['invented_task']([8,-4,0])==89


def test_automatic_plan_clarification_keeps_examples_across_multiple_turns():
    request='Build a Python tool named f.\nf([]) == []\nf([1]) == [1]\nf([2,3]) == [2,3]'
    history=[dict(role='user',content=request)]
    answer=reply(request)
    assert answer['response'].startswith(tools.QUESTION),answer
    # Identity specification supplies the requested distinguishing cases.
    for _ in range(4):
        if answer['route']=='chat/code-task-tool-built':break
        witness=ast.literal_eval(re.search(r'`f\((.*?)\)`',answer['response'])[1])
        history.append(dict(role='assistant',content=answer['response']))
        text='f('+repr(witness)+') == '+repr(witness);history.append(dict(role='user',content=text))
        answer=reply(text,messages=history)
    assert answer['route']=='chat/code-task-tool-built',answer


def test_search_failure_does_not_fall_back_to_unverified_code():
    text='Build a Python tool named f.\nf([]) == 17\nf([0]) == 19\nf([3]) == 99'
    answer=reply(text)
    assert answer['route']=='chat/code-task-tool-not-found' and '```python' not in answer['response'],answer


@pytest.mark.parametrize('source',[
    'def f(x):\n    if x>100: return open("never_opened").read()\n    return x',
    'def f(x):\n    if x>100: return eval("x")\n    return x',
    'def f(x):\n    if x>100: return x.__class__\n    return x',
])
def test_unreached_external_capabilities_are_not_emitted_in_a_successful_tool(source):
    answer=reply(prompt(['map using f'],source,[1,2]))
    assert answer['route']=='chat/code-task-tool-clarify' and '```python' not in answer['response'],answer
