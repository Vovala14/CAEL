"""Whole-clause natural-language grounding into non-neural symbolic engines.

Finite surface grammars, open literal entities. Unknown extra clauses remain
unknown. Compiled data and source evidence accompany every supported answer.
"""
import copy
from fractions import Fraction
import hashlib
import json
import re
from . import finite_constraints as fc
from . import natural_relations as nr
from . import world_reasoning as wr

Unclear=nr.Unclear
NP=r"[\w][\w'’ -]{0,65}?"
WHY=re.compile(r'(?i)^(?:why|why is that|explain(?: (?:that|the answer|your answer))?|show (?:me )?(?:why|(?:the |your )?(?:steps|reasoning|working)))[?.!]*$')
SOCIAL=re.compile(r'(?i)^(?:thanks|thank you|ok|okay|got it|great)[.!]*$')
RESET=re.compile(r'(?i)^(?:reset|clear|forget) (?:the |this )?(?:problem|puzzle|reasoning context)[.!?]*$')
ORDINALS=dict(zip('first second third fourth fifth sixth seventh eighth'.split(),range(1,9)))


def clean(text):return text.strip().rstrip('.?!').strip()


def parts(text):
    if len(text)>12000:raise Unclear('The complete natural-language problem exceeds12000 characters.')
    text=re.sub(r'(?i)^(?:please )?(?:help me (?:solve|work through) this|here is (?:a|the) problem|new problem)\s*:\s*','',text)
    lines=[clean(p) for p in re.split(r'(?<=[.!?])\s+|\n+|,\s*(?=(?:how many|how much|which|who|what)\b)',text,flags=re.I) if p.strip()]
    if not 1<=len(lines)<=40:raise Unclear('Supply at most40 complete clauses.')
    return lines


def listing(text):
    values=[v.strip() for v in re.split(r'\s*,\s*|\s+and\s+|\s+or\s+',text) if v.strip()]
    if not 2<=len(values)<=8 or len(set(v.casefold() for v in values))!=len(values):raise Unclear('Use two to eight distinct explicitly listed entities/values.')
    if any(not re.fullmatch(r"[\w][\w'’-]*(?: [\w][\w'’-]*){0,3}",v) for v in values):raise Unclear('An entity/value list contains an unsupported clause.')
    return values


def evidence(frame,text,at):
    if len(frame['evidence'])>=120:raise Unclear('The conversation task exceeds120 source clauses.')
    frame['evidence'].append(dict(message=at,text=text))


def entity(frame,text):
    text=re.sub(r'(?i)^(?:the )?','',text.strip())
    matches=[n for n in frame['labels'] if re.sub(r'(?i)^the ','',n).casefold()==text.casefold()]
    if len(matches)!=1:raise Unclear('The relation/question names an undeclared or ambiguous entity: '+text+'.')
    return matches[0]


def code(frame,label):return frame['labels'][entity(frame,label)]


