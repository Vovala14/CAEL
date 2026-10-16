# Modified for CAEL 0.2.1: portable bundle paths and package imports.
"""CAEL reply skeletons: (A) learned typed reply forms, (B) integer CA polarity/tense gate, (C) role-tagged copy slots.
No neural nets, embeddings, gradients, transformers, external LMs, or whole-answer index. Integer count tables only.
Disclosed outside-CA parts: tokenizer/compiler, training-only cue labeller, role tagger, count tables, global readout, renderer."""
import re,math,json,hashlib
from collections import Counter,defaultdict

POS_EMO={'excited','proud','grateful','joyful','content','impressed','hopeful','confident','caring','trusting','faithful','prepared','anticipating','sentimental','nostalgic'}
NEG_EMO={'sad','angry','afraid','terrified','annoyed','lonely','guilty','disgusted','furious','anxious','disappointed','jealous','embarrassed','devastated','ashamed','apprehensive'}
def emo_val(e): return 1 if e in POS_EMO else -1 if e in NEG_EMO else 0

TOK=re.compile(r"[a-z]+(?:'[a-z]+)?|[0-9]+|[?!.,]")
def toks(t): return TOK.findall(t.lower().replace('\u2019',"'"))
NEGATORS={'not',"n't",'never','no',"don't","didn't","can't","won't","isn't","wasn't","doesn't","couldn't","wouldn't","haven't","hasn't","aren't","weren't","nothing","cannot"}
PAST={'was','were','did','had','yesterday','ago','last','went','got','came','felt','saw','told','made','found','lost','passed','happened','bought','took','gave'}
FUT={'will','going','gonna','tomorrow','next','soon','upcoming','plan','planning','tonight','weekend',"i'll","we'll","can't wait",'wait','hope','hoping'}
STOP=set("""i me my mine we our you your he she it they them his her its their this that these those a an the and or but so to of in on at for with
from by about as is am are was were be been being have has had do does did not no yes just very really so too also then than there here what
when where why how who which would could should can will just like get got go going went one some any all more most much many lot lots
im i'm it's that's dont don't didn't was wasn't thing things time day today know think feel felt want really still even back up out over now
well oh yeah yea ok okay sure good great bad sad happy new old little big always never ever been made make way first last year years week
last night everything something anything nothing someone everyone people person myself himself herself them""".split())

# ---------------- (B) cellular automaton gate -----------------
LIM=1<<20
def clip(v): return max(-LIM,min(LIM,int(v)))
class GateCA:
    """1-D ring of token cells. Cell = (val,neg,isneg,past,fut,q,ready,aV,aP,aF,aQ,aN). One uniform radius-one synchronous rule:
    negation scope moves right one cell per tick (decrementing); a ready token sweeps right accumulating effective valence and cue counts."""
    @staticmethod
    def rule(L,C,R):
        val,neg,isneg,past,fut,q,ready,aV,aP,aF,aQ,aN=C
        nneg=max(neg,L[1]-1 if L[1]>0 else 0)
        if ready or not L[6]:
            return (val,nneg,isneg,past,fut,q,ready,aV,aP,aF,aQ,aN)
        eff=-val if (nneg>0 and not isneg) else val
        return (val,nneg,isneg,past,fut,q,1,clip(L[7]+eff),L[8]+past,L[9]+fut,L[10]+q,L[11]+(1 if val else 0))
    @classmethod
    def step(cls,cells):
        n=len(cells);return [cls.rule(cells[i-1],cells[i],cells[(i+1)%n]) for i in range(n)]
    @classmethod
    def run(cls,cells):
        # cell 0 is the source (ready=1) with zero accumulators; run len ticks synchronously
        for _ in range(len(cells)):cells=cls.step(cells)
        return cells[-1]

def compile_cells(text,lex,weight=1,channel='v'):
    ts=toks(text);cells=[(0,0,1,0,0,0,1,0,0,0,0,0)]
    L=lex[channel] if isinstance(lex,dict) and channel in lex else lex
    for i,w in enumerate(ts):
        isn=1 if w in NEGATORS or w.endswith("n't") else 0
        bg=(ts[i-1]+' '+w) if i else None   # radius-one left-neighbour lookup
        val=L.get(bg,L.get(w,0)) if bg else L.get(w,0)
        if channel=='f':isn=0
        cells.append((weight*val,3 if isn else 0,isn,1 if w in PAST or (w.endswith('ed') and len(w)>4) else 0,1 if w in FUT else 0,1 if w=='?' else 0,0,0,0,0,0,0))
    return cells

