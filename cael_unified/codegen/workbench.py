"""Review and test-guided minimal repairs of pasted Python, without exec/eval."""
import ast
from dataclasses import dataclass
import difflib
import io
import itertools
import re
import time
import tokenize

from .code_review import analyze
from .python_vm import BUILTINS, run_cases


ASK=re.compile(r'(?i)\b(?:review|audit|inspect|debug|repair|fix|correct|find (?:the )?(?:bug|error))\b')


def examples(text):
    """Literal call/result assertions outside source blocks; keywords supported."""
    outside=re.sub(r'```.*?```','',text,flags=re.S);cases=[]
    for line in outside.splitlines():
        line=re.sub(r'^\s*(?:assert\s+|[-*]\s*)','',line).strip()
        if len(line)>2500:continue
        depth=0;split=None
        try:
            for token in tokenize.generate_tokens(io.StringIO(line).readline):
                if token.type==tokenize.OP:
                    if token.string in '([{':depth+=1
                    elif token.string in ')]}':depth-=1
                    elif depth==0 and token.string in {'==','->'}:split=token.start[1],token.end[1];break
            if split is None:continue
            call=ast.parse(line[:split[0]].strip(),mode='eval').body
            if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Name):continue
            args=[ast.literal_eval(n) for n in call.args]
            kwargs={k.arg:ast.literal_eval(k.value) for k in call.keywords if k.arg is not None}
            if len(kwargs)!=len(call.keywords):continue
            expected=ast.literal_eval(line[split[1]:].strip())
            cases.append(dict(name=call.func.id,args=args,kwargs=kwargs,expected=expected))
        except (SyntaxError,ValueError,TypeError,tokenize.TokenError,RecursionError):continue
    return cases[:16]


def same(a,b):
    if type(a) is bool or type(b) is bool:return type(a) is type(b) and a==b
    if type(a) in (list,tuple) or type(b) in (list,tuple):
        return type(a) is type(b) and len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
    if type(a) is dict and type(b) is dict:
        return a.keys()==b.keys() and all(same(a[k],b[k]) for k in a)
    return a==b


def check(source,cases):
    result=run_cases(source,cases)
    passed=[]
    for i,case in enumerate(cases):
        got=result.get('cases',[])[i] if i<len(result.get('cases',[])) else {}
        passed.append(got.get('status')=='value' and same(got['value'],case['expected']))
    supported=result.get('status')=='ok' and all(c.get('status') in {'value','error'} for c in result.get('cases',[]))
    return dict(passed=passed,all_passed=all(passed) and bool(cases),supported=supported,execution=result)


@dataclass(frozen=True)
class Edit:
    start:int
    end:int
    replacement:str


@dataclass(frozen=True)
class Change:
    edits:tuple
    reason:str
    line:int


