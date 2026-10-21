import ast
import random

from cael_unified.codegen.toolmaker import build,reply
from cael_unified.codegen.python_vm import run_cases


def test_compound_helper_is_derived_with_arbitrary_field_names():
    arrays=[[],[0],[-2],[1,2],[1,-1,3],[-2,4,-3,5],[2,2,-1,0]]
    cases=[((values,),{'violet':sum(values),'cloud':sum(x>0 for x in values)}) for values in arrays]
    result=build('derive',cases)
    assert result['status']=='built',result
    assert 'state_0' in result['source'] and 'state_1' in result['source']
    rng=random.Random(712)
    for _ in range(20):
        values=[rng.randint(-7,8) for _ in range(rng.randint(0,15))]
        actual=run_cases(result['source'],[dict(name='derive',args=[values])])
        assert actual['cases'][0]['value']=={'violet':sum(values),'cloud':sum(x>0 for x in values)}


def test_tuple_and_running_field_compose_without_saved_function():
    arrays=[[],[0],[1,-2,4],[-3,2,0,4],[2,3,-1]]
    def expected(xs):
        total=0;prefix=[]
        for x in xs:total+=x;prefix.append(total)
        return (sum(x*x for x in xs),prefix)
    result=build('custom',[( (xs,),expected(xs)) for xs in arrays])
    assert result['status']=='built',result
    xs=[7,-2,3]
    assert run_cases(result['source'],[dict(name='custom',args=[xs])])['cases'][0]['value']==expected(xs)


def test_weak_compound_examples_request_a_distinguishing_input():
    cases=[(([2],),{'a':2,'b':1}),(([3],),{'a':3,'b':1})]
    result=build('weak',cases)
    assert result['status']=='ambiguous'
    assert result['predictions'][0]!=result['predictions'][1]


def test_schema_labels_do_not_select_the_algorithm():
    arrays=[[],[0],[-2],[1,2],[1,-1,3],[-2,4,-3,5],[-3,-3]]
    cases=[((xs,),{'count':sum(xs),'sum':sum(x>0 for x in xs)}) for xs in arrays]
    result=build('counterintuitive',cases)
    assert result['status']=='built',result
    assert run_cases(result['source'],[dict(name='counterintuitive',args=[[2,-3,7]])])['cases'][0]['value']=={'count':6,'sum':2}


def test_constructed_helper_can_be_used_on_a_new_literal_input():
    from cael_unified.codegen.chat import reply as chat_reply
    text='Create a Python helper.\n'
    for xs in [[],[0],[-2],[1,2],[1,-1,3],[-2,4,-3,5],[-3,-3]]:
        text+=f"novel({xs!r}) == {{'a': {sum(xs)}, 'b': {sum(x>0 for x in xs)}}}\n"
    text+='Use it on [4,-1,2]'
    answer=chat_reply(text)
    assert answer['route']=='chat/code-tool-synthesized',answer
    assert "{'a': 5, 'b': 2}" in answer['response']


def test_unknown_or_coupled_domain_is_not_claimed_as_a_tool():
    assert build('f',[((1,),{'a':1,'b':2}),((2,),{'a':2,'b':3})])['status']=='outside-domain'
    assert build('f',[(([1],),{'a':'x','b':2}),(([2],),{'a':'y','b':3})])['status']=='not-found'


def test_compound_ambiguity_can_be_resolved_in_a_followup():
    from cael_unified.codegen.chat import reply as chat_reply
    first='Create a Python helper.\n'
    for xs in [[],[0],[-2],[1,2],[1,-1,3],[-2,4,-3,5]]:
        first+=f"resolved({xs!r}) == {{'a': {sum(xs)}, 'b': {sum(x>0 for x in xs)}}}\n"
    question=chat_reply(first)
    assert question['route']=='chat/code-tool-clarify',question
    follow="resolved([-3,-3]) == {'a': -6, 'b': 0}"
    answer=chat_reply(follow,messages=[dict(role='user',content=first),dict(role='assistant',content=question['response']),dict(role='user',content=follow)])
    assert answer['route']=='chat/code-tool-synthesized',answer