def finite_fact(frame,text):
    t=clean(re.sub(r'(?i)^(?:also|and|additionally)[,: ]+','',text))
    labels=frame['labels']; task=frame['task']
    escaped='(?:the )?('+'|'.join(re.escape(n) for n in sorted(labels,key=len,reverse=True))+')'
    if frame['kind']=='ordering':
        m=re.fullmatch(escaped+r'\s+(?:is |stands |sits |comes |must be )?(not )?(?:(immediately |directly )?(?:to the )?(left of|right of|before|after|ahead of|behind)|next to|adjacent to)\s+'+escaped,t,re.I)
        if m:
            a,neg,immediate,op,b=m.groups();a,b=labels[entity(frame,a)],labels[entity(frame,b)]
            if op is None:rule='abs('+a+'-'+b+')==1'
            else:
                if op.casefold() in ('right of','after','behind'):a,b=b,a
                rule=a+'+1=='+b if immediate else a+'<'+b
            if neg:rule='not ('+rule+')'
        else:
            m=re.fullmatch(escaped+r'\s+(?:is|stands|sits|must be)\s+(not )?(?:in (?:the )?)?(first|second|third|fourth|fifth|sixth|seventh|eighth|last|leftmost|rightmost|(?:position|place) \d+)',t,re.I)
            if not m:return False
            a,neg,pos=m.groups();position=position_value(pos,len(labels))
            rule=labels[entity(frame,a)]+('!=' if neg else '==')+str(position)
    else:
        noun=re.escape(frame['property'])
        m=re.fullmatch(escaped+r"(?:'s\s+"+noun+r')?\s+(?:has|gets|uses|is|does not have|doesn\'t have|is not|has not|does not use)\s+(?:the\s+)?(.+)',t,re.I)
        if not m:return False
        a,val=m.groups()
        # A supplied property noun can appear after the value, never silently
        # remove any other modifier/condition.
        val=re.sub(r'(?i)\s+'+noun+r'$','',val).strip()
        candidates=[v for v in frame['values'] if v.casefold()==val.casefold()]
        if len(candidates)!=1:raise Unclear('The assignment names an undeclared value or contains an extra clause.')
        neg=bool(re.search(r"(?i)\b(?:not|doesn't)\b",t))
        rule=labels[entity(frame,a)]+('!=' if neg else '==')+repr(candidates[0])
    task['constraints'].append(rule);fc.prepare(task);return True


def position_value(text,size):
    text=text.casefold()
    reverse=False
    suffix=re.fullmatch(r'(.+?) from (?:the )?(left|right)',text)
    if suffix:text=suffix[1];reverse=suffix[2]=='right'
    if text in ('first','leftmost','far left'):return size if reverse else 1
    if text in ('last','rightmost','far right'):return 1 if reverse else size
    if text in ('middle','the middle'):
        if size%2==0:raise Unclear('An even-length row has two middle positions; specify which position.')
        return size//2+1
    if text in ORDINALS:
        n=ORDINALS[text]
    else:
        match=re.fullmatch(r'(?:position|place) (\d+)',text)
        if not match:raise Unclear('The requested row position is unsupported.')
        n=int(match[1])
    if not 1<=n<=size:raise Unclear('The row position is outside the declared row.')
    return size+1-n if reverse else n


def finite_query(frame,text):
    t=clean(text)
    if WHY.fullmatch(t):return dict(frame['query'],explain=True) if frame.get('query') else dict(kind='solutions',explain=True)
    if frame['kind']=='ordering':
        match=re.fullmatch(r'(?i)(?:who|which (?:one|person|object)) (?:is|stands|sits|comes)\s+(?:on |at |in )?(?:the )?(.+)',t)
        if match:return dict(kind='occupant',position=position_value(match[1],len(frame['labels'])))
        match=re.fullmatch(r'(?i)where (?:is|does) (.+?)(?: stand| sit)?',t)
        if match:return dict(kind='value',name=entity(frame,match[1]))
    else:
        prop=re.escape(frame['property'])
        match=re.fullmatch(r'(?i)(?:which|what)\s+(?:'+prop+r'|one|value)\s+(?:does|will)\s+(.+?)\s+(?:have|get|use)',t)
        if not match:match=re.fullmatch(r"(?i)what (?:is|will be)\s+(.+?)'s\s+"+prop,t)
        if match:return dict(kind='value',name=entity(frame,match[1]))
    match=re.fullmatch(r'(?i)(?:what|how) about (.+)',t)
    if match:return dict(kind='value',name=entity(frame,match[1]))
    if re.fullmatch(r'(?i)how many (?:solutions|arrangements|assignments)(?: are there)?',t):return dict(kind='count')
    if re.fullmatch(r'(?i)(?:solve (?:it|this)|give (?:me )?(?:a |one )?(?:solution|arrangement)|what (?:is|are) (?:the )?(?:order|solution|arrangement))',t):return dict(kind='solutions')
    if re.fullmatch(r'(?i)(?:give me (?:a |one )?hint|hint)',t):return dict(kind='hint')
    return None


