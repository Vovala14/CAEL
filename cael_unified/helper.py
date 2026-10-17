"""Authored exact arithmetic helper, with a bounded AST and no eval."""
import ast
from fractions import Fraction
import re

UNITS = {
    'mm': ('length', Fraction(1, 1000)), 'millimeter': ('length', Fraction(1, 1000)),
    'cm': ('length', Fraction(1, 100)), 'centimeter': ('length', Fraction(1, 100)),
    'm': ('length', Fraction(1)), 'meter': ('length', Fraction(1)),
    'km': ('length', Fraction(1000)), 'kilometer': ('length', Fraction(1000)),
    'inch': ('length', Fraction(127, 5000)), 'inches': ('length', Fraction(127, 5000)),
    'ft': ('length', Fraction(381, 1250)), 'foot': ('length', Fraction(381, 1250)),
    'feet': ('length', Fraction(381, 1250)), 'mile': ('length', Fraction(201168, 125)),
    'mg': ('mass', Fraction(1, 1000000)), 'g': ('mass', Fraction(1, 1000)),
    'gram': ('mass', Fraction(1, 1000)), 'kg': ('mass', Fraction(1)), 'kilogram': ('mass', Fraction(1)),
    'second': ('time', Fraction(1)), 'minute': ('time', Fraction(60)),
    'hour': ('time', Fraction(3600)), 'day': ('time', Fraction(86400)),
    'ml': ('volume', Fraction(1, 1000)), 'liter': ('volume', Fraction(1)), 'litre': ('volume', Fraction(1)),
}


def unit_key(word):
    word = word.lower()
    return word if word in UNITS else word[:-1] if word.endswith('s') and word[:-1] in UNITS else None


def calculate(text):
    normalized = text.strip().lower().rstrip(' ?.')
    conversion = re.fullmatch(r'(?:convert\s+)?(-?\d+(?:\.\d+)?)\s+([a-z]+)\s+(?:to|in)\s+([a-z]+)', normalized)
    if conversion and len(normalized) <= 200:
        amount, source, target = conversion.groups()
        first, last = unit_key(source), unit_key(target)
        if first and last and UNITS[first][0] == UNITS[last][0]:
            result = Fraction(amount) * UNITS[first][1] / UNITS[last][1]
            answer = str(result.numerator) if result.denominator == 1 else str(result)
            return dict(route='helper/conversion', response=f'{amount} {source} = {answer} {target}', exact=True)
        return None
    expression = re.sub(r'(?i)^\s*(?:what is|calculate|compute|work out|solve)\s+', '', text).strip().rstrip(' ?=')
    percent = re.fullmatch(r'(?i)(-?\d+(?:\.\d+)?)\s*%\s+of\s+(-?\d+(?:\.\d+)?)', expression)
    change = re.fullmatch(r'(?i)(increase|decrease)\s+(-?\d+(?:\.\d+)?)\s+by\s+(-?\d+(?:\.\d+)?)\s*%', expression)
    if percent:
        expression = f'({percent[1]}/100)*({percent[2]})'
    elif change:
        expression = f'({change[2]})*(1 {"+" if change[1].lower() == "increase" else "-"} ({change[3]}/100))'
    for phrase, symbol in [('divided by','/'), ('multiplied by','*'), ('times','*'), ('plus','+'), ('minus','-')]:
        expression = re.sub(r'(?i)\b' + phrase + r'\b', symbol, expression)
    expression = expression.replace('×', '*').replace('÷', '/').replace('^', '**')
    if not expression or len(expression) > 200 or not re.fullmatch(r'[0-9eE+*/%().\s-]+', expression):
        return None
    try:
        tree = ast.parse(expression, mode='eval')
        if sum(1 for _ in ast.walk(tree)) > 80:
            return None

        def value(node):
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                return Fraction(str(node.value))
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                number = value(node.operand)
                return number if isinstance(node.op, ast.UAdd) else -number
            if isinstance(node, ast.BinOp):
                left, right = value(node.left), value(node.right)
                if max(left.numerator.bit_length(), left.denominator.bit_length(), right.numerator.bit_length(), right.denominator.bit_length()) > 4096:
                    raise ValueError('Arithmetic too large')
                if isinstance(node.op, ast.Add): return left + right
                if isinstance(node.op, ast.Sub): return left - right
                if isinstance(node.op, ast.Mult): return left * right
                if isinstance(node.op, ast.Div): return left / right
                if isinstance(node.op, ast.FloorDiv): return Fraction(left // right)
                if isinstance(node.op, ast.Mod): return left % right
                if isinstance(node.op, ast.Pow) and right.denominator == 1 and abs(right) <= 100:
                    return left ** int(right)
            raise ValueError('Unsupported arithmetic')

        result = value(tree.body)
        if max(result.numerator.bit_length(), result.denominator.bit_length()) > 4096:
            return None
    except (ValueError, SyntaxError, ZeroDivisionError, OverflowError):
        return None
    answer = str(result.numerator) if result.denominator == 1 else str(result)
    return dict(route='helper/arithmetic', response=f'{expression} = {answer}', exact=True)
