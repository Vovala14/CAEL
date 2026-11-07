"""Source-covered rule, precedence and chronological event compilation.

Symbolic relations and finite state only. No learned answer table or neural path.
"""
import re
from .interpretation_common import ATOM,Result,TaskError,alphabet,boundary,clauses,clean,spans,symbol

def relation_atom(s):
    s=re.sub(r'(?i)^(?:(?:the|an?) )?(?:(?:class|category|type|group)\s+)?','',s.strip())
    return symbol(s)

def membership(text,question=False):
    t=text.strip().strip('"\'').rstrip(' ?.');negative=False
    if question and re.match(r'(?i)^is ',t):
        t=t[3:];m=re.fullmatch(rf'({ATOM}?) (not )?(?:an? |the |in (?:the )?(?:class |category |group )?|of type )(.+)',t,re.I)
        if m:return symbol(m[1]),relation_atom(m[3]),bool(m[2])
    m=re.fullmatch(rf'({ATOM}?) (does not belong to|is not a member of|is a member of|is classified as|has type|belongs to|is not|is) (.+)',t,re.I)
    if not m:return None
    return symbol(m[1]),relation_atom(m[3]),m[2].casefold() in ('is not','does not belong to','is not a member of')

def _logic_query(q):
    q=q.strip().rstrip(' ?.');q=re.sub(r'(?i)^(?:question|query)\s*:\s*','',q)
    q=re.sub(r'(?i)^(?:(?:under|using) open[- ]world (?:logic|assumptions),?\s*)','',q)
    quoted=re.search(r'''(["'])(.+?)\1''',q)
    if quoted:
        tail=q[quoted.end():]
        if not re.fullmatch(r'(?i)\s*(?:(?:as )?(?:true|false|unknown|undetermined|inconsistent|or|and|,|/|\s)+)?',tail):return None
        if not re.fullmatch(r'(?i)(?:is|classify|evaluate|judge)(?: the (?:claim|statement|proposition))?\s*',q[:quoted.start()]):return None
        return membership(quoted[2])
    q=re.sub(r'(?i)^(?:classify|judge|evaluate|determine)(?: the)? (?:claim|statement|proposition)(?: that)?\s*','',q)
    q=re.sub(r'(?i)^(?:does (?:it|the information|the evidence) (?:follow|establish)(?: that)?|can (?:we|you) conclude(?: that)?|is it true that|prove(?: that)?|what follows about)\s*','',q)
    # A truth-value legend must have its complete standard meanings. It is
    # metadata, not additional facts about the entities.
    if ':' in q:
        q,legend=q.split(':',1)
        words=set(re.findall(r'[a-z]+',legend.casefold()))
        allowed=set('true false unknown undetermined inconsistent conflicting means proved proven negation its is neither both and or not established supported contradicted the statement claim'.split())
        if not words<=allowed:raise TaskError('The answer legend contains an unsupported logical convention.')
        if not {'true','false'}<=words:raise TaskError('State the complete logical answer convention.')
        standard=re.fullmatch(r'(?i)\s*true means (?:proved|proven|supported),? false means (?:its|the) negation is (?:proved|proven|supported),? unknown means neither,? and (?:inconsistent|conflicting) means both\s*',legend)
        if not standard:raise TaskError('The truth-value legend must preserve the standard proved/negated/neither/both meanings.')
    return membership(q,True) or membership(q)

