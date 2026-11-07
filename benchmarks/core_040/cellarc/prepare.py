"""Download only pinned evaluation artifacts after core qualification."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,requests
H=Path(__file__).resolve().parent;E=H.parent;O=E/'candidate_runtime'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert load(E/'CORE_QUALIFICATION.json')['gate_passed']
freeze=load(E/'SOURCE_FREEZE.json')
for n,v in freeze['files'].items():assert sha(O/n)==v,n
assert not (H/'INPUT_SEAL.json').exists()
revision='76040e6aef0edc4982e53c13a85ef227378ed171'
base=f'https://huggingface.co/datasets/mireklzicar/cellarc_100k/resolve/{revision}/'
expected={'test_interpolation':'457e092bcaa5ab2be2c51f58a246621b14d924900a5425a831a5decf5b945284',
          'test_extrapolation':'015f58ce3bcc8a772db567171aea5b4538467d23aba5b0ec959cb66644fce4b1'}
s=requests.Session();artifacts={};inputs=[];gold=[]
for name in ['LICENSE','README.md','data_files.json','features.json']:
    r=s.get(base+name,timeout=60);r.raise_for_status();p=H/'upstream'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(r.content)
    artifacts['dataset/'+name]=sha(p)
for name in ['LICENSE','README.md','cellarc/eval/common.py','cellarc/generation/cax_runner.py']:
    r=s.get('https://raw.githubusercontent.com/mireklzicar/cellarc/2a317a6f78025f67d0666e0ce7ad10436a18a807/'+name,timeout=60);r.raise_for_status()
    p=H/'upstream'/'github'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(r.content);artifacts['github/'+name]=sha(p)
for split,digest in expected.items():
    r=s.get(base+'data/'+split+'.jsonl',timeout=60);r.raise_for_status();p=H/'upstream'/(split+'.jsonl');p.write_bytes(r.content)
    assert sha(p)==digest,split
    rows=[json.loads(line) for line in r.content.decode('utf-8').splitlines() if line.strip()]
    assert len(rows)==1000 and len({x['id'] for x in rows})==1000
    for episode in rows:
        assert len(episode['train'])==5
        pairs=[dict(input=x['input'],output=x['output']) for x in episode['train']]
        # Schema adaptation only; gold and all per-task metadata stay out.
        inputs.append(dict(id=episode['id'],split=split,task=dict(examples=pairs,query=episode['query'])))
        gold.append(dict(id=episode['id'],split=split,solution=episode['solution']))
    artifacts[split]=digest
assert len({r['id'] for r in inputs})==2000
for name,rows in [('inputs.jsonl',inputs),('gold.jsonl',gold)]:
    p=H/name;p.write_text(''.join(json.dumps(row,separators=(',',':'))+'\n' for row in rows),encoding='utf-8');artifacts[name]=sha(p)
seal=dict(prepared_utc=datetime.now(timezone.utc).isoformat(),dataset='mireklzicar/cellarc_100k',revision=revision,
    episodes=2000,split_counts={s:1000 for s in expected},artifacts=artifacts,
    source_freeze_sha256=sha(E/'SOURCE_FREEZE.json'),core_qualification_sha256=sha(E/'CORE_QUALIFICATION.json'),
    model_inputs=['five examples input/output pairs','query'],forbidden_metadata_removed=True,
    evaluator_files={n:sha(H/n) for n in ['prepare.py','predict.py','score.py','PROTOCOL.md']})
(H/'INPUT_SEAL.json').write_text(json.dumps(seal,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(prepared=True,episodes=2000,splits=list(expected),gold_not_model_input=True)))
