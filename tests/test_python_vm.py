"""Authored pure-Python fixtures checked against CPython; no user files run."""
import copy

import pytest

from cael_unified.codegen.python_vm import run_cases


FIXTURES=[
    ('def f(xs):\n    total=0\n    for x in xs:\n        if x<0: continue\n        if x>5: break\n        total+=x\n    else:\n        total+=100\n    return total',[[[1,-2,3]],[[2,9,1]]]),
    ('def f(n):\n    s=0\n    while n>0:\n        s+=n\n        n-=1\n    return s',[[4],[0]]),
    ('def f(x,cache=[]):\n    cache.append(x)\n    return list(cache)',[[1],[2],[3]]),
    ('def f(x,cache=[]):\n    cache.append(x)\n    return cache',[[1],[2],[3]]),
    ('def f(x=2,*,offset=3):\n    return x+offset', [[],[4]]),
    ('def f(x,/,**kw):\n    return [x,kw]',[[2]]),
    ('def f(*args,**kwargs):\n    return [sum(args),kwargs]',[[1,2,3],[]]),
    ('def f(x):\n    def g(y):\n        return x+y\n    x+=2\n    return g(3)',[[1],[5]]),
    ('def f(n):\n    if n<2: return 1\n    return n*f(n-1)',[[5],[0]]),
    ('def f(xs):\n    return [x+y for x in xs if x>0 for y in [1,2]]',[[[-1,2,3]]]),
    ('def f(xs):\n    return {x:x*x for x in xs}',[[[1,2,3]]]),
    ('def f(xs):\n    return {x%3 for x in xs}',[[[1,2,3,4]]]),
    ('def f(xs):\n    alias=xs\n    xs += [9]\n    return alias',[[[1,2]]]),
    ('def f(xs):\n    alias=xs\n    xs *= 2\n    return alias',[[[1,2]]]),
    ('def f(xs):\n    other=xs[0]\n    xs[0] += [9]\n    return other',[[[[1,2]]]]),
    ('def f(x):\n    try:\n        y=10//x\n    except ZeroDivisionError:\n        y=-1\n    else:\n        y+=1\n    finally:\n        y+=2\n    return y',[[0],[2]]),
    ('def f(x):\n    try:\n        raise ValueError("bad")\n    except ValueError as err:\n        return str(err)',[[0]]),
    ('def f(x):\n    try:\n        return 1\n    finally:\n        return 2',[[0]]),
    ('def f(x):\n    try:\n        raise ValueError("bad")\n    except ValueError as err:\n        pass\n    return err',[[0]]),
    ('x=9\ndef f(flag):\n    if flag: x=1\n    return x',[[True],[False]]),
    ('def f(xs):\n    return sorted(xs,key=lambda x: -x)',[[[2,-1,4]]]),
    ('def f(x):\n    assert x>0,"positive only"\n    return x*2',[[2],[-1]]),
    ('def f(x):\n    return [bool(x),type(x)==int,isinstance(x,(int,str))]',[[3],['a']]),
    ('def f(xs):\n    d={}\n    for x in xs:\n        d[x]=d.get(x,0)+1\n    return d',[[['a','b','a']]]),
    ('def f(x):\n    d={"n":x}\n    d["n"]+=3\n    return d',[[2]]),
    ('def f(xs):\n    it=enumerate(xs)\n    xs.append(9)\n    return list(it)',[[[1,2]]]),
    ('def f(xs):\n    d={x:x for x in xs}\n    for k in d.keys():\n        d[k+10]=0\n    return d',[[[1,2]]]),
    ('def f(x):\n    print(x,sep=None,end=None)\n    return x',[[3]]),
    ('def f(xs):\n    funcs=[lambda: x for x in xs]\n    return [fn() for fn in funcs]',[[[1,2,3]]]),
    ('def f(xs):\n    offset=1\n    g=(x+offset for x in xs)\n    offset=4\n    return list(g)',[[[1,2]]]),
    ('def f(xs):\n    return any(10//x>0 for x in xs)',[[[1,0]],[[0,1]]]),
    ('def f(xs):\n    return list(filter(lambda x:x>0,map(lambda x:x-2,xs)))',[[[1,2,3,4]]]),
    ('def f(xs):\n    return sorted(xs,key=abs)',[[[-4,1,-2]]]),
    ('def f(xs):\n    return list(reversed(tuple(xs)))',[[[1,2,3]]]),
    ('def print(x):\n    return x+1\ndef f(x):\n    return print(x)',[[2]]),
    ('def f(x):\n    return x()',[[3]]),
    ('def f(xs):\n    d={x:x for x in xs}\n    g=(x for x in d)\n    d[99]=1\n    return list(g)',[[[1,2]]]),
]


