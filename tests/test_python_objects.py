"""Locally authored object semantics; native exec is confined to these fixtures."""
import copy

import pytest

from cael_unified.codegen.python_vm import run_cases, run_script
from cael_unified.codegen.code_review import analyze


FIXTURES=[
    # State is per instance; aliases preserve identity.
    '''class Box:
    shared=[]
    def __init__(self,x): self.x=x
    def add(self,x): self.x+=x
def f(x):
    a=Box(x)
    b=Box(3)
    alias=a
    alias.add(2)
    a.shared.append(x)
    return [a.x,b.x,a is alias,a is b,list(b.shared)]''',
    '''class A:
    x=3
def f(x):
    a=A()
    a.x=x
    A.x+=1
    return [a.x,A().x,A.x]''',
    '''class A:
    def __init__(self,x): self.x=x
    def get(self): return self.x
class B(A):
    def __init__(self,x): super().__init__(x+1)
    def get(self): return super().get()*2
def f(x):
    b=B(x)
    return [b.get(),A.get(b),isinstance(b,A),type(b) is B,issubclass(B,A)]''',
    '''class A:
    def get(self): return [1]
class B(A):
    def get(self): return [2]+super().get()
class C(A):
    def get(self): return [3]+super().get()
class D(B,C): pass
def f(x): return D().get()''',
    '''class A:
    n=4
    @staticmethod
    def scale(x): return x*2
    @classmethod
    def make(cls,x): return cls.scale(x)+cls.n
class B(A): n=9
def f(x): return [A.make(x),B.make(x),B().make(x),B().scale(x)]''',
    '''class A:
    n=2
    @classmethod
    def value(cls,x): return cls.n+x
class B(A):
    n=5
    @classmethod
    def value(cls,x): return super().value(x)*3
def f(x): return B.value(x)''',
    '''class A:
    def __init__(self,x): self._x=x
    @property
    def x(self): return self._x*2
    @x.setter
    def x(self,value): self._x=value+1
def f(x):
    a=A(0)
    a.x=x
    a.x+=3
    return [a.x,a._x]''',
    '''class A:
    @property
    def x(self): return 9
def f(x):
    a=A()
    try: a.x=x
    except AttributeError: return a.x
    return 0''',
    '''x=10
class A:
    x=2
    def f(self,y=x): return x+y
def f(x): return A().f()''',
    '''def f(x):
    class A:
        x=999
        def get(self): return x
    return A().get()''',
    '''class A:
    x=2
    class B:
        def get(self): return x
def f(x): return A.B().get()''',
    '''class A:
    def m(self): return x
def f(x): return A().m()''',
    '''class A:
    def __init__(self,x): self.x=x
    def get(self): return self.x
def f(x):
    a=A(x)
    bound=a.get
    a.x+=2
    return bound()''',
    '''class A:
    def weight(self,x): return -x
def f(x): return sorted([x,-1,4],key=A().weight)''',
    '''class A:
    def weight(self,x): return x+1
def f(x): return list(map(A().weight,[x,2,3]))''',
    '''class A:
    def __init__(self,x): self.x=x
    def get(self): return self.x
def f(x):
    a=A(x)
    a.get=lambda: 42
    return a.get()''',
    '''class A:
    def get(self): return 5
class B(A):
    def get(self): return super(B,self).get()+1
class C(B): pass
def f(x): return C().get()''',
    '''class A:
    def get(self):
        def nested(): return __class__
        return nested() is A
def f(x): return A().get()''',
    '''class A:
    def get(self):
        def nested(): return super()
        return nested()
def f(x): return A().get()''',
    '''class A:
    def __init__(self,x): self.x=x
class B(A): pass
def f(x): return B(x).x''',
    '''class A: pass
def f(x):
    a=A()
    return a.missing''',
    '''class A:
    def __init__(self,x): return x
def f(x): return A(x)''',
    '''class A: pass
def f(x): return A(x)''',
    '''class A: pass
def f(x):
    a=A()
    return [isinstance(a,(int,A)),isinstance(a,int),isinstance(a,object),isinstance(2,object),issubclass(int,object)]''',
    '''class A:
    def get(self): return 3
class B(A):
    def get(self): return super(B,B).get(self)+1
def f(x): return B().get()''',
    '''class A:
    def __init__(self): self.x=[]
def f(x):
    a=A()
    alias=a.x
    a.x += [x]
    return alias''',
    '''class A:
    @staticmethod
    def fn(x): return x+2
def f(x):
    g=A.fn
    return g(x)''',
    '''x=7
class A:
    x=2
    y=[x for _ in [1]]
def f(x): return A.y''',
]


@pytest.mark.parametrize('source',FIXTURES)
def test_object_semantics_match_cpython(source):
    scope={};exec(source,scope)
    calls=[dict(name='f',args=[x]) for x in (-2,0,3)]
    expected=[]
    for case in calls:
        try:expected.append(('value',copy.deepcopy(scope['f'](*case['args']))))
        except Exception as error:expected.append(('error',type(error).__name__))
    result=run_cases(source,calls)
    assert result['status']=='ok',result
    for got,(kind,value) in zip(result['cases'],expected):
        assert got['status']==kind,result
        assert got['value' if kind=='value' else 'error']==value,result


