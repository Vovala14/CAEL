"""Bounded, non-neural semantics for pure Python ASTs. No exec/eval/imports.

Unsupported operations and resource limits are distinct from Python exceptions.
Only literal data, our Function/Scope records and selected native data primitives
exist in the machine. Native Python never executes a user-supplied function body.
"""
import ast
import builtins
import copy
from dataclasses import dataclass
import math
import operator
from .object_model import (ClassValue, InstanceValue, BoundMethod, StaticMethod,
    ClassMethod, PropertyValue, SuperValue, DataMethod, OBJECT, OBJECT_INIT,
    SUPER, STATIC, CLASS, PROPERTY, OWNED, METHODS, c3)


class Unsupported(BaseException):
    pass


class Limit(Unsupported):
    pass


class Flow(BaseException):
    def __init__(self, kind, value=None):
        self.kind, self.value = kind, value


class GeneratorValue:
    """An owned iterator whose body interprets ASTs; limits native consumers."""
    def __init__(self,iterator,machine):
        self.iterator,self.machine,self.count=iterator,machine,0
    def __iter__(self):return self
    def __next__(self):
        value=next(self.iterator);self.count+=1
        if self.count>1000:self.machine.fail('Generator item limit',True)
        return value


class Bindings(ast.NodeVisitor):
    def __init__(self): self.names=set()
    def visit_Name(self,n):
        if isinstance(n.ctx,(ast.Store,ast.Del)):self.names.add(n.id)
    def visit_FunctionDef(self,n):self.names.add(n.name)
    visit_AsyncFunctionDef=visit_FunctionDef
    def visit_ClassDef(self,n):self.names.add(n.name)
    def visit_Lambda(self,n):pass
    def visit_ListComp(self,n):pass
    visit_SetComp=visit_ListComp
    visit_DictComp=visit_ListComp
    visit_GeneratorExp=visit_ListComp
    def visit_ExceptHandler(self,n):
        if n.name:self.names.add(n.name)
        for child in n.body:self.visit(child)


class Scope:
    def __init__(self,parent=None,locals_=(),machine=None):
        self.parent,self.locals,self.values=parent,set(locals_),{}
        self.machine=parent.machine if parent else machine
        self.class_body=False;self.class_cell=None
    def lookup(self,name):
        if name in self.values:return self.values[name]
        if name in self.locals:raise UnboundLocalError(f"local variable '{name}' is not bound")
        if self.parent is not None:return self.parent.lookup(name)
        if name in BUILTINS:return BUILTINS[name]
        if hasattr(builtins,name):self.machine.fail('Builtin outside pure-data subset: '+name)
        raise NameError(f"name '{name}' is not defined")


@dataclass(eq=False)
class Function:
    node: object
    closure: Scope
    defaults: list
    kwdefaults: dict
    locals: set
    class_cell: object = None


EXCEPTIONS={c.__name__:c for c in (Exception,ValueError,TypeError,KeyError,IndexError,ZeroDivisionError,
                                  RuntimeError,NameError,UnboundLocalError,AssertionError,OverflowError,AttributeError)}
BUILTINS={name:value for name,value in dict(len=len,sum=sum,min=min,max=max,sorted=sorted,reversed=reversed,
    range=range,list=list,tuple=tuple,set=set,dict=dict,str=str,int=int,float=float,bool=bool,abs=abs,round=round,
    enumerate=enumerate,zip=zip,any=any,all=all,isinstance=isinstance,issubclass=issubclass,type=type,ord=ord,chr=chr,map=map,filter=filter).items()}
BUILTINS.update(EXCEPTIONS)
BUILTINS.update(object=OBJECT,super=SUPER,staticmethod=STATIC,classmethod=CLASS,property=PROPERTY)
VIEWS=(type({}.keys()),type({}.values()),type({}.items()))
ITERATORS=(enumerate,zip,type(reversed([])),type(reversed(())),type(reversed(range(0))),GeneratorValue)


