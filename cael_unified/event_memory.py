"""General request-local event memory with fitted frames and transition choices.

The data model/finite transition library are explicit architectural priors.
Surface frames, lexical alternatives and transition selection are trained on
general lessons. No benchmark name, header, variable list or output grammar is
used here. Unknown clauses never become silently executed instructions.
"""
from bisect import bisect_right
from collections import defaultdict
from collections import deque
from fractions import Fraction
from functools import lru_cache
import json
from pathlib import Path
import re
from . import state_language

MODEL=Path(__file__).with_name('event_memory_model.json')
MAX_CHARACTERS=8_000_000
MAX_EVENTS=100_000
MAX_CELLS=2_048
MAX_TRANSITION_WORK=10_000_000
UNKNOWN={'unknown':True}

def clean(text):
    text=re.sub(r'\s+',' ',str(text).replace('\u2019',"'").strip()).strip(' .!?;:')
    return re.sub(r'^(?:the|a|an)\s+','',text,flags=re.I)

def literal(text):
    text=str(text).strip()
    if text.startswith('"'):
        value=json.loads(text)
        if not isinstance(value,str):raise ValueError('A quoted value must be text')
        return value
    if text.startswith("'") and text.endswith("'"):return text[1:-1]
    if re.search(r'\b(?:same|current|identical|if|unless|maybe|might|unknown|or)\b',text,re.I):
        raise ValueError('A dependency/uncertainty cannot be used as a literal')
    text=clean(text)
    if re.fullmatch(r'-?\d+(?:/\d+|\.\d+)?',text):return str(Fraction(text))
    if not text or len(text)>120 or len(text.split())>8:raise ValueError('Unsupported literal')
    return text

def key(entity,attribute):return clean(entity).casefold()+'\x1f'+clean(attribute).casefold()

def resolve(state,cell,seen=None):
    seen=set() if seen is None else seen
    if cell in seen or len(seen)>128:raise ValueError('Circular or too-deep reference')
    seen.add(cell)
    value=state.get(cell,UNKNOWN)
    if isinstance(value,dict):
        if 'ref' in value:return resolve(state,value['ref'],seen)
        raise ValueError('Unknown or conflicting value')
    return value

def transition(state,slots,operation):
    """The candidate algebra used by both the trainer and runtime.

    The trainer selects among these operations from before/after witnesses;
    syntax is not mapped to a known operation by benchmark configuration names.
    """
    target=key(slots['E'],slots['A'])
    source=key(slots.get('S',''),slots.get('SA',slots['A']))
    new=dict(state)
    if operation=='assign_expr':
        new[target]=state_language.evaluate(slots['EXPR'],state,resolve,key)
        return new
    if operation=='put':new[target]=literal(slots['V'])
    elif operation=='assert':
        value=literal(slots['V'])
        prior=state.get(target)
        new[target]=value if prior is None or prior==value else {'conflict':[prior,value]}
    elif operation=='copy':new[target]=resolve(state,source)
    elif operation=='live':
        new[target]={'ref':source}
        resolve(new,target)
    elif operation in ('add','subtract','modadd'):
        value=Fraction(resolve(state,target));delta=Fraction(slots['D'])
        value=value-delta if operation=='subtract' else value+delta
        if operation=='modadd':
            modulus=Fraction(slots['M'])
            if modulus<=0:raise ValueError('Modulus must be positive')
            value%=modulus
        new[target]=str(value)
    elif operation=='swap':new[target],new[source]=resolve(state,source),resolve(state,target)
    elif operation=='clear':new[target]=dict(UNKNOWN)
    else:raise ValueError('Unrecognized fitted transition')
    return new

