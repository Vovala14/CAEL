"""Independent checks on CAEL's answers, with corrections when a check finds an error.

Each check works the answer out a different way from the engine that produced it:

* arithmetic   - the expression is re-evaluated by a separate exact evaluator (fractions, own syntax walk).
* equations    - the solution is substituted back into the original equation; both sides must be equal.
* code         - the function is run on the person's own examples and on the tests shown in the reply.
* code fixes   - the repaired code must parse.
* logic proofs - a yes/no from rule chaining is re-checked by exhaustive case analysis (a different solver).
* sequences    - the found rule is re-run on every given number.
* plans        - every step is checked; a corrected step value is what later steps use.

Results: 'verified' (the check passed), 'failed' (it found an error; a correction is applied when the check
itself gives the right value, otherwise the reply carries a warning), or 'unchecked' (no independent check
exists for this kind of answer, e.g. a looked-up fact or a story). Counts go to long-term memory per engine.
"""
import ast
from fractions import Fraction
import math
import re

NUMBER = r'-?\d+(?:\.\d+)?(?:/\d+)?'
SAFE_BUILTINS = ('len', 'sum', 'min', 'max', 'sorted', 'list', 'dict', 'set', 'tuple', 'str', 'int', 'float', 'abs', 'round',
                 'range', 'all', 'any', 'zip', 'enumerate', 'reversed', 'bool', 'isinstance', 'map', 'filter')


class Unchecked(Exception):
    pass


def exact(text):
    """'5/2', '2.5', '-3' -> Fraction."""
    return Fraction(text.replace(',', ''))


def evaluate(node, names=None):
    """A separate exact evaluator: + - * / // % ** and unary minus on fractions only."""
    names = names or {}
    if isinstance(node, ast.Expression):
        return evaluate(node.body, names)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return Fraction(str(node.value))
    if isinstance(node, ast.Name) and node.id in names:
        return names[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = evaluate(node.operand, names)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp):
        a, b = evaluate(node.left, names), evaluate(node.right, names)
        if isinstance(node.op, ast.Add):
            return a + b
        if isinstance(node.op, ast.Sub):
            return a - b
        if isinstance(node.op, ast.Mult):
            return a * b
        if isinstance(node.op, ast.Div):
            return a / b
        if isinstance(node.op, ast.FloorDiv):
            return Fraction(math.floor(a / b))
        if isinstance(node.op, ast.Mod):
            return a - b * math.floor(a / b)
        if isinstance(node.op, ast.Pow) and b.denominator == 1 and abs(b) <= 64:
            return a ** int(b)
    raise Unchecked('expression outside the checker')


def show(value):
    return str(value.numerator) if value.denominator == 1 else f'{value.numerator}/{value.denominator}'


# Checks -----------------------------------------------------------------------------------------
def check_arithmetic(request, answer):
    first = answer['response'].split('\n', 1)[0]
    match = re.fullmatch(r'(.+?) = (' + NUMBER + r')(?: \(about [^)]*\))?', first.strip())
    if not match:
        raise Unchecked('no "expression = value" line')
    expression = match[1].replace('×', '*').replace('÷', '/').replace('^', '**')
    try:
        tree = ast.parse(expression, mode='eval')
    except SyntaxError:
        raise Unchecked('expression does not parse')
    if sum(1 for _ in ast.walk(tree)) > 120:
        raise Unchecked('expression too large')
    expected = evaluate(tree)
    stated = exact(match[2])
    if expected == stated:
        return dict(status='verified', check=f're-evaluated {expression} independently: {show(expected)}')
    return dict(status='failed', check=f'independent evaluation gives {show(expected)}, not {match[2]}',
                correction=f'{match[1]} = {show(expected)}', value=show(expected))


def check_equation(request, answer):
    solved = re.match(r'([a-z]) = (' + NUMBER + r')', answer['response'])
    if not solved:
        raise Unchecked('no single solution stated')
    name, value = solved[1], exact(solved[2])
    equation = re.search(r'([\d\s' + name + r'+*/().\-]+=[\d\s' + name + r'+*/().\-]+)', request.lower())
    if not equation:
        raise Unchecked('equation not found in the request')
    text = re.sub(r'(\d|\))\s*(?=' + name + r'\b)', r'\1*', equation[1])
    text = re.sub(r'(\d|\))\s*(?=\()', r'\1*', text)
    try:
        left, right = [evaluate(ast.parse(side.strip(), mode='eval'), {name: value}) for side in text.split('=')]
    except (SyntaxError, ZeroDivisionError):
        raise Unchecked('equation does not parse')
    if left == right:
        return dict(status='verified', check=f'substituted {name} = {show(value)} back: both sides equal {show(left)}')
    return dict(status='failed', check=f'with {name} = {show(value)} the sides are {show(left)} and {show(right)}')


def sandbox_function(code):
    name = re.search(r'^def (\w+)\(', code, re.M)
    if not name:
        raise Unchecked('no function')
    builtins = __builtins__ if isinstance(__builtins__, dict) else vars(__builtins__)
    scope = {'math': math, '__builtins__': {k: builtins[k] for k in SAFE_BUILTINS}}
    exec(code.replace('import math\n', ''), scope)
    return name[1], scope[name[1]]


