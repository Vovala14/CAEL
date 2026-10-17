# Modified for CAEL 0.2.1: portable bundle paths and package imports.
"""Skeleton v2. Same CA family as v1 plus: reply-stance valence channel (learned from human reply opener acts, cross-turn
weighted), outcome-stated / future / achievement / user-question cue channels, mandatory second sentence from role-tagged slots,
type selection fixes. No neural nets, embeddings, gradients, transformers, external LM, or whole-answer index."""
import sys,os,re,math,json

from .reply_skeleton_ca import toks,sents,norm,opener_act,STOP,NEGATORS,PERSON,emo_val,LIM,clip
from collections import Counter,defaultdict

PAST={'was','were','did','had','yesterday','ago','last','went','got','came','felt','saw','told','made','found','lost','passed','happened','bought','took','gave','won','finished'}
FUT={'will','going','gonna','tomorrow','next','soon','upcoming','tonight','weekend','coming','forward','planning','plan',"i'll","we'll",'cant','wait','await','awaiting'}
OUTCOME={'won','win','lost','passed','failed','finished','died','passed','broke','broken','scored','ended','turned','worked','got','fixed','returned','graduated','accepted','hired','fired','promoted','great','well','amazing','fun','perfect','loved','ruined','awesome','terrible'}
ACHIEVE={'won','winning','win','grades','scores','passed','graduated','promoted','accepted','hired','scored','finished','achieved','award','promotion','degree','raise','engaged','married','pregnant','born','first','record'}
LUCK={'test','exam','interview','job','competition','contest','game','tryout','audition','surgery','apply','applied','application','results','race','match','tournament','presentation','bid','nervous','scared','worried','anxious','hoping','hope'}
QAUX=re.compile(r"\b(has your|have you|do you|did you|are you|were you|would you|could you|can you|is it|what about you|how about you|you ever)\b")

class CA2:
    """Ring of word cells (s,f,isneg,neg,past,fut,out,ach,luck,q,ready,aS,aF,aP,aU,aO,aA,aL,aQ,aN). One uniform radius-one rule:
    negation scope travels right; a ready token sweeps right accumulating stance s (sign-flipped in scope), fear f and cue counts."""
    @staticmethod
    def rule(L,C,R):
        s,f,isn,neg,past,fut,out,ach,luck,q,ready=C[:11];acc=C[11:]
        nneg=max(neg,L[3]-1 if L[3]>0 else 0)
        if ready or not L[10]:return C[:3]+(nneg,)+C[4:]
        eff=-s if (nneg>0 and not isn) else s
        la=L[11:]
        new=(clip(la[0]+eff),clip(la[1]+f),la[2]+past,la[3]+fut,la[4]+out,la[5]+ach,la[6]+luck,la[7]+q,la[8]+(1 if s else 0))
        return (s,f,isn,nneg,past,fut,out,ach,luck,q,1)+new
    @classmethod
    def step(cls,c):n=len(c);return [cls.rule(c[i-1],c[i],c[(i+1)%n]) for i in range(n)]
    @classmethod
    def run(cls,c):
        for _ in range(len(c)):c=cls.step(c)
        return c[-1]
def compile2(text,lex,w=1):
    ts=toks(text);cells=[(0,)*10+(1,)+(0,)*9]
    S=lex['s'];F=lex['f']
    for i,t in enumerate(ts):
        bg=(ts[i-1]+' '+t) if i else None
        s=S.get(bg,S.get(t,0)) if bg else S.get(t,0);f=F.get(bg,F.get(t,0)) if bg else F.get(t,0)
        isn=1 if t in NEGATORS or t.endswith("n't") else 0
        cells.append((w*s,w*f,isn,3 if isn else 0,1 if t in PAST or (t.endswith('ed') and len(t)>4) else 0,1 if t in FUT else 0,
                      1 if t in OUTCOME else 0,1 if t in ACHIEVE else 0,1 if t in LUCK else 0,1 if t=='?' else 0,0)+(0,)*9)
    return cells
def direct2(cells):
    acc=[0]*9;scope=0
    for c in cells[1:]:
        s,f,isn=c[:3]
        if isn:eff=s;scope=3
        else:eff=-s if scope-1>0 else s;scope=max(scope-1,0)
        acc=[clip(acc[0]+eff),clip(acc[1]+f),acc[2]+c[4],acc[3]+c[5],acc[4]+c[6],acc[5]+c[7],acc[6]+c[8],acc[7]+c[9],acc[8]+(1 if s else 0)]
    return tuple(acc)
