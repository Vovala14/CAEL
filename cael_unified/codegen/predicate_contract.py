"""Whole-description integer parity/bounds contracts; unsupported clauses clarify.

This is a finite symbolic reader, not arbitrary Python/English understanding.
Generated functions are checked only in the existing bounded AST interpreter.
"""
import keyword
import operator
import re

from .python_vm import run_cases

START = re.compile(r"(?is)^\s*(?:please\s+)?(?:(do not|don['’]t|never)\s+)?"
                   r"(?:write|build|create|make|implement|generate|give me)\s+(?:me\s+)?(?:an?\s+)?(?:python\s+)?function\b")
HEADER = re.compile(r"(?is)^\s*(?:please\s+)?(?:write|build|create|make|implement|generate|give me)\s+"
                    r"(?:me\s+)?(?:an?\s+)?(?:python\s+)?function(?:\s+(?:named|called)\s+(.+?))?\s+"
                    r"(?:that|which|to)\s+(.+?)\s*$")
PARITY = re.compile(r"(?is)^(?:(?:tests?|checks?|determines?)\s+(?:whether|if)|returns?\s+true\s+(?:if|when))\s+"
                    r"(?:(?:a|an|the)\s+)?(?:number|integer|n)\s+is\s+(not\s+)?(even(?:ness)?|odd(?:ness)?)(.*)$")
OPS = {'<':operator.lt, '<=':operator.le, '>':operator.gt, '>=':operator.ge, '==':operator.eq, '!=':operator.ne}
OPPOSITE = {'<':'>=', '<=':'>', '>':'<=', '>=':'<', '==':'!=', '!=':'=='}
RELATIONS = {
    'greater than':'>', 'bigger than':'>', 'larger than':'>', 'more than':'>',
    'less than':'<', 'smaller than':'<', 'lower than':'<',
    'not greater than':'<=', 'not bigger than':'<=', 'not larger than':'<=', 'not more than':'<=',
    'no greater than':'<=', 'no bigger than':'<=', 'no more than':'<=', 'at most':'<=',
    'not less than':'>=', 'not smaller than':'>=', 'not lower than':'>=', 'at least':'>=',
    'greater than or equal to':'>=', 'less than or equal to':'<=', 'equal to':'==', 'not equal to':'!=',
}

class Unclear(ValueError):
    pass

def comparison(text):
    value=' '.join(text.lower().split()).strip()
    value=re.sub(r'^(?:(?:the|a|an) (?:number|integer)|n|it)\s+', '', value)
    value=re.sub(r'^is\s+', '', value)
    match=re.fullmatch(r'(<=|>=|==|!=|<|>)\s*(-?\d{1,12})', value)
    if match:return match[1],int(match[2])
    match=re.fullmatch(r'(.+?)\s+(-?\d{1,12})',value)
    if match and match[1] in RELATIONS:return RELATIONS[match[1]],int(match[2])
    raise Unclear('I cannot read the whole additional condition. Give an integer comparison or a contrasting example; I will not drop it.')

def function_name(raw, default):
    if raw is None:return default
    value=raw.strip()
    quotes={'`':'`', "'":"'", '"':'"', '‘':'’', '“':'”'}
    if value[:1] in quotes:
        if len(value)<2 or value[-1]!=quotes[value[0]]:raise Unclear('The function name has unmatched quotation marks.')
        value=value[1:-1]
    if not value.isidentifier() or keyword.iskeyword(value):
        raise Unclear('The requested function name is not a Python identifier. Replace the placeholder with the exact valid name you want; I will not silently rename it.')
    return value

def reply(text):
    if not isinstance(text,str) or '```' in text or re.search(r'(?m)^\s*(?:async\s+)?def\s+\w+\s*\(',text):return None
    start=START.match(text)
    if not start:return None
    out=lambda response,kind,**extra:dict(response=response,route='chat/code-'+kind,sources=[],**extra)
    if start[1]:
        return out('Okay, I will not generate that function.', 'request-declined',
                   details='The creation request was explicitly negated; no code was emitted.')
    if not re.search(r'(?i)\b(?:even(?:ness)?|odd(?:ness)?)\b',text) or not re.search(r'(?i)\b(?:tests?|checks?|determines?|returns?)\b',text):return None
    try:
        if len(text)>1800 or '\n' in text:raise Unclear('This single-function predicate reader needs one complete description within its size limit. Extra text was not discarded.')
        header=HEADER.fullmatch(text.strip().rstrip('.!'))
        if not header:raise Unclear('State one function name and its complete integer predicate; I cannot safely reduce this request to a simpler recipe.')
        predicate=PARITY.fullmatch(header[2])
        if not predicate:raise Unclear('I cannot read the complete predicate. Please state the integer parity and every condition explicitly; I will not emit a keyword-only guess.')
        bit=int(predicate[2].lower().startswith('odd')) ^ bool(predicate[1])
        name=function_name(header[1],'is_odd' if bit else 'is_even')
        tail=predicate[3].strip();bounds=[]
        if tail:
            if re.match(r'(?i)^and\s+',tail):
                clauses=re.split(r'(?i)\s+and\s+',re.sub(r'(?i)^and\s+','',tail))
                if len(clauses)>4:raise Unclear('There are too many additional clauses for this bounded predicate reader.')
                bounds=[comparison(clause) for clause in clauses]
            else:
                exception=re.fullmatch(r'(?is),?\s*(?:but|however)\s*,?\s*returns?\s+false\s+if\s+(.+)',tail)
                if not exception:raise Unclear('The extra rule is outside the supported predicate grammar. I will not emit code that drops it.')
                op,value=comparison(exception[1]);bounds=[(OPPOSITE[op],value)]
        expression='n % 2 '+('!= 0' if bit else '== 0')
        expression+=''.join(' and n '+op+' '+str(value) for op,value in bounds)
        code='def '+name+'(n):\n    return '+expression+'\n'
        probes={-5,-1,0,1,2,9,10,99,100}
        for _,value in bounds:probes.update((value-1,value,value+1))
        probes=sorted(probes)
        checked=run_cases(code,[dict(name=name,args=[value]) for value in probes])
        expected=[(value%2!=0)==bool(bit) and all(OPS[op](value,limit) for op,limit in bounds) for value in probes]
        if len(checked['cases'])!=len(probes) or not all(row.get('status')=='value' and row.get('value') is answer for row,answer in zip(checked['cases'],expected)):
            raise Unclear('The complete predicate did not pass the bounded interpreter checks; no code was emitted.')
        return out('```python\n'+code+'```\nAssumes integer input. The return expression includes every stated parity and range condition.',
                   'predicate-contract',details='Whole finite integer-predicate grammar; checked '+str(len(probes))+
                   ' integer/boundary cases with the existing bounded AST VM. No native generated-code execution or unparsed clause fallback.',
                   predicate_contract=dict(parity='odd' if bit else 'even',bounds=[dict(operator=op,value=value) for op,value in bounds],
                                           complete_description=header[2],vm_checks=len(probes),all_clauses_consumed=True))
    except Unclear as error:
        return out(str(error),'contract-clarify',details='No function emitted because the complete requested name or predicate was not established.')
