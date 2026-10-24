"""Authored pure task construction/use and structured-tool integration."""
import copy
import hashlib
from unittest.mock import patch
import pytest
from cael_unified.codegen.python_tasks import reply,owns,protect_input
from cael_unified.codegen.chat import reply as code_reply
from cael_unified.codegen.tool_contract import read
from cael_unified.codegen.python_vm import run_cases
from cael_unified import orchestrator as o,verify
from cael_unified.helper import calculate

@pytest.fixture(autouse=True)
def isolate_statistics(monkeypatch):
    original=verify.apply
    monkeypatch.setattr(verify,'apply',lambda text,answer:original(text,answer,record=False))


def task(steps,value,domain=''):
    return 'Use Python'+(' for '+domain if domain else '')+' to '+steps+'\nInput: '+repr(value)

@pytest.mark.parametrize('steps,reference',[
 ('keep positive values; square each value; sum',lambda xs:sum(x*x for x in xs if x>0)),
 ('map x*3+2; keep even values; take the last 2 values',lambda xs:[x*3+2 for x in xs if (x*3+2)%2==0][-2:]),
 ('remove duplicates; sort descending; take the first 3 values',lambda xs:sorted(set(xs),reverse=True)[:3]),
 ('sum each full window of size 2; sum',lambda xs:sum(sum(xs[i:i+2]) for i in range(len(xs)-1))),
 ('keep odd values; count',lambda xs:sum(x%2!=0 for x in xs)),
])
def test_integer_tasks_match_independent_oracles_and_compiled_function(steps,reference):
    for xs in ([],[-4,3,0,3,2],[1,2,3,4]):
        before=copy.deepcopy(xs);answer=reply(task(steps,xs))
        assert answer['route']=='chat/code-python-task-used',answer
        assert answer['tool_result']['value']==reference(xs) and xs==before
        artifact=read(answer['python_tool'])
        assert artifact['entrypoint']=='process_task'
        assert artifact['sha256']==hashlib.sha256(artifact['source'].encode()).hexdigest()
        assert run_cases(artifact['source'],[dict(name=artifact['entrypoint'],args=[xs])])['cases'][0]['value']==reference(xs)

@pytest.mark.parametrize('message,expected',[
 ('Sum of squares of positive numbers in [-2,3,4]',25),
 ('Calculate the product of cubes of odd integers in [2,3,-1]',-27),
 ('Find sum of absolute values of negative values in [-2,3,-5]',7),
])
def test_small_natural_semantic_requests_construct_tools(message,expected):
    assert reply(message)['tool_result']['value']==expected

@pytest.mark.parametrize('value,steps,expected',[
 (' A\nB\n',['split lines','strip each value','casefold each value','keep nonempty values','join with "|"'],'a|b'),
 ('A a b',['split words','casefold each value','count by x'],{'a':2,'b':1}),
 ('a;b c',['split on ";"','join with " and then "'],'a and then b c'),
 ([{'team':'a','qty':2,'active':True},{'team':'b','qty':9,'active':False}],
  ['keep where x["active"]','sum x["qty"] by x["team"]'],{'a':2}),
 ([{'name':'B','qty':1},{'name':'A','qty':3}],['select fields ["name","qty"]','sort by x["qty"] descending'],[{'name':'A','qty':3},{'name':'B','qty':1}]),
])
def test_record_and_text_workflows(value,steps,expected):
    answer=reply(task('; '.join(steps),value))
    assert answer['tool_result']['value']==expected,answer


def test_same_conversation_can_reuse_and_review_but_does_not_install_tool():
    text=task('keep positive values; square each value; sum',[2,-3]);answer=reply(text)
    history=[dict(role='user',content=text),dict(role='assistant',content=answer['response'])]
    for query,expected in [('Use it on [3,-2,4]',25),('Show the tool',None),('Use it on []',0)]:
        history.append(dict(role='user',content=query));result=reply(query,history)
        if query.startswith('Show'):
            assert 'def process_task(' in result['response'] and 'tool_result' not in result
        else:assert result['tool_result']['value']==expected
        history.append(dict(role='assistant',content=result['response']))
    assert reply('Use it on [9]') is None
    unrelated=history+[dict(role='user',content='Hello'),dict(role='assistant',content='Hi!'),dict(role='user',content='Use it on [9]')]
    assert reply('Use it on [9]',unrelated) is None