def check_code(request, answer):
    blocks = re.findall(r'```python\n(.*?)```', answer['response'], re.S)
    if not blocks:
        raise Unchecked('no code')
    code = blocks[0]
    if answer['route'] == 'chat/code-fixed':
        try:
            ast.parse(code)
        except SyntaxError as error:
            return dict(status='failed', check=f'the repaired code still does not parse: {error.msg}')
        return dict(status='verified', check='the repaired code parses')
    if not re.search(r'^def \w+\(', code, re.M):
        raise Unchecked('not a function')
    name, function = sandbox_function(code)
    tests = []
    for block in blocks[1:]:
        for line in block.splitlines():
            call = re.match(r'assert (' + re.escape(name) + r'\(.*\)) == (.+)$', line.strip())
            if call:
                tests.append((call[1], call[2]))
    from .codegen.chat import examples
    given_name, cases = examples(request)
    passed = failed = 0
    problems = []
    builtins = __builtins__ if isinstance(__builtins__, dict) else vars(__builtins__)
    for call, expected in tests:
        try:
            ok = eval(call, {name: function, '__builtins__': {k: builtins[k] for k in SAFE_BUILTINS}}) == ast.literal_eval(expected)
        except Exception:
            ok = False
        passed += ok
        failed += not ok
        if not ok:
            problems.append(f'{call} != {expected}')
    if given_name == name:
        for args, expected in cases:
            try:
                ok = function(*args) == expected
            except Exception:
                ok = False
            passed += ok
            failed += not ok
            if not ok:
                problems.append(f'{name}{args!r} != {expected!r}')
    if not passed and not failed:
        raise Unchecked('no tests to run')
    if failed:
        return dict(status='failed', check=f'{failed} of {passed + failed} tests fail: ' + '; '.join(problems[:3]))
    return dict(status='verified', check=f'ran the function on {passed} test{"s" if passed != 1 else ""}; all pass')


def check_logic(request, answer):
    result = answer.get('reasoning') or {}
    if result.get('family') != 'logic' or result.get('answer') not in ('true', 'false'):
        raise Unchecked('not a rule-chaining proof')
    from .reasoning import split_problem
    from .reasoning_logic import Unparsed
    from .reasoning_sat import query
    problem = split_problem(request)
    if not problem:
        raise Unchecked('premises not found')
    try:
        second = query(problem[0], problem[1])['answer']
    except Unparsed:
        raise Unchecked('case analysis cannot read these premises')
    if second == 'unknown':
        raise Unchecked('case analysis is undecided')
    if second == result['answer']:
        return dict(status='verified', check='exhaustive case analysis reaches the same conclusion')
    return dict(status='failed', check=f'exhaustive case analysis says {second}, rule chaining said {result["answer"]}')


def check_sequence(request, answer):
    from .rules import SEQUENCE, differences, run_rule
    match = SEQUENCE.search(request)
    stated = re.search(r'\*\*(' + NUMBER + r')\*\*', answer['response'])
    if not match or not stated:
        raise Unchecked('no sequence')
    numbers = [int(x) for x in re.findall(r'-?\d+', match[1] or match[2])]
    code = re.search(r'```python\n(.*?)```', answer['response'], re.S)
    if code:
        rule = dict(name='term', code=code[1])
        if [run_rule(rule, (i,)) for i in range(len(numbers))] != numbers:
            return dict(status='failed', check='the rule does not reproduce the given numbers')
        return dict(status='verified', check=f'the rule reproduces all {len(numbers)} given numbers')
    found = differences(numbers)
    if found and str(found[0]) == stated[1]:
        return dict(status='verified', check='finite differences of all the numbers give the same next value')
    raise Unchecked('no rule to re-run')


CHECKS = [('helper/arithmetic', check_arithmetic), ('helper/equation', check_equation), ('chat/code-', check_code),
          ('chat/reasoning-logic', check_logic), ('chat/rules-sequence', check_sequence)]


def check(request, answer):
    """dict(status, check, correction?) for one answer."""
    route = answer.get('route', '')
    for prefix, function in CHECKS:
        if route.startswith(prefix):
            try:
                return function(request, answer)
            except Unchecked as reason:
                return dict(status='unchecked', check=str(reason))
            except Exception as error:   # a checker bug must never break a reply
                return dict(status='unchecked', check=f'checker error: {type(error).__name__}')
    return dict(status='unchecked', check='no independent check for this kind of answer')


def apply(request, answer, record=True):
    """Check an answer, correct or flag it when the check fails, and record the outcome per engine."""
    from . import ltm
    if answer.get('route') == 'chat/plan':
        steps = [s.get('verification', {}).get('status', 'unchecked') for s in answer.get('plan', [])]
        status = 'failed' if 'failed' in steps else 'verified' if steps and all(s == 'verified' for s in steps) else \
            'partly verified' if 'verified' in steps else 'unchecked'
        return dict(answer, verification=dict(status=status, check=f'{steps.count("verified")} of {len(steps)} steps verified'))
    result = check(request, answer)
    answer = dict(answer, verification=result)
    if result['status'] == 'failed':
        if result.get('correction'):
            answer['response'] = (f'{result["correction"]}\n\n(Corrected: my first answer was wrong; an independent check '
                                  f'found it. {result["check"]}.)')
            result['status'] = 'corrected'
        else:
            answer['response'] = answer['response'].rstrip() + f'\n\n⚠ My own check found a problem: {result["check"]}.'
    if result['status'] != 'unchecked':
        answer['details'] = answer.get('details', '') + f'\nIndependent check ({result["status"]}): {result["check"]}.'
    if record:
        memory = ltm.memory()
        memory.record(answer.get('route'), 'answered')
        if result['status'] in ('verified', 'failed', 'corrected'):
            memory.record(answer.get('route'), 'verified' if result['status'] == 'verified' else 'failed', result['check'])
            if result['status'] == 'corrected':
                memory.record(answer.get('route'), 'corrected')
    return answer
