"""Chat front end for Python synthesis: parse examples, search, report honestly."""
import ast
from pathlib import Path
import re

from . import explain, specs
from .synth import render, synthesize
from .train import costs, load

MODEL = Path(__file__).resolve().parents[2] / 'models/cael-code-0.3.8/model.json'
REQUEST = re.compile(r'(?i)\b(?:write|create|make|generate|build|give me|code|implement)\b.{0,40}\b(?:python )?(?:function|def|program|code|script)\b|\bpython function\b')
EXAMPLE = re.compile(r'([A-Za-z_]\w*)\s*\((.*?)\)\s*(?:==|->|=>|returns|should return|gives|=)\s*(.+?)\s*$')
DETAILS = ('Written by CAEL\'s non-neural program search: small Python operations are combined until one composition returns '
           'every example correctly. A trained count model (MBPP training split) decides which operations to try first; '
           'no stored solution is copied. Passing your examples does not prove the function is right for every input.')
HELP = ('I can write small Python functions when you give me examples to check against. Describe the function and add '
        'two or three examples, one per line, for example:\n\n'
        'Write a python function that counts vowels.\ncount_vowels("hello") == 2\ncount_vowels("sky") == 0\n'
        'count_vowels("aeiou") == 5')

_model = None


def model():
    global _model
    if _model is None and MODEL.exists():
        _model = load(MODEL)
    return _model


def literal_prefix(text):
    """The longest leading Python literal in text ('2, f(3) == 4' -> 2)."""
    text = text.strip()
    for end in range(len(text), 0, -1):
        if end < len(text) and text[end] not in ' ,;.\n':
            continue
        try:
            # "2," would read as the tuple (2,); a separator after a value is not part of it.
            return ast.literal_eval(text[:end].strip().rstrip(',;').rstrip())
        except (ValueError, SyntaxError, MemoryError, RecursionError):
            continue
    raise ValueError('no literal')


def inline_examples(text):
    """Examples written on one line: 'count(\"a\") == 1, count(\"bb\") == 0'."""
    names = re.findall(r'\b([A-Za-z_]\w*)\s*\([^()]*(?:\([^()]*\)[^()]*)*\)\s*(?:==|->|=>|returns|=)', text)
    if not names:
        return None, []
    name = max(set(names), key=names.count)
    found = []
    for chunk in re.split(r'\b' + re.escape(name) + r'(?=\s*\()', text)[1:]:
        match = re.match(r'\s*\((.*?)\)\s*(?:==|->|=>|returns|should return|gives|=)\s*(.+)', chunk, re.S)
        if not match:
            continue
        try:
            inputs = ast.literal_eval('(' + match[1] + ',)') if match[1].strip() else ()
            found.append((tuple(inputs), literal_prefix(match[2])))
        except (ValueError, SyntaxError):
            continue
    return name, found


def examples(text):
    """(function name, [(inputs, output)]) from lines like f(1, 2) == 3, or the same inline."""
    name, inline = inline_examples(text)
    lines = examples_by_line(text)
    return (name, inline) if len(inline) > len(lines[1]) else lines


def examples_by_line(text):
    found, names = [], []
    for line in re.split(r'[\n;]+', text):
        line = line.strip().strip('`').strip()
        line = re.sub(r'^(?:>>>\s*|assert\s+|e\.g\.\s*|example:?\s*|-\s*)', '', line, flags=re.I)
        match = EXAMPLE.match(line)
        if not match:
            continue
        try:
            inputs = ast.literal_eval('(' + match[2] + ',)') if match[2].strip() else ()
            output = ast.literal_eval(match[3].rstrip('.'))
        except (ValueError, SyntaxError):
            continue
        names.append(match[1])
        found.append((tuple(inputs), output))
    if not found:
        return None, []
    name = max(set(names), key=names.count)
    return name, [ex for ex, n in zip(found, names) if n == name]


HOW_TO = re.compile(r'(?i)\b(?:how (?:do|can|would|should) (?:i|you|we)|how to)\b.*\b(?:python|function|code|list|string|dict(?:ionary)?|number)\b|\bin python\b')


def is_request(text):
    return bool(REQUEST.search(text)) or len(examples(text)[1]) >= 2 or bool(HOW_TO.search(text) and specs.find(text))


