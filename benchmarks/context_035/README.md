# CAEL 0.3.5 context & reasoning benchmark

Conversations of 5–50 messages, one question at the end, graded by predefined criteria (`grade.py`), not exact wording.
All systems get the identical transcript; CPU only; LLMs use greedy decoding, max 64 new tokens, float32, 8 threads and
one fixed system prompt (`run_llm.py`). Full tables, every CAEL failure and every item where a neural model beat CAEL
are in [RESULTS.md](RESULTS.md).

## Read this first: what each number can and cannot tell you

| Set | Questions | How independent | CAEL 0.3.5 (final) | Qwen2.5-0.5B | SmolLM2-360M |
|---|---|---|---|---|---|
| **Blind paraphrases, round 2** (`fresh2`) | 100 | written after the round-2 freeze, run once, same author | **47.0%** | 40.0% | 3.0% |
| **Blind paraphrases, round 1** (`fresh`, first run) | 100 | written after the round-1 freeze, run once, same author | **13.0%** (round-1 parser) | 46.0% | 8.0% |
| Held-out test (`test`) | 200 | **development-informed**: the CAEL author wrote these wording families before writing the parser | 93.0% | 52.5% | 5.5% |
| Development (`dev`) | 120 | tuned on | 100% | — | — |

* **The 93% is a development-informed result**, not an independent one: the test sentences come from phrasing
  families the CAEL author wrote and saw while building the rules (the test used the other half of each family, and
  some test-only wordings were covered by rules). Treat it as an upper bound for wording CAEL was built around.
* **The blind results are 13% (round 1) and 47% (round 2).** They are small (100 questions each) and written by the
  same author after each freeze, so they are only semi-independent. `fresh` was then used as the round-2 development set,
  so CAEL's later 100% on it means nothing.
* Rule coverage, not understanding: on unseen wordings CAEL still fails most memory (20%) and all planning (0%) questions
  of `fresh2`; it is strong on conflicts (100%) and references (73%).
* **No claim that CAEL outperforms Qwen is made here.** On `fresh2` CAEL scored 47% vs Qwen2.5-0.5B 40%, but the set is
  small and not independent; on `fresh` the round-1 CAEL lost 13% vs 46%. An independent, like-for-like comparison
  (questions written by a separate evaluator that never saw CAEL) is in `independent/` and reported separately.
* SmolLM2 mostly echoes the transcript's acknowledgements ("I see.", "Okay, noted.") — 77% of its test replies —
  despite the system prompt. That is a real failure on this transcript format, not a judgment of its general recall.
* Round-1 code was not committed before round 2 edited it; its outputs (`results/cael-0.3.5-r1-*`, md5 of the module
  `4cf69b17d09869a8d9e3b102472c213c`) are kept, but that exact code cannot be rerun. Round 2 module md5:
  `97d46221f76e7c55d0edd7060733a939`.

## Efficiency (held-out test)

| System | Peak RAM (process) | Median latency | p95 latency | Disk |
|---|---|---|---|---|
| CAEL 0.3.5 | 348 MB | 0.003 s | 0.035 s | ~535 MB bundle (memory module 77 KB + WordNet 31 MB) |
| Qwen2.5-0.5B-Instruct | 2,560 MB | 9.6 s | 14.9 s | ~954 MB (bf16 weights, run in float32) |
| SmolLM2-360M-Instruct | 2,046 MB | 8.6 s | 14.1 s | ~694 MB |

CAEL's peak RAM depends on which fallback routes a question touches (348 MB on `test`, ~660 MB on the paraphrase sets,
where unanswered questions reach the local Wikipedia/web fallbacks). Compression ratio (raw history bytes / structured
store bytes) is ~5–8×; it is **lossy by design**: small talk is not stored.

## Reproduce

```
python generate.py; python paraphrase.py; python paraphrase2.py
bash run_all.sh <python> <cael-0.3.4 checkout> <cael-0.3.5 checkout>      # round 1 (historical)
bash run_round2.sh <python> <cael-0.3.4 checkout> <cael-0.3.5 checkout>
python report.py
```
The before/after ladder switches improvements off with `CAEL_CONTEXT_FEATURES` (see `cael_unified/conversation_memory.py`).
