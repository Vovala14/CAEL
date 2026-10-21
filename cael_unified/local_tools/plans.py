"""Allowlisted capability plans and Python emission; runner never uses exec."""
import ast
import json
import keyword
import re

from .workspace import ToolError,Workspace


def validate(plan):
    if not isinstance(plan,dict) or set(plan)-{'name','steps'}:raise ToolError('Invalid local capability plan')
    name=plan.get('name','local_tool')
    if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,59}',name) or keyword.iskeyword(name):raise ToolError('Choose a public Python tool name')
    steps=plan.get('steps')
    if not isinstance(steps,list) or not 1<=len(steps)<=8:raise ToolError('Use 1..8 local steps')
    found=False
    for step in steps:
        if not isinstance(step,dict):raise ToolError('Invalid capability step')
        op=step.get('op');allowed={'find':{'op','pattern'},'touch':{'op','path'},'read':{'op','path'},'pdf':{'op','path','query'},
             'inspect':{'op','path'},'enqueue':{'op','path','upload_ref'},'read_found':{'op'},'pdf_found':{'op'},'enqueue_found':{'op'}}
        if op not in allowed or set(step)-allowed[op]:raise ToolError('Unsupported local operation')
        if op.endswith('_found') and not found:raise ToolError('Find files before processing matching files')
        if op=='find':
            if not isinstance(step.get('pattern'),str):raise ToolError('Find requires a literal glob')
            Workspace.pattern(step['pattern'])
            found=True
        elif op not in {'read_found','pdf_found','enqueue_found'}:
            if not isinstance(step.get('path'),str):raise ToolError('Use a literal relative path')
            Workspace.relative(step['path'])
        if 'query' in step and (not isinstance(step['query'],str) or not 1<=len(step['query'])<=500):raise ToolError('Use a PDF query of 1..500 characters')
        if 'upload_ref' in step and (not isinstance(step['upload_ref'],str) or not 1<=len(step['upload_ref'])<=200):raise ToolError('Invalid upload reference')
    return dict(name=name,steps=steps)


def execute(workspace,plan):
    plan=validate(plan);results=[];found=[]
    for step in plan['steps']:
        if 'path' in step:workspace.path(step['path'],existing=False)
    # Only explicitly requested capabilities run, not the displayed Python.
    from .review import ReviewQueue
    from .pdf_tools import search
    queue=None
    def one(operation,path,step):
        nonlocal queue
        if operation=='touch':return workspace.touch(path)
        if operation=='read':return workspace.read(path)
        if operation=='pdf':
            document=workspace.pdf(path)
            return dict(path=path,document=document,evidence=search(document,step['query'])) if step.get('query') else dict(path=path,document=document)
        if operation=='inspect':return dict(path=path,assessment=workspace.inspect_media(path))
        if operation=='enqueue':
            if queue is None:queue=ReviewQueue(workspace)
            return queue.enqueue(path,step.get('upload_ref'))
        raise ToolError('Unknown operation')
    for step in plan['steps']:
        op=step['op']
        if op=='find':
            listing=workspace.find(step['pattern'],limit=20);found=[r['path'] for r in listing['files']];results.append(listing)
        elif op.endswith('_found'):
            for path in found:results.append(one(op.removesuffix('_found'),path,step))
        else:results.append(one(op,step['path'],step))
        # Bound aggregate output. Touch/queue effects already executed remain
        # recorded; a plan is sequential and is not an atomic transaction.
        if len(json.dumps(results))>1_000_000:raise ToolError('Aggregate tool output limit; earlier steps may have completed')
    return dict(status='completed',results=results,atomic=False)


def emit(plan):
    plan=validate(plan)
    # A caller must explicitly supply Workspace authority to the generated tool.
    source='def '+plan['name']+'(workspace):\n    return workspace.run_plan('+repr(plan)+')\n'
    ast.parse(source);return source
