"""Read Python the person pastes: say what it does, repair common syntax errors, explain core concepts.

Explanations come from the parsed syntax tree (ast), not from guessing. A pure expression made only of
literals and a short list of safe built-ins is also evaluated (with a size guard) so the reply can show the
actual result. Repairs are small textual fixes tried one at a time until the code parses; each one is named.
Concept notes and standard-library recipes are short hand-written references and are labelled as such.
"""
import ast
import re

CODE_ASK = re.compile(r'(?i)\b(?:what does (?:this|the|my|following)? ?(?:code|snippet|function|line|program|script|expression)?\s*(?:do|return|print|mean)'
                      r'|explain (?:this|the|my|following) (?:code|snippet|function|line|program|script|expression)'
                      r'|what is the (?:output|result) of)\b')
FIX_ASK = re.compile(r'(?i)\b(?:fix|debug|repair|correct)\b.{0,30}\b(?:code|function|snippet|syntax|error|this|it|script)\b'
                     r'|\bwhat(?:\'s| is) wrong with\b|\bwhy (?:does|doesn\'t|won\'t|is) (?:this|my) (?:code|function)')
CONCEPT_ASK = re.compile(r'(?i)^\s*(?:(?:can you |please )?explain|what (?:is|are)|how do(?:es)?|how to use|tell me about)\s+(?:an? |the )?'
                         r'(?:python\s+)?(.+?)(?:\s+in python)?\s*\??\s*$')

SAFE_CALLS = {'range', 'len', 'sum', 'min', 'max', 'sorted', 'reversed', 'list', 'tuple', 'set', 'dict', 'str', 'int',
              'float', 'abs', 'round', 'enumerate', 'zip', 'map', 'filter', 'any', 'all', 'bool', 'ord', 'chr'}
SAFE_METHODS = {'upper', 'lower', 'title', 'strip', 'split', 'join', 'replace', 'count', 'index', 'find', 'startswith',
                'endswith', 'items', 'keys', 'values', 'get', 'capitalize'}

CALL_WORDS = dict(range='a range of whole numbers', len='the length', sum='the sum', min='the smallest item',
                  max='the largest item', sorted='a sorted copy', reversed='the items in reverse order',
                  enumerate='each item with its position', zip='items paired up from several sequences',
                  print='printed output', input='a line typed by the user', open='an open file', map='a function applied to each item',
                  filter='only the items a test accepts', any='whether any item is true', all='whether every item is true')

