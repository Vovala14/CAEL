# CAEL 0.3.6

CAEL 0.3.6 adds conversation reasoning and compact spelling tables to the existing
non-neural assistant. It retains the text, helper, math, Python, retrieval, story,
prompt and emoji engines. Picture and portrait model weights are excluded.

The context implementation was frozen at `e7fa521` before the final evaluation.
Release preparation changes version labels, documentation and packaging only;
the reasoning implementation and learned model files are unchanged from that freeze.
The existing CAEL Non-Commercial License and third-party notices are retained.

## Changes since 0.3.4

- Structured conversation records for entities, attributes, corrections, events,
  source disagreements and plan progress (0.3.5).
- Clause-based retrieval using WordNet lemmas/synonyms, typed values, reported
  statements and corrections; bounded compositional operations over stated facts
  and abstention when the supported interpretation is missing (0.3.6).
- Compact hash/value and word-group arrays for spelling lookups, with
  memory-mapped caches instead of millions of resident Python dictionary objects.
- Existing architecture retained: symbolic rules, counts and automaton components;
  no neural network or transformer is used by CAEL at runtime.

## Context benchmark

Saved final runs on the same 400 locally authored synthetic conversations:

| System | Correct | Accuracy |
|---|---:|---:|
| CAEL 0.3.5 | 53/400 | 13.25% |
| CAEL 0.3.6 | 122/400 | 30.50% |
| Qwen2.5-0.5B-Instruct, float32 | 102/400 | 25.50% |
| Qwen3-0.6B, float32 | 121/400 | 30.25% |
| SmolLM2-360M-Instruct, float32 | 28/400 | 7.00% |

CAEL improved by 69 answers / 17.25 percentage points over 0.3.5 on this set.
Its one-answer difference from Qwen3 is effectively a tie. This is not evidence
of a general lead over either Qwen model or a new external leaderboard score.
No new HellaSwag, Tiny ToM or NNAI-Bench score is claimed for 0.3.6.

CAEL still misses 278/400. Category accuracies: conflict handling 70%, memory 42%,
unsupported-question handling 35%, updates 24%, reasoning 20%, planning 12%,
references 10%. Clear limitations remain in reference resolution, plans and
avoiding unsupported answers.

The evaluator brief describes a separate model/writer producing questions after
the freeze without source access. This was a local evaluation, not an independently
verified external human evaluation. Grading uses keyword/phrase heuristics; the
saved flags were recalculated and matched, which does not establish semantic
correctness of every judgement. Earlier 93% development-informed results are
not an independent measure of this release.

All runners use CPU. CAEL records one thread; comparison LMs use eight, greedy
decoding and 64 new tokens. Qwen3 uses its non-thinking template. Float32 runs
are reported above; the anomalously weak bfloat16 Qwen3 run is not used to claim
a lead. Saved summaries do not pin exact LLM weight revisions.

The actual histories contain 91 conversations of at most 20 messages, 196 of
21–50 messages and 113 of 100–200 messages. The legacy summary's bucket named
"21-50 messages" includes all histories longer than 20 and must not be read as
an accurate length breakdown.

## Evidence and reproduction

- Input: [final.jsonl](benchmarks/context_036/final.jsonl), SHA-256
  `525aa74580014013838254a6b7e2d5dc5d358d00042a766e6323754ea3427fbd`.
- Protocol: [evaluator brief](benchmarks/context_036/EVALUATOR_BRIEF.md).
- Saved outputs and summaries: `benchmarks/context_035/results/*-final.jsonl`
  and `*-final.summary.json` for the five systems above.
- Runner and grader: `benchmarks/context_035/run_cael.py`, `run_llm.py`,
  `grade.py`, `summarize.py`. The committed float32 runner is retained.

To rerun CAEL after installing the release dependencies and downloading its bundle:

```bash
python -c "import shutil; shutil.copyfile('benchmarks/context_036/final.jsonl', 'benchmarks/context_035/final.jsonl')"
python benchmarks/context_035/run_cael.py --root . --split final --tag cael-0.3.6-reproduction
```

The benchmark runner also needs `psutil`. Comparison LMs separately need their
own Transformers dependencies; these are not part of CAEL's runtime.

## Release verification

The text-only release regression selection passed **172 tests and 129 subtests**
covering conversation memory/reasoning, release guards, everyday answers, image-prompt
writing, orchestrator routing, Python helpers, small talk and typo context. This is
a focused selection, not a full-suite pass claim. All 97 archived members were
checksum-verified and 73 packaged runtime files matched the local model files.
No private source photos or private conversations were opened.

## Install

```bash
git clone --branch v0.3.6 https://github.com/Vovala14/CAEL.git
cd CAEL
python -m pip install -r requirements-unified.txt
python -m cael_unified --download
python -m cael_unified --ui
```

Alternatively, extract `CAEL-0.3.6.zip` and run the last three commands there.
`cael-0.3.6.cael` is the checksum-verified no-images model archive; the source
ZIP is separate. Model files are inherited unchanged from the verified 0.3.4
archive, with updated bundle metadata. The new context capabilities are code
changes, not a newly trained language checkpoint. Existing local model selections
are preserved by the installer; a clean directory is recommended for reproduction.
