"""Read complete literal equality examples, preserving kwargs/default contracts.

Used by the inline compiler and independent checker. Only AST/literal parsing;
no evaluated calls. Incomplete/extra clauses fail rather than dropping a case.
"""
import ast
import re

class Unclear(ValueError):pass

def parse_section(text,name):
    chunks=[c.strip() for c in re.split(r'[;\n]+',text) if c.strip()]
    if not 1<=len(chunks)<=32:raise Unclear('Use one to thirty-two complete literal equality examples.')
    cases=[]
    for chunk in chunks:
        chunk=re.sub(r'(?i)^(?:assert\s+|>>>\s*)','',chunk).rstrip('.')
        node=ast.parse(chunk,mode='eval').body
        if not isinstance(node,ast.Compare) or len(node.ops)!=1 or not isinstance(node.ops[0],ast.Eq):raise Unclear('An example is not a complete call == literal result.')
        call=node.left
        if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Name) or call.func.id!=name or any(k.arg is None for k in call.keywords):raise Unclear('An example must call the declared function directly without argument expansion.')
        args=[ast.literal_eval(a) for a in call.args];kwargs={k.arg:ast.literal_eval(k.value) for k in call.keywords}
        if len(kwargs)!=len(call.keywords):raise Unclear('An example repeats a keyword.')
        expected=ast.literal_eval(node.comparators[0])
        from .python_vm import Machine
        for value in [*args,*kwargs.values(),expected]:Machine().bounded(value)
        cases.append((dict(name=name,args=args,kwargs=kwargs),expected))
    return cases

def from_request(text,name):
    parts=re.split(r'(?i)\bexamples?\s*:\s*',text)
    if len(parts)>2:raise Unclear('More than one Examples section needs clarification.')
    return None if len(parts)==1 else parse_section(parts[1],name)