def finite_new(text,at):
    pp=parts(text);head=pp[0]
    order=re.fullmatch(r'(?i)(.+?)\s+(?:are|stand|sit)\s+(?:standing |sitting )?(?:in (?:a|one|a single) (?:row|line)|lined up)(?:\s+from left to right)?(?:\s+in (?:some|an unknown) order)?',head)
    assign=re.fullmatch(r'(?i)(.+?)\s+each\s+(?:have|has|get|gets|use|uses)\s+(?:exactly )?one\s+different\s+([a-z][a-z -]{0,30}?)\s*(?:from|chosen from|:)\s*(.+)',head)
    if not order and not assign:return None
    names=listing(order[1] if order else assign[1]);mapping={n:'v'+str(i) for i,n in enumerate(names)}
    vals=list(range(1,len(names)+1)) if order else listing(assign[3])
    frame=dict(kind='ordering' if order else 'assignment',labels=mapping,values=vals,property='position' if order else assign[2].strip(),
               task=dict(domains={n:list(vals) for n in mapping.values()},constraints=['all_different('+','.join(mapping.values())+')']),evidence=[],query=None)
    evidence(frame,head,at)
    for p in pp[1:]:
        q=finite_query(frame,p)
        if q:
            if frame['query'] is not None:raise Unclear('Ask one question per turn; neither question can be discarded.')
            frame['query']=q
        elif not finite_fact(frame,p):raise Unclear('An ordering/assignment clause is unsupported: '+p+'.')
        evidence(frame,p,at)
    if frame['query'] is None:frame['query']=dict(kind='solutions')
    fc.prepare(frame['task']);return frame


def numeric_new(text,at):
    if not re.search(r'(?i)\b(?:how many|how much)\b',text):return None
    if not re.search(r'(?i)\b(?:has|have|holds|owns|carries|gives|receives)\s+(?:'+nr.NUMBER+r')\b',text):return None
    # Established rate, sharing/group, percent and currency specialists retain
    # their full contracts. This reader owns explicit same-unit relations.
    if re.search(r'(?i)\b(?:each|per|percent|rate|speed|costs?|profit|revenue)\b|%',text):return None
    frame=nr.empty();frame['evidence']=[];frame['query']=None
    for p in parts(text):
        if re.match(r'(?i)^how (?:many|much)\b',p):
            q=quantity_query(frame,p)
            if q is None:raise Unclear('The complete quantity question is outside the admitted owner/unit grammar.')
            if frame['query'] is not None:raise Unclear('Ask one complete quantity question per turn.')
            frame['query']=q
        else:
            # Coordinated complete owners, not arbitrary "and" inside a unit.
            clauses=re.split(r'\s+and\s+(?='+nr.ENTITY+r'\s+(?:has|holds|owns|carries)\b)',p,flags=re.I)
            for clause in clauses:
                if not nr.add(frame,clause,at):raise Unclear('A quantity clause is unsupported: '+clause+'.')
        evidence(frame,p,at)
    if not frame['query']:raise Unclear('A complete quantity query is missing.')
    return frame


def quantity_query(frame,text):
    t=clean(text);t=re.sub(r'(?i)^and\s+','',t)
    m=re.fullmatch(r'(?i)what about (.+)',t)
    if m:
        asked=m[1]
        u=(frame.get('query') or {}).get('unit') or frame['last_units']
        if asked.casefold() in ('the other one','the other person','the other owner'):
            used={nr.owner(n) for n in (frame.get('query') or {}).get('owners',[])}
            candidates=set(frame['display'])-used
            if len(candidates)!=1:raise Unclear('The other-owner reference is not unique.')
            asked=frame['display'][next(iter(candidates))]
        t='How many '+frame['units'][u]+' does '+asked+' have'
    elif re.fullmatch(r'(?i)(?:how many|how much)(?: (?:are there|is that))? (?:in all|altogether|in total|together)',t):
        u=(frame.get('query') or {}).get('unit') or frame['last_units']
        t='How many '+frame['units'][u]+' do they have altogether'
    return nr.question(frame,t)