CONCEPTS = {
    'list comprehension': ('A **list comprehension** builds a new list from an existing sequence in one expression:\n\n'
                           '```python\nsquares = [x * x for x in range(5)]          # [0, 1, 4, 9, 16]\n'
                           'evens = [x for x in range(10) if x % 2 == 0]  # [0, 2, 4, 6, 8]\n```\n'
                           'Read it as "x * x, for each x in range(5)". The optional `if` keeps only items that pass the test. '
                           'Use `{...}` for a set or `{k: v for ...}` for a dictionary.'),
    'dictionary': ('A **dictionary** (`dict`) maps keys to values:\n\n```python\nages = {"ann": 31, "bo": 27}\n'
                   'ages["cy"] = 40          # add or change\nages.get("dan", 0)       # 0 when the key is missing\n'
                   'for name, age in ages.items():\n    print(name, age)\n```\nKeys must be hashable (strings, numbers, tuples). '
                   'Since Python 3.7 a dict keeps insertion order.'),
    'lambda': ('A **lambda** is a small unnamed function written as one expression:\n\n```python\n'
               'double = lambda x: x * 2\nsorted(words, key=lambda w: len(w))   # sort by length\n```\n'
               'It can only hold one expression (no statements). For anything longer, use `def`.'),
    'decorator': ('A **decorator** wraps a function to add behaviour without changing its code:\n\n```python\n'
                  'def shout(func):\n    def wrapper(*args, **kwargs):\n        return func(*args, **kwargs).upper()\n    return wrapper\n\n'
                  '@shout\ndef greet(name):\n    return f"hi {name}"\n\ngreet("ann")   # "HI ANN"\n```\n'
                  '`@shout` above `def greet` means `greet = shout(greet)`.'),
    'generator': ('A **generator** produces values one at a time, only when asked, using `yield`:\n\n```python\n'
                  'def count_up(n):\n    i = 0\n    while i < n:\n        yield i\n        i += 1\n\n'
                  'for x in count_up(3):\n    print(x)        # 0, 1, 2\n```\n'
                  'It saves memory because the whole sequence never exists at once. `(x * x for x in data)` is a generator expression.'),
    'class': ('A **class** defines a new kind of object with its own data and methods:\n\n```python\n'
              'class Dog:\n    def __init__(self, name):\n        self.name = name\n\n    def speak(self):\n'
              '        return f"{self.name} says woof"\n\nDog("Rex").speak()\n```\n'
              '`__init__` runs when an object is created; `self` is the object itself.'),
    'for loop': ('A **for loop** runs a block once for each item of a sequence:\n\n```python\n'
                 'for name in ["ann", "bo"]:\n    print(name)\n\nfor i in range(3):      # 0, 1, 2\n    print(i)\n```\n'
                 '`break` leaves the loop early and `continue` skips to the next item. Use `enumerate()` for positions too.'),
    'while loop': ('A **while loop** repeats while a condition stays true:\n\n```python\nn = 3\nwhile n > 0:\n    print(n)\n'
                   '    n -= 1\n```\nMake sure something in the loop changes the condition, or it never stops.'),
    'f-string': ('An **f-string** puts values straight into text:\n\n```python\nname, score = "ann", 9.5\n'
                 'f"{name} scored {score:.1f}"   # "ann scored 9.5"\n```\nAnything inside `{}` is evaluated; '
                 'after `:` comes a format such as `.2f` (2 decimals) or `>8` (right-align in 8 characters).'),
    'try except': ('**try / except** handles errors instead of crashing:\n\n```python\ntry:\n    value = int(text)\n'
                   'except ValueError:\n    value = 0\nfinally:\n    print("done")   # always runs\n```\n'
                   'Catch the specific error you expect, not a bare `except:`.'),
    'args kwargs': ('`*args` and `**kwargs` let a function take any number of arguments:\n\n```python\n'
                    'def show(*args, **kwargs):\n    print(args)    # tuple of positional arguments\n'
                    '    print(kwargs)  # dict of named arguments\n\nshow(1, 2, colour="red")\n```'),
    'with statement': ('The **with** statement sets something up and always cleans it up, even after an error:\n\n```python\n'
                       'with open("notes.txt") as f:\n    text = f.read()\n# the file is closed here\n```'),
    'slicing': ('**Slicing** takes part of a sequence with `[start:stop:step]` (stop is not included):\n\n```python\n'
                's = "python"\ns[1:4]    # "yth"\ns[:2]     # "py"\ns[-2:]    # "on"\ns[::-1]   # "nohtyp" (reversed)\n```'),
    'tuple': ('A **tuple** is an ordered collection that cannot be changed after it is made:\n\n```python\n'
              'point = (3, 4)\nx, y = point      # unpacking\n```\nUse a tuple for fixed groups of values, a list when items change.'),
    'set': ('A **set** holds unique items with no order:\n\n```python\nseen = {1, 2, 2, 3}   # {1, 2, 3}\n'
            'seen.add(4)\n3 in seen             # fast membership test\na | b, a & b, a - b   # union, intersection, difference\n```'),
}
CONCEPT_NAMES = {
    'list comprehension': r'list comprehensions?|comprehensions?', 'dictionary': r'dict(?:ionary|ionaries|s)?',
    'lambda': r'lambdas?(?: functions?)?', 'decorator': r'decorators?', 'generator': r'generators?|yield',
    'class': r'class(?:es)?|objects? oriented|oop', 'for loop': r'for loops?|loops?', 'while loop': r'while loops?',
    'f-string': r'f-?strings?|string formatting', 'try except': r'try(?: ?/? ?except)?|exceptions?|error handling',
    'args kwargs': r'\*?args|\*?\*?kwargs|\*args and \*\*kwargs', 'with statement': r'with(?: statements?)?|context managers?',
    'slicing': r'slic(?:e|es|ing)', 'tuple': r'tuples?', 'set': r'sets?',
}

