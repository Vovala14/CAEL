"""Score exact saved predictions only after both streams are sealed."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import hashlib,json,statistics
H=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8'))
seal=load(H/'INPUT_SEAL.json');assert sha(H/'score.py')==seal['evaluator_files']['score.py']
receipts={}
for engine in ['baseline','candidate']:
    rec=load(H/'runs'/engine/'receipt.json');assert rec['complete'] and rec['total']==2000
    assert sha(H/'runs'/engine/'predictions.jsonl')==rec['predictions_sha256'];receipts[engine]=rec
# No gold is opened until both actual inference receipts exist.
assert sha(H/'gold.jsonl')==seal['artifacts']['gold.jsonl']
gold=[json.loads(line) for line in (H/'gold.jsonl').read_text().splitlines()]
report={};decisions={}
for engine,rec in receipts.items():
    predictions=[json.loads(line) for line in (H/'runs'/engine/'predictions.jsonl').read_text().splitlines()]
    assert len(predictions)==len(gold)==2000
    rows=[]
    for expected,actual in zip(gold,predictions,strict=True):
        assert (expected['id'],expected['split'])==(actual['id'],actual['split'])
        target=expected['solution'];pred=actual['prediction']
        assert type(target) is list and target and all(type(v) is int for v in target)
        correct=sum(x==y for x,y in zip(target,pred,strict=True)) if pred is not None else 0
        rows.append(dict(id=actual['id'],split=actual['split'],correct_cells=correct,total_cells=len(target),
                         exact=pred==target,invalid=pred is None,error=actual['error']))
    splits={}
    for split in ['test_interpolation','test_extrapolation']:
        part=[r for r in rows if r['split']==split];outputs=[r for r in predictions if r['split']==split]
        correct=sum(r['correct_cells'] for r in part);total=sum(r['total_cells'] for r in part)
        supported=sum(sum((r['reply'].get('automaton') or {}).get('supported',[])) for r in outputs if r['reply'])
        diag=Counter((r['reply'].get('automaton') or {}).get('status','no-native-model') for r in outputs if r['reply'])
        splits[split]=dict(episodes=len(part),correct_cells=correct,total_cells=total,cell_accuracy=correct/total,
            mean_episode_cell_accuracy=statistics.mean(r['correct_cells']/r['total_cells'] for r in part),
            exact_episodes=sum(r['exact'] for r in part),episode_accuracy=sum(r['exact'] for r in part)/len(part),
            invalid=sum(r['invalid'] for r in part),errors=sum(bool(r['error']) for r in part),
            selected_hypothesis_supported_cells=supported,diagnostic_statuses=dict(diag),
            median_response_seconds=statistics.median(r['seconds'] for r in outputs))
    report[engine]=dict(splits=splits,load_seconds=rec['load_seconds'],inference_seconds=rec['inference_seconds'],
                       peak_process_rss_bytes=rec['peak_process_rss_bytes'],predictions_sha256=rec['predictions_sha256'])
    decisions[engine]=rows
    (H/(engine+'_grades.json')).write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
out=dict(scored_utc=datetime.now(timezone.utc).isoformat(),complete=True,systems=report,
    input_seal_sha256=sha(H/'INPUT_SEAL.json'),gold_sha256=sha(H/'gold.jsonl'),
    scope='Full official CellARC interpolation/extrapolation, no per-episode oracle metadata, actual Assistant structured interface',
    cautions=['Per-cell/token accuracy differs from exact-episode accuracy','Predicted guesses remain in every denominator',
              'No tuning after test access','Published leaderboard model protocols/subsets/oracle metadata differ',
              'Not general chat competence or an independent reproduction of other models'])
(H/'report.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