def state_new(text,at):
    pp=parts(text);initial=None;transitions={};states=[];action=None;query_text=None;source=[]
    owns=bool(re.search(r'(?i)\b(?:starts|begins)\b',text) and re.search(r'(?i)\b(?:cycles through|changes .+ to|toggles between)\b',text))
    if not owns:return None
    for p in pp:
        start=re.fullmatch(r'(?i)(?:an? |the )?'+NP+r'\s+(?:starts|begins)\s+(?:in (?:state )?|at |on )?('+NP+')',p)
        cycle=re.fullmatch(r'(?i)(?:an? |the )?'+NP+r'\s+cycles through\s+(.+?)(?:,?\s+in that order)?',p)
        advance=re.fullmatch(r'(?i)(?:each|every)\s+('+NP+r')\s+(?:advances|moves)\s+(?:it|the state|the display|the marker)\s+(?:forward )?(?:by )?one\s+(?:step|state|position)',p)
        change=re.fullmatch(r'(?i)(?:each|every)\s+('+NP+r')\s+changes\s+(.+)',p)
        if cycle:
            if transitions:raise Unclear('The transition cycle was repeated or conflicts with an earlier transition model.')
            vals=listing(cycle[1]);states=list(vals)
            for i,v in enumerate(vals):transitions[v]=vals[(i+1)%len(vals)]
        elif advance:
            if action and action.casefold()!=advance[1].casefold():raise Unclear('Two different action types require explicit distinct transition models.')
            action=advance[1]
        elif change:
            if action and action.casefold()!=change[1].casefold():raise Unclear('The action labels conflict.')
            action=change[1]
            for clause in re.split(r'\s+and\s+',change[2]):
                m=re.fullmatch('('+NP+r')\s+to\s+('+NP+')',clause,re.I)
                if not m or m[1] in transitions:raise Unclear('A transition is incomplete, conditional or repeated.')
                transitions[m[1]]=m[2]
                for v in m.groups():
                    if v not in states:states.append(v)
        elif re.match(r'(?i)^(?:what|which|and after|after)\b',p):
            if query_text is not None:raise Unclear('Ask one state query at a time.')
            query_text=p
        elif start:
            if initial is not None:raise Unclear('The initial state was supplied twice.')
            initial=start[1]
        else:raise Unclear('An explicit state-transition clause is unsupported: '+p+'.')
        source.append(p)
    if initial is None or not action or not transitions or len(transitions)>16:raise Unclear('Supply the initial state, action and every explicit transition.')
    # State labels are literal; do not infer a missing pair from a noun.
    if initial not in states:raise Unclear('The initial label is outside the stated transition model.')
    frame=dict(kind='state-machine',initial=initial,transitions=transitions,action=action,query=None,last_count=0,evidence=[])
    q=state_query(frame,query_text or '')
    if q is None:raise Unclear('Ask for the state after an explicit number of the declared actions.')
    frame['query']=q;frame['last_count']=q['count']
    for p in source:evidence(frame,p,at)
    return frame


def action_match(a,b):
    # Ordinary plural inflection only, never a semantic synonym guess.
    def norm(s):
        s=s.casefold().strip()
        if re.search(r'(?:ches|shes|sses|xes)$',s):return s[:-2]
        return s[:-1] if s.endswith('s') and not s.endswith('ss') else s
    return norm(a)==norm(b)


def state_query(frame,text):
    t=clean(text)
    if WHY.fullmatch(t):return dict(frame['query'],explain=True)
    m=re.fullmatch(r'(?i)(?:(?:what|which) (?:is |will be )?(?:its |the )?(?:state|value|label)(?: be)?\s+)?(?:and )?after\s+('+nr.NUMBER+r')\s+(more\s+)?(.+)',t)
    if not m:
        m=re.fullmatch(r'(?i)(?:what|which) (?:state|value|label) (?:is|will) (?:it|the \w+) (?:be )?(?:in )?after\s+('+nr.NUMBER+r')\s+(more\s+)?(.+)',t)
    if not m:return None
    raw,more,action=m.groups();action=re.sub(r'(?i)\s+(?:in total|altogether)$','',action)
    if not action_match(action,frame['action']):raise Unclear('The question refers to a different or conditional action.')
    n=nr.number(raw)
    if n.denominator!=1 or not 0<=n<=10**9:raise Unclear('Use a nonnegative whole-number action count within10^9.')
    count=int(n)+(frame['last_count'] if more else 0)
    if count>10**9:raise Unclear('The cumulative action count exceeds10^9.')
    return dict(kind='state',count=count)