def direct_sum(cells):
    """Independent direct integer control (same semantics, procedural)."""
    aV=aP=aF=aQ=aN=0;negpos=-99;scope=0
    for i,c in enumerate(cells[1:],1):
        val,neg,isn,past,fut,q=c[:6]
        if isn:
            eff=val; scope=3
        else:
            eff=-val if scope-1>0 else val
            scope=max(scope-1,0) if scope else 0
        # scope semantics: scope value at cell = max over negators at distance d of (3-d)
        aV=clip(aV+eff);aP+=past;aF+=fut;aQ+=q;aN+=1 if val else 0
    return aV,aP,aF,aQ,aN

def ca_state(messages,lex):
    users=[m['content'] for m in messages if m['role']=='user']
    latest=users[-1];prior=' '.join(users[:-1])
    endL=GateCA.run(compile_cells(latest,lex,2));endC=GateCA.run(compile_cells(prior,lex,1)) if prior else (0,)*12
    fL=GateCA.run(compile_cells(latest+' '+prior,lex,1,'f'))
    V=endL[7]+endC[7];N=endL[11]+endC[11]
    return dict(V=V,N=N,P=endL[8],F=endL[9],Q=endL[10],W=fL[7],WN=fL[11],cells_latest=endL,cells_prior=endC)

def pol_bin(V,N,W=0,WN=0):
    if W/max(1,WN)>=14 and V<0:return 'fear'
    m=V/max(1,N)
    return 'n2' if m<=-12 else 'n1' if m<-3 else 'p2' if m>=12 else 'p1' if m>3 else 'z'

# --------------- (A) forms ------------------
OPEN_RULES=[('SYMP',r"\b(sorry|oh no|sucks|too bad|terrible|awful|horrible|unfortunate|bummer|that's rough|so sad|hate that)\b"),
            ('PRAISE',r"\b(congrat\w*|great|awesome|amazing|wonderful|nice|cool|good for you|glad|happy for you|exciting|fantastic|lucky|fun|sweet|good)\b"),
            ('SURPR',r"\b(wow|really|oh my|whoa|omg|yikes|geez)\b"),
            ('UNDER',r"\b(understand|know how you feel|know what you mean|i bet|imagine|makes sense|i agree|true|same|me too)\b"),
            ('HOPE',r"\b(hope|good luck|fingers crossed|i'm sure|you'll|you will|don't worry|be fine|be ok)\b")]
def sents(t): return [s.strip() for s in re.split(r'(?<=[.!?])\s+',t.strip()) if s.strip()]
def norm(s): return re.sub(r'\s+',' ',s.lower().replace('\u2019',"'").strip())
def opener_act(s):
    s=norm(s)
    if s.endswith('?'):return None
    for a,p in OPEN_RULES:
        if re.search(p,s):return a
    return None
FOLLOW_RULES=[('QHAP',r"^(what happened|what did (he|she|they|you) do|why|how come|what's going on|what was it)"),
              ('QGO',r"^(how did it go|how was it|did you (have fun|enjoy|have a good)|how did (that|you do)|how'd it go)"),
              ('QFEEL',r"^(are you (ok|okay|alright|nervous|excited|scared|worried)|how do you feel|how are you)"),
              ('QFUT',r"^(when is|when are|what are you going to|where are you going|what will)")]
def follow_act(s,user_words):
    n=norm(s)
    if n.endswith('?'):
        for a,p in FOLLOW_RULES:
            if re.search(p,n):return a
        if any(w in user_words for w in toks(n) if w not in STOP and len(w)>2):return 'QSLOT'
        return 'QOTH'
    if re.match(r"^(that|it|this) (must|sounds|would|seems)",n):return 'EMPA'
    if re.search(r"\b(hope|good luck|fingers crossed|you'll|you will|have fun)\b",n):return 'HOPE'
    return None
