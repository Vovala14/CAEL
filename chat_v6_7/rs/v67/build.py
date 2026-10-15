# v6.5 store build: licensed passages + QA pairs, deduped and leakage-filtered vs held-back trees.
import json,gzip,re,glob,collections,hashlib,sys,numpy as np,pyarrow.parquet as pq
from multiprocessing import Pool
B='/workspace/cael/'
nrm=lambda s:re.sub(r'\W+',' ',str(s).lower()).strip()
# ---- held-back texts: all messages of trees in eval panels (sc1, v2, v65) + reserve/val tree ids (ids only)
R=json.load(open(B+'rs/v64/reserve_ids_only.json'));V=set(json.load(open(B+'rs/v64/official_val_tree_ids.json')))
PT=set()
for p in [B+'softca_chat_v1/panel_sc1.jsonl',B+'gen_ca_v2/panel_v2.jsonl',B+'rs/v65/panel_v65.jsonl']:
    PT|={json.loads(l)['group'] for l in open(p)}
EXT=PT|set(R['confirmation']['trees'])|set(R['development']['trees'])|V
HT=[]
for f in ['o1_train','o2_train']:
    t=pq.read_table(B+f'rs/v64/src/{f}.parquet',columns=['text','message_tree_id'])
    for x,tr in zip(t.column('text').to_pylist(),t.column('message_tree_id').to_pylist()):
        if tr in PT: HT.append(x)
HN={nrm(x) for x in HT};HN.discard('')
G=set()   # word 12-gram hashes (~80 chars) of held-back texts
def grams(s):
    w=s.split();return {hash(' '.join(w[i:i+12])) for i in range(max(0,len(w)-11))}
for x in HN: G|=grams(x)
SH=set()
for x in HN:
    for i in range(0,max(1,len(x)-79)): SH.add(x[i:i+80])
def leak(s):
    n=nrm(s);return n in HN or bool(grams(n)&G)
print('held-back texts',len(HN),'grams',len(G),flush=True)
# ---- passages
def paras(title,text,maxp):
    out=[];sec='';
    for blk in text.split('\n'):
        b=blk.strip()
        if not b: continue
        if len(b)<60 and not b.endswith('.'): sec=b;continue   # section heading
        if sec.lower() in('references','external links','see also','notes','further reading','bibliography','sources','other websites'): continue
        if 80<=len(b)<=1500 and b.isascii(): out.append((title,sec,b))
        if len(out)>=maxp: break
    return out
P=[];seen=set();drop=0
for f,maxp,tag in [('data/simple.parquet',12,'Simple English Wikipedia'),(B+'gen_ca_v2/data/wiki_00000.parquet',8,'English Wikipedia'),(B+'gen_ca_v2/data/wiki_00001.parquet',8,'English Wikipedia'),(B+'gen_ca_v2/data/wiki_00002.parquet',8,'English Wikipedia')]:
    pf=pq.ParquetFile(f)
    for rg in range(pf.num_row_groups):
        t=pf.read_row_group(rg,columns=['title','text','url'])
        for ti,tx,u in zip(t.column('title').to_pylist(),t.column('text').to_pylist(),t.column('url').to_pylist()):
            if ti.startswith('List of'): continue
            for (a,s,b) in paras(ti,tx,maxp):
                h=hashlib.md5(nrm(b).encode()).digest()[:8]
                if h in seen: continue
                seen.add(h);P.append((a,s,b,u,tag))
    print(f,len(P),flush=True)
def chk(i): return leak(P[i][2])
with Pool(8) as pool: bad=pool.map(chk,range(len(P)),chunksize=5000)
nb=sum(bad);P=[p for p,b in zip(P,bad) if not b]
print('passages',len(P),'leak-dropped',nb,flush=True)
# ---- QA pairs
QA=[];qd=collections.Counter()
def addqa(q,a,src,kind):
    if not q or not a or leak(q) or leak(a): qd['leak_'+kind]+=1;return
    QA.append(dict(q=q,a=a,src=src,k=kind))
for r in json.load(gzip.open(B+'rs/v64/oasst_big_pool.json.gz','rt')):
    if r['tree'] in EXT: qd['tree_oasst']+=1;continue
    addqa(r['q'],r['a'],r['src'],'oasst')
for l in open(B+'src/dolly_train.jsonl'):
    r=json.loads(l)
    if r.get('context','').strip() or not r['response'].isascii() or len(r['response'])<15: continue
    addqa(r['instruction'],r['response'],'Databricks Dolly 15k (CC BY-SA 3.0), human-written','dolly')
import ast
for l in open(B+'src/squad_train_folds0to7.jsonl'):
    r=json.loads(l);A=r.get('answers') or [];A=ast.literal_eval(A) if isinstance(A,str) else A
    if not A: continue
    ans=A[0];ans=ans['text'] if isinstance(ans,dict) else ans
    sent=next((s for s in re.split(r'(?<=[.!?])\s+',r['context']) if ans and ans in s),None)
    if not sent or len(sent)>350 or not sent.isascii(): continue
    addqa(r['question'],sent,f"SQuAD v1.1 TRAIN folds 0-7 (CC BY-SA 4.0), from Wikipedia article \"{r['group'].replace('_',' ')}\"",'squad')
for r in json.load(gzip.open(B+'rs/v64/nq_pool.json.gz','rt')):
    addqa(r['q'],r['a'],r['src'],'nq')
# dedupe QA by normalized question+answer
d={};[d.setdefault((nrm(x['q']),nrm(x['a'])[:200]),x) for x in QA];QA=list(d.values())
print('qa',collections.Counter(x['k'] for x in QA),dict(qd),flush=True)
json.dump(dict(passages=P,qa=QA,stats=dict(passages=len(P),passage_leak_dropped=nb,qa=dict(collections.Counter(x['k'] for x in QA)),qa_drops=dict(qd),heldback_trees=len(PT))),gzip.open('store65_raw.json.gz','wt'))
