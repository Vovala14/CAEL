"""Finite option references and exact user-supplied price conditions.

Only explicit complete clauses are read. Unknown prices/currencies/conditions
clarify, rather than inventing a cheaper option or assuming an alternative.
"""
from fractions import Fraction
import re

ORDINALS=dict(zip('first second third fourth fifth sixth seventh eighth ninth tenth'.split(),range(10)))
CARDINALS=dict(zip('one two three four five six seven eight nine ten'.split(),range(10)))

def reference(text,options):
    value=' '.join(text.casefold().strip(' .!?').split())
    value=re.sub(r'^(?:the\s+)?(?:option|choice|number)\s+|^the\s+','',value)
    value=re.sub(r'\s+(?:one|option|choice)$','',value)
    if value in ORDINALS:index=ORDINALS[value]
    elif value in CARDINALS:index=CARDINALS[value]
    elif re.fullmatch(r'\d{1,2}',value):index=int(value)-1
    else:
        named=[i for i,o in enumerate(options) if re.sub(r'^(?:a|an|the)\s+','',o.casefold())==re.sub(r'^(?:a|an|the)\s+','',value)]
        return named[0] if len(named)==1 else None
    return index if 0<=index<len(options) else -1

def selection(text,options):
    text=text.strip(' .!?').replace('’',"'")
    hit=re.fullmatch(r"(?i)(?:(?:i|we)(?:'ll| will| would like to)?\s+|let(?: us|'s)\s+)?(?:choose|chose|pick|picked|select|selected|prefer|take|use|go with|go for|settle on)\s+(.+)",text)
    if hit:return reference(hit[1],options)
    if re.fullmatch(r'(?i)(?:the )?(?:option|number|choice)\s+\w+|(?:the )?(?:'+ '|'.join(ORDINALS)+r')(?: option| one| choice)?',text):return reference(text,options)
    return None

def condition(text,options):
    split=re.split(r'(?i)\s*,?\s*\b(unless|only if|if|provided that)\b\s*',text,maxsplit=1)
    if len(split)!=3:return None
    base=selection(split[0],options)
    if base is None:return None
    result={'base':base,'operator':split[1].casefold(),'text':split[2].strip(' .!?'),'supported':False}
    otherwise=re.split(r'(?i)\s*[,;]?\s*\botherwise\b\s*',result['text'])
    if len(otherwise)>2:return result
    clause=otherwise[0]
    if len(otherwise)==2:
        fallback=selection(otherwise[1],options)
        if fallback is None or fallback<0:return result
        result['otherwise']=fallback
    relation=re.fullmatch(r'(?i)(.+?)\s+(?:is|costs)\s+(?:cheaper|less expensive|less)(?:\s+than\s+(.+))?',clause)
    if not relation:return result
    left=base if relation[1].casefold()=='it' else reference(relation[1],options)
    right=reference(relation[2],options) if relation[2] else base
    if left is None or right is None or min(base,left,right)<0 or left==right:return result
    result.update(left=left,right=right,supported=True)
    return result

def prices(text,options):
    chunks=re.split(r'\s*;\s*|\.\s+',text.strip(' .!?'))
    found={}
    for chunk in chunks:
        hit=re.fullmatch(r'(?i)(.+?)\s+costs?\s+([0-9]{1,7}(?:\.[0-9]{1,4})?)\s+(dollars?|euros?|pounds?|USD|EUR|GBP)',chunk)
        if not hit:return None
        index=reference(hit[1],options)
        if index is None or index<0 or index in found:return None
        unit=hit[3].casefold().rstrip('s');found[index]={'value':Fraction(hit[2]),'unit':unit}
    return found or None

def update(task,text):
    opts=task['options'];text=text.strip().replace('’',"'")
    guarded=condition(text,opts)
    if guarded is not None:
        task['selection_condition']=guarded;task.pop('selected',None);task.pop('selection_unsupported',None);return True
    index=selection(text,opts)
    if index is not None:
        if index<0:task['selection_unsupported']=True;task.pop('selected',None)
        else:
            task['selected']=opts[index]
            for key in ('selection_unsupported','selection_condition','pricing_unsupported','selection_reason'):task.pop(key,None)
        return True
    amounts=prices(text,opts)
    if amounts:
        task.setdefault('prices',{}).update(amounts);task.setdefault('price_sources',[]).append(text);task.pop('pricing_unsupported',None);return True
    if re.search(r'(?i)\b(?:choose|pick|take|select|go with)\b',text) and re.search(r'(?i)\b(?:not|but|unless|only if|provided|if)\b',text):
        task['selection_unsupported']=True;task.pop('selected',None);return True
    if re.search(r'(?i)\b(?:cost|costs|price)\b',text):task['pricing_unsupported']=True;return True
    return False

def resolve(task):
    if task.get('pricing_unsupported'):return 'I could not read the full price statement. Give one explicit amount and currency for each option; no price was guessed.'
    guard=task.get('selection_condition')
    if not guard:return None
    if not guard['supported']:return 'I cannot resolve that complete condition yet: '+guard['text']+'. State the missing facts or choose an option unconditionally.'
    amounts=task.get('prices',{});left=amounts.get(guard['left']);right=amounts.get(guard['right'])
    if left is None or right is None:return 'Your choice depends on this condition: '+guard['text']+'. Give the prices and currencies for both compared options before I choose.'
    if left['unit']!=right['unit']:return 'The stated prices use different currencies. I need comparable amounts in the same currency; I have not assumed an exchange rate.'
    less=left['value']<right['value'];allowed=not less if guard['operator']=='unless' else less
    selected=guard['base'] if allowed else guard.get('otherwise')
    proof=str(left['value'])+' '+left['unit']+(' < ' if less else ' >= ')+str(right['value'])+' '+right['unit']
    if selected is None:return 'The condition blocks the requested option ('+proof+'). You have not specified an alternative; which option should I use?'
    task['selected']=task['options'][selected];task['selection_reason']='Using your stated prices, '+proof+'. '
    return None
