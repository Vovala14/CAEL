"""CAEL v6: precision-first. v4 RouterCA (unchanged) + new MoodCA (radius-1 integer carrier) + veto + cleanliness guard.
CA parts: RouterCA (route/type counts), MoodCA (polarity/negation/contrast/tense/wrongdoing/loss/fear counts, carried
cell-to-cell). Hybrid (authored, disclosed): cue lexicons, reply templates, NP extraction regexes, retrieval scoring
(integer, v5), shape-match rule, veto table, cleanliness checks."""
import retr63 as R63
import json,gzip,re,os,sys,collections
HERE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(HERE,'../v4'));sys.path.insert(0,os.path.join(HERE,'../v2'))
_c=os.getcwd();os.chdir(os.path.join(HERE,'../v4'));import cael_v4 as V4M;os.chdir(_c)
# ---------------- MoodCA ----------------
W=lambda s:set(s.split())
POS=W("happy glad excited exciting love loved loving enjoy enjoyed enjoying great amazing awesome wonderful proud fun beautiful best good nice relaxed relaxing peaceful thrilled won win winning promotion promoted passed graduated graduate adopted engaged married delicious favorite favourite cool lucky luckily thankfully finally grateful thankful priceless joyful blessed hired accepted impressive impressed excellent perfect fantastic yay celebrate celebrated surprise surprised confident hopeful awesome glad amazed dope relieved kind sweet cute funny laugh laughed smile")
NEG=W("sad destroyed destroying ruined unacceptable mold miss rejected pissed unhappy irritated irritating bummed furious demoted unable upset angry mad annoyed annoying terrible awful horrible bad worse worst hate hated lost lose losing broke broken crash crashed accident sick ill hurt hurts injured cancer stress stressful stressed stressing tired exhausting exhausted lonely alone depressed miserable frustrated frustrating disappointed disappointing fired rejected rescinded failed fail failing stolen stealing stole cheated heartbroken shattered crappy sucks sucked cry cried crying embarrassed embarrassing ashamed jealous envious hard difficult struggle struggling expensive suffering allergies pain painful teary sigh ugh unfortunately dang horrible gross disgusting rude mean ruined scam dirty cracked smashed homeless poor ugly fault clumsy dead kill killed")
FEAR=W("scared afraid nervous anxious terrified worried worry worrying fear frightened scary praying nerve")
LOSS=W("died passed funeral death dies dying")
WRONG=W("lied lie lying stole steal shoplifted shoplift cheat cheating unfaithful faithful guilty bodies revenge")
NEGT=W("didnt dont cant couldnt wasnt isnt wont wouldnt havent hasnt arent werent not no none never didn't don't can't couldn't wasn't isn't won't wouldn't haven't hasn't hadn't aren't weren't cannot nobody nothing without hardly")
CONTR=W("but although though however yet except")
FUT=W("will gonna tomorrow next soon upcoming planning preparing tonight")
PST=W("was were went got had did saw yesterday ago last used wasn't weren't didn't")
FP=W("i my me i'm i've i'd i'll myself we our us")
WH=W("what why how when where who which")
TOKR=re.compile(r"[a-z0-9]+(?:'[a-z]+)?|[?.!,;]")
def mcells(text):
    out=[]
    for t in TOKR.findall(text.lower()):
        v=dict(p=t in POS,n=t in NEG,f=t in FEAR,l=0,w=0,neg=t in NEGT or t.endswith("n't"),c=t in CONTR,fu=t in FUT,pa=t in PST or (len(t)>4 and t.endswith('ed')),fp=t in FP,q=t=='?',b=t in '.!?;')
        out.append((t,{k:int(x) for k,x in v.items()}))
    return out
ZERO=dict(p0=0,n0=0,p1=0,n1=0,f=0,l=0,w=0,fu=0,pa=0,fp=0,q=0,neg=0,ctr=0,win=0)
def mstep(c,cell):
    """radius-1 update: new carrier from left carrier + own cell only."""
    t,v=cell;d=dict(c)
    flip=d['win']>0
    side='1' if d['ctr'] else '0'
    if v['p']: d[('n' if flip else 'p')+side]+=1
    if v['n']:
        if not flip: d['n'+side]+=1
    for k in ('f','l','w','fu','pa','fp','q'):
        if v[k] and not (k in('f','l') and flip): d[k]+=1
    d['neg']+=v['neg']
    d['win']=3 if v['neg'] else max(0,d['win']-1)
    if v['b']: d['win']=0
    if v['c']: d['ctr']=1;d['win']=0
    return d
