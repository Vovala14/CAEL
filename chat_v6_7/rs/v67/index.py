# Integer BM25 inverted index over hashed terms (no embeddings, no NN).
import json,gzip,re,zlib,numpy as np,sys
STOP=set("a an the of to in on for and or is are was were be been being do does did what who whom how why which when where please can could would you me i my it this that these those with as at by from your we our us will should there their they them its if so but not about into than then also just any some have has had am tell explain describe give know want need like get way much many more most".split())
def stem(w):
    if len(w)>4 and w.endswith('ies'): return w[:-3]+'y'
    if len(w)>3 and w.endswith('s') and not w.endswith('ss') and not w.endswith('us'): return w[:-1]
    return w
def toks(t): return [stem(w) for w in re.findall(r"[a-z0-9]+",t.lower()) if w not in STOP and len(w)>1]
NB=1<<23
th=lambda w:zlib.crc32(w.encode())&(NB-1)
def build(docs,out):   # docs: list of (title_text, body_text)
    TT=[];DD=[];FF=[];T=[];D=[];F=[];L=np.zeros(len(docs),np.int32)
    for i,(ti,bo) in enumerate(docs):
        if len(T)>5000000:
            TT.append(np.array(T,np.int32));DD.append(np.array(D,np.int32));FF.append(np.array(F,np.int32));T=[];D=[];F=[]
        c={}
        for w in toks(bo): h=th(w);c[h]=c.get(h,0)+1
        for w in toks(ti): h=th(w);c[h]=c.get(h,0)+3
        L[i]=sum(c.values())
        T.extend(c.keys());D.extend([i]*len(c));F.extend(c.values())
        if i%500000==0: print(out,i,flush=True)
    TT.append(np.array(T,np.int32));DD.append(np.array(D,np.int32));FF.append(np.array(F,np.int32))
    T=np.concatenate(TT);D=np.concatenate(DD);F=np.concatenate(FF);del TT,DD,FF
    o=np.argsort(T,kind='stable');T,D,F=T[o],D[o],F[o]
    df=np.bincount(T,minlength=NB).astype(np.int64);ptr=np.zeros(NB+1,np.int64);ptr[1:]=np.cumsum(df)
    N=len(docs);idf=(1000*np.log((N-df+0.5)/(df+0.5)+1)).astype(np.int32)
    avg=int(L.mean());k1,b=1200,750
    lenn=L[D].astype(np.int64)
    tfp=F.astype(np.int64)*(k1+1000)*1000//(F.astype(np.int64)*1000+k1*(1000-b+b*lenn//avg))
    W=(idf[T].astype(np.int64)*tfp//1000).astype(np.int32)
    np.savez(out,ptr=ptr,doc=D,w=W,idf=idf,tf=F.astype(np.uint16))
if __name__=='__main__':
    R=json.load(gzip.open('store65_raw.json.gz','rt'))
    build([(q['q'],'') for q in R['qa']],'idx_qa')
    build([(p[0]+' '+p[1],p[2]) for p in R['passages']],'idx_pass')