def map_new(text,at):
    if not re.search(r'(?i)\b(?:passages|paths|links|routes|rooms|nodes|stops)\b',text) or not re.search(r'(?i)\b(?:leads? to|go from|go |between|to)\b',text):return None
    labels=[];edges=[];start=goal=None;closed=False;pp=parts(text);owned=False;question_seen=False
    for p in pp:
        declaration=re.fullmatch(r'(?i)(?:(?:a|the) (?:game|map|network) (?:has|contains) )?(?:rooms|nodes|stops)\s*(?:(?:are|named|called)\s+|:\s*)?(.+)',p)
        route=re.fullmatch(r'(?i)(?:passages|paths|links|routes)\s+(?:go|lead|run)(?:\s+from)?\s+(.+)',p)
        relation=re.fullmatch('('+NP+r')\s+leads to\s+('+NP+')',p,re.I)
        between=re.fullmatch(r'(?i)(?:a |the )?(?:path|passage|link) (?:goes |runs )?(?:in both directions )?between\s+('+NP+r')\s+and\s+('+NP+')',p)
        initial=re.fullmatch(r"(?i)I(?: am|'m)?\s+(?:start(?:ing)?|currently|now|at|in)\s*(?:in |at )?(.+)",p)
        target=re.fullmatch(r'(?i)I (?:need|want|must) (?:to )?(?:reach|get to|go to)\s+(.+)',p)
        combined=re.fullmatch(r"(?i)I(?: am|'m)? (?:start(?:ing)?|currently|now|at|in)\s*(?:in |at )?(.+?)\s+and (?:I )?(?:need|want|must)(?: to (?:reach|get to|go to))?\s+(.+)",p)
        asks=re.fullmatch(r'(?i)(?:how (?:can|do) I (?:get|go|travel) (?:from (.+?) )?to (.+)|give (?:me )?(?:the |a )?(?:route|path)|what (?:is|are) (?:the )?(?:route|path|next room|next node|next stop))',p)
        if declaration:
            if labels:raise Unclear('The map node list is repeated.')
            labels=listing(declaration[1]);owned=True
        elif route:
            owned=True
            for item in re.split(r'\s*,\s*|\s+and\s+',route[1]):
                edge=re.fullmatch(r'(?i)(?:from )?('+NP+r')\s+to\s+('+NP+')',item)
                if not edge:raise Unclear('A route clause is incomplete or conditional.')
                edges.append(edge.groups())
        elif relation:owned=True;edges.append(relation.groups())
        elif between:owned=True;edges.extend([between.groups(),tuple(reversed(between.groups()))])
        elif re.fullmatch(r'(?i)there are no other (?:passages|paths|links|routes)',p):closed=True
        elif combined:
            if start is not None or goal is not None:raise Unclear('The map start/goal was repeated.')
            start,goal=combined.groups()
        elif initial:
            if start is not None:raise Unclear('The map start was repeated.')
            start=initial[1]
        elif target:
            if goal is not None:raise Unclear('The map goal was repeated.')
            goal=target[1]
        elif asks:
            if question_seen:raise Unclear('Ask one navigation question per turn.')
            question_seen=True
            if asks[2]:
                if asks[1]:
                    if start is not None and start.casefold()!=asks[1].casefold():raise Unclear('The route question conflicts with the stated starting location.')
                    start=asks[1]
                if goal is not None and goal.casefold()!=asks[2].casefold():raise Unclear('The route question conflicts with the stated destination.')
                goal=asks[2]
        else:
            if owned:raise Unclear('A map clause is unsupported: '+p+'.')
            return None
    if not owned:return None
    if not labels:
        labels=list(dict.fromkeys(v for e in edges for v in e))
    if not 2<=len(labels)<=32 or start is None or goal is None:raise Unclear('A map needs explicit nodes/edges, a start and a goal.')
    def node(s):
        found=[v for v in labels if v.casefold()==s.casefold()]
        if len(found)!=1:raise Unclear('A map reference is unknown or ambiguous: '+s+'.')
        return found[0]
    start,goal=node(start),node(goal);edges=[(node(a),node(b)) for a,b in edges]
    actions=[dict(name='move_'+str(i),pre=dict(at=a),effects=dict(at=b)) for i,(a,b) in enumerate(edges)]
    if not actions:raise Unclear('No complete navigation edge was supplied.')
    frame=dict(kind='map',labels={n:n for n in labels},edges=edges,closed=closed,
               task=dict(initial=dict(at=start),goal=dict(at=goal),bounds=dict(at=labels),actions=actions),query=dict(kind='route'),evidence=[])
    for p in pp:evidence(frame,p,at)
    return frame


