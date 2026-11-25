---
language:
- en
license: other
license_name: cael-non-commercial
license_link: https://huggingface.co/vynly/CAEL-0.4.5/blob/main/LICENSE
pipeline_tag: text-generation
tags:
- cael
- non-neural
- cellular-automata
- symbolic-reasoning
- retrieval
- custom-code
inference: false
---

# CAEL 0.4.5

[![HF downloads (30 days)](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fhuggingface.co%2Fapi%2Fmodels%2Fvynly%2FCAEL-0.4.5&query=%24.downloads&label=HF%20downloads%20%2830%20days%29&color=blue)](https://huggingface.co/vynly/CAEL-0.4.5)
[![version 0.4.5](https://img.shields.io/badge/version-0.4.5-blue)](https://github.com/Vovala14/CAEL/releases/tag/v0.4.5)
![CPU only](https://img.shields.io/badge/CPU-only-green)

A chat assistant with **no neural network**: a team of small agents, rules, exact solvers, cellular automata and
retrieval over human-written answers, on CPU.

**0.4.5** adds chess, story reasoning and word problems, and widens the ARC solver:
- **Chess in chat:**
  - What you can do: play CAEL's own non-neural engine, get the best move for a FEN, rank every legal move, or review a
    game.
  - The engine: alpha-beta search, about 100 hand-written evaluation terms, and several cores.
  - Wins: Cyber Chess AI "Hard Pro" (checkmate in 28 moves), ChatGPT 6.1 Terra 2–0, Grok 4.7 1–0, and Stockfish 19
    limited to 2850 Elo 4–2.
  - Play it in your browser: [vynly/cael-chess](https://huggingface.co/spaces/vynly/cael-chess).
- **Stories:** a world model (who moved where, who has what, before/after, deduction, routes). bAbI test **494/500**;
  the 0.4.4 behaviour scored 241.
- **Word problems:** question-guided arithmetic that ignores distracting numbers. SVAMP test **70/300**; the 0.4.4
  behaviour scored 58, and no previously correct answer was lost.
- **ARC-AGI-1:** a compositional program search and a per-cell rule learner were added.

| ARC set | Solved (pass@2, 60 s per task, CPU) |
|---|---:|
| ARC-AGI-1 evaluation | **83 / 400** (0.4.4: 62) |
| ARC-AGI-1 training (development set) | 192 / 400 |
| ARC-AGI-2 evaluation | 1 / 120 |

Reproduce it with `python evaluate_arc.py --data ARC-AGI/data/evaluation` (from a clone of
[fchollet/ARC-AGI](https://github.com/fchollet/ARC-AGI)), and compare task by task with
`results/arc_agi_1_evaluation_0.4.5.jsonl` in the source zip. Development used the training set only.

Full notes: [RELEASE_0_4_5.md](RELEASE_0_4_5.md).

## Install and run

Use Python 3.12. Download and extract [CAEL-0.4.5.zip](https://huggingface.co/vynly/CAEL-0.4.5/resolve/main/CAEL-0.4.5.zip). For full chat, also extract [cael-open-chat-v1.1.zip](https://huggingface.co/vynly/CAEL-0.4.5/resolve/main/cael-open-chat-v1.1.zip) into `models/`, so that `models/cael-open-chat-v1/` holds `open.sqlite` and `fielded.sqlite`. Then from the extracted directory:

```bash
python -m pip install -r requirements-unified.txt
python -m cael_unified --download
python -m cael_unified --ui
```

Open http://127.0.0.1:8765. For terminal chat use `python -m cael_unified --mode chat`. Set `CAEL_WEB_SEARCH=0` to turn
off public web lookup.
- `--download` fetches the integrity-checked resource bundle. It is still byte-identical 0.3.7 (562,714,794 bytes) and
  is required.
- This is **custom Python code, not a Transformers checkpoint**.
- Picture and portrait weights are excluded.

## Size and resources

- **Disk:** about 2.6 GB of tables and indexes, no neural weights. The chat code is about 8 MB, plus a 3.6 MB chess opening book.
- **Memory:** about 100–600 MB (568 MB peak over a 48-conversation run).
- **Hardware:** CPU only, no GPU.

## Honest limits

- The readers are hand-written: problem types they were not written for get a general answer or an honest refusal.
- Subjects outside the authored desks depend on the index and the web.
- ARC-AGI-2 puzzles are almost entirely unsolved (1 of 120).
- Free-form word problems (GSM8K style) remain weak; the new arithmetic answers only shapes it reads reliably.

## Files

| File | What it is |
|---|---|
| `CAEL-0.4.5.zip` | Source release (the files committed to git), including `evaluate_arc.py` and the per-task ARC results |
| `cael-open-chat-v1.1.zip` | Open-chat index (`open.sqlite`) and fielded index (`fielded.sqlite`), unchanged from 0.4.2 |
| `bundle_config.json` | Checksum-pinned resource bundle (0.3.7) used by `--download` |
| `params.json` | Download parameters and checksums |
| `SHA256SUMS.txt` | SHA-256 of every release file |
| `RELEASE_0_4_5.md`, `CHANGELOG.md` | Release notes and history |

Licence: CAEL non-commercial source-available ([LICENSE](LICENSE)). The open-chat data keeps its own licences: Stack
Exchange CC BY-SA 4.0, OpenAssistant Apache 2.0, databricks-dolly-15k CC BY-SA 3.0. Source: [github.com/Vovala14/CAEL](https://github.com/Vovala14/CAEL).
