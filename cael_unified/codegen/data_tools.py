"""Symbolic compilation of bounded record/text tasks and structured state.

Value-oriented tools: clone input/stage results, never mutate caller data or
install executable code. Explicit operation plans, not a general Python model.
"""
import ast
from dataclasses import dataclass
import keyword
import re

from .python_vm import Machine, Scope, Unsupported, run_cases, BUILTINS
from .object_model import METHODS
from .task_tools import ASK, APPLY, Unclear, helper_definitions, outcome
from .workbench import examples, same

PREFIX='Built data tool '
USED='Using data tool '
MISSING=object()


@dataclass
class Step:
    kind: str
    expression: str = ''
    key: str = ''
    helper: str = ''
    initial: object = None
    count: int = 0
    reverse: bool = False
    policy: str = ''


def clone(value,depth=0,count=None):
    count=[0] if count is None else count;count[0]+=1
    if depth>6 or count[0]>800:raise ValueError('Data nesting/item budget exceeded')
    kind=type(value)
    if value is None or kind is bool:return value
    if kind is int:
        if abs(value)>10**12:raise ValueError('Integer bound exceeded')
        return value
    if kind is str:
        if len(value)>2048:raise ValueError('Text value exceeds 2048 characters')
        return value
    if kind is list:
        if len(value)>40:raise ValueError('At most 40 list items are supported')
        return [clone(x,depth+1,count) for x in value]
    if kind is dict:
        if len(value)>40:raise ValueError('At most 40 dictionary entries are supported')
        out={}
        for key,item in value.items():
            if type(key) not in (str,int,bool,type(None)):raise ValueError('Unsupported dictionary key')
            out[clone(key,depth+1,count)]=clone(item,depth+1,count)
        return out
    raise ValueError('Expected bounded text, integers, booleans, None, lists or dictionaries')


def literal(text):
    if len(text)>6500:raise Unclear('The literal data is too large.')
    try:
        tree=ast.parse(text.strip(),mode='eval')
        if sum(1 for _ in ast.walk(tree))>500:raise Unclear('The literal data exceeds the AST budget.')
        return clone(ast.literal_eval(tree))
    except (SyntaxError,ValueError,TypeError,RecursionError) as error:raise Unclear('Use bounded Python literal data: a string or list of records; '+str(error)) from error


def expression(text,names,functions):
    try:tree=ast.parse(text.strip().strip('`'),mode='eval')
    except (SyntaxError,RecursionError) as error:raise Unclear('Use a small valid Python expression for this step.') from error
    nodes=list(ast.walk(tree));calls={'len','sum','min','max','abs','str','int','bool','sorted',*functions}
    allowed=(ast.Expression,ast.Name,ast.Load,ast.Constant,ast.List,ast.Dict,ast.Subscript,ast.Slice,ast.Attribute,
             ast.BinOp,ast.UnaryOp,ast.BoolOp,ast.Compare,ast.IfExp,ast.Call,ast.keyword,
             ast.Add,ast.Sub,ast.Mult,ast.FloorDiv,ast.Mod,ast.USub,ast.UAdd,ast.Not,
             ast.And,ast.Or,ast.Eq,ast.NotEq,ast.Lt,ast.LtE,ast.Gt,ast.GtE,ast.In,ast.NotIn,ast.Is,ast.IsNot)
    if len(nodes)>70 or any(not isinstance(n,allowed) for n in nodes):raise Unclear('That expression exceeds the supported data-expression grammar.')
    methods=set.union(*METHODS.values())
    for node in nodes:
        if isinstance(node,ast.Name) and node.id not in {*names,*calls}:raise Unclear('Unknown expression binding: '+node.id)
        if isinstance(node,ast.Constant) and (type(node.value) not in (int,bool,str,type(None)) or type(node.value) is int and abs(node.value)>1000 or type(node.value) is str and len(node.value)>256):raise Unclear('Use small literal strings/integers in expressions.')
        if isinstance(node,ast.Attribute) and node.attr not in methods:raise Unclear('Unsupported data method: '+node.attr)
        if isinstance(node,ast.Call) and (not isinstance(node.func,(ast.Name,ast.Attribute)) or isinstance(node.func,ast.Name) and node.func.id not in calls or any(k.arg is None for k in node.keywords)):raise Unclear('Unsupported expression call.')
        if isinstance(node,ast.Dict) and any(k is None for k in node.keys):raise Unclear('Dictionary unpacking is unsupported.')
    return ast.unparse(tree.body)


