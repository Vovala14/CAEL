"""Bounded exact symbolic mathematics and explicit quantity frames.

Authored helper algorithms, not learned language weights. Parse Python AST
ourselves; never sympify/eval an untrusted string. No model or network calls.
"""
import ast
from fractions import Fraction
import math
import re

import sympy as sp

N = r'-?\d{1,9}(?:\.\d{1,6})?'


def parsed(source):
    source = source.strip().replace('−', '-').replace('×', '*').replace('÷', '/').replace('^', '**')
    source = re.sub(r'(\d|\))\s*(?=[a-z(])', r'\1*', source)
    source = re.sub(r'\b([a-z])\s*(?=\()', r'\1*', source)
    if not source or len(source) > 240 or '__' in source:
        raise ValueError('Expression limit')
    tree = ast.parse(source, mode='eval')
    if sum(1 for _ in ast.walk(tree)) > 90:
        raise ValueError('Expression limit')

    def read(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            if not math.isfinite(float(node.value)) or abs(node.value) > 10**50:
                raise ValueError('Number limit')
            return sp.Rational(ast.get_source_segment(source, node))
        if isinstance(node, ast.Name):
            if node.id == 'pi':
                return sp.pi
            if re.fullmatch('[a-z]', node.id):
                return sp.Symbol(node.id)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            x = read(node.operand)
            return -x if isinstance(node.op, ast.USub) else x
        if isinstance(node, ast.BinOp):
            a, b = read(node.left), read(node.right)
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.Mult):
                return a * b
            if isinstance(node.op, ast.Div) and b != 0:
                return a / b
            if isinstance(node.op, ast.Mod) and a.is_Integer and b.is_Integer and b:
                return a % b
            if isinstance(node.op, ast.Pow) and b.is_Integer and abs(b) <= 64:
                if a.free_symbols and (abs(b) > 6 or a.has(sp.Pow)):
                    raise ValueError('Symbolic power limit')
                if a.is_Rational and max(abs(int(a.p)).bit_length(), int(a.q).bit_length()) * max(1, abs(int(b))) > 4096:
                    raise ValueError('Power limit')
                return a ** b
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            args = [read(x) for x in node.args]
            name = node.func.id
            if name in {'sqrt', 'abs', 'sin', 'cos', 'tan'} and len(args) == 1:
                return {'sqrt': sp.sqrt, 'abs': sp.Abs, 'sin': sp.sin, 'cos': sp.cos, 'tan': sp.tan}[name](*args)
            if name in {'gcd', 'lcm', 'comb'} and len(args) == 2 and all(x.is_Integer and abs(x) <= 10**9 for x in args):
                a, b = map(int, args)
                if name == 'comb' and not (0 <= b <= a <= 1000):
                    raise ValueError('Combination limit')
                return sp.Integer({'gcd': math.gcd, 'lcm': math.lcm, 'comb': math.comb}[name](a, b))
            if name == 'factorial' and len(args) == 1 and args[0].is_Integer and 0 <= args[0] <= 100:
                return sp.Integer(math.factorial(int(args[0])))
        raise ValueError('Unsupported expression')

    value = read(tree.body)
    if value.has(sp.zoo, sp.oo, -sp.oo, sp.nan) or sp.count_ops(value) > 100:
        raise ValueError('Undefined or oversized expression')
    return value


def fmt(value):
    if isinstance(value, Fraction):
        value = sp.Rational(value.numerator, value.denominator)
    if isinstance(value, sp.Rational) and not value.is_Integer:
        denominator = int(value.q)
        for prime in (2, 5):
            while denominator % prime == 0:
                denominator //= prime
        if denominator == 1:
            from decimal import Decimal, localcontext
            with localcontext() as context:
                context.prec = 100
                return format(Decimal(int(value.p))/Decimal(int(value.q)), 'f').rstrip('0').rstrip('.')
    return str(value).replace('**', '^')


def answer(response, steps, kind='symbolic'):
    return dict(route='helper/' + kind, response=response, sources=[], exact=True,
                details='Authored bounded exact mathematics; AST allowlist and rational/symbolic arithmetic. '
                        'No neural inference, benchmark answers or internet.\n' + '\n'.join(steps),
                helper_reasoning=dict(steps=steps, exact=True))


