# All English Wikipedia (20231101, 41 shards) + Simple English: title -> lead (first 1-2 sentences). sqlite, leakage-filtered.
import sqlite3,re,glob,json,pyarrow.parquet as pq
exec(open('build.py').read().split('# ---- passages')[0])
SENT=re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"(])')
db=sqlite3.connect('leads65.sqlite');pass
db.execute('create table if not exists leads(k text, tag text, title text, url text, lead text, primary key(k,tag))')
st=collections.Counter()
for f,tag in [(f,'English Wikipedia') for f in sorted(glob.glob('data/en_000*.parquet'))[18:]]:
    pf=pq.ParquetFile(f);rows=[]
    for rg in range(pf.num_row_groups):
        t=pf.read_row_group(rg,columns=['title','text','url'])
        for ti,tx,u in zip(t.column('title').to_pylist(),t.column('text').to_pylist(),t.column('url').to_pylist()):
            p=next((b.strip() for b in tx.split('\n') if len(b.strip())>=60),'')
            if not p or re.search(r'may (?:also )?refer to|can (?:also )?refer to|may mean',p[:250]): st['nolead']+=1;continue
            ss=SENT.split(p);a=ss[0]
            if len(a)<100 and len(ss)>1: a+=' '+ss[1]
            if len(a)<25 or len(a)>500: st['len']+=1;continue
            if leak(a): st['leak']+=1;continue
            rows.append((re.sub(r'\s+',' ',ti).strip().lower(),tag,ti,u,a))
    db.executemany('insert or ignore into leads values(?,?,?,?,?)',rows);db.commit();st['rows']+=len(rows);print(f,dict(st),flush=True)
json.dump(dict(st),open('leads_stats.json','w'))
