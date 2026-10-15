# Tatoeba (CC BY 2.0 FR) English->X sentence pairs, exact-match phrase table. sqlite.
import bz2,tarfile,sqlite3,re,collections
L=['deu','fra','spa','ita','por','nld','rus']
S={}
for l in ['eng']+L:
    for line in bz2.open(f'data/{l}_sentences.tsv.bz2','rt',encoding='utf-8'):
        p=line.rstrip('\n').split('\t')
        if len(p)>=3: S[int(p[0])]=(l,p[2])
print('sentences',len(S),flush=True)
k=lambda t:re.sub(r'[^\w\s]','',t.lower()).strip()
db=sqlite3.connect('tatoeba66.sqlite');db.execute('drop table if exists tr');db.execute('create table tr(en text, lang text, tx text, sid integer, tid integer)')
rows=[];n=0
tf=tarfile.open('data/links.tar.bz2');f=tf.extractfile([m for m in tf.getmembers() if m.isfile()][0])
for line in f:
    a,b=line.split(b'\t');a=int(a);b=int(b)
    x=S.get(a);y=S.get(b)
    if x and y and x[0]=='eng' and y[0]!='eng': rows.append((k(x[1]),y[0],y[1],a,b))
    if len(rows)>200000: db.executemany('insert into tr values(?,?,?,?,?)',rows);n+=len(rows);rows=[]
db.executemany('insert into tr values(?,?,?,?,?)',rows);n+=len(rows);db.execute('create index ie on tr(en,lang)');db.commit()
print('pairs',n,collections.Counter(r[0] for r in db.execute('select lang from tr')))
