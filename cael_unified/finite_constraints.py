"""Bounded finite constraints: explicit domains, interpreted expressions, witnesses.

This is a reusable symbolic interpreter/search, not Python execution or a puzzle
answer table. Exhaustion, an incomplete search and a checked witness are distinct.
"""
import ast
from fractions import Fraction
import hashlib
import json
import time


class Unclear(ValueError):
    pass


UNKNOWN = object()
RESERVED = {'True', 'False', 'abs', 'all_different', 'sum', 'and', 'or', 'not', 'in'}


def literal(value):
    return (type(value) in (bool, str) and (type(value) is bool or 0 < len(value) <= 80)
            or type(value) is int and abs(value) <= 1000000)


def equal(a, b):
    if type(a) in (int, Fraction) and type(b) in (int, Fraction):
        return a == b
    return type(a) is type(b) and a == b


def numeric(value):
    if type(value) not in (int, Fraction):
        raise Unclear('Arithmetic and ordered comparisons require numbers, not Boolean or text values.')
    q = Fraction(value)
    if abs(q.numerator) > 1000000000 or q.denominator > 1000000000:
        raise Unclear('Arithmetic exceeded the exact rational size bound.')
    return q


def compile_rule(text, names):
    if not isinstance(text, str) or not 0 < len(text) <= 1000:
        raise Unclear('Each rule needs one bounded complete expression.')
    try:
        tree = ast.parse(text, mode='eval').body
    except (SyntaxError, RecursionError):
        raise Unclear('The complete rule is not in the admitted expression grammar.')
    nodes = list(ast.walk(tree))
    if len(nodes) > 180:
        raise Unclear('A rule exceeds the expression size limit.')
    admitted = (ast.Constant, ast.Name, ast.Load, ast.BinOp, ast.Add, ast.Sub, ast.Mult,
                ast.Div, ast.Mod, ast.UnaryOp, ast.USub, ast.UAdd, ast.Not,
                ast.BoolOp, ast.And, ast.Or, ast.Compare, ast.Eq, ast.NotEq,
                ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
                ast.Call, ast.List, ast.Tuple)
    call_functions = {id(n.func) for n in nodes if isinstance(n, ast.Call)}
    for node in nodes:
        if not isinstance(node, admitted):
            raise Unclear('Unsupported expression clause: ' + type(node).__name__ + '.')
        if isinstance(node, ast.Constant) and not literal(node.value):
            raise Unclear('Use bounded integer, text or Boolean constants.')
        if isinstance(node, ast.Name) and node.id not in names | {'abs', 'all_different', 'sum'}:
            raise Unclear('Undeclared variable: ' + node.id + '.')
        if isinstance(node, ast.Name) and node.id in {'abs', 'all_different', 'sum'} and id(node) not in call_functions:
            raise Unclear('A function name is not a value or predicate.')
        if isinstance(node, ast.Call):
            if (not isinstance(node.func, ast.Name) or node.func.id not in {'abs', 'all_different', 'sum'}
                    or node.keywords or not 1 <= len(node.args) <= 16):
                raise Unclear('Only abs(value), sum([values]) and all_different(values) are admitted calls.')
            if node.func.id in ('abs', 'sum') and len(node.args) != 1:
                raise Unclear('abs and sum need exactly one argument.')
        if isinstance(node, (ast.List, ast.Tuple)) and not 1 <= len(node.elts) <= 32:
            raise Unclear('Expression lists must contain 1 to 32 values.')
    refs = {n.id for n in nodes if isinstance(n, ast.Name) and n.id in names}
    return tree, refs