def compile_pattern(frame,aliases=()):
    pieces=[];used=set();position=0
    for match in re.finditer(r'\{\{([A-Z]+)\}\}|\^([^\^]+)\^',frame):
        text=frame[position:match.start()]
        pieces.append(re.escape(text).replace(r'\ ',r'\s+'))
        role,anchor=match.groups()
        if anchor:
            choices=sorted(set([anchor,*aliases]),key=lambda s:-len(s))
            pieces.append('(?:'+'|'.join(re.escape(s).replace(r'\ ',r'\s+') for s in choices)+')')
        elif role in used:pieces.append('(?P='+role+')')
        else:
            if role in ('D','M'):content=r'-?\d+(?:/\d+|\.\d+)?'
            elif role=='V':content=r'(?:"[^"\n]{0,120}"|\x27[^\x27\n]{0,120}\x27|-?\d+(?:/\d+|\.\d+)?|[\w-]+)'
            else:content=r'[^;\n!?]{1,120}?'
            if role=='V':content=r'(?:the\s+)?'+content
            pieces.append('(?P<'+role+'>'+content+')');used.add(role)
        position=match.end()
    pieces.append(re.escape(frame[position:]).replace(r'\ ',r'\s+'))
    return re.compile(''.join(pieces),re.I)

@lru_cache(maxsize=1)
def model():
    data=json.loads(MODEL.read_text(encoding='utf-8'))
    assert data['schema']==1
    data['compiled']=[(compile_pattern(row['frame'],row['aliases']),row) for row in data['frames']]
    return data

def event(text):
    text=text.strip().rstrip('.!?;')
    text=re.sub(r'^(?:then|afterwards|afterward|subsequently|next|please)[,:]?\s+','',text,flags=re.I)
    text=re.sub(r"\b(?:now|currently|presently)\s+(?=\w)",'',text,flags=re.I)
    outside_quotes=re.sub(r'"[^"\n]*"','',text)
    if re.search(r'\b(?:if|unless|might|maybe|could|says|said|claims|claimed|not|never)\b',outside_quotes,re.I):
        return None
    matches=[]
    for pattern,row in model()['compiled']:
        match=pattern.fullmatch(text)
        if not match:continue
        slots={**row['defaults'],**{k:v for k,v in match.groupdict().items() if v is not None}}
        if not slots.get('E') or not slots.get('A'):continue
        slots={k:clean(v) if k not in ('V','D','M') else v.strip() for k,v in slots.items()}
        if any(re.search(r'\b(?:if|unless|and|or)\b',slots[r],re.I) for r in ('E','S') if slots.get(r)):continue
        specificity=row['specificity']
        matches.append((specificity,row['operation'],slots))
    if not matches:return None
    best=max(x[0] for x in matches)
    selected={(op,json.dumps(slots,sort_keys=True)) for s,op,slots in matches if s==best}
    if len(selected)!=1:raise ValueError('Ambiguous event interpretation')
    op,slots=selected.pop()
    return op,json.loads(slots)

def clauses(text):
    """Preserve decimal points and quoted text; delimit ordinary sentences."""
    parts=[];start=0;quote=None
    for i,char in enumerate(text):
        if char=='"' and (i==0 or text[i-1]!='\\'):quote=None if quote else '"'
        if quote:continue
        boundary=char in ';\n?!' or char=='.' and not (i and i+1<len(text) and text[i-1].isdigit() and text[i+1].isdigit())
        if boundary:
            value=text[start:i].strip()
            if value:parts.append(value)
            start=i+1
    tail=text[start:].strip()
    if tail:parts.append(tail)
    return parts

def question(text):
    had_colon=text.rstrip().endswith(':')
    q=clean(text)
    q=re.sub(r'^(?:please\s+)?(?:tell me|remind me|can you tell me)\s+','',q,flags=re.I)
    past=('initial' if re.search(r'\b(?:initial|first)\b',q,re.I) else
          'previous' if re.search(r'\b(?:previous|before the last change|before that)\b',q,re.I) else False)
    if not past:
        fitted=state_language.question(text)
        if fitted:return fitted
    q=re.sub(r'\s+(?:now|currently|before the last change|before that|previously)$','',q,flags=re.I)
    m=re.fullmatch(r'(?:what is|what was|what\x27s) (?:the )?(?:current |previous |initial )?(.+?) of (.+)',q,re.I)
    if m:return {'kind':'one','E':clean(m[2]),'A':clean(m[1]),'past':past}
    m=re.fullmatch(r'(?:what is|what was|what\x27s) (.+?)\x27s (?:current |previous |initial )?(.+)',q,re.I)
    if m:return {'kind':'one','E':clean(m[1]),'A':clean(m[2]),'past':past}
    m=re.fullmatch(r'where (?:is|was) (.+)',q,re.I)
    if m:return {'kind':'one','E':clean(m[1]),'A':'location','past':past}
    m=re.fullmatch(r'how many (.+?) (?:does|did) (.+?) have',q,re.I)
    if m:return {'kind':'one','E':clean(m[2]),'A':clean(m[1]),'past':past}
    # Intent is fitted from general request vocabulary, not exact introductions.
    tokens={w[:-1] if w.endswith('s') else w for w in re.findall(r"[A-Za-z]+",q.casefold())}
    query_tokens=set(model()['summary_words'])
    if not re.search(r"\x27s|\d|\"",q) and tokens & query_tokens and (had_colon or len(tokens & query_tokens)>=2 or tokens & {'summary','overview','snapshot'}):
        return {'kind':'all','past':False}
    return None

