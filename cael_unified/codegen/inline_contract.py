"""Complete inline return contracts through the existing stub/AST VM compiler.

The original signature, defaults and keyword rules remain authoritative.
Extra clauses/examples are never silently discarded. This is a finite explicit
expression compiler, not arbitrary algorithm understanding or native execution.
"""
import ast
import re
from . import signature_contract as checked

def reply(text):
 if len(text)>10000 or '```' in text:return None
 hit=re.match(r'(?is)^\s*(?:please\s+)?(?:write|implement|create|build)\s+(?:an?\s+)?(?:Python\s+)?function\s+([A-Za-z_]\w*)\s*\(([^()\n]{0,240})\)\s+(.+)$',text)
 if not hit:return None
 name,signature,tail=hit.groups()
 def unclear(message):return dict(route='chat/code-inline-clarify',response=message,sources=[],details='The explicit signature remains the contract. No native execution or inferred name/argument repair.')
 try:
  parts=re.split(r'(?i)\bexamples?\s*:\s*',tail)
  if len(parts)>2:raise checked.Unclear('Use one explicit Examples section; no trailing requirement was discarded.')
  behavior=re.fullmatch(r'(?is)(?:that\s+)?returns?\s+(.+?)\s*[.]?\s*',parts[0].strip())
  if not behavior:raise checked.Unclear('I can preserve this signature for an explicit return expression. Put the complete behavior in a return expression or a declarative function docstring.')
  tree=ast.parse('def '+name+'('+signature+'):\n    pass\n');stub=tree.body[0]
  doc='Return '+behavior[1].rstrip('.')+'.'
  if len(parts)==2:
   chunks=[c.strip() for c in re.split(r'[;\n]+',parts[1]) if c.strip()]
   if not 1<=len(chunks)<=16:raise checked.Unclear('Supply one to sixteen complete literal equality examples.')
   for chunk in chunks:
    node=ast.parse(chunk.rstrip('.'),mode='eval').body
    if not isinstance(node,ast.Compare) or len(node.ops)!=1 or not isinstance(node.ops[0],ast.Eq):raise checked.Unclear('Every inline example must be a complete function call == literal result.')
    call=node.left
    if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Name) or call.func.id!=name:raise checked.Unclear('All examples must call the declared function directly.')
    checked.bind(stub,call)
    expected=ast.literal_eval(node.comparators[0]);checked.Machine().bounded(expected)
    doc+='\n>>> '+ast.unparse(call)+'\n'+repr(expected)
  stub.body=[ast.Expr(value=ast.Constant(value=doc)),ast.Pass()]
  source=ast.unparse(ast.fix_missing_locations(tree))
  result=checked.reply('Implement:\n```python\n'+source+'\n```')
  if result is None:raise checked.Unclear('The full signature could not be represented by the checked contract compiler.')
  result['inline_contract']={'complete_request':text,'signature_preserved':True,'same_bounded_vm':True}
  return result
 except (checked.Unclear,ValueError,TypeError,SyntaxError,RecursionError,checked.Unsupported) as error:
  return unclear('I could not verify the complete inline contract: '+str(error))