RECIPES = [
    (r'\bcsv\b', 'Read a CSV file and print its rows', 'import csv\n\nwith open("data.csv", newline="") as f:\n'
     '    for row in csv.reader(f):\n        print(row)\n'),
    (r'\bjson\b', 'Read and write JSON', 'import json\n\nwith open("data.json") as f:\n    data = json.load(f)\n\n'
     'with open("out.json", "w") as f:\n    json.dump(data, f, indent=2)\n'),
    (r'\b(?:download\w*|fetch\w*|get|request\w*)\b.*\b(?:web ?page|url|website|html|page)\b', 'Download a web page',
     'from urllib.request import urlopen\n\nwith urlopen("https://example.com") as response:\n'
     '    html = response.read().decode("utf-8")\nprint(html[:200])\n'),
    (r'\b(?:read|open)\b.*\b(?:text )?file\b', 'Read a text file line by line',
     'with open("notes.txt", encoding="utf-8") as f:\n    for line in f:\n        print(line.rstrip())\n'),
    (r'\bwrite\b.*\b(?:to )?(?:a )?(?:text )?file\b', 'Write text to a file',
     'with open("notes.txt", "w", encoding="utf-8") as f:\n    f.write("first line\\n")\n'),
    (r'\b(?:current|today\'?s?)\b.*\b(?:date|time)\b', 'Get the current date and time',
     'from datetime import datetime\n\nnow = datetime.now()\nprint(now.strftime("%Y-%m-%d %H:%M"))\n'),
    (r'\brandom (?:number|integer|choice)\b', 'Pick a random number or item',
     'import random\n\nrandom.randint(1, 6)          # 1..6 inclusive\nrandom.choice(["a", "b", "c"])\n'),
    (r'\blist (?:the )?files\b|\bfiles in (?:a )?(?:folder|directory)\b', 'List the files in a folder',
     'from pathlib import Path\n\nfor path in Path(".").iterdir():\n    print(path.name)\n'),
]
RECIPE_NOTE = ('This is a standard-library recipe from my reference notes, not a program found by search: '
               'file and network code cannot be checked against examples.')


def code_in(text):
    """The Python part of a message: a fenced block, text after a colon, or the lines that parse."""
    fenced = re.search(r'```(?:python|py)?\s*\n?(.*?)```', text, re.S)
    if fenced:
        return fenced[1].strip('\n')
    inline = re.search(r'`([^`\n]+)`', text)
    if inline:
        return inline[1]
    lines = text.split('\n')
    if len(lines) > 1:
        body = '\n'.join(lines[1:]).strip('\n')
        head = lines[0].split(':', 1)
        return (head[1].strip() + '\n' + body).strip('\n') if len(head) == 2 and head[1].strip() else body
    match = re.search(r'(?i)\b(?:output|result|value) of\s+(.+?)\s*\??$', text) or re.search(r'[?:]\s*(.+)$', text)
    return match[1].strip() if match else None


def safe_to_run(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Lambda, ast.Await, ast.Yield, ast.YieldFrom, ast.Starred,
                             ast.FunctionDef, ast.ClassDef, ast.While, ast.Global, ast.Nonlocal, ast.Delete)):
            return False
        if isinstance(node, ast.Attribute) and (node.attr.startswith('_') or node.attr not in SAFE_METHODS):
            return False
        if isinstance(node, ast.Name) and node.id.startswith('_'):
            return False
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id not in SAFE_CALLS:
            return False
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            return False
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and abs(node.value) > 10 ** 6:
            return False
    return True


