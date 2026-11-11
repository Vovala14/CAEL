"""Bounded age, schedule and partial-event-order reasoning over supplied text.

All clauses must compile; exact rational equations/DAG paths are checked. This
is an open-entity finite grammar, not arbitrary natural-language understanding.
"""
import re
from fractions import Fraction

from . import natural_relations as nr

LABEL = r"[\w][\w'’ -]{0,45}?"
NUM = nr.NUMBER
RESET = re.compile(r'(?i)^(?:reset|clear|forget) (?:the |this )?(?:problem|puzzle|reasoning context)[.!?]*$')
WHY = re.compile(r'(?i)^(?:why|why is that|explain(?: (?:that|the answer|your answer))?|show (?:the |your )?(?:working|steps|reasoning))[.!?]*$')


def interested(text):
    return bool(re.search(r'(?i)\b(?:years? (?:old|older|younger|ago)|as old as|ages? (?:add up|sum)|how old|starts? at \d+|ends? at \d+|lasts? \d+|starts? .+ after .+ ends?|happens? (?:before|after)|happen (?:first|before|after))\b', text))


def clean(text):return text.strip().rstrip('.!?').strip()


def fresh():
    return dict(variables=[], rows=[], labels={}, kinds={}, evidence=[], superseded=[], query=None, edges=[], nodes=[])


def label(model, text, kind):
    text=text.strip();key=text.casefold()
    if not re.fullmatch(r"[\w][\w'’-]*(?: [\w][\w'’-]*){0,4}",text) or re.search(r'(?i)\b(?:if|unless|maybe|and|or|not|before|after)\b',text):
        raise nr.Unclear('Name one explicit person or event; an extra relation/condition remains.')
    lookup=kind+'|'+key
    if lookup not in model['labels']:
        if len(model['variables'])>=24:raise nr.Unclear('This temporal task exceeds24 scalar variables.')
        name='t'+str(len(model['variables']));model['labels'][lookup]=name;model['variables'].append(name);model['kinds'][name]=kind
    return model['labels'][lookup]


def add(model, coeff, value, text, message, correction=False):
    coeff={n:nr.fmt(Fraction(v)) for n,v in coeff.items() if v}
    if not coeff:raise nr.Unclear('A temporal relation is empty or self-contradictory.')
    if correction:
        # Only an explicitly corrected same scalar/relationship is replaced.
        removed=[r for r in model['rows'] if r['coefficients']==coeff]
        model['superseded'].extend(removed)
        model['rows']=[r for r in model['rows'] if r not in removed]
    if len(model['rows'])>=64:raise nr.Unclear('This temporal task exceeds64 equations.')
    model['rows'].append(dict(coefficients=coeff,value=nr.fmt(Fraction(value)),text=text,message=message))


def compile_fact(model, text, message, correction=False):
    t=clean(text)
    m=re.fullmatch('('+LABEL+r') is ('+NUM+r') years? old',t,re.I)
    if m:
        a,n=m.groups();n=nr.number(n)
        if n<0:raise nr.Unclear('A stated age is negative.')
        add(model,{label(model,a,'age'):1},n,text,message,correction);return True
    m=re.fullmatch('('+LABEL+r') is ('+NUM+r') years? (older|younger) than ('+LABEL+')',t,re.I)
    if m:
        a,n,d,b=m.groups();n=nr.number(n)
        if n<0:raise nr.Unclear('Use a nonnegative age difference and explicit direction.')
        av,bv=label(model,a,'age'),label(model,b,'age')
        if av==bv:raise nr.Unclear('An age difference refers to the same person.')
        add(model,{av:1,bv:-1},n if d.lower()=='older' else -n,text,message,correction);return True
    m=re.fullmatch(r'(?:In ('+NUM+r') years?,? |('+NUM+r') years? ago,? )?('+LABEL+r') (?:is|was|will be) (twice|three times|'+NUM+r' times) as old as ('+LABEL+')',t,re.I)
    if m:
        future,past,a,k,b=m.groups();offset=nr.number(future) if future else -nr.number(past) if past else Fraction(0)
        if future and offset<0 or past and offset>0:raise nr.Unclear('A temporal offset must have a nonnegative stated magnitude.')
        factor={'twice':Fraction(2),'three times':Fraction(3)}.get(k.lower())
        if factor is None:factor=nr.number(k.rsplit(' ',1)[0])
        if factor<=0:raise nr.Unclear('An age multiplier must be positive.')
        av,bv=label(model,a,'age'),label(model,b,'age')
        if av==bv:raise nr.Unclear('Use distinct people in an age-ratio relation.')
        add(model,{av:1,bv:-factor},(factor-1)*offset,text,message,correction);return True
    m=re.fullmatch('('+LABEL+r') and ('+LABEL+r")'s ages? (?:add up|sum) to ("+NUM+r') years?',t,re.I)
    if m:
        a,b,n=m.groups();av,bv=label(model,a,'age'),label(model,b,'age')
        if av==bv:raise nr.Unclear('The total repeats the same person.')
        add(model,{av:1,bv:1},nr.number(n),text,message,correction);return True
    m=re.fullmatch('('+LABEL+r') (starts|ends) at (\d{1,2}):(\d{2})',t,re.I)
    if m:
        a,side,h,minute=m.groups();h=int(h);minute=int(minute)
        if h>=24 or minute>=60:raise nr.Unclear('Use a valid explicit24-hour clock time.')
        add(model,{label(model,a,side.lower().rstrip('s')):1},60*h+minute,text,message,correction);return True
    m=re.fullmatch('('+LABEL+r') lasts ('+NUM+r') (minutes?|hours?)',t,re.I)
    if m:
        a,n,u=m.groups();duration=nr.number(n)*(60 if u.lower().startswith('hour') else 1)
        if duration<0:raise nr.Unclear('An event duration cannot be negative.')
        add(model,{label(model,a,'end'):1,label(model,a,'start'):-1},duration,text,message,correction);return True
    m=re.fullmatch('('+LABEL+r') starts ('+NUM+r') (minutes?|hours?) after ('+LABEL+r') ends',t,re.I)
    if m:
        a,n,u,b=m.groups();duration=nr.number(n)*(60 if u.lower().startswith('hour') else 1)
        if duration<0:raise nr.Unclear('Use a nonnegative delay after the named event.')
        add(model,{label(model,a,'start'):1,label(model,b,'end'):-1},duration,text,message,correction);return True
    m=re.fullmatch('('+LABEL+r') happens (before|after) ('+LABEL+')',t,re.I)
    if m:
        a,op,b=m.groups();a=a.strip();b=b.strip()
        if op.lower()=='after':a,b=b,a
        for node in (a,b):
            if node.casefold() not in [v.casefold() for v in model['nodes']]:model['nodes'].append(node)
        if len(model['nodes'])>24:raise nr.Unclear('The event graph exceeds24 named events.')
        names={v.casefold():v for v in model['nodes']};a,b=names[a.casefold()],names[b.casefold()]
        model['edges'].append(dict(before=a,after=b,text=text,message=message));return True
    return False