def logic(text,reasoner):
    parts=clauses(text)
    if len(parts)<2:return None
    if not re.search(r'(?i)\b(?:every|all|each|anything|everything|implies|open[- ]world|premises|facts|rules)\b|(?:^|\n)(?:query|question)\s*:|true,? false',text):return None
    if not re.match(r'(?i)^(?:is\b|under\b|using\b|classify\b|judge\b|evaluate\b|determine\b|question\s*:|query\s*:|does\b|can\b|prove\b|what follows about\b)',parts[-1]):return None
    if any(re.search(r'(?i)\band\b',p) for p in parts[:-1]) and not re.search(r'(?i)\b(?:class|category|belongs|type)\b',text):return None
    q=_logic_query(parts[-1])
    if q is None:return None
    # A local scenario, not an unsupported attempt to answer general knowledge.
    if not any(re.search(r'(?i)\b(?:is|has|every|all|each|anything|belongs|implies|classified)\b',p) for p in parts[:-1]):return None
    facts=[];rules=[];used=[]
    for raw in parts[:-1]:
        p=re.sub(r'(?i)^(?:facts|premises|given|rules|scenario|context)\s*:\s*','',raw).strip()
        if not p:used.append(raw);continue
        if re.fullmatch(r'(?i)(?:use|consider) only (?:these|the stated|the supplied) (?:facts|statements|premises)(?:,? (?:a )?missing (?:fact|statement) is not false,? and (?:an )?implication cannot be reversed)?',p):used.append(raw);continue
        if re.fullmatch(r'(?i)(?:no fact implies its converse|use open[- ]world (?:logic|reasoning)|absence (?:of a fact )?(?:is|means) (?:not falsity|unknown))',p):used.append(raw);continue
        if re.fullmatch(r'(?i)(?:an? )?(?:missing|unstated|absent) (?:fact|statement) (?:is not false|is unknown|does not imply (?:its )?negation)(?:,? and (?:an? )?implication cannot be reversed)?',p):used.append(raw);continue
        boundary(p)
        m=re.fullmatch(r'(?i)(?:anything|everything|any entity|any object) (?:in (?:the )?(?:class|category|group)|that is|of type|with type) (.+?) (?:also belongs to|belongs to|is also|is) (.+)',p)
        if not m:m=re.fullmatch(r'(?i)(?:all|every|each|any) (.+?) (?:are also|is also|are|is|belong to|belongs to|must be) (.+)',p)
        if not m:m=re.fullmatch(r'(?i)if (?:something|an? (?:object|entity|thing)) (?:is|belongs to) (.+?)(?:,)? then (?:it|that entity|that object) (?:is|belongs to) (.+)',p)
        if not m:m=re.fullmatch(r'(?i)(.+?) implies (.+)',p)
        if m:
            from .reasoning_logic import LogicCA
            grammar=LogicCA(reasoner().model)
            source=grammar.noun(relation_atom(m[1]),plural=bool(re.match(r'(?i)^all\b',p)))
            target=m[2].strip();neg=bool(re.match(r'(?i)^not ',target))
            target=grammar.noun(relation_atom(re.sub(r'(?i)^not ','',target)),plural=bool(re.search(r'(?i)\bare(?: also)?\b',p)))
            rules.append((source,target,neg));used.append(raw);continue
        f=membership(p)
        if f is None:raise TaskError('A local logical premise could not be compiled in full: '+p[:100])
        facts.append(f);used.append(raw)
    if not facts or len(facts)>128 or len(rules)>128:return None
    mapping={}
    def bound(kind,v):
        key=(kind,v)
        if key not in mapping:mapping[key]='native'+alphabet(len(mapping))+'q'
        return mapping[key]
    canonical=[f'{bound("entity",e)} is {"not " if neg else ""}{bound("property",p)}.' for e,p,neg in facts]
    canonical += [f'Every {bound("property",a)} is {"not " if neg else ""}{bound("property",b)}.' for a,b,neg in rules]
    query=f'{bound("entity",q[0])} is {"not " if q[2] else ""}{bound("property",q[1])}'
    from .reasoning_logic import LogicCA,Unparsed
    try:answer=LogicCA(reasoner().model).query(' '.join(canonical),query)
    except Unparsed as exc:raise TaskError(str(exc)) from exc
    return Result(answer['answer'],'logic',{'coverage':spans(text,parts),'facts':facts,'rules':rules,'query':q,
        'canonical_premises':canonical,'canonical_query':query,'proof':answer,'symbols':{f'{k[0]}:{k[1]}':v for k,v in mapping.items()}})

