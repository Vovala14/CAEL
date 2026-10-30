"""Protect names and unsupported constraints before generic code recipes."""
import ast
import re

REQUEST = re.compile(r'(?i)\b(?:write|build|create|make|implement|generate)\b.{0,45}\b(?:python|function|code|script|tool)\b')
NAME = re.compile(r'(?i)\b(?:named|called)\s+`?([A-Za-z_]\w*)`?')


def protected(text):
    return bool(REQUEST.search(text) and NAME.search(text))


def guard(text):
    if not REQUEST.search(text) or '```' in text or len(text) > 1800:
        return None
    # These constraints have no complete contract in the current description
    # composer. A plain recipe must not quietly answer a different task.
    if re.search(r'(?i)\b(?:except|excluding|unless)\b|\bwhile preserving\b', text):
        return dict(route='chat/code-contract-clarify', sources=[],
                    response='I have not resolved that exception or preservation rule, so I will not emit a simpler function that drops it. Please give contrasting input/output examples covering the extra rule.',
                    details='The requested contract contains a modifier outside the supported description grammar. No code was emitted and no successful implementation is claimed.')
    return None


def named_reply(text):
    if not protected(text) or '```' in text:
        return None
    from .contracts import reply
    return reply(text)


def explanation(text):
    match = re.fullmatch(r'(?is)\s*(?:what does|explain)\s+`?([^`\n]{1,150}?)`?\s+(?:mean|do)\s+in\s+python[?.!]*\s*', text)
    if not match:
        return None
    try:
        tree = ast.parse(match[1])
    except SyntaxError:
        return None
    if len(tree.body) != 1:
        return None
    statement = tree.body[0]
    if (not isinstance(statement, ast.Assign) or len(statement.targets) != 1
            or not isinstance(statement.targets[0], ast.Name)
            or not isinstance(statement.value, (ast.Name, ast.Constant))):
        return None
    target, value = statement.targets[0].id, ast.unparse(statement.value)
    response = 'This assigns the value of '+value+' to '+target+'. '
    if isinstance(statement.value, ast.Name):
        response += value+' must already be defined; otherwise Python raises NameError. Both names then refer to the same object. '
    response += 'The = operator assigns a value; == compares two values for equality.'
    return dict(route='chat/code-explanation', response=response, sources=[],
                details='Read from the Python assignment syntax tree; no source execution or inferred values.')
