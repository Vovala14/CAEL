import json,gzip,re,collections,os
HERE=os.path.dirname(os.path.abspath(__file__))
D=json.load(gzip.open(os.path.join(HERE,'answer_store_v64.json.gz'),'rt'));STORE=D['store'];IDF=D['idf']
STOP=set("a an the of to in on for and or is are was were be been do does did what who how why which please can could would you me i my it this that with as at by from your we our us will should there their they them its if so but not about into than then also just any some have has had am hi hello hey thanks thank".split())
stem=lambda w:w[:-1] if len(w)>3 and w.endswith('s') and not w.endswith('ss') else w
toks=lambda t:{stem(w) for w in re.findall(r"[a-z0-9+#]+",t.lower()) if w not in STOP}
INV=collections.defaultdict(list)
for j,s in enumerate(STORE):
    s['_t']=toks(s['q'])
    for w in s['_t']: INV[w].append(j)
idf=lambda w:IDF.get(w,IDF.get(w+'s',900))
LEAD=re.compile(r"^\W*(?:hi|hello|hey)?[\W]*(what|which|who|why|how|when|where|is|are|can|does|do|write|list|give|name|tell|explain|show|describe|suggest|recommend|create|make)\b")
def lead(t):
    m=LEAD.search(t.lower());return m.group(1) if m else ''
def best(text):
    q=toks(text);tot=sum(idf(w) for w in q)
    if not q or tot==0: return None
    cand=collections.Counter()
    for w in q:
        for j in INV.get(w,()): cand[j]+=idf(w)
    out=None
    for j,sc in cand.most_common(50):
        s=STORE[j];st=sum(idf(w) for w in s['_t'])
        cq=1000*sc//tot; cs=1000*sc//max(1,st); f=min(cq,cs)
        if out is None or f>out[0]: out=(f,cq,cs,j)
    if out is None: return None
    f,cq,cs,j=out;s=STORE[j]
    rare=max(q,key=idf)
    return dict(f=f,cq=cq,cs=cs,lead_eq=int(lead(text)==lead(s['q'])),rare_in_a=int(rare in toks(s['a'])),nq=len(q),s=s)
