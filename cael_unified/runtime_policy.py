"""Install the bounded checker policy used to qualify this release, once per process."""
import ast
import inspect
import threading

_lock = threading.RLock()
_installed = False

def install():
    global _installed
    with _lock:
        if _installed:
            return
        from . import rules
        from .codegen import specs, recurrence
        for module in (specs, recurrence, rules):
            tree = ast.parse(inspect.getsource(module))
            bad = [n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call)
                   and isinstance(n.func, ast.Name) and n.func.id in {'eval', 'exec', 'compile'}]
            if bad:
                raise RuntimeError('Unexpected native generated-code checker in ' + module.__name__)
        from ._bounded_python_help import install as install_checkers
        install_checkers()
        _installed = True