def parse_step(text,functions):
    t=text.strip().rstrip('.');low=t.lower();expr=lambda s,names={'x'}:expression(s,names,functions)
    if low in {'split words','split into words'}:return Step('words')
    if low in {'split lines','split into lines'}:return Step('lines')
    if low in {'return values','return the values','return records','return the records'}:return Step('identity')
    if low in {'keep nonempty values','keep nonempty strings'}:return Step('filter','bool(x)')
    if low in {'strip each value','trim each value'}:return Step('map',"x.strip()")
    if low in {'lowercase each value','casefold each value'}:return Step('map','x.'+('casefold' if low.startswith('casefold') else 'lower')+'()')
    if low in {'count','return the count'}:return Step('count')
    if low in {'sum','sum values','return the sum'}:return Step('sum','x')
    if low in {'values of mapping','keys of mapping'}:return Step('values' if low.startswith('values') else 'keys')
    match=re.fullmatch(r'(?:split on|join with)\s+(.+)',t,re.I)
    if match:
        separator=literal(match[1])
        if type(separator) is not str or len(separator)>64:raise Unclear('Use a literal separator string of at most 64 characters.')
        return Step('split' if low.startswith('split') else 'join',initial=separator)
    match=re.fullmatch(r'(map|filter|keep|map entries) using ([A-Za-z]\w*)',t,re.I)
    if match:return Step({'keep':'filter','map entries':'entries'}.get(match[1].lower(),match[1].lower()),helper=match[2])
    match=re.fullmatch(r'(?:scan|fold|reduce) using ([A-Za-z]\w*) starting with (.+)',t,re.I)
    if match:return Step('scan' if low.startswith('scan') else 'reduce',helper=match[1],initial=literal(match[2]))
    match=re.fullmatch(r'(?:keep where|filter) (.+)',t,re.I)
    if match:return Step('filter',expr(match[1]))
    match=re.fullmatch(r'(?:map entries|map) (.+)',t,re.I)
    if match:return Step('entries' if low.startswith('map entries') else 'map',expr(match[1],{'key','value'} if low.startswith('map entries') else {'x'}))
    match=re.fullmatch(r'select fields (.+)',t,re.I)
    if match:
        fields=literal(match[1])
        if type(fields) is not list or not fields or any(type(k) is not str or not k or len(k)>80 for k in fields) or len(set(fields))!=len(fields):raise Unclear('Select a nonempty list of distinct literal field names.')
        return Step('select',initial=fields)
    match=re.fullmatch(r'sort by (.+?) (ascending|descending)',t,re.I)
    if match:return Step('sort',expr(match[1]),reverse=match[2].lower()=='descending')
    match=re.fullmatch(r'(group|count|unique) by (.+)',t,re.I)
    if match:return Step({'group':'group','count':'frequency','unique':'unique'}[match[1].lower()],key=expr(match[2]))
    match=re.fullmatch(r'sum (.+?) by (.+)',t,re.I)
    if match:return Step('total',expr(match[1]),key=expr(match[2]))
    match=re.fullmatch(r'index by (.+?) (keeping first|keeping last|rejecting duplicates)',t,re.I)
    if match:return Step('index',key=expr(match[1]),policy=match[2].lower())
    if low.startswith('index by'):raise Unclear('Specify index duplicate policy: keeping first, keeping last, or rejecting duplicates.')
    match=re.fullmatch(r'(?:take|keep) (?:the )?(first|last) (\d{1,2})(?: values| records)?',low)
    if match and int(match[2])<=40:return Step(match[1],count=int(match[2]))
    match=re.fullmatch(r'sum (.+)',t,re.I)
    if match:return Step('sum',expr(match[1]))
    raise Unclear('Unknown data step: '+t+'. Use one explicit operation per step.')


