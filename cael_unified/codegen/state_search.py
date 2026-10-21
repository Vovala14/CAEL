"""Example-guided synthesis of integer stream programs from a small grammar.

There are no task-name branches or completed function solutions here. A program
is an initial integer, an expression updating loop state, and a projection of
the resulting stream. Search uses interpreted primitive expressions, never
exec/eval. Agreement on examples is evidence, not a proof of the user's intent.
"""
from dataclasses import dataclass
import ast
import itertools
import keyword
import re
import time

LIMIT = 10 ** 12
RESERVED_NAMES = {'len', 'type', 'abs', 'any', 'enumerate', 'max', 'min', 'ValueError', 'list', 'int'}


class OutsideDomain(ValueError):
    pass


@dataclass(frozen=True)
class Expr:
    op: str
    args: tuple = ()

    @property
    def cost(self):
        return 1 + sum(a.cost for a in self.args if isinstance(a, Expr))

    def read(self, env):
        op = self.op
        if op == 'const':
            return self.args[0]
        if op == 'var':
            return env[self.args[0]]
        if op == 'if':
            return self.args[1 if self.args[0].read(env) else 2].read(env)
        a = self.args[0].read(env)
        b = self.args[1].read(env) if len(self.args) > 1 else None
        if op == '+': value = a + b
        elif op == '-': value = a - b
        elif op == '*': value = a * b
        elif op == '%': value = a % b
        elif op == 'max': value = max(a, b)
        elif op == 'min': value = min(a, b)
        elif op == 'abs': value = abs(a)
        elif op == '>': return a > b
        elif op == '<': return a < b
        elif op == '>=': return a >= b
        elif op == '<=': return a <= b
        elif op == '==': return a == b
        elif op == '!=': return a != b
        elif op == 'and': return bool(a and b)
        elif op == 'or': return bool(a or b)
        else: raise OutsideDomain('Unknown primitive')
        if type(value) is not int or abs(value) > LIMIT:
            raise OutsideDomain('Intermediate integer limit')
        return value

    def source(self):
        if self.op == 'const': return repr(self.args[0])
        if self.op == 'var': return self.args[0]
        parts = [a.source() for a in self.args]
        if self.op == 'if': return f'({parts[1]} if {parts[0]} else {parts[2]})'
        if self.op in {'max', 'min', 'abs'}: return self.op + '(' + ', '.join(parts) + ')'
        return '(' + (' ' + self.op + ' ').join(parts) + ')'


def node(op, *args):
    return Expr(op, tuple(args))


S, X, I, P = (node('var', name) for name in ('state', 'value', 'index', 'previous'))
ZERO, ONE = node('const', 0), node('const', 1)


def integer_list(value):
    return (type(value) is list and len(value) <= 40 and
            all(type(x) is int and abs(x) <= 10 ** 6 for x in value))


@dataclass(frozen=True)
class Program:
    initial: int
    update: Expr
    projection: str

    @property
    def cost(self):
        return self.update.cost + int(self.initial != 0) + int(self.projection not in {'last', 'scan'})

    def run(self, numbers):
        if not integer_list(numbers):
            raise OutsideDomain('Expected a list of at most 40 bounded integers')
        state, previous = self.initial, 0
        history = []
        for index, value in enumerate(numbers):
            state = self.update.read(dict(state=state, value=value, index=index, previous=previous))
            if type(state) is not int or abs(state) > LIMIT:
                raise OutsideDomain('State limit')
            history.append(state)
            previous = value
        if self.projection == 'scan': return history
        if self.projection == 'last': return state
        if self.projection == 'max': return max(history, default=self.initial)
        if self.projection == 'min': return min(history, default=self.initial)
        raise OutsideDomain('Projection')

    def render(self, name):
        if not name.isidentifier() or len(name)>80 or keyword.iskeyword(name) or name.startswith('_') or name in RESERVED_NAMES:
            raise OutsideDomain('Invalid function name')
        # Bounds are explicit in emitted code, so checked and real domains agree.
        lines = [f'def {name}(numbers):',
                 '    if type(numbers) is not list or len(numbers) > 40:',
                 "        raise ValueError('Expected a list of at most 40 integers')",
                 '    if any(type(x) is not int or abs(x) > 1000000 for x in numbers):',
                 "        raise ValueError('Expected bounded integer inputs')",
                 f'    state = {self.initial}', '    previous = 0', '    history = []',
                 '    for index, value in enumerate(numbers):',
                 '        state = ' + self.update.source(),
                 '        if abs(state) > 1000000000000:',
                 "            raise ValueError('Intermediate integer limit')",
                 '        history.append(state)', '        previous = value']
        if self.projection == 'scan': lines.append('    return history')
        elif self.projection == 'last': lines.append('    return state')
        else: lines.append(f'    return {self.projection}(history) if history else {self.initial}')
        return '\n'.join(lines) + '\n'


