"""Independent artifact integrity/scoring audit and honest candidate report."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import difflib,hashlib,json,statistics,zipfile
import numpy as np
H=Path(__file__).resolve().parent;O=H/'candidate_runtime';B=H/'baseline_runtime';C=H/'cellarc'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
checks=0
def check(value,reason):
    global checks
    assert value,reason;checks+=1
freeze=load(H/'SOURCE_FREEZE.json');setup=load(H/'SETUP.json');qual=load(H/'CORE_QUALIFICATION.json');seal=load(C/'INPUT_SEAL.json')
check(qual['gate_passed'],'Core gate')
for n,v in freeze['files'].items():check(sha(O/n)==v,n)
for n,v in freeze['resources'].items():
    check(sha(O/n)==sha(B/n)==v,n)
check(sha(O/'research/active_models.json')==freeze['active_configuration_sha256'],'Candidate selection frozen')
for n in ['cael_unified/choice.py','cael_unified/wordmath.py']:
    check(sha(O/n)==setup['runtimes']['baseline_runtime']['files'][n],n)
for n in ['prepare.py','predict.py','score.py','PROTOCOL.md']:
    check(sha(C/n)==seal['evaluator_files'][n],n)
inputs=[json.loads(l) for l in (C/'inputs.jsonl').read_text().splitlines()]
gold=[json.loads(l) for l in (C/'gold.jsonl').read_text().splitlines()]
check(sha(C/'inputs.jsonl')==seal['artifacts']['inputs.jsonl'],'Input hash')
check(sha(C/'gold.jsonl')==seal['artifacts']['gold.jsonl'],'Gold hash')
for inp in inputs:
    check(set(inp['task'])=={'examples','query'},'No gold/metadata input')
    check(len(inp['task']['examples'])==5,'Five support pairs')
metrics={};rng=np.random.default_rng(740117)
for engine in ['baseline','candidate']:
    rec=load(C/'runs'/engine/'receipt.json');p=C/'runs'/engine/'predictions.jsonl'
    check(sha(p)==rec['predictions_sha256'],engine+' raw hash')
    predictions=[json.loads(l) for l in p.read_text().splitlines()]
    check(len(predictions)==len(gold)==2000,'All episodes')
    scores=[]
    for actual,target in zip(predictions,gold,strict=True):
        check(actual['id']==target['id'] and actual['split']==target['split'],'Ordered ID')
        pred=actual['prediction'];expected=target['solution']
        if pred is not None:check(len(pred)==len(expected),'Prediction length')
        # Independent indexed reproduction, not the main scorer's zip expression.
        correct=sum(pred is not None and pred[i]==expected[i] for i in range(len(expected)))
        scores.append(dict(split=target['split'],correct=correct,total=len(expected),exact=pred==expected))
    metrics[engine]={}
    recorded=load(C/'report.json')['systems'][engine]['splits']
    for split in ['test_interpolation','test_extrapolation']:
        rows=[r for r in scores if r['split']==split]
        correct=np.array([r['correct'] for r in rows]);totals=np.array([r['total'] for r in rows])
        value=float(correct.sum()/totals.sum());exact=sum(r['exact'] for r in rows)
        check(int(correct.sum())==recorded[split]['correct_cells'],'Cell reproduction')
        check(exact==recorded[split]['exact_episodes'],'Episode reproduction')
        sampled=rng.integers(0,len(rows),size=(5000,len(rows)))
        boot=correct[sampled].sum(axis=1)/totals[sampled].sum(axis=1)
        metrics[engine][split]=dict(cell_accuracy=value,episode_exact=exact,episodes=len(rows),
            episode_cluster_bootstrap95=[float(x) for x in np.quantile(boot,[.025,.975])],
            uncertainty_scope='Exploratory resampling of episodes; family dependence and benchmark-aware engineering limit inference')
changes={};patch=[]
for path in sorted((O/'cael_unified').rglob('*')):
    if not path.is_file() or path.suffix not in ('.py','.json') or '__pycache__' in path.parts:continue
    name=path.relative_to(O).as_posix();old=B/name
    if old.exists() and sha(old)==sha(path):continue
    changes[name]=dict(before_sha256=sha(old) if old.exists() else None,after_sha256=sha(path))
    patch.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True) if old.exists() else [],
                 path.read_text(encoding='utf-8').splitlines(True),fromfile='a/'+name,tofile='b/'+name))
(H/'CORE_0_4.patch').write_text(''.join(patch),encoding='utf-8')
out=dict(audited_utc=datetime.now(timezone.utc).isoformat(),passed=True,integrity_checks=checks,
         capability_tests_not_integrity_count=True,source_freeze_sha256=sha(H/'SOURCE_FREEZE.json'),
         core_qualification_sha256=sha(H/'CORE_QUALIFICATION.json'),input_seal_sha256=sha(C/'INPUT_SEAL.json'),
         cellarc_scores=metrics,changes=changes,changed_existing_files=sum(v['before_sha256'] is not None for v in changes.values()),
         new_runtime_files=sum(v['before_sha256'] is None for v in changes.values()),patch_sha256=sha(H/'CORE_0_4.patch'),
         weights_and_protected_solvers_unchanged=True,live_worker_changed=False,published=False,
         licensing_amendment='cellarc/LICENCE_NOTE.md')
(H/'FINAL_AUDIT.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(passed=True,integrity_checks=checks,changes=len(changes),cellarc=metrics),indent=2))
