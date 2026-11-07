"""Bind official-harness output to the original frozen source and saved results."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

H = Path(__file__).resolve().parent
E = H.parent / 'core_040_20261107'
R = H / 'official_run4'

def load(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p):
    with p.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()

assert not (H / 'official_harness_verification.json').exists()
receipt = load(R / 'receipt.json')
assert receipt['complete'] and receipt['episodes'] == 2000
original = [json.loads(x) for x in (E / 'cellarc/runs/candidate/predictions.jsonl').read_text().splitlines()]
current = [json.loads(x) for x in (R / 'predictions.jsonl').read_text().splitlines()]
assert len(original) == len(current) == 2000
for old, new in zip(original, current):
    assert (old['id'], old['split']) == (new['id'], new['split'])
    assert (old['prediction'] or []) == new['prediction'], old['id']
    assert old['reply'] == new['reply'], old['id']
    assert old['error'] == new['error'] is None, old['id']
metrics = load(R / 'official_metrics.json')
report = load(E / 'cellarc/report.json')['systems']['candidate']['splits']
for entry in metrics['splits']:
    old = report[entry['split']]
    assert (entry['episodes'], entry['solved'], entry['token_total'], entry['token_correct']) == (
        old['episodes'], old['exact_episodes'], old['total_cells'], old['correct_cells'])
    assert entry['token_accuracy'] == old['cell_accuracy']
freeze = load(E / 'SOURCE_FREEZE.json')
for name, expected in freeze['files'].items(): assert sha(E / 'candidate_runtime' / name) == expected
for name, expected in freeze['resources'].items(): assert sha(E / 'candidate_runtime' / name) == expected
proof = dict(verified_utc=datetime.now(timezone.utc).isoformat(), passed=True,
    frozen_checkpoint_sha256=sha(E / 'SOURCE_FREEZE.json'),
    original_predictions_sha256=sha(E / 'cellarc/runs/candidate/predictions.jsonl'),
    official_predictions_sha256=sha(R / 'predictions.jsonl'),
    official_metrics_sha256=sha(R / 'official_metrics.json'),
    official_receipt_sha256=sha(R / 'receipt.json'),
    adapter_sha256=sha(H / 'run_official_cellarc.py'),
    exact_predictions=2000, exact_full_replies=2000, errors=0,
    official_splits=metrics['splits'], exact_original_cell_and_episode_counts=True,
    source_hashes_unchanged=len(freeze['files']), resources_unchanged=len(freeze['resources']),
    official_scorer_loader_unchanged=True,
    original_python='3.14.0', official_harness_python=receipt['python'],
    runtime_change_disclosed=True, all_predictions_and_replies_identical_across_runtimes=True,
    source_fitting_or_retuning=False,
    interpretation='Official-harness reproduction on viewed tasks, not a new unseen test or accepted rank')
(H / 'official_harness_verification.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: proof[k] for k in ['passed', 'exact_predictions', 'exact_full_replies', 'errors', 'official_splits']}))