def grammar(description):
    """Finite grammar, with literals from the request, never expected outputs."""
    literals = {0, 1, 2, -1}
    # Strip example calls before extracting constants: labels are not a source
    # of constants. chat.py supplies only the description here as well.
    for literal in re.findall(r'(?<![\w.])-?\d{1,3}(?![\w.])', description):
        if abs(int(literal)) <= 100:
            literals.add(int(literal))
    if len(literals) > 9:
        raise OutsideDomain('Too many specification constants')
    const = [node('const', v) for v in sorted(literals)]
    atoms = [X, I, P, *const]
    terms = set(atoms + [node('abs', X)])
    for op in ('+', '-', '*'):
        for left, right in itertools.product([X, I], [X, I, *const]):
            terms.add(node(op, left, right))
    bases = {S, X, *const}
    for op in ('+', '-', '*', 'max', 'min'):
        for term in terms:
            bases.add(node(op, S, term))
    bases.add(node('-', X, S))
    # Cheap transition primitives can also be guarded and reset. This is a
    # grammar restriction, not a lookup of "running total" or "longest run".
    guarded = [S, X, node('+', S, X), node('-', S, X), node('*', S, X),
               node('+', S, ONE), node('-', S, ONE)]
    predicates = set()
    for c in const:
        for op in ('>', '<', '>=', '<=', '==', '!='):
            predicates.add(node(op, X, c))
    for v in literals:
        if 2 <= v <= 10:
            for op in ('==', '!='):
                predicates.add(node(op, node('%', X, node('const', v)), ZERO))
    # Conjunction/disjunction of atomic conditions can be stated explicitly.
    explicit = re.search(r'\bcondition\s*:\s*([^\n;]+)', description, re.I)
    if explicit:
        predicates.add(condition(explicit[1]))
    transitions = set(bases)
    for pred, yes, no in itertools.product(predicates, guarded, [S, ZERO, ONE]):
        if yes != no:
            transitions.add(node('if', pred, yes, no))
    return sorted(transitions, key=lambda e:(e.cost, e.source())), [0, 1, -1]


def condition(source):
    """Read a bounded boolean formula in terms of value; no Python execution."""
    tree = ast.parse(source.strip(), mode='eval')
    if sum(1 for _ in ast.walk(tree)) > 40:
        raise OutsideDomain('Condition too large')
    def read(n):
        if isinstance(n, ast.Name) and n.id in {'x', 'value'}: return X
        if isinstance(n, ast.Constant) and type(n.value) is int and abs(n.value) <= 100: return node('const', n.value)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub) and isinstance(n.operand, ast.Constant):
            v=n.operand.value
            if type(v) is int and abs(v)<=100:return node('const', -v)
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mod):
            rhs=read(n.right)
            if rhs.op!='const' or not 1<=rhs.args[0]<=10:raise OutsideDomain('Modulus')
            return node('%',read(n.left),rhs)
        comparisons={ast.Gt:'>',ast.Lt:'<',ast.GtE:'>=',ast.LtE:'<=',ast.Eq:'==',ast.NotEq:'!='}
        if isinstance(n,ast.Compare) and len(n.ops)==1 and type(n.ops[0]) in comparisons:
            return node(comparisons[type(n.ops[0])],read(n.left),read(n.comparators[0]))
        if isinstance(n,ast.BoolOp) and len(n.values)==2:
            return node('and' if isinstance(n.op,ast.And) else 'or',*(read(v) for v in n.values))
        raise OutsideDomain('Unsupported condition')
    result=read(tree.body)
    if result.op not in {'>','<','>=','<=','==','!=','and','or'}:
        raise OutsideDomain('Expected a boolean condition')
    return result


def probes(cases, description=''):
    """Inputs without answer labels; used only to find disagreements, not grade."""
    values=list(range(-3,11))
    for literal in re.findall(r'(?<![\w.])-?\d{1,3}(?![\w.])',description):
        value=int(literal)
        if abs(value)<=100:values.extend([value-1,value,value+1])
    for args,_ in cases:
        values.extend(args[0][:5])
    values=sorted(set(values))
    found=[[],*[[v] for v in values],*[[v,v] for v in values]]
    found.extend([list(v) for v in itertools.product([-2,0,1,3],repeat=3)])
    found.extend([[2,-1,3,-2,0],[-1,-1,2,3,-2,4],[0,1,1,0,1,1,1]])
    return found