def evaluate(source):
    """The value of a short pure expression, or None when it is not safe or not small."""
    try:
        tree = ast.parse(source, mode='eval')
    except SyntaxError:
        return None
    if not safe_to_run(tree):
        return None
    allowed = {name: __builtins__[name] if isinstance(__builtins__, dict) else getattr(__builtins__, name) for name in SAFE_CALLS}
    try:
        value = eval(compile(tree, '<snippet>', 'eval'), {'__builtins__': allowed})
    except Exception as error:
        return ('error', f'{type(error).__name__}: {error}')
    if isinstance(value, (map, filter, zip, enumerate, reversed, range)):
        value = list(value)
    text = repr(value)
    return ('value', text if len(text) <= 300 else text[:300] + ' ...')


def name_of(node):
    try:
        return ast.unparse(node)
    except Exception:
        return 'a value'


def describe(node, depth=0):
    """A short plain-language sentence for one syntax node."""
    if isinstance(node, ast.Expr):
        return describe(node.value, depth)
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
        gen = node.generators[0]
        kind = {ast.ListComp: 'a list', ast.SetComp: 'a set', ast.GeneratorExp: 'a generator', ast.DictComp: 'a dictionary'}[type(node)]
        made = f'`{name_of(node.key)}: {name_of(node.value)}`' if isinstance(node, ast.DictComp) else f'`{name_of(node.elt)}`'
        conds = ''.join(f', keeping only those where `{name_of(c)}`' for c in gen.ifs)
        return f'Builds {kind} of {made} for each `{name_of(gen.target)}` in `{name_of(gen.iter)}`{conds}.'
    if isinstance(node, ast.FunctionDef):
        args = ', '.join(a.arg for a in node.args.args) or 'no arguments'
        inner = [describe(n, depth + 1) for n in node.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
        returns = [n for n in ast.walk(node) if isinstance(n, ast.Return) and n.value is not None]
        out = f'Defines a function `{node.name}` that takes {args}.'
        if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == node.name for n in ast.walk(node)):
            out += ' It calls itself (recursion).'
        if returns and len(node.body) == 1:
            out += f' It returns `{name_of(returns[0].value)}`.'
        elif inner:
            out += ' Inside it: ' + ' '.join(i for i in inner if i)
        return out
    if isinstance(node, ast.ClassDef):
        methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
        return f'Defines a class `{node.name}`' + (f' with methods {", ".join(f"`{m}`" for m in methods)}.' if methods else '.')
    if isinstance(node, ast.For):
        body = ' '.join(describe(n, depth + 1) for n in node.body[:3])
        return f'Loops over `{name_of(node.iter)}`, calling each item `{name_of(node.target)}`. Each time: {body}'
    if isinstance(node, ast.While):
        return f'Repeats while `{name_of(node.test)}` is true: ' + ' '.join(describe(n, depth + 1) for n in node.body[:3])
    if isinstance(node, ast.If):
        out = f'If `{name_of(node.test)}`: ' + ' '.join(describe(n, depth + 1) for n in node.body[:2])
        if node.orelse:
            out += ' Otherwise: ' + ' '.join(describe(n, depth + 1) for n in node.orelse[:2])
        return out
    if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
        target = name_of(node.targets[0] if isinstance(node, ast.Assign) else node.target)
        if isinstance(node, ast.AugAssign):
            return f'Updates `{target}` with `{name_of(node)}`.'
        return f'Sets `{target}` to `{name_of(node.value)}`.'
    if isinstance(node, ast.Return):
        return f'Returns `{name_of(node.value)}`.' if node.value is not None else 'Returns nothing.'
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return f'Imports {", ".join(a.name for a in node.names)}.'
    if isinstance(node, ast.Call):
        func = name_of(node.func)
        if func == 'print':
            return f'Prints `{", ".join(name_of(a) for a in node.args)}`.'
        word = CALL_WORDS.get(func)
        return f'Calls `{func}`' + (f', which gives {word}.' if word else '.')
    if isinstance(node, ast.Try):
        return 'Tries a block and handles errors of type ' + ', '.join(f'`{name_of(h.type)}`' if h.type else 'any' for h in node.handlers) + '.'
    if isinstance(node, ast.With):
        return f'Opens `{name_of(node.items[0].context_expr)}` and closes it again after the block.'
    if isinstance(node, ast.Lambda):
        return f'Makes a small unnamed function of `{", ".join(a.arg for a in node.args.args)}` that returns `{name_of(node.body)}`.'
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
        s = node.slice
        if s.step is not None and name_of(s.step) == '-1' and s.lower is None and s.upper is None:
            return f'Gives `{name_of(node.value)}` reversed.'
        return f'Takes a slice of `{name_of(node.value)}`.'
    if isinstance(node, ast.Compare):
        return f'Checks whether `{name_of(node)}` (gives True or False).'
    return f'Computes `{name_of(node)}`.'


