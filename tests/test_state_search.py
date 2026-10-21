"""Locally authored development specifications, not external benchmark cases."""
import ast
import random

import pytest

from cael_unified.codegen.state_search import (
    Expr, OutsideDomain, Program, X, S, ZERO, condition, grammar, node, synthesize,
)
from cael_unified.codegen.chat import reply


def generated(program, name='derived'):
    code=program.render(name)
    ns={}
    # Only CAEL's own grammar-generated AST is executed in tests.
    exec(compile(ast.parse(code),'<CAEL-generated-test>','exec'),ns)
    return ns[name]


def test_grammar_has_no_named_algorithm_dispatch():
    a,_=grammar('A completely arbitrary function called marigold')
    b,_=grammar('Find the longest consecutive streak')
    assert a==b


@pytest.mark.parametrize('update,projection,initial',[
    (node('+',S,X),'scan',0),
    (node('*',S,X),'last',1),
    (node('if',node('>',X,ZERO),node('+',S,node('const',1)),ZERO),'max',0),
    (node('+',S,node('*',X,node('+',node('var','index'),node('const',1)))),'scan',0),
    (node('-',X,node('var','previous')),'scan',0),
])
def test_emitted_function_matches_independent_ir(update,projection,initial):
    program=Program(initial,update,projection);fn=generated(program)
    rng=random.Random(8827)
    for _ in range(60):
        values=[rng.randint(-4,5) for _ in range(rng.randint(0,12))]
        assert fn(values)==program.run(values)


def test_search_infers_a_loop_and_generalises_to_new_lengths():
    cases=[(([],),[]), (([2,-1,3],),[2,1,4]), (([-2,0,1,-4],),[-2,-2,-1,-5])]
    result=synthesize(cases,seconds=5)
    assert result['status']=='synthesized',result
    fn=generated(result['program'])
    assert fn([4,5,-2,0,8])==[4,9,7,7,15]
    assert result['stats']['programs']>1
    assert result['stats']['complete']


def test_search_infers_conditional_state_and_projection():
    cases=[(([],),0), (([2,-1,3,4],),2), (([-2,0,1,2,3,-1,4],),3), (([0,-1],),0), (([-3],),0)]
    result=synthesize(cases,seconds=5)
    assert result['status']=='synthesized',result
    assert generated(result['program'])([9,8,-4,1,2,3,4,0])==4


def test_ambiguity_produces_a_counterexample_input():
    cases=[(([2],),[2]), (([3],),[3])]
    result=synthesize(cases,seconds=5)
    assert result['status']=='ambiguous'
    assert result['predictions'][0]!=result['predictions'][1]


@pytest.mark.parametrize('cases',[
    [(([True],),1), (([False],),0)],
    [(([1.0],),1), (([2.0],),2)],
    [(([1],2),1), (([2],3),2)],
    [(([1],),'a'), (([2],),'b')],
    [(([1]*41,),1), (([],),0)],
])
def test_outside_domain_is_refused(cases):
    assert synthesize(cases)['status']=='outside-domain'


def test_bounded_search_does_not_guess_when_incomplete():
    cases=[(([1,2],),[1,3]), (([2,4],),[2,6])]
    assert synthesize(cases,max_programs=1)['status']=='search-limit'


@pytest.mark.parametrize('formula',[
    '__import__("os").system("echo unwanted")', 'value.__class__',
    'value % 0 == 0', '[x for x in range(100)]', '1',
])
def test_condition_reader_rejects_unsafe_or_nonboolean_forms(formula):
    with pytest.raises((OutsideDomain,SyntaxError)):
        condition(formula)


def test_boolean_condition_composes_and_render_is_safe():
    expr=condition('value > 2 and value % 3 == 0')
    assert expr.read({'value':6}) is True
    assert expr.read({'value':2}) is False
    with pytest.raises(OutsideDomain):
        Program(0,S,'last').render('bad():\n import os')