def label_reply(resp,user_text):
    ss=sents(resp)
    if not ss:return None
    uw=set(toks(user_text));op=opener_act(ss[0])
    fo=None
    for s in ss[(1 if op else 0):]:
        a=follow_act(s,uw)
        if a:fo=a;break
    return f"{op or 'NONE'}+{fo or 'NONE'}"

def features(messages,st,slot_ok):
    prev=[m['content'] for m in messages if m['role']=='assistant']
    tense='fut' if st['F']>0 and st['F']>=st['P'] else 'past' if st['P']>0 else 'none'
    pb=pol_bin(st['V'],st['N'],st['W'],st['WN'])
    f=['pol:'+pb,'tense:'+tense,'uq:'+str(int(st['Q']>0)),'turn:'+('first' if len(messages)==1 else 'later'),
       'prevq:'+str(int(bool(prev) and '?' in prev[-1])),'slot:'+str(int(slot_ok))]
    f+=['pt:'+pb+'|'+tense,'pq:'+pb+'|'+f[3]]
    return f

# --------------- (C) role-tagged slots -------------
PERSON={'mom','mother','dad','father','son','daughter','wife','husband','brother','sister','friend','boyfriend','girlfriend','grandma','grandmother','grandpa','grandfather','boss','kid','kids','baby','aunt','uncle','cousin','neighbor','coworker','family','parents','children','child','niece','nephew','fiance','roommate','teacher'}
def role_slots(text):
    ts=toks(text);out=[]
    for i,w in enumerate(ts):
        if w in STOP or len(w)<3 or not w.isalpha():continue
        prev=ts[i-1] if i else ''
        role='POSSESSED' if prev in ('my','our') else 'PERSON' if w in PERSON else 'OBJECT' if prev in ('a','an','the','new','some') else None
        if role:out.append((w,role,i))
    return out

