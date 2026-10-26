"""Run a small instruction-tuned LLM on the context benchmark: CPU only, greedy decoding, full history via the chat template.

    python run_llm.py --model Qwen/Qwen2.5-0.5B-Instruct --split dev --tag qwen2.5-0.5b
Same transcripts as CAEL plus one fixed system prompt (SYSTEM; --no-system drops it), max_new_tokens 64,
float32, a fixed number of torch threads (recorded). RAM = process peak working set; it includes the loaded weights.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['HIP_VISIBLE_DEVICES'] = ''
os.environ['HF_HUB_OFFLINE'] = '1'
THREADS = next((int(a.split('=')[1]) for a in sys.argv if a.startswith('--threads=')), 8)
for var in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[var] = str(THREADS)
SYSTEM = "You are a helpful assistant. Answer the user's last question using what was said earlier in the conversation."
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from grade import grade  # noqa: E402
from summarize import summary  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument('--model', required=True)
p.add_argument('--split', default='dev')
p.add_argument('--tag', required=True)
p.add_argument('--threads', type=int, default=THREADS)  # pass as --threads=N
p.add_argument('--no-system', action='store_true')
p.add_argument('--max-new-tokens', type=int, default=64)
p.add_argument('--limit', type=int, default=0)
p.add_argument('--quantize', choices=['none', 'int8'], default='none')  # int8 = torch dynamic quantization of Linear layers
args = p.parse_args()

import psutil  # noqa: E402
import torch  # noqa: E402
from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: E402

torch.set_num_threads(args.threads)
torch.set_num_interop_threads(1)
proc = psutil.Process()
rss0 = proc.memory_info().rss
t0 = time.perf_counter()
tok = AutoTokenizer.from_pretrained(args.model)
model = AutoModelForCausalLM.from_pretrained(args.model, dtype=torch.float32).to('cpu').eval()
if args.quantize == 'int8':
    model = torch.ao.quantization.quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8)
load_seconds = time.perf_counter() - t0
rss_loaded = proc.memory_info().rss

items = [json.loads(line) for line in (HERE / f'{args.split}.jsonl').open(encoding='utf-8')]
if args.limit:
    items = items[:args.limit]
rows = []
for item in items:
    messages = item['history'] + [dict(role='user', content=item['question'])]
    if not args.no_system:
        messages = [dict(role='system', content=SYSTEM)] + messages
    # enable_thinking=False: Qwen3 answers directly (its templated non-thinking mode); other templates ignore the flag
    ids = tok.apply_chat_template(messages, add_generation_prompt=True, return_tensors='pt', return_dict=True, enable_thinking=False)
    t = time.perf_counter()
    c = time.process_time()
    with torch.inference_mode():
        out = model.generate(**ids, max_new_tokens=args.max_new_tokens, do_sample=False, temperature=None, top_p=None, top_k=None,
                             pad_token_id=tok.pad_token_id or tok.eos_token_id)
    wall, cpu = time.perf_counter() - t, time.process_time() - c
    reply = tok.decode(out[0, ids['input_ids'].shape[1]:], skip_special_tokens=True)
    reply = reply.split('</think>')[-1].strip()
    rows.append(dict(id=item['id'], category=item['category'], n_messages=item['n_messages'], question=item['question'], reply=reply,
                     route='llm', ok=grade(reply, item['criteria']), seconds=round(wall, 4), cpu_seconds=round(cpu, 4),
                     prompt_tokens=int(ids['input_ids'].shape[1]), compression=None))

mem = proc.memory_info()
peak = getattr(mem, 'peak_wset', None) or mem.rss
out_dir = HERE / 'results'
out_dir.mkdir(exist_ok=True)
with (out_dir / f'{args.tag}-{args.split}.jsonl').open('w', encoding='utf-8', newline='\n') as f:
    for row in rows:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')
s = summary(rows)
s.update(system=args.tag, model=args.model, split=args.split, load_seconds=round(load_seconds, 2), rss_loaded_mb=round(rss_loaded / 2**20, 1),
         peak_ram_mb=round(peak / 2**20, 1), python_baseline_mb=round(rss0 / 2**20, 1), threads=args.threads, device='cpu',
         system_prompt=None if args.no_system else SYSTEM, decoding=f'greedy, max_new_tokens={args.max_new_tokens}, ' + ('float32' if args.quantize == 'none' else 'dynamic int8 Linear'), torch=torch.__version__)
(out_dir / f'{args.tag}-{args.split}.summary.json').write_text(json.dumps(s, indent=1), encoding='utf-8')
print(json.dumps(s, indent=1))
