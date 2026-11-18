---
language:
- en
license: other
license_name: cael-non-commercial
license_link: https://huggingface.co/vynly/CAEL-0.4.3/blob/main/LICENSE
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

# CAEL 0.4.3

[![HF downloads (30 days)](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fhuggingface.co%2Fapi%2Fmodels%2Fvynly%2FCAEL-0.4.3&query=%24.downloads&label=HF%20downloads%20%2830%20days%29&color=blue)](https://huggingface.co/vynly/CAEL-0.4.3)
[![version 0.4.3](https://img.shields.io/badge/version-0.4.3-blue)](https://github.com/Vovala14/CAEL/releases/tag/v0.4.3)
![CPU only](https://img.shields.io/badge/CPU-only-green)

A chat assistant with **no neural network**: a team of small agents, rules, exact solvers, cellular automata and
retrieval over human-written answers, on CPU.

**0.4.3** adds new desks to the conversation team, each with authored answers and the follow-ups to them:
- **Host:** honest answers about CAEL itself, its web access, and the time and date in about 100 cities.
- **Programmer:** 83 Python topics, 31 error messages explained, changes to the code just written, and 106 scripts CAEL
  wrote and verified itself.
- **Explainer:** 18 concepts and 22 everyday-science explanations (rain and snow, thunder, sky colour, the seasons and
  more).
- **Coach:** beginner guides, habits, and ranked tips that can answer "Which of those helps the most?".
- **Ideas desk:** parties, gifts, rainy days, dates and weekends.

It also adds:
- new calculator sums (deposits and what's left, monthly splits, rates and savings goals);
- a wider Supporter (an operation, a death, waiting for news, interviews, a friend moving away);
- a non-neural **ARC grid solver**.

In a sealed 24-conversation comparison, CAEL won **13**, lost 5 and tied 6 against **LFM2-700M**. Each conversation was
judged with the names hidden and the order shuffled, by the developer of CAEL, which is a conflict of interest. CAEL ran
with web lookups on; LFM2 ran offline. On the ARC-AGI-1 evaluation set (held out, two attempts), CAEL solves **34 of
400**, up from 5. Full notes: [RELEASE_0_4_3.md](RELEASE_0_4_3.md).

## Install and run

Use Python 3.12. Download and extract [CAEL-0.4.3.zip](https://huggingface.co/vynly/CAEL-0.4.3/resolve/main/CAEL-0.4.3.zip). For full chat, also extract [cael-open-chat-v1.1.zip](https://huggingface.co/vynly/CAEL-0.4.3/resolve/main/cael-open-chat-v1.1.zip) into `models/`, so that `models/cael-open-chat-v1/` holds `open.sqlite` and `fielded.sqlite`. Then from the extracted directory:

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

- **Disk:** about 2.6 GB, nearly all data. The code is about 20 MB.
- **Memory:** about 100–230 MB.
- **Hardware:** CPU only, no GPU.

## Honest limits

- Subjects outside the authored desks depend on the index and the web, and follow-ups there can drift.
- ARC-AGI-2 puzzles stay unsolved (0 of 120).
- 24 self-judged conversations is a small sample (p ≈ 0.10).

## Files

| File | What it is |
|---|---|
| `CAEL-0.4.3.zip` | Source release (the files committed to git) |
| `cael-open-chat-v1.1.zip` | Open-chat index (`open.sqlite`) and fielded index (`fielded.sqlite`), unchanged from 0.4.2 |
| `bundle_config.json` | Checksum-pinned resource bundle (0.3.7) used by `--download` |
| `params.json` | Download parameters and checksums |
| `SHA256SUMS.txt` | SHA-256 of every release file |
| `RELEASE_0_4_3.md`, `CHANGELOG.md` | Release notes and history |

Licence: CAEL non-commercial source-available ([LICENSE](LICENSE)). The open-chat data keeps its own licences: Stack
Exchange CC BY-SA 4.0, OpenAssistant Apache 2.0, databricks-dolly-15k CC BY-SA 3.0. Source: [github.com/Vovala14/CAEL](https://github.com/Vovala14/CAEL).