def mutations(source):
    """Source-derived local edits; no expected answer literals or full solutions."""
    tree=ast.parse(source);lines=source.splitlines(keepends=True)
    offsets=[0]
    for line in lines:offsets.append(offsets[-1]+len(line))
    def position(line,byte_col):
        return offsets[line-1]+len(lines[line-1].encode('utf-8')[:byte_col].decode('utf-8'))
    def span(node):return position(node.lineno,node.col_offset),position(node.end_lineno,node.end_col_offset)
    def replacement(node,text,reason):
        start,end=span(node);return Change((Edit(start,end,text),),reason,node.lineno)
    tokens=list(tokenize.generate_tokens(io.StringIO(source).readline))
    def operator_edit(left,right,old,new,reason,line):
        lo=span(left)[1];hi=span(right)[0]
        for token in tokens:
            start=offsets[token.start[0]-1]+token.start[1];end=offsets[token.end[0]-1]+token.end[1]
            if lo<=start<end<=hi and token.string==old:
                return Change((Edit(start,end,new),),reason,line)
        return None
    known=set(BUILTINS)
    known.update(n.id for n in ast.walk(tree) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store))
    known.update(a.arg for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.Lambda)) for a in [*n.args.posonlyargs,*n.args.args,*n.args.kwonlyargs])
    known.update(n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.ClassDef)))
    attributes={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute) and isinstance(n.ctx,ast.Store)}
    attributes|={n.name for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)}
    result=[]
    for n in ast.walk(tree):
        if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load) and n.id not in known:
            for candidate in difflib.get_close_matches(n.id,sorted(known),n=3,cutoff=.6):
                if abs(len(candidate)-len(n.id))<=2:
                    result.append(replacement(n,candidate,f'Resolve `{n.id}` to the existing binding `{candidate}`.'))
        if isinstance(n,ast.Attribute) and isinstance(n.ctx,ast.Load) and n.attr not in attributes:
            for candidate in difflib.get_close_matches(n.attr,sorted(attributes),n=3,cutoff=.7):
                if abs(len(candidate)-len(n.attr))<=2:
                    end=span(n)[1]
                    result.append(Change((Edit(end-len(n.attr),end,candidate),),
                                         f'Try the existing attribute `{candidate}` for `{n.attr}`; examples must confirm it.',n.lineno))
        if isinstance(n,ast.BinOp):
            ops={ast.Add:('+',['-','*']),ast.Sub:('-',['+','*']),ast.Mult:('*',['+','-']),
                 ast.Div:('/',['//','*']),ast.FloorDiv:('//',['/','*']),ast.Mod:('%',['//'])}
            if type(n.op) in ops:
                old,alts=ops[type(n.op)]
                for new in alts:
                    edit=operator_edit(n.left,n.right,old,new,f'Change arithmetic operator `{old}` to `{new}`.',n.lineno)
                    if edit:result.append(edit)
        if isinstance(n,ast.AugAssign):
            ops={ast.Add:('+=',['-=','*=']),ast.Sub:('-=',['+=','*=']),ast.Mult:('*=',['+=','-=']),
                 ast.Div:('/=',['//=','*=']),ast.FloorDiv:('//=',['/=','*='])}
            if type(n.op) in ops:
                old,alts=ops[type(n.op)]
                for new in alts:
                    edit=operator_edit(n.target,n.value,old,new,f'Change state update `{old}` to `{new}`.',n.lineno)
                    if edit:result.append(edit)
        if isinstance(n,ast.Compare) and len(n.ops)==1:
            ops={ast.Lt:('<',['<=','>']),ast.LtE:('<=',['<','>=']),ast.Gt:('>',['>=','<']),ast.GtE:('>=',['>','<=']),
                 ast.Eq:('==',['!=']),ast.NotEq:('!=',['==']),ast.Is:('is',['==']),ast.IsNot:('is not',['!='])}
            if type(n.ops[0]) in ops:
                old,alts=ops[type(n.ops[0])]
                for new in alts:
                    edit=operator_edit(n.left,n.comparators[0],old,new,f'Change comparison `{old}` to `{new}`.',n.lineno)
                    if edit:result.append(edit)
        if isinstance(n,ast.BoolOp) and len(n.values)==2:
            old='and' if isinstance(n.op,ast.And) else 'or';new='or' if old=='and' else 'and'
            edit=operator_edit(n.values[0],n.values[1],old,new,f'Change boolean connector `{old}` to `{new}`.',n.lineno)
            if edit:result.append(edit)
        if isinstance(n,ast.Constant) and type(n.value) is int and abs(n.value)<=100:
            for value in sorted({0,1,n.value-1,n.value+1}-{n.value}):
                result.append(replacement(n,str(value),'Adjust a source-derived integer boundary or initial value.'))
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='range' and 1<=len(n.args)<=3:
            upper=n.args[0] if len(n.args)==1 else n.args[1]
            text=ast.get_source_segment(source,upper)
            for sign in ['+','-']:
                result.append(replacement(upper,f'({text} {sign} 1)','Adjust the exclusive range stop by one.'))
        if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call):
            start,_=span(n)
            result.append(Change((Edit(start,start,'return '),),'Return the call result instead of discarding it.',n.lineno))
        if isinstance(n,(ast.For,ast.While)):
            ret=n.body[-1] if n.body and isinstance(n.body[-1],ast.Return) else None
            if ret is not None and ret.lineno>n.lineno:
                prefix=lines[ret.lineno-1][:len(lines[ret.lineno-1])-len(lines[ret.lineno-1].lstrip())]
                parent_prefix=lines[n.lineno-1][:len(lines[n.lineno-1])-len(lines[n.lineno-1].lstrip())]
                if ret.lineno==ret.end_lineno:
                    result.append(Change((Edit(offsets[ret.lineno-1],offsets[ret.lineno-1]+len(prefix),parent_prefix),),
                                         'Move the unconditional return after the loop so later items are processed.',ret.lineno))
            for child in n.body:
                if isinstance(child,ast.Assign) and len(child.targets)==1 and isinstance(child.targets[0],ast.Name):
                    # Preserve only source-derived assignments; tests decide
                    # whether accumulation rather than replacement is intended.
                    target=child.targets[0];lo=span(target)[1];hi=span(child.value)[0]
                    for token in tokens:
                        start=offsets[token.start[0]-1]+token.start[1]
                        if lo<=start<hi and token.string=='=':
                            for op in ['+=','*=','-=']:
                                result.append(Change((Edit(start,start+1,op),),f'Update `{target.id}` with `{op}` rather than replacing it.',child.lineno))
        if isinstance(n,ast.FunctionDef):
            params=[*n.args.posonlyargs,*n.args.args]
            for param,default in zip(params[-len(n.args.defaults):] if n.args.defaults else [],n.args.defaults):
                if isinstance(default,(ast.List,ast.Dict,ast.Set)) and n.body[0].lineno>n.lineno:
                    first=n.body[1] if isinstance(n.body[0],ast.Expr) and isinstance(n.body[0].value,ast.Constant) and isinstance(n.body[0].value.value,str) and len(n.body)>1 else n.body[0]
                    prefix=lines[first.lineno-1][:len(lines[first.lineno-1])-len(lines[first.lineno-1].lstrip())]
                    literal=ast.get_source_segment(source,default)
                    guard=prefix+f'if {param.arg} is None:\n'+prefix+'    '+f'{param.arg} = {literal}\n'
                    start,end=span(default)
                    result.append(Change((Edit(start,end,'None'),Edit(offsets[first.lineno-1],offsets[first.lineno-1],guard)),
                                         f'Create a fresh `{param.arg}` default for each call.',default.lineno))
    # Deduplicate; stable order prioritizes binding/control-flow changes.
    unique={change.edits:change for change in result}
    return sorted(unique.values(),key=lambda c:(0 if 'binding' in c.reason or 'return after' in c.reason else 1,c.line,c.reason))[:180]