PHR=[(r"\bbest friends?\b","bestfriend"),(r"\bhard to believe\b","surprising"),(r"\b(studied|worked|prepared|tried|trained|practiced)( very| so| really)? hard\b",r"\1"),(r"\bmade at\b","mad at"),
     (r"\bran away\b","lost"),(r"\bkilling it\b","great"),(r"(not|n't|never) (like|liked|enjoy|enjoyed|love|loved)\b",r"\1 good"),(r"\bliked\b","enjoyed"),(r"\bnobody to\b","lonely to"),(r"\blook(?:ing)? forward\b","excited"),(r"\bfingers crossed\b","hopeful worried"),(r"\b(?:never|n't ever) (felt|been) so\b",r"\1 so"),(r"\b(?:not|wasn't|isn't) (?:too|that|so) bad\b","fine good"),(r"\bused to be (?:terrible|bad|awful)\b","used"),(r"\bblown away\b","amazed"),(r"\bas best\b","as"),(r"\bbittersweet\b","happy sad"),(r"\b(scared|bored|worried|frightened) to death\b",r"very \1"),(r"\bnever been (?:this|so)\b","very"),(r"\bturned down\b","rejected"),(r"\bdid (?:really |so )?well\b","great"),(r"\blost (?:a|my|our) loved one\b","died")]
def norm_text(text):
    t=text.lower()
    for a,b in PHR: t=re.sub(a,b,t)
    return t
def mood_ca(text):
    text=norm_text(text);c=dict(ZERO)
    for cell in mcells(text): c=mstep(c,cell)
    return c
def mood_direct(text):   # non-CA reference computation for conformance
    cs=mcells(norm_text(text));d=dict(ZERO);ctr=0;win=0
    for t,v in cs:
        flip=win>0;side='1' if ctr else '0'
        if v['p']:d[('n' if flip else 'p')+side]+=1
        if v['n'] and not flip:d['n'+side]+=1
        for k in ('f','l','w','fu','pa','fp','q'):
            if v[k] and not (k in('f','l') and flip):d[k]+=1
        d['neg']+=v['neg'];win=3 if v['neg'] else max(0,win-1)
        if v['b']:win=0
        if v['c']:ctr=1;win=0
    d['ctr']=ctr;d['win']=win;return d
def mood_of(text):
    m=mood_ca(text);tl=text.lower()
    P=m['p0']+2*m['p1'];N=m['n0']+2*m['n1']
    if re.search(r"\b(got|was|been|get|being) cheated on\b|\bcheated on me\b",tl): m['w']=0;N+=3
    if re.search(r"\b(died|dies|funeral|(?<!to )death of|passed away|put (?:him|her|it|my \w+) (?:down|to sleep)|put to sleep|lost my (?:mom|dad|mother|father|grand\w+|wife|husband|son|daughter|brother|sister|dog|cat|friend))\b",tl): m['l']+=1
    if re.search(r"\bi pulled (?:his|her|their) pants|\bi [^.]{0,50}even though i knew\b|\bi (?:punched|hit|kicked|pushed|pranked|tricked|yelled at|insulted|stole|shoplifted|cheated|lied)\b",tl) and not re.search(r"\b(accused|blamed) of\b",tl): m['w']+=1
    if re.search(r"\b(not my cup of tea|is wrong|hate (?:cheating|cheaters|liars|lying))\b",tl): m['w']=0
    if re.search(r"\b(didn't|did not|forgot to) pay\b|\bhard to be faithful\b",tl): m['w']+=1
    if re.search(r"\b(not|never|n't) (?:cheat|cheated|lie|lied|steal|stole)\b",tl): m['w']=0
    if re.search(r"\b(can't|cannot|can not) wait\b",tl): P+=2;N=max(0,N-1)
    futx=len(re.findall(r"\b(will|going to|gonna|about to|tomorrow|next (?:week|month|year|weekend|time)|coming up|upcoming|soon|tonight|can't wait|cannot wait|this (?:sunday|monday|tuesday|wednesday|thursday|friday|saturday|weekend|summer|fall|winter))\b",tl))
    pastx=len(re.findall(r"\b(was|were|went|had|did|got|wasn't|weren't|didn't|yesterday|ago|last (?:week|night|year|month|time))\b|\b\w{3,}ed\b",tl))
    fut=futx>0 and (futx>pastx or bool(re.search(r"\b(upcoming|tomorrow|next|will|coming up)\b",tl)))
    if m['l'] and not re.search(r"\bnot\b.{0,10}\b(die|dead)",tl): lab='loss'
    elif m['w'] and m['fp']: lab='wrong'
    elif m['f'] and fut: lab='worry'
    elif m['f'] and not P: lab='fear'
    elif m['ctr'] and m['win'] and m['p0'] and not m['p1'] and not m['n1'] and not m['n0']: lab='neg'
    elif m['ctr'] and (m['p1'] or m['n1']) and m['p1']!=m['n1'] and not (m['f'] and fut): lab='pos' if m['p1']>m['n1'] else 'neg'
    elif (m['p0'] and m['n1']) or (m['n0'] and m['p1']) or (P and N and abs(P-N)<=1): lab='mixed'
    elif N>P: lab='neg'
    elif P>N: lab='pos'
    else: lab='neutral'
    conf=abs(P-N)+ (2 if lab in('loss','wrong','worry','fear') else 0)
    return lab,('fut' if fut else 'past' if m['pa'] else 'pres'),conf,m
