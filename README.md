# CAEL

A chat assistant with no neural network: cellular automata, rules and retrieval, on CPU.

[![version 0.4.1](https://img.shields.io/badge/version-0.4.1-blue)](https://github.com/Vovala14/CAEL/releases/tag/v0.4.1)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![CPU only](https://img.shields.io/badge/CPU-only-green)
[![license: source-available, non-commercial](https://img.shields.io/badge/license-source--available%2C_non--commercial-blue)](LICENSE)

In a self-judged 20-conversation comparison, CAEL 0.4.1 scored about **796 Elo** against Qwen3.5-0.8B fixed at 1000 (95% interval 611–915; 3 wins / 14 losses / 3 ties). The same development agent wrote the tests and judged them. That is a conflict of interest. CAEL does not match Qwen3.5-0.8B at general chat. See [RELEASE_0_4_1.md](RELEASE_0_4_1.md).

## Quick start

Use Python 3.12. From this checkout, or from the extracted [CAEL-0.4.1.zip](https://github.com/Vovala14/CAEL/releases/download/v0.4.1/CAEL-0.4.1.zip) release (extract [cael-open-chat-v1.zip](https://github.com/Vovala14/CAEL/releases/download/v0.4.1/cael-open-chat-v1.zip) into `models/` for the full open-chat index):

```bash
python -m pip install -r requirements-unified.txt
python -m cael_unified --download
python -m cael_unified --ui
```

Open http://127.0.0.1:8765. For terminal chat use `python -m cael_unified --mode chat`. Set `CAEL_WEB_SEARCH=0` to disable public web lookup. `--download` fetches the integrity-checked resource archive, still **byte-identical 0.3.7** (562,714,794 bytes), versioned separately from the 0.4 source. Both are required. This is **custom Python code, not a Transformers-compatible checkpoint**. Picture/portrait weights are excluded.

## A real chat

This is one unchanged terminal session of CAEL 0.4.1 (`python -m cael_unified --mode chat` on Python 3.12), with the 0.3.7 bundle and `models/cael-open-chat-v1` installed and web lookup left on. The same text is in [docs/demo-0.4.1-chat.txt](docs/demo-0.4.1-chat.txt). The open question is answered off-topic. The clock-time question is exact.

```text
CAEL 0.4.1: chat, helper, emoji and small pictures. Type quit to exit.
You: How's your week going?
If you are feeling battered, something is wrong. I would overeat slightly, focusing on quality food at 10am and 3pm. Avoid the usual: trans fats and refined sugars. Make sure you have enough salt (yup, salt), magnesium and healthy fatty acids in your diet. Also make sure you are getting enough sleep. Forego all steady-state aerobic work, though you may want to do a lighter version of your normal lifting routine during your week off. If your significant other or boss are giving you a hard time, I would do my best to avoid them too during your recovery time.
You: My train leaves at 08:50 and the trip takes 2 hours 35 minutes. When do I arrive?
You arrive at **11:25** (08:50 + 2 h 35 min).
You: quit
```

## Where it stands

| Good at | Still behind |
| --- | --- |
| Math and quantities, rates, clock times, schedules, and short logic | Open chat against Qwen3.5-0.8B (about 796 Elo; 3 wins / 14 losses / 3 ties) |

Other known gaps, from the same comparison: web lookups that decline when two sources do not agree, generic replies, missed follow-ups, and off-topic retrieved answers. On CellARC, whole puzzles are still rare (79/1000 interpolation, 5/1000 extrapolation).

## What 0.4.1 is

**0.4.1** adds exact conversation skills, chat memory, and web answers checked against a second source, on top of the 0.4.0 core engines. Open chat can retrieve from about 285,000 human-written answers (Stack Exchange, OpenAssistant, and databricks-dolly-15k). There are no neural weights and no external LLM writes the replies. Finite readers, ambiguity, and conversational gaps remain.

## Core changes and measured scope

Indexed graph propagation replaces full rescans; ownership transactions validate before mutation; finite-domain ordering supports up to twelve objects; live references avoid the old recursion/link limit; count retrieval honours neighbour counts and deterministic ties. A bounded-checker interface fix resolves inherited tool orchestration failures.

The Assistant accepts `Infer discrete transition:` followed by JSON containing `examples` (integer-list input/output pairs), `query`, and optional `boundary` (`wrap` or `zero`). It learns request-local finite neighbourhood maps, ranks them by whole-pair validation, and reports unsupported cells and backoff guesses. This is not general program synthesis or proof of a unique hidden rule.

Authored confirmation: 60/60 positive answers versus 12/60 for unchanged 0.3.9.1; focused boundaries 16/16. These known-family, maintainer/AI-assisted cases establish scoped engineering gains. Relevant regressions: 671 passed, four inherited conversation failures remain. No general chatbot breakthrough is established.

## CellARC: official-harness reproduction

| Metric | Interpolation | Extrapolation |
| --- | ---: | ---: |
| Tasks | 1000 | 1000 |
| Correct cells | 6361/11099 | 3815/10918 |
| Aggregate cell accuracy | **57.31%** | **34.94%** |
| Whole puzzles correct | **79/1000 (7.9%)** | **5/1000 (0.5%)** |

The exact frozen candidate was run through the **unmodified official CellARC symbolic evaluation harness**. Every prediction and full reply matches the original recorded run. No test-based solver change, training or validation fitting, metadata or gold input, or omitted failure. This rerun is a reproduction on viewed tasks, not additional unseen evidence. Eight interpolation clarifications count fully wrong. Many cells use empirical or backoff guesses; exact extrapolation remains weak.

Download [cellarc-evidence.zip](https://huggingface.co/vynly/CAEL-0.4.0/resolve/v0.4.0/cellarc-evidence.zip), or see the [full public evidence and exact script](https://github.com/Vovala14/CAEL/tree/v0.4.0/benchmarks/core_040), including [reproduction instructions](https://github.com/Vovala14/CAEL/blob/v0.4.0/benchmarks/core_040/REPRODUCE.md). Official leaderboard inclusion is subject to maintainer review; no accepted rank, Qwen win, or unrestricted architectural superiority is claimed. Other models were not rerun, and published LLM scores use smaller subsets and different protocols.

Original structured-run measurements: load 0.973 s, 2000-task inference 1.498 s, peak full process 109.13 MiB on one shared Windows host. The official harness has additional import overhead, including Torch and neural baseline definitions; no neural model is instantiated by the CAEL solver. These measurements are not an optimized-neural efficiency comparison.

## Downloads and licences

[![HF downloads (30 days)](https://img.shields.io/huggingface/d/vynly/CAEL-0.4.0?label=HF%20downloads%20%2830%20days%29)](https://huggingface.co/vynly/CAEL-0.4.0)

The live badge reports Hugging Face's counted query-file requests over 30 days, not unique users or all completed installs. `params.json` is a meaningful source and resource download configuration. Direct ZIP and resource clicks are not comprehensively counted; no simulated events or telemetry were added. For a full repository download: `hf download vynly/CAEL-0.4.0 --local-dir CAEL-0.4.0-download`.

The Hugging Face model card, including its YAML front matter, is [MODEL_CARD.md](MODEL_CARD.md). Nothing in this repository copies `README.md` to Hugging Face.

CAEL is [source-available, non-commercial](LICENSE) ([same terms on Hugging Face](https://huggingface.co/vynly/CAEL-0.4.0/blob/main/LICENSE)). Upstream resources retain their licences. CellARC is by **Miroslav Lžičař**: [dataset](https://huggingface.co/datasets/mireklzicar/cellarc_100k), [official code](https://github.com/mireklzicar/cellarc), [paper](https://arxiv.org/abs/2511.07908). The actual pinned dataset LICENSE is **CC BY 4.0**, despite the card's MIT tag; byte-preserved data and transformed evaluation files retain attribution. Official source licences are preserved separately. These results are our evaluation, not the author's endorsement. No live Vynly worker change is part of this release.

If this experiment interests you, starring and watching releases is how you'll hear about the next build.