def fresh(text,at):
    # These explicit formats retain their previous owners, including invalid
    # extra clauses. User/source quotations are not instructions to execute.
    if text.lstrip().startswith(('{','[','"',"'",'`')) or re.match(r'(?i)^(?:constraint puzzle|finite problem|puzzle|planning (?:task|problem)|variables|domain |order:|arrange:|facts:|given:|premises:|add:|question:)',text):return None
    if re.match(r'(?i)^(?:quote|translate|proofread|rewrite|write a story)\b',text):return None
    for parser in [finite_new,state_new,map_new,numeric_new]:
        value=parser(text,at)
        if value is not None:return value
    return None


def update(frame,text,at):
    f=copy.deepcopy(frame);t=clean(text);temporary=False
    m=re.fullmatch(r'(?is)what if\s+(.+)',t)
    if m:temporary=True;t=clean(m[1])
    q=None
    if f['kind'] in ('ordering','assignment'):
        q=finite_query(f,t)
        if q:f['query']=q
        elif finite_fact(f,t):pass
        else:return frame,frame,False
    elif f['kind']=='quantities':
        if WHY.fullmatch(t):q=dict(f['query'],explain=True)
        else:q=quantity_query(f,t)
        if q:f['query']=q
        elif nr.add(f,re.sub(r'(?i)^(?:also|and)[,: ]+','',t),at):
            # Queries are references to current owner/unit state, not cached
            # coefficients pointing at an earlier inventory epoch.
            f['query']=nr.question(f,f['query']['question'])
        else:return frame,frame,False
    elif f['kind']=='state-machine':
        q=state_query(f,t)
        if q:f['query']=q;f['last_count']=q['count']
        else:return frame,frame,False
    elif f['kind']=='map':
        m=re.fullmatch(r"(?i)I (?:have )?(?:reached|arrived (?:at|in)|am (?:now )?(?:at|in))\s+(.+)",t)
        if m:
            n=entity(f,m[1]);f['task']['initial']['at']=n
        elif WHY.fullmatch(t):f['query']=dict(kind='route',explain=True)
        elif re.fullmatch(r'(?i)(?:what (?:is|should be) (?:the )?next (?:room|node|stop|step)|what now|next step)',t):f['query']=dict(kind='next')
        elif re.fullmatch(r'(?i)(?:give (?:me )?(?:the |a )?(?:route|path)|where should I go)',t):f['query']=dict(kind='route')
        else:return frame,frame,False
    evidence(f,text,at);f['temporary']=temporary
    return frame if temporary else f,f,True


def quantity_update_turn(frame,text,at):
    body=re.sub(r'(?i)^(?:add|also|update)\s*:\s*','',text)
    body=re.sub(r'(?i)(?:^|(?<=[.!?])\s+)question\s*:\s*',lambda m:' ' if m[0][0].isspace() else '',body)
    body=body.strip()
    clauses=parts(body)
    persistent=frame;view=frame;query_seen=False
    for p in clauses:
        if WHY.fullmatch(p) or re.match(r'(?i)^(?:how many|how much|what about|and how|and what)\b',p):
            if query_seen:raise Unclear('Ask one complete query per update; no second question was discarded.')
            query_seen=True
        persistent,view,handled=update(persistent,p,at)
        if not handled:raise Unclear('A quantity update contains an unsupported clause: '+p+'.')
    return persistent,view,True