# ---------------- templates (authored) ----------------
def pick(opts,text): return opts[sum(map(ord,text))%len(opts)]
T={('pos','past'):["That's wonderful, I'm really glad to hear it!","That's great, it sounds like a lovely moment.","That's really nice to hear. I'm happy for you!"],
   ('pos','pres'):["That's great to hear!","That sounds really nice.","I love that, it sounds great."],
   ('pos','fut'):["That sounds exciting! I hope it goes really well.","How exciting! I hope you have a great time.","That sounds like something to look forward to!"],
   ('neg','past'):["I'm sorry, that sounds really rough.","Oh no, I'm sorry that happened.","That sounds really frustrating, I'm sorry."],
   ('neg','pres'):["I'm sorry you're dealing with that. It sounds hard.","That sounds really tough, I'm sorry.","I'm sorry, that can't be easy."],
   ('neg','fut'):["That sounds stressful. I hope it works out better than you expect.","I'm sorry, that sounds tough. I hope things work out."],
   ('worry','fut'):["It's completely normal to feel nervous about that. I hope it goes well for you.","Feeling a bit nervous is natural. I'm sure you'll handle it, and I hope it goes well."],
   ('fear','past'):["That sounds really scary.","That must have been frightening."],
   ('fear','pres'):["That's a really common fear, and it can be tough to deal with.","I can understand that. It's not an easy feeling."],
   ('fear','fut'):["It's completely normal to feel nervous about that. I hope it goes well for you."],
   ('loss','x'):["I'm so sorry for your loss.","I'm really sorry. Losing someone you love is so hard."],
   ('wrong','x'):["It sounds like that's been weighing on you. Owning up to it is a good first step.","It's good that you're thinking it over honestly. Maybe there's a way to make it right."],
   ('mixed','x'):["That sounds like a bit of a mixed bag.","It sounds like there's some good and some hard in that."],
   ('neutral','x'):["I see. Tell me a bit more about it.","Oh, I see. How do you feel about it?"],
   ('neutral','past'):["Oh, I see. How did that turn out?","I see. How did you feel about it?"]}
