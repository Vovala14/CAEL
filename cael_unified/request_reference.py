"""Typed visible-request references for rechecks and scalar projections.

No hidden session cache; no incidental-number extraction or public search of
private facts. A new substantive request stops traversal to an older task.
"""
import re
from .turn_instructions import read

def anchor(messages):
    from .dialogue import arithmetic,act,ACTS,PRIVATE
    from .dialogue_state import read_writing,goal_task
    from . import web_search
    for index in range(len(messages)-1,-1,-1):
        message=messages[index]
        if message['role']!='user':continue
        text=message['content']
        calculated=arithmetic(text)
        if calculated is not None:return {'kind':'arithmetic','question':text,'index':index,'checked':calculated}
        if re.search(r'(?i)\b(?:write|implement|create|build|complete|fix|repair)\b.*\b(?:function|code|program|script)\b|```python',text):
            code=next((m['content'] for m in reversed(messages[index+1:]) if m['role']=='assistant' and '```python' in m['content']),None)
            return {'kind':'code','question':text,'index':index,'code':code}
        # Concrete writing/goal/private requests end an earlier numerical/public task.
        if read_writing(text) or goal_task(text) or PRIVATE.search(text) and not read(text):return None
        if read(text) or act(text)[0] in ACTS:continue
        if web_search.should_search(text):
            response=messages[index+1]['content'] if index+1<len(messages) and messages[index+1]['role']=='assistant' else ''
            return {'kind':'public','question':text,'index':index,'response':response}
        return None
    return None

def project_year(request,response):
    """Project one unnegated, anchored year from the visible answer, not a citation."""
    if not re.search(r'(?i)\b(?:when|year|born|birth|founded|opened|established|invented|created)\b',request):return None
    first=re.split(r'\n\s*\n|(?<=[.!])\s+',response.strip(),maxsplit=1)[0]
    if re.search(r'(?i)\b(?:not|never|unknown|unavailable|cannot|could not|conflict|incorrect|alleged|possibly|maybe|around|about)\b',first):return None
    if not re.search(r'(?i)\b(?:born|birth|founded|opened|established|invented|created|took place)\b|^The pages I read support \*\*',first):return None
    years=re.findall(r'(?<!\d)(?:1\d{3}|20\d{2})(?!\d)',first)
    return years[0] if len(set(years))==1 else None

def reply(messages,chosen):
    if chosen not in ('source','recheck','number') or len(messages)<3:return None
    found=anchor(messages[:-1])
    if found is None:return None
    from .dialogue import answer
    if found['kind']=='arithmetic':
        checked=dict(found['checked'])
        if chosen=='number':checked['response']=checked['response'].split('\n')[0].split(' = ')[-1]
        else:checked['response']+='\n\nI recalculated this with the independent exact arithmetic checker.'
        checked['dialogue']={'act':chosen,'original_request':found['question'],'source_message':found['index']}
        return checked
    if found['kind']=='code' and chosen=='recheck':
        if not found['code']:return answer('There is no visible implementation to check yet. Give the function and its complete examples.','code-recheck-missing')
        from .verify import check
        result=check(found['question'],{'route':'chat/code-generated','response':found['code']})
        if result['status']=='verified':body='I checked the visible code with the bounded interpreter: '+result['check']+'. These are case checks, not proof for every input.'
        elif result['status']=='failed':body='The code check found a problem: '+result['check']+'.'
        else:body='I could not establish correctness with the bounded checker: '+result['check']+'. I have not marked the program correct.'
        return answer(body,'code-recheck',verification=result,original_request=found['question'])
    if found['kind']=='public' and chosen=='number' and re.search(r'(?i)\byear\b',messages[-1]['content']):
        year=project_year(found['question'],found['response'])
        if year is not None:return answer(year,'year-projection',verification={'status':'unchecked','check':'One anchored year projected from the preceding visible answer; no new factual verification.'},original_request=found['question'],visible_answer=found['response'])
    return None
