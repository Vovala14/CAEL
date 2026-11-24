# CAEL

A chat assistant with no neural network: cellular automata, rules and retrieval, on CPU.

[![version 0.4.5](https://img.shields.io/badge/version-0.4.5-blue)](https://github.com/Vovala14/CAEL/releases/tag/v0.4.5)
[![HF downloads](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fhuggingface.co%2Fapi%2Fmodels%2Fvynly%2FCAEL-0.4.5&query=%24.downloads&label=HF%20downloads&color=blue)](https://huggingface.co/vynly/CAEL-0.4.5)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![CPU only](https://img.shields.io/badge/CPU-only-green)
[![license: source-available, non-commercial](https://img.shields.io/badge/license-source--available%2C_non--commercial-blue)](LICENSE)

**0.4.5** adds chess, story reasoning and word problems, and widens the ARC solver, still with no neural network:

- **Chess in chat:** play CAEL's own non-neural engine ("let's play chess"), get the best move for a position, rank
  every legal move, or review a game. The engine beat Cyber Chess AI on its "Hard Pro" level (checkmate in 28 moves),
  and won games against ChatGPT 6.1 Terra (2–0) and Grok 4.7 (1–0). Play it in your browser:
  [vynly/cael-chess](https://huggingface.co/spaces/vynly/cael-chess).
- **Stories:** a world model reads who moved where and who has what, then answers from that state. On the bAbI test
  split, the score went from 241/500 to **494/500**.
- **Word problems:** question-guided arithmetic ignores numbers that don't matter. On the SVAMP test split, the score
  went from 58/300 to **70/300**, with no previously correct answer lost.
- **ARC-AGI-1:** a compositional program search and a per-cell rule learner were added. The solver now solves **83 of 400
  evaluation tasks (20.75%, pass@2)**, at 60 seconds per task on a CPU.

Release notes: [RELEASE_0_4_5.md](RELEASE_0_4_5.md). Architecture (0.4.4 base): [ARCHITECTURE_0_4_4.md](ARCHITECTURE_0_4_4.md).

## Reproduce the ARC result

```bash
python -m pip install -r requirements-unified.txt
git clone https://github.com/fchollet/ARC-AGI
python evaluate_arc.py --data ARC-AGI/data/evaluation --out results/my_arc_eval
```

| Set | Solved (pass@2, 60 s per task, CPU) |
|---|---:|
| ARC-AGI-1 evaluation | **83 / 400** |
| ARC-AGI-1 training (development set) | 192 / 400 |
| ARC-AGI-2 evaluation | 1 / 120 |

Compare your run task by task with [results/arc_agi_1_evaluation_0.4.5.jsonl](results/arc_agi_1_evaluation_0.4.5.jsonl).
- The solver was developed on the training set only.
- The evaluation set was scored at milestones but never used to fix anything, so a run on a set CAEL has never seen
  (for example ConceptARC) is especially welcome.

## Dataset: CAEL Verified Reasoning

[![HF dataset](https://img.shields.io/badge/HF%20dataset-cael--verified--reasoning-blue)](https://huggingface.co/datasets/vynly/cael-verified-reasoning)

CAEL's exact solvers also generate training data for other models:
[**vynly/cael-verified-reasoning**](https://huggingface.co/datasets/vynly/cael-verified-reasoning). It holds 2,000,000
reasoning problems whose answers are computed, not guessed, plus a 1,427-item hard evaluation split.
- **Areas:** arithmetic, dates and times, logic and line-ups, conflicting sources, chat memory, unanswerable questions,
  ARC-style grids, and multi-step composites.
- **Each row** has step-by-step working and a difficulty from 1 to 5.
- **Licence:** CC BY 4.0.
- **Verifier:** [`datasets/verified_reasoning/verify.py`](datasets/verified_reasoning/verify.py) checks any model's reply
  against a row, so it can serve as an RL reward.
- **Generator:** [`datasets/verified_reasoning/generate.py`](datasets/verified_reasoning/generate.py) makes as many fresh
  problems as you want:

```bash
python datasets/verified_reasoning/generate.py --out mydata --n 100000 --seed 123
```

## Quick start

Use Python 3.12. From this checkout, or from the extracted [CAEL-0.4.5.zip](https://github.com/Vovala14/CAEL/releases/download/v0.4.5/CAEL-0.4.5.zip) release (extract [cael-open-chat-v1.1.zip](https://github.com/Vovala14/CAEL/releases/download/v0.4.5/cael-open-chat-v1.1.zip) into `models/` for the full open-chat index and the fielded index):

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
| Math and quantities, rates, clock times, dates, line-up and if-then logic, sources that disagree, memory updates, emotional support, everyday Python questions, explanations and tips with their follow-ups | Problem types the hand-written readers were not written for (they get an honest refusal); practical multi-turn how-to chats outside the authored desks |

Other known gaps: facts outside CAEL's knowledge depend on the web, and some follow-ups still get advice of the right kind but not specific to the case. On CellARC, whole puzzles are still rare (79/1000 interpolation, 5/1000 extrapolation). ARC-AGI-2 puzzles are almost entirely unsolved (1/120).

## How CAEL answers

CAEL answers each turn with a team of small agents: planner, researchers, calculator, memory, writer, critic, the Supporter for emotional conversations, and authored desks for questions about CAEL itself, Python, explanations, tips and ideas. A new fielded index (BM25F over title, tags, body and answer, with learned word associations) finds threads about the user's own problem among about 285,000 human-written answers (Stack Exchange, OpenAssistant, and databricks-dolly-15k). A coherence check keeps follow-up answers on the thing the conversation is about. There are no neural weights and no external LLM writes the replies. Finite readers, ambiguity, and conversational gaps remain.

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

Download [cellarc-evidence.zip](https://huggingface.co/vynly/CAEL-0.4.0/resolve/v0.4.0/cellarc-evidence.zip), or see the [full public evidence and exact script](https://github.com/Vovala14/CAEL/tree/v0.4.0/benchmarks/core_040), including [reproduction instructions](https://github.com/Vovala14/CAEL/blob/v0.4.0/benchmarks/core_040/REPRODUCE.md). Official leaderboard inclusion is subject to maintainer review; no accepted rank or architectural superiority is claimed.

Original structured-run measurements: load 0.973 s, 2000-task inference 1.498 s, peak full process 109.13 MiB on one shared Windows host. The official harness has additional import overhead, including Torch and neural baseline definitions; no neural model is instantiated by the CAEL solver. These measurements are not an optimized-neural efficiency comparison.

## Downloads and licences

[![HF downloads (30 days)](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fhuggingface.co%2Fapi%2Fmodels%2Fvynly%2FCAEL-0.4.5&query=%24.downloads&label=HF%20downloads%20%2830%20days%29&color=blue)](https://huggingface.co/vynly/CAEL-0.4.5)

The live badge reports Hugging Face's counted query-file requests over 30 days, not unique users or all completed installs. `params.json` is a meaningful source and resource download configuration. Direct ZIP and resource clicks are not comprehensively counted; no simulated events or telemetry were added. For a full repository download: `hf download vynly/CAEL-0.4.5 --local-dir CAEL-0.4.5-download`.

The Hugging Face model card, including its YAML front matter, is [MODEL_CARD.md](MODEL_CARD.md). Nothing in this repository copies `README.md` to Hugging Face.

CAEL is [source-available, non-commercial](LICENSE) ([same terms on Hugging Face](https://huggingface.co/vynly/CAEL-0.4.5/blob/main/LICENSE)). Upstream resources retain their licences. CellARC is by **Miroslav Lžičař**: [dataset](https://huggingface.co/datasets/mireklzicar/cellarc_100k), [official code](https://github.com/mireklzicar/cellarc), [paper](https://arxiv.org/abs/2511.07908). The actual pinned dataset LICENSE is **CC BY 4.0**, despite the card's MIT tag; byte-preserved data and transformed evaluation files retain attribution. Official source licences are preserved separately. These results are our evaluation, not the author's endorsement. No live Vynly worker change is part of this release.

If this experiment interests you, starring and watching releases is how you'll hear about the next build.
