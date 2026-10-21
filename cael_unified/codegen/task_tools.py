"""Ordered, bounded task tools compiled from primitive plans, without neural AI.

This is a deliberately small specification language, not general language or
Python understanding. It composes operations and supplied helper calls, checks
the emitted AST against an IR evaluator/examples, and can use the tool on data.
Nothing is installed, persisted globally, or executed as native user code.
"""
import ast
import builtins
from dataclasses import dataclass
import keyword
import re

from .python_vm import Machine, Unsupported, Limit, run_cases, BUILTINS
from .workbench import examples, same
from .object_model import METHODS


PREFIX='Built Python tool '
USE_PREFIX='Using Python tool '
QUESTION='The examples leave more than one tool plan.'
ASK=re.compile(r'(?is)\b(?:build|write|create|make|implement)\b.{0,65}\b(?:tool|helper|workflow)\b')
APPLY=re.compile(r'(?im)^\s*(?:use|run|apply)(?: it| this tool| this helper| the tool)? (?:on|with)\s+(.+?)\s*$')
LIMIT_ITEMS=40
LIMIT_VALUE=10**12


class Unclear(ValueError): pass


@dataclass(frozen=True)
class Step:
    kind: str
    expression: str = ''
    count: int = 0
    initial: int = 0
    helper: str = ''
    reverse: bool = False


def literal(text):
    if len(text)>1800:raise Unclear('Use at most 40 integer values as literal input.')
    try:
        tree=ast.parse(text.strip(),mode='eval')
        if sum(1 for _ in ast.walk(tree))>180:raise Unclear('The literal input is too large.')
        value=ast.literal_eval(tree)
    except (SyntaxError,ValueError,TypeError,RecursionError) as error:raise Unclear('Supply a literal integer list, for example Use it on [3, -1, 4].') from error
    guard(value,10**6);return value


def guard(value,bound=LIMIT_VALUE):
    if type(value) is not list or len(value)>LIMIT_ITEMS:raise ValueError('Expected a list of at most 40 integers')
    if any(type(x) is not int or abs(x)>bound for x in value):raise ValueError('Expected bounded integer values')
    return value


def scalar(value):
    if type(value) is not int or abs(value)>LIMIT_VALUE:raise ValueError('Expected a bounded integer result')
    return value


def expression(text,names):
    """Allow only an explicit, small arithmetic/predicate expression."""
    try:tree=ast.parse(text.strip(),mode='eval')
    except (SyntaxError,RecursionError) as error:raise Unclear('That step needs a valid small Python expression.') from error
    nodes=list(ast.walk(tree))
    allowed=(ast.Expression,ast.Name,ast.Load,ast.Constant,ast.BinOp,ast.UnaryOp,ast.BoolOp,ast.Compare,ast.IfExp,
             ast.Add,ast.Sub,ast.Mult,ast.FloorDiv,ast.Mod,ast.Pow,ast.USub,ast.UAdd,ast.Not,
             ast.And,ast.Or,ast.Eq,ast.NotEq,ast.Lt,ast.LtE,ast.Gt,ast.GtE,ast.Call)
    if len(nodes)>45 or any(not isinstance(n,allowed) for n in nodes):raise Unclear('Use only bounded arithmetic, comparisons, abs/min/max, and x (plus state in a fold).')
    for n in nodes:
        if isinstance(n,ast.Name) and n.id not in {*names,'abs','min','max'}:raise Unclear('Unknown expression binding: '+n.id)
        if isinstance(n,ast.Constant) and (type(n.value) not in (int,bool) or abs(n.value)>100):raise Unclear('Expression constants must be integers within ±100.')
        if isinstance(n,ast.Call) and (not isinstance(n.func,ast.Name) or n.func.id not in {'abs','min','max'} or n.keywords):raise Unclear('Only abs/min/max calls are supported inside expressions.')
        if isinstance(n,ast.Pow) or isinstance(n,ast.BinOp) and isinstance(n.op,ast.Pow):
            if isinstance(n,ast.BinOp) and (not isinstance(n.right,ast.Constant) or type(n.right.value) is not int or not 0<=n.right.value<=6):raise Unclear('Powers need a literal exponent between 0 and 6.')
    return ast.unparse(tree.body)


