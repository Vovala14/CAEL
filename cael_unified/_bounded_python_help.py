"""Same bounded execution policy for both CAEL systems; no native generated code."""
import ast


def install():
    from cael_unified import python_help, verify
    from cael_unified.codegen.python_vm import run_cases

    def execute(source, calls):
        cases = []
        for text in calls:
            call = ast.parse(text, mode='eval').body
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name) or any(k.arg is None for k in call.keywords):
                raise ValueError('Not a literal function call')
            cases.append(dict(name=call.func.id, args=[ast.literal_eval(a) for a in call.args],
                              kwargs={k.arg: ast.literal_eval(k.value) for k in call.keywords}))
        result = run_cases(source, cases)
        if result['status'] != 'ok' or any(r['status'] != 'value' for r in result['cases']):
            raise ValueError('Bounded interpreter coverage or execution failure')
        return [r['value'] for r in result['cases']]

    def checked(source, examples):
        try:
            values = execute(source, [call for call, _ in examples])
            return all(repr(value) == expected for value, (_, expected) in zip(values, examples))
        except (ValueError, TypeError, SyntaxError):
            return False

    def composed(text):
        built = python_help.compose(text)
        if not built:
            return None
        code, calls = built
        try:
            values = execute(code, calls)
        except (ValueError, TypeError, SyntaxError):
            return None
        shown = '\n'.join(f'{call}  # {value!r}' for call, value in zip(calls, values))
        return dict(route='chat/code-composed', sources=[],
                    response=f'```python\n{code}```\nExamples (run):\n```python\n{shown}\n```',
                    details='Built from the wording of the request by CAEL\'s Python templates and run on the examples shown. No neural model.')

    python_help.verified = checked
    python_help.composed = composed

    def denied(source):
        raise verify.Unchecked('Legacy native code checker disabled; final grading uses bounded AST VM')

    verify.sandbox_function = denied
    apply = verify.apply
    def unrecorded_apply(text, answer, record=False):
        # Preserve the checker's call contract for orchestrators that explicitly
        # request no recording. Keep the bounded policy's no-record behaviour.
        return apply(text, answer, record=False)
    verify.apply = unrecorded_apply

