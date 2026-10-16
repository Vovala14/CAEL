"""Authored exact arithmetic helper, with a bounded AST and no eval."""
import ast
from fractions import Fraction
import re


def calculate(text):
    expression = re.sub(r'(?i)^\s*(?:what is|calculate|compute|work out|solve)\s+', '', text).strip().rstrip(' ?=')
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
