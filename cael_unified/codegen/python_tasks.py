"""Build, check and use a pure Python data tool from a bounded task request.

This reads explicit operation semantics, not arbitrary natural language. The
existing integer/record/text compilers emit a new function and check it against
their plan interpreters. No native execution, installation or global tool cache.
"""
import re

from . import data_tools,task_tools
from .tool_contract import attach
from .python_vm import Unsupported

PREFIX='Python task result:'
SOURCE='Python task source:'
USE=re.compile(r'(?is)^\s*(?:use|run|apply)(?: it| this tool| the tool)? (?:on|with)\s+(.+?)\s*$')
SHOW=re.compile(r'(?i)^\s*(?:show|explain) (?:the |your )?(?:python )?(?:tool|source|code)\s*[?.!]*$')
HEAD=re.compile(r'(?is)^\s*(?:please\s+)?use python(?: if needed)?(?: for (numbers|records|text))? to\s+(.+?)\s*$')
NATURAL=re.compile(r'(?is)^\s*(?:(?:calculate|find|compute)\s+)?(?:the )?(sum|product) of (?:the )?(squares|cubes|absolute values) of (positive|negative|nonnegative|nonzero|even|odd) (?:numbers|integers|values) in\s+(.+?)\s*$')


def active_request(text,messages):
    if not (USE.fullmatch(text) or SHOW.fullmatch(text)):return None
    history=messages or []
    if len(history)<3 or history[-2].get('role')!='assistant' or not history[-2].get('content','').startswith((PREFIX,SOURCE)):
        return None
    for i in range(len(history)-3,max(-1,len(history)-13),-2):
        old=history[i]
        if old.get('role')!='user':break
        if HEAD.fullmatch(old.get('content','')) or NATURAL.fullmatch(old.get('content','')):return old['content']
        if i<1 or not history[i-1].get('content','').startswith((PREFIX,SOURCE)):break
    return None


def owns(text,messages=None):
    return bool(HEAD.fullmatch(text) or NATURAL.fullmatch(text) or active_request(text,messages))


def structured_request(text):
    heading=text.split('\n',1)[0]
    return bool(re.match(r'(?i)^\s*(?:build|write|create|make|implement)\b',heading)
                and task_tools.ASK.search(heading) and re.search(r'(?im)^\s*steps?\s*:',text))


def protect_input(text,messages=None):
    if owns(text,messages) or structured_request(text):return True
    return bool(USE.fullmatch(text) and messages and len(messages)>=3 and messages[-2].get('role')=='assistant'
                and messages[-2].get('content','').startswith((task_tools.PREFIX,task_tools.USE_PREFIX,data_tools.PREFIX,data_tools.USED)))


def clauses(text):
    from ..orchestrator import protected_spans,unprotected
    spans=protected_spans(text);depth=0;parts=[];start=0
    pattern=r'[\[\]{}()]|\s*(?:;|\n|,?\s+(?:and\s+)?then\s+|,\s+(?=keep|map|square|sum|count|sort|return|reverse))\s*'
    for m in re.finditer(pattern,text,flags=re.I):
        if not unprotected(text,m,spans):continue
        if m[0] in ('[','{','('):depth+=1
        elif m[0] in (']','}',')'):depth-=1
        elif depth==0:
            part=text[start:m.start()].strip().rstrip('.')
            if part:parts.append(part)
            start=m.end()
    part=text[start:].strip().rstrip('.')
    if part:parts.append(part)
    if not 1<=len(parts)<=8:raise ValueError('Use one to eight explicit data operations.')
    return parts


def prepare(text,override=None):
    if len(text)>10000 or '```' in text:raise ValueError('Use a short pure-data task with literal input; no executable source blocks.')
    natural=NATURAL.fullmatch(text)
    if natural:
        reducer,transform,selection,raw=natural.groups()
        parts=['keep '+selection+' values',{'squares':'square each value','cubes':'map x**3','absolute values':'map abs(x)'}[transform.lower()],reducer.lower()]
        domain='numbers'
    else:
        markers=list(re.finditer(r'(?im)^\s*input\s*:\s*',text))
        if len(markers)!=1:raise ValueError('Provide one Input: line containing a literal list of numbers, records, or a quoted string.')
        head=HEAD.fullmatch(text[:markers[0].start()])
        if not head:raise ValueError('Start with Use Python to followed by the ordered operations.')
        domain,operations=head.groups();raw=text[markers[0].end():].strip()
        parts=clauses(operations)
    data=data_tools.literal(override if override is not None else raw)
    if domain is None:
        domain='text' if type(data) is str else 'records' if type(data) is list and data and all(type(r) is dict for r in data) else 'numbers'
    domain=domain.lower()
    compiler=task_tools if domain=='numbers' else data_tools
    # Only literals and parsed operation clauses enter the existing compilers.
    heading='integer lists' if domain=='numbers' else domain
    request='Build a Python tool named process_task for '+heading+'.\nSteps:\n'+'\n'.join(parts)+'\nUse it on '+repr(data)
    plan=compiler.parse(request)
    if plan is None:raise ValueError('Unsupported data domain for this task.')
    result=compiler.build(plan)
    return domain,parts,plan,result


def reply(text,messages=None):
    previous=active_request(text,messages)
    if not owns(text,messages):return None
    request=previous or text
    applied=USE.fullmatch(text) if previous else None
    out=lambda response,suffix,details='':dict(route='chat/code-python-task-'+suffix,response=response,sources=[],details=details)
    try:
        domain,parts,plan,result=prepare(request,applied[1] if applied else None)
    except Unsupported:
        return out('That task exceeded the supported compiler/interpreter or resource budget. No completed result is claimed.','unsupported')
    except (ValueError,TypeError,SyntaxError,RecursionError) as error:
        return out(str(error),'clarify','No tool was built or run. Data operations are limited to the existing bounded compilers.')
    if result['status']!='built':return out(result['message'],result['status'])
    source=result['source'];checks=dict(probes=result['probes'],examples=len(plan['cases']))
    details=('Constructed a fresh Python function from the ordered '+domain+' plan: '+' → '.join(parts)+'. '
        'Checked emitted code against the plan interpreter and ran the supplied data in the bounded Python VM. '
        'These checks establish compiler/plan agreement, not general correctness or understanding of arbitrary prose. '
        'No file/network access, external model, native execution, installation or global tool memory.\n\nGenerated source:\n'+source)
    show_source=bool(previous and SHOW.fullmatch(text))
    if show_source:
        response=SOURCE+'\n```python\n'+source+'```\nPlan: '+' → '.join(parts)+'.'
    else:
        response=PREFIX+'\n```text\n'+repr(result['value'])+'\n```\nUsed a generated `process_task` helper, checked against the ordered plan. '
        'You can ask “show the tool” or use it on another input.'
    return attach(out(response,'source' if show_source else 'used',details),plan['name'],source,domain,checks,not show_source,result['value'])
