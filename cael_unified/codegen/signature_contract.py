"""Compile a declarative Python stub without losing its signature or examples.

Only fully parsed pure expression/ordered collection contracts are compiled.
All emitted bodies are interpreted in the existing bounded AST VM, never exec.
This is a finite symbolic language, not general Python/prose understanding.
"""
import ast
import copy
import doctest
import io
import re
import tokenize

from .python_vm import Machine, Unsupported, run_cases


class Unclear(ValueError):
    pass


REQUEST = re.compile(r'(?is)\s*(?:(?:please\s+)?(?:complete|implement|finish|write|create|build|generate)\b[^\n`]{0,130})?\s*')
METHODS = {'strip', 'lstrip', 'rstrip', 'lower', 'upper', 'casefold', 'split', 'join', 'count', 'replace', 'startswith', 'endswith'}
CALLS = {'abs', 'len', 'sum', 'min', 'max', 'sorted', 'reversed', 'list', 'tuple', 'set', 'str', 'int', 'float', 'bool', 'round', 'all', 'any', 'range', 'zip', 'enumerate'}
EXPR_NODES = (ast.Expression, ast.Name, ast.Load, ast.Constant, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
              ast.IfExp, ast.Subscript, ast.Slice, ast.List, ast.Tuple, ast.Set, ast.Dict, ast.Call, ast.Attribute,
              ast.keyword, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.UAdd, ast.USub,
              ast.Not, ast.And, ast.Or, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn)


def scoped_expression(tree,params):
    """Validate lexical comprehension scopes; never leak aliases into siblings.

    The first iterable is evaluated in the outer scope, as in Python/the VM.
    Later iterables/filters cannot read a not-yet-bound later target. Calls are
    pure-data primitives, never arbitrary functions or attribute traversal.
    """
    comprehensions=(ast.ListComp,ast.SetComp,ast.DictComp,ast.GeneratorExp)
    def target_names(node):
        if isinstance(node,ast.Name):return [node.id]
        if isinstance(node,(ast.Tuple,ast.List)) and 1<=len(node.elts)<=6:
            if not all(isinstance(n,ast.Name) for n in node.elts):raise Unclear('Only flat explicit comprehension targets are supported.')
            return [n.id for n in node.elts]
        raise Unclear('A comprehension target must be a name or flat name tuple; no attribute/subscript assignment.')
    def visit(node,scope,depth=0):
        if depth>24:raise Unclear('Expression scope nesting exceeds the supported bound.')
        if isinstance(node,comprehensions):
            if not 1<=len(node.generators)<=3 or any(g.is_async for g in node.generators):
                raise Unclear('Use at most three synchronous comprehension generators.')
            targets=[target_names(g.target) for g in node.generators];flat=[n for group in targets for n in group]
            if len(flat)!=len(set(flat)):raise Unclear('Repeated targets make this comprehension scope unsupported; use distinct aliases.')
            visit(node.generators[0].iter,scope,depth+1)
            local=set(scope)-set(flat)
            for i,(generator,names) in enumerate(zip(node.generators,targets)):
                if i:visit(generator.iter,local,depth+1)
                local.update(names)
                for test in generator.ifs:visit(test,local,depth+1)
            if isinstance(node,ast.DictComp):visit(node.key,local,depth+1);visit(node.value,local,depth+1)
            else:visit(node.elt,local,depth+1)
            return
        if not isinstance(node,EXPR_NODES):raise Unclear('Unsupported expression syntax: '+type(node).__name__+'.')
        if isinstance(node,ast.Name):
            if not isinstance(node.ctx,ast.Load) or node.id not in scope:raise Unclear('Undeclared or unbound expression name '+node.id+'.')
            return
        if isinstance(node,ast.Call):
            if isinstance(node.func,ast.Name):
                if node.func.id not in CALLS or node.func.id in scope:raise Unclear('Only unshadowed explicit pure-data calls are supported.')
            elif isinstance(node.func,ast.Attribute):visit(node.func,scope,depth+1)
            else:raise Unclear('Only named pure primitives or whitelisted data methods are supported.')
            if any(k.arg is None for k in node.keywords):raise Unclear('Expanded keyword calls are outside the supported expression contract.')
            for argument in node.args:visit(argument,scope,depth+1)
            for keyword in node.keywords:visit(keyword.value,scope,depth+1)
            return
        if isinstance(node,ast.Attribute) and node.attr not in METHODS:raise Unclear('Only whitelisted pure-data methods are supported.')
        for child in ast.iter_child_nodes(node):visit(child,scope,depth+1)
    visit(tree,set(params))