def synthesize(cases, description='', seconds=2.0, max_programs=24000):
    """Return best supported hypothesis, or an explicit ambiguity/limit result.

    Both input and result types are checked. Every allowed transition at every
    allowed initial state is examined within the budget. All fitting hypotheses
    up to two cost units above the cheapest one are compared on unlabelled
    probes. No synthesized function is stored or reused as a training answer.
    """
    started=time.monotonic();stats=dict(programs=0,matching=0,complete=False)
    result=lambda status,**kw:dict(status=status,stats={**stats,'seconds':time.monotonic()-started},**kw)
    if not 2<=len(cases)<=16 or any(len(args)!=1 or not integer_list(args[0]) for args,_ in cases):
        return result('outside-domain')
    list_output=all(integer_list(out) for _,out in cases)
    scalar_output=all(type(out) is int and abs(out)<=LIMIT for _,out in cases)
    if not(list_output or scalar_output):return result('outside-domain')
    try:transitions,initials=grammar(description)
    except (OutsideDomain,SyntaxError,RecursionError):return result('outside-domain')
    modes=['scan'] if list_output else ['last','max','min']
    fits=[];best_cost=None
    for update,initial in itertools.product(transitions,initials):
        if best_cost is not None and update.cost+int(initial!=0)>best_cost+2:
            continue
        for mode in modes:
            program=Program(initial,update,mode)
            if best_cost is not None and program.cost>best_cost+2:continue
            stats['programs']+=1
            if stats['programs']>max_programs or time.monotonic()-started>seconds:
                return result('search-limit')
            try:
                if all(program.run(args[0])==expected for args,expected in cases):
                    fits.append(program);best_cost=program.cost if best_cost is None else min(best_cost,program.cost)
            except (OutsideDomain,ZeroDivisionError):pass
    stats['complete']=True;stats['matching']=len(fits)
    if not fits:return result('not-found')
    fits=sorted((p for p in fits if p.cost<=best_cost+2),key=lambda p:(p.cost,p.update.source(),p.initial,p.projection))
    best=fits[0]
    witnesses=probes(cases,description)
    for sample in witnesses:
        try:a=best.run(sample)
        except OutsideDomain:continue
        for other in fits[1:]:
            try:b=other.run(sample)
            except OutsideDomain:continue
            if a!=b:
                return result('ambiguous',witness=sample,predictions=[a,b],program=best)
    return result('synthesized',program=best,probe_count=len(witnesses),hypotheses_compared=len(fits))


def interested(description):
    """Stateful requests use this grammar; ordinary expression search stays intact."""
    return bool(re.search(r'\b(?:running|cumulative|consecutive|streak|accumulat\w*|stateful|scan|prefix|reset\w*)\b',description,re.I))


def reply(name, cases, description):
    if not interested(description):return None
    result=synthesize(cases,description)
    status=result['status'];stats=result['stats']
    details=('Non-neural integer program synthesis. A finite grammar supplies primitive arithmetic, predicates, '
             'loop-state updates and output projections; no completed function solutions or task-name lookup. '
             f"Examined {stats['programs']} programs; search complete={stats['complete']}. "
             'Examples constrain a hypothesis, not human-like understanding or a proof for all inputs.')
    out=lambda response,route:dict(response=response,route='chat/code-'+route,sources=[],details=details)
    if status=='outside-domain':return None
    if status=='ambiguous':
        a,b=result['predictions'];w=result['witness']
        return out(f'The examples leave more than one plausible program. What should `{name}({w!r})` return? '
                   f'Two candidate programs give `{a!r}` and `{b!r}`. Add the intended result as another example.', 'state-clarify')
    if status in {'not-found','search-limit'}:
        reason='within its bounded grammar' if status=='not-found' else 'within its search budget'
        return out(f'I could not synthesize a verified stateful function {reason}. '
                   'I currently support bounded integer lists with one accumulator. Specify the initial state, '
                   'the per-item update, or add contrasting examples.', 'state-not-found')
    p=result['program']
    try:code=p.render(name)
    except OutsideDomain:
        return out('Choose a public Python function name that does not shadow a required built-in.', 'state-clarify')
    return out(f'```python\n{code}```\nI constructed a loop with initial state `{p.initial}`, '
               f'update `{p.update.source()}`, and output `{p.projection}`. It matches all {len(cases)} examples. '
               f"The {result['hypotheses_compared']} low-cost fitting hypotheses agree on {result['probe_count']} "
               'additional unlabelled probe inputs; those are ambiguity checks, not independent correctness tests. '
               'Domain: lists of at most 40 integers, each within ±1,000,000, with bounded intermediate integers. '
               'Please check new inputs too.', 'state-synthesized')
