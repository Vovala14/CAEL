"""Patch independently confirmed errata without regenerating or moving questions."""
import hashlib,importlib.util,json,re
from collections import Counter
from decimal import Decimal
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
HERE=Path(__file__).resolve().parent
import argparse,shutil
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,required=True,help='Local snapshot of pinned original HF revision')
parser.add_argument('--out',type=Path,required=True,help='New separate output directory')
args=parser.parse_args();ROOT=args.source.resolve();OUT=args.out.resolve()
assert ROOT!=OUT,'Never modify the source snapshot in place'
OUT.mkdir(parents=True,exist_ok=True)
if (HERE/'generate.py').resolve()!=(OUT/'generate.py').resolve():shutil.copyfile(HERE/'generate.py',OUT/'generate.py')
shutil.copyfile(ROOT/'stats.json',OUT/'stats.json')
spec=importlib.util.spec_from_file_location('fixed_generator',OUT/'generate.py');gen=importlib.util.module_from_spec(spec);spec.loader.exec_module(gen)
pat=re.compile(r'earns ([$£€])([\d,.]+) an hour\. They worked ([\d.]+) hours on Monday and ([\d.]+) hours on Tuesday, then spent ([$£€])([\d,.]+)')
assert not (OUT/'data').exists();(OUT/'data').mkdir()
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
totals=Counter();by_split={};files={}
changes=(OUT/'errata.jsonl').open('x',encoding='utf-8')
for source in sorted((ROOT/'data').glob('*.parquet')):
    before=pq.ParquetFile(source);target=OUT/'data'/source.name;counter=Counter();writer=None
    try:
        for batch in before.iter_batches(batch_size=8192):
            rows=batch.to_pylist()
            for row in rows:
                totals['rows']+=1;counter['rows']+=1
                original=dict(row);delta={}
                if row['task']=='pay_minus_spending':
                    m=pat.search(' '.join(x['content'] for x in row['messages']));assert m,row['id']
                    sym,rate,h1,h2,sym2,spent=m.groups();assert sym==sym2
                    net=(Decimal(h1)+Decimal(h2))*Decimal(rate.replace(',',''))-Decimal(spent.replace(',',''))
                    expected=gen.money(sym,int(net*100))
                    if expected!=row['answer']:
                        assert net!=Decimal(row['answer'].replace(sym,'').replace(',',''))
                        wrong=row['answer'];assert row['solution'].endswith(wrong+'.')
                        row['answer']=expected;row['solution']=row['solution'][:-len(wrong)-1]+expected+'.'
                        delta['answer']={'before':wrong,'after':expected};delta['solution']={'before':original['solution'],'after':row['solution']}
                        totals['answer_corrections']+=1;counter['answer_corrections']+=1
                if row['task']=='comparisons' and re.search(r'Who is the (?:shortest|youngest|lightest|slowest)\?',row['messages'][-1]['content']) and 'never on the losing side' in row['solution']:
                    row['solution']=row['solution'].replace('never on the losing side','never on the winning side')
                    delta['solution']={'before':original['solution'],'after':row['solution']}
                    totals['comparison_explanation_corrections']+=1;counter['comparison_explanation_corrections']+=1
                if delta:
                    row['generator']='cael-verified-reasoning-1.1.1'
                    delta['generator']={'before':original['generator'],'after':row['generator']}
                    assert set(k for k in row if row[k]!=original[k])==set(delta)
                    changes.write(json.dumps({'id':row['id'],'file':'data/'+source.name,'changes':delta},ensure_ascii=False)+'\n')
                    totals['changed_rows']+=1;counter['changed_rows']+=1
                assert row['id']==original['id'] and row['messages']==original['messages']
            table=pa.Table.from_pylist(rows,schema=before.schema_arrow)
            if writer is None:writer=pq.ParquetWriter(target,table.schema,compression='zstd')
            writer.write_table(table,row_group_size=8192)
    finally:
        if writer is not None:writer.close()
    files['data/'+source.name]={'old_sha256':sha(source),'new_sha256':sha(target),'rows':before.metadata.num_rows,'row_group_max':max(pq.ParquetFile(target).metadata.row_group(i).num_rows for i in range(pq.ParquetFile(target).metadata.num_row_groups))}
    by_split[source.name]=dict(counter);print(source.name,dict(counter),flush=True)
changes.close()
assert totals['answer_corrections']==142 and totals['comparison_explanation_corrections']==30763 and totals['rows']==2001427
manifest={'data_revision':'1.1.1','original_revision':'31780cd0fed31c04a50deafd3c27f75f33a84825','scope':'Targeted confirmed errata only. Every question, ID, split, category, task and reference other than the listed answer corrections is preserved. Smaller Parquet row groups bound read memory; this does not guarantee recovery of the external viewer service.','counts':dict(totals),'by_file':by_split,'files':files,'errata_sha256':sha(OUT/'errata.jsonl')}
(OUT/'data_revision.json').write_text(json.dumps(manifest,indent=2))
stats=json.loads((OUT/'stats.json').read_text());stats['version']='1.1.1';stats['data_revision']={'base_generator':'1.1','corrected_generator':'1.1.1','answer_corrections':142,'comparison_explanation_corrections':30763,'questions_and_split_membership_unchanged':True};(OUT/'stats.json').write_text(json.dumps(stats,indent=1))
print(json.dumps(dict(totals)))
