import ast

import pytest

from cael_unified.codegen.code_review import analyze
from cael_unified.codegen.workbench import examples,repair,check,reply


@pytest.mark.parametrize('source,code',[
    ('def f(x):\n    if x>0: y=1\n    return y','UNBOUND_LOCAL'),
    ('def f(xs):\n    for x in xs: pass\n    return x','UNBOUND_LOCAL'),
    ('def f(x):\n    total+=x\n    return total','UNBOUND_LOCAL'),
    ('def f(x,cache=[]):\n    cache.append(x)\n    return cache','MUTABLE_DEFAULT'),
    ('def f(xs):\n    sorted(xs)\n    return xs','DISCARDED_RESULT'),
    ('def f(x):\n    return x is 200','IDENTITY_LITERAL'),
    ('def f(x):\n    return x/0','ZERO_DIVISOR'),
    ('def f(xs):\n    for x in xs:\n        xs.remove(x)\n    return xs','MUTATE_ITERATED'),
    ('def f(x):\n    total=x\n    return totla','UNRESOLVED_NAME'),
    ('def f():\n    try: return 1\n    except: return 2','BARE_EXCEPT'),
    ('def f(x):\n    return x\n    x+=1','UNREACHABLE'),
])
def test_static_findings_have_locations(source,code):
    findings=analyze(source)
    assert any(f['code']==code and f['line']>0 for f in findings),findings


@pytest.mark.parametrize('source',[
    'def f(x):\n    if x>0: y=1\n    else: y=2\n    return y',
    'def f(x):\n    if x>0: return 1\n    else: y=2\n    return y',
    'def f(xs):\n    return [x+1 for x in xs]',
    'def f(xs):\n    total=0\n    for x in xs:\n        total+=x\n    return total',
    'def f(x):\n    def g(y):\n        return x+y\n    return g(2)',
    'def f(x):\n    import math\n    return math.sqrt(x)',
    'def f(path):\n    with open(path) as stream:\n        text=stream.read()\n    return text',
    'def f(xs):\n    xs.sort()\n    return xs',
    'def f(x):\n    return x is None',
    'def f(x):\n    try:\n        y=x+1\n    except ValueError:\n        return 0\n    else:\n        z=y+2\n    return z',
    'def f(x):\n    try:\n        y=x+1\n        return 2\n    finally:\n        print(y)',
])
def test_no_binding_or_defect_warning_on_authored_clean_functions(source):
    assert not [f for f in analyze(source) if f['severity'] in {'error','warning'}],analyze(source)


def calls(name,values):
    return [dict(name=name,args=args,kwargs={},expected=out) for args,out in values]


REPAIRS=[
    ('def f(a,b):\n    # keep this comment\n    return a-b',calls('f',[([2,3],5),([-1,4],3),([0,0],0)])),
    ('def f(n):\n    total=0\n    for i in range(1,n):\n        total+=i\n    return total',calls('f',[([4],10),([1],1),([0],0)])),
    ('def f(xs):\n    total=0\n    for x in xs:\n        total+=x\n        return total',calls('f',[([[2,3]],5),([[4,-1,2]],5)])),
    ('def f(xs):\n    total=0\n    for x in xs:\n        total=x\n    return total',calls('f',[([[2,3]],5),([[4,-1,2]],5),([[]],0)])),
    ('def f(xs):\n    total=sum(xs)\n    return totla',calls('f',[([[1,2]],3),([[]],0),([[-3,4]],1)])),
    ('def f(xs):\n    sorted(xs)',calls('f',[([[3,1]],[1,3]),([[]],[]),([[2,1,2]],[1,2,2])])),
    ('def f(x,cache=[]):\n    # keep state local\n    cache.append(x)\n    return cache',calls('f',[([1],[1]),([2],[2]),([3],[3])])),
    ('def f(x):\n    return x>3',calls('f',[([3],True),([4],True),([2],False)])),
]


@pytest.mark.parametrize('source,cases',REPAIRS)
def test_repairs_are_test_supported_and_preserve_comments(source,cases):
    result=repair(source,cases)
    assert result['status']=='patched',result
    assert check(result['source'],cases)['all_passed']
    for line in source.splitlines():
        if line.strip().startswith('#'):assert line in result['source']


def test_does_not_claim_fix_without_contrasting_tests():
    source='def f(a,b):\n    return a-b'
    result=repair(source,calls('f',[([2,3],5)]))
    assert result['status']=='needs-tests'
    assert 'source' not in result


def test_no_patch_when_all_examples_pass():
    result=repair('def f(x):\n    return x+1',calls('f',[([2],3),([4],5)]))
    assert result['status']=='already-passes'


def test_unsupported_filesystem_is_never_run_or_repaired():
    result=repair('def f(path):\n    return open(path).read()',calls('f',[(['secret'],'x'),(['other'],'y')]))
    assert result['status']=='unsupported'
    assert 'source' not in result


def test_literals_with_keywords_tuples_and_operator_strings():
    text='Fix:\n```python\ndef f(x=1): return x\n```\nassert f(x=2) == (2, 3)\nf("==") -> "=="'
    got=examples(text)
    assert got[0]['kwargs']=={'x':2}
    assert got[0]['expected']==(2,3)
    assert got[1]['expected']=='=='
    assert got[1]['args']==['==']


def test_chat_review_and_behavioral_repair():
    from cael_unified.codegen.chat import reply as chat_reply
    result=chat_reply('Review this Python code:\n```python\ndef f(flag):\n    if flag: x=1\n    return x\n```')
    assert result['route']=='chat/code-review'
    assert 'may be unbound' in result['response']
    result=chat_reply('Fix this Python function:\n```python\ndef f(a,b):\n    return a-b\n```\nf(2,3) == 5\nf(-1,4) == 3')
    assert result['route']=='chat/code-repaired',result
    assert 'not proof for untested inputs' in result['response']


def test_no_code_review_hijack_from_a_word_inside_explained_source():
    assert reply('Explain this Python code:\n```python\ndef review(x):\n    return x+1\n```') is None


def test_followup_tests_keep_the_pasted_function():
    from cael_unified.codegen.chat import reply as chat_reply
    first='Fix this Python function:\n```python\ndef f(a,b):\n    return a-b\n```'
    question=chat_reply(first)
    follow='f(2,3) == 5\nf(-1,4) == 3'
    answer=chat_reply(follow,messages=[dict(role='user',content=first),dict(role='assistant',content=question['response']),dict(role='user',content=follow)])
    assert answer['route']=='chat/code-repaired',answer


def test_unicode_source_and_comments_survive_repair():
    source='def f(a,b):\n    # café\n    résultat=a-b\n    return résultat'
    result=repair(source,calls('f',[([2,3],5),([4,-1],3)]))
    assert result['status']=='patched',result
    assert '# café' in result['source']


def test_large_explanation_expression_is_bounded_not_native_eval():
    from cael_unified.codegen.explain import evaluate
    assert evaluate("'x' * 1000000 * 1000000") is None
    assert evaluate('list(range(1000000))') is None
    assert evaluate('[x*2 for x in range(4)]')==('value','[0, 2, 4, 6]')


def test_review_derives_a_concrete_counterexample_without_inventing_gold():
    answer=reply('Review this Python function:\n```python\ndef f(xs):\n    return xs[0]\n```')
    assert '`f([])` raises `IndexError`' in answer['response']
    assert 'an exception may be intended' in answer['response']
    assert '```python' not in answer['response']
