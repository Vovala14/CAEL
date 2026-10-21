"""Scope/control-flow review of Python ASTs; findings distinguish risk from fact."""
import ast
import builtins

from .python_vm import Bindings


def analyze(source):
    findings=[];seen=set()
    def add(code,node,message,severity='warning'):
        key=(code,getattr(node,'lineno',1),message)
        if key not in seen and len(findings)<35:
            seen.add(key);findings.append(dict(code=code,line=key[1],severity=severity,message=message))
    if len(source)>16000:
        return [dict(code='SOURCE_LIMIT',line=1,severity='info',message='Source exceeds the 16,000-character review limit.')]
    try:tree=ast.parse(source);compile(tree,'<syntax-review-only>','exec')
    except SyntaxError as error:
        return [dict(code='SYNTAX',line=error.lineno or 1,severity='error',message=error.msg)]
    except RecursionError:
        return [dict(code='AST_LIMIT',line=1,severity='info',message='Source nesting exceeds the review limit.')]
    if sum(1 for _ in ast.walk(tree))>1200:
        return [dict(code='AST_LIMIT',line=1,severity='info',message='AST exceeds the bounded review limit.')]
    globals_=set(dir(builtins))
    for n in tree.body:
        if isinstance(n,(ast.FunctionDef,ast.ClassDef,ast.AsyncFunctionDef)):globals_.add(n.name)
        elif isinstance(n,(ast.Import,ast.ImportFrom)):
            globals_.update(a.asname or a.name.split('.')[0] for a in n.names)
        elif isinstance(n,(ast.Assign,ast.AnnAssign)):
            targets=n.targets if isinstance(n,ast.Assign) else [n.target]
            globals_.update(c.id for t in targets for c in ast.walk(t) if isinstance(c,ast.Name) and isinstance(c.ctx,ast.Store))

    def review_function(fn,outer):
        bindings=Bindings()
        for n in fn.body:bindings.visit(n)
        params={a.arg for a in [*fn.args.posonlyargs,*fn.args.args,*fn.args.kwonlyargs]}
        if fn.args.vararg:params.add(fn.args.vararg.arg)
        if fn.args.kwarg:params.add(fn.args.kwarg.arg)
        locals_=bindings.names|params
        external=set(outer)|globals_
        # Explicit global/nonlocal declarations change lexical binding.
        def declarations(nodes):
            result=set()
            for n in nodes:
                if isinstance(n,(ast.Global,ast.Nonlocal)):result.update(n.names)
                elif not isinstance(n,(ast.FunctionDef,ast.ClassDef,ast.Lambda)):
                    result.update(declarations(ast.iter_child_nodes(n)))
            return result
        declared=declarations(fn.body);locals_-=declared;external|=declared
        def imports(nodes):
            names=set()
            for n in nodes:
                if isinstance(n,(ast.Import,ast.ImportFrom)):names|={a.asname or a.name.split('.')[0] for a in n.names}
                elif not isinstance(n,(ast.FunctionDef,ast.ClassDef,ast.Lambda)):
                    names|=imports(ast.iter_child_nodes(n))
            return names
        locals_|=imports(fn.body)
        for default in [*fn.args.defaults,*(d for d in fn.args.kw_defaults if d is not None)]:
            if isinstance(default,(ast.List,ast.Dict,ast.Set)) or isinstance(default,ast.Call) and isinstance(default.func,ast.Name) and default.func.id in {'list','dict','set'}:
                add('MUTABLE_DEFAULT',default,'This mutable default is created once and shared by calls; changes can persist between calls.')

        def reads(node,definite,possible,bound=()):
            if node is None:return
            if isinstance(node,ast.Name) and isinstance(node.ctx,ast.Load) and node.id not in bound:
                if node.id in locals_ and node.id not in definite:
                    qualifier='may be unbound on this path' if node.id in possible else 'is read before a local binding on this path'
                    add('UNBOUND_LOCAL',node,f'`{node.id}` {qualifier}.')
                elif node.id not in locals_ and node.id not in external:
                    add('UNRESOLVED_NAME',node,f'`{node.id}` is not defined in this snippet; it may require an external binding.')
                return
            if isinstance(node,(ast.Lambda,ast.FunctionDef)):return
            if isinstance(node,(ast.ListComp,ast.SetComp,ast.DictComp,ast.GeneratorExp)):
                names=set(bound)
                for g in node.generators:
                    reads(g.iter,definite,possible,names)
                    names|={x.id for x in ast.walk(g.target) if isinstance(x,ast.Name)}
                    for test in g.ifs:reads(test,definite,possible,names)
                for value in ([node.key,node.value] if isinstance(node,ast.DictComp) else [node.elt]):reads(value,definite,possible,names)
                return
            for child in ast.iter_child_nodes(node):reads(child,definite,possible,bound)

        def target_names(target):
            return {n.id for n in ast.walk(target) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store)}

        def flow(nodes,definite,possible,inside_loop=False):
            definite,possible=set(definite),set(possible)
            alive=True
            for n in nodes:
                if not alive:
                    add('UNREACHABLE',n,'This statement follows an unconditional exit from this block.','info');continue
                if isinstance(n,ast.Assign):
                    reads(n.value,definite,possible)
                    for t in n.targets:
                        reads(t,definite,possible);names=target_names(t);definite|=names;possible|=names
                elif isinstance(n,ast.AnnAssign):
                    reads(n.value,definite,possible)
                    if n.value is not None:
                        names=target_names(n.target);definite|=names;possible|=names
                elif isinstance(n,ast.AugAssign):
                    if isinstance(n.target,ast.Name):
                        loaded=ast.Name(id=n.target.id,ctx=ast.Load());loaded.lineno=n.lineno
                        reads(loaded,definite,possible)
                    else:reads(n.target,definite,possible)
                    reads(n.value,definite,possible)
                    names=target_names(n.target);definite|=names;possible|=names
                elif isinstance(n,ast.If):
                    reads(n.test,definite,possible)
                    if isinstance(n.test,ast.Constant) and type(n.test.value) is bool:
                        a=flow(n.body if n.test.value else n.orelse,definite,possible,inside_loop)
                        if a is None:alive=False
                        else:definite,possible=a
                    else:
                        a=flow(n.body,definite,possible,inside_loop);b=flow(n.orelse,definite,possible,inside_loop)
                        if a is None and b is None:alive=False
                        elif a is None:definite,possible=b
                        elif b is None:definite,possible=a
                        else:definite,possible=a[0]&b[0],a[1]|b[1]
                elif isinstance(n,(ast.For,ast.While)):
                    reads(n.iter if isinstance(n,ast.For) else n.test,definite,possible)
                    bound=target_names(n.target) if isinstance(n,ast.For) else set()
                    body=flow(n.body,definite|bound,possible|bound,True)
                    if body is not None:possible|=body[1]
                    possible|=bound
                    # A loop may have zero iterations; assignments in its body
                    # are not definitely available after the loop.
                    flow(n.orelse,definite,possible,inside_loop)
                    for child in n.body:
                        if isinstance(child,ast.Return):add('LOOP_RETURN',child,'This return exits the function during the first iteration that reaches it. Confirm that later items should be skipped.','info')
                elif isinstance(n,ast.Try):
                    # Conservative branch merge; do not pretend to prove which
                    # statement in the try body can raise.
                    normal=flow(n.body,definite,possible,inside_loop)
                    if normal is not None:normal=flow(n.orelse,*normal,inside_loop)
                    branches=[normal]
                    for handler in n.handlers:
                        names={handler.name} if handler.name else set()
                        branch=flow(handler.body,definite|names,possible|names,inside_loop)
                        if branch is not None:branch=(branch[0]-names,branch[1]-names)
                        branches.append(branch)
                    live=[b for b in branches if b is not None]
                    if live:
                        definite=set.intersection(*(b[0] for b in live));possible=set.union(*(b[1] for b in live))
                    # Terminated branches do not retain a proof state in this
                    # analyzer. Suppress unbound-local claims in their finally
                    # block rather than invent a false definite-assignment proof.
                    final=flow(n.finalbody,definite if live else locals_,possible if live else locals_,inside_loop)
                    if final is None:alive=False
                    else:
                        definite,possible=final
                        if not live:alive=False
                elif isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    for value in [*n.args.defaults,*(d for d in n.args.kw_defaults if d is not None)]:reads(value,definite,possible)
                    review_function(n,external|locals_)
                    definite.add(n.name);possible.add(n.name)
                elif isinstance(n,(ast.Import,ast.ImportFrom)):
                    names={a.asname or a.name.split('.')[0] for a in n.names}
                    definite|=names;possible|=names
                elif isinstance(n,(ast.With,ast.AsyncWith)):
                    bound=set()
                    for item in n.items:
                        reads(item.context_expr,definite|bound,possible|bound)
                        if item.optional_vars:bound|=target_names(item.optional_vars)
                    body=flow(n.body,definite|bound,possible|bound,inside_loop)
                    if body is None:alive=False
                    else:definite,possible=body
                elif isinstance(n,ast.Delete):
                    for target in n.targets:
                        if isinstance(target,ast.Name):definite.discard(target.id);possible.discard(target.id)
                        else:reads(target,definite,possible)
                elif isinstance(n,ast.ClassDef):
                    for value in [*n.bases,*n.decorator_list]:reads(value,definite,possible)
                    review_class(n,external|locals_)
                    definite.add(n.name);possible.add(n.name)
                elif isinstance(n,(ast.Return,ast.Raise,ast.Break,ast.Continue)):
                    reads(getattr(n,'value',None) or getattr(n,'exc',None),definite,possible);alive=False
                elif isinstance(n,ast.Expr):
                    reads(n.value,definite,possible)
                    if isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id in {'sorted','reversed','map','filter'}:
                        add('DISCARDED_RESULT',n,f'The result of `{n.value.func.id}` is discarded; this call does not update the input collection.')
                else:reads(n,definite,possible)
            return (definite,possible) if alive else None
        flow(fn.body,params,params)

    def review_class(cls,outer):
        # Class attributes are not lexical bindings in method bodies. Methods
        # still capture an enclosing function and the compiler's __class__ cell.
        for child in cls.body:
            if isinstance(child,(ast.FunctionDef,ast.AsyncFunctionDef)):
                review_function(child,set(outer)|{'__class__'})
            elif isinstance(child,ast.ClassDef):review_class(child,outer)

    for n in tree.body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):review_function(n,set())
        elif isinstance(n,ast.ClassDef):review_class(n,set())
    for n in ast.walk(tree):
        if isinstance(n,ast.BinOp) and isinstance(n.op,(ast.Div,ast.FloorDiv,ast.Mod)) and isinstance(n.right,ast.Constant) and type(n.right.value) in (int,float) and n.right.value==0:
            add('ZERO_DIVISOR',n,'The literal divisor is zero; evaluating this expression raises ZeroDivisionError.','error')
        if isinstance(n,ast.ExceptHandler) and n.type is None:add('BARE_EXCEPT',n,'Bare except also catches process-control exceptions; confirm that a narrower exception type is intended.')
        if isinstance(n,ast.Compare) and any(isinstance(o,(ast.Is,ast.IsNot)) for o in n.ops):
            literals=[x for x in [n.left,*n.comparators] if isinstance(x,ast.Constant) and x.value is not None and type(x.value) is not bool]
            if literals:add('IDENTITY_LITERAL',n,'Identity comparison with a non-singleton literal depends on object identity; use equality if you intend a value comparison.')
        if isinstance(n,ast.For):
            iterable=n.iter
            receiver=iterable.id if isinstance(iterable,ast.Name) else iterable.func.value.id if isinstance(iterable,ast.Call) and isinstance(iterable.func,ast.Attribute) and isinstance(iterable.func.value,ast.Name) else None
            if receiver:
                for child in ast.walk(ast.Module(body=n.body,type_ignores=[])):
                    if isinstance(child,ast.Call) and isinstance(child.func,ast.Attribute) and isinstance(child.func.value,ast.Name) and child.func.value.id==receiver and child.func.attr in {'append','extend','remove','pop','clear','update','setdefault','add','discard'}:
                        add('MUTATE_ITERATED',child,f'`{receiver}` may change size while it is being iterated; this can skip items, extend the loop or raise an error.')
    return sorted(findings,key=lambda f:(f['line'],f['code']))