def apply(source,changes):
    edits=sorted((e for change in changes for e in change.edits),key=lambda e:(e.start,e.end))
    if any(a.end>b.start or a.start==b.start for a,b in zip(edits,edits[1:])):return None
    for edit in reversed(edits):source=source[:edit.start]+edit.replacement+source[edit.end:]
    try:compile(source,'<candidate-syntax-only>','exec')
    except (SyntaxError,IndentationError):return None
    return source


def repair(source,cases,seconds=3.0,max_candidates=350):
    started=time.monotonic();before=check(source,cases);stats=dict(tried=0,budget_exhausted=False)
    out=lambda status,**kw:dict(status=status,before=before,stats={**stats,'seconds':time.monotonic()-started},**kw)
    if not before['supported']:return out('unsupported')
    if before['all_passed']:return out('already-passes')
    if len(cases)<2:return out('needs-tests')
    changes=mutations(source);single=[];seen={source}
    def attempt(group):
        candidate=apply(source,group)
        if candidate is None or candidate in seen:return None,None
        seen.add(candidate);stats['tried']+=1
        result=check(candidate,cases)
        return candidate,result
    for change in changes:
        if stats['tried']>=max_candidates or time.monotonic()-started>seconds:
            stats['budget_exhausted']=True;return out('not-found')
        candidate,result=attempt([change])
        if result is None:continue
        if result['supported'] and result['all_passed']:return out('patched',source=candidate,changes=[change.reason],after=result)
        single.append((sum(result['passed']),change))
    # Two non-overlapping local changes, prioritized by observed pass count.
    promising=[c for _,c in sorted(single,key=lambda pair:-pair[0])[:28]]
    for group in itertools.combinations(promising,2):
        if stats['tried']>=max_candidates or time.monotonic()-started>seconds:
            stats['budget_exhausted']=True;break
        candidate,result=attempt(group)
        if result and result['supported'] and result['all_passed']:
            return out('patched',source=candidate,changes=[c.reason for c in group],after=result)
    return out('not-found')