def equations(text):
    text = re.sub(r'(?i)^(?:please\s+)?(?:solve(?:\s+(?:the\s+)?(?:equations?|system))?(?:\s+for\s+[a-z](?:\s*(?:and|,)\s*[a-z])?)?\s*:?\s*|find\s+[a-z]\s+(?:in\s+)?)', '', text).rstrip(' ?.')
    parts = re.split(r'\s*;\s*|\s*,\s*|\s+and\s+', text)
    if len(parts) not in {1, 2} or any(p.count('=') != 1 for p in parts):
        return None
    expressions = [parsed(a) - parsed(b) for a, b in (p.split('=') for p in parts)]
    variables = sorted(set().union(*(e.free_symbols for e in expressions)), key=str)
    if not variables or len(variables) > 2:
        return None
    polys = [sp.Poly(e, *variables) for e in expressions]
    if len(variables) == 2:
        if len(parts) != 2 or any(p.total_degree() > 1 for p in polys):
            return None
        solutions = sp.linsolve(expressions, variables)
        if solutions == sp.EmptySet:
            return answer('The system has no solution.', [text], 'equation')
        values = next(iter(solutions))
        if any(v.free_symbols for v in values):
            return answer('The system has infinitely many solutions; another independent constraint is needed.', [text], 'equation')
        return answer(', '.join(f'{v} = {fmt(x)}' for v, x in zip(variables, values)),
                      ['Solve both equations simultaneously using exact elimination.'], 'equation')
    if len(parts) != 1 or polys[0].degree() > 2:
        return None
    x = variables[0]
    if polys[0].degree() <= 1:
        # Existing linear helper owns identities, contradictions and follow-ups.
        return None
    a, b, c = polys[0].all_coeffs()
    discriminant = b*b - 4*a*c
    if discriminant.is_negative:
        return answer('There are no real solutions.', [f'Discriminant = {fmt(discriminant)} < 0.'], 'equation')
    values = sorted({sp.cancel((-b + sign*sp.sqrt(discriminant))/(2*a)) for sign in (-1, 1)}, key=sp.default_sort_key)
    return answer(' or '.join(f'{x} = {fmt(v)}' for v in values),
                  [f'Discriminant = {fmt(discriminant)}.', 'Use the quadratic formula; substitute each root into the original equation.'], 'equation')


def word_frame(text):
    lower = text.lower().strip().rstrip(' ?.').replace(',', '')
    # Explicit unit-price relation; require the same product in both quantities.
    m = re.fullmatch(r'(?:if\s+)?(' + N + r')\s+(\w+)\s+cost\s+\$?(' + N + r')[.;]?\s+(?:how much (?:do|would)|what (?:do|would))\s+(' + N + r')\s+\2\s+cost', lower)
    if m and Fraction(m[1]) > 0:
        unit = Fraction(m[3]) / Fraction(m[1]); total = unit * Fraction(m[4])
        return answer(f'Total cost = {fmt(total)}.', [f'Unit price = {m[3]} / {m[1]} = {unit}.', f'{unit} * {m[4]} = {total}.'], 'proportion')
    ratio = re.fullmatch(r'(?:split|divide|share)\s+(' + N + r')\s+(?:in (?:the )?ratio|in a ratio of)\s*(\d+)\s*:\s*(\d+)', lower)
    if ratio and int(ratio[2]) + int(ratio[3]) > 0:
        unit = Fraction(ratio[1]) / (int(ratio[2]) + int(ratio[3]))
        return answer(f'{unit*int(ratio[2])} and {unit*int(ratio[3])}', ['Divide the total by the sum of ratio parts, then multiply by each part.'], 'ratio')
    # One explicit price and one/two explicit percentage operations, in order.
    money = list(re.finditer(r'\$(' + N + r')', lower))
    operations = list(re.finditer(r'(' + N + r')\s*%\s*(discount|off|tax|increase|decrease)', lower))
    if len(money) == 1 and 1 <= len(operations) <= 2 and re.search(r'\b(?:final|after|pay|price|cost|total)\b', lower):
        scrubbed = re.sub(r'\$(' + N + r')|(' + N + r')\s*%\s*(?:discount|off|tax|increase|decrease)', '', lower)
        if re.search(r'\d', scrubbed):
            return None
        value = Fraction(money[0][1]); steps = []
        for operation in operations:
            rate = Fraction(operation[1]) / 100
            multiplier = 1 + rate if operation[2] in {'tax', 'increase'} else 1 - rate
            if multiplier < 0:
                return None
            steps.append(f'{value} * {multiplier} = {value*multiplier}')
            value *= multiplier
        return answer(f'Final price = {fmt(value)}.', steps, 'percentage')
    fraction = re.fullmatch(r'(?:what is |calculate )?(' + N + r'/\d+)\s+of\s+(' + N + r')', lower)
    if fraction:
        value = Fraction(fraction[1]) * Fraction(fraction[2])
        return answer(f'{fraction[1]} of {fraction[2]} = {fmt(value)}', ['Multiply the fraction by the amount.'], 'fraction')
    temperature = re.fullmatch(r'(?:convert )?(' + N + r')\s*(?:degrees?\s*)?(celsius|fahrenheit|°c|°f)\s+(?:to|in)\s+(celsius|fahrenheit|°c|°f)', lower)
    if temperature:
        a, b = temperature[2] in {'celsius', '°c'}, temperature[3] in {'celsius', '°c'}
        value = Fraction(temperature[1])
        value = value if a == b else value*9/5+32 if a else (value-32)*5/9
        return answer(f'{temperature[1]} {temperature[2]} = {fmt(value)} {temperature[3]}', ['F = 9*C/5 + 32; C = 5*(F-32)/9.'], 'conversion')
    speed = re.fullmatch(r'(?:a |the )?(?:train|car|cyclist|runner)\s+(?:travels|moves|drives|runs)\s+at\s+(' + N + r')\s*(km/h|mph)\s+for\s+(' + N + r')\s+hours?[.;]?\s+how far (?:does|will) (?:it|the \w+) (?:travel|go|move)', lower)
    if speed:
        value = Fraction(speed[1])*Fraction(speed[3])
        return answer(f'Distance = {fmt(value)} ' + ('km' if speed[2] == 'km/h' else 'miles'), ['Distance = constant speed * time.'], 'rate')
    return None