def _order_query(q):
    q=re.sub(r'(?i)^(?:question|query)\s*:\s*','',q.strip()).rstrip(' ?.').casefold()
    m=re.search(r'\b(?:immediately|directly|right) (after|before|following|preceding) (.+?)(?: in (?:that|the) (?:sequence|order))?$',q)
    if m:return ('after' if m[1] in ('after','following') else 'before',symbol(m[2]))
    m=re.fullmatch(r'(?:name|give|identify|find|select|choose|which|what)(?: the| item| object| entry| is| comes| one| earliest| final)* (?:item )?(?:comes |is )?(first|last|earliest|latest|final)(?: item| one)?(?: in (?:that|the) (?:sequence|order))?',q)
    if m:return ('first' if m[1] in ('first','earliest') else 'last',None)
    if re.search(r'\b(?:earliest|first|final|last|latest) (?:item|object|entry)\b',q) and re.match(r'(?:name|give|identify|find|select|choose|which|what)\b',q):return ('unsupported',None)
    m=re.fullmatch(r'(?:which|what) (?:item|object|entry) (?:comes|is) (?:in )?(?:position )?(\d+)(?:st|nd|rd|th)?',q)
    if m:return ('index',int(m[1])-1)
    m=re.fullmatch(r'(?:give|what is|find)(?: the)? (?:complete )?(?:order|sequence)',q)
    if m:return ('all',None)
    return None

def order(text):
    parts=clauses(text)
    if len(parts)<2:return None
    query=_order_query(parts[-1])
    if query is None:return None
    if not any(re.search(r'(?i)\b(?:before|after|ahead of|behind|precedes|follows)\b',p) for p in parts[:-1]):return None
    boundary(parts[-1])
    if query[0]=='unsupported':raise TaskError('The complete ordering question contains an unsupported qualifier.')
    # Richer explicit constraints belong to the same finite-domain engine used
    # by ordinary reasoning. Do not reject them in the precedence-only reader.
    if re.match(r'(?i)^(?:items|people|objects|participants|runners|books|cars|order)\s*:', parts[0]) and any(
            re.search(r'(?i)\b(?:immediately|directly|adjacent|next to|between|not|first|last|second|third|fourth|fifth)\b', p)
            for p in parts[1:-1]):
        from .reasoning_order import ordering
        try: result = ordering('. '.join(parts[:-1]), parts[-1])
        except ValueError as exc: raise TaskError(str(exc)) from exc
        return Result(result['answer'], 'ordering', {'coverage': spans(text, parts),
                      'engine': 'finite-domain-constraint-automaton', 'proof': result})
    names=[];edges=[]
    for raw in parts[:-1]:
        p=raw.strip()
        listed=re.fullmatch(r'(?i)(?:items|objects|entries|participants)\s*:\s*(.+)',p)
        if listed:
            names.extend(symbol(x) for x in re.split(r'\s*,\s*|\s+and\s+',listed[1]));continue
        if re.fullmatch(r'(?i)(?:all|each) (?:items|objects|entries) (?:occur|occurs|appear|appears) once',p):continue
        if re.fullmatch(r'(?i)(?:the following|these) (?:constraints|statements|clues) describe (?:their|the) order',p):continue
        boundary(p)
        p=re.sub(r'(?i) in the (?:sequence|order)$','',p)
        m=re.fullmatch(rf'(?i)({ATOM}?) (?:comes |is |occurs |appears )?(before|after|ahead of|behind|precedes|follows) ({ATOM})(?: in the (?:sequence|order))?',p)
        if not m:raise TaskError('An ordering constraint is unsupported or incomplete: '+p[:100])
        a,b=symbol(m[1]),symbol(m[3]);relation=m[2].casefold()
        if relation in ('after','behind','follows'):a,b=b,a
        names.extend((a,b));edges.append((a,b))
    names=list(dict.fromkeys(names))
    if not 2<=len(names)<=64 or len(edges)>512:raise TaskError('Use 2–64 distinct items and at most 512 precedence constraints.')
    reach={a:{b for x,b in edges if x==a} for a in names}
    # Monotone relation-cell fixed point, not factorial permutation search.
    for _ in range(len(names)):
        following={a:reach[a]|set().union(*(reach[b] for b in reach[a])) if reach[a] else set() for a in names}
        if following==reach:break
        reach=following
    if any(a in reach[a] for a in names):raise TaskError('The stated order contains a cycle; no linear order satisfies it.')
    predecessors={b:{a for a in names if b in reach[a]} for b in names}
    op,arg=query;possible=[]
    if op=='first':possible=[a for a in names if not predecessors[a]]
    elif op=='last':possible=[a for a in names if not reach[a]]
    elif op=='index':
        if not 0<=arg<len(names):raise TaskError('The requested position is outside the stated order.')
        possible=[a for a in names if len(predecessors[a])<=arg<=len(names)-1-len(reach[a])]
    elif op in ('after','before'):
        if arg not in names:raise TaskError('The queried item is absent from the constraints.')
        rel=reach if op=='after' else predecessors
        # Adjacent candidates are precisely incomparable nodes or cover edges;
        # if the anchor may be last/first, no next/previous item is guaranteed.
        if not rel[arg]:possible=[]
        else:possible=[b for b in names if b!=arg and arg not in rel[b] and not any(x in rel[arg] and b in rel[x] for x in names if x not in (arg,b))]
    else:
        if any(not (a in reach[b] or b in reach[a]) for i,a in enumerate(names) for b in names[i+1:]):possible=[]
        else:possible=[', '.join(sorted(names,key=lambda a:len(predecessors[a])))]
    value=possible[0] if len(possible)==1 else 'unknown'
    return Result(value,'ordering',{'coverage':spans(text,parts),'entities':names,'edges':edges,'query':query,
        'transitive_relation':{a:sorted(v) for a,v in reach.items()},'possible_answers':possible,'unique':len(possible)==1})

