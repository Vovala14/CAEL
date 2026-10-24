# Modified for CAEL 0.2.1: portable bundle paths and package imports.
"""CAEL v4: CA router + v2 small-talk path + task/answer programs.
CA part: radius-1 integer CA (router) computes route and task-type counts. Everything else (lexicon cue sets,
templates, slot extraction, knowledge lookup, renderer) is AUTHORED and disclosed as hybrid."""
import re,json,gzip,sys
from pathlib import Path
TOK=re.compile(r"[a-z0-9]+(?:'[a-z]+)?|[?.!]")
CH=['imp','wh','aux','you','modal','fp','past','feel','qmark','code','rt','ident','write','define','compare','howto','rec','greet','math','opinion']
C={k:i for i,k in enumerate(CH)}
CUE={'imp':'write give tell explain list describe create make help suggest recommend summarize summarise show translate compare generate find calculate solve name provide please imagine pretend act draft compose design teach define plan build formulate rewrite expand prove proof turn return add edit fix convert summarise outline'.split(),
 'wh':"what why how when where who which whats what's where's who's how's whos".split(),'aux':'is are does do can could would should will was were did has have'.split(),
 'you':['you','your','yourself'],'modal':['can','could','would','will'],'fp':['i','my','me',"i'm","i've","i'd",'we','our'],
 'past':'was were went got had felt did saw made found lost took came told said bought ate'.split(),
 'feel':'feel felt sad happy angry upset scared afraid excited proud lonely nervous anxious grateful disappointed jealous embarrassed guilty glad terrified annoyed nostalgic feeling down tired depressed stressed bored'.split(),
 'code':'python javascript java code coding script program programming function sql html css c++ rust lua bash regex api typescript compile git linux docker json'.split(),
 'rt':"weather today's current currently latest news tonight tomorrow schedule scheduled calendar look search internet link stock price score".split(),
 'ident':'yourself sentient chatbot assistant ai bot creator creation created'.split(),
 'write':'letter email story poem essay song cv resume speech dialogue script haiku limerick lyrics joke tweet message cover'.split(),
 'define':'mean meaning definition define explain whats about'.split(),'compare':'difference differences vs versus compare compared better between'.split(),
 'rec':'recommend suggest best good ideas idea gift present should'.split(),'greet':'hi hello hey greetings'.split(),
 'math':'plus minus times divided sum calculate'.split(),'opinion':'think opinion believe favorite favourite'.split()}
LEX={}
for ch,ws in CUE.items():
    for w in ws: LEX.setdefault(w,[]).append(C[ch])
BOUND={'.','!','?'}
def cells_of(text):
    toks=TOK.findall(text.lower())
    cells=[]
    for t in toks:
        v=[0]*len(CH)
        for c in LEX.get(t,[]): v[c]+=1
        if t=='?': v[C['qmark']]=1
        if re.fullmatch(r'\d+',t): v[C['math']]+=0
        cells.append((t,v))
    return cells
class RouterCA:
    """Ring of token cells; a ready-carrier moves right one cell per tick (radius-1 rule).
    The carrier holds: counts per channel, clause-start bit, open question scope (wh/aux at clause start), closed-question count,
    imperative-at-clause-start count, and 'you'-modal adjacency. Each tick updates only from the left neighbour's carrier."""
    def __init__(s,cells): s.cells=cells; s.n=len(cells)
    def run(s):
        n=s.n; car=[None]*(n+1); car[0]=dict(cnt=[0]*len(CH),start=1,scope=0,closedq=0,impstart=0,youmod=0,prevmod=0,pos=0,qbare=0)
        for tick in range(n):            # synchronous update: only cell tick+1 changes, reading neighbour tick
            c=car[tick]; t,v=s.cells[tick]; d=dict(cnt=[a+b for a,b in zip(c['cnt'],v)],start=0,scope=c['scope'],closedq=c['closedq'],impstart=c['impstart'],youmod=c['youmod'],prevmod=0,pos=c['pos']+1,qbare=c['qbare'])
            if (c['start'] and (v[C['wh']] or v[C['aux']])) or (c['pos']<4 and v[C['wh']]): d['scope']=1
            if c['start'] and v[C['imp']]: d['impstart']+=1
            if c['prevmod'] and v[C['you']]: d['youmod']+=1
            d['prevmod']=1 if v[C['modal']] else 0
            if t in BOUND:
                if t=='?' and d['scope']: d['closedq']+=1
                elif t=='?': d['qbare']+=1
                d['scope']=0; d['start']=1; d['pos']=0
            car[tick+1]=d
        e=dict(car[n]);
        if e['scope']: e['closedq']+=1   # end of text closes an open question scope
        return e