def geometry(text):
    if not re.search(r'\b(?:find|what|calculate)\b', text):
        return None
    area = bool(re.search(r'\barea\b', text)); perimeter = bool(re.search(r'\bperimeter|circumference\b', text))
    if area == perimeter:
        return None
    # No incidental numeric labels or extra dimensions may be ignored.
    found = list(re.finditer(r'(?<!\w)' + N + r'(?!\w)', text))
    values = [Fraction(x[0]) for x in found]
    if not values or any(v < 0 for v in values):
        return None
    from .helper import UNITS, unit_key
    units = []
    for match in found:
        following = re.match(r'\s*([a-z]+)', text[match.end():])
        units.append(unit_key(following[1]) if following else None)
    known = [unit for unit in units if unit]
    unit_label = ''
    if known:
        if any(UNITS[unit][0] != 'length' for unit in known):
            return None
        reference = known[0]
        values = [value * UNITS[unit or reference][1] / UNITS[reference][1] for value, unit in zip(values, units)]
        unit_label = ' square ' + reference if area else ' ' + reference
    value = None; formula = ''
    if re.search(r'\brectangle|rectangular\b', text) and len(values) == 2:
        a, b = values; value = a*b if area else 2*(a+b); formula = 'Area = length * width.' if area else 'Perimeter = 2*(length+width).'
    elif re.search(r'\bsquare\b', text) and len(values) == 1:
        value = values[0]**2 if area else 4*values[0]; formula = 'Area = side^2.' if area else 'Perimeter = 4*side.'
    elif re.search(r'\btriangle\b', text):
        if area and len(values) == 2 and 'base' in text and 'height' in text:
            value = values[0]*values[1]/2; formula = 'Triangle area = base * perpendicular height / 2.'
        elif perimeter and len(values) == 3:
            value = sum(values); formula = 'Perimeter = sum of three sides.'
    elif re.search(r'\bcircle\b', text) and len(values) == 1 and re.search(r'\bradius|diameter\b', text):
        radius = values[0]/2 if 'diameter' in text else values[0]
        radius = sp.Rational(radius.numerator, radius.denominator)
        value = sp.pi*radius**2 if area else 2*sp.pi*radius
        formula = 'Circle area = pi*r^2.' if area else 'Circumference = 2*pi*r.'
    if value is None:
        return None
    extra = '' if isinstance(value, Fraction) or value.is_Rational else f' (approximately {float(value):.10g})'
    return answer(('Area' if area else 'Perimeter') + f' = {fmt(value)}' + unit_label + extra, [formula], 'geometry')


