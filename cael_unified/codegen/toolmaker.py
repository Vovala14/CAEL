"""Construct a compound pure helper when a single-output helper is insufficient.

Output schema comes from examples; each field's update logic is independently
synthesized. The field names never select algorithms or supply answer constants.
The resulting state graphs are compiled into a shared loop and checked by the
bounded Python machine. No new unrestricted executable tool is installed.
"""
import ast
import re

from . import state_search
from .python_vm import run_cases
from .workbench import same


def schema(cases):
    if len(cases)<2 or len(cases)>12:return None
    first=cases[0][1]
    if type(first) is dict and 2<=len(first)<=4 and all(type(k) is str and 0<len(k)<=40 for k in first):
        keys=list(first)
        if all(type(out) is dict and set(out)==set(keys) for _,out in cases):return 'dict',keys
    if type(first) is tuple and 2<=len(first)<=4:
        if all(type(out) is tuple and len(out)==len(first) for _,out in cases):return 'tuple',list(range(len(first)))
    return None


def render(name,kind,keys,programs):
    # The single-field renderer supplies the same public-name policy.
    programs[0].render(name)
    lines=[f'def {name}(numbers):',
           '    if type(numbers) is not list or len(numbers) > 40:',
           "        raise ValueError('Expected a list of at most 40 integers')",
           '    for number in numbers:',
           '        if type(number) is not int or abs(number) > 1000000:',
           "            raise ValueError('Expected bounded integer inputs')",
           '    previous = 0']
    for index,p in enumerate(programs):
        lines += [f'    state_{index} = {p.initial}',f'    history_{index} = []']
    lines.append('    for index, value in enumerate(numbers):')
    for index,p in enumerate(programs):
        expr=re.sub(r'\bstate\b',f'state_{index}',p.update.source())
        lines += [f'        state_{index} = {expr}',f'        if abs(state_{index}) > 1000000000000:',
                  "            raise ValueError('Intermediate integer limit')",f'        history_{index}.append(state_{index})']
    lines.append('        previous = value')
    outputs=[]
    for index,p in enumerate(programs):
        if p.projection=='scan':outputs.append(f'history_{index}')
        elif p.projection=='last':outputs.append(f'state_{index}')
        else:outputs.append(f'({p.projection}(history_{index}) if history_{index} else {p.initial})')
    result=('{'+', '.join(repr(key)+': '+value for key,value in zip(keys,outputs))+'}') if kind=='dict' else '('+', '.join(outputs)+')'
    lines.append('    return '+result)
    return '\n'.join(lines)+'\n'


def build(name,cases,description=''):
    shape=schema(cases)
    if shape is None:return dict(status='outside-domain')
    if any(len(args)!=1 or not state_search.integer_list(args[0]) for args,_ in cases):return dict(status='outside-domain')
    kind,keys=shape;programs=[];stats=[]
    for key in keys:
        field_cases=[(args,out[key]) for args,out in cases]
        result=state_search.synthesize(field_cases,description,seconds=.8,max_programs=18000)
        stats.append(result['stats'])
        if result['status']=='ambiguous':return dict(status='ambiguous',field=key,witness=result['witness'],predictions=result['predictions'],stats=stats)
        if result['status']!='synthesized':return dict(status='not-found',field=key,stats=stats)
        programs.append(result['program'])
    try:code=render(name,kind,keys,programs)
    except state_search.OutsideDomain:return dict(status='invalid-name')
    execution=run_cases(code,[dict(name=name,args=list(args)) for args,_ in cases],steps=80000)
    if execution['status']!='ok' or len(execution['cases'])!=len(cases) or any(row.get('status')!='value' or not same(row['value'],expected) for row,(_,expected) in zip(execution['cases'],cases)):
        return dict(status='verification-failed',stats=stats)
    return dict(status='built',source=code,stats=stats,kind=kind,keys=keys,programs=programs,checks=len(cases))


def reply(name,cases,description,request):
    result=build(name,cases,description)
    if result['status']=='outside-domain':return None
    details=('Non-neural helper construction: infer independent integer-state updates for 2–4 output fields, '
             'compose their expression graphs into one Python loop, and verify the emitted AST in the bounded interpreter. '
             'No completed function lookup, native execution of user code, installation, filesystem or network access. '
             'This does not synthesize arbitrary tools or prove untested inputs.')
    out=lambda response,route:dict(response=response,route='chat/code-tool-'+route,sources=[],details=details)
    if result['status']=='ambiguous':
        return out(f"The examples do not determine field `{result['field']}`. What should `{name}({result['witness']!r})` return for that field? "
                   f"Candidate values are `{result['predictions'][0]!r}` and `{result['predictions'][1]!r}`. Add a contrasting example.",'clarify')
    if result['status']!='built':
        return out('I could not construct and verify this compound helper within the supported integer-state grammar. '
                   'It supports 2–4 independent outputs from one integer list; coupled states and arbitrary libraries remain unsupported. '
                   'No new executable tool was installed.','not-found')
    lines=[f'```python\n{result["source"]}```',
           f"I constructed {len(result['keys'])} independent state updates and combined them into this helper. "
           f"The emitted function matches all {result['checks']} supplied examples in the bounded Python interpreter. "
           'That is evidence for those examples, not a general correctness proof. Domain: at most 40 integers within ±1,000,000, '
           'with bounded intermediate states. No executable tool was installed.']
    apply=re.search(r'(?im)^\s*(?:use|apply|run)(?: it| this helper)? (?:on|for)\s+(.+?)\s*$',request)
    if apply:
        try:
            values=ast.literal_eval(apply[1])
            if state_search.integer_list(values):
                checked=run_cases(result['source'],[dict(name=name,args=[values])],steps=20000)
                if checked['cases'] and checked['cases'][0].get('status')=='value':
                    lines.append(f"For `{values!r}`, the constructed helper returns `{checked['cases'][0]['value']!r}`.")
        except (SyntaxError,ValueError,TypeError,RecursionError):pass
    return out('\n\n'.join(lines),'synthesized')