FOLLOW_LATER={'pos':"That sounds really nice.",'neg':"That sounds hard.",'mixed':"I can see why you'd feel that way.",'neutral':"I see what you mean."}
def smalltalk(messages):
    last=messages[-1]['content'];later=len(messages)>1
    lab,tense,conf,m=mood_of(last);lab_gate=None
    if later and (lab=='neutral' or (lab in('pos','neg','mixed') and conf<=1)):
        lab0,_,c0,_=mood_of(messages[0]['content'])
        if lab0 in('loss','neg','pos','fear','worry') and c0>=2: lab=lab0 if lab0 not in('fear','worry') else 'neg'
        elif lab=='neutral':
            la,_,ca,_=mood_of(' '.join(x['content'] for x in messages if x['role']=='user'))
            if la in('neg','pos') and ca>=2: lab=la;lab_gate='neutral'
    if later and any(mood_of(x['content'])[0]=='wrong' for x in messages if x['role']=='user'): lab='wrong'
    if lab=='neutral' and tense=='fut' and not later: return "I hope it goes well for you!",lab,tense,conf
    if later and last.strip().endswith('?') and re.search(r"\b(should i|what should|what would you|do you think|what do you)\b",last.lower()):
        return "That's a hard call, and you know the situation best. What feels right to you?",lab,tense,conf
    tl=last.lower();parts=[]
    qm=re.search(r"\b(have|did|do|were|are) you( ever)?\b[^?]*\?|\bwhat about you\b|\bhow about you\b|\bwhat was your\b[^?]*\?|\byour\b[^?]*\?",tl)
    if qm or (last.strip().endswith('?') and re.match(r"\s*(ever|do you|have you)",tl)):
        q=qm.group(0) if qm else tl
        if re.search(r"\byour\b",q) and not re.search(r"\byou( ever)?\b",q.replace('your','')): parts.append("I don't have one of my own, I'm afraid.")
        elif lab in('neg','loss','fear','worry'): parts.append("I haven't myself, but I can imagine how hard that is.")
        elif lab=='pos': parts.append("I haven't myself, but it sounds great.")
        else: parts.append("Not really myself, but I'd like to hear about it.")
        if lab=='neutral': return ' '.join(parts),lab,tense,conf
    if lab=='loss' and re.search(r"\b(plants?|garden|flowers?|trees?|crops?|grass|lawn)\b",tl): return "Oh no, that's a shame, especially after all that care. I'm sorry.",lab,tense,conf
    if lab=='loss' and not re.search(r"\b(mom|mother|dad|father|grand\w*|wife|husband|son|daughter|brother|sister|friend|uncle|aunt|cousin|baby|dog|cat|pet|puppy|kitten|fish|goldfish|turtle|bird|hamster|horse|rabbit|bunny|he|she|him|her|family|someone|loved one|neighbor|teacher|grandpa|grandma)\b",tl+' '+messages[0]['content'].lower()):
        return "Oh no, that's a shame. I'm sorry that happened.",lab,tense,conf
    key=(lab,tense) if (lab,tense) in T and lab!='neutral' else ('neutral','past') if (lab=='neutral' and tense=='past' and not later) else (lab,tense) if (lab,tense) in T else (lab,'x') if (lab,'x') in T else ('neutral','x')
    if lab in('pos','neg') and conf<=1 and not later: key=('mixed','x') if (m['p0']+m['p1'] and m['n0']+m['n1']) else key
    if later and lab in FOLLOW_LATER and not parts: parts.append(pick(["I see.","Ah, okay.","Got it."],last)); parts.append(FOLLOW_LATER[lab] if lab!='neutral' else "Thanks for telling me more.")
    else:
        opts=T[key]
        if key==('neutral','x') and (m['p0']+m['p1']+m['n0']+m['n1']+m['f']): opts=["I see. Tell me a bit more about it."]
        if key==('neutral','x') and later: opts=["I see. Tell me a bit more about it."]
        parts.append(pick(opts,last))
    return ' '.join(parts),(lab_gate or lab),tense,conf
# ---------------- clean noun phrase + safe task replies ----------------
SW=set("a an the of to in on for and or is are was were be been do does did what who how why which please can could would you me i my it this that with as at by from your we our us will should there their they them its if so but not about into than then also just any some have has had am explain tell give write make create list describe help show some something me want need like know way best".split())
def clean_np(text):
    t=re.split(r"[?.!\n:;]",text.strip())[0]
    for pat in [r"\b(?:about|regarding|is|are) (?:an? |the )?([A-Za-z][A-Za-z0-9+#' -]{2,40}?)(?=$|,| and | in | for | to | with | that | which)",r"\b([A-Z][a-z]+(?: [A-Z][a-z]+){1,3})(?=\s+[a-z]|[,.?!;:]|$)"]:
        m=re.search(pat,t)
        if m:
            np=m.group(1).strip(" '-")
            ws=np.split()
            if not (np[0].isupper() or ('"'+np in t and len(ws)>=2)) or (len(ws)<2 and not np[0].isupper()): continue
            if ws[0].lower() in ('dear','hi','hello','hey','please'): continue
            if 1<=len(ws)<=4 and ws[0].lower() not in SW and ws[-1].lower() not in SW and all(re.fullmatch(r"[A-Za-z][A-Za-z0-9+#'-]*",w) for w in ws) and not re.search(r"(ing|ly)$",ws[0].lower()) :
                return np
    return None
