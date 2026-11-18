"""Scripts CAEL wrote for itself: a library of its own verified Python helpers.

During Python training (research/python_training_*/practice.py) CAEL's program
search solves practice tasks. Each function it writes that also passes a test the
search never saw is kept here as a script. Later searches can call these scripts as
single operations, so a new program can be built on top of helpers CAEL wrote
earlier, and a script can call older scripts. This is library learning by search
and verification only: no neural network, no stored human solution.

Only CAEL's own generated code is stored. Before a script is compiled, its syntax
tree is checked against the same small vocabulary the search writes in (built-ins
like len and sorted, the math module, other scripts); anything else is rejected.
Arguments are size-guarded so a helper cannot run away inside a search.
"""
import ast
import builtins
import json
import math
import re
from pathlib import Path

from . import synth
from .train import words

PATH = Path(__file__).resolve().parents[2] / 'models/cael-scripts-v1/library.json'
BUILTINS = {name: getattr(builtins, name)
            for name in ('len', 'sum', 'max', 'min', 'sorted', 'set', 'list', 'tuple', 'str', 'int', 'float', 'abs', 'bool',
                         'round', 'ord', 'chr', 'bin', 'dict', 'range', 'zip', 'any', 'all')}
ALLOWED_NODES = (ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return, ast.Import, ast.alias, ast.expr,
                 ast.expr_context, ast.operator, ast.boolop, ast.cmpop, ast.unaryop, ast.comprehension, ast.keyword,
                 ast.Expression)
COST = 3


class Rejected(ValueError):
    pass


def check_source(source, known=()):
    """Raise Rejected unless source is one function in the search's own vocabulary."""
    tree = ast.parse(source)
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    if len(functions) != 1 or any(not isinstance(n, (ast.FunctionDef, ast.Import)) for n in tree.body):
        raise Rejected('expected one function')
    allowed_names = set(BUILTINS) | {'math', 'True', 'False', 'None'} | set(known)
    local = {a.arg for a in functions[0].args.args}
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES) or isinstance(node, (ast.Await, ast.Yield, ast.YieldFrom, ast.NamedExpr)):
            raise Rejected(f'node {type(node).__name__}')
        if isinstance(node, ast.Import) and [a.name for a in node.names] != ['math']:
            raise Rejected('import')
        if isinstance(node, ast.Attribute) and node.attr.startswith('_'):
            raise Rejected('private attribute')
        if isinstance(node, ast.comprehension):
            local |= {n.id for n in ast.walk(node.target) if isinstance(n, ast.Name)}
        if isinstance(node, ast.Lambda):
            local |= {a.arg for a in node.args.args}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in allowed_names | local:
            raise Rejected(f'name {node.id}')
    return functions[0].name


def _guard(fn, loops):
    limit = 10 ** 4 if loops else synth.MAX_INT

    def call(*args):
        for a in args:
            if isinstance(a, int) and not isinstance(a, bool) and abs(a) > limit:
                raise ValueError('argument too large')
            if isinstance(a, (str, list, tuple, dict, set)) and len(a) > 500:
                raise ValueError('argument too long')
        return fn(*args)
    return call


def _literal(text):
    return ast.literal_eval(text)


class Library:
    """Scripts by name, compiled into one shared namespace (so scripts can call scripts)."""

    def __init__(self, scripts=()):
        self.scripts = {}
        self.namespace = dict(__builtins__=BUILTINS, math=math)
        for script in scripts:
            self.add(script)

    def source(self, script):
        return synth.render(script['name'], script['params'], script['expression'])

    def add(self, script):
        """Compile and re-check a script on its own tests; returns False if it is rejected."""
        name = script['name']
        if not name.isidentifier() or name in self.scripts or name in BUILTINS or name.startswith('_'):
            return False
        source = self.source(script)
        try:
            check_source(source, known=self.scripts)
            space = self.namespace
            exec(compile(source, f'<cael-script {name}>', 'exec'), space)  # CAEL's own checked code only
            fn = space[name]
            for args, expected in script['tests']:
                args, expected = _literal(args), _literal(expected)
                if not synth.matches((fn(*args),), (expected,)):
                    raise Rejected('own test failed')
        except Exception:
            self.namespace.pop(name, None)
            return False
        self.scripts[name] = dict(script, fn=_guard(fn, 'range(' in source or ' for ' in source))
        return True

    def __len__(self):
        return len(self.scripts)

    def ops(self, exclude=()):
        """The scripts as search operations, shaped like synth.OPS."""
        out = []
        for name, s in self.scripts.items():
            if name in exclude or s.get('origin') in exclude:
                continue
            kinds = tuple(set(k) for k in s['kinds'])
            template = name + '(' + ', '.join('{%d}' % i for i in range(len(kinds))) + ')'
            out.append((name, 'lib', kinds, s['fn'], template, s.get('cost', COST)))
        return out

    def uses(self, text):
        """Scripts an expression or source calls, with everything they call, oldest first."""
        found, todo = [], [n for n in self.scripts if re.search(r'\b' + re.escape(n) + r'\(', text)]
        while todo:
            name = todo.pop()
            if name in found:
                continue
            found.append(name)
            todo += [n for n in self.scripts if n != name and re.search(r'\b' + re.escape(n) + r'\(', self.scripts[name]['expression'])]
        order = list(self.scripts)
        return sorted(found, key=order.index)

    def render(self, function_name, params, expression):
        """The new function with the helper scripts it calls written out above it."""
        used = self.uses(expression)
        helpers = [self.source(self.scripts[n]).replace('import math\n\n\n', '') for n in used]
        main = synth.render(function_name, params, expression).replace('import math\n\n\n', '')
        if function_name in used:  # a helper with the new function's own name is written out as <name>_helper
            pattern = re.compile(r'\b' + re.escape(function_name) + r'\(')
            helpers = [pattern.sub(function_name + '_helper(', h) for h in helpers]
            head, body = main.split('\n', 1)
            main = head + '\n' + pattern.sub(function_name + '_helper(', body)
        code = '\n\n'.join(helpers + [main])
        return ('import math\n\n\n' if 'math.' in code else '') + code

    def lookup(self, description, least=0.6):
        """The script whose practice description best matches (word overlap), or None."""
        asked = words(description)
        if len(asked) < 2:
            return None
        best, score = None, 0.0
        for s in self.scripts.values():
            have = words(s['description'])
            if not have:
                continue
            overlap = len(asked & have) / len(asked | have)
            if overlap > score:
                best, score = s, overlap
        return best if score >= least else None

    def to_json(self):
        keep = ('name', 'params', 'kinds', 'expression', 'description', 'tests', 'origin', 'round', 'cost')
        return [{k: s[k] for k in keep if k in s} for s in self.scripts.values()]

    def save(self, path=PATH, note=''):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(version=1, note=note, scripts=self.to_json()), indent=1, ensure_ascii=False), encoding='utf-8')


def script_from(name, params, expression, description, tests, origin, round_, cost=None):
    """A library entry from a search result; tests are (inputs tuple, output) pairs."""
    kinds = [sorted({synth.kind(args[i]) for args, _ in tests}) for i in range(len(params))]
    entry = dict(name=name, params=list(params), kinds=kinds, expression=expression, description=description,
                 tests=[[repr(tuple(args)), repr(out)] for args, out in tests], origin=origin, round=round_)
    if cost is not None:
        entry['cost'] = cost
    return entry


_library = None


def load(path=PATH):
    global _library
    if path != PATH:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        return Library(data['scripts'])
    if _library is None:
        _library = Library(json.loads(PATH.read_text(encoding='utf-8'))['scripts'] if PATH.exists() else ())
    return _library