def review_text(findings):
    if not findings:return 'No findings from the supported scope/control-flow checks. This is not proof that the code is correct.'
    return '\n'.join(f"- Line {f['line']} [{f['severity']}]: {f['message']}" for f in findings)


def probes(source):
    """AST-derived diagnostic inputs with explicit type assumptions; no golds."""
    tree=ast.parse(source);cases=[]
    for fn in tree.body:
        if not isinstance(fn,ast.FunctionDef) or fn.args.vararg or fn.args.kwarg or fn.args.kwonlyargs:continue
        params=[a.arg for a in [*fn.args.posonlyargs,*fn.args.args]]
        if len(params)>2:continue
        pools=[]
        for param in params:
            kinds=set()
            for n in ast.walk(fn):
                if isinstance(n,ast.For) and isinstance(n.iter,ast.Name) and n.iter.id==param:kinds.add('list')
                if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in {'sum','len','sorted','min','max'} and n.args and isinstance(n.args[0],ast.Name) and n.args[0].id==param:kinds.add('list')
                if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='range' and any(isinstance(a,ast.Name) and a.id==param for a in n.args):kinds.add('integer')
                if isinstance(n,ast.Subscript) and isinstance(n.value,ast.Name) and n.value.id==param:kinds.add('list')
                if isinstance(n,ast.Attribute) and isinstance(n.value,ast.Name) and n.value.id==param:
                    if n.attr in {'split','lower','strip','upper','startswith','endswith'}:kinds.add('string')
                    if n.attr in {'get','items','keys','values','setdefault'}:kinds.add('dict')
                if isinstance(n,(ast.BinOp,ast.Compare)) and any(isinstance(c,ast.Name) and c.id==param for c in ast.iter_child_nodes(n)):kinds.add('integer')
            if len(kinds)!=1:break
            pools.append({'list':[[],[0],[1,-1,2]],'integer':[0,1,-1,2],
                          'string':['','a b',' A '],'dict':[{}, {'a':1}]}[next(iter(kinds))])
        if len(pools)!=len(params):continue
        for args in itertools.product(*pools):
            cases.append(dict(name=fn.name,args=list(args),kwargs={},assumption='AST-inferred primitive input types; caller contract is unknown'))
            if len(cases)>=12:return cases
    return cases


def diagnostic_text(source):
    calls=probes(source)
    if not calls:return ''
    result=run_cases(source,calls,steps=5000);observations=[]
    for case,got in zip(calls,result.get('cases',[])):
        if got['status']=='error':
            observations.append(f"- `{case['name']}({', '.join(repr(a) for a in case['args'])})` raises `{got['error']}`.")
        elif got['status'] in {'limit','unsupported'}:
            observations.append(f"- Interpretation stopped: {got['message']}.");break
        if len(observations)>=3:break
    if not observations:return f'\n\n{len(result.get("cases",[]))} AST-derived probe calls completed without an observed exception. Their assumed input types may differ from your contract; they are not correctness tests.'
    return '\n\nDiagnostic probes (input types inferred from syntax; an exception may be intended):\n'+'\n'.join(observations)