def query(model, text):
    t=clean(text)
    m=re.fullmatch(r'How old (?:is|will) ('+LABEL+r')(?: be in ('+NUM+r') years?)?',t,re.I)
    if m:
        a,n=m.groups();return dict(kind='age',person=a,offset=nr.fmt(nr.number(n) if n else Fraction(0)))
    m=re.fullmatch(r'How old was ('+LABEL+r') ('+NUM+r') years? ago',t,re.I)
    if m:return dict(kind='age',person=m[1],offset=nr.fmt(-nr.number(m[2])))
    m=re.fullmatch(r'When (?:does|will) ('+LABEL+r') (start|end)',t,re.I)
    if m:return dict(kind='clock',event=m[1],side=m[2].lower())
    m=re.fullmatch(r'Does ('+LABEL+r') happen (before|after) ('+LABEL+')',t,re.I)
    if m:
        a,op,b=m.groups();return dict(kind='order',before=a if op.lower()=='before' else b,after=b if op.lower()=='before' else a)
    m=re.fullmatch(r'What must happen before ('+LABEL+')',t,re.I)
    if m:return dict(kind='ancestors',event=m[1])
    if re.fullmatch(r'What happens first',t,re.I):return dict(kind='first')
    return None


def evaluate(model, q):
    if q['kind'] in ('age','clock'):
        key=('age|'+q['person'].casefold()) if q['kind']=='age' else q['side']+'|'+q['event'].casefold()
        if key not in model['labels']:raise nr.Unclear('The question names a person/event without supplied relations.')
        variable=model['labels'][key]
        variables,matrix,pivots,combinations=nr.reduce_rows(model)
        column=variables.index(variable)
        if column not in pivots:raise nr.Unclear('The supplied relations do not determine the requested value.')
        row=matrix[pivots.index(column)]
        if any(v for j,v in enumerate(row[:-1]) if j!=column):raise nr.Unclear('A missing age, duration or clock anchor leaves the answer undetermined.')
        for c,line in zip(pivots,matrix):
            if model['kinds'][variables[c]]=='age' and not any(v for j,v in enumerate(line[:-1]) if j!=c) and line[-1]<0:
                raise nr.Unclear('The complete age relations imply a negative current age.')
        value=row[-1]+Fraction(q.get('offset','0'))
        if value<0:raise nr.Unclear('The requested age/time lies before the supported nonnegative origin.')
        weights=combinations[pivots.index(column)]
        proof=dict(method='exact-rational-elimination',rows=model['rows'],variables=variables,target=variable,
                   row_combination=[nr.fmt(x) for x in weights],offset=q.get('offset','0'),value=nr.fmt(value))
        if q['kind']=='age':return nr.fmt(value)+' years old.',proof
        if value.denominator!=1:raise nr.Unclear('The derived clock time contains a fraction of a minute; provide a minute-exact duration.')
        days,minutes=divmod(int(value),1440);h,minute=divmod(minutes,60)
        return f'{h:02}:{minute:02}'+(f' (+{days} day'+('s' if days!=1 else '')+')' if days else '')+'.',proof
    nodes=model['nodes'];edges=model['edges'];reach={n:set() for n in nodes}
    if not nodes:raise nr.Unclear('No explicit event-order relations have been established.')
    for e in edges:reach[e['before']].add(e['after'])
    for pivot in nodes:
        for a in nodes:
            if pivot in reach[a]:reach[a].update(reach[pivot])
    if any(n in reach[n] for n in nodes):raise nr.Unclear('The before/after statements contain a cycle and cannot all hold.')
    def node(text):
        found=[n for n in nodes if n.casefold()==text.casefold()]
        if len(found)!=1:raise nr.Unclear('The question names an event not established in this task.')
        return found[0]
    if q['kind']=='order':
        a,b=node(q['before']),node(q['after'])
        response='Yes. '+a+' must happen before '+b+'.' if b in reach[a] else 'No. '+b+' must happen before '+a+'.' if a in reach[b] else 'Their order is not determined by the stated relations.'
    elif q['kind']=='ancestors':
        b=node(q['event']);before=[a for a in nodes if b in reach[a]]
        response='These events must happen before '+b+': '+', '.join(before)+'.' if before else 'No earlier event is established for '+b+'.'
    else:
        first=[n for n in nodes if not any(n in reach[a] for a in nodes)]
        response=first[0]+' must be first among the named events.' if len(first)==1 else 'No unique first event is determined. Possible first events: '+', '.join(first)+'.'
    return response,dict(method='finite-transitive-closure',edges=edges,reachability={k:sorted(v) for k,v in reach.items()})


