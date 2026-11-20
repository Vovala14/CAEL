"""Score CAEL's non-neural ARC solver on a folder of ARC tasks (ARC-AGI-1 or ARC-AGI-2 JSON format).

    git clone https://github.com/fchollet/ARC-AGI
    python evaluate_arc.py --data ARC-AGI/data/evaluation --out results/my_arc_run

Rules (the same as the published 0.4.4 numbers):
- pass@2: for each test input the solver may give two grids; a task counts as solved only if every test output is
  matched exactly by one of its two grids;
- the solver sees only the demonstration pairs and the test inputs; the test outputs are read by this parent process
  after the solver has answered;
- each task runs in its own process with a wall-clock limit (default 10 s, CPU only), and a task that runs over counts
  as unsolved.

Writes <out>.jsonl (one row per task) and <out>.summary.json, and prints the total.
"""
import argparse
import json
import multiprocessing as mp
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent


def child(task, seconds, queue):
    sys.path.insert(0, str(HERE))
    sys.dont_write_bytecode = True
    try:
        from cael_unified import arc_solver
        outs = [arc_solver.attempts(task['train'], t['input'], seconds=max(1.0, seconds - 1)) for t in task['test']]
        queue.put(('ok', outs))
    except Exception as exc:
        queue.put(('error', repr(exc)[:300]))


def run_task(path, seconds):
    task = json.loads(Path(path).read_text())
    blind = dict(train=task['train'], test=[dict(input=t['input']) for t in task['test']])
    q = mp.Queue()
    p = mp.Process(target=child, args=(blind, seconds, q))
    started = time.time()
    p.start()
    p.join(seconds + 5)
    if p.is_alive():
        p.terminate(); p.join()
        return dict(id=Path(path).stem, solved=False, status='timeout', seconds=round(time.time() - started, 1))
    status, outs = q.get() if not q.empty() else ('error', 'no result')
    if status != 'ok':
        return dict(id=Path(path).stem, solved=False, status=status, error=outs)
    right = [any(a == t['output'] for a in attempts[:2]) for attempts, t in zip(outs, task['test'])]
    return dict(id=Path(path).stem, solved=all(right), tests=len(right), right=sum(right), attempted=sum(bool(a) for a in outs),
                seconds=round(time.time() - started, 1), status='ok')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data', required=True, help='folder of ARC task .json files')
    ap.add_argument('--out', default='results/arc_run', help='output path prefix')
    ap.add_argument('--seconds', type=float, default=10.0, help='wall-clock limit per task (default 10)')
    ap.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 2) - 2), help='tasks run side by side')
    ap.add_argument('--limit', type=int, default=None, help='only the first N tasks (for a quick check)')
    args = ap.parse_args()
    paths = sorted(Path(args.data).glob('*.json'))[:args.limit]
    if not paths:
        sys.exit(f'no .json tasks in {args.data}')
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    with ThreadPoolExecutor(args.workers) as pool:
        rows = list(pool.map(lambda p: run_task(p, args.seconds), paths))
    (out.with_suffix('.jsonl')).write_text('\n'.join(json.dumps(r) for r in rows) + '\n')
    solved = sum(r['solved'] for r in rows)
    summary = dict(tasks=len(rows), solved=solved, percent=round(100 * solved / len(rows), 2), attempted=sum(r.get('attempted', 0) > 0 for r in rows),
                   timeouts=sum(r['status'] == 'timeout' for r in rows), errors=sum(r['status'] == 'error' for r in rows),
                   seconds_per_task=args.seconds, workers=args.workers, wall_seconds=round(time.time() - started, 1))
    (out.with_suffix('.summary.json')).write_text(json.dumps(summary, indent=1))
    print(f'solved {solved} of {len(rows)} ({summary["percent"]}%), attempted {summary["attempted"]}, timeouts {summary["timeouts"]}, '
          f'errors {summary["errors"]}')


if __name__ == '__main__':
    main()