class Machine:
    def __init__(self,steps=20000):
        self.remaining=steps;self.steps=0;self.depth=0;self.tainted=False
        self.events=[];self.printed=[];self.active_error=None;self.frames=[]

    def fail(self,message,limit=False):
        self.tainted=True
        raise (Limit if limit else Unsupported)(message)

    def tick(self,node=None,scope=None):
        self.remaining-=1;self.steps+=1
        if self.remaining<0:self.fail('Step budget exhausted',True)
        if node is not None and scope is not None and len(self.events)<40:
            values={k:repr(v)[:100] for k,v in scope.values.items() if type(v) in (int,float,bool,str,list,dict,tuple,set,type(None))}
            self.events.append(dict(line=getattr(node,'lineno',None),locals=values))

    def bounded(self,value):
        count=[0];seen=set()
        def check(v,depth=0):
            count[0]+=1
            if count[0]>5000 or depth>14:self.fail('Nested value limit',True)
            if type(v) is int and v.bit_length()>2048:self.fail('Integer size limit',True)
            elif type(v) is float and not math.isfinite(v):self.fail('Non-finite arithmetic',True)
            elif type(v) is str and len(v)>4096:self.fail('String size limit',True)
            elif type(v) in (list,tuple,dict,set,range,*VIEWS):
                try:length=len(v)
                except OverflowError:self.fail('Collection size limit',True)
                if length>1000:self.fail('Collection size limit',True)
                if id(v) in seen:self.fail('Cyclic values are unsupported')
                seen.add(id(v))
                values=list(v.items()) if type(v) is dict else v
                for item in values:check(item,depth+1)
                seen.remove(id(v))
            elif isinstance(v,InstanceValue):
                if id(v) in seen:self.fail('Cyclic instance values are unsupported')
                seen.add(id(v));check(v.fields,depth+1);seen.remove(id(v))
            elif type(v) not in (int,float,str,bool,type(None),*ITERATORS) and not isinstance(v,(Function,BaseException,type,*OWNED)) and not any(v is b for b in BUILTINS.values()):
                self.fail('Value type outside pure-data subset')
            return v
        return check(value)

    def assign(self,target,value,scope):
        self.bounded(value)
        if isinstance(target,ast.Name):scope.values[target.id]=value;return
        if isinstance(target,(ast.Tuple,ast.List)):
            if not isinstance(value,(list,tuple,range)) or len(target.elts)!=len(value):raise ValueError('Unpacking length mismatch')
            for t,v in zip(target.elts,value):self.assign(t,v,scope)
            return
        if isinstance(target,ast.Subscript):
            receiver=self.expr(target.value,scope);key=self.index(target.slice,scope)
            if type(receiver) not in (list,dict):self.fail('Assignment receiver')
            receiver[key]=value;self.bounded(receiver);return
        if isinstance(target,ast.Attribute):
            self.set_attribute(self.expr(target.value,scope),target.attr,value);return
        self.fail('Assignment form')

    def index(self,node,scope):
        if isinstance(node,ast.Slice):
            return slice(*(self.expr(n,scope) if n else None for n in (node.lower,node.upper,node.step)))
        return self.expr(node,scope)

    def binop(self,op,a,b):
        funcs={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,
               ast.FloorDiv:operator.floordiv,ast.Mod:operator.mod,ast.Pow:operator.pow,
               ast.BitAnd:operator.and_,ast.BitOr:operator.or_,ast.BitXor:operator.xor}
        if type(op) not in funcs:self.fail('Binary operator')
        if isinstance(op,ast.Pow) and (type(b) is not int or abs(b)>64 or type(a) is int and a.bit_length()*max(1,abs(b))>2048):self.fail('Power limit',True)
        if isinstance(op,ast.Mult):
            for seq,n in ((a,b),(b,a)):
                if type(seq) in (str,list,tuple) and type(n) is int and len(seq)*max(n,0)>(4096 if type(seq) is str else 1000):self.fail('Repetition limit',True)
        if isinstance(op,ast.Mod) and isinstance(a,str):self.fail('String percent formatting is unsupported')
        return self.bounded(funcs[type(op)](a,b))

    def function(self,node,scope):
        if isinstance(node,ast.Lambda):body=[ast.Return(value=node.body)]
        else:body=node.body
        def own(nodes):
            for n in nodes:
                yield n
                if isinstance(n,(ast.FunctionDef,ast.Lambda,ast.ClassDef)):continue
                yield from own(ast.iter_child_nodes(n))
        if any(isinstance(n,(ast.Global,ast.Nonlocal,ast.Yield,ast.YieldFrom)) for n in own(body)):
            self.fail('Global/nonlocal/generator function semantics')
        annotations=[getattr(node,'returns',None),*(a.annotation for a in [*node.args.posonlyargs,*node.args.args,*node.args.kwonlyargs])]
        for annotation in annotations:
            if annotation is not None:self.annotation(annotation)
        bindings=Bindings()
        for child in body:bindings.visit(child)
        args=node.args
        names={a.arg for a in [*args.posonlyargs,*args.args,*args.kwonlyargs]}
        if args.vararg:names.add(args.vararg.arg)
        if args.kwarg:names.add(args.kwarg.arg)
        defaults=[self.expr(n,scope) for n in args.defaults]
        kwdefaults={a.arg:self.expr(n,scope) for a,n in zip(args.kwonlyargs,args.kw_defaults) if n is not None}
        closure=scope.parent if scope.class_body else scope
        cell=scope.class_cell
        fn=Function(node,closure,defaults,kwdefaults,bindings.names|names,cell)
        for decorator in reversed(getattr(node,'decorator_list',[])):
            # Only these owned descriptors have defined behavior in this VM.
            if isinstance(decorator,ast.Name) and decorator.id in {'staticmethod','classmethod','property'}:
                marker=scope.lookup(decorator.id)
                if marker not in (STATIC,CLASS,PROPERTY):self.fail('Custom decorator')
                fn=self.call(marker,[fn],{})
            elif isinstance(decorator,ast.Attribute) and decorator.attr in {'setter','getter'}:
                prop=self.expr(decorator.value,scope)
                if not isinstance(prop,PropertyValue):self.fail('Custom property decorator')
                fn=PropertyValue(fn,prop.setter) if decorator.attr=='getter' else PropertyValue(prop.getter,fn)
            else:self.fail('Custom decorator')
        return fn

    def invoke(self,fn,args,kwargs=None):
        kwargs=dict(kwargs or {})
        if not isinstance(fn,Function):self.fail('Not an interpreted function')
        if self.depth>=24:self.fail('Call depth limit',True)
        spec=fn.node.args;params=[*spec.posonlyargs,*spec.args];names=[a.arg for a in params]
        bound={};extra=[]
        for i,value in enumerate(args):
            if i<len(names):bound[names[i]]=value
            else:extra.append(value)
        if extra and not spec.vararg:raise TypeError('Too many positional arguments')
        if spec.vararg:bound[spec.vararg.arg]=tuple(extra)
        extras={};posonly={a.arg for a in spec.posonlyargs};kwonly={a.arg for a in spec.kwonlyargs}
        for k,v in kwargs.items():
            if k in posonly:
                if spec.kwarg:extras[k]=v;continue
                raise TypeError('Positional-only argument passed as keyword')
            if k in names or k in kwonly:
                if k in bound:raise TypeError('Multiple values for an argument')
                bound[k]=v
            elif spec.kwarg:extras[k]=v
            else:raise TypeError('Unexpected keyword argument')
        default_start=len(names)-len(fn.defaults)
        for i,name in enumerate(names):
            if name not in bound:
                if i>=default_start:bound[name]=fn.defaults[i-default_start]
                else:raise TypeError('Missing positional argument')
        for name in kwonly:
            if name not in bound:
                if name not in fn.kwdefaults:raise TypeError('Missing keyword-only argument')
                bound[name]=fn.kwdefaults[name]
        if spec.kwarg:bound[spec.kwarg.arg]=extras
        local=Scope(fn.closure,fn.locals);local.values.update(bound);local.class_cell=fn.class_cell
        if fn.class_cell is not None and fn.class_cell[0] is not None and '__class__' not in fn.locals:local.values['__class__']=fn.class_cell[0]
        self.depth+=1;self.frames.append((fn,local))
        try:
            self.block([ast.Return(value=fn.node.body)] if isinstance(fn.node,ast.Lambda) else fn.node.body,local)
        except Flow as flow:
            if flow.kind!='return':self.fail('Loop control escaped function')
            return self.bounded(flow.value)
        finally:self.depth-=1;self.frames.pop()
        return None

    def call_builtin(self,fn,args,kwargs):
        if not any(fn is value for value in BUILTINS.values()):
            if type(fn) in (int,float,str,bool,list,dict,tuple,set,type(None)):raise TypeError('Object is not callable')
            self.fail('Unknown callable')
        if fn is type and (len(args)!=1 or kwargs):self.fail('Class construction')
        if fn is type and isinstance(args[0],InstanceValue):return args[0].cls
        if fn in (isinstance,issubclass):
            if len(args)!=2 or kwargs:raise TypeError('Type check arguments')
            def matches(target):
                if isinstance(target,tuple):return any(matches(t) for t in target)
                value=args[0]
                if fn is issubclass:
                    if any(value is marker for marker in (STATIC,CLASS,PROPERTY,SUPER)):self.fail('Descriptor/metatype class checks')
                    if not isinstance(value,(ClassValue,type)):raise TypeError('issubclass arg 1 must be a class')
                    actual=value
                else:actual=value.cls if isinstance(value,InstanceValue) else type(value)
                if target is OBJECT:return True
                if isinstance(target,ClassValue):return isinstance(actual,ClassValue) and target in actual.mro
                if any(target is marker for marker in (STATIC,CLASS,PROPERTY,SUPER)):self.fail('Descriptor/metatype class checks')
                if not isinstance(target,type):raise TypeError('Type check arg 2 must be a type')
                if fn is isinstance and isinstance(value,ClassValue) and target is type:return True
                return False if isinstance(actual,ClassValue) else issubclass(actual,target)
            return matches(args[1])
        if fn in (map,filter):
            if kwargs or len(args)<2 or fn is filter and len(args)!=2:raise TypeError('Mapping/filter arguments')
            function=args[0];iterables=args[1:]
            def invoke(values):
                self.tick()
                if function is PRINT:self.fail('Print as callback')
                return self.call(function,list(values),{})
            if fn is map:
                return GeneratorValue((invoke(values) for values in zip(*iterables)),self)
            return GeneratorValue((value for value in iterables[0] if (bool(value) if function is None else invoke([value]))),self)
        if fn in (sorted,min,max) and 'key' in kwargs and kwargs['key'] is not None:
            key=kwargs['key']
            if not isinstance(key,(Function,BoundMethod,DataMethod,ClassValue)) and not any(key is b for b in BUILTINS.values()):self.fail('Unsupported sorting key')
            if key is PRINT:self.fail('Print as callback')
            kwargs={**kwargs,'key':lambda x:self.call(key,[x],{})}
        if fn in (list,tuple,set,dict,sum,min,max,any,all,sorted,reversed,enumerate,zip) and any(isinstance(a,Function) for a in args):self.fail('Function used as data')
        def contains_owned(v):
            if isinstance(v,(Function,*OWNED)):return True
            if type(v) in (list,tuple,set):return any(contains_owned(x) for x in v)
            if type(v) is dict:return any(contains_owned(k) or contains_owned(x) for k,x in v.items())
            return False
        if (fn in (str,int,float,type) or fn in EXCEPTIONS.values()) and any(contains_owned(a) for a in args):self.fail('Host conversion of interpreted objects')
        value=fn(*args,**kwargs)
        return self.bounded(value)

    def define_class(self,node,scope):
        if node.decorator_list or node.keywords or getattr(node,'type_params',[]):self.fail('Class decorators/metaclasses/type parameters')
        # Private-name mangling depends on the compiler's enclosing class name.
        # Refuse it until represented explicitly, rather than merging unrelated
        # parent/child fields that CPython would keep distinct.
        for child in ast.walk(node):
            names=[child.id] if isinstance(child,ast.Name) else [child.attr] if isinstance(child,ast.Attribute) else [child.arg] if isinstance(child,ast.arg) else [child.name] if isinstance(child,(ast.FunctionDef,ast.ClassDef)) else []
            if any(name.startswith('__') and not name.endswith('__') for name in names):self.fail('Private-name mangling subset')
        bases=tuple(self.expr(b,scope) for b in node.bases) or (OBJECT,)
        if any(not isinstance(b,ClassValue) for b in bases):self.fail('Native or custom class base')
        merged=c3(bases)
        local=Scope(scope.parent if scope.class_body else scope);local.class_body=True;local.class_cell=[None]
        self.block(node.body,local)
        forbidden=[k for k in local.values if k.startswith('__') and k.endswith('__') and k not in {'__init__','__doc__'}]
        if forbidden:self.fail('Custom special method/protocol: '+forbidden[0])
        cls=ClassValue(node.name,bases,local.values);cls.mro=(cls,*merged)
        local.class_cell[0]=cls
        return cls

    def raw_attribute(self,cls,name):
        for base in cls.mro:
            if name in base.namespace:return base.namespace[name]
        raise AttributeError("No attribute '"+name+"'")

    def descriptor(self,value,receiver,cls):
        if isinstance(value,StaticMethod):return value.function
        if isinstance(value,ClassMethod):return BoundMethod(value.function,cls)
        if isinstance(value,PropertyValue):
            if receiver is None:return value
            return self.call(value.getter,[receiver],{})
        if isinstance(value,Function) and receiver is not None:return BoundMethod(value,receiver)
        if value is OBJECT_INIT and receiver is not None:return BoundMethod(OBJECT_INIT,receiver)
        return value

    def attribute(self,receiver,name):
        if name.startswith('__') and name.endswith('__') and name not in {'__init__','__class__'}:
            self.fail('Introspection/special attribute: '+name)
        if isinstance(receiver,InstanceValue):
            if name=='__class__':return receiver.cls
            try:value=self.raw_attribute(receiver.cls,name)
            except AttributeError:value=None
            if isinstance(value,PropertyValue):return self.descriptor(value,receiver,receiver.cls)
            if name in receiver.fields:return receiver.fields[name]
            # Missing is different from a class attribute whose value is None.
            return self.descriptor(self.raw_attribute(receiver.cls,name),receiver,receiver.cls)
        if isinstance(receiver,ClassValue):
            if name=='__class__':self.fail('Metaclass introspection')
            return self.descriptor(self.raw_attribute(receiver,name),None,receiver)
        if isinstance(receiver,SuperValue):
            if name=='__class__':self.fail('Super metatype introspection')
            cls=receiver.receiver.cls if isinstance(receiver.receiver,InstanceValue) else receiver.receiver
            start=cls.mro.index(receiver.start)+1
            for base in cls.mro[start:]:
                if name in base.namespace:
                    instance=receiver.receiver if isinstance(receiver.receiver,InstanceValue) else None
                    return self.descriptor(base.namespace[name],instance,cls)
            raise AttributeError("No super attribute '"+name+"'")
        if name in METHODS.get(type(receiver),set()):return DataMethod(receiver,name)
        self.fail('Attribute outside pure-data allowlist')

    def set_attribute(self,receiver,name,value):
        if name.startswith('__') and name.endswith('__'):self.fail('Special attribute assignment')
        if isinstance(receiver,InstanceValue):
            try:prop=self.raw_attribute(receiver.cls,name)
            except AttributeError:prop=None
            if isinstance(prop,PropertyValue):
                if prop.setter is None:raise AttributeError('Property has no setter')
                self.call(prop.setter,[receiver,value],{});return
            receiver.fields[name]=value;self.bounded(receiver);return
        if isinstance(receiver,ClassValue) and receiver is not OBJECT:
            receiver.namespace[name]=value
            if len(receiver.namespace)>1000:self.fail('Class namespace size limit',True)
            return
        self.fail('Attribute assignment receiver')

    def call(self,fn,args,kwargs):
        self.tick()
        if isinstance(fn,Function):return self.invoke(fn,args,kwargs)
        if isinstance(fn,BoundMethod):return self.call(fn.function,[fn.receiver,*args],kwargs)
        if isinstance(fn,InstanceValue):raise TypeError('Instance is not callable')
        if isinstance(fn,ClassValue):
            value=InstanceValue(fn)
            init=self.attribute(value,'__init__')
            if self.call(init,args,kwargs) is not None:raise TypeError('__init__ must return None')
            return self.bounded(value)
        if fn is OBJECT_INIT:
            if len(args)!=1 or kwargs or not isinstance(args[0],InstanceValue):raise TypeError('object initializer takes no arguments')
            return None
        if fn in (STATIC,CLASS,PROPERTY):
            if kwargs or len(args)!=1 or not isinstance(args[0],Function):self.fail('Descriptor construction subset')
            return (StaticMethod if fn is STATIC else ClassMethod if fn is CLASS else PropertyValue)(args[0])
        if fn is SUPER:
            if kwargs:raise TypeError('super takes no keyword arguments')
            if not args:
                if not self.frames:raise RuntimeError('super(): no current frame')
                current,local=self.frames[-1];params=[*current.node.args.posonlyargs,*current.node.args.args]
                if not params:raise RuntimeError('super(): no arguments')
                if current.class_cell is None or current.class_cell[0] is None:raise RuntimeError('super(): no class cell')
                args=[current.class_cell[0],local.lookup(params[0].arg)]
            if len(args)!=2 or not isinstance(args[0],ClassValue):self.fail('Unbound/native super subset')
            cls=args[1].cls if isinstance(args[1],InstanceValue) else args[1]
            if not isinstance(cls,ClassValue) or args[0] not in cls.mro:raise TypeError('super receiver is not an instance or subtype')
            return SuperValue(*args)
        if isinstance(fn,DataMethod):
            receiver,name=fn.receiver,fn.name
            if type(receiver) is str and name=='join' and args:
                values=list(args[0]);self.bounded(values);args=[values,*args[1:]]
                if all(type(x) is str for x in values) and sum(map(len,values))+len(receiver)*max(0,len(values)-1)>4096:self.fail('Join limit',True)
            if type(receiver) is str and name=='replace' and len(args)>=2 and type(args[1]) is str and len(receiver)*max(1,len(args[1]))>4096:self.fail('Replace limit',True)
            value=getattr(receiver,name)(*args,**kwargs);self.bounded(receiver)
            return self.bounded(value)
        if fn is PRINT:
            def printable(v):
                if isinstance(v,(Function,type,*OWNED)) or any(v is b for b in BUILTINS.values()):self.fail('Printing callable/interpreted object values')
                if type(v) in (list,tuple,set):
                    for x in v:printable(x)
                if type(v) is dict:
                    for k,x in v.items():printable(k);printable(x)
            for v in args:printable(v)
            if set(kwargs)-{'sep','end'}:self.fail('Print target')
            sep,end=kwargs.get('sep',' '),kwargs.get('end','\n')
            sep=' ' if sep is None else sep;end='\n' if end is None else end
            if not isinstance(sep,str) or not isinstance(end,str):raise TypeError('print separators must be strings')
            text=sep.join(str(v) for v in args)+end
            if sum(map(len,self.printed))+len(text)>4096:self.fail('Print limit',True)
            self.printed.append(text);return None
        return self.call_builtin(fn,args,kwargs)

    def expr(self,n,scope):
        self.tick();read=lambda child:self.expr(child,scope)
        if isinstance(n,ast.Constant) and type(n.value) in (int,float,str,bool,type(None)):return self.bounded(n.value)
        if isinstance(n,ast.Name):return scope.lookup(n.id)
        if isinstance(n,(ast.List,ast.Tuple,ast.Set)):
            values=[read(x) for x in n.elts]
            return self.bounded(tuple(values) if isinstance(n,ast.Tuple) else set(values) if isinstance(n,ast.Set) else values)
        if isinstance(n,ast.Dict):
            if any(k is None for k in n.keys):self.fail('Dictionary unpacking')
            return self.bounded({read(k):read(v) for k,v in zip(n.keys,n.values)})
        if isinstance(n,ast.BinOp):return self.binop(n.op,read(n.left),read(n.right))
        if isinstance(n,ast.UnaryOp):
            ops={ast.USub:operator.neg,ast.UAdd:operator.pos,ast.Not:operator.not_,ast.Invert:operator.invert}
            if type(n.op) not in ops:self.fail('Unary operator')
            return self.bounded(ops[type(n.op)](read(n.operand)))
        if isinstance(n,ast.BoolOp):
            value=None
            for part in n.values:
                value=read(part)
                if isinstance(n.op,ast.And) and not value or isinstance(n.op,ast.Or) and value:return value
            return value
        if isinstance(n,ast.Compare):
            ops={ast.Eq:operator.eq,ast.NotEq:operator.ne,ast.Lt:operator.lt,ast.LtE:operator.le,ast.Gt:operator.gt,ast.GtE:operator.ge,
                 ast.In:lambda a,b:a in b,ast.NotIn:lambda a,b:a not in b,ast.Is:operator.is_,ast.IsNot:operator.is_not}
            a=read(n.left)
            for op,other in zip(n.ops,n.comparators):
                b=read(other)
                if type(op) not in ops:self.fail('Comparison')
                if not ops[type(op)](a,b):return False
                a=b
            return True
        if isinstance(n,ast.IfExp):return read(n.body if read(n.test) else n.orelse)
        if isinstance(n,ast.Attribute):return self.attribute(read(n.value),n.attr)
        if isinstance(n,ast.Subscript):
            value=read(n.value)
            if type(value) not in (str,list,tuple,dict):self.fail('Subscript receiver')
            return self.bounded(value[self.index(n.slice,scope)])
        if isinstance(n,(ast.ListComp,ast.SetComp,ast.DictComp,ast.GeneratorExp)):
            result={} if isinstance(n,ast.DictComp) else set() if isinstance(n,ast.SetComp) else []
            if any(g.is_async for g in n.generators):self.fail('Async comprehension')
            first_iter=iter(self.bounded(self.expr(n.generators[0].iter,scope)))
            targets={child.id for g in n.generators for child in ast.walk(g.target) if isinstance(child,ast.Name)}
            local=Scope(scope.parent if scope.class_body else scope,targets)
            def walk(i):
                if i==len(n.generators):
                    if isinstance(n,ast.DictComp):yield (self.expr(n.key,local),self.expr(n.value,local))
                    else:yield self.expr(n.elt,local)
                    return
                g=n.generators[i]
                values=first_iter if i==0 else self.bounded(self.expr(g.iter,local))
                for value in values:
                    self.tick();self.assign(g.target,value,local)
                    if all(self.expr(c,local) for c in g.ifs):yield from walk(i+1)
            iterator=GeneratorValue(walk(0),self)
            if isinstance(n,ast.GeneratorExp):return iterator
            for value in iterator:
                if isinstance(n,ast.DictComp):result[value[0]]=value[1]
                elif isinstance(n,ast.SetComp):result.add(value)
                else:result.append(value)
                self.bounded(result)
            return result
        if isinstance(n,ast.Lambda):return self.function(n,scope)
        if isinstance(n,ast.Call):
            if any(isinstance(a,ast.Starred) for a in n.args) or any(k.arg is None for k in n.keywords):self.fail('Call unpacking')
            # Resolve descriptors before evaluating call arguments, as Python does.
            fn=read(n.func)
            args=[read(a) for a in n.args];kwargs={k.arg:read(k.value) for k in n.keywords}
            return self.call(fn,args,kwargs)
        self.fail('Unsupported expression: '+type(n).__name__)

    def block(self,nodes,scope):
        for n in nodes:
            self.tick(n,scope)
            if isinstance(n,ast.Expr):self.expr(n.value,scope)
            elif isinstance(n,ast.Assign):
                value=self.expr(n.value,scope)
                for target in n.targets:self.assign(target,value,scope)
            elif isinstance(n,ast.AnnAssign):
                self.annotation(n.annotation)
                if n.value is not None:self.assign(n.target,self.expr(n.value,scope),scope)
            elif isinstance(n,ast.AugAssign):
                # Target is evaluated once, before the RHS.
                if isinstance(n.target,ast.Name):
                    before=scope.lookup(n.target.id);rhs=self.expr(n.value,scope)
                    self.assign(n.target,self.augmented(n.op,before,rhs),scope)
                elif isinstance(n.target,ast.Subscript):
                    receiver=self.expr(n.target.value,scope);index=self.index(n.target.slice,scope)
                    if type(receiver) not in (list,dict):self.fail('Augmented assignment receiver')
                    receiver[index]=self.augmented(n.op,receiver[index],self.expr(n.value,scope));self.bounded(receiver)
                elif isinstance(n.target,ast.Attribute):
                    receiver=self.expr(n.target.value,scope);before=self.attribute(receiver,n.target.attr)
                    self.set_attribute(receiver,n.target.attr,self.augmented(n.op,before,self.expr(n.value,scope)))
                else:self.fail('Augmented assignment')
            elif isinstance(n,ast.If):self.block(n.body if self.expr(n.test,scope) else n.orelse,scope)
            elif isinstance(n,(ast.For,ast.While)):
                broken=False
                if isinstance(n,ast.For):iterator=iter(self.bounded(self.expr(n.iter,scope)))
                while True:
                    if isinstance(n,ast.For):
                        try:value=next(iterator)
                        except StopIteration:break
                        self.assign(n.target,value,scope)
                    elif not self.expr(n.test,scope):break
                    self.tick()
                    try:self.block(n.body,scope)
                    except Flow as flow:
                        if flow.kind=='break':broken=True;break
                        if flow.kind!='continue':raise
                if not broken:self.block(n.orelse,scope)
            elif isinstance(n,ast.FunctionDef):scope.values[n.name]=self.function(n,scope)
            elif isinstance(n,ast.ClassDef):scope.values[n.name]=self.define_class(n,scope)
            elif isinstance(n,ast.Return):raise Flow('return',self.expr(n.value,scope) if n.value else None)
            elif isinstance(n,ast.Break):raise Flow('break')
            elif isinstance(n,ast.Continue):raise Flow('continue')
            elif isinstance(n,ast.Pass):pass
            elif isinstance(n,ast.Assert):
                if not self.expr(n.test,scope):raise AssertionError(self.expr(n.msg,scope) if n.msg else '')
            elif isinstance(n,ast.Raise):
                if n.cause:self.fail('Exception chaining')
                value=self.expr(n.exc,scope) if n.exc else self.active_error
                if isinstance(value,type) and value in EXCEPTIONS.values():value=value()
                if not isinstance(value,Exception):self.fail('Raise form')
                raise value
            elif isinstance(n,ast.Try):
                try:self.block(n.body,scope)
                except Exception as error:
                    handled=False;previous=self.active_error;self.active_error=error
                    try:
                        for handler in n.handlers:
                            cls=self.expr(handler.type,scope) if handler.type else Exception
                            if not isinstance(cls,(type,tuple)):self.fail('Exception handler type')
                            if isinstance(error,cls):
                                handled=True
                                if handler.name:scope.values[handler.name]=error
                                try:self.block(handler.body,scope)
                                finally:
                                    if handler.name:scope.values.pop(handler.name,None)
                                break
                        if not handled:raise
                    finally:self.active_error=previous
                else:self.block(n.orelse,scope)
                finally:self.block(n.finalbody,scope)
            else:self.fail('Unsupported statement: '+type(n).__name__)

    def load(self,source):
        if len(source)>16000:self.fail('Source size limit',True)
        tree=ast.parse(source)
        if sum(1 for _ in ast.walk(tree))>800:self.fail('AST size limit',True)
        compile(tree,'<syntax-validation-only>','exec')
        # Module-level execution is limited to definitions/literal assignments.
        for n in tree.body:
            if not isinstance(n,(ast.FunctionDef,ast.ClassDef,ast.Assign,ast.AnnAssign,ast.Expr)) or isinstance(n,ast.Expr) and not isinstance(n.value,ast.Constant):self.fail('Module-level statements')
        scope=Scope(machine=self);self.block(tree.body,scope);return scope

    def annotation(self,node):
        # Valid, side-effect-free builtin annotations only; no deferred calls.
        names={'int','float','str','bool','list','tuple','set','dict','None'}
        for child in ast.walk(node):
            if isinstance(child,ast.Name) and child.id not in names:self.fail('Annotation name')
            if not isinstance(child,(ast.Name,ast.Load,ast.Subscript,ast.Tuple,ast.Constant,ast.BinOp,ast.BitOr)):
                self.fail('Executable or unsupported annotation')

    def augmented(self,op,before,rhs):
        if type(before) is list and isinstance(op,ast.Add):
            if type(rhs) not in (list,tuple,range,str):raise TypeError('Not iterable')
            if len(before)+len(rhs)>1000:self.fail('Collection size limit',True)
            before+=rhs;return self.bounded(before)
        result=self.binop(op,before,rhs)
        if type(before) is list and isinstance(op,ast.Mult):before[:]=result;return before
        if type(before) is set and isinstance(op,(ast.BitAnd,ast.BitOr,ast.BitXor,ast.Sub)):
            before.clear();before.update(result);return before
        if type(before) is dict and isinstance(op,ast.BitOr):before.update(result);return before
        return result