def condition(text,params):
    value=text.strip()
    match=re.fullmatch(r'(.+?) is (not )?(empty|even|odd)',value,re.I)
    if match:
        base=expression(match[1],params)
        test='len('+base+') == 0' if match[3].lower()=='empty' else '('+base+') % 2 == '+('0' if match[3].lower()=='even' else '1')
        return 'not ('+test+')' if match[2] else test
    from ..orchestrator import protected_spans,unprotected
    for words,symbol in [('is greater than or equal to','>='),('is less than or equal to','<='),('is not equal to','!='),
                         ('is greater than','>'),('is less than','<'),('is equal to','==')]:
        spans=protected_spans(value)
        value=re.sub(r'\b'+words+r'\b',lambda m:symbol if unprotected(value,m,spans) else m[0],value,flags=re.I)
    return expression(value,params)


def conditional_body(description,params):
    if not re.match(r'(?i)^if\s+',description):return None
    from ..orchestrator import protected_spans,unprotected
    spans=protected_spans(description)
    separators=[m for m in re.finditer(r'[.;]\s*otherwise\s*,?\s*return\s+',description,re.I) if unprotected(description,m,spans)]
    if len(separators)!=1:raise Unclear('A conditional contract requires one complete If branch and one Otherwise return branch.')
    separator=separators[0];first=re.sub(r'(?i)^if\s+','',description[:separator.start()]);last=description[separator.end():].strip().rstrip('.')
    spans=protected_spans(first)
    returns=[m for m in re.finditer(r',\s*return\s+',first,re.I) if unprotected(first,m,spans)]
    if len(returns)!=1:raise Unclear('Separate the complete condition and return expression with a comma; no clause was discarded.')
    at=returns[0]
    test=ast.parse(condition(first[:at.start()],params),mode='eval').body
    yes=ast.parse(expression(first[at.end():],params),mode='eval').body
    no=ast.parse(expression(last,params),mode='eval').body
    return [ast.If(test=test,body=[ast.Return(value=yes)],orelse=[ast.Return(value=no)])]


def extract(text):
    """None for ordinary explanation/repair requests; own only declarative stubs."""
    if len(text) > 10000:
        return None
    blocks = list(re.finditer(r'```(?:python|py)?\s*\n(.*?)```', text, re.S))
    if blocks:
        prefix, source, suffix = text[:blocks[0].start()], blocks[0][1], text[blocks[0].end():]
        if not REQUEST.fullmatch(prefix):
            return None
        # Decided after parsing: real source with steps (a task tool) is not a stub and belongs to other routes.
        extra = len(blocks) != 1 or bool(suffix.strip())
    else:
        start = re.search(r'(?m)^\s*(?:def|async def)\s+\w+\s*\(', text)
        if not start or not REQUEST.fullmatch(text[:start.start()]):
            return None
        source = text[start.start():]
        extra = False
    try:
        tree = ast.parse(source)
    except (SyntaxError, RecursionError):
        return None
    if sum(1 for _ in ast.walk(tree)) > 500:
        raise Unclear('The function specification exceeds the bounded syntax limit.')
    functions = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if not functions:
        return None
    # Real source belongs to review/repair, even when headed "complete".
    def placeholder(node):
        return isinstance(node, ast.Pass) or isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and node.value.value is Ellipsis
    for fn in functions:
        body = fn.body[1:] if ast.get_docstring(fn) is not None else fn.body
        if not body or not all(placeholder(n) for n in body):
            return None
    if extra:
        raise Unclear('Use one function stub and put every behavioral requirement in its docstring; extra blocks or trailing clauses were not discarded.')
    if len(functions) != 1 or len(tree.body) != 1:
        raise Unclear('Complete one declarative function at a time; imports, decorators and extra definitions are outside this contract.')
    # Requirements in comments must not disappear during AST parsing. Real
    # implementations were already deferred above to explanation/repair.
    if any(t.type == tokenize.COMMENT for t in tokenize.generate_tokens(io.StringIO(source).readline)):
        raise Unclear('Put all requirements in the docstring; source comments were not silently discarded.')
    fn = functions[0]
    if isinstance(fn, ast.AsyncFunctionDef) or fn.decorator_list or fn.args.vararg or fn.args.kwarg:
        raise Unclear('Async, decorated and variadic signatures are not supported by this contract compiler.')
    params = [a.arg for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs]
    if not 1 <= len(params) <= 6 or len(set(params)) != len(params):
        raise Unclear('Use one to six distinct explicit parameters.')
    machine = Machine()
    for node in [*fn.args.defaults, *(n for n in fn.args.kw_defaults if n is not None)]:
        try:
            machine.bounded(ast.literal_eval(node))
        except (ValueError, SyntaxError, Unsupported):
            raise Unclear('Defaults must be bounded Python literals; no default expression was executed.')
    for node in [*(a.annotation for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs), fn.returns]:
        if node is not None:
            try:
                machine.annotation(node)
            except Unsupported:
                raise Unclear('Only static builtin type annotations are supported; no annotation expression was executed.')
    doc = ast.get_docstring(fn, clean=True)
    if not doc or not doc.strip():
        raise Unclear('The signature gives no behavior. Add a docstring describing the complete result and contrasting literal examples.')
    return fn, params, doc


