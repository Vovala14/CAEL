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


def evaluate(node, names=None, source=None):
    """A separate exact evaluator: + - * / // % ** and unary minus on fractions only."""
    names = names or {}
    if isinstance(node, ast.Expression):
        return evaluate(node.body, names, source)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return Fraction(ast.get_source_segment(source, node) if source is not None else str(node.value))
    if isinstance(node, ast.Name) and node.id in names:
        return names[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = evaluate(node.operand, names, source)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp):
        a, b = evaluate(node.left, names, source), evaluate(node.right, names, source)
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
    expected = evaluate(tree, source=expression)
    stated = exact(match[2])
    if expected == stated:
        return dict(status='verified', check=f're-evaluated {expression} independently: {show(expected)}')
    return dict(status='failed', check=f'independent evaluation gives {show(expected)}, not {match[2]}',
                correction=f'{match[1]} = {show(expected)}', value=show(expected))


def check_equation(request, answer):
    solved = re.findall(r'\b([a-z]) = (' + NUMBER + r')', answer['response'].split('\n', 1)[0])
    if not solved:
        raise Unchecked('no single solution stated')
    text = request.lower().strip().rstrip(' ?.').replace('−', '-').replace('×', '*').replace('÷', '/')
    text = re.sub(r'^(?:please\s+|(?:can|could|would) you\s+(?:please\s+)?)', '', text)
    text = re.sub(r'^(?:solve(?:\s+(?:the\s+)?(?:equations?|system))?(?:\s+for\s+[a-z](?:\s*(?:and|,)\s*[a-z])?)?\s*:?\s*|find\s+[a-z]\s+(?:in\s+)?)', '', text)
    if not re.fullmatch(r'[\d\sa-z+*/().,^=;\-]+', text) or any(w != 'and' for w in re.findall(r'[a-z]{2,}', text)):
        raise Unchecked('the complete original equation is outside the checker grammar')
    text = text.replace('^', '**')
    text = re.sub(r'(\d|\))\s*(?=[a-z]\b)', r'\1*', text)
    text = re.sub(r'\b([a-z])\s*(?=\()', r'\1*', text)
    text = re.sub(r'(\d|\))\s*(?=\()', r'\1*', text)
    parts = re.split(r'\s*;\s*|\s*,\s*|\s+and\s+', text)
    if len(parts) > 2 or any(p.count('=') != 1 for p in parts):
        raise Unchecked('equation count')
    from itertools import product
    values = {}
    for name, value in solved:
        values.setdefault(name, []).append(exact(value))
    if len(values) > 2 or len(solved) > 4:
        raise Unchecked('solution count')
    checks = 0
    try:
        for chosen in product(*values.values()):
            names = dict(zip(values, chosen))
            for equation in parts:
                sides = [side.strip() for side in equation.split('=')]
                trees = [ast.parse(side, mode='eval') for side in sides]
                if sum(sum(1 for _ in ast.walk(t)) for t in trees) > 180:
                    raise Unchecked('equation AST limit')
                left, right = [evaluate(tree, names, source=side) for tree, side in zip(trees, sides)]
                if left != right:
                    return dict(status='failed', check='a stated solution does not satisfy the complete original equation')
                checks += 1
    except SyntaxError:
        raise Unchecked('equation does not parse')
    except ZeroDivisionError:
        return dict(status='failed', check='a stated solution makes the original equation undefined')
    return dict(status='verified', check=f'checked {checks} exact substitutions in the complete original equation(s)')


def sandbox_function(code):
    raise Unchecked('Native generated-code execution is disabled; use the bounded AST interpreter')


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
    name = re.search(r'^def (\w+)\(', code, re.M)[1]
    tests = []
    for block in blocks[1:]:
        try:
            tree = ast.parse(block)
        except SyntaxError:
            continue
        for statement in tree.body:
            if not isinstance(statement, ast.Assert) or not isinstance(statement.test, ast.Compare):
                continue
            test = statement.test
            if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq) or not isinstance(test.left, ast.Call):
                continue
            call = test.left
            if not isinstance(call.func, ast.Name) or call.func.id != name or any(k.arg is None for k in call.keywords):
                continue
            try:
                args = [ast.literal_eval(a) for a in call.args]
                kwargs = {k.arg: ast.literal_eval(k.value) for k in call.keywords}
                expected = ast.literal_eval(test.comparators[0])
            except (ValueError, TypeError, SyntaxError):
                continue
            tests.append((dict(name=name, args=args, kwargs=kwargs), expected))
    from .codegen.chat import examples
    given_name, cases = examples(request)
    if given_name == name:
        for args, expected in cases:
            tests.append((dict(name=name, args=args), expected))
    if not tests:
        raise Unchecked('no tests to run')
    if len(tests) > 100:
        raise Unchecked('test count exceeds the bounded checker budget')
    from .codegen.python_vm import run_cases
    result = run_cases(code, [call for call, _ in tests])
    if result['status'] in ('unsupported', 'limit') or any(r['status'] in ('unsupported', 'limit') for r in result.get('cases', [])):
        raise Unchecked('bounded interpreter does not cover this program or exceeded its budget')
    if result['status'] != 'ok':
        return dict(status='failed', check='the bounded interpreter could not load the function')
    passed = sum(row['status'] == 'value' and row.get('value') == expected
                 for row, (_, expected) in zip(result['cases'], tests))
    failed = len(tests) - passed
    if failed:
        return dict(status='failed', check=f'{failed} of {len(tests)} bounded interpreter tests fail')
    return dict(status='verified', check=f'interpreted {passed} tests with the bounded AST VM; all pass')


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
    if 'python_tool' in answer:
        from .codegen.tool_contract import read
        try:read(answer['python_tool'])
        except ValueError as error:return dict(status='failed',check=str(error))
        return dict(status='unchecked',check='Compiler/plan consistency checks are recorded on the tool; they are not an independent proof of intent. Calls use the bounded Python interpreter.')
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