def PRINT(*args,**kwargs):
    raise AssertionError('VM-only print marker')


BUILTINS['print']=PRINT


def run_script(source,steps=4000):
    machine=Machine(steps)
    try:
        if len(source)>3000:machine.fail('Script source limit',True)
        tree=ast.parse(source)
        if sum(1 for _ in ast.walk(tree))>350:machine.fail('Script AST limit',True)
        compile(tree,'<script-syntax-only>','exec')
        machine.block(tree.body,Scope(machine=machine))
        if machine.tainted:raise Unsupported('Unsupported semantics')
        return dict(status='ok',printed=''.join(machine.printed),steps=machine.steps)
    except Unsupported as error:return dict(status='limit' if isinstance(error,Limit) else 'unsupported',message=str(error))
    except Exception as error:return dict(status='error',error=type(error).__name__,message=str(error))


def run_cases(source,cases,steps=20000):
    """Cases: name/args/kwargs. One module instance preserves default semantics."""
    machine=Machine(steps);results=[]
    try:scope=machine.load(source)
    except (Unsupported,SyntaxError,Exception) as error:
        status='limit' if isinstance(error,Limit) else 'unsupported' if isinstance(error,Unsupported) else 'error'
        return dict(status=status,error=type(error).__name__,message=str(error),cases=[],steps=machine.steps)
    for case in cases:
        start=len(machine.events)
        try:
            args=machine.bounded(copy.deepcopy(case.get('args',[])));kwargs=machine.bounded(copy.deepcopy(case.get('kwargs',{})))
            value=machine.call(scope.lookup(case['name']),args,kwargs)
            if machine.tainted:raise Unsupported('Earlier unsupported semantics')
            def literal(v):
                if type(v) in (int,float,str,bool,type(None)):return True
                if type(v) in (list,tuple,set):return all(literal(x) for x in v)
                if type(v) is dict:return all(literal(k) and literal(x) for k,x in v.items())
                return False
            if not literal(value):raise Unsupported('Non-literal return value')
            results.append(dict(status='value',value=copy.deepcopy(value),events=machine.events[start:]))
        except Unsupported as error:
            results.append(dict(status='limit' if isinstance(error,Limit) else 'unsupported',message=str(error),events=machine.events[start:]))
            break
        except Exception as error:
            results.append(dict(status='error',error=type(error).__name__,message=str(error),events=machine.events[start:]))
    return dict(status='ok' if len(results)==len(cases) else 'incomplete',cases=results,steps=machine.steps,printed=''.join(machine.printed))
