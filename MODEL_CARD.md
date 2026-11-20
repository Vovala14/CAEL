---
language:
- en
license: other
license_name: cael-non-commercial
license_link: https://huggingface.co/vynly/CAEL-0.4.4/blob/main/LICENSE
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

# CAEL 0.4.4

[![HF downloads (30 days)](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fhuggingface.co%2Fapi%2Fmodels%2Fvynly%2FCAEL-0.4.4&query=%24.downloads&label=HF%20downloads%20%2830%20days%29&color=blue)](https://huggingface.co/vynly/CAEL-0.4.4)
[![version 0.4.4](https://img.shields.io/badge/version-0.4.4-blue)](https://github.com/Vovala14/CAEL/releases/tag/v0.4.4)
![CPU only](https://img.shields.io/badge/CPU-only-green)

A chat assistant with **no neural network**: a team of small agents, rules, exact solvers, cellular automata and
retrieval over human-written answers, on CPU.

**0.4.4** makes CAEL think before it answers, with a swarm:
- **Chat:** nine exact readers each propose an answer to several readings of the question:
  - everyday sums, dates and times;
  - line-up and if-then logic, solved by trying every order;
  - sources that disagree, correct or copy each other;
  - chat memory;
  - short explanations.

  Each proposal is checked: the answer type must fit, and a word problem's number must be derivable from the user's
  own numbers. The checked answers vote. A final guard turns off-topic replies into an honest "I can't work this out".
- **ARC-AGI-1:** a non-neural grid solver solves **62 of 400 evaluation tasks (15.5%, pass@2)**, 10 seconds per task on
  a CPU. It uses:
  - 53 solver programs, each of which must reproduce every demonstration;
  - augment-and-vote over the 8 symmetries;
  - a union swarm of drawing specialists;
  - a leave-one-out self-check that prefers rules that generalise.

| ARC set | Solved (pass@2) |
|---|---:|
| ARC-AGI-1 evaluation | **62 / 400** |
| ARC-AGI-1 training (development set) | 152 / 400 |
| ARC-AGI-2 evaluation | 0 / 120 |

Reproduce it with `python evaluate_arc.py --data ARC-AGI/data/evaluation` (from a clone of
[fchollet/ARC-AGI](https://github.com/fchollet/ARC-AGI)), and compare task by task with
`results/arc_agi_1_evaluation_0.4.4.jsonl` in the source zip.
- The solver was developed on the training set only.
- The evaluation set was scored at several milestones but never used to fix anything. A run on a set CAEL has never
  seen is welcome.

Full notes: [RELEASE_0_4_4.md](RELEASE_0_4_4.md).

## Install and run

Use Python 3.12. Download and extract [CAEL-0.4.4.zip](https://huggingface.co/vynly/CAEL-0.4.4/resolve/main/CAEL-0.4.4.zip). For full chat, also extract [cael-open-chat-v1.1.zip](https://huggingface.co/vynly/CAEL-0.4.4/resolve/main/cael-open-chat-v1.1.zip) into `models/`, so that `models/cael-open-chat-v1/` holds `open.sqlite` and `fielded.sqlite`. Then from the extracted directory:

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

- **Disk:** about 2.6 GB of tables and indexes, no neural weights. The chat code is about 8 MB.
- **Memory:** about 100–600 MB (568 MB peak over a 48-conversation run).
- **Hardware:** CPU only, no GPU.

## Honest limits

- The readers are hand-written: problem types they were not written for get a general answer or an honest refusal.
- Subjects outside the authored desks depend on the index and the web.
- ARC-AGI-2 puzzles stay unsolved (0 of 120).

## Files

| File | What it is |
|---|---|
| `CAEL-0.4.4.zip` | Source release (the files committed to git), including `evaluate_arc.py` and the per-task ARC results |
| `cael-open-chat-v1.1.zip` | Open-chat index (`open.sqlite`) and fielded index (`fielded.sqlite`), unchanged from 0.4.2 |
| `bundle_config.json` | Checksum-pinned resource bundle (0.3.7) used by `--download` |
| `params.json` | Download parameters and checksums |
| `SHA256SUMS.txt` | SHA-256 of every release file |
| `RELEASE_0_4_4.md`, `CHANGELOG.md` | Release notes and history |

Licence: CAEL non-commercial source-available ([LICENSE](LICENSE)). The open-chat data keeps its own licences: Stack
Exchange CC BY-SA 4.0, OpenAssistant Apache 2.0, databricks-dolly-15k CC BY-SA 3.0. Source: [github.com/Vovala14/CAEL](https://github.com/Vovala14/CAEL).
