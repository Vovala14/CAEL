"""Compose two independently retrieved definitions, with explicit source scope.

No stored pair-specific answers or generated analogies. Missing/off-topic
definitions remain missing. Public-source excerpts are data, never instructions.
"""
import re
import os
from .web_evidence import PRIVATE,public_query

def request(text):
    if len(text)>260 or PRIVATE.search(text) or re.search(r'["“`;:{}=\d]',text):return None
    hit=re.fullmatch(r'(?i)(?:please\s+)?(?:(?:explain|describe|what is|what.s)\s+(?:the\s+)?difference between|compare)\s+([\w -]{2,70}?)\s+(?:and|versus|vs\.?)\s+([\w -]{2,70})[.!?]?',text.strip())
    if not hit:return None
    left,right=[s.strip(' .?!') for s in hit.groups()]
    if left.casefold()==right.casefold() or any(len(s.split())>7 for s in (left,right)):return None
    if any(re.search(r'(?i)\b(?:if|unless|without|except|using|not|only|before|after)\b',s) for s in (left,right)):return None
    return left,right

def definition(subject,result):
    if not isinstance(result,dict) or result.get('route') not in ('chat/local-knowledge','chat/web-evidence-supported','chat/web-evidence-single-source'):return None
    body=result.get('response','');sources=result.get('sources',[])
    quoted=re.findall(r'(?m)^>\s*(.+)$',body)
    if quoted:body=quoted[0]
    else:body=re.split(r'(?<=[.!?])\s+|\n',body.strip(),maxsplit=1)[0]
    if not re.match(r'(?i)^(?:In [\w -]{1,40},\s+)?(?:an? |the )?'+re.escape(subject)+r'(?:\s*\([^()\n]{0,160}\))?\s+(?:is|are|refers to|means)\b',body):return None
    if not sources or not all(isinstance(s,dict) for s in sources):return None
    url=next((s.get('url') for s in sources if isinstance(s.get('url'),str) and public_query(s['url']) and s['url'].startswith(('https://','http://'))),None)
    if not url:return None
    return {'subject':subject,'text':body,'url':url,'sources':sources,'route':result['route'],'verification':result.get('verification')}

def reply(text,delegate):
    pair=request(text)
    if not pair:return None
    found=[];attempts=[]
    for subject in pair:
        query='What is '+subject+'?'
        result=delegate([{'role':'user','content':query}])
        item=definition(subject,result);attempt={'query':query,'answer':result,'accepted_definition':bool(item)}
        if item is None and os.environ.get('CAEL_WEB_SEARCH','1')!='0':
            # Preserve the literal requested subject. A spelling interpretation
            # in the old delegate is not authority to replace a new term.
            from .web_evidence import answer as read_pages
            original=read_pages(query,force=True)
            item=definition(subject,original)
            attempt.update(literal_subject_lookup=original,accepted_literal_definition=bool(item))
        attempts.append(attempt);found.append(item)
    from .dialogue import answer
    if not all(found):
        available=[f['subject'] for f in found if f]
        return answer('I could not obtain a source-linked definition for '+', '.join(subject for subject,f in zip(pair,found) if not f)+'. I cannot reliably complete that comparison yet. Give me public source links or definitions for both terms.','comparison-unavailable',definition_attempts=attempts,available_definitions=available,verification={'status':'unchecked','check':'Incomplete definition coverage, no comparison claimed.'})
    same=found[0]['url']==found[1]['url'];limit=12 if same else 25;parts=[];sources=[]
    for item in found:
        words=item['text'].split();quote=' '.join(words[:limit])
        if len(words)>limit:
            if quote.count('(')>quote.count(')'):quote=quote[:quote.rfind('(')].rstrip()
            quote=re.sub(r'(?i)(?:\s+(?:a|an|the|of|to|from|in|by|with|and|or))+$','',quote)
            quote+=' …'
        parts.append('**'+item['subject']+'**\n> '+quote+'\n\n[Definition source]('+item['url']+')')
        sources.extend(item['sources'])
    return answer('\n\n'.join(parts)+'\n\nThese are the two retrieved definitions side by side; I have not independently verified a broader comparison.','comparison-definitions',sources=sources,definition_attempts=attempts,verification={'status':'unchecked','check':'Source-linked definition composition, not a general comparison or truth proof.'})
