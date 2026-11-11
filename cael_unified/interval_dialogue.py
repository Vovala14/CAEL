"""User-grounded availability as finite unions/intersections of clock intervals.

Learned surface decoding preserves owners/endpoints. Intervals are half-open on
one explicitly assumed common day; no timezone or overnight conversion guessed.
"""
import re
from .surface_grammar import read as decode

RESET=re.compile(r'(?i)^(?:start over|new topic|reset (?:the |this )?(?:chat|conversation|problem)|forget (?:this conversation|the schedule))[.!?]*$')


def minute(text):
    h,m=map(int,text.split(':'))
    if h>=24 or m>=60:raise ValueError('An availability endpoint is not a valid24-hour clock time.')
    return 60*h+m


def clock(n):return f'{n//60:02}:{n%60:02}'


def merge(intervals):
    result=[]
    for start,end in sorted(intervals):
        if result and start<=result[-1][1]:result[-1][1]=max(result[-1][1],end)
        else:result.append([start,end])
    return result


def intersect(a,b):
    result=[];i=j=0
    while i<len(a) and j<len(b):
        low=max(a[i][0],b[j][0]);high=min(a[i][1],b[j][1])
        if low<high:result.append([low,high])
        if a[i][1]<=b[j][1]:i+=1
        else:j+=1
    return merge(result)


def clarify(text):return dict(route='chat/interval-clarify',response=text,sources=[],interval_reasoning=dict(whole_clause_consumed=False,native_generated_code=False))


def reply(messages):
    if not messages or len(messages)>256 or sum(len(m['content']) for m in messages)>400000:return None
    owners={};evidence=[];superseded=[];current_query=None;active=False
    for at,m in enumerate(messages):
        if m['role']!='user':continue
        text=m['content'].strip().replace('’',"'")
        if RESET.fullmatch(text):owners={};evidence=[];active=False;current_query=None;continue
        if len(text)>5000:active=False;continue
        parts=[p.strip().rstrip('.!?') for p in re.split(r'(?<=[.!?])\s+|\n+|;\s*',text) if p.strip()]
        if len(parts)>32:
            if at==len(messages)-1 and owners:return clarify('The interval request exceeds32 complete clauses.')
            continue
        parsed=[]
        for part in parts:
            correction=bool(re.match(r'(?i)^(?:correction|actually)[,: ]+',part))
            statement=re.sub(r'(?i)^(?:correction|actually)[,: ]+','',part)
            value=decode(statement)
            parsed.append((part,statement,value,correction))
        owns=any(value and value['intent']=='availability' for _,_,value,_ in parsed)
        asks=any(value and value['intent']=='query_overlap' for _,_,value,_ in parsed)
        explains=bool(active and current_query and len(parts)==1 and re.fullmatch(r'(?i)why|explain(?: (?:that|the answer))?',parts[0]))
        if not owns and not (owners and asks) and not explains:
            # Do not swallow a malformed availability request merely because
            # another valid clause decoded. A wholly unsupported form defers.
            active=False;continue
        active=True
        if any(not value or value['intent'] not in ('availability','query_overlap') for _,_,value,_ in parsed) and not explains:
            if at==len(messages)-1:return clarify('I have not interpreted every availability clause or condition. State each person’s full time intervals, then ask for their overlap.')
            owners={};evidence=[];current_query=None;continue
        try:
            question=False
            for part,statement,value,correction in parsed:
                if explains:break
                if value['intent']=='query_overlap':current_query=statement;question=True;continue
                slots=value['slots'];owner=slots['owner'].strip();key=owner.casefold()
                if key in ('i','me','myself'):key='you';owner='you'
                if re.search(r'(?i)\b(?:he|she|it|they|both|we|everyone)\b',key):raise ValueError('An owner reference is ambiguous; name each participant explicitly.')
                low,high=minute(slots['start']),minute(slots['end'])
                if high<=low:raise ValueError('An interval must end after it starts on the same day. State an overnight/day offset explicitly; I will not invent one.')
                if key not in owners:
                    if len(owners)>=8:raise ValueError('The availability task exceeds8 named participants.')
                    owners[key]=dict(label=owner,intervals=[])
                if correction:
                    superseded.extend(e for e in evidence if e['owner']==key)
                    evidence=[e for e in evidence if e['owner']!=key];owners[key]['intervals']=[]
                if len(evidence)>=64:raise ValueError('The availability task exceeds64 intervals.')
                owners[key]['intervals'].append([low,high]);owners[key]['intervals']=merge(owners[key]['intervals'])
                evidence.append(dict(message=at,text=part,owner=key,interval=[low,high],surface=value))
            if at!=len(messages)-1:continue
            if not question and not explains:
                return dict(route='chat/interval-recorded',response='I have noted those availability windows for this conversation.',sources=[],interval_reasoning=dict(evidence=evidence,native_generated_code=False))
            if len(owners)<2:raise ValueError('At least two explicit participants’ availability windows are needed for a shared overlap.')
            if re.search(r'(?i)\bboth\b',current_query or '') and len(owners)!=2:raise ValueError('More than two participants are present. Name the pair, or ask when everyone is free.')
            values=list(owners.values());answer=values[0]['intervals']
            operations=[]
            for row in values[1:]:
                before=answer;answer=intersect(answer,row['intervals']);operations.append(dict(left=before,right=row['intervals'],result=answer))
            if answer:response='Shared availability: '+', '.join(clock(a)+'–'+clock(b) for a,b in answer)+'.'
            else:response='There is no shared availability with a positive duration in those intervals.'
            response+=' Assuming all supplied times refer to the same day and time zone.'
            if explains:response+=' I intersected each person’s stated windows; I did not infer any additional free time.'
            return dict(route='chat/interval-overlap',response=response,sources=[],
                interval_reasoning=dict(evidence=evidence,superseded=superseded,owners=owners,operations=operations,result=answer,
                     same_day_and_zone_assumption=True,half_open_intervals=True,whole_clause_consumed=True,native_generated_code=False))
        except ValueError as exc:
            if at==len(messages)-1:return clarify(str(exc))
            owners={};evidence=[];current_query=None;active=False
    return None