@pytest.mark.parametrize('source',[
    'class A:\n    def __getattribute__(self,n): return 1',
    'class A:\n    def __iter__(self): return [1]',
    'class A(metaclass=type): pass',
    'class A(list): pass',
    'def custom(x): return x\n@custom\nclass A: pass',
    'class A:\n    @unknown\n    def f(self): return 2',
    'class A:\n    def f(self): self.__private=2',
])
def test_unsupported_class_protocols(source):
    result=run_cases(source,[dict(name='f',args=[])])
    assert result['status']=='unsupported',result


@pytest.mark.parametrize('expression',[
    'A().__dict__','A.__mro__','A().f.__globals__','A().f.__func__',
    'str(A())','str([A()])','type(A)','A().__class__.__bases__',
])
def test_no_host_introspection_or_fake_host_repr(expression):
    source='class A:\n    def f(self): return 2\ndef f():\n    return '+expression
    result=run_cases(source,[dict(name='f',args=[])])
    assert result['cases'][0]['status']=='unsupported',result


def test_cycle_and_property_recursion_are_bounded():
    for source in [
        'class A: pass\ndef f():\n    a=A()\n    a.self=a\n    return 1',
        'class A:\n    @property\n    def x(self): return self.x\ndef f():\n    return A().x',
    ]:
        result=run_cases(source,[dict(name='f',args=[])])
        assert result['cases'][0]['status'] in {'unsupported','limit'},result


def test_duplicate_and_inconsistent_mro():
    sources=['class A: pass\nclass B(A,A): pass',
             'class A: pass\nclass B(A): pass\nclass C(A,B): pass']
    for source in sources:
        assert run_cases(source,[])['error']=='TypeError'


def test_method_review_respects_class_and_function_scope():
    findings=analyze('class A:\n    limit=3\n    def f(self,flag):\n        if flag: n=1\n        return n+limit')
    assert {f['code'] for f in findings}=={'UNBOUND_LOCAL','UNRESOLVED_NAME'}
    assert not analyze('def f(x):\n    class A:\n        def g(self): return x\n    return A().g()')


def test_checked_class_script():
    source='class A:\n    def __init__(self,n): self.n=n\n    def add(self,x): self.n+=x\na=A(2)\na.add(3)\nprint(a.n)'
    result=run_script(source)
    assert result['status']=='ok' and result['printed']=='5\n',result


@pytest.mark.parametrize('source',[
    'class T:\n    def __init__(self,x): self.amount=x\n    def add(self,y): self.amount-=y\ndef f(x,y):\n    t=T(x)\n    t.add(y)\n    return t.amount',
    'class T:\n    def __init__(self,x): self.amount=x\n    def add(self,y): self.amount+=y\ndef f(x,y):\n    t=T(x)\n    t.add(y)\n    return t.amonut',
])
def test_method_repairs_are_checked_in_both_machines(source):
    from cael_unified.codegen.workbench import repair
    supplied=[dict(name='f',args=[2,3],expected=5),dict(name='f',args=[-2,7],expected=5)]
    answer=repair(source,supplied)
    assert answer['status']=='patched',answer
    scope={};exec(answer['source'],scope)
    for x,y in [(-10,3),(4,-6),(0,0)]:assert scope['f'](x,y)==x+y


def test_bound_method_equality_and_instance_identity():
    result=run_cases('class A:\n    def f(self): return 2\ndef f():\n    a=A()\n    b=A()\n    return [a.f==a.f,a.f==b.f,a==a,a==b]',[dict(name='f',args=[])])
    assert result['cases'][0]['value']==[True,False,True,False],result


def test_displayed_diff_keeps_last_removed_and_added_lines_separate():
    from cael_unified.codegen.workbench import reply
    answer=reply('Fix this Python code:\n```python\ndef f(x,y):\n    return x-y\n```\nf(2,3) == 5\nf(-2,7) == 5')
    assert '-    return x-y\n+    return x+y\n' in answer['response'],answer


def test_class_is_an_instance_of_type_without_exposing_host_type():
    result=run_cases('class A: pass\ndef f(): return [isinstance(A,type),isinstance(A,A),issubclass(A,type)]',[dict(name='f',args=[])])
    assert result['cases'][0]['value']==[True,False,False],result


@pytest.mark.parametrize('expression',['isinstance(A.x,property)','issubclass(property,object)','super(A,A).__class__'])
def test_unsupported_metatype_cases_are_not_claimed_as_python_errors(expression):
    source='class A:\n    @property\n    def x(self): return 3\ndef f(): return '+expression
    result=run_cases(source,[dict(name='f',args=[])])
    assert result['cases'][0]['status']=='unsupported',result
