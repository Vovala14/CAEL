---
language:
- en
license: other
license_name: cael-non-commercial
license_link: https://huggingface.co/vynly/CAEL-0.4.0/blob/main/LICENSE
pipeline_tag: text-generation
tags:
- cael
- non-neural
- cellular-automata
- symbolic-reasoning
- custom-code
inference: false
---

# CAEL 0.4.1

[![HF downloads (30 days)](https://img.shields.io/huggingface/d/vynly/CAEL-0.4.0?label=HF%20downloads%20%2830%20days%29)](https://huggingface.co/vynly/CAEL-0.4.0)

**0.4.1** adds exact conversation skills, chat memory and web answers checked against a second source on top of the 0.4.0 core engines. In a self-judged 20-conversation comparison it scored about 796 Elo against Qwen3.5-0.8B fixed at 1000, so it is not a match for small LLMs at general chat. See [RELEASE_0_4_1.md](RELEASE_0_4_1.md).

A source-available Python assistant using non-neural symbolic, count and automaton engines. Version 0.4 updates core execution and adds example-induced local discrete transitions. There are no new neural weights or external LLM runtime answers. Finite readers, ambiguity and conversational gaps remain.

## Install and run

Use Python 3.12. Download and extract [CAEL-0.4.1.zip](https://github.com/Vovala14/CAEL/releases/download/v0.4.1/CAEL-0.4.1.zip) (and, for full chat, [cael-open-chat-v1.zip](https://github.com/Vovala14/CAEL/releases/download/v0.4.1/cael-open-chat-v1.zip) into `models/`), then from the extracted directory:

```bash
python -m pip install -r requirements-unified.txt
python -m cael_unified --download
python -m cael_unified --ui
```

Open http://127.0.0.1:8765. For terminal chat use `python -m cael_unified --mode chat`. Set `CAEL_WEB_SEARCH=0` to disable public web lookup. The integrity-checked resource archive is still **byte-identical 0.3.7** (562,714,794 bytes), versioned separately from the 0.4 source. Both are required. This is **custom Python code, not a Transformers-compatible checkpoint**. Picture/portrait weights are excluded.

## Core changes and measured scope

Indexed graph propagation replaces full rescans; ownership transactions validate before mutation; finite-domain ordering supports up to twelve objects; live references avoid the old recursion/link limit; count retrieval honours neighbour counts and deterministic ties. A bounded-checker interface fix resolves inherited tool orchestration failures.

The actual Assistant accepts `Infer discrete transition:` followed by JSON containing `examples` (integer-list input/output pairs), `query`, and optional `boundary` (`wrap` or `zero`). It learns request-local finite neighbourhood maps, ranks them by whole-pair validation, and reports unsupported cells/backoff guesses. This is not general program synthesis or proof of a unique hidden rule.

Authored confirmation: 60/60 positive answers versus 12/60 for unchanged 0.3.9.1; focused boundaries 16/16. These known-family, maintainer/AI-assisted cases establish scoped engineering gains. Relevant regressions: 671 passed, four inherited conversation failures remain. No general chatbot breakthrough is established.

## CellARC: official-harness reproduction

| Metric | Interpolation | Extrapolation |
|---|---:|---:|
| Tasks | 1000 | 1000 |
| Correct cells | 6361/11099 | 3815/10918 |
| Aggregate cell accuracy | **57.31%** | **34.94%** |
| Whole puzzles correct | **79/1000 (7.9%)** | **5/1000 (0.5%)** |

The exact frozen candidate was run through the **unmodified official CellARC symbolic evaluation harness**. Every prediction and full reply matches the original recorded run. No test-based solver change, training/validation fitting, metadata/gold input or omitted failure. This rerun is a reproduction on viewed tasks, not additional unseen evidence. Eight interpolation clarifications count fully wrong. Many cells use empirical/backoff guesses; exact extrapolation remains weak.

Download [cellarc-evidence.zip](https://huggingface.co/vynly/CAEL-0.4.0/resolve/v0.4.0/cellarc-evidence.zip), or see the [full public evidence and exact script](https://github.com/Vovala14/CAEL/tree/v0.4.0/benchmarks/core_040), including [reproduction instructions](https://github.com/Vovala14/CAEL/blob/v0.4.0/benchmarks/core_040/REPRODUCE.md). Official leaderboard inclusion is subject to maintainer review; no accepted rank, Qwen win or unrestricted architectural superiority is claimed. Other models were not rerun, and published LLM scores use smaller subsets/different protocols.

Original structured-run measurements: load 0.973 s, 2000-task inference 1.498 s, peak full process 109.13 MiB on one shared Windows host. The official harness has additional import overhead, including Torch/neural baseline definitions; no neural model is instantiated by the CAEL solver. These measurements are not an optimized-neural efficiency comparison.

## Downloads and licences

The live badge reports HF's counted query-file requests over 30 days, not unique users or all completed installs. `params.json` is a meaningful source/resource download configuration. Direct ZIP/resource clicks are not comprehensively counted; no simulated events or telemetry were added. For a full repository download: `hf download vynly/CAEL-0.4.0 --local-dir CAEL-0.4.0-download`.

CAEL: [non-commercial source-available licence](https://huggingface.co/vynly/CAEL-0.4.0/blob/main/LICENSE). Upstream resources retain their licences. CellARC is by **Miroslav Lžičař**: [dataset](https://huggingface.co/datasets/mireklzicar/cellarc_100k), [official code](https://github.com/mireklzicar/cellarc), [paper](https://arxiv.org/abs/2511.07908). The actual pinned dataset LICENSE is **CC BY 4.0**, despite the card's MIT tag; byte-preserved data and transformed evaluation files retain attribution. Official source licences are preserved separately. These results are our evaluation, not the author's endorsement. No live Vynly worker change is part of this release.