def test_runtime_domain_and_overflow_agree():
    p=Program(1,node('*',S,X),'last');fn=generated(p)
    for values in [[True],[1.1],[10**7],[10**6]*4]:
        with pytest.raises(ValueError):fn(values)
        with pytest.raises(OutsideDomain):p.run(values)


@pytest.mark.parametrize('name',['len','max','type','ValueError','_hidden','class','a'*81])
def test_names_cannot_break_generated_scope(name):
    with pytest.raises(OutsideDomain):Program(0,node('+',S,X),'scan').render(name)


def test_described_function_name_cannot_shadow_runtime_builtins():
    answer=reply('Write a Python function named len for cumulative sum of numbers.')
    assert answer['route']=='chat/code-state-clarify'


def test_actual_chat_builds_a_new_loop():
    answer=reply('Write a Python function for running totals. '
                 'folded([]) == []\nfolded([2,-1,3]) == [2,1,4]\n'
                 'folded([-2,0,1,-4]) == [-2,-2,-1,-5]')
    assert answer['route']=='chat/code-state-synthesized',answer
    assert 'for index, value in enumerate(numbers)' in answer['response']


def test_stateful_description_preserves_running_output():
    answer=reply('Write a Python function that returns the cumulative sum of a list.')
    assert answer['route']=='chat/code-state-planned'
    ns={};exec(answer['response'].split('```python\n')[1].split('```')[0],ns)
    assert ns['process_stream']([2,-1,3])==[2,1,4]


@pytest.mark.parametrize('prompt,values,expected',[
    ('cumulative sum of squared positive numbers',[2,-3,4,0],[4,4,20,20]),
    ('running product of even numbers',[2,3,4,0],[2,2,8,0]),
    ('running total of numbers, reset to 0 on negative',[2,3,-4,5],[2,5,0,5]),
    ('longest consecutive count of even numbers',[2,4,1,6,8,10,3],3),
    ('running maximum of numbers starting at -5',[-3,-4,0,-2],[-3,-3,0,0]),
    ('cumulative sum of absolute numbers starting at 3',[-2,4,-1],[5,9,10]),
    ('cumulative count of positive even numbers',[2,-2,3,4],[1,1,1,2]),
])
def test_description_plan_composes_primitives(prompt,values,expected):
    answer=reply('Write a Python function named cobalt for '+prompt+'.')
    assert answer['route']=='chat/code-state-planned',answer
    ns={};exec(answer['response'].split('```python\n')[1].split('```')[0],ns)
    assert ns['cobalt'](values)==expected


@pytest.mark.parametrize('prompt',[
    'cumulative sum but skip negative numbers',
    'running maximum of numbers',
    'cumulative sum of squares and cubes of numbers',
    'running count of positive or negative and even numbers',
    'cumulative sum of numbers, reset whenever it feels right',
    'cumulative mean of numbers',
    'running total of sorted numbers',
    'cumulative sum of the first 3 values',
    'running product of numbers without using a loop',
])
def test_unsupported_description_is_not_silently_ignored(prompt):
    answer=reply('Write a Python function for '+prompt+'.')
    assert answer['route']=='chat/code-state-clarify',answer
    assert '```python' not in answer['response']


def test_counterexample_answer_extends_only_the_same_function():
    first='Write a Python function for running values. inferred([2]) == [2]\ninferred([3]) == [3]'
    question=reply(first)
    assert question['route']=='chat/code-state-clarify'
    follow='inferred([2,-1,3]) == [2,1,4]\ninferred([]) == []'
    answer=reply(follow,messages=[{'role':'user','content':first},{'role':'assistant','content':question['response']},{'role':'user','content':follow}])
    assert answer['route']=='chat/code-state-synthesized',answer
    unrelated='another([2,-1]) == [2,1]'
    answer=reply(unrelated,messages=[{'role':'user','content':first},{'role':'assistant','content':question['response']},{'role':'user','content':unrelated}])
    assert answer is None