def render(frame):
    kind=frame['kind'];q=frame['query'];result=None
    if kind=='quantities':
        value,proof=nr.solve(frame,q)
        text=nr.fmt(value)+' '+frame['units'][q['unit']]+'.'
        if q.get('explain'):
            text+='\nI kept each owner and item separate, preserved earlier/current quantities, and solved every supplied exact relation:\n'
            text+='\n'.join('- '+r['text'] for r in frame['rows'])
            for r in frame['rows']:
                plus=[n for n,c in r['coefficients'].items() if Fraction(c)==1]
                minus=[n for n,c in r['coefficients'].items() if Fraction(c)==-1]
                if len(plus)==len(minus)==1 and len(r['coefficients'])==2 and all(n in proof['known_values'] for n in plus+minus):
                    before,after=proof['known_values'][minus[0]],proof['known_values'][plus[0]];delta=Fraction(r['value'])
                    text+='\n'+before+(' + ' if delta>=0 else ' - ')+nr.fmt(abs(delta))+' = '+after
        result=dict(value=nr.fmt(value),query=q,proof=proof)
        answer=dict(route='helper/natural-quantity',response=text,sources=[],exact=True,
                    helper_reasoning=dict(exact=True,value=nr.fmt(value),all_clauses_consumed=True))
    elif kind in ('ordering','assignment'):
        solved=fc.solve(frame['task']);sols=solved['solutions'];result=solved
        if not solved['complete']:text='The finite search reached '+solved['status']+'. I cannot give a forced answer or a complete count.'
        elif not sols:text='Those complete rules conflict; there is no satisfying assignment in the declared model.'
        elif q['kind']=='occupant':
            possible=[label for label,var in frame['labels'].items() if any(s[var]==q['position'] for s in sols)]
            text=(possible[0]+'.') if len(possible)==1 and all(any(s[var]==q['position'] for var in frame['labels'].values()) for s in sols) else 'Possible occupants: '+', '.join(possible)+'. A unique occupant is not determined.'
        elif q['kind']=='value':
            name=q['name'];vals=solved['possible_values'][frame['labels'][name]]
            text=name+': '+', '.join(map(str,vals))+('.' if len(vals)==1 else '. More than one value remains possible.')
        elif q['kind']=='count':text=str(len(sols))+' complete satisfying assignments.'
        elif q['kind']=='hint':
            fixed=[(label,solved['forced'][var]) for label,var in frame['labels'].items() if var in solved['forced']]
            text='One hint: '+fixed[0][0]+' must be '+str(fixed[0][1])+'.' if fixed else 'No individual value is forced yet. Another rule is needed to determine one.'
        else:
            one={label:sols[0][var] for label,var in frame['labels'].items()}
            text=('The assignment: ' if len(sols)==1 else 'One possible assignment: ')+json.dumps(one,ensure_ascii=False)+'.'
        if q.get('explain'):
            text+='\nI checked every declared relation against all admitted finite assignments. Supplied clauses:\n'+'\n'.join('- '+r['text'] for r in frame['evidence'])
        answer=dict(route='chat/natural-'+kind,response=text,sources=[])
    elif kind=='state-machine':
        n=q['count'];state=frame['initial'];seen={};sequence=[]
        while state not in seen and len(sequence)<=16:
            seen[state]=len(sequence);sequence.append(state)
            if state not in frame['transitions']:break
            state=frame['transitions'][state]
        if n<len(sequence):value=sequence[n];cycle=None
        elif state in seen and state in frame['transitions']:
            begin=seen[state];period=len(sequence)-begin;value=sequence[begin+(n-begin)%period];cycle=dict(start=begin,period=period)
        else:raise Unclear('The explicit transition model is missing a state needed for that many actions.')
        result=dict(initial=frame['initial'],transitions=frame['transitions'],count=n,value=value,sequence=sequence,cycle=cycle)
        text=value+'.'
        if q.get('explain'):text+='\nStarting from '+frame['initial']+', the explicit states are '+ ' -> '.join(sequence)+'. I applied '+str(n)+' '+frame['action']+' actions'+(' using the repeated cycle of length'+str(cycle['period']) if cycle else '')+'.'
        answer=dict(route='chat/natural-state',response=text,sources=[])
    else:
        solved=wr.solve(frame['task']);result=solved
        if solved['status']!='plan':text='No route was found within the supplied map and limits. I have not assumed additional passages.'
        else:
            nodes=[frame['task']['initial']['at']]+[s['after']['at'] for s in solved['steps']]
            if q['kind']=='next':text=nodes[1]+'.' if len(nodes)>1 else 'You are already at the stated destination.'
            else:text=' -> '.join(nodes)+'.'
            if q.get('explain'):text+='\nEach step follows a supplied directed passage; I replayed the route from the current stated location.'
        answer=dict(route='chat/natural-map',response=text,sources=[])
    if frame.get('temporary'):answer['response']='For that temporary scenario: '+answer['response']
    proof=dict(kind=kind,complete_interpretation=True,user_evidence=frame['evidence'],program=frame['task'] if 'task' in frame else {k:v for k,v in frame.items() if k not in ('evidence','query')},
               query=q,result=result,temporary=bool(frame.get('temporary')),assistant_text_as_evidence=False,native_generated_code=False)
    proof['program_sha256']=hashlib.sha256(json.dumps(proof['program'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    answer['natural_reasoning']=proof
    return answer


def reply(messages):
    if not messages or len(messages)>256 or sum(len(m['content']) for m in messages)>400000:return None
    current=None;view=None;last=len(messages)-1
    for i,m in enumerate(messages):
        if m['role']!='user':continue
        text=m['content'].strip()
        # Typed tasks own all their rows/frames/clauses. Establish ownership
        # before the natural-language clause limit, and reset stale references.
        from .structured_input import read as structured_task
        if structured_task(text) is not None:
            current=view=None;continue
        if len(text)>12000:
            current=None;continue
        try:
            if RESET.fullmatch(text):current=None;continue
            # A one-clause follow-up composes the previous complete task before
            # being considered a different problem. It cannot drop a second
            # sentence/condition from a new request.
            handled=False
            if current is not None and current.get('kind')=='quantities' and re.match(r'(?i)^(?:add|also|update)\s*:',text):
                current,view,handled=quantity_update_turn(current,text,i)
            if current is not None and current.get('kind')!='invalid' and len(parts(text))==1:
                if not handled:current,view,handled=update(current,text,i)
            if not handled:
                new=fresh(text,i)
                if new is not None:current=view=new;handled=True
                elif current is not None and SOCIAL.fullmatch(text):continue
                elif current is not None and current.get('kind')=='invalid' and re.match(r'(?i)^(?:how many|how much|who|why|which|what about|what if|and after|after)\b',text):raise Unclear('An earlier problem turn was unsupported; supply a complete corrected problem or reset it before continuing.')
                elif current is not None and re.match(r'(?i)^(?:what if|why|and after|after|also|then|now|what about)\b',text):raise Unclear('The follow-up contains an unsupported reference, condition or action; no subset was solved.')
                else:current=view=None
            if i==last and handled:
                return render(view)
        except (Unclear,fc.Unclear,wr.Unclear,KeyError,TypeError,OverflowError,RecursionError) as exc:
            if i==last:return dict(route='chat/natural-clarify',response='I could not interpret the complete problem safely: '+str(exc),sources=[],
                natural_reasoning=dict(complete_interpretation=False,rejected_message=i,assistant_text_as_evidence=False))
            if not (current is not None and re.match(r'(?i)^what if\b',text)):current=dict(kind='invalid')
    return None
