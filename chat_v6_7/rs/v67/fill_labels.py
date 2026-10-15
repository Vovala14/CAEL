# Fill English labels/aliases missing from the stream (CC0, Wikidata API wbgetentities) for entities with >=20 facts.
import duckdb,json,urllib.request,time
d=duckdb.connect('kg67.duckdb');ids=[r[0] for r in d.execute('select g.q from deg g anti join lbl l on g.q=l.q where g.n>=20').fetchall()]
print('missing',len(ids),flush=True);L=[];A=[]
for i in range(0,len(ids),50):
    ch=ids[i:i+50];u='https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&props=labels|aliases&languages=en&ids='+'|'.join(f'Q{q}' for q in ch)
    for t in range(3):
        try: js=json.load(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'CAEL-research/0.1 (label backfill)'}),timeout=30));break
        except Exception as e: time.sleep(3);js=None
    if not js: continue
    for k,e in js.get('entities',{}).items():
        q=int(k[1:]);lb=e.get('labels',{}).get('en')
        if lb: L.append((q,lb['value']))
        for a in e.get('aliases',{}).get('en',[]): A.append((q,a['value']))
    if i%5000==0: print(i,len(L),flush=True)
d.executemany('insert into lbl values (?,?)',L)
d.executemany('insert into lab values (lower(?),?,false)',[(n,q) for q,n in L])
d.executemany('insert into lab values (lower(?),?,true)',[(n,q) for q,n in A])
d.execute('checkpoint');print('filled',len(L),'aliases',len(A))