def parse(text):
    outside=re.sub(r'```.*?```','',text,flags=re.S)
    if not ASK.search(outside):return None
    marker=re.search(r'(?im)^\s*steps?\s*:\s*',outside)
    heading=outside[:marker.start()] if marker else outside.split('\n',1)[0]
    domain=re.search(r'(?i)\bfor (?:a |the )?(?:list of )?(records|text)\b',heading)
    if domain is None:return None
    if len(text)>12000:raise Unclear('Shorten the data tool specification.')
    if marker is None:raise Unclear('Record/text tools currently need an explicit Steps: list; automatic data-tool inference is not supported.')
    if re.search(r'(?i)\b(?:without|do not|in[- ]place|files?|network|async|pandas|numpy|csv|floats?)\b',heading):raise Unclear('Those input/implementation requirements are outside this bounded data-tool compiler.')
    chosen=re.search(r'\b(?:named|called)\s+`?([A-Za-z_]\w*)',heading,re.I);name=chosen[1] if chosen else 'data_tool'
    if keyword.iskeyword(name) or name in BUILTINS or name.startswith('_') or len(name)>60:raise Unclear('Choose a public tool name that does not shadow built-ins.')
    blocks=re.findall(r'```(?:python|py)?\s*\n(.*?)```',text,re.S)
    if len(blocks)>1:raise Unclear('Use one block for reusable Python helper definitions.')
    source=blocks[0].strip() if blocks else '';functions=helper_definitions(source,[])
    if name in functions:raise Unclear('New tool and supplied helper names must differ.')
    clauses=[];use=MISSING
    for line in outside[marker.end():].splitlines():
        if not line.strip():continue
        applied=APPLY.fullmatch(line)
        if applied:
            if use is not MISSING:raise Unclear('Supply one Use it on input per request.')
            use=literal(applied[1]);continue
        if examples(line):continue
        # Semicolons inside Python strings/expressions are data, not separators.
        try:
            import io,tokenize
            pieces=[];last=0;depth=0
            for token in tokenize.generate_tokens(io.StringIO(line).readline):
                if token.type==tokenize.OP:
                    if token.string in '([{':depth+=1
                    elif token.string in ')]}':depth-=1
                    elif token.string==';' and depth==0:pieces.append(line[last:token.start[1]]);last=token.end[1]
            pieces.append(line[last:])
        except (tokenize.TokenError,IndentationError):raise Unclear('A data step has unbalanced quotes/brackets.')
        for part in pieces:
            part=re.sub(r'^\s*(?:[-*]|\d+[.)])\s*','',part).strip()
            if part:clauses.append(part)
    if not 1<=len(clauses)<=8:raise Unclear('Use between one and eight explicit data steps.')
    steps=[parse_step(c,functions) for c in clauses]
    # Reuse the shared helper capability and positional-arity checks.
    helper_definitions(source,[Step('reduce' if s.kind=='entries' else s.kind,helper=s.helper) for s in steps])
    state='text' if domain[1].lower()=='text' else 'sequence'
    for step in steps:
        required='text' if step.kind in {'words','lines','split'} else 'mapping' if step.kind in {'keys','values','entries'} else None if step.kind=='identity' else 'sequence'
        if required is not None and state!=required:raise Unclear('Invalid type transition: '+step.kind+' needs '+required+', but receives '+state+'.')
        state='mapping' if step.kind in {'group','frequency','total','index'} else 'text' if step.kind=='join' else 'scalar' if step.kind in {'sum','count','reduce'} else 'sequence' if step.kind in {'words','lines','split','keys','values','entries'} else state
    cases=examples(text)
    if any(c['name']!=name or len(c['args'])!=1 or c['kwargs'] for c in cases):raise Unclear('Examples must call '+name+' with one input argument.')
    plan=dict(name=name,domain=domain[1].lower(),steps=steps,clauses=clauses,source=source,functions=functions,cases=cases,input=use)
    for value in [c['args'][0] for c in cases]+([] if use is MISSING else [use]):check_input(plan,value)
    return plan