def predicate(text):
    text=text.strip().lower()
    if text in {'positive','negative','nonnegative','nonpositive','nonzero','even','odd'}:
        return {'positive':'x > 0','negative':'x < 0','nonnegative':'x >= 0','nonpositive':'x <= 0',
                'nonzero':'x != 0','even':'x % 2 == 0','odd':'x % 2 != 0'}[text]
    match=re.fullmatch(r'(above|below|at least|at most) (-?\d{1,3})',text)
    if match:return expression('x '+{'above':'>','below':'<','at least':'>=','at most':'<='}[match[1]]+' '+match[2],{'x'})
    return expression(text,{'x'})


def parse_step(text):
    t=text.strip().strip('`').rstrip('.').strip();low=t.lower()
    if low in {'sum','sum the values','return the sum','return sum','total the values'}:return Step('sum')
    if low in {'count','count the values','return the count','return count'}:return Step('count')
    if low in {'product','multiply the values','return the product'}:return Step('product')
    if low in {'maximum','return the maximum','minimum','return the minimum'}:return Step('max' if 'max' in low else 'min')
    if low in {'return the values','return values','return the list'}:return Step('identity')
    if low in {'reverse','reverse the values'}:return Step('reverse')
    if low in {'remove duplicates','remove duplicates preserving order','deduplicate','keep distinct values in order'}:return Step('unique')
    if low in {'sort','sort ascending','sort the values ascending','sort descending','sort the values descending'}:return Step('sort',reverse='descending' in low)
    if low in {'square','square each value','square the values'}:return Step('map','x * x')
    if low in {'absolute values','take absolute values'}:return Step('map','abs(x)')
    if low in {'running totals','running sums','prefix sums','cumulative sums'}:return Step('scan','state + x',initial=0)
    match=re.fullmatch(r'(map|filter|keep|scan|reduce) (?:using|through|with) ([a-zA-Z]\w*)(?: starting at (-?\d{1,3}))?',t,re.I)
    if match:
        kind={'keep':'filter'}.get(match[1].lower(),match[1].lower())
        if kind in {'scan','reduce'} and match[3] is None:raise Unclear('Specify the initial state: '+kind+' using '+match[2]+' starting at 0.')
        if kind not in {'scan','reduce'} and match[3] is not None:raise Unclear('Only scan/reduce steps have an initial state.')
        initial=int(match[3] or 0)
        if abs(initial)>100:raise Unclear('The initial state must be within ±100.')
        return Step(kind,helper=match[2],initial=initial)
    match=re.fullmatch(r'(?:keep|filter)(?: only)? (.+?)(?: values| numbers| integers)?',t,re.I)
    if match:
        condition=re.sub(r'^where\s+','',match[1],flags=re.I)
        return Step('filter',predicate(condition))
    match=re.fullmatch(r'(?:map|transform)(?: each value to)?\s+(.+)',t,re.I)
    if match:return Step('map',expression(match[1].strip('`'),{'x'}))
    match=re.fullmatch(r'(scan|reduce) (.+?) starting at (-?\d{1,3})',t,re.I)
    if match:
        initial=int(match[3])
        if abs(initial)>100:raise Unclear('The initial state must be within ±100.')
        return Step(match[1].lower(),expression(match[2].strip('`'),{'state','x'}),initial=initial)
    match=re.fullmatch(r'(?:sum each full window|full window sums)(?: of size| size) (\d{1,2})',low)
    if match:
        size=int(match[1])
        if not 1<=size<=LIMIT_ITEMS:raise Unclear('Full window size must be between 1 and 40.')
        return Step('window',count=size)
    if re.search(r'\brolling|\bwindow',low):raise Unclear('Specify full or partial windows. Supported syntax: sum each full window of size 3.')
    match=re.fullmatch(r'(?:take|keep)(?: the)? (first|last) (\d{1,2})(?: values)?',low)
    if match:
        count=int(match[2])
        if count>LIMIT_ITEMS:raise Unclear('Take at most 40 values.')
        return Step(match[1],count=count)
    raise Unclear('I cannot interpret this step reliably: '+t+'. Use one explicit operation per step; no code was built.')


