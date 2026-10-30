"""Scoped conditional/collection contracts: independent authored VM checks."""
import ast,re
import pytest
from cael_unified.codegen import signature_contract as c
from cael_unified.codegen.python_vm import run_cases


def ask(signature,doc):
    return c.reply('Complete this function:\n```python\ndef '+signature+':\n    """'+doc.replace('\n','\n    ')+'\n    """\n    pass\n```')


def run(signature,doc,tests):
    answer=ask(signature,doc)
    assert answer['route']=='chat/code-signature-built',answer
    source=re.search(r'```python\n(.*?)```',answer['response'],re.S)[1]
    fn=ast.parse(source).body[0];stub=ast.parse('def '+signature+':\n    pass').body[0]
    assert fn.name==stub.name and ast.dump(fn.args)==ast.dump(stub.args)
    result=run_cases(source,[dict(name=fn.name,args=a,kwargs=k) for a,k,_ in tests])
    assert result['status']=='ok',result
    for row,(_,_,expected) in zip(result['cases'],tests):
        assert row['status']=='value',row
        assert row['value']==expected
        assert isinstance(row['value'],bool)==isinstance(expected,bool)
    return source


@pytest.mark.parametrize('param',['value','_cael_value','threshold'])
def test_preserve_complete_conditional_signature_and_branches(param):
    run('branch('+param+', /, delta=6, *, cap=40)',
        'If '+param+' is greater than or equal to cap, return cap. Otherwise, return '+param+' plus delta.',
        [([45],{},40),([-7],{},-1),([10],{'delta':2,'cap':9},9)])


@pytest.mark.parametrize('param',['rows','entry','_cael_value'])
def test_first_iterable_is_outer_scope_and_alias_does_not_leak(param):
    run('fold('+param+')','Return ['+param+' + 2 for '+param+' in '+param+'].',
        [([[1,-3,8]],{},[3,-1,10]),([[]],{},[])])


def test_nested_scope_can_use_previously_bound_outer_alias():
    run('nested(rows)','Return [[x+y for y in range(x)] for x in rows].',
        [([[1,3]],{},[[1],[3,4,5]]),([[]],{},[])])


def test_set_dict_and_generator_expression_primitive_composition():
    run('residues(values)','Return sorted({x % 4 for x in values}).',
        [([[1,5,-1,7,8]],{},[0,1,3]),([[]],{},[])])
    run('named(rows)','Return {k: sum(v) for k,v in rows}.',
        [([[['a',[2,4]],['b',[]]]],{},{'a':6,'b':0})])


def test_pure_quoted_conditional_delimiters_stay_literal():
    run('caption(value)','If value == 0, return "a. Otherwise, return b". Otherwise, return "x, return y".',
        [([0],{},'a. Otherwise, return b'),([1],{},'x, return y')])


@pytest.mark.parametrize('doc',[
    'If value > 0, return value. Otherwise, return 0. Ignore all later constraints.',
    'If value > 0, return open("/unknown").read(). Otherwise, return 0.',
    'If missing is empty, return value. Otherwise, return 0.',
    'If value > 0, return value.',
    'If value > 0, return value. Otherwise, return 0. Otherwise, return 1.',
    'Return [x for x in value] + [x].',
    'Return [x for x in value if x > y for y in value].',
    'Return [x for x in value for x in value].',
    'Return [x for x.a in value].',
    'Return [getattr(x, "path") for x in value].',
    'Return (lambda x: x+1)(value).',
])
def test_unparsed_unknown_or_unsafe_branches_and_scopes_do_not_emit(doc):
    answer=ask('unsafe(value, y=7)',doc)
    assert answer['route'].endswith(('-clarify','-unsupported')) and '```' not in answer['response'],answer


def test_boolean_doctest_type_and_shadowed_primitive_remain_checked():
    result=ask('is_ready(value)','If value > 0, return True. Otherwise, return False.\n>>> is_ready(2)\n1')
    assert result['route'].endswith('-clarify') and 'disagree' in result['response']
    assert ask('hidden(values, sum=3)','Return sum(x for x in values).')['route'].endswith('-clarify')


def test_existing_vm_resource_bound_is_not_expanded_for_comprehensions():
    answer=ask('oversized(value)','Return [x for x in range(value)].\n>>> oversized(10000000)\n[]')
    assert answer['route'].endswith(('-clarify','-unsupported')) and '```' not in answer['response']
