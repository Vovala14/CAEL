"""Bounded AST interpreter for short pure teaching snippets; no eval/exec.

No imports, files, network, attributes on arbitrary objects or real stdout.
Unsupported syntax/large computations produce no claimed execution result.
"""
import ast
import operator


class Refused(ValueError):
    pass


class Returned(Exception):
    def __init__(self, value):
        self.value = value


class Interpreter:
    def __init__(self):
        self.budget = 4000
        self.depth = 0
        self.output = []

    def tick(self):
        self.budget -= 1
        if self.budget < 0:
            raise Refused('Step budget')

    def bounded(self, value):
        if isinstance(value, int) and value.bit_length() > 4096:
            raise Refused('Integer limit')
        if isinstance(value, (str, list, tuple, dict, set, range)) and len(value) > 1000:
            raise Refused('Collection limit')
        return value

    def assign(self, target, value, scope):
        if isinstance(target, ast.Name) and not target.id.startswith('_'):
            scope[target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)) and len(target.elts) == len(value):
            for t, v in zip(target.elts, value):
                self.assign(t, v, scope)
        else:
            raise Refused('Assignment form')

    def expression(self, node, scope):
        self.tick()
        read = lambda n: self.expression(n, scope)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float, str, bool, type(None)):
            return self.bounded(node.value)
        if isinstance(node, ast.Name) and not node.id.startswith('_') and node.id in scope:
            if isinstance(scope[node.id], ast.AST):
                raise Refused('First-class function values are outside this interpreter')
            return scope[node.id]
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            values = [read(n) for n in node.elts]
            return self.bounded(tuple(values) if isinstance(node, ast.Tuple) else set(values) if isinstance(node, ast.Set) else values)
        if isinstance(node, ast.Dict):
            return self.bounded({read(k): read(v) for k, v in zip(node.keys, node.values)})
        if isinstance(node, ast.UnaryOp) and type(node.op) in {ast.USub, ast.UAdd, ast.Not}:
            return {ast.USub:operator.neg, ast.UAdd:operator.pos, ast.Not:operator.not_}[type(node.op)](read(node.operand))
        if isinstance(node, ast.BinOp):
            a, b = read(node.left), read(node.right)
            operations = {ast.Add:operator.add, ast.Sub:operator.sub, ast.Mult:operator.mul,
                          ast.Div:operator.truediv, ast.FloorDiv:operator.floordiv, ast.Mod:operator.mod, ast.Pow:operator.pow}
            if type(node.op) not in operations:
                raise Refused('Operator')
            if isinstance(node.op, ast.Pow) and (not isinstance(b, int) or abs(b)>64 or isinstance(a,int) and a.bit_length()*max(1,abs(b))>4096):
                raise Refused('Power limit')
            if isinstance(node.op, ast.Mult) and ((isinstance(a,(str,list,tuple)) and isinstance(b,int) and len(a)*max(b,0)>1000) or (isinstance(b,(str,list,tuple)) and isinstance(a,int) and len(b)*max(a,0)>1000)):
                raise Refused('Repetition limit')
            if isinstance(node.op, ast.Mod) and isinstance(a,str):
                raise Refused('Unbounded format width')
            return self.bounded(operations[type(node.op)](a,b))
        if isinstance(node, ast.Compare):
            ops = {ast.Eq:operator.eq, ast.NotEq:operator.ne, ast.Lt:operator.lt, ast.LtE:operator.le,
                   ast.Gt:operator.gt, ast.GtE:operator.ge, ast.In:lambda a,b:a in b, ast.NotIn:lambda a,b:a not in b,
                   ast.Is:operator.is_, ast.IsNot:operator.is_not}
            a = read(node.left)
            for op, other in zip(node.ops,node.comparators):
                b = read(other)
                if type(op) not in ops or not ops[type(op)](a,b):return False
                a = b
            return True
        if isinstance(node, ast.BoolOp):
            value = None
            for part in node.values:
                value = read(part)
                if isinstance(node.op,ast.And) and not value or isinstance(node.op,ast.Or) and value:return value
            return value
        if isinstance(node, ast.IfExp):
            return read(node.body if read(node.test) else node.orelse)
        if isinstance(node, ast.Subscript):
            value = read(node.value)
            if not isinstance(value,(str,list,tuple,dict)):raise Refused('Subscript receiver')
            if isinstance(node.slice,ast.Slice):
                index = slice(*(read(n) if n else None for n in (node.slice.lower,node.slice.upper,node.slice.step)))
            else:index = read(node.slice)
            return value[index]
        if isinstance(node, ast.ListComp) and len(node.generators)==1:
            g=node.generators[0]; values=self.bounded(read(g.iter)); result=[]
            if g.is_async:raise Refused('Async')
            for value in values:
                local=dict(scope);self.assign(g.target,value,local)
                if all(self.expression(c,local) for c in g.ifs):result.append(self.expression(node.elt,local))
            return self.bounded(result)
        if isinstance(node, ast.Call) and not node.keywords:
            args=[read(a) for a in node.args]
            if isinstance(node.func,ast.Name) and node.func.id=='print':
                if 'print' in scope:raise Refused('Shadowed print')
                if len(self.output)>100:raise Refused('Output limit')
                self.output.append(' '.join(str(x) for x in args));return None
            if isinstance(node.func,ast.Name) and node.func.id in scope:
                function=scope[node.func.id]
                if not isinstance(function,ast.FunctionDef) or self.depth>=16 or len(args)!=len(function.args.args):raise Refused('Call')
                local=dict(scope);local.update(zip((a.arg for a in function.args.args),args));self.depth+=1
                try:
                    self.statements(function.body,local)
                except Returned as result:return result.value
                finally:self.depth-=1
                return None
            builtins={'len':len,'range':range,'sum':sum,'min':min,'max':max,'sorted':sorted,'list':list,'tuple':tuple,
                      'set':set,'dict':dict,'str':str,'int':int,'float':float,'abs':abs,'round':round,
                      'enumerate':lambda x:list(enumerate(x)), 'zip':lambda *xs:list(zip(*xs)), 'bool':bool,'any':any,'all':all}
            if isinstance(node.func,ast.Name) and node.func.id in builtins:
                return self.bounded(builtins[node.func.id](*args))
            if isinstance(node.func,ast.Attribute):
                receiver=read(node.func.value);method=node.func.attr
                methods={list:{'append','extend','count','index','pop','reverse'},dict:{'get','keys','values','items'},str:{'lower','upper','strip','split','join','replace','count','startswith','endswith'}}
                if method in methods.get(type(receiver),set()):
                    result=getattr(receiver,method)(*args);self.bounded(receiver)
                    return self.bounded(list(result) if type(receiver)==dict and method in {'keys','values','items'} else result)
        raise Refused('Unsupported expression')

    def statements(self, nodes, scope):
        for node in nodes:
            self.tick()
            if isinstance(node,ast.Expr):self.expression(node.value,scope)
            elif isinstance(node,ast.Assign):
                value=self.expression(node.value,scope)
                for target in node.targets:self.assign(target,value,scope)
            elif isinstance(node,ast.AugAssign) and isinstance(node.target,ast.Name):
                expression=ast.BinOp(left=node.target,op=node.op,right=node.value)
                self.assign(node.target,self.expression(expression,scope),scope)
            elif isinstance(node,ast.If):self.statements(node.body if self.expression(node.test,scope) else node.orelse,scope)
            elif isinstance(node,ast.For):
                values=self.bounded(self.expression(node.iter,scope))
                if not isinstance(values,(list,tuple,str,dict,range,set)):raise Refused('Iterator')
                for value in values:
                    self.tick();self.assign(node.target,value,scope);self.statements(node.body,scope)
                self.statements(node.orelse,scope)
            elif isinstance(node,ast.While):
                while self.expression(node.test,scope):self.tick();self.statements(node.body,scope)
                self.statements(node.orelse,scope)
            elif isinstance(node,ast.FunctionDef) and not node.decorator_list and not node.args.defaults and not node.args.vararg and not node.args.kwarg:
                scope[node.name]=node
            elif isinstance(node,ast.Return):raise Returned(self.expression(node.value,scope) if node.value else None)
            elif isinstance(node,ast.Pass):pass
            else:raise Refused('Unsupported statement')


def output(source):
    # Keep the legacy interpreter above as historical code; checked replies now
    # share lexical scoping and resource semantics with review/repair execution.
    from .python_vm import run_script
    result=run_script(source)
    return result['printed'].rstrip('\n') if result['status']=='ok' and result['printed'] else None