def check_input(plan,value):
    clone(value)
    if plan['domain']=='text':
        if type(value) is not str:raise ValueError('This tool requires a literal text string')
    elif type(value) is not list or any(type(row) is not dict or any(type(k) is not str for k in row) for row in value):raise ValueError('This tool requires a list of records with string field names')


GUARD='''def _cael_data(value, depth=0, count=None):
    if count is None: count=[0]
    count[0]+=1
    if depth>6 or count[0]>800: raise ValueError('Data nesting/item budget exceeded')
    kind=type(value)
    if value is None or kind is bool: return value
    if kind is int:
        if abs(value)>1000000000000: raise ValueError('Integer bound exceeded')
        return value
    if kind is str:
        if len(value)>2048: raise ValueError('Text value exceeds 2048 characters')
        return value
    if kind is list:
        if len(value)>40: raise ValueError('At most 40 list items are supported')
        return [_cael_data(x,depth+1,count) for x in value]
    if kind is dict:
        if len(value)>40: raise ValueError('At most 40 dictionary entries are supported')
        out={}
        for key,item in value.items():
            if type(key) not in (str,int,bool,type(None)): raise ValueError('Unsupported dictionary key')
            out[_cael_data(key,depth+1,count)]=_cael_data(item,depth+1,count)
        return out
    raise ValueError('Unsupported data type')
'''


def compile_plan(plan):
    lines=[f'def {plan["name"]}(data):','    values = _cael_data(data)']
    add=lambda s:lines.append('    '+s)
    if plan['domain']=='text':add("if type(values) is not str: raise ValueError('Expected text')")
    else:
        add("if type(values) is not list: raise ValueError('Expected records')")
        add("if any(type(row) is not dict or any(type(k) is not str for k in row) for row in values): raise ValueError('Expected records with string fields')")
    for s in plan['steps']:
        kind=s.kind;expr=s.helper+'(x)' if s.helper else s.expression
        if kind in {'words','lines','split'}:add('values = values.'+('split()' if kind=='words' else 'splitlines()' if kind=='lines' else 'split('+repr(s.initial)+')'))
        elif kind=='map':add('values = ['+expr+' for x in values]')
        elif kind=='filter':add('values = [x for x in values if '+expr+']')
        elif kind=='select':add('values = [{key: x[key] for key in '+repr(s.initial)+'} for x in values]')
        elif kind=='sort':add('values = sorted(values, key=lambda x: '+expr+', reverse='+repr(s.reverse)+')')
        elif kind in {'first','last'}:add('values = values[:'+str(s.count)+']' if kind=='first' else 'values = values[-'+str(s.count)+':]' if s.count else 'values = []')
        elif kind=='unique':
            for line in ['seen = []','kept = []','for x in values:','    key = '+s.key,'    if key not in seen:','        seen.append(key)','        kept.append(x)','values = kept']:add(line)
        elif kind in {'group','frequency','total','index'}:
            add('mapping = {}');add('for x in values:');add('    key = '+s.key)
            if kind=='group':add('    mapping.setdefault(key, []).append(x)')
            elif kind=='frequency':add('    mapping[key] = mapping.get(key, 0) + 1')
            elif kind=='total':add('    mapping[key] = mapping.get(key, 0) + ('+expr+')')
            elif s.policy=='rejecting duplicates':add("    if key in mapping: raise ValueError('Duplicate index key')");add('    mapping[key] = x')
            elif s.policy=='keeping first':add('    if key not in mapping: mapping[key] = x')
            else:add('    mapping[key] = x')
            add('values = mapping')
        elif kind=='entries':add('values = ['+(s.helper+'(key, value)' if s.helper else expr)+' for key, value in values.items()]')
        elif kind in {'keys','values'}:add('values = list(values.'+kind+'())')
        elif kind=='count':add('values = len(values)')
        elif kind=='sum':add('values = sum('+expr+' for x in values)')
        elif kind=='join':add('values = '+repr(s.initial)+'.join(values)')
        elif kind in {'scan','reduce'}:
            add('state = _cael_data('+repr(s.initial)+')')
            if kind=='scan':add('history = []')
            add('for x in values:');add('    state = _cael_data('+s.helper+'(state, x))')
            if kind=='scan':add('    history.append(_cael_data(state))')
            add('values = history' if kind=='scan' else 'values = state')
        elif kind!='identity':raise Unclear('Unknown internal operation')
        add('values = _cael_data(values)')
    add('return values')
    return (plan['source']+'\n\n' if plan['source'] else '')+GUARD+'\n'+'\n'.join(lines)+'\n'


