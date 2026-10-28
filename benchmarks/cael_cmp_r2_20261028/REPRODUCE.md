# Evidence and CAEL packaging replay

final.jsonl is the original frozen80-item set. candidate.jsonl/qwen3.jsonl/
qwen35.jsonl are the complete original replies and preliminary flags.
semantic_review_*.json and the Markdown reviews retain every full-reply
decision/reason; report.json contains paired/category/functional/latency/RAM
statistics. run_settings.json records official revisions/templates/sampling,
CPU precisions and output budget. The original two-tokenizer cap check is
budget_audit.json. Never train on final questions or Qwen replies.

After installing the resource bundle, run:

```bash
python benchmarks/cael_cmp_r2_20261028/replay_candidate.py --out replay_037.json
```

This offline replay compares all80 actual unified CAEL replies/routes with the
recorded r2 output, using the same system prompt, histories, mode and seed.
It is a packaging regression on already-viewed data, not another unseen test.
It does not download/run Qwen, use internet retrieval or execute generated
Python natively. Semantic overrides are human/author review evidence and not
a claim that automatic keyword grading establishes answer quality.

Opponents used official hash-pinned checkpoints/tokenizers and non-thinking
templates,1024 output tokens,16384 input reject-not-crop, recommended sampling,
eight intra/one inter CPU threads, mkldnn off. Qwen3.5's full multimodal
checkpoint was loaded text-only. Cross-family/independent generalization is
not established. The original sealed metadata had a stale64 distinct-input
label; actual frozen file has80 distinct inputs, documented separately.