@pytest.mark.parametrize('source,args_list',FIXTURES)
def test_matches_cpython_on_authored_fixtures(source,args_list):
    scope={};exec(source,scope)
    expected=[]
    for args in args_list:
        try:expected.append(dict(status='value',value=copy.deepcopy(scope['f'](*copy.deepcopy(args)))))
        except Exception as error:expected.append(dict(status='error',error=type(error).__name__))
    result=run_cases(source,[dict(name='f',args=args) for args in args_list])
    assert result['status']=='ok',result
    for got,gold in zip(result['cases'],expected):
        assert got['status']==gold['status'],result
        if gold['status']=='value':assert got['value']==gold['value'],result
        else:assert got['error']==gold['error'],result


def test_defaults_and_keyword_binding():
    source='def f(a,/,b=3,*,c=4,**extra):\n    return [a,b,c,extra]'
    calls=[dict(name='f',args=[2],kwargs={'a':9,'c':7}),dict(name='f',args=[],kwargs={'a':2})]
    result=run_cases(source,calls)
    assert result['cases'][0]['value']==[2,3,7,{'a':9}]
    assert result['cases'][1]['error']=='TypeError'


@pytest.mark.parametrize('body',[
    'open("secret.txt").read()', '__import__("os").system("echo no")',
    '(1).__class__', 'eval("2+2")','getattr(1,"real")',
    'type("New",(),{})', 'open', 'None.append(1)',
])
def test_unsupported_has_no_claimed_python_result(body):
    result=run_cases('def f():\n    return '+body,[dict(name='f',args=[])])
    assert result['cases'][0]['status']=='unsupported',result


def test_unsupported_cannot_be_hidden_by_finally():
    source='def f():\n    try:\n        return open("secret")\n    finally:\n        return 2'
    result=run_cases(source,[dict(name='f',args=[])])
    assert result['cases'][0]['status']=='unsupported'


@pytest.mark.parametrize('source',[
    'def f():\n    while True: pass',
    'def f():\n    return [0]*100000000',
    'def f():\n    return 2**100000000',
    'def f():\n    return list(range(10**50))',
    'def f():\n    return f()',
])
def test_resource_limits(source):
    result=run_cases(source,[dict(name='f',args=[])],steps=500)
    assert result['cases'][0]['status']=='limit',result


@pytest.mark.parametrize('source',[
    'def f(x: print("should not run")):\n    return x',
    'def f():\n    global x\n    return 1',
    'def f():\n    if False: yield 1\n    return 2',
    'return 2',
])
def test_unsupported_definition_or_invalid_syntax(source):
    result=run_cases(source,[dict(name='f',args=[2])])
    assert result['status'] in {'unsupported','error'}


def test_safe_builtin_annotations_and_print_capture():
    result=run_cases('def f(xs: list[int]) -> int:\n    print(len(xs),end="!")\n    return len(xs)',[dict(name='f',args=[[1,2]])])
    assert result['cases'][0]['value']==2
    assert result['printed']=='2!'


def test_script_trace_uses_lexical_scoping_and_print_alias():
    from cael_unified.codegen.trace import output
    source='x=1\ndef f():\n    return x\ndef g():\n    x=2\n    return f()\np=print\np(g())'
    assert output(source)=='1'