def direct(cells):
    cnt=[sum(v[i] for _,v in cells) for i in range(len(CH))]; closedq=impstart=youmod=qbare=0; start=1; scope=0; prev=0; pos=0
    for t,v in cells:
        if (start and (v[C['wh']] or v[C['aux']])) or (pos<4 and v[C['wh']]): scope=1
        if start and v[C['imp']]: impstart+=1
        if prev and v[C['you']]: youmod+=1
        prev=1 if v[C['modal']] else 0; start=0; pos+=1
        if t in BOUND:
            if t=='?' and scope: closedq+=1
            elif t=='?': qbare+=1
            scope=0; start=1; pos=0
    if scope: closedq+=1
    return dict(cnt=cnt,start=start,scope=scope,closedq=closedq,impstart=impstart,youmod=youmod,prevmod=prev,pos=pos,qbare=qbare)
def route(messages):
    text=messages[-1]['content']; cells=cells_of(text); st=RouterCA(cells).run()
    k=st['cnt']; g=lambda c:k[C[c]]
    multiturn=len(messages)>1
    req=3*st['impstart']+2*st['closedq']+st['qbare']+2*st['youmod']+2*g('code')+g('write')*(1 if g('imp') else 0)+(1 if g('rt') and g('wh') else 0)
    if re.search(r"\b(i want you|act as|i would like|i need|i want to (?:find|know|learn|make|create|write|build|apply)|task:|how to|what can i do|should i|how can i|how do i|come up with|let's play|lets play)\b",text.lower()): req+=3
    talk=0
    if re.search(r"\b(have|has|did|do|were|was) (you|your \w+) ever\b|\bdo you (like|have|know|enjoy|remember)\b",text.lower()) and not st['impstart']: talk+=4
    talk=talk+2*min(g('feel'),2)+min(g('past'),3)+(3 if multiturn else 0)+(1 if g('fp')>=2 and not st['closedq'] else 0)
    if g('greet') and len(cells)<=4: typ='greet'
    elif req<=talk: typ='smalltalk'
    elif re.search(r"\b(chest pain|fever|temperature|bleeding|symptom|symptoms|heart attack|overdose|poison|suicid|can't breathe|pain in)\b",text.lower()): typ='health'
    elif g('ident') and g('you') or re.search(r"\b(what are you|who are you|your name|what can you do|are you an? )",text.lower()): typ='ident'
    elif g('code'): typ='code'
    elif g('rt') and (g('wh') or g('imp')) and re.search(r"\b(weather|today|current|latest|news|schedule|scheduled|tonight|look up|search|link|stock|price)\b",text.lower()): typ='realtime'
    elif g('write') and (g('imp') or g('you')): typ='write'
    elif re.search(r"\d+\s*[-+*/x]\s*\d+",text) : typ='math'
    elif g('compare') and re.search(r"\b(difference|vs\.?|versus|compare)\b",text.lower()): typ='compare'
    elif re.search(r"\bhow (do|can|should|to|would) (i|you|we|one)\b|\bhow to\b",text.lower()): typ='howto'
    elif g('rec') and (g('imp') or g('wh')): typ='recommend'
    elif re.search(r"\b(what|who) (is|are|was|were)\b|\bwhat does .* mean\b|\bexplain\b|\btell me about\b|\bdefine\b",text.lower()): typ='define'
    elif g('opinion') and g('you'): typ='opinion'
    else: typ='other'
    return typ,st,cells,dict(req=req,talk=talk)