@pytest.mark.parametrize('message',[
 'Use Python to sum',
 'Use Python to keep positive values except 3; sum\nInput: [3,4]',
 'Use Python to sum; reverse\nInput: [3,4]',
 'Use Python to read private_photo.jpg\nInput: []',
 'Use Python to map open(x)\nInput: [1]',
 'Use Python to map x.__class__\nInput: [1]',
 'Use Python to map x**999\nInput: [1]',
 'Use Python to map x+1\nInput: __import__("os")',
 'Use Python to sum\nInput: [1.5]',
 'Use Python to sum\nInput: [True]',
 'Use Python to sum\nInput: [1]\nInput: [2]',
])
def test_unsupported_or_ambiguous_requests_never_claim_a_completed_result(message):
    with patch('builtins.exec',side_effect=AssertionError('No native execution')):
        answer=reply(message)
    assert answer and answer['route'].endswith(('-clarify','-unsupported','-execution-error'))
    assert 'tool_result' not in answer and 'python_tool' not in answer


def test_data_size_and_execution_errors_are_not_success():
    for message in (task('sum',list(range(41))),task('minimum',[]),task('map 10//x',[0])):
        answer=reply(message)
        assert 'tool_result' not in answer


def test_tool_source_and_result_are_preserved_separately_across_plan_steps():
    first=task('keep positive values; square each value; sum',[-2,3,4])
    board=o.run([first,'double it','run the function from step 1 on [1,2]'],
                lambda text,history:code_reply(text,messages=history) or calculate(text))
    assert [e.value for e in board.entries]==['25','50',5]
    assert board.entries[-1].dependencies==[1]
    assert board.entries[0].tool['entrypoint']=='process_task'


def test_old_integer_compiler_reuses_public_function_not_first_guard():
    prompt='Build a Python tool named weighted for integer lists.\nSteps:\nmap x*3\nsum'
    board=o.run([prompt,'run the function from step 1 on [1,2]'],lambda text,history:code_reply(text,messages=history))
    assert board.entries[-1].value==9 and 'weighted(' in board.entries[-1].response


def test_old_data_compiler_reuses_public_function_not_first_guard():
    prompt='Build a Python tool named quantity for records.\nSteps:\nsum x["qty"]'
    board=o.run([prompt,'run the function from step 1 on [{"qty":3},{"qty":5}]'],lambda text,history:code_reply(text,messages=history))
    assert board.entries[-1].value==8


def test_result_none_and_false_are_real_values_not_absence():
    # Data tools can return arbitrary literal expression values as elements.
    a=reply(task('map {"flag": False, "value": None}',[{'x':1}]))
    assert a['tool_result']['value']==[{'flag':False,'value':None}]


def test_invalid_source_checksum_and_wrong_result_source_block_dependents():
    first=reply(task('sum',[1,2]))
    for target in ('python_tool','tool_result'):
        altered=copy.deepcopy(first)
        if target=='python_tool':altered[target]['source']+='\n# tampered'
        else:altered[target]['source_sha256']='0'*64
        board=o.run(['use data','double it'],lambda text,history:altered)
        assert board.entries[0].status=='failed' and board.entries[1].status=='skipped'


def test_artifact_verification_does_not_execute_source_natively():
    answer=reply(task('sum',[1,2]))
    with patch('builtins.exec',side_effect=AssertionError('Native execution forbidden')) as native:
        checked=verify.check('synthetic task',answer)
    assert native.call_count==0 and checked['status']=='unchecked'


def test_unrelated_language_math_and_code_are_not_intercepted():
    for text in ('Hello','What is Python?','Write a Python function to count vowels','Explain this Python code: x=2','Sum the squares of numbers unless it rains'):
        assert reply(text) is None
    assert protect_input(task('count by x','helo helo'))
