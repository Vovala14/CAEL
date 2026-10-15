# Definitional sentence store from licensed TRAIN passages (SQuAD TRAIN folds 0-7 contexts, Dolly TRAIN contexts).
# Only passage text is used; no question, answer or response field is read into the store.
import json,re,gzip,hashlib
DEF=re.compile(r"^(?:The |A |An )?([A-Z0-9][^,;:()]{1,60}?)\s*(?:\([^)]{0,80}\)\s*)?(?:,[^,]{0,80},\s*)?(?:is|are|was|were|refers to)\s+(?:a|an|the|one|any|also)\b")
def sents(t): return re.split(r'(?<=[.!?])\s+(?=[A-Z])',t.strip())
store={}
def add(text,src,title):
    for i,s in enumerate(sents(text)):
        if not(40<=len(s)<=320) or not s.endswith('.'): continue
        m=DEF.match(s)
        if not m: continue
        k=m.group(1).lower().strip()
        k=re.sub(r'\s+',' ',k)
        if len(k.split())>6: continue
        prio=(0 if i==0 else 1, len(s))
        cur=store.get(k)
        if cur is None or prio<tuple(cur['prio']): store[k]=dict(s=s,src=src,title=title,prio=prio)
seen=set()
for l in open('../../src/squad_train_folds0to7.jsonl'):
    r=json.loads(l)
    if r['context'] in seen: continue
    seen.add(r['context']); add(r['context'],'SQuAD 2.0 TRAIN (Wikipedia, CC BY-SA 4.0)',r['group'].replace('_',' '))
for l in open('../../src/dolly_train.jsonl'):
    r=json.loads(l)
    if r.get('context') and r['context'] not in seen:
        seen.add(r['context']); add(r['context'],'databricks-dolly-15k TRAIN context (CC BY-SA 3.0)','')
json.dump(store,gzip.open('knowledge_v4.json.gz','wt'))
print(len(seen),len(store)); import random
for k in random.Random(3).sample(sorted(store),12): print(k,'=>',store[k]['s'][:120])