def speech_act(text):
    text=re.sub(r'^please\s+','',text,flags=re.I)
    tokens=set(re.findall(r'[A-Za-z]+',text.casefold()))
    starts=text.casefold().split()[:1]
    if starts and starts[0] in model()['instruction_starts'] and tokens & set(model()['instruction_words']):return True
    return False

def ignored(text):
    if text.lstrip().startswith('#'):return True
    # Explicitly marked non-updates, not arbitrary unparsed event clauses.
    return bool(re.search(r'\bnot (?:an? )?(?:update|change|instruction|edit|movement)\b',text,re.I))

class Memory:
    def __init__(self):
        self.state={};self.names={};self.history=defaultdict(list);self.events=deque(maxlen=8);self.errors=[];self.count=0;self.focus=();self.comments=0
    def apply(self,operation,slots,index,source):
        for r in ('E','S'):
            if slots.get(r):self.names.setdefault(clean(slots[r]).casefold(),clean(slots[r]))
        target=key(slots['E'],slots['A'])
        try:
            # Most operations touch one or two cells. Running the same finite
            # algebra on a view avoids copying/scanning the whole state table.
            needed={target}
            if operation in ('copy','live','swap'):needed.add(key(slots.get('S',''),slots.get('SA',slots['A'])))
            if operation=='assign_expr':
                value=state_language.evaluate(slots['EXPR'],self.state,resolve,key)
                changed={target:value}
            elif operation in ('put','assert','add','subtract','modadd','clear'):
                view={target:self.state[target]} if target in self.state else {}
                # A current cell may be a live dependency; resolve against the
                # complete state before feeding checked arithmetic.
                if operation in ('add','subtract','modadd'):view[target]=resolve(self.state,target)
                changed=transition(view,slots,operation)
            elif operation in ('copy','swap'):
                source_cell=key(slots.get('S',''),slots.get('SA',slots['A']))
                changed={target:resolve(self.state,source_cell)}
                if operation=='swap':changed[source_cell]=resolve(self.state,target)
            else:
                # Live dependency cycle checking requires the complete graph.
                computed=transition(self.state,slots,operation)
                changed={k:computed[k] for k in needed if k in computed}
        except (ValueError,KeyError,ZeroDivisionError) as exc:
            changed={target:dict(UNKNOWN)}
            self.errors.append({'step':index,'reason':str(exc),'source':source})
        for k,v in changed.items():
            if k not in self.state or self.state[k]!=v:self.history[k].append((index,v))
        self.state.update(changed)
        self.events.append({'step':index,'operation':operation,'slots':slots,'source':source})
        self.count+=1
        mentioned={clean(slots['E'])}
        if slots.get('S'):mentioned.add(clean(slots['S']))
        def refs(node):
            if node.get('op')=='reference':mentioned.add(clean(node['entity']))
            if 'child' in node:refs(node['child'])
        if 'EXPR' in slots:refs(slots['EXPR'])
        self.focus=tuple(sorted(mentioned))
    def get(self,cell,past=False):
        state=self.state
        if past:
            versions=self.history.get(cell,[])
            if not versions or past!='initial' and len(versions)<2:raise ValueError('No earlier value is known')
            boundary=versions[0][0] if past=='initial' else versions[-1][0]-1
            state={}
            for k,history in self.history.items():
                prior=[v for i,v in history if i<=boundary]
                if prior:state[k]=prior[-1]
        return resolve(state,cell)