def bind(fn, call):
    """Bind literal inputs statically, preserving /, *, keyword names and defaults."""
    positional = fn.args.posonlyargs + fn.args.args
    names = [a.arg for a in positional + fn.args.kwonlyargs]
    if len(call.args) > len(positional) or any(k.arg is None for k in call.keywords):
        raise Unclear('A doctest has an incompatible call signature.')
    values = {a.arg: ast.literal_eval(v) for a, v in zip(positional, call.args)}
    posonly = {a.arg for a in fn.args.posonlyargs}
    for keyword in call.keywords:
        if keyword.arg in posonly or keyword.arg not in names or keyword.arg in values:
            raise Unclear('A doctest has duplicate, unknown or positional-only keyword arguments.')
        values[keyword.arg] = ast.literal_eval(keyword.value)
    defaults = dict(zip([a.arg for a in positional][-len(fn.args.defaults):], fn.args.defaults)) if fn.args.defaults else {}
    defaults.update({a.arg: value for a, value in zip(fn.args.kwonlyargs, fn.args.kw_defaults) if value is not None})
    for name in names:
        if name not in values:
            if name not in defaults:
                raise Unclear('A doctest omits required parameter '+name+'.')
            values[name] = ast.literal_eval(defaults[name])
    return tuple(values[n] for n in names)


def examples(fn, doc):
    try:
        pieces = doctest.DocTestParser().parse(doc)
    except ValueError as error:
        raise Unclear('Malformed doctest layout: '+str(error))
    description, cases, inputs, outputs = [], [], [], []
    for piece in pieces:
        if isinstance(piece, str):
            # Remove a standalone section label, never any behavioral clause.
            description.append(re.sub(r'(?im)^\s*examples?:\s*$', '', piece))
            continue
        if len(cases) >= 16 or piece.exc_msg:
            raise Unclear('Use at most sixteen literal-result doctests; expected exceptions are not supported here.')
        try:
            call = ast.parse(piece.source.strip(), mode='eval').body
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name) or call.func.id != fn.name:
                raise Unclear('Each doctest must call the declared function directly with literal inputs.')
            ordered = bind(fn, call)
            expected = ast.literal_eval(piece.want.strip())
            case = dict(name=fn.name, args=[ast.literal_eval(a) for a in call.args],
                        kwargs={k.arg: ast.literal_eval(k.value) for k in call.keywords})
            for value in [*ordered, expected]:
                Machine().bounded(value)
        except (ValueError, SyntaxError, Unsupported, TypeError) as error:
            raise Unclear('A doctest is not a bounded literal call/result: '+str(error))
        for previous, result in zip(inputs, outputs):
            if previous == ordered and (result != expected or isinstance(result, bool) != isinstance(expected, bool)):
                raise Unclear('The doctests give conflicting results for the same bound inputs.')
        inputs.append(ordered)
        outputs.append(expected)
        cases.append(case)
    return ' '.join(' '.join(description).split()).strip(), cases, inputs, outputs