def reply(messages):
    if len(messages)>256 or sum(len(m['content']) for m in messages)>400000:return None
    model=None;last=None;active=False
    for i,m in enumerate(messages):
        if m['role']!='user':continue
        text=m['content'].strip().replace('’',"'")
        if RESET.fullmatch(text):model=None;active=False;continue
        if len(text)>6000:active=False;continue
        relevant=interested(text)
        follow=model is not None and (query(model,text) is not None or WHY.fullmatch(text))
        # Standalone factual age questions belong to factual lookup. This
        # contextual engine owns a question only after supplied temporal facts.
        if model is None and query(fresh(),text) is not None:continue
        if not relevant and not follow:
            active=False;continue
        branch=bool(re.match(r'(?i)^what if\b',text))
        if branch:
            # An unsupported branch is never committed to the real frame.
            if i==len(messages)-1:return clarify('Please state a separate complete hypothetical temporal problem; I will not overwrite the actual facts.')
            continue
        if re.search(r'(?i)```|["“]|\b(?:quote|translate|suppose|imagine|if|unless|except|maybe)\b',text):
            if i==len(messages)-1 and relevant:return clarify('An unsupported condition, quotation or hypothetical remains in this temporal task.')
            active=False;continue
        if model is None:model=fresh()
        if relevant and not active and last is not None:
            model=fresh()  # an unrelated turn ended the active task
        active=True
        try:
            lines=[clean(p) for p in re.split(r'(?<=[.!?])\s+|\n+|;\s*',text) if p.strip()]
            if len(lines)>32:raise nr.Unclear('The temporal request exceeds32 complete clauses.')
            q=None
            for part in lines:
                correction=bool(re.match(r'(?i)^(?:correction|actually)[,: ]+',part))
                part=re.sub(r'(?i)^(?:correction|actually)[,: ]+','',part)
                if WHY.fullmatch(part):
                    if not model['query']:raise nr.Unclear('There is no previous temporal answer to explain.')
                    q=dict(model['query'],explain=True)
                else:
                    candidate=query(model,part)
                    if candidate:
                        if q:raise nr.Unclear('Ask one temporal question at a time.')
                        q=candidate
                    elif not compile_fact(model,part,i,correction):
                        raise nr.Unclear('I have not interpreted this complete clause: '+part+'.')
                model['evidence'].append(dict(message=i,text=part))
            if q:model['query']=q
            if i!=len(messages)-1:last=i;continue
            if not q:
                return dict(route='chat/temporal-recorded',response='I have recorded those temporal relations for this conversation.',sources=[],temporal_reasoning=dict(evidence=model['evidence'],native_generated_code=False))
            response,proof=evaluate(model,q)
            if q.get('explain'):
                response+='\nI used only these supplied relations:\n'+'\n'.join('- '+e['text'] for e in model['rows'] if q['kind'] in ('age','clock'))
                if q['kind'] not in ('age','clock'):response+='\n'.join('- '+e['text'] for e in model['edges'])
            return dict(route='chat/temporal-'+q['kind'],response=response,sources=[],
                temporal_reasoning=dict(query=q,proof=proof,evidence=model['evidence'],superseded=model['superseded'],
                    native_generated_code=False,all_clauses_consumed=True,temporary=False))
        except nr.Unclear as exc:
            if i==len(messages)-1:return clarify(str(exc))
            model=None;active=False;last=None
    return None


def clarify(reason):
    return dict(route='chat/temporal-clarify',response=reason,sources=[],
                temporal_reasoning=dict(all_clauses_consumed=False,native_generated_code=False,clarification=reason))