def interpret(plan,data):
    check_input(plan,data);values=clone(data);machine=Machine(30000);scope=machine.load(plan['source'])
    def calc(expr,**bindings):
        local=Scope(scope);local.values.update(bindings)
        return machine.expr(ast.parse(expr,mode='eval').body,local)
    for s in plan['steps']:
        kind=s.kind
        def value(x):return machine.call(scope.lookup(s.helper),[x],{}) if s.helper else calc(s.expression,x=x)
        if kind in {'words','lines','split'}:values=values.split() if kind=='words' else values.splitlines() if kind=='lines' else values.split(s.initial)
        elif kind=='map':values=[value(x) for x in values]
        elif kind=='filter':values=[x for x in values if value(x)]
        elif kind=='select':values=[{key:x[key] for key in s.initial} for x in values]
        elif kind=='sort':values=sorted(values,key=value,reverse=s.reverse)
        elif kind=='first':values=[x for i,x in enumerate(values) if i<s.count]
        elif kind=='last':values=[x for i,x in enumerate(values) if i>=len(values)-s.count]
        elif kind=='unique':
            seen=[];kept=[]
            for x in values:
                key=calc(s.key,x=x)
                if key not in seen:seen.append(key);kept.append(x)
            values=kept
        elif kind in {'group','frequency','total','index'}:
            mapping={}
            for x in values:
                key=calc(s.key,x=x)
                if kind=='group':
                    if key not in mapping:mapping[key]=[]
                    mapping[key].append(x)
                elif kind=='frequency':mapping[key]=mapping[key]+1 if key in mapping else 1
                elif kind=='total':mapping[key]=(mapping[key] if key in mapping else 0)+value(x)
                elif key in mapping:
                    if s.policy=='rejecting duplicates':raise ValueError('Duplicate index key')
                    if s.policy=='keeping last':mapping[key]=x
                else:mapping[key]=x
            values=mapping
        elif kind=='entries':values=[machine.call(scope.lookup(s.helper),[key,val],{}) if s.helper else calc(s.expression,key=key,value=val) for key,val in values.items()]
        elif kind=='keys':values=list(values)
        elif kind=='values':values=[values[key] for key in values]
        elif kind=='sum':values=sum(value(x) for x in values)
        elif kind=='count':values=len(values)
        elif kind=='join':values=s.initial.join(values)
        elif kind in {'scan','reduce'}:
            state=clone(s.initial);history=[]
            for x in values:
                state=clone(machine.call(scope.lookup(s.helper),[state,x],{}));history.append(clone(state))
            values=history if kind=='scan' else state
        values=clone(values)
    if machine.tainted:machine.fail('Unsupported helper semantics')
    return values