FOREIGN=W("hola wie ist und das der die bonjour merci gracias por favor como que est ciao hallo wer wann warum qu'est")
def safe_task(typ,text):
    np=clean_np(text);tl=text.lower()
    if re.search(r"\b(do you|can you|which languages? do you) speak\b|\blanguages? (?:do|can) you\b",tl):
        return "I can only chat in English, I'm afraid, and only about simple everyday things."
    if re.search(r"\b(your opinion|what do you think|do you think|do you (?:feel|like|believe|consider yourself)|are you (?:sentient|conscious|alive|self-aware)|your (?:favorite|favourite|feelings|views?))\b",tl):
        return "I'm a small experimental chatbot built from simple rules, so I don't really have views, feelings or experiences of my own on that."
    if typ not in('code','write') and (re.match(r"\s*(please )?(write|generate|come up with|create|make|imagine|pretend|act as|repeat|let's|lets|play|compose|draft|give me|list|describe|summarize|translate|tell me a)\b",tl) or re.search(r"\b(let's play|act as|pretend|role ?play|from now on|respond in|answer in)\b",tl)):
        return pick(["That's not something I can do well, I'm afraid. I'm a very limited, experimental chatbot, so I'd rather be upfront than give you a poor attempt.","Sorry, that's beyond what I can do. I'm a small experimental chatbot and can only handle simple everyday chat."],text)
    if typ=='code': return pick(["I'm not able to write or check code reliably, so I'd rather not hand you something broken. The official documentation or a programming Q&A site would be a better bet for this one.","Code is beyond what I can do reliably, I'm afraid. The language's official docs or a programming forum would give you a trustworthy answer."],text)
    if typ=='write' and re.search(r"\bhow (?:to|do i|can i|should i|would i|do you) (?:write|create|make)\b|\bwhat (?:is|are) the structure\b",tl): typ='howto'
    if typ=='write' and not re.search(r"^\s*(please )?(write|compose|draft|create|make|tell)\b|\b(can|could|would) you (?:please )?(?:write|compose|draft|create|make)\b|\bwrite (?:me|a|an)\b",tl): typ='other'
    if typ=='write':
        kind=next((w for w in ['cover letter','letter','email','story','poem','essay','song','speech','script','haiku','joke','review','article','scene','lyrics','message','tweet'] if re.search(r'\b'+w+r'\b',tl)),None)
        if kind in('letter','email','message','cover letter'): return f"Happy to help with the {kind}. Who is it for, and what's the main point you want to get across?"
        return f"I'm not able to write a good {kind or 'piece'} on request, I'm afraid; my writing ability is very limited. If you share a draft, I can at least react to it." if kind else "I'm not able to write that well on request, I'm afraid; my writing ability is very limited."
    if np:
        return pick([f"I'm not confident I know enough about {np} to answer that accurately, and I'd rather not guess. A reliable reference on {np} would be a better source.",
                     f"Honestly, I'm not sure about that one. I don't know enough about {np} to give you a trustworthy answer, so a good reference would be the safer place to check.",
                     f"That's a good question, but I don't know enough about {np} to answer it reliably. I'd suggest checking a trusted source rather than taking a guess from me."],text)
    return pick(["I'm not sure I can answer that accurately, and I'd rather not guess. A reliable reference or an expert would be a better source here.",
                 "Honestly, that's beyond what I can answer reliably. A trusted source would serve you better than a guess from me.",
                 "I don't think I can give you a trustworthy answer to that one, so I'd rather not guess."],text)
# ---------------- retrieval with shape match ----------------
D=json.load(gzip.open(os.path.join(HERE,'answer_store_v64.json.gz'),'rt'));STORE=D['store'];IDF=D['idf']
STOP5=set("a an the of to in on for and or is are was were be been do does did what who how why which please can could would you me i my it this that with as at by from your we our us will should there their they them its if so but not about into than then also just any some have has had am".split())
toks=lambda t:[w for w in re.findall(r"[a-z0-9]+",t.lower()) if w not in STOP5]
INV=collections.defaultdict(list)
for j,s in enumerate(STORE):
    s['_t']=set(toks(s['q']))
    for w in s['_t']: INV[w].append(j)
LEAD=re.compile(r"\b(what|which|who|why|how many|how much|how|when|where|is|are|can|does|do|write|list|give|name|tell|explain|show|describe|suggest|recommend|create|make)\b")
LC={'which':'what','are':'yn','is':'yn','can':'yn','does':'yn','do':'yn','write':'imp','list':'imp','give':'imp','name':'imp','tell':'imp','explain':'imp','show':'imp','describe':'imp','suggest':'imp','recommend':'imp','create':'imp','make':'imp'}
FILL=set("most many much some all one get make tell give show list name explain describe write create best good simple example examples way ways thing things really".split())
stem=lambda w:w[:-1] if len(w)>3 and w.endswith('s') and not w.endswith('ss') else w
def frame(text):
    tl=text.lower();m=LEAD.search(tl);lead=LC.get(m.group(1),m.group(1)) if m else ''
    tk=[stem(w) for w in toks(text)];q=set(tk)
    cont=[w for w in tk if w not in FILL]
    head=cont[0] if cont else ''
    keys=set(sorted(set(cont),key=lambda w:-IDF.get(w,800))[:2])
    return lead,head,keys,q
