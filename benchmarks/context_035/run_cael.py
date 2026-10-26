"""Run one CAEL checkout on the context benchmark (CPU only, web search off, one process per run).

    python run_cael.py --root <cael checkout> --split dev --tag cael-0.3.4
Writes results/<tag>-<split>.jsonl (one line per question) and results/<tag>-<split>.summary.json.
RAM: process peak working set (psutil peak_wset on Windows, else ru_maxrss) after the whole run, plus resident memory after loading.
Compression ratio: raw history bytes / bytes of CAEL's structured conversation store, when the checkout has one.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from grade import grade  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument('--root', required=True)
p.add_argument('--split', default='dev')
p.add_argument('--tag', required=True)
p.add_argument('--limit', type=int, default=0)
args = p.parse_args()

os.environ['CAEL_WEB_SEARCH'] = '0'
os.environ.pop('BRAVE_API_KEY', None)
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['HIP_VISIBLE_DEVICES'] = ''
root = str(Path(args.root).resolve())
sys.path.insert(0, root)
os.chdir(root)

import psutil  # noqa: E402

proc = psutil.Process()
rss0 = proc.memory_info().rss
t0 = time.perf_counter()
from cael_unified.assistant import Assistant  # noqa: E402
assistant = Assistant()
try:
    from cael_unified import conversation_memory as memory_module
except ImportError:
    memory_module = None
load_seconds = time.perf_counter() - t0
rss_loaded = proc.memory_info().rss

items = [json.loads(line) for line in (HERE / f'{args.split}.jsonl').open(encoding='utf-8')]
if args.limit:
    items = items[:args.limit]
out_dir = HERE / 'results'
out_dir.mkdir(exist_ok=True)
rows = []
for item in items:
    messages = item['history'] + [dict(role='user', content=item['question'])]
    t = time.perf_counter()
    c = time.process_time()
    try:
        r = assistant.respond(messages)
        reply, route = r.get('response', ''), r.get('route', '')
    except Exception as exc:  # a crash is a wrong answer, not a skipped item
        reply, route = f'ERROR {type(exc).__name__}: {exc}', 'error'
    wall, cpu = time.perf_counter() - t, time.process_time() - c
    ratio = None
    if memory_module is not None and hasattr(memory_module, 'compression_stats'):
        raw, packed = memory_module.compression_stats(item['history'])
        ratio = round(raw / packed, 2) if packed else None
    rows.append(dict(id=item['id'], category=item['category'], n_messages=item['n_messages'], question=item['question'],
                     reply=reply, route=route, ok=grade(reply, item['criteria']), seconds=round(wall, 4), cpu_seconds=round(cpu, 4),
                     compression=ratio))

mem = proc.memory_info()
peak = getattr(mem, 'peak_wset', None)
if peak is None:
    import resource
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
with (out_dir / f'{args.tag}-{args.split}.jsonl').open('w', encoding='utf-8', newline='\n') as f:
    for row in rows:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')

from summarize import summary  # noqa: E402
s = summary(rows)
s.update(system=args.tag, split=args.split, load_seconds=round(load_seconds, 2), rss_loaded_mb=round(rss_loaded / 2**20, 1),
         peak_ram_mb=round(peak / 2**20, 1), python_baseline_mb=round(rss0 / 2**20, 1), threads=1, device='cpu')
(out_dir / f'{args.tag}-{args.split}.summary.json').write_text(json.dumps(s, indent=1), encoding='utf-8')
print(json.dumps(s, indent=1))