class SkeletonModel:
    def __init__(self,m):self.m=m
    @staticmethod
    def fit(rows):
        # valence lexicon from user turns, TRAIN emotion label as supervision only
        FEAR={'afraid','terrified','anxious','apprehensive'}
        def grams(t):
            ts=toks(t);return set(ts)|{ts[i-1]+' '+ts[i] for i in range(1,len(ts))}
        def ratio(a,b,na,nb,minc):
            out={}
            for w in set(a)|set(b):
                if a[w]+b[w]<minc or w in NEGATORS:continue
                v=round(16*math.log(((a[w]+1)/(na+1))/((b[w]+1)/(nb+1))))
                if abs(v)>=4:out[w]=max(-48,min(48,v))
            return out
        pc=Counter();nc=Counter();fc_=Counter();oc=Counter();npos=nneg=nf=no=0;seen=set()
        for r in rows:
            v=emo_val(r['emotion_label'])
            for k,mm in enumerate(r['messages']):
                if mm['role']!='user' or (r['group'],k) in seen:continue
                seen.add((r['group'],k));ws=grams(mm['content'])
                if v>0:npos+=1;pc.update(ws)
                elif v<0:nneg+=1;nc.update(ws)
                if r['emotion_label'] in FEAR:nf+=1;fc_.update(ws)
                elif v<0:no+=1;oc.update(ws)
        lex=dict(v=ratio(pc,nc,npos,nneg,6),f={w:x for w,x in ratio(fc_,oc,nf,no,6).items() if x>0})
        m=dict(lex=lex)
        # forms over ALL fitting replies
        formc=Counter();lab=[]
        for r in rows:
            ut=r['messages'][-1]['content'];f=label_reply(r['response'],ut);lab.append(f);formc[f]+=1
        keep=sorted(f for f,c in formc.items() if c>=30 and f!='NONE+NONE')
        # slot templates
        tmpl=Counter();tw=defaultdict(Counter);tmpl_groups=defaultdict(set);tpol=defaultdict(Counter)
        for r in rows:
            ut=r['messages'][-1]['content'];slots={w for w in toks(ut) if w not in STOP and len(w)>2 and w.isalpha()}
            for s in sents(r['response']):
                n=norm(s)
                if not n.endswith('?'):continue
                tt=toks(n);hits=[w for w in tt if w in slots]
                if len(set(hits))!=1:continue
                w=hits[0];t=re.sub(r'\b%s\b'%re.escape(w),'{N}',n)
                if len(tt)>12:continue
                tmpl[t]+=1;tw[t][w]+=1;tmpl_groups[t].add(r['group']);tpol[t][emo_val(r['emotion_label'])]+=1
        tmpls={t:dict(tw[t]) for t,c in tmpl.items() if len(tmpl_groups[t])>=4 and len(tw[t])>=3 and len(t.replace('{N}','').strip(' ?'))>8}
        m['templates']=tmpls;m['template_pol']={t:{str(k):v for k,v in tpol[t].items()} for t in tmpls}
        model=SkeletonModel(m)
        # surface strings per act x polbin
        surf=defaultdict(Counter);fcount=defaultdict(Counter);fc=Counter();wcount=defaultdict(Counter);surf_word=defaultdict(Counter)
        for r,f in zip(rows,lab):
            st=ca_state(r['messages'],lex);pb=pol_bin(st['V'],st['N'],st['W'],st['WN'])
            ss=sents(r['response']);sur_used=[norm(x) for x in ss if len(toks(x))<=9]
            if ss:
                op=opener_act(ss[0])
                if op and len(toks(ss[0]))<=8:surf[op+'|'+pb][norm(ss[0])]+=1;surf[op][norm(ss[0])]+=1
                for s in ss:
                    a=follow_act(s,set(toks(r['messages'][-1]['content'])))
                    if a and a not in('QSLOT','QOTH') and len(toks(s))<=9:
                        tn='fut' if st['F']>0 and st['F']>=st['P'] else 'past'
                        surf[a+'|'+pb][norm(s)]+=1;surf[a][norm(s)]+=1;surf[a+'|'+pb+'|'+tn][norm(s)]+=1
            if f not in keep:continue
            so=model.best_slot(r['messages'][-1]['content'])is not None
            fc[f]+=1
            for x in features(r['messages'],st,so):fcount[f][x]+=1
            for w in set(toks(r['messages'][-1]['content'])):
                if w not in STOP and w.isalpha() and len(w)>2:wcount[w][f]+=1
            for w in set(toks(r['messages'][-1]['content'])):
                if w not in STOP and w.isalpha() and len(w)>2:
                    for sx in sur_used:surf_word[sx][w]+=1
        m['surface']={k:[(s,n) for s,n in c.most_common(12)] for k,c in surf.items() if c}
        keep_s={s for k in m['surface'] for s,_ in m['surface'][k]}
        m['surface_word']={s:{w:n for w,n in surf_word[s].items() if n>=2} for s in keep_s}
        wn=Counter({w:sum(c.values()) for w,c in wcount.items()})
        m['word_form']={w:{f:round(64*math.log(((wcount[w][f]+.5)/(fc[f]+1))/((wn[w]+.5)/(sum(fc.values())+1)))) for f in keep} for w in wn if wn[w]>=20}
        n=sum(fc.values());allf=set(x for f in fcount for x in fcount[f])
        m['forms']={f:dict(prior=round(64*math.log(fc[f]/n)),rules={x:round(64*math.log((fcount[f][x]+.5)/(fc[f]+1))) for x in allf}) for f in keep}
        m['form_coverage']=dict(fitting_replies=len(rows),labelled_kept=sum(fc.values()),forms=len(keep),form_counts={f:fc[f] for f in keep})
        return model
    def best_slot(self,text,pb=None):
        best=None
        for w,role,i in role_slots(text):
            for t,ws in self.m['templates'].items():
                c=ws.get(w,0)
                tp=self.m.get('template_pol',{}).get(t,{});pos=tp.get('1',0);neg=tp.get('-1',0);tot=max(1,pos+neg)
                if pb in('n1','n2','fear') and neg/tot<0.4:continue   # (B) polarity gate on slot questions
                if pb in('p1','p2') and pos/tot<0.4:continue
                if c>=1 and (best is None or c>best[0]):best=(c,t,w,role)
        return best
    def respond(self,messages):
        st=ca_state(messages,self.m['lex']);slot=self.best_slot(messages[-1]['content'],pol_bin(st['V'],st['N'],st['W'],st['WN']))
        fs=features(messages,st,slot is not None);pb=pol_bin(st['V'],st['N'],st['W'],st['WN'])
        prevq=[m['content'] for m in messages if m['role']=='assistant']
        uwords={w for w in toks(messages[-1]['content']) if w not in STOP and w.isalpha() and len(w)>2}
        scores={}
        for f,d in self.m['forms'].items():
            op,fo=f.split('+')
            # (B) polarity gate
            if op=='SYMP' and pb in('p1','p2'):continue
            if op=='PRAISE' and pb in('n1','n2'):continue
            if fo=='QSLOT' and slot is None:continue
            if fo=='QOTH':continue
            if fo=='NONE' and len(messages)==1 and op!='HOPE':continue
            if op=='PRAISE' and pb=='fear':continue
            if fo=='QHAP' and pb in('p1','p2'):continue
            if fo=='QFUT':continue
            if fo=='QFEEL' and pb!='fear':continue
            if op=='HOPE' and fo=='HOPE':continue
            if fo=='EMPA' and pb=='z':continue
            if fo=='QHAP' and len(toks(messages[-1]['content']))>=10 and 'tense:past' in fs:continue
            if fo=='EMPA' and op in('PRAISE',) and pb in('p1','p2'):continue
            if fo=='HOPE' and not ('tense:fut' in fs or pb=='fear'):continue
            if op=='HOPE' and not ('tense:fut' in fs or pb=='fear'):continue
            if pb=='z' and op in('PRAISE','SYMP'):continue
            if fo=='QGO' and (pb in('n1','n2','fear') or 'tense:past' not in fs):continue
            if len(messages)==1 and op=='NONE' and fo!='QSLOT' and pb!='z':continue
            if fo=='QSLOT' and slot is not None:scores_bonus=128
            else:scores_bonus=0
            if fo=='QGO' and 'tense:fut' in fs:continue
            if fo=='QFUT' and 'tense:past' in fs:continue
            scores[f]=d['prior']+sum(d['rules'].get(x,-400) for x in fs)+scores_bonus+sum(self.m['word_form'].get(w,{}).get(f,0) for w in uwords)
        if not scores:   # fallback: polarity gate only
            for f,d in self.m['forms'].items():
                op,fo=f.split('+')
                if fo in('QOTH','QFUT','HOPE') or (fo=='QSLOT' and slot is None) or op in('PRAISE','SYMP','HOPE'):continue
                scores[f]=d['prior']+sum(d['rules'].get(x,-400) for x in fs)
        form=max(sorted(scores),key=lambda f:scores[f]);op,fo=form.split('+');parts=[]
        def pick(act):
            tn='fut' if 'tense:fut' in fs else 'past'
            keys=(act+'|'+pb+'|'+tn,act+'|'+pb,act) if act in('HOPE','EMPA') else (act,) if act in('QGO','QHAP','QFEEL') else (act+'|'+pb,act)
            for k in keys:
                cands=self.m['surface'].get(k,[])
                if not cands:continue
                tot=sum(n for _,n in cands)
                def sc(sn):
                    s,n=sn;sw=self.m['surface_word'].get(s,{})
                    return round(64*math.log(n/tot))+sum(round(64*math.log((sw.get(w,0)+.5)/(n*0.02+.5))) for w in uwords if sw.get(w,0)>=2)
                for s,n in sorted(cands,key=lambda x:-sc(x)):
                    if not prevq or norm(s) not in norm(prevq[-1]):return s
            return None
        if op!='NONE':parts.append(pick(op))
        if fo=='QSLOT':parts.append(slot[1].replace('{N}',slot[2]))
        elif fo!='NONE':parts.append(pick(fo))
        parts=[p for p in parts if p]
        text=' '.join(p[0].upper()+p[1:] for p in parts)
        text=re.sub(r"\bi\b","I",text);text=re.sub(r"\bi'","I'",text)
        return dict(response=text,form=form,polarity_bin=pb,ca_V=st['V'],slot=slot[2:] if slot else None,features=fs)