def state(messages,lex):
    users=[m['content'] for m in messages if m['role']=='user'];latest=users[-1];prior=' '.join(users[:-1])
    L=CA2.run(compile2(latest,lex,3))[11:];P=CA2.run(compile2(prior,lex,1))[11:] if prior else (0,)*9
    S=L[0]+P[0];N=3*L[8]+P[8]
    m=S/max(1,N);fm=(L[1]+P[1])/max(1,N)
    pol='fear' if fm>=14 and m<0 else 'n2' if m<=-10 else 'n1' if m<-2 else 'p2' if m>=10 else 'p1' if m>2 else 'z'
    tense='fut' if L[3]>0 and L[3]>=L[2] else 'past' if L[2]>0 else 'none'
    if pol=='z' and 'v1' in lex:   # secondary CA channel: v1 episode-valence lexicon (same CA family)
        from .reply_skeleton_ca import ca_state,pol_bin
        s1=ca_state(messages,lex['v1']);b=pol_bin(s1['V'],s1['N'])
        pol=b if b!='z' else 'z'
    return dict(pol=pol,m=m,tense=tense,outcome=L[4]>0 and tense!='fut',achieve=L[5]>0,luck=L[6]+P[6]>0,uq=L[7]>0,L=L,P=P)

FEEL_RX=re.compile(r"\b(?:i am|i'm|im|i was|i feel|i felt|i get|i got|made me|makes me|feeling)\s+(?:so |very |really |a little |kind of |pretty |super |extremely |quite )?([a-z]+)")
def fit_v2(rows):
    # stance lexicon: latest-user-turn grams, target = human reply opener SYMP(-) vs PRAISE(+); fear lexicon from fear episodes vs other negative
    def grams(t):ts=toks(t);return set(ts)|{ts[i-1]+' '+ts[i] for i in range(1,len(ts))}
    pc=Counter();nc=Counter();npos=nneg=0;fc=Counter();oc=Counter();nf=no=0;feel=Counter()
    for r in rows:
        ss=sents(r['response']);op=opener_act(ss[0]) if ss else None;g=grams(r['messages'][-1]['content'])
        if op=='PRAISE':npos+=1;pc.update(g)
        elif op=='SYMP':nneg+=1;nc.update(g)
        if r['emotion_label'] in('afraid','terrified','anxious','apprehensive'):nf+=1;fc.update(g)
        elif emo_val(r['emotion_label'])<0:no+=1;oc.update(g)
        for mm in r['messages']:
            if mm['role']=='user':feel.update(FEEL_RX.findall(mm['content'].lower()))
    def ratio(a,b,na,nb,minc):
        out={}
        for w in set(a)|set(b):
            if a[w]+b[w]<minc or w in NEGATORS:continue
            v=round(16*math.log(((a[w]+1)/(na+1))/((b[w]+1)/(nb+1))))
            if abs(v)>=4:out[w]=max(-48,min(48,v))
        return out
    lex=dict(s=ratio(pc,nc,npos,nneg,5),f={k:v for k,v in ratio(fc,oc,nf,no,6).items() if v>0})
    feelings=sorted(w for w,n in feel.items() if n>=15 and w not in STOP and w not in('going','not','sure','glad','happy','sad') or w in('glad','happy','sad'))
    return dict(lex=lex,feelings=feelings,feeling_val={w:lex['s'].get(w,0) for w in feelings})