def reply(text):
    if not ASK.search(text.split('```',1)[0]):return None
    fenced=re.search(r'```(?:python|py)?\s*\n(.*?)```',text,re.S)
    if fenced:source=fenced[1].strip('\n')
    else:
        from .explain import code_in,looks_like_code
        source=code_in(text)
        if not source or not looks_like_code(source,text):return None
    if len(source)>16000:
        return dict(route='chat/code-review',response='This source exceeds the current 16,000-character review limit. Send the function and its failing examples.',sources=[])
    findings=analyze(source)
    details=('Non-neural AST scope/control-flow analysis and bounded interpretation of a pure-Python subset. '
             'Pasted code is never run with exec/eval and has no file/network/process access here. '
             'Static risks and observations are not all confirmed defects; examples do not prove general correctness.')
    out=lambda response,route:dict(response=response,route='chat/code-'+route,sources=[],details=details)
    cases=examples(text)
    fixing=bool(re.search(r'(?i)\b(?:fix|debug|repair|correct)\b',text.split('```',1)[0]))
    if findings and findings[0]['code']=='SYNTAX':
        if fixing:return None  # Existing syntax-repair adapter retains its contract.
        return out(review_text(findings),'review')
    heading=review_text(findings)
    if not fixing:
        if cases:
            checked=check(source,cases);passed=sum(checked['passed'])
            heading+=f'\n\nBounded interpretation matches {passed}/{len(cases)} supplied examples.'
            if not checked['supported']:heading+=' Some execution is unsupported or exceeded the budget; no exact result is claimed for those cases.'
        else:heading+=diagnostic_text(source)
        return out(heading,'review')
    if len(cases)<2:
        return out(heading+diagnostic_text(source)+'\n\nFor a behavioral repair, provide at least two literal calls and expected results outside the code block, one per line. '
                   'Include a failing case and a case that already works, for example `f([1, 2]) == 3`. No behavioral patch was applied.','repair-needs-tests')
    result=repair(source,cases)
    if result['status']=='patched':
        patch=result['source']
        # Displayed diff lines need separators even when pasted source has no
        # trailing newline. The actual source/candidate bytes stay untouched.
        diff=''.join(difflib.unified_diff([line+'\n' for line in source.splitlines()],
                    [line+'\n' for line in patch.splitlines()],fromfile='original.py',tofile='candidate.py'))
        failed=next(i for i,ok in enumerate(result['before']['passed']) if not ok)
        observation=result['before']['execution']['cases'][failed]
        actual=repr(observation.get('value')) if observation['status']=='value' else observation.get('error',observation['status'])
        note=f"Example {failed+1}: original result {actual}; expected {cases[failed]['expected']!r}."
        explanation='\n'.join('- '+reason for reason in result['changes'])
        return out(f'Candidate repair:\n\n```python\n{patch}\n```\n{explanation}\n\n{note}\n'
                   f"It matches all {len(cases)} supplied examples after testing {result['stats']['tried']} patches in the bounded interpreter. "
                   'This is a test-supported candidate, not proof for untested inputs. Your source files were not changed.\n\n'
                   f'```diff\n{diff}\n```','repaired')
    if result['status']=='already-passes':
        return out(f'All {len(cases)} supplied examples pass in the bounded interpreter. No behavioral patch is proposed.\n\n'+heading,'review')
    if result['status']=='unsupported':
        return out(heading+'\n\nThe supplied tests use execution outside the supported pure-Python subset or resource budget. '
                   'I cannot verify a behavioral patch here; no corrected code is claimed.','repair-unsupported')
    return out(heading+f"\n\nNo patch passed all {len(cases)} examples within the local-edit search ({result['stats']['tried']} candidates). "
               'The original code is unchanged. More precise requirements or a smaller function may help.','repair-not-found')