def validate_types(node, domains, depth=0):
    """Check even unreachable branches, using every declared domain's types."""
    if depth > 24:
        raise Unclear('Expression nesting exceeds the checked bound.')
    read = lambda n: validate_types(n, domains, depth+1)
    def scalar_shape(types):
        return ('scalar', set(types))
    def scalar(s):
        if s[0] != 'scalar':
            raise Unclear('This expression requires scalar operands.')
        return s[1]
    def number(s):
        if not scalar(s) <= {int, Fraction}:
            raise Unclear('An arithmetic/ordered operand has a nonnumeric admitted domain value.')
    def boolean(s):
        if scalar(s) != {bool}:
            raise Unclear('A logical operand is not a Boolean predicate.')
    if isinstance(node, ast.Constant):
        return scalar_shape([type(node.value)])
    if isinstance(node, ast.Name):
        return scalar_shape(type(v) for v in domains[node.id])
    if isinstance(node, (ast.List, ast.Tuple)):
        return ('list', [read(n) for n in node.elts])
    if isinstance(node, ast.BinOp):
        number(read(node.left));number(read(node.right))
        if isinstance(node.op, (ast.Div, ast.Mod)) and isinstance(node.right, ast.Constant) and node.right.value == 0:
            raise Unclear('A denominator is zero.')
        return scalar_shape([Fraction])
    if isinstance(node, ast.UnaryOp):
        child=read(node.operand)
        if isinstance(node.op, ast.Not):
            boolean(child);return scalar_shape([bool])
        number(child);return scalar_shape([Fraction])
    if isinstance(node, ast.BoolOp):
        for n in node.values:boolean(read(n))
        return scalar_shape([bool])
    if isinstance(node, ast.Compare):
        shapes=[read(node.left)]+[read(n) for n in node.comparators]
        for a, op, b in zip(shapes,node.ops,shapes[1:]):
            if isinstance(op,(ast.In,ast.NotIn)):
                scalar(a)
                if b[0]!='list':raise Unclear('Membership requires an explicit list.')
                for s in b[1]:scalar(s)
            elif isinstance(op,(ast.Eq,ast.NotEq)):
                scalar(a);scalar(b)
            else:
                number(a);number(b)
        return scalar_shape([bool])
    if isinstance(node, ast.Call):
        shapes=[read(n) for n in node.args];name=node.func.id
        if name=='all_different':
            if len(shapes)==1 and shapes[0][0]=='list':shapes=shapes[0][1]
            for s in shapes:scalar(s)
            return scalar_shape([bool])
        if name=='sum':
            if shapes[0][0]!='list':raise Unclear('sum requires a list.')
            for s in shapes[0][1]:number(s)
        else:number(shapes[0])
        return scalar_shape([Fraction])
    raise Unclear('Unsupported expression type.')


def interpret(node, assignment, depth=0):
    if depth > 24:
        raise Unclear('Expression nesting exceeds the checked bound.')
    read = lambda n: interpret(n, assignment, depth + 1)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return assignment.get(node.id, UNKNOWN)
    if isinstance(node, (ast.List, ast.Tuple)):
        return [read(n) for n in node.elts]
    if isinstance(node, ast.UnaryOp):
        value = read(node.operand)
        if value is UNKNOWN:
            return UNKNOWN
        if isinstance(node.op, ast.Not):
            if type(value) is not bool:
                raise Unclear('not requires a Boolean predicate.')
            return not value
        return numeric(-numeric(value) if isinstance(node.op, ast.USub) else numeric(value))
    if isinstance(node, ast.BinOp):
        a, b = read(node.left), read(node.right)
        if a is UNKNOWN or b is UNKNOWN:
            return UNKNOWN
        a, b = numeric(a), numeric(b)
        if isinstance(node.op, (ast.Div, ast.Mod)) and b == 0:
            raise Unclear('A rule is undefined for an admitted zero denominator.')
        if isinstance(node.op, ast.Add):
            result = a + b
        elif isinstance(node.op, ast.Sub):
            result = a - b
        elif isinstance(node.op, ast.Mult):
            result = a * b
        elif isinstance(node.op, ast.Div):
            result = a / b
        else:
            if a.denominator != 1 or b.denominator != 1:
                raise Unclear('Remainder needs integers.')
            result = a % b
        return numeric(result)
    if isinstance(node, ast.BoolOp):
        values = [read(n) for n in node.values]  # inspect every branch
        if any(v is not UNKNOWN and type(v) is not bool for v in values):
            raise Unclear('and/or require predicates, not arbitrary truthy values.')
        if isinstance(node.op, ast.And):
            return False if False in values else UNKNOWN if any(v is UNKNOWN for v in values) else True
        return True if True in values else UNKNOWN if any(v is UNKNOWN for v in values) else False
    if isinstance(node, ast.Call):
        values = [read(n) for n in node.args]
        name = node.func.id
        if name == 'all_different':
            if len(values) == 1 and type(values[0]) is list:
                values = values[0]
            assigned = [v for v in values if v is not UNKNOWN]
            if any(type(v) is list for v in assigned):
                raise Unclear('all_different needs scalar values.')
            if any(equal(a, b) for i, a in enumerate(assigned) for b in assigned[i+1:]):
                return False
            return UNKNOWN if len(assigned) != len(values) else True
        if name == 'sum':
            if type(values[0]) is not list:
                raise Unclear('sum needs an explicit list.')
            values = values[0]
            if any(v is UNKNOWN for v in values):
                return UNKNOWN
            return numeric(sum((numeric(v) for v in values), Fraction(0)))
        if values[0] is UNKNOWN:
            return UNKNOWN
        return numeric(abs(numeric(values[0])))
    if isinstance(node, ast.Compare):
        operands = [read(node.left)] + [read(n) for n in node.comparators]
        results = []
        for a, op, b in zip(operands, node.ops, operands[1:]):
            if a is UNKNOWN or b is UNKNOWN or type(b) is list and any(v is UNKNOWN for v in b):
                results.append(UNKNOWN)
            elif isinstance(op, (ast.In, ast.NotIn)):
                if type(b) is not list or type(a) is list:
                    raise Unclear('Membership needs a scalar and explicit list.')
                inside = any(equal(a, v) for v in b)
                results.append(inside if isinstance(op, ast.In) else not inside)
            elif type(a) is list or type(b) is list:
                raise Unclear('Lists are admitted only in membership, sum and all_different.')
            elif isinstance(op, (ast.Eq, ast.NotEq)):
                same = equal(a, b)
                results.append(same if isinstance(op, ast.Eq) else not same)
            else:
                a, b = numeric(a), numeric(b)
                results.append(a < b if isinstance(op, ast.Lt) else a <= b if isinstance(op, ast.LtE)
                               else a > b if isinstance(op, ast.Gt) else a >= b)
        return False if False in results else UNKNOWN if any(v is UNKNOWN for v in results) else True
    raise Unclear('Unsupported predicate node.')


