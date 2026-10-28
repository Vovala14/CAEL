"""Frozen preliminary grading; retain raw flags for later full semantic review."""
import ast
import math
import re


def same(actual, expected):
    if type(actual) in (int,float) and type(expected) in (int,float):
        return (type(actual) is int or math.isfinite(actual)) and actual==expected
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return actual.keys()==expected.keys() and all(same(actual[k],v) for k,v in expected.items())
    if type(expected) in (list,tuple):
        return len(actual)==len(expected) and all(same(a,b) for a,b in zip(actual,expected))
    return actual==expected


def extract(reply,name):
    blocks=re.findall(r'```(?:python|py)?\s*\n(.*?)```',reply,re.S|re.I)
    if not blocks and reply.lstrip().startswith(('def ','class ')):
        blocks=[reply.strip()]
    candidates=[]
    for block in blocks:
        try:tree=ast.parse(block)
        except (SyntaxError,RecursionError):continue
        if any(isinstance(n,ast.FunctionDef) and n.name==name for n in tree.body):
            candidates.append((block,tree))
    if len(candidates)!=1:return None,None
    return candidates[0]


def grade(reply,item):
    checks=item['criteria']
    if item.get('contract') is None:
        missing=[p for p in checks['all'] if not re.search(p,reply,re.I)]
        forbidden=[p for p in checks['none'] if re.search(p,reply,re.I)]
        return dict(ok=not missing and not forbidden,status='text_preliminary',missing=missing,forbidden=forbidden)
    contract=item['contract'];source,tree=extract(reply,contract['name'])
    if source is None:return dict(ok=False,status='missing_or_ambiguous_function')
    if any(isinstance(n,(ast.Import,ast.ImportFrom)) for n in ast.walk(tree)):
        return dict(ok=False,status='contract_violation_import',reason='All systems were told built-ins only, no imports')
    if sum(1 for _ in ast.walk(tree))>1800:
        return dict(ok=None,status='grader_ast_budget',reason='Needs disclosed manual evaluation, not automatically incorrect')
    from cael_unified.codegen.python_vm import run_cases
    cases=[dict(name=contract['name'],args=c['args']) for c in contract['cases']]
    result=run_cases(source,cases,steps=160000)
    if result['status'] in ('unsupported','limit','incomplete') or any(r['status'] in ('unsupported','limit') for r in result.get('cases',[])):
        return dict(ok=None,status='vm_ungraded',execution=result,reason='Interpreter coverage/limit; review rather than call it wrong code')
    passed=[]
    for case,actual in zip(contract['cases'],result.get('cases',[])):
        okay=actual['status']=='value' and same(actual.get('value'),case['expected'])
        # Two-sum's contract does not specify index order. Check its actual
        # mathematical condition instead of rejecting a reversed valid pair.
        if 'two-sum' in item['question'].lower() and actual['status']=='value':
            value=actual.get('value');numbers,target=case['args']
            okay=value is None if case['expected'] is None else (
                type(value) in (list,tuple) and len(value)==2 and all(type(i) is int for i in value)
                and value[0]!=value[1] and all(0<=i<len(numbers) for i in value)
                and numbers[value[0]]+numbers[value[1]]==target)
        passed.append(bool(okay))
    return dict(ok=len(passed)==len(cases) and all(passed),status='functional',
                checks=passed,execution=result,source=source)