def explain(source):
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        fixed, notes = repair(source)
        if fixed is None:
            return f'That code does not parse: {error.msg} on line {error.lineno}. I could not repair it automatically.'
        return ('That code has a syntax error, so first a fix:\n\n' + fix_reply(source, fixed, notes) + '\n\n' + explain(fixed))
    lines = [describe(node) for node in tree.body[:8]]
    out = '\n'.join(f'- {line}' for line in lines if line)
    if len(tree.body) == 1 and isinstance(tree.body[0], ast.Expr):
        result = evaluate(source.strip())
        if result and result[0] == 'value':
            out += f'\n\nResult: `{result[1]}`'
        elif result:
            out += f'\n\nRunning it raises `{result[1]}`.'
    return out


BLOCK_START = re.compile(r'^(\s*)(def |class |if |elif |else|for |while |try|except|finally|with )(.*)$')


def repair(source):
    """Fix common syntax errors one at a time until the code parses. Returns (fixed source, notes) or (None, notes)."""
    notes = []
    code = source.replace('\t', '    ')
    for _ in range(8):
        try:
            ast.parse(code)
            return code, notes
        except SyntaxError as error:
            lineno = (error.lineno or 1) - 1
            lines = code.split('\n')
            lineno = min(lineno, len(lines) - 1)
            line = lines[lineno]
            changed = None
            # def f(a, b) return a + b  ->  def f(a, b):\n    return a + b
            one = re.match(r'^(\s*)((?:def|if|elif|for|while|with|class)\b.*?\))\s+(return|print|pass|break|continue|yield)\b(.*)$', line) \
                or re.match(r'^(\s*)((?:if|elif|while)\b.*?|else|try|finally)\s+(return|print|pass|break|continue)\b(.*)$', line)
            block = BLOCK_START.match(line)
            if one and not one[2].rstrip().endswith(':'):
                lines[lineno:lineno + 1] = [f'{one[1]}{one[2]}:', f'{one[1]}    {one[3]}{one[4]}']
                changed = f'added the missing `:` after `{one[2].strip()}` and put the body on its own line'
            elif block and not line.rstrip().endswith(':') and not re.search(r':\s*\S', block[3].split('#')[0][-40:] if block[3] else ''):
                lines[lineno] = line.rstrip() + ':'
                changed = f'added the missing `:` at the end of line {lineno + 1}'
            elif re.match(r'^\s*print\s+[^(=\s]', line):
                lines[lineno] = re.sub(r'^(\s*)print\s+(.*?)\s*$', r'\1print(\2)', line)
                changed = f'`print` is a function in Python 3, so it needs brackets (line {lineno + 1})'
            elif re.search(r'^\s*(?:if|elif|while)\b[^=!<>]*[^=!<>]=[^=]', line):
                lines[lineno] = re.sub(r'(?<=[^=!<>])=(?=[^=])', '==', line, count=1)
                changed = f'used `==` to compare instead of `=` (line {lineno + 1})'
            elif 'expected an indented block' in error.msg and lineno < len(lines):
                prev = lines[lineno - 1] if lineno > 0 else ''
                indent = len(prev) - len(prev.lstrip()) + 4
                lines[lineno] = ' ' * indent + line.lstrip()
                changed = f'indented line {lineno + 1} under the line before it'
            elif 'unindent' in error.msg or 'unexpected indent' in error.msg:
                lines[lineno] = line.lstrip() if lineno == 0 else ' ' * (len(lines[lineno - 1]) - len(lines[lineno - 1].lstrip())) + line.lstrip()
                changed = f'fixed the indentation of line {lineno + 1}'
            else:
                opened = sum(code.count(c) for c in '([{') - sum(code.count(c) for c in ')]}')
                quotes = [q for q in ('"', "'") if line.count(q) % 2]
                if quotes:
                    lines[lineno] = line.rstrip() + quotes[0]
                    changed = f'closed the string on line {lineno + 1}'
                elif opened > 0:
                    stack = []
                    for c in code:
                        if c in '([{':
                            stack.append(c)
                        elif c in ')]}' and stack:
                            stack.pop()
                    closing = ''.join({'(': ')', '[': ']', '{': '}'}[c] for c in reversed(stack))
                    target = max(i for i, l in enumerate(lines) if l.strip()) if lineno >= len(lines) - 1 else lineno
                    lines[target] = lines[target].rstrip() + closing
                    changed = f'closed the open bracket with `{closing}` on line {target + 1}'
            if changed is None:
                return None, notes
            notes.append(changed)
            code = '\n'.join(lines)
    return None, notes