def helper_definitions(source,steps):
    if not source:
        if any(s.helper for s in steps):raise Unclear('Paste the helper function definitions in a Python code block.')
        return {}
    if len(source)>6000:raise Unclear('Keep supplied helper code within 6,000 characters.')
    try:tree=ast.parse(source)
    except (SyntaxError,RecursionError) as error:raise Unclear('The supplied helper definitions do not parse.') from error
    if sum(1 for _ in ast.walk(tree))>300:raise Unclear('Supplied helper definitions exceed the AST budget.')
    functions={}
    for item in tree.body:
        if isinstance(item,ast.Expr) and isinstance(item.value,ast.Constant) and isinstance(item.value.value,str):continue
        if not isinstance(item,ast.FunctionDef) or item.decorator_list or item.name in functions:raise Unclear('Supply unique function definitions only; module statements and decorators are unsupported here.')
        if item.name in BUILTINS or item.name.startswith('_'):raise Unclear('Helpers must use public names that do not shadow built-ins.')
        if item.args.vararg or item.args.kwarg or item.args.kwonlyargs:raise Unclear('Helpers currently need ordinary positional parameters.')
        if any(not isinstance(d,ast.Constant) or type(d.value) not in (int,bool,str,type(None)) for d in item.args.defaults):raise Unclear('Mutable or computed helper defaults are unsupported for reusable task tools.')
        functions[item.name]=item
    if len(functions)>5:raise Unclear('Supply at most five small helper definitions.')
    local_callables={n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    safe_builtins=set(BUILTINS)-{'print','super','staticmethod','classmethod','property'}
    attributes=set.union(*METHODS.values())|local_callables|{'__init__'}
    for node in ast.walk(tree):
        if isinstance(node,(ast.Import,ast.ImportFrom,ast.Global,ast.Nonlocal,ast.AsyncFunctionDef)):
            raise Unclear('Imports, global/nonlocal writes and async are unsupported in reusable task helpers.')
        if isinstance(node,ast.Name) and isinstance(node.ctx,ast.Load) and node.id not in safe_builtins|local_callables and hasattr(builtins,node.id):
            raise Unclear('Unsupported helper capability: '+node.id)
        if isinstance(node,ast.Attribute) and node.attr not in attributes:
            raise Unclear('Unsupported helper attribute/protocol: '+node.attr)
    for step in steps:
        if not step.helper:continue
        if step.helper not in functions:raise Unclear('Helper is not defined: '+step.helper)
        fn=functions[step.helper];total=len(fn.args.posonlyargs)+len(fn.args.args);required=total-len(fn.args.defaults)
        count=2 if step.kind in {'scan','reduce'} else 1
        if not required<=count<=total:raise Unclear('Helper '+step.helper+' does not accept '+str(count)+' positional arguments.')
    return functions


def parse(text):
    outside=re.sub(r'```.*?```','',text,flags=re.S)
    if not ASK.search(outside):return None
    marker=re.search(r'(?im)^\s*steps?\s*:\s*',outside)
    if marker is None:return parse_automatic(text,outside)
    if len(text)>10000:raise Unclear('Please shorten the tool request.')
    heading=outside[:marker.start()]
    if re.search(r'(?i)\b(?:without|do not|no loops|in[- ]place|recursive|recursion|files?|network|async|threads?|pandas|numpy|floats?|strings?|dictionaries|csv)\b',heading):
        raise Unclear('Those input or implementation requirements are outside this integer-list tool compiler. No code was built.')
    chosen=re.search(r'\b(?:named|called)\s+`?([A-Za-z_]\w*)',heading,re.I)
    name=chosen[1] if chosen else 'task_tool'
    if len(name)>60 or keyword.iskeyword(name) or name in BUILTINS or name.startswith('_'):raise Unclear('Choose a public Python name that does not shadow built-ins.')
    # Every post-marker clause must be understood or be an explicit assertion/input.
    body=outside[marker.end():];clauses=[];input_value=None
    for line in body.splitlines():
        if not line.strip():continue
        use=APPLY.fullmatch(line)
        if use:
            if input_value is not None:raise Unclear('Supply one Use it on input per request.')
            input_value=literal(use[1]);continue
        if examples(line):continue
        for part in re.split(r'\s*;\s*|\s+then\s+',line,flags=re.I):
            part=re.sub(r'^\s*(?:[-*]|\d+[.)])\s*','',part).strip()
            if part:clauses.append(part)
    if not 1<=len(clauses)<=8:raise Unclear('Give between one and eight ordered steps.')
    steps=[parse_step(c) for c in clauses];scalar_seen=False
    for step in steps:
        if scalar_seen:raise Unclear('A scalar result cannot feed another list step. Put sum/count/reduce/min/max/product last.')
        scalar_seen=step.kind in {'sum','count','product','reduce','min','max'}
    blocks=re.findall(r'```(?:python|py)?\s*\n(.*?)```',text,re.S)
    if len(blocks)>1:raise Unclear('Put the reusable helper definitions in one Python block.')
    source=blocks[0].strip() if blocks else ''
    functions=helper_definitions(source,steps)
    if name in functions:raise Unclear('The new tool name must differ from supplied helper names.')
    cases=examples(text)
    if any(c['name']!=name or len(c['args'])!=1 or c['kwargs'] for c in cases):raise Unclear('Examples must call '+name+' with one integer-list argument.')
    for c in cases:guard(c['args'][0],10**6)
    return dict(name=name,steps=steps,clauses=clauses,helpers=source,functions=functions,input=input_value,cases=cases)


def parse_automatic(text,outside):
    # Explicit tool requests only: preserve existing example-driven helper paths.
    if not re.search(r'(?i)\btool\b',outside):return None
    if len(text)>10000:raise Unclear('Please shorten the tool request.')
    cases=examples(text)
    if len(cases)<3:raise Unclear('For automatic tool planning, give at least three contrasting function examples, or supply a Steps: list. The current domain is integer lists.')
    names={c['name'] for c in cases}
    if len(names)!=1:raise Unclear('Use one function name for all tool examples.')
    name=cases[0]['name']
    if keyword.iskeyword(name) or name in BUILTINS or name.startswith('_') or len(name)>60:raise Unclear('Choose a public tool name that does not shadow built-ins.')
    chosen=re.search(r'\b(?:named|called)\s+`?([A-Za-z_]\w*)',outside,re.I)
    if chosen and chosen[1]!=name:raise Unclear('The tool name and example names must agree.')
    if re.search(r'(?i)\b(?:without|do not|no loops|in[- ]place|recursive|recursion|files?|network|async|threads?|pandas|numpy|floats?|strings?|dictionaries|csv)\b',outside.split('\n',1)[0]):raise Unclear('Those implementation/input requirements cannot be verified by this integer-list tool planner.')
    for case in cases:
        if len(case['args'])!=1 or case['kwargs']:raise Unclear('Automatic tools currently take one integer list.')
        guard(case['args'][0],10**6)
        if type(case['expected']) is list:guard(case['expected'])
        else:scalar(case['expected'])
    blocks=re.findall(r'```(?:python|py)?\s*\n(.*?)```',text,re.S)
    if len(blocks)>1:raise Unclear('Use one Python block for reusable helper definitions.')
    source=blocks[0].strip() if blocks else '';functions=helper_definitions(source,[])
    if name in functions:raise Unclear('The requested new tool must differ from supplied helper names.')
    applied=APPLY.findall(outside)
    if len(applied)>1:raise Unclear('Supply one Use it on input per request.')
    description=re.sub(r'(?m)^.*?'+re.escape(name)+r'\(.*$','',outside)
    return dict(name=name,steps=None,clauses=[],helpers=source,functions=functions,input=literal(applied[0]) if applied else None,cases=cases,description=description)


CHECKS='''def _cael_check(values, bound):
    if type(values) is not list or len(values) > 40:
        raise ValueError('Expected a list of at most 40 integers')
    for value in values:
        if type(value) is not int or abs(value) > bound:
            raise ValueError('Expected bounded integer values')
    return values

def _cael_scalar(value):
    if type(value) is not int or abs(value) > 1000000000000:
        raise ValueError('Expected a bounded integer result')
    return value
'''


def compile_plan(plan):
    lines=[f'def {plan["name"]}(numbers):','    _cael_check(numbers, 1000000)','    values = list(numbers)']
    add=lambda s:lines.append('    '+s)
    for step in plan['steps']:
        expr=step.helper+'(x)' if step.helper else step.expression
        if step.kind=='filter':add('values = [x for x in values if '+expr+']')
        elif step.kind=='map':add('values = ['+expr+' for x in values]')
        elif step.kind=='window':add(f'values = [sum(values[i:i + {step.count}]) for i in range(max(0, len(values) - {step.count} + 1))]')
        elif step.kind=='sort':add('values = sorted(values, reverse='+str(step.reverse)+')')
        elif step.kind=='reverse':add('values = values[::-1]')
        elif step.kind=='first':add('values = values[:'+str(step.count)+']')
        elif step.kind=='last':add('values = values[-'+str(step.count)+':]' if step.count else 'values = []')
        elif step.kind=='unique':
            for line in ['unique = []','for x in values:','    if x not in unique:','        unique.append(x)','values = unique']:add(line)
        elif step.kind in {'scan','reduce','product'}:
            add('state = '+str(1 if step.kind=='product' else step.initial))
            if step.kind=='scan':add('history = []')
            add('for x in values:')
            update=step.helper+'(state, x)' if step.helper else 'state * x' if step.kind=='product' else step.expression
            add('    state = _cael_scalar('+update+')')
            if step.kind=='scan':add('    history.append(state)')
            add('values = history' if step.kind=='scan' else 'return state')
        elif step.kind in {'sum','count','min','max'}:add('return _cael_scalar('+('len' if step.kind=='count' else step.kind)+'(values))')
        elif step.kind!='identity':raise Unclear('Unsupported internal plan kind')
        if step.kind not in {'sum','count','reduce','min','max','product'}:add('_cael_check(values, 1000000000000)')
    if plan['steps'][-1].kind not in {'sum','count','reduce','min','max','product'}:add('return values')
    source=plan['helpers']+'\n\n' if plan['helpers'] else ''
    return source+CHECKS+'\n'+'\n'.join(lines)+'\n'


def interpret(plan,values,input_bound=10**6):
    """IR oracle: direct primitives; only helper/expression bodies use the VM."""
    guard(values,input_bound);values=list(values);machine=Machine(20000)
    scope=machine.load(plan['helpers'])
    def calc(step,x,state=None):
        if step.helper:return machine.call(scope.lookup(step.helper),[state,x] if step.kind in {'scan','reduce'} else [x],{})
        from .python_vm import Scope
        local=Scope(scope);local.values.update(x=x,state=state)
        return machine.expr(ast.parse(step.expression,mode='eval').body,local)
    for step in plan['steps']:
        kind=step.kind
        if kind=='filter':values=[x for x in values if calc(step,x)]
        elif kind=='map':values=[scalar(calc(step,x)) for x in values]
        elif kind=='window':
            result=[]
            for index in range(step.count-1,len(values)):
                result.append(sum(values[index-step.count+1:index+1]))
            values=result
        elif kind=='sort':values=sorted(values,reverse=step.reverse)
        elif kind=='reverse':values=list(reversed(values))
        elif kind=='first':values=[x for i,x in enumerate(values) if i<step.count]
        elif kind=='last':values=[x for i,x in enumerate(values) if i>=len(values)-step.count]
        elif kind=='unique':
            result=[]
            for value in values:
                if value not in result:result.append(value)
            values=result
        elif kind in {'scan','reduce','product'}:
            state=1 if kind=='product' else step.initial;history=[]
            for x in values:
                state=scalar(state*x if kind=='product' else calc(step,x,state));history.append(state)
            if kind!='scan':return state
            values=history
        elif kind in {'sum','count','min','max'}:return scalar({'sum':sum,'count':len,'min':min,'max':max}[kind](values))
        guard(values)
    return values


def outcome(function):
    try:return dict(status='value',value=function())
    except Unsupported as error:return dict(status='limit' if isinstance(error,Limit) else 'unsupported',message=str(error))
    except Exception as error:return dict(status='error',error=type(error).__name__)


def build(plan):
    source=compile_plan(plan)
    probes=[[],[0],[1,-1,2],[2,2,-3],[4,-2,5]]
    # Probes check compiler behavior, not inferred task intent. Supplied tests
    # and the real use input are separate obligations and never search targets.
    inputs=probes+[c['args'][0] for c in plan['cases']]
    if plan['input'] is not None:inputs.append(plan['input'])
    reference=[outcome(lambda xs=xs:interpret(plan,xs)) for xs in inputs]
    if any(c['status'] in {'unsupported','limit'} for c in reference):return dict(status='unsupported',message='A supplied helper or expression is outside the bounded interpreter, or exhausted its budget.')
    actual=run_cases(source,[dict(name=plan['name'],args=[xs]) for xs in inputs],steps=80000)
    if actual['status']!='ok' or len(actual.get('cases',[]))!=len(reference):return dict(status='unsupported',message='The generated tool exceeded the supported interpreter or AST budget.')
    for wanted,got in zip(reference,actual['cases']):
        if wanted['status']!=got['status'] or (not same(wanted['value'],got.get('value')) if wanted['status']=='value' else wanted.get('error')!=got.get('error')):
            return dict(status='verification-failed',message='The generated code did not agree with its ordered plan; no successful tool is claimed.')
    for case,observed in zip(plan['cases'],reference[len(probes):]):
        if observed['status']!='value' or not same(observed['value'],case['expected']):
            return dict(status='contradiction',message='The ordered steps disagree with a supplied example. For '+repr(case['args'][0])+', the plan gives '+repr(observed.get('value',observed.get('error')))+'; your example expects '+repr(case['expected'])+'. Clarify the step order or expected result.')
    if plan['input'] is not None and reference[-1]['status']!='value':return dict(status='execution-error',message='The requested use raises '+reference[-1].get('error','an error')+' under the stated steps; no completed task result is claimed.')
    return dict(status='built',source=source,probes=len(probes),examples=len(plan['cases']),probe_errors=sum(c['status']=='error' for c in reference[:len(probes)]),value=reference[-1].get('value') if plan['input'] is not None else None)


def reply(text,messages=None):
    from ..local_tools.chat import reply as local_reply
    local_tool=local_reply(text)
    if local_tool is not None:return local_tool
    from .data_tools import reply as data_reply
    data_tool=data_reply(text,messages=messages)
    if data_tool is not None:return data_tool
    request=text;follow=False;override=None
    if messages and len(messages)>=3 and messages[-2].get('role')=='assistant' and messages[-2].get('content','').startswith(QUESTION) and examples(text):
        new_names={c['name'] for c in examples(text)};parts=[text]
        for index in range(len(messages)-3,max(-1,len(messages)-12),-2):
            old=messages[index]
            if old.get('role')!='user' or {c['name'] for c in examples(old.get('content',''))}!=new_names:break
            parts.insert(0,old['content'])
            if ASK.search(old['content']):request='\n'.join(parts);break
            if index<1 or not messages[index-1].get('content','').startswith(QUESTION):break
    # Rebuild from the human's immediately active tool specification, not from
    # arbitrary assistant code or cross-session learned memory.
    if messages and len(messages)>=3 and APPLY.fullmatch(text.strip()) and messages[-2].get('role')=='assistant' and messages[-2].get('content','').startswith((PREFIX,USE_PREFIX)):
        for index in range(len(messages)-3,max(-1,len(messages)-10),-2):
            old=messages[index]
            if old.get('role')!='user':break
            if ASK.search(old.get('content','')):
                request=old['content'];follow=True;override=APPLY.fullmatch(text.strip())[1];break
            if index<1 or not messages[index-1].get('content','').startswith((PREFIX,USE_PREFIX)):break
    details=('Non-neural ordered tool compiler. Parses explicit steps into a typed integer-list plan, composes Python statements and supplied helper calls, '
             'checks generated code against a plan interpreter and supplied examples, then uses it in the bounded AST machine. '
             'At most 40 integers within ±1,000,000 and integer intermediate states/results within ±1,000,000,000,000. '
             'No native execution of user code, external access, installation or global persistence. Plan probes are compiler checks, not proof of intent or general Python understanding.')
    out=lambda response,route:dict(response=response,route='chat/code-task-tool-'+route,sources=[],details=details)
    try:
        plan=parse(request)
        if plan is None:return None
        if follow:plan['input']=literal(override)
        search_stats=None
        if plan['steps'] is None:
            from .tool_search import synthesize
            searched=synthesize(plan);search_stats=searched['stats']
            if searched['status']=='ambiguous':return out(QUESTION+' What should `'+plan['name']+'('+repr(searched['witness'])+')` return? Candidate values are `'+repr(searched['predictions'][0])+'` and `'+repr(searched['predictions'][1])+'`. Add a contrasting example.','clarify')
            if searched['status']!='planned':return out('No tool plan passed all supplied examples within the bounded search ('+str(search_stats['plans'])+' plans). The planner composes at most four integer-list stages; no new tool was claimed.','not-found')
            plan=searched['plan']
        result=build(plan)
    except (Unclear,ValueError) as error:return out(str(error),'clarify')
    except (Unsupported,SyntaxError,RecursionError) as error:return out('That helper or plan is outside the bounded tool compiler. No successful tool was created.','unsupported')
    if result['status']!='built':return out(result['message'],result['status'])
    if follow:return out(USE_PREFIX+'`'+plan['name']+'` on '+repr(plan['input'])+':\n\n```text\n'+repr(result['value'])+'\n```\nThe tool was reconstructed from this conversation’s specification and checked in the bounded interpreter.','used')
    lines=[PREFIX+'`'+plan['name']+'`.', 'Plan: '+' → '.join(plan['clauses'])+'.', '```python\n'+result['source']+'```']
    if search_stats:lines.append('I searched '+str(search_stats['plans'])+' operation compositions against the supplied examples. This bounded search is incomplete and does not establish a unique solution; no expected answer was inserted into the code.')
    if plan['functions']:
        lines.append('Reused supplied code: '+', '.join('`'+name+'` ('+str(len(fn.args.posonlyargs)+len(fn.args.args))+' positional parameters)' for name,fn in plan['functions'].items())+'.')
    lines.append('The emitted function agrees with the ordered plan on '+str(result['probes'])+' bounded probes and '+str(result['examples'])+' supplied examples. '
                 + (str(result['probe_errors'])+' probes raise expected Python errors under this plan. ' if result['probe_errors'] else '')
                 +'These checks do not prove your intended behavior. Limits: 40 integer inputs within ±1,000,000; intermediate integers/results within ±1,000,000,000,000. No executable tool was installed.')
    if plan['input'] is not None:lines.append('Used on '+repr(plan['input'])+':\n```text\n'+repr(result['value'])+'\n```')
    else:lines.append('To use it here, reply: Use it on [3, -1, 4].')
    return out('\n\n'.join(lines),'built')
