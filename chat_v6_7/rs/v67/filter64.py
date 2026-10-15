# Remove from the inherited v6.4 store every entry tied to panel_v2/panel_sc1/panel_v65 trees or sharing text with them.
import json,gzip,re
exec(open('build.py').read().split('# ---- passages')[0])
import pyarrow.parquet as pq
mt={}
for f in ['o1_train','o2_train']:
    t=pq.read_table(B+f'rs/v64/src/{f}.parquet',columns=['message_id','message_tree_id'])
    mt.update(zip(t.column('message_id').to_pylist(),t.column('message_tree_id').to_pylist()))
D=json.load(gzip.open('answer_store_v64.json.gz','rt'));k=[];dr=0
for s in D['store']:
    m=re.search(r'message (\S+)',s['src'])
    if (m and mt.get(m.group(1)) in EXT) or leak(s['q']) or leak(s['a']): dr+=1;continue
    k.append(s)
print('v64 store',len(D['store']),'dropped',dr,'kept',len(k));D['store']=k
json.dump(D,gzip.open('answer_store_v64.json.gz','wt'))
