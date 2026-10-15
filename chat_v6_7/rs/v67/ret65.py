# v6.5 lexical retrieval over licensed store. Integer BM25 + integer coverage gate. No embeddings/NN.
import json,gzip,re,os,numpy as np
from index import toks,th
HERE=os.path.dirname(os.path.abspath(__file__))
class Idx:
    def __init__(s,p):
        z=np.load(p);s.ptr=z['ptr'];s.doc=z['doc'];s.w=z['w'];s.idf=z['idf'];s.N=int(s.doc.max())+1
    def search(s,terms,k=30):
        sc=np.zeros(s.N,np.int64)
        for h in set(th(t) for t in terms):
            a,b=s.ptr[h],s.ptr[h+1]
            if b>a: np.add.at(sc,s.doc[a:b],s.w[a:b]) if b-a<2000 else sc.__iadd__(np.bincount(s.doc[a:b],weights=s.w[a:b],minlength=s.N).astype(np.int64))
        top=np.argpartition(-sc,k)[:k];top=top[np.argsort(-sc[top])]
        return [(int(i),int(sc[i])) for i in top if sc[i]>0]
    def tidf(s,t): return int(s.idf[th(t)])
def load_meta():
    m=os.path.join(HERE,'store65_meta.json.gz')
    if not os.path.exists(m):
        R=json.load(gzip.open(os.path.join(HERE,'store65_raw.json.gz'),'rt'))
        json.dump(dict(qa=R['qa'],stats=R['stats']),gzip.open(m,'wt'))
        P=R['passages'];del R
        off=[0];blob=open(os.path.join(HERE,'pass_text.bin'),'wb');meta=[]
        for (a,sec,b,u,tag) in P:
            e=b.encode();blob.write(e);off.append(off[-1]+len(e));meta.append((a,sec,u,tag))
        blob.close();np.save(os.path.join(HERE,'pass_off.npy'),np.array(off,np.int64))
        json.dump(meta,gzip.open(os.path.join(HERE,'pass_meta.json.gz'),'wt'))
    return json.load(gzip.open(m,'rt'))
M=load_meta();QA=M['qa']
IQ=Idx(os.path.join(HERE,'idx_qa.npz'))
def cov(qset,tset,idx):
    tot=sum(idx.tidf(t) for t in qset) or 1
    return 1000*sum(idx.tidf(t) for t in qset if t in tset)//tot
SENT=re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"(])')
def qa_best(text):
    q=set(toks(text))
    if len(q)<2: return None
    best=None
    for i,sc in IQ.search(list(q),20):
        r=QA[i];c=set(toks(r['q']))
        cq=cov(q,c,IQ);cs=cov(c,q,IQ);f=min(cq,cs)
        if best is None or f>best['f']: best=dict(f=f,cq=cq,cs=cs,i=i,r=r)
    return best
# ---- exact-title lead lookup (subject phrase -> article lead). Simple English preferred, then English.
import sqlite3
DB=sqlite3.connect(os.path.join(HERE,'leads65.sqlite'),check_same_thread=False)
def lead(subject):
    s=re.sub(r'\s+',' ',subject).strip().lower()
    cands=[s]+([s[:-1]] if s.endswith('s') and not s.endswith('ss') else [])+([s[:-2]] if s.endswith('es') else [])
    for c in cands:
        for tag in ('Simple English Wikipedia','English Wikipedia'):
            r=DB.execute('select title,url,lead from leads where k=? and tag=?',(c,tag)).fetchone()
            if r: return dict(title=r[0],url=r[1],tag=tag,ans=r[2])
    return None