def retrieve(text,typ):
    if len(text)>160: return None,'too_long'
    lead,head,keys,q=frame(text)
    if len(q)<2 or not lead: return None,'too_short_or_no_frame'
    cand=collections.Counter()
    for w in q:
        for j in INV.get(w,()): cand[j]+=IDF[w]
        for j in INV.get(w+'s',()): cand[j]+=IDF[w+'s']
    for j,_ in cand.most_common(300):
        s=STORE[j]
        if len(s['q'])>200: continue
        l2,h2,k2,q2=frame(s['q'])
        if l2!=lead or head not in q2 or not keys<=q2 or not set(sorted(k2,key=lambda w:-IDF.get(w,800))[:1])<=q: continue
        if len(q-q2)>1 or len(q2-q)>3: continue
        if (q-q2)&keys: continue
        return s,'shape_match'
    return None,'no_shape_match'
# ---------------- veto + cleanliness ----------------
def clean_ok(r):
    if not r or not r.isascii(): return False
    if re.search(r"\b(\w+) \1\b",r.lower()): return False
    if re.search(r"\{|\}|\bNone\b|  \w",r): return False
    return True
def veto(cand,user_lab,user_tense,user_text):
    c=cand.lower()
    if user_lab in('neg','loss','fear','mixed','wrong') and re.search(r"\b(congratulations|congrats|happy for you|that's great|wonderful|have fun|awesome)\b",c): return 'mood'
    if user_lab=='pos' and re.search(r"\b(sorry|oh no|frustrating|awful|hard)\b",c): return 'mood'
    if user_tense!='fut' and re.search(r"\b(good luck|hope it goes|have fun)\b",c): return 'tense'
    if user_tense=='fut' and re.search(r"\bhow did it go\b",c): return 'tense'
    return None
# ---------------- top level ----------------
_V2=None
def V2():
    global _V2
    if _V2 is None:
        c=os.getcwd();os.chdir(os.path.join(HERE,'../v4'));_V2=V4M.load_v2();os.chdir(c)
    return _V2
FEELADJ=W("happy sad angry mad upset scared afraid excited proud lonely nervous anxious grateful disappointed jealous embarrassed guilty glad terrified annoyed nostalgic tired depressed stressed bored pissed bummed furious confident thankful relieved shocked surprised worried frustrated irritated envious ashamed")
def veto2(r,messages,lab,tense,conf):
    """CA veto for the v2 small-talk candidate: compare its surface with the MoodCA state of the user turn(s)."""
    c=r.lower();last=messages[-1]['content'].lower();allu=' '.join(x['content'].lower() for x in messages if x['role']=='user');later=len(messages)>1
    pos_s=bool(re.search(r"\b(nice!|that's great|congratulations|congrats|happy for you|sounds great|sounds amazing|sounds exciting|sounds really nice|have fun|proud|great to hear)",c))
    neg_s=bool(re.search(r"\b(oh no|sorry|frustrating|awful|must be hard|really hard|scary|terrible)",c))
    if lab=='neutral' and (pos_s or neg_s):
        lex=V2().m['lex']['s'];ws=re.findall(r"[a-z']+",last);sg=1 if pos_s else -1
        agree=max([lex.get(w,0)*sg for w in ws]+[0]);opp=max([-lex.get(w,0)*sg for w in ws]+[0])
        if not (agree>=16 and opp<=0) or (pos_s and neg_s): return 'mood'
    elif pos_s and lab!='pos': return 'mood'
    elif neg_s and lab not in('neg','loss','fear','worry','mixed'): return 'mood'
    if lab in('mixed','wrong'): return 'mixed_or_wrong'
    if re.search(r"sorry for your loss|losing someone",c) and re.search(r"\b(plants?|garden|flowers?|trees?|crops?|grass|lawn)\b",last): return 'loss_object'
    if re.search(r"sorry for your loss|losing someone",c) and not re.search(r"\b(mom|mother|dad|father|grand\w*|wife|husband|son|daughter|brother|sister|friend|uncle|aunt|cousin|baby|dog|cat|pet|puppy|kitten|fish|turtle|bird|hamster|horse|rabbit|someone|loved one|neighbor|teacher|he|she|him|her)\b",allu): return 'loss_object'
    if lab=='loss' and re.search(r"sorry for your loss",c) and not re.search(r"\b(died|passed away|put down|put to sleep|death|funeral)\b",allu): return 'loss_object'
    if lab=='loss' and not re.search(r"sorry for your loss|so sorry",c): return 'loss_needs_condolence'
    if tense!='fut' and re.search(r"\b(good luck|hope it goes|have fun|that sounds exciting)",c): return 'tense'
    if tense=='fut' and re.search(r"\b(would have been|must have been|how did it go|what happened)",c): return 'tense'
    if re.search(r"\b(how did it go|what happened|did you|what kind of \w+ (?:was|is) it|why (?:were|are) you)\b",c) and (later or len(last.split())>12 or re.search(r"\b(was|were|is|are) (?:a|an|the)? ?\w+\b",last)): return 'asks_stated'
    m=re.search(r"\bwhat kind of (\w+)|\bwhat (\w+) (?:was|is) (?:it|that)|\bhow old is your (\w+)|\byour (\w+) sounds?|\bhope your (\w+)",c)
    if m:
        w=[g for g in m.groups() if g][0]
        if w not in allu: return 'slot_not_in_user'
    m=re.search(r"\bi would (?:have been|be) (\w+) too",c)
    if m and m.group(1) not in FEELADJ: return 'feeling_echo'
    ws=re.findall(r"[a-z']+",c)
    if len(ws)!=len(set(ws)) and re.search(r"\b(\w{4,})\b.*\b\1\b",c): return 'duplicate'
    if re.search(r"\bi haven't, but i'd like to|\bi do sometimes|\bi did not|\bi am not, but",c) and lab!='pos': return 'canned_answer'
    if '?' in messages[-1]['content'] and not re.search(r"\b(i |i'm|me too|not really|no,|yes)",c[:20]): return 'ignores_question'
    if not clean_ok(r): return 'unclean'
    return None