class SkeletonV2:
    def __init__(self,v1model,v2model):self.m1=v1model;self.m=v2model
    def surf(self,act,pol,tense,uwords):
        for k in (f'{act}|{pol}|{tense}',f'{act}|{pol}',act):
            c=self.m1['surface'].get(k)
            if c:return c
        return []
    def first(self,act,pol,tense,uwords,avoid=()):
        for s,_ in self.surf(act,pol,tense,uwords):
            if s not in avoid:return s
        return None
    def respond(self,messages):
        st=state(messages,self.m['lex']);pol=st['pol'];tense=st['tense']
        last=messages[-1]['content'];ll=last.lower();ts=toks(last)
        uwords={w for w in ts if w not in STOP and w.isalpha() and len(w)>2}
        prev=[m['content'] for m in messages if m['role']=='assistant'];later=len(messages)>1
        f0=[w for w in FEEL_RX.findall(ll) if abs(self.m['lex']['s'].get(w,0))>=16]
        if f0 and not later:   # explicit feeling word overrides stance sign
            v=self.m['lex']['s'][f0[0]]
            if v>0 and pol not in('p1','p2'):pol='p1'
            if v<0 and pol in('p1','p2','z'):pol='n1'
        neg=pol in('n1','n2','fear');pos=pol in('p1','p2')
        parts=[]
        # --- user question: a fixed yes/no guess ("I am not, but I understand.") read as
        # nonsense for most questions, so questions about CAEL are now answered by the
        # authored smalltalk rules instead and this empathy model only reacts to the share.
        # --- opener (stance gate)
        if neg:op='SYMP' if pol!='fear' else 'FEAR'
        elif pos:op='CONGR' if (st['achieve'] and st['outcome']) else 'PRAISE'
        else:op='UNDER' if later else 'SURPR'
        opener={'SYMP':self.first('SYMP',pol,tense,uwords),'FEAR':'That sounds scary.' if tense!='fut' else "That's understandable.",
                'CONGR':'Congratulations!','PRAISE':self.first('PRAISE',pol,tense,uwords,avoid=('congratulations!','congrats!','congratulations.')),
                'UNDER':'I see.','SURPR':'Oh, really?'}[op]
        if not parts or op!='UNDER':parts.append(opener)
        # --- second sentence from slots / state (never bare)
        second=None
        feel=[w for w in FEEL_RX.findall(ll) if w in self.m['feeling_val'] and not w.endswith('ing') and (abs(self.m['lex']['s'].get(w,0))>=8 or self.m['lex']['f'].get(w,0)>=8) and w not in('ready','able','sure','glad','fine','okay','ok')]
        persons=[w for w in ts if w in PERSON];poss=[ts[i+1] for i,w in enumerate(ts[:-1]) if w in('my','our') and ts[i+1] not in STOP and ts[i+1].isalpha() and len(ts[i+1])>2]
        slotq=None
        for w in poss+[w for w in uwords]:
            for t,ws in self.m1['templates'].items():
                tp=self.m1['template_pol'].get(t,{});p=tp.get('1',0);n=tp.get('-1',0);tot=max(1,p+n)
                if ws.get(w,0)>=1 and ((neg and n/tot>=.4) or (pos and p/tot>=.4) or pol=='z'):
                    if tense=='fut' and re.search(r'\b(was|did|were)\b',t):continue
                    if tense=='past' and re.search(r'\b(is|are|will)\b',t) and w not in PERSON:continue
                    slotq=t.replace('{N}',w);break
            if slotq:break
        asked=bool(prev) and '?' in prev[-1]
        if feel and not later:
            f=feel[0];second=(f"I would have been {f} too." if tense=='past' else f"I would be {f} too.")
        elif tense=='fut' and not st['outcome']:
            if st['luck'] or pol=='fear':second='Good luck! I hope it goes well.' if pol!='fear' else "I'm sure you'll do great. Good luck!"
            elif pos and re.search(r'\b(trip|vacation|show|party|concert|event|game|movie|weekend|festival|wedding|holiday|tonight|beach|camping|visit|cruise|christmas|birthday)\b',ll):second='Have fun! I hope you have a great time.'
            else:second='That sounds exciting!' if pos else (slotq or 'I hope it goes well.')
        elif persons and neg and re.search(r'\b(sick|ill|hospital|hurt|injured|accident|cancer|surgery|broke his|broke her|fell)\b',ll):
            second=f"I hope your {persons[0]} is okay." if not re.search(r'\b(died|passed away|death|funeral)\b',ll) else "I'm so sorry for your loss."
        elif re.search(r'\b(died|passed away|put down)\b',ll):second="I'm so sorry for your loss."
        elif later and asked:
            second={'n1':'That must be hard.','n2':'That must have been really hard.','fear':'That must have been scary.',
                    'p1':'That sounds really nice.','p2':"That's really great to hear.",'z':'That makes sense.'}[pol]
        elif slotq and not later and not st['outcome']:second=slotq[0].upper()+slotq[1:]
        elif neg and not st['outcome'] and len(ts)<10 and not later:second='What happened?'
        elif pos and tense=='past' and not st['outcome'] and not later:second='How did it go?'
        else:
            second={'n1':'That must be frustrating.','n2':'That must have been awful.','fear':'That must have been scary.',
                    'p1':'That sounds really nice.','p2':'That sounds amazing.','z':'Tell me more about it.'}[pol]
            if pos and persons:second=f"Your {persons[0]} sound{'s' if not persons[0].endswith('s') else ''} great."
        if op=='CONGR' and (not second or 'sound' in second):second='You must be so proud.'
        if second and opener and 'nice' in opener.lower() and 'nice' in second.lower():second="I'm happy for you."
        if second and (not prev or norm(second) not in norm(prev[-1])):parts.append(second)
        parts=[p for p in parts if p]
        txt=' '.join(p[0].upper()+p[1:] for p in parts)
        txt=re.sub(r"\bi\b","I",txt);txt=re.sub(r"\bi'","I'",txt)
        return dict(response=txt,pol=pol,tense=tense,outcome=st['outcome'],uq=st['uq'])