def reply(text):
    if len(text) > 500 or '\n' in text or '```' in text:
        return None
    text = text.strip().rstrip(' ?.').lower()
    text = re.sub(r'^(?:please\s+|(?:can|could|would) you\s+(?:please\s+)?)(?=(?:calculate|compute|solve|find|evaluate|factor|expand|simplify|convert|differentiate)\b)', '', text)
    try:
        if '=' in text:
            return equations(text)
        frame = word_frame(text)
        if frame:
            return frame
        from .helper_math_frames import solve as frame_solve
        framed = frame_solve(text)
        if framed:
            value, derivation, assumptions = framed
            return answer(f'Answer = {fmt(value)}' + ('%' if assumptions == 'Result is a percentage.' else ''), [derivation, assumptions], 'relationship')
        shape = geometry(text)
        if shape:
            return shape
        stats = re.fullmatch(r'(?:what is (?:the )?|find (?:the )?|(?:calculate|compute) (?:the )?)?(mean|average|median|range)\s+of\s*\[?([\d\s.,/\-]+(?:\s+and\s+[\d./\-]+)?)\]?', text)
        if stats:
            values = [Fraction(x.strip()) for x in re.split(r'\s*,\s*|\s+and\s+', stats[2])]
            if not 1 <= len(values) <= 100:
                return None
            ordered = sorted(values); n = len(values)
            result = {'mean': lambda: sum(values)/n, 'average': lambda: sum(values)/n,
                      'median': lambda: (ordered[(n-1)//2]+ordered[n//2])/2,
                      'range': lambda: ordered[-1]-ordered[0]}[stats[1]]()
            return answer(f'{stats[1].capitalize()} = {fmt(result)}', [f'{n} supplied values; exact rational calculation.'], 'statistics')
        command = re.fullmatch(r'(differentiate|derivative of|factor|expand|simplify)\s+(.+?)(?:\s+(?:with respect to|wrt)\s+([a-z]))?', text)
        if command:
            value = parsed(command[2]); symbols = sorted(value.free_symbols, key=str)
            if len(symbols) > 2 or sp.count_ops(value) > 40:
                return None
            if command[1] in {'differentiate', 'derivative of'}:
                variable = sp.Symbol(command[3]) if command[3] else symbols[0] if len(symbols) == 1 else None
                if variable is None:
                    return None
                result = sp.diff(value, variable)
            else:
                if symbols and any(sp.Poly(value, *symbols).degree(x) > 6 for x in symbols):
                    return None
                result = {'factor': sp.factor, 'expand': sp.expand, 'simplify': sp.cancel}[command[1]](value)
            return answer(fmt(result), [f'{command[1].capitalize()}: {fmt(value)}.'])
        source = re.sub(r'^(?:what is|calculate|compute|evaluate|find)\s+', '', text)
        source = re.sub(r'(?<![\w.])(\d{1,3})!', r'factorial(\1)', source)
        source = re.sub(r'^(' + N + r')\s+(?:to the power of|raised to(?: the power of)?)\s+(' + N + r')$', r'(\1)^(\2)', source)
        source = re.sub(r'^(?:the )?square root of\s+(.+)$', r'sqrt(\1)', source)
        source = re.sub(r'^factorial of\s+(\d+)$', r'factorial(\1)', source)
        source = re.sub(r'^([\d.]+)\s+factorial$', r'factorial(\1)', source)
        for phrase, function in [('greatest common divisor', 'gcd'), ('least common multiple', 'lcm'), ('gcd', 'gcd'), ('lcm', 'lcm')]:
            source = re.sub(r'^' + phrase + r'(?: of)?\s+(' + N + r')\s*(?:and|,)\s*(' + N + r')$', function+r'(\1,\2)', source)
        value = parsed(source)
        if value.free_symbols:
            return None
        # Leave the established arithmetic handler's response/follow-up format intact.
        if not re.search(r'[a-z]', source):
            return None
        return answer(f'{source} = {fmt(value)}', ['Evaluate the bounded expression exactly.'])
    except (ValueError, TypeError, SyntaxError, ZeroDivisionError, OverflowError, RecursionError, sp.PolynomialError):
        return None
