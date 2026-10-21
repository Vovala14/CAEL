"""Owned Python object records. No host classes or user descriptors are invoked.

The VM implements lookup and calls on these records explicitly. Identity equality
matches ordinary Python objects; diagnostic representations expose no VM scopes.
"""
from dataclasses import dataclass, field


@dataclass(eq=False, repr=False)
class ClassValue:
    name: str
    bases: tuple = ()
    namespace: dict = field(default_factory=dict)
    mro: tuple = ()

    def __repr__(self): return '<interpreted class '+self.name+'>'


@dataclass(eq=False, repr=False)
class InstanceValue:
    cls: ClassValue
    fields: dict = field(default_factory=dict)

    def __repr__(self): return '<interpreted '+self.cls.name+' instance>'


@dataclass(eq=False, repr=False)
class BoundMethod:
    function: object
    receiver: object

    def __eq__(self,other):
        return isinstance(other,BoundMethod) and self.function is other.function and self.receiver is other.receiver
    def __hash__(self):return hash((id(self.function),id(self.receiver)))


@dataclass(eq=False, repr=False)
class StaticMethod:
    function: object


@dataclass(eq=False, repr=False)
class ClassMethod:
    function: object


@dataclass(eq=False, repr=False)
class PropertyValue:
    getter: object
    setter: object = None


@dataclass(eq=False, repr=False)
class SuperValue:
    start: ClassValue
    receiver: object


@dataclass(eq=False, repr=False)
class DataMethod:
    receiver: object
    name: str

    def __eq__(self,other):
        return isinstance(other,DataMethod) and self.receiver is other.receiver and self.name==other.name
    def __hash__(self):return hash((id(self.receiver),self.name))


def c3(bases):
    """C3 merge, using identity comparisons for owned class records."""
    if len(set(bases)) != len(bases): raise TypeError('Duplicate base class')
    sequences=[list(b.mro) for b in bases]+[list(bases)]
    result=[]
    while any(sequences):
        sequences=[s for s in sequences if s]
        head=next((s[0] for s in sequences if not any(s[0] in t[1:] for t in sequences)),None)
        if head is None: raise TypeError('Inconsistent method resolution order')
        result.append(head)
        for seq in sequences:
            if seq[0] is head: seq.pop(0)
    return tuple(result)


def SUPER(*args): raise AssertionError('VM-only super marker')
def STATIC(*args): raise AssertionError('VM-only staticmethod marker')
def CLASS(*args): raise AssertionError('VM-only classmethod marker')
def PROPERTY(*args): raise AssertionError('VM-only property marker')
def OBJECT_INIT(*args): raise AssertionError('VM-only object initializer')


OBJECT=ClassValue('object',namespace={'__init__':OBJECT_INIT})
OBJECT.mro=(OBJECT,)
OWNED=(ClassValue,InstanceValue,BoundMethod,StaticMethod,ClassMethod,PropertyValue,SuperValue,DataMethod)
METHODS={list:{'append','extend','pop','remove','clear','reverse','count','index','copy'},
         dict:{'get','setdefault','pop','update','keys','values','items','copy','clear'},
         set:{'add','remove','discard','copy','clear'},
         str:{'lower','upper','casefold','strip','split','splitlines','join','replace','count','find','startswith','endswith','isdigit','isalpha','isalnum'}}