class V6:
    def respond(s,messages):
        text=messages[-1]['content'];tl=text.lower()
        typ,st,cells,sc=V4M.route(messages)
        toks_=re.findall(r"[a-zà-ÿ']+",tl)
        if toks_ and sum(t in FOREIGN for t in toks_)>=min(2,len(toks_)) and sum(t in FOREIGN for t in toks_)*5>=len(toks_) : return dict(response="Sorry, I can only chat in English for now. Could you ask me that in English?",route='foreign')
        if re.fullmatch(r"\W*(hi|hello|hey)?\W*(how's|how is) (your day|it going|everything)( going)?( today)?\W*",tl): return dict(response="It's going well, thanks for asking! How's yours?",route='greet')
        if re.fullmatch(r"\W*(hi|hello|hey)?\W*(what's|whats|what is) up( doc)?\W*",tl): return dict(response="Not much, just here to chat! What's up with you?",route='greet')
        if re.fullmatch(r"\W*(hi|hello|hey)?\W*how are you( doing)?( today)?\W*",tl): return dict(response="I'm doing well, thanks for asking! How are you?",route='greet')
        lab,tense,conf,m=mood_of(text)
        isq=('?' in text) or bool(st['impstart']) or bool(re.match(r"\s*(what|why|how|where|who|which|is|are|can|could|would|does|do|should|will|please)\b",tl))
        if len(messages)==1 and re.match(r"\s*(have|did|do) you ever\b|\s*ever\b",tl) and len(text)<120: typ='smalltalk';isq=False
        # CA-gated reroute: declarative first-person turn with mood -> small talk; questions/requests never to small talk
        if typ!='smalltalk' and typ not in('greet',) and not isq and m['fp'] and lab!='neutral' and sc['req']<3: typ='smalltalk'
        narr=('?' not in text) and m['fp']>=1 and not st['youmod'] and not re.match(r"\s*(what|why|how|where|who|which|is|are|can|could|would|does|do|should|will|please|tell|explain|write|give|list)\b",tl) and not re.search(r"\b(can you|could you|would you|please|help me|explain|tell me|i want you|act as|pretend|find|how do i|how can i|be my|ideas for|an idea for|given the|i would need|i am planning|i'm planning|trying to remember|imagine|i'm trying to|i am trying to|present idea|gift idea|having trouble coming up|for me|what was i|write|recommend|suggest|i want|i need|i would like|i'd like|code|script|dataframe|function|app|program|converse|with me for|on my behalf|respond|reply as)\b",tl)
        everq=len(messages)==1 and bool(re.match(r"\s*(have|did|do) you ever\b|\s*ever\b",tl)) and len(text)<300
        tasklike=len(messages)==1 and (bool(st['impstart']) or st['cnt'][V4M.C['code']]>0 or bool(re.search(r"^\s*(please |hi[^.!]*[.!,] *)?(list|give|show|write|create|generate|teach|provide|explain|describe|summari[sz]e|translate|make|tell|imagine|pretend|act)\b|\b(let's play|lets play|you will|i will tell you|i will give you|from now on|act as|pretend|you are now|implementation|exercise|in python|code|i give you|you analy[sz]e|you add)\b",tl)))
        if tasklike: narr=False;everq=False
        story=len(messages)==1 and '?' not in text and m['fp']>=1 and not tasklike and bool(re.match(r"\s*(i |i'|my |we |our |last |yesterday|today|this |when i|once |the other day|so |well,? i)",tl)) and not re.search(r"\b(can you|could you|would you|please|help me|i want you|act as|pretend|for me|recommend|suggest|ideas? for|how (?:do|can|should) i|code|script|program)\b",tl)
        if story: narr=True
        if len(messages)>1 or narr or everq: typ='smalltalk';isq=False
        if tasklike and typ=='smalltalk': typ='other'
        if typ=='smalltalk' and len(messages)==1 and not (narr or everq or story) and (isq or re.search(r"\b(trying to|i want to|i need|how i can|how can i|using this|on a scale|explain|help me|be my|ideas? for|what was i|can you|could you|tell me)\b",tl)): typ='other'
        if len(messages)==1 and len(text)<60 and " or " not in tl and re.match(r"\W*(did|does|is|was|what's|what is|how is|how was|why did|why is)\s+(it|that|this|he|she)\b",tl):
            return dict(response="Sorry, I'm not sure what you're referring to. Could you give me a bit more context?",route='clarify')
        if typ=='smalltalk' and len(messages)==1 and lab=='neutral' and len(text)>120 and not narr: typ='other'
        if typ=='smalltalk':
            r,lab,tense,conf=smalltalk(messages)
            v=veto(r,lab,tense,text)
            if v or not clean_ok(r): r="I see. Tell me a bit more about it."
            r2=V2().respond(messages)['response']
            v2why=veto2(r2,messages,lab,tense,conf)
            if not v2why: return dict(response=r2,route='smalltalk+v2',mood=lab,tense=tense,conf=conf)
            return dict(response=r,route='smalltalk+template',mood=lab,tense=tense,conf=conf,veto=v2why)
        if typ=='greet': return dict(response="Hello! How can I help?",route='greet')
        if typ=='ident' and not re.search(r"\b(help me|can you (?:please )?(?:help|write|show|explain|tell))\b",tl) and re.search(r"\b(who are you|what are you|your name|are you (?:an? )?(?:ai|bot|human|robot|sentient|real|conscious)|what can you do)\b",tl):
            return dict(response="I'm CAEL, an experimental non-neural chatbot built from cellular-automaton rules and small hand-written programs. I can chat about everyday things, but my knowledge is very limited.",route='ident')
        if typ=='math' and not re.search(r"[()^=]|\d\s*[-+*/x]\s*\d+\s*[-+*/x]\s*\d",text) and len(text)<80:
            return dict(response=V4M.task_reply('math',messages),route='math')
        if typ=='health' and m['fp']:
            return dict(response="I can't give medical advice, but please don't ignore it. A doctor or medical helpline can check it properly, and if it's severe or sudden, call your local emergency number.",route='health')
        if re.search(r"\b(weather|news today|latest news|right now|what time|current time|next bus|what's the time|days until|today's date|what day is it)\b",tl):
            return dict(response="I don't have access to live information like that, so I can't tell you. A quick web search or your phone's clock or weather app will have the up-to-date answer.",route='realtime')
        if typ in('define','other','opinion') and len(text)<120:
            e=V4M.lookup(V4M.subj(text))
            if e and clean_ok(e['s']) and len(e['s'])<300:
                return dict(response=e['s']+V4M.cite(e),route=typ+'+definition')
        best,why=retrieve(text,typ)
        if best:   # topic veto: the query's rarest key must appear in the answer itself
            k=frame(text)[2];at={stem(w) for w in toks(best['a'])}
            if not (set(sorted(k,key=lambda w:-IDF.get(w,800))[:1])<=at) or not clean_ok(best['a'][:400].replace('  ',' ')) and False: best=None;why='veto_topic'
        if best:
            return dict(response=best['a'].strip()+f"\n\n[Retrieved human-written answer to a similar question: \"{best['q'][:120]}\" | Source: {best['src']}]",route=typ+'+retrieved')
        if typ not in('code','ident','realtime'):
            b63=R63.best(text)
            selfref=re.search(r"\b(you|your|yourself)\b",re.sub(r"\b(can|could|would|will) you\b","",tl))
            if b63 and b63['cq']>=1000 and b63['cs']>=400 and b63['rare_in_a'] and b63['nq']>=2 and not selfref and len(text)<200 and clean_ok(b63['s']['a'][:300]):
                s_=b63['s'];return dict(response=s_['a'].strip()+f"\n\n[Retrieved human-written answer to a similar question: \"{s_['q'][:120]}\" | Source: {s_['src']}]",route=typ+'+retrieved63')
        r=safe_task(typ,text)
        if not clean_ok(r): r="I'm not sure I can answer that accurately, and I'd rather not guess."
        return dict(response=r,route=typ+'+safe',why=why)