def _state_query(q):
    q=re.sub(r'(?i)^(?:question|query)\s*:\s*','',q.strip()).rstrip(' ?.').casefold()
    q=re.sub(r'^(?:after (?:the )?(?:last|final) (?:entry|event|update),?\s*)','',q)
    m=re.fullmatch(r'(?:where (?:is|was)|(?:give|name|find|state|report|what is)(?: the)? (?:current|latest|final|present|last known) (?:location|position|room) (?:of|for)) (.+?)(?: now| currently| at the end)?',q)
    if m:return ('location',symbol(m[1]))
    m=re.fullmatch(r'who (?:has|holds|owns|is carrying) (?:the )?(.+)',q)
    if m:return ('owner',symbol(m[1]))
    return None

def state(text,reasoner):
    parts=clauses(text)
    if len(parts)<2:return None
    query=_state_query(parts[-1])
    if query is None:return None
    if not any(re.search(r'(?i)\b(?:went|moved|relocated|entered|arrived|walked|travelled|traveled|journeyed|is in|is at|holds|picked up|gave|gives|dropped|location becomes)\b',p) for p in parts[:-1]):return None
    events=[];reverse=False
    header_words=set('read this the following movement location log events event entries entry are is listed recorded ordered from earliest latest oldest newest to top bottom each replaces that person s previous position in chronological order timeline record updates update given all information complete'.split())
    for raw in parts[:-1]:
        p=re.sub(r'(?i)^(?:facts|events|log|timeline|context)\s*:\s*','',raw).strip()
        if not p:continue
        if re.fullmatch(r'(?i)(?:events|entries|updates)(?: are)? (?:listed |recorded )?(?:in )?(?:reverse chronological order|latest first|newest first)',p):reverse=True;continue
        words=set(re.findall(r'[a-z]+',p.casefold()))
        if words and words<=header_words and words&{'log','events','entries','chronological','updates'}:continue
        boundary(p)
        m=re.fullmatch(rf'(?i)({ATOM}?) is either in (?:the )?({ATOM}?) or (?:the )?({ATOM})',p)
        if m:events.append(('uncertain',symbol(m[1]),symbol(m[2]),symbol(m[3])));continue
        m=re.fullmatch(rf'(?i)({ATOM}?) is (?:not|no longer) in (?:the )?({ATOM})',p)
        if m:events.append(('exclude',symbol(m[1]),symbol(m[2])));continue
        m=re.fullmatch(rf'(?i)({ATOM}?) (?:went|moved|relocated|walked|travelled|traveled|journeyed|returned)(?: back)? (?:to|into) (?:the )?({ATOM})',p)
        if m:events.append(('move',symbol(m[1]),symbol(m[2])));continue
        m=re.fullmatch(rf'(?i)({ATOM}?) (?:entered|visited) (?:the )?({ATOM})',p)
        if m:events.append(('move',symbol(m[1]),symbol(m[2])));continue
        m=re.fullmatch(rf'(?i)({ATOM}?) (?:is|was|is currently|was initially)(?: located)? (?:in|at|inside) (?:the )?({ATOM})',p)
        if m:events.append(('move',symbol(m[1]),symbol(m[2])));continue
        m=re.fullmatch(rf'(?i)({ATOM}?) (?:arrived|arrives) at (?:the )?({ATOM})',p)
        if m:events.append(('move',symbol(m[1]),symbol(m[2])));continue
        m=re.fullmatch(rf'(?i)({ATOM}?) moved from (?:the )?({ATOM}?) to (?:the )?({ATOM})',p)
        if m:events.append(('from',symbol(m[1]),symbol(m[2]),symbol(m[3])));continue
        m=re.fullmatch(rf'(?i)({ATOM}?) (?:holds|has|got|picked up|takes|took) (?:the )?({ATOM})',p)
        if m:events.append(('take',symbol(m[1]),symbol(m[2])));continue
        m=re.fullmatch(rf'(?i)({ATOM}?) (?:gave|gives|handed|hands|passed) (?:the )?({ATOM}?) to ({ATOM})',p)
        if m:events.append(('give',symbol(m[1]),symbol(m[2]),symbol(m[3])));continue
        m=re.fullmatch(rf'(?i)({ATOM}?) (?:dropped|drops|put down) (?:the )?({ATOM})',p)
        if m:events.append(('drop',symbol(m[1]),symbol(m[2])));continue
        m=re.fullmatch(rf'(?i)({ATOM}?)\x27s location becomes ({ATOM}?)\x27s current location',p)
        if m:events.append(('copy',symbol(m[1]),symbol(m[2])));continue
        raise TaskError('A chronological event could not be compiled in full: '+p[:100])
    if not events or len(events)>128:raise TaskError('Use a nonempty log of at most 128 explicit events.')
    if reverse:events.reverse()
    mapping={};back={}
    def name(v):
        if v not in mapping:
            mapped='native'+alphabet(len(mapping))+'q';mapping[v]=mapped;back[mapped]=v
        return mapping[v]
    from .reasoning_world import WorldCA
    world=WorldCA(reasoner().model);canonical=[];known_actors=set();known_objects=set()
    for index,event in enumerate(events,1):
        op,actor,value,*extra=event
        if actor in ('he','she','they','it'):
            if len(known_actors)!=1:raise TaskError('A pronoun has more than one possible actor; name the person explicitly.')
            actor=next(iter(known_actors))
        known_actors.add(actor)
        if op in ('take','drop','give'):
            if value=='it':
                if len(known_objects)!=1:raise TaskError('The object pronoun has no unique referent.')
                value=next(iter(known_objects))
            known_objects.add(value)
        if op=='give':known_actors.add(extra[0])
        if op=='copy':
            cell=world.cells.get(name(value))
            if cell is None or len(cell.locations)!=1:raise TaskError('A copied location is not uniquely known at that event.')
            place=next(iter(cell.locations));event_text=f'{name(actor)} went to {place}'
        elif op=='from':
            cell=world.cells.get(name(actor))
            if cell and cell.locations and cell.locations!={name(value)}:raise TaskError('A departure location conflicts with the preceding event state.')
            event_text=f'{name(actor)} went to {name(extra[0])}'
        elif op=='move':event_text=f'{name(actor)} went to {name(value)}'
        elif op=='uncertain':event_text=f'{name(actor)} is either in {name(value)} or {name(extra[0])}'
        elif op=='exclude':event_text=f'{name(actor)} is not in {name(value)}'
        elif op=='take':event_text=f'{name(actor)} got {name(value)}'
        elif op=='drop':event_text=f'{name(actor)} dropped {name(value)}'
        else:
            old=world.cells.get(name(value))
            if old and old.owner not in (None,name(actor)):raise TaskError('The giver is not the established holder of the object.')
            event_text=f'{name(actor)} gave {name(value)} to {name(extra[0])}'
        try: world.apply(world.event(event_text),index)
        except ValueError as exc: raise TaskError(str(exc)) from exc
        canonical.append(event_text+'.')
    target_value=query[1]
    if target_value in ('he','she','they','it'):
        referents=known_objects if query[0]=='owner' else known_actors
        if len(referents)!=1:raise TaskError('The question pronoun has no unique referent.')
        target_value=next(iter(referents))
    target=name(target_value);q=('Where is '+target if query[0]=='location' else 'Who holds '+target)+'?'
    result=WorldCA(reasoner().model).query(' '.join(canonical),q)
    value=back.get(result['answer'],result['answer'])
    return Result(value,'state',{'coverage':spans(text,parts),'events':events,'reverse_source_order':reverse,
        'canonical_events':canonical,'query':query,'proof':result,'symbols':mapping})