def show(value):
    return repr(value)


def from_description(text, out):
    """A request with no examples: if it names an everyday task, search against that task's own test cases."""
    task = specs.find(text)
    if task is None:
        return None
    code, checked = specs.solve(task, synthesize, lambda d: costs(model(), d))
    if code is None:
        return out(f'This looks like `{task["name"]}`, but my program search could not find a function that passes '
                   'its test cases. It needs several steps or nested conditions, which I cannot build yet. If you give '
                   'me examples of a simpler version, I can try that.', 'not-found')
    shown = task['cases'][:3]
    tests = '\n'.join(f'assert {task["name"]}({", ".join(map(show, args))}) == {show(expected)}' for args, expected in shown)
    note = (f'I wrote this by searching over small Python operations until one passed all {checked} of my test cases for '
            f'this task, including held-out ones the search never saw. Some of them:\n\n```python\n{tests}\n```\n'
            'Please test it on your own inputs too.')
    return out(f'```python\n{code}```\n{note}', 'from-description')


EXPLAIN_DETAILS = ('Read from the Python syntax tree (ast) and, for short pure expressions, evaluated with a small set of '
                   'safe built-ins. Concept notes and recipes are short hand-written references.')


def reply(text, seed=0, messages=None):
    from .signature_contract import reply as signature_reply
    signature = signature_reply(text)
    if signature is not None:
        return signature
    from .natural_program import reply as natural_reply
    natural = natural_reply(text,messages)
    if natural is not None:return natural
    from .python_tasks import reply as python_task_reply
    completed=python_task_reply(text,messages)
    if completed is not None:return completed
    from .task_tools import reply as task_tool_reply
    task_tool=task_tool_reply(text,messages=messages)
    if task_tool is not None:return task_tool
    # A counterexample answer can extend the immediately preceding coding
    # request. Never merge unrelated function names or an arbitrary old turn.
    questions=('The examples leave more than one plausible program.',
               'The examples do not determine field ')
    if messages and len(messages) >= 3 and messages[-2].get('role') == 'assistant' and \
            messages[-2].get('content', '').startswith(questions):
        follow_name, follow_cases = examples(text)
        if follow_cases:
            for index in range(len(messages)-3,max(-1,len(messages)-10),-2):
                previous=messages[index]
                if previous.get('role')!='user':break
                old_name,old_cases=examples(previous.get('content',''))
                if old_name!=follow_name or not old_cases:break
                text=previous['content']+'\n'+text
                if index<2 or messages[index-1].get('role')!='assistant' or not messages[index-1].get('content','').startswith(questions):break
    # Keep a pasted repair request when the very next turn supplies tests.
    if messages and len(messages)>=3 and messages[-2].get('role')=='assistant' and \
            messages[-2].get('content','').endswith('No behavioral patch was applied.') and '```' not in text:
        from .workbench import examples as repair_examples
        previous=messages[-3]
        if previous.get('role')=='user' and '```' in previous.get('content','') and len(repair_examples(text))>=2:
            text=previous['content']+'\n'+text
    from .workbench import reply as workbench_reply
    reviewed = workbench_reply(text)
    if reviewed is not None:
        return reviewed
    out = lambda response, route, details=DETAILS: dict(response=response, route='chat/code-' + route, sources=[], details=details)
    # Stateful functions have their own example-guided transition grammar.
    # Handle these before the fixed algorithm/description adapters, which do
    # not preserve stateful modifiers such as "running" and "reset".
    from . import state_search
    state_name, state_cases = examples(text)
    first_example = re.search(r'\b' + re.escape(state_name) + r'\s*\(', text) if state_name else None
    description = text[:first_example.start()] if first_example else text
    if len(state_cases) >= 2 and '```' not in text:
        from .toolmaker import reply as toolmaker_reply
        built = toolmaker_reply(state_name, state_cases, description, text)
        if built is not None:
            return built
    if state_search.interested(description) and is_request(text) and '```' not in text:
        if re.search(r'(?i)\b(?:without|do not|in[- ]place|recursion|recursive|async|numpy|pandas)\b', description):
            return out('I cannot verify those implementation constraints with the stateful synthesizer. '
                       'Specify whether an ordinary integer loop is acceptable.', 'state-clarify')
        if len(state_cases) >= 2:
            answer = state_search.reply(state_name, state_cases, description)
            if answer is not None:
                return answer
        if not state_cases:
            from .state_plan import reply as planned_state_reply
            answer = planned_state_reply(description)
            if answer is not None:
                return answer
        return out('I can synthesize a stateful function from contrasting examples. '
                   'Give two or more calls with expected results, including an empty input or a reset boundary. '
                   'I support integer lists, one changing accumulator, and final or running outputs.',
                   'state-needs-examples', 'The requested stateful behavior has not been inferred. No function was emitted.')
    if len(examples(text)[1]) < 2:
        from .contracts import reply as compose_reply
        composed = compose_reply(text)
        if composed is not None:
            return composed
        if is_request(text) and re.search(r'(?i)\b(?:without using|do not use|in[- ]place)\b', text):
            return out('I cannot verify those extra implementation constraints with this composer. '
                       'Please clarify the allowed operations or whether a standard implementation is acceptable.',
                       'clarify', 'No code was emitted because the requested implementation constraints are unsupported.')
    if len(examples(text)[1]) < 2:
        answer = explain.reply(text, lambda response, route: out(response, route, EXPLAIN_DETAILS))
        if answer is not None:
            return answer
    if not is_request(text):
        return None
    name, cases = examples(text)
    if len(cases) < 2:
        answer = from_description(text, out)
        if answer is not None:
            return answer
        from .. import ltm, rules
        rule = ltm.memory().find_rule(text)
        if rule is not None:
            ltm.memory().used(rule['name'])
            return out(f'```python\n{rule["code"]}```\nThis is a {rules.LEARNED_MARK.format(rule["name"])} from an earlier '
                       f'explicit learning session. It passed {rule["checks"]} checks when I learned it (confidence {ltm.confidence(rule):.0%}).',
                       'learned-rule')
        return out(HELP, 'needs-examples', 'CAEL writes code by searching for a program that fits examples; it does not guess code from a description alone.')
    if len({len(c[0]) for c in cases}) != 1:
        return out('Your examples call the function with different numbers of arguments. Please use the same arguments in every example.', 'needs-examples')
    # The description is the text before the first example, which may share its line.
    first = re.search(r'\b' + re.escape(name) + r'\s*\(', text)
    description = text[:first.start()] if first else text
    expr, params, stats = synthesize([c[0] for c in cases], [c[1] for c in cases], description,
                                     costs(model(), description), seconds=8.0, inner_cost=10)
    if expr is None:
        return out(f'I could not find a function that fits all {len(cases)} examples within my search limits '
                   f'({stats["expressions"]:,} candidate expressions tried). I can only build fairly short one-line functions; '
                   'loops with state, recursion and multi-step algorithms are beyond me for now. Simpler examples may help.', 'not-found')
    code = render(name, params, expr)
    note = (f'It returns the expected result for all {len(cases)} of your examples. I built it by searching over small '
            'Python operations, so please test it on other inputs too.')
    if not stats.get('uses_all_parameters', True):
        note += ' Note: it does not use every argument, so it may only fit your examples by coincidence. More examples would help.'
    # Hypothesis testing (rules.py): re-derive the function with one example hidden and check it predicts that example.
    if len(cases) >= 3:
        from .. import rules
        learned = rules.learn(name, cases, description, lambda d: costs(model(), d))
        if learned and learned['validated']:
            code = learned['code']
            note = (f'It returns the expected result for all {len(cases)} of your examples. I also re-derived it '
                    f'{learned["tried"]} times with one example hidden, and each time it predicted the hidden one correctly.')
            if learned['stored']:
                if learned.get('storage_scope') == 'request':
                    note += ' This inferred rule is limited to the current request; it will not affect an unrelated request.'
                else:
                    note += f' It is available as {rules.LEARNED_MARK.format(name)} within this explicit learning session.'
        elif learned:
            note += (f' When I hid one of your examples and searched again, the result did not predict the hidden example '
                     f'({learned["held_out"]} of {learned["tried"]}), so I will not save it as a rule. More examples would help.')
    return out(f'```python\n{code}```\n{note}', 'synthesized')