# ---------------- answer programs (authored, disclosed) ----------------
STORE = {}
STORE={k:v for k,v in STORE.items() if not re.match(r'The [a-z]+ (is|are|was|were)\b',v['s']) and not re.match(r'(these|this|that|those|another|though|it|he|she|they|there|one|other|its|his|her|their|although|while|in|on|as|today|most|some|many|the tallest|the largest|the first)\b',k)}
STOP=set('hello hi hey want would like should best go generate act as a an the of to in on for and or is are was were do does what who how why which please can could you me i my tell explain about define meaning mean simple terms layman layman\'s detailed answer give some briefly short'.split())
def subj(text):
    t=text.strip().rstrip('?.! ')
    for pat in [r"what (?:is|are|was|were) (?:an? |the )?(.+)",r"who (?:is|was|are|were) (.+)",r"what does (.+?) mean",r"explain (?:to me )?(?:what )?(?:an? |the )?(.+?)(?: is| are| in .*| to .*)?$",r"tell me about (?:an? |the )?(.+)",r"define (?:an? |the )?(.+)",r"what(?:'s| is) (?:an? |the )?(.+)"]:
        m=re.search(pat,t,re.I)
        if m:
            s=re.split(r"[?,.;]| and | in simple| in layman| like i| for a | for an ",m.group(1))[0].strip().strip('"\'').lower()
            return s
    return None
def lookup(s):
    if not s: return None
    s=re.sub(r'^(an?|the) ','',s)
    for k in [s,'the '+s]:
        if k in STORE: return STORE[k]
    return None
def cite(e): return f" (From my knowledge store: {e['src']}{', article '+chr(39)+e['title']+chr(39) if e['title'] else ''}.)"
def topic(text):
    sj=subj(text)
    if sj and len(sj.split())<=6: return sj
    text=re.sub(r"^(hi|hello|hey)\b[^a-z]*","",text.strip(),flags=re.I)
    text=re.split(r"[?.!\n]",text)[0]
    w=[x for x in re.findall(r"[A-Za-z][A-Za-z0-9+'-]*",text) if x.lower() not in STOP]
    return ' '.join(w[:5]) if w else 'that'
def idk(text,what='answer that'):
    return f"I don't have reliable knowledge to {what}, so I'd rather not guess. A trusted reference or specialist source about {topic(text)} would be the safest place to check."
def write_prog(text):
    tl=text.lower()
    kind=next((w for w in ['letter','email','cover letter','story','poem','essay','song','cv','resume','speech','dialogue','script','haiku','joke','tweet','message','lyrics'] if re.search(r'\b'+w+r'\b',tl)),'text')
    if kind in ('cv','resume'):
        return "I can lay out a CV, but I need your details first: your name and contact details, the role you're applying for, your education, your work or project experience (with dates), and your main skills. Send those and I'll arrange them into a clean CV."
    if kind in ('letter','email','message'):
        m=re.search(r"\bto (?:my |the |our )?([a-z][a-z ]{1,30}?)\b(?: (?:about|explaining|expressing|asking|telling|saying|that|to|for|regarding|letting)\b|[,.]|$)",tl)
        rec=m.group(1).strip() if m else None
        pm=re.search(r"\b(about|explaining|expressing|asking|telling|regarding|saying|that|letting)\b(.+)",text,re.I)
        purpose=(pm.group(1).lower()+pm.group(2)).strip().rstrip('.?!') if pm else None
        if not rec or not purpose:
            return f"Happy to draft that {kind}. Who is it for, and what is the main point you want to get across?"
        purpose=re.sub(r'\bmy\b','my',re.sub(r'\bme\b','me',purpose))
        greet=('Dear '+rec.title()) if rec not in ('boss','manager','team') else ('Dear '+{'boss':'[Boss\'s name]','manager':'[Manager\'s name]','team':'team'}[rec])
        return f"Here is a short draft:\n\n{greet},\n\nI am writing {purpose if purpose.startswith(('about','regarding','to')) else 'regarding the following: '+purpose}. I wanted to let you know directly and would be glad to discuss it further.\n\nThank you for your time and understanding.\n\nBest regards,\n[Your name]"
    return f"Writing a full {kind} is beyond what I can do reliably; my generator only handles short letters and emails. If a short letter or email would help instead, tell me who it is for and the main point."