def prepare(task):
    if type(task) is not dict or set(task) != {'domains', 'constraints'}:
        raise Unclear('A finite task needs exactly domains and constraints.')
    domains = task['domains']
    if type(domains) is not dict or not 1 <= len(domains) <= 16:
        raise Unclear('Use 1 to 16 explicitly declared variables.')
    for name, values in domains.items():
        if (type(name) is not str or not name.isidentifier() or not name.isascii()
                or name in RESERVED or len(name) > 40):
            raise Unclear('Variable names need distinct bounded identifiers, excluding expression keywords.')
        if (type(values) is not list or not 1 <= len(values) <= 32
                or any(not literal(v) for v in values)):
            raise Unclear('Each domain needs 1 to 32 bounded literal values.')
        if any(equal(a, b) for i, a in enumerate(values) for b in values[i+1:]):
            raise Unclear('A domain repeats a value.')
    rules = task['constraints']
    if type(rules) is not list or not 0 <= len(rules) <= 64:
        raise Unclear('Use at most 64 complete constraints.')
    compiled = [compile_rule(s, set(domains)) for s in rules]
    for tree, _ in compiled:
        if validate_types(tree, domains) != ('scalar', {bool}):
            raise Unclear('Every rule must be a Boolean predicate, including all branches.')
    return domains, compiled


def solve(task, max_nodes=20000, max_solutions=256, seconds=2.0):
    domains, compiled = prepare(task)
    started = time.monotonic()
    nodes, solutions, stop = 0, [], None
    class SearchLimit(Exception):pass

    def compatible(partial):
        if time.monotonic()-started > seconds:
            raise SearchLimit()
        matched = True
        for tree, refs in compiled:
            result = interpret(tree, partial)
            if result is not UNKNOWN and type(result) is not bool:
                raise Unclear('Every complete constraint must evaluate to a Boolean predicate.')
            if result is False:
                matched = False
        return matched

    def visit(partial):
        nonlocal nodes, stop
        if stop:
            return
        if nodes >= max_nodes or time.monotonic() - started > seconds:
            stop = 'resource-limit'
            return
        nodes += 1
        if not compatible(partial):
            return
        if len(partial) == len(domains):
            # Independent full witness replay: no partial/unknown can pass.
            if any(interpret(tree, partial) is not True for tree, _ in compiled):
                raise AssertionError('A full witness did not satisfy every rule.')
            solutions.append(dict(partial))
            if len(solutions) >= max_solutions:
                stop = 'solution-limit'
            return
        choices = []
        for name, values in domains.items():
            if name in partial:
                continue
            remaining = [v for v in values if compatible(dict(partial, **{name: v}))]
            if not remaining:
                return
            degree = sum(name in refs for _, refs in compiled)
            choices.append((len(remaining), -degree, name, remaining))
        _, _, name, remaining = min(choices)
        for value in remaining:
            visit(dict(partial, **{name: value}))
            if stop:
                break

    try:
        visit({})
    except SearchLimit:
        stop = 'resource-limit'
    complete = stop is None
    possibilities = {}
    for name in domains:
        values = []
        for s in solutions:
            if not any(equal(s[name], v) for v in values):
                values.append(s[name])
        possibilities[name] = values
    forced = {n: v[0] for n, v in possibilities.items() if complete and len(v) == 1}
    return dict(status=stop or ('satisfiable' if solutions else 'inconsistent'), complete=complete,
                solution_count=len(solutions), solutions=solutions, possible_values=possibilities,
                forced=forced, visited_nodes=nodes, seconds=time.monotonic()-started,
                witnesses_replayed=True, neural=False,
                task_sha256=hashlib.sha256(json.dumps(task, sort_keys=True, separators=(',', ':')).encode()).hexdigest())
