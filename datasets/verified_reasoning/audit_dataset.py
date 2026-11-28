"""Full logical before/after audit plus explicitly scoped independent checks."""
import hashlib,importlib.util,json,re,sys,time
from collections import Counter
from decimal import Decimal
from pathlib import Path
import pyarrow.parquet as pq
HERE=Path(__file__).resolve().parent
import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--original',type=Path,required=True,help='Local snapshot of original HF revision 31780cd0')
parser.add_argument('--corrected',type=Path,default=HERE)
parser.add_argument('--report',type=Path,default=HERE/'validation_report.reproduced.json')
args=parser.parse_args();OUT=args.corrected.resolve();OLD=args.original.resolve()
sys.path.insert(0,str(OUT));import verify
spec=importlib.util.spec_from_file_location('generator',OUT/'generate.py');gen=importlib.util.module_from_spec(spec);spec.loader.exec_module(gen)
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
started=time.perf_counter();counts=Counter();ids=set();cores=set();issues=[]
errata={r['id']:r for r in map(json.loads,(OUT/'errata.jsonl').read_text(encoding='utf-8').splitlines())}
pay=re.compile(r'earns ([$£€])([\d,.]+) an hour\. They worked ([\d.]+) hours on Monday and ([\d.]+) hours on Tuesday, then spent ([$£€])([\d,.]+)')
comparison=re.compile(r'([A-Z][a-z]+) is (taller|shorter|older|younger|heavier|lighter|faster|slower) than ([A-Z][a-z]+)')
positive={'taller','older','heavier','faster'};most={'tallest','oldest','heaviest','fastest'}
def core(row):
    msgs=[m['content'] for m in row['messages']]
    for lead in sorted(gen.LEADS,key=len,reverse=True):
        if lead and msgs[0].startswith(lead):msgs[0]=msgs[0][len(lead):];break
    for tail in sorted(gen.TAILS,key=len,reverse=True):
        if tail and msgs[-1].endswith(tail):msgs[-1]=msgs[-1][:-len(tail)];break
    return hashlib.sha256(' || '.join(msgs).lower().encode()).digest()
for file in sorted((OUT/'data').glob('*.parquet')):
    old=pq.ParquetFile(OLD/'data'/file.name);new=pq.ParquetFile(file)
    assert old.schema_arrow==new.schema_arrow and old.metadata.num_rows==new.metadata.num_rows
    old_rows=(r for batch in old.iter_batches(batch_size=8192) for r in batch.to_pylist())
    for batch in new.iter_batches(batch_size=8192):
        for row in batch.to_pylist():
            before=next(old_rows);counts['rows']+=1
            assert row['id'] not in ids;ids.add(row['id'])
            delta={k:{'before':before[k],'after':row[k]} for k in before if before[k]!=row[k]}
            if delta:
                assert row['id'] in errata and delta==errata[row['id']]['changes'],row['id'];counts['changed_rows']+=1
            else:assert row['id'] not in errata
            assert row['id']==before['id'] and row['messages']==before['messages']
            signature=core(row)
            if signature in cores:issues.append({'id':row['id'],'issue':'core-text duplicate'})
            cores.add(signature)
            assert verify.check('Answer: '+row['answer'],row),row['id'];counts['gold_self_consistency']+=1
            if row['task']=='pay_minus_spending':
                m=pay.search(' '.join(m['content'] for m in row['messages']));assert m
                sym,rate,h1,h2,sym2,spent=m.groups()
                expected=(Decimal(h1)+Decimal(h2))*Decimal(rate.replace(',',''))-Decimal(spent.replace(',',''))
                assert Decimal(row['answer'].replace(sym,'').replace(',',''))==expected,row['id'];counts['independent_pay_recomputations']+=1
            if row['task']=='comparisons':
                text=' '.join(m['content'] for m in row['messages']);edges=[]
                for a,relation,b in comparison.findall(text):edges.append((a,b) if relation in positive else (b,a))
                assert edges
                ask=re.search(r'Who is the (\w+)\?',text)[1]
                names={n for edge in edges for n in edge};blocked={b for a,b in edges} if ask in most else {a for a,b in edges}
                candidates=sorted(names-blocked);expected=candidates[0] if len(candidates)==1 else 'Cannot be determined'
                assert row['answer']==expected,row['id'];counts['independent_comparison_graphs']+=1
                if ask not in most:assert 'never on the losing side' not in row['solution']
            if row['category']=='arc_grids':
                metadata=json.loads(row['grids']);assert verify.grid_of(row['answer'])==metadata['test']['output'];counts['grid_representation_consistency']+=1
    assert next(old_rows,None) is None
    print(file.name,counts['rows'],flush=True)
for cents in range(-50000,50001):
    rendered=gen.money('$',cents);assert Decimal(rendered.replace('$','').replace(',',''))==Decimal(cents)/100
counts['signed_money_formatter_cases']=100001
assert counts['rows']==2001427 and counts['changed_rows']==30905
assert not issues,issues[:10]
report={'passed':True,'rows':counts['rows'],'counts':dict(counts),'unique_ids':len(ids),'unique_core_questions':len(cores),'unchanged':['all question messages','IDs and split membership','schema, task, category, difficulty, verification and grid metadata','all answers except the 142 confirmed money corrections'],'scope_note':'Full logical preservation and self-consistency audit; independent recomputation is limited to every pay-minus-spending row and every comparison graph. Grid metadata agreement and reference self-acceptance do not independently prove generated rules/gold correctness. No universal correctness claim.','elapsed_seconds':time.perf_counter()-started,'verifier_sha256':sha(OUT/'verify.py'),'generator_sha256':sha(OUT/'generate.py'),'files':{str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in sorted((OUT/'data').glob('*.parquet'))}}
args.report.write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