def expression(text, params, depth=0):
    """Read a whole finite arithmetic/collection expression, never a keyword cue."""
    if depth > 8:
        raise Unclear('Expression nesting exceeds the supported limit.')
    text = text.strip()
    if text.startswith('the '):
        text = text[4:]
    nested = lambda value: expression(value, params, depth+1)
    match = re.fullmatch(r'(absolute )?difference between (.+?) and (.+)', text, re.I)
    if match:
        value = '('+nested(match[2])+') - ('+nested(match[3])+')'
        return 'abs('+value+')' if match[1] else value
    match = re.fullmatch(r'(sum|length|count|minimum|maximum|sorted values|reversed values|unique values) of (.+)', text, re.I)
    if match:
        operation = {'length': 'len', 'count': 'len', 'minimum': 'min', 'maximum': 'max',
                     'sorted values': 'sorted', 'reversed values': 'list', 'unique values': 'set'}.get(match[1].lower(), 'sum')
        value = nested(match[2])
        if match[1].lower() == 'reversed values':
            value = 'reversed('+value+')'
        return operation+'('+value+')'
    match = re.fullmatch(r'(squares|cubes|absolute values) of (.+)', text, re.I)
    if match:
        name = fresh(params, '_cael_value')
        mapped = {'squares': name+' ** 2', 'cubes': name+' ** 3', 'absolute values': 'abs('+name+')'}[match[1].lower()]
        return '['+mapped+' for '+name+' in '+nested(match[2])+']'
    match = re.fullmatch(r'(positive|negative|nonnegative|nonzero|even|odd) (?:values|entries|integers) (?:in|of) (.+)', text, re.I)
    if match:
        name = fresh(params, '_cael_value')
        condition = {'positive': '> 0', 'negative': '< 0', 'nonnegative': '>= 0', 'nonzero': '!= 0',
                     'even': '% 2 == 0', 'odd': '% 2 != 0'}[match[1].lower()]
        return '['+name+' for '+name+' in '+nested(match[2])+' if '+name+' '+condition+']'
    # Operator words become syntax only; the entire result must parse and use
    # declared names/whitelisted pure primitives. Unparsed words never vanish.
    if text in params:
        return text
    from ..orchestrator import protected_spans, unprotected
    for words, symbol in [('floor divided by', '//'), ('multiplied by', '*'), ('divided by', '/'),
                          ('to the power of', '**'), ('plus', '+'), ('minus', '-'), ('times', '*'), ('modulo', '%')]:
        spans = protected_spans(text)
        text = re.sub(r'\b'+words+r'\b', lambda match: symbol if unprotected(text, match, spans) else match[0], text)
    try:
        if any(t.type == tokenize.COMMENT for t in tokenize.generate_tokens(io.StringIO(text).readline)):
            raise Unclear('Comments are not accepted as hidden expression clauses.')
        tree = ast.parse(text, mode='eval')
    except (SyntaxError, tokenize.TokenError):
        raise Unclear('The whole result expression is outside the supported symbolic grammar.')
    if sum(1 for _ in ast.walk(tree)) > 160:
        raise Unclear('The expression is too large.')
    scoped_expression(tree,params)
    return ast.unparse(tree.body)


def fresh(used, prefix):
    name = prefix
    while name in used:
        name += '_'
    return name


def transplant(stub, generated):
    """Hygienically adapt a one-input compiler body to the caller's signature."""
    module = ast.parse(generated)
    old = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == stub.name)
    helpers = [n for n in module.body if n is not old]
    params = stub.args.posonlyargs + stub.args.args + stub.args.kwonlyargs
    if len(params) != 1 or len(old.args.args) != 1 or not isinstance(old, ast.FunctionDef):
        raise Unclear('The collection compiler currently requires exactly one explicit input parameter.')
    original = old.args.args[0].arg
    locals_ = {n.id for n in ast.walk(old) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    globals_ = {n.id for n in ast.walk(old) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)} - locals_ - {original}
    helper_names = {n.name for n in helpers if isinstance(n, ast.FunctionDef)}
    globals_ -= helper_names
    from .python_vm import BUILTINS
    globals_ |= {n.id for n in ast.walk(module) if isinstance(n, ast.Name) and n.id in BUILTINS}
    if params[0].arg in globals_ or stub.name in globals_:
        raise Unclear('That signature shadows a primitive required by the selected compiler.')
    used = {params[0].arg} | globals_
    mapping = {original: params[0].arg}
    for name in sorted(locals_ - {original}):
        mapping[name] = fresh(used, '_cael_'+name)
        used.add(mapping[name])
    helper_map = {}
    for name in sorted(helper_names):
        helper_map[name] = fresh(used, name)
        used.add(helper_map[name])
    mapping.update(helper_map)

    class Rename(ast.NodeTransformer):
        def visit_Name(self, node):
            return ast.copy_location(ast.Name(id=mapping.get(node.id, node.id), ctx=node.ctx), node)

    class RenameHelpers(ast.NodeTransformer):
        def visit_Name(self, node):
            return ast.copy_location(ast.Name(id=helper_map.get(node.id, node.id), ctx=node.ctx), node)
        def visit_FunctionDef(self, node):
            node.name = helper_map.get(node.name, node.name)
            return self.generic_visit(node)

    # Keep the compiler's input/result guards as local helper definitions. Their
    # own parameters have distinct scopes, so only helper references are renamed.
    prefix = [RenameHelpers().visit(copy.deepcopy(n)) for n in helpers]
    return prefix + [Rename().visit(copy.deepcopy(n)) for n in old.body if not isinstance(n, ast.Expr) or not isinstance(n.value, ast.Constant) or not isinstance(n.value.value, str)]