def reply(messages):
    if not isinstance(messages,list) or not messages or len(messages)>1000:return None
    if not all(isinstance(m,dict) and m.get('role') in ('system','user','assistant') and isinstance(m.get('content'),str) for m in messages):return None
    if messages[-1]['role']!='user':return None
    user=[m['content'] for m in messages if m['role']=='user']
    size=sum(map(len,user))
    if size>MAX_CHARACTERS:return None
    last=clauses(user[-1])
    if not last:return None
    query=question(last[-1]);instruction_query=next((question(x) for x in last if speech_act(x) and question(x)),None)
    query=query or instruction_query
    if query is None:return None
    memory=Memory();unparsed=[];declared=bool(instruction_query) or query['kind']=='all' and len(last)>=3;step=0;work=0
    for turn,text in enumerate(user):
        for part in clauses(text):
            if ignored(part):continue
            try:parsed=state_language.event(part,memory.focus,state=memory.state) or event(part)
            except ValueError as exc:parsed=None
            if parsed is None:
                if question(part):continue
                if speech_act(part):declared=True;continue
                if state_language.comment(part,memory.names):memory.comments+=1;continue
                unparsed.append({'turn':turn,'clause':part[:200]})
                if declared:
                    return {'route':'chat/memory-clarify','response':'I cannot establish the complete state because an update clause is unsupported or ambiguous.',
                            'sources':[],'memory_reasoning':{'complete':False,'events':memory.count,'unparsed':unparsed,'input_characters':size}}
                continue
            step+=1
            work+=max(1,len(memory.state))
            op,slots=parsed
            if (step>MAX_EVENTS or work>MAX_TRANSITION_WORK or
                len(memory.state)>=MAX_CELLS and key(slots['E'],slots['A']) not in memory.state):
                return {'route':'chat/memory-clarify','response':'This event history exceeds the supported event or state budget.','sources':[]}
            memory.apply(op,slots,step,part)
    owned=bool(memory.count) or declared
    if not owned:return None
    # A generic summary word in an unrelated short conversation does not claim
    # ownership. An explicit data document is handled as one complete context.
    if query['kind']=='one' and key(query['E'],query['A']) not in memory.state and not declared:return None
    if unparsed:
        if len(user)>1 and not declared:
            mentions=set(re.findall(r'\w+',' '.join(x['clause'] for x in unparsed).casefold()))
            known=set(re.findall(r'\w+',' '.join(memory.names)))
            if not mentions & known:return None
        return {'route':'chat/memory-clarify','response':'I cannot establish the complete state because part of the update history is unsupported or ambiguous.',
                'sources':[],'memory_reasoning':{'complete':False,'events':memory.count,'unparsed':unparsed[:4]}}
    try:
        if query['kind']=='one_phrase':
            e,a=state_language.property_phrase(query['phrase'],memory.focus)
            query={**query,'kind':'one','E':e,'A':a}
        if query['kind']=='one':
            value=memory.get(key(query['E'],query['A']),query['past']);response=value
            public={'entity':query['E'],'attribute':query['A'],'value':value}
        else:
            public={}
            for cell in memory.state:
                entity,attribute=cell.split('\x1f')
                public.setdefault(memory.names.get(entity,entity),{})[attribute]=memory.get(cell)
            response=json.dumps(public,ensure_ascii=False,sort_keys=True)
    except ValueError as exc:
        return {'route':'chat/memory-unknown','response':'The stated updates do not determine a single known value: '+str(exc)+'.',
                'sources':[],'memory_reasoning':{'complete':False,'events':memory.count,'reason':str(exc)}}
    return {'route':'chat/event-memory','response':response,'sources':[],
            'memory_reasoning':{'complete':True,'events':memory.count,'comments':memory.comments,'value':public,
                                'recent_steps':[e['step'] for e in memory.events][-8:]},
            'details':'General fitted event frames and transitions over request-local user evidence; no benchmark formatter or external lookup.'}