def fix_reply(source, fixed, notes):
    listed = '\n'.join(f'- {n[0].upper() + n[1:]}.' for n in notes)
    return f'```python\n{fixed.strip()}\n```\nWhat I changed:\n{listed}'


def concept(text):
    match = CONCEPT_ASK.match(text.strip())
    if not match:
        return None
    subject = match[1].lower().strip(' ?.')
    subject = re.sub(r'^(?:python\s+)|\s+(?:in|for) python$|\s+work(?:s)?$', '', subject)
    for key, pattern in CONCEPT_NAMES.items():
        if re.fullmatch(rf'(?:a |an |the )?(?:python )?(?:{pattern})(?: in python)?(?: work)?', subject):
            return key
    return None


def recipe(text):
    lower = text.lower()
    for pattern, title, code in RECIPES:
        if re.search(pattern, lower):
            return title, code
    return None


def reply(text, out):
    """A reply for code pasted to explain or fix, a Python concept, or a standard file/web task; else None."""
    pythonish = re.search(r'(?i)\bpython\b|```|\bdef \w+\(|\bcode\b|\bscript\b|\bfunction\b', text)
    if FIX_ASK.search(text):
        source = code_in(text)
        if source:
            try:
                ast.parse(source)
                return out('That code parses fine, so it has no syntax error. Here is what it does:\n\n' + explain(source)
                           + '\n\nIf it gives a wrong result, tell me the input, what you expected and what you got.', 'explained')
            except SyntaxError:
                fixed, notes = repair(source)
                if fixed is None:
                    return out('I could not repair that automatically. Python reports: '
                               f'{syntax_error(source)}. Check that line for a missing `:`, bracket or quote.', 'not-fixed')
                return out(fix_reply(source, fixed, notes), 'fixed')
    if CODE_ASK.search(text):
        source = code_in(text)
        if source:
            return out(explain(source), 'explained')
    name = concept(text)
    if name and (pythonish or name in ('list comprehension', 'lambda', 'decorator', 'generator', 'f-string', 'args kwargs', 'slicing')):
        return out(CONCEPTS[name] + '\n\n(From my Python reference notes.)', 'concept')
    if pythonish and re.search(r'(?i)\b(?:write|how (?:do|can) i|how to|code|script|program)\b', text):
        found = recipe(text)
        if found:
            return out(f'**{found[0]}:**\n\n```python\n{found[1]}```\n{RECIPE_NOTE}', 'recipe')
    return None


def syntax_error(source):
    try:
        ast.parse(source)
        return 'no error'
    except SyntaxError as error:
        return f'{error.msg} (line {error.lineno})'