def build(plan):
    probes=['',' A  b\nA ', 'a\r\nb\n'] if plan['domain']=='text' else [[],[{}],[{'name':'A','amount':2,'active':True}]]
    inputs=probes+[c['args'][0] for c in plan['cases']]+([] if plan['input'] is MISSING else [plan['input']])
    expected=[outcome(lambda x=x:interpret(plan,x)) for x in inputs]
    if any(r['status'] in {'limit','unsupported'} for r in expected):return dict(status='unsupported',message='A helper/expression exceeded the supported interpreter or resource budget. No successful data tool was built.')
    source=compile_plan(plan);actual=run_cases(source,[dict(name=plan['name'],args=[x]) for x in inputs],steps=160000)
    if actual['status']!='ok' or len(actual.get('cases',[]))!=len(inputs):return dict(status='unsupported',message='The generated tool exceeds the AST/interpreter budget.')
    for wanted,got in zip(expected,actual['cases']):
        if wanted['status']!=got['status'] or (not same(wanted.get('value'),got.get('value')) if wanted['status']=='value' else wanted.get('error')!=got.get('error')):return dict(status='verification-failed',message='The generated code disagrees with its data plan. No successful tool is claimed.')
    for c,wanted in zip(plan['cases'],expected[len(probes):]):
        if wanted['status']!='value' or not same(wanted.get('value'),c['expected']):return dict(status='contradiction',message='The data plan disagrees with a supplied expected result. Clarify the steps or expected value; no successful tool was emitted.')
    if plan['input'] is not MISSING and expected[-1]['status']!='value':return dict(status='execution-error',message='The requested data task raises '+expected[-1].get('error','an error')+'. No completed result is claimed.')
    # A collection of errors alone does not establish a usable tool.
    if not any(r['status']=='value' for r in expected):return dict(status='needs-example',message='The plan only raised errors on available checks. Supply a valid input or expected example before a usable tool is claimed.')
    return dict(status='built',source=source,value=expected[-1].get('value') if plan['input'] is not MISSING else None,probes=len(probes),probe_errors=sum(r['status']=='error' for r in expected[:len(probes)]))


def reply(text,messages=None):
    request=text;follow=False;override=None
    if messages and len(messages)>=3 and APPLY.fullmatch(text.strip()) and messages[-2].get('role')=='assistant' and messages[-2].get('content','').startswith((PREFIX,USED)):
        for i in range(len(messages)-3,max(-1,len(messages)-10),-2):
            old=messages[i]
            if old.get('role')!='user':break
            if ASK.search(old.get('content','')):request=old['content'];follow=True;override=APPLY.fullmatch(text.strip())[1];break
            if i<1 or not messages[i-1].get('content','').startswith((PREFIX,USED)):break
    details=('Non-neural record/text plan compiler with bounded Python AST execution. Ordered expression/helper composition, value-oriented input copies and snapshot scans. '
             '40 list/dictionary entries, depth 6, 800 data nodes, strings up to 2048 characters and integers within ±1e12. '
             'No native user-code execution, external access or tool installation. Plan probes check compilation consistency, not general Python understanding or proof of user intent.')
    out=lambda response,suffix:dict(response=response,route='chat/code-data-tool-'+suffix,sources=[],details=details)
    try:
        plan=parse(request)
        if plan is None:return None
        if follow:plan['input']=literal(override);check_input(plan,plan['input'])
        result=build(plan)
    except (Unclear,ValueError,TypeError) as error:return out(str(error),'clarify')
    except (Unsupported,SyntaxError,RecursionError):return out('That data tool is outside the bounded grammar/interpreter. No successful tool is claimed.','unsupported')
    if result['status']!='built':return out(result['message'],result['status'])
    if follow:return out(USED+'`'+plan['name']+'`:\n```text\n'+repr(result['value'])+'\n```\nReconstructed from this conversation and checked in the bounded interpreter.','used')
    lines=[PREFIX+'`'+plan['name']+'`.', 'Plan: '+' → '.join(plan['clauses'])+'.','```python\n'+result['source']+'```',
           'Checked generated code against the plan on '+str(result['probes'])+' probes ('+str(result['probe_errors'])+' raised errors) and '+str(len(plan['cases']))+' supplied examples. '
           'These are bounded checks, not a correctness proof. The tool copies input values; scan outputs are independent state snapshots. No executable tool was installed.']
    if plan['input'] is not MISSING:lines.append('Used on supplied data:\n```text\n'+repr(result['value'])+'\n```')
    else:lines.append('Reply Use it on followed by a literal string or record list to use this tool here.')
    return out('\n\n'.join(lines),'built')