def math_prog(text):
    m=re.search(r"(-?\d+(?:\.\d+)?)\s*([-+*/x])\s*(-?\d+(?:\.\d+)?)",text)
    a,op,b=float(m.group(1)),m.group(2),float(m.group(3))
    if op=='/' and b==0: return "That divides by zero, so it has no defined value."
    r={'+':a+b,'-':a-b,'*':a*b,'x':a*b,'/':a/b if b else 0}[op]
    r=int(r) if r==int(r) else round(r,6)
    return f"{m.group(1)} {op} {m.group(3)} = {r}."
def task_reply(typ,messages):
    text=messages[-1]['content'];tl=text.lower()
    if typ=='greet': return "Hello! How can I help?"
    if typ=='ident':
        nm=re.search(r"\b(?:i am|i'm|my name is) ([A-Z][a-z]+)",text)
        hi=f"Nice to meet you, {nm.group(1)}! " if nm else ""
        return hi+"I'm CAEL, an experimental non-neural assistant built from cellular-automaton rules and small symbolic programs. I can chat about everyday things and answer a few simple factual questions, but my knowledge is small and my replies can be unreliable."
    if typ=='realtime':
        thing=next((w for w in ['weather','news','schedule','calendar','tasks','stock price','score','release date','latest information'] if w.split()[0] in tl),'live information')
        return f"I can't access live or personal data such as the {thing}, so I can't tell you that. A {'weather app or forecast site' if thing=='weather' else 'current official source or your own calendar/app' if thing in ('schedule','calendar','tasks') else 'current search or official source'} will have the up-to-date answer."
    if typ=='write': return write_prog(text)
    if typ=='health': return "I can't give medical advice, and symptoms like these can be serious. Please contact a doctor or a medical helpline, and if it feels severe or sudden (for example chest pain, trouble breathing or a very high temperature) call your local emergency number now."
    if typ=='code': return "I can't write or debug code reliably; I have no programming knowledge beyond a few keywords. The official documentation for the language or library you're using, or a programming Q&A site, is a better place for this."
    if typ=='math': return math_prog(text)
    if typ in ('define','other','opinion','howto','recommend','compare'):
        if typ=='compare':
            parts=re.split(r"\b(?:and|vs\.?|versus|or)\b",re.sub(r".*\b(?:between|compare)\b","",tl).strip(' ?.'))
            es=[lookup(p.strip(' ?.')) for p in parts[:2]]
            if all(es) and len(es)==2: return es[0]['s']+' '+es[1]['s']+cite(es[0])
        e=lookup(subj(text)) if typ in ('define','other','opinion') else None
        if e: return e['s']+cite(e)
        if typ=='recommend' and re.search(r'\b(gift|present)\b',tl):
            return "Happy to help with ideas. What does the person enjoy (hobbies, interests), and roughly what budget do you have in mind?"
        what={'howto':'give you step-by-step instructions for that','recommend':'make a good recommendation here','compare':'compare those properly','opinion':'give an informed opinion on that'}.get(typ,'answer that')
        return idk(text,what)
    return idk(text)
class V4:
    def __init__(s,v2=None):
        s.v2=v2
    def respond(s,messages):
        typ,st,cells,sc=route(messages)
        if typ=='smalltalk':
            # The 0.2.1 small-talk reply models were fitted on non-commercial data and are no longer loaded; the
            # unified assistant answers small talk with its own engines (smalltalk, chat_extra, chat_corpus).
            return dict(response="Tell me more about that.",route='smalltalk')
        return dict(response=task_reply(typ,messages),route=typ)
def load_v2(directory):
    """Load the knowledge store (Dolly CC BY-SA 3.0 and SQuAD CC BY-SA 4.0 sentences). Returns no reply model."""
    global STORE
    directory = Path(directory)
    STORE = json.load(gzip.open(directory / "knowledge.json.gz", "rt", encoding="utf-8"))
    return None