def reply(text):
    out = lambda response, suffix, **extra: dict(response=response, route='chat/code-signature-'+suffix, sources=[], **extra)
    try:
        contract = extract(text)
        if contract is None:
            return None
        stub, params, doc = contract
        description, cases, inputs, outputs = examples(stub, doc)
        if not description:
            raise Unclear('The docstring has examples but no complete behavioral specification.')
        return_match = re.fullmatch(r'(?:Return|Returns|Compute|Calculate)\s+(.+?)[.]?', description, re.S)
        evidence = {}
        conditional = conditional_body(description,params)
        if conditional is not None:
            body=conditional
            method='complete conditional contract compilation'
        elif return_match:
            value = expression(return_match[1], params)
            body = [ast.Return(value=ast.parse(value, mode='eval').body)]
            method = 'whole-expression symbolic compilation'
        elif re.match(r'(?i)^(?:keep|filter|split|trim|strip|drop|remove|double|triple|square|cube|multiply|add|subtract|group|count|sort)\b', description):
            from .natural_program import prepare
            plan, built, parts, domain = prepare('Write a Python function named '+stub.name+' that '+description)
            if built['status'] != 'built':
                raise Unclear(built['message'])
            body = transplant(stub, built['source'])
            method = 'ordered collection plan compilation'
            evidence = dict(plan=parts, compiler_probes=built['probes'])
        else:
            raise Unclear('I cannot yet interpret the complete docstring. Restate it as an explicit return expression or an ordered pure-data workflow; no unrelated recipe was substituted.')
        if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in {*params, stub.name}
               for statement in body for n in ast.walk(statement)):
            raise Unclear('The declared signature shadows a primitive required by this implementation.')
        finished = copy.deepcopy(stub)
        finished.body = [copy.deepcopy(stub.body[0])] + body
        source = ast.unparse(ast.fix_missing_locations(ast.Module(body=[finished], type_ignores=[])))+'\n'
        # Even a spec with no doctests must safely load; cases, when present,
        # check the original positional/keyword/default contract unchanged.
        result = run_cases(source, cases)
        if result['status'] != 'ok' or any(r['status'] != 'value' for r in result.get('cases', [])):
            raise Unclear('The generated function could not be verified in the bounded interpreter; no successful implementation is claimed.')
        from .synth import matches
        values = [r['value'] for r in result['cases']]
        if not matches(values, outputs):
            raise Unclear('The docstring interpretation and the literal doctest results disagree. Please resolve the specification; no code was emitted.')
        details = ('Preserved the declared function name, argument order, positional/keyword-only restrictions, literal defaults and static annotations. '
                   'Compiled the entire supported contract using '+method+'. Checked '+str(len(cases))+' literal doctests in the bounded AST VM. '
                   'No native code execution, neural model, external model, benchmark solution lookup or general-correctness proof.')
        return out('```python\n'+source+'```\n'+('Checked all '+str(len(cases))+' supplied literal doctests. ' if cases else 'No doctests were supplied. ')+
                   'This implements the supported symbolic contract; test additional inputs and boundaries.', 'built',
                   details=details, signature_checks=dict(method=method, doctests=len(cases), **evidence))
    except (Unclear, ValueError, TypeError, SyntaxError, RecursionError) as error:
        return out(str(error), 'clarify', details='No successful Python implementation is claimed; the complete signature/docstring remains the contract.')
    except Unsupported:
        return out('The contract exceeded the supported compiler/interpreter budget. No successful function is claimed.', 'unsupported')
