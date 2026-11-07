---
language:
- en
license: other
license_name: cael-non-commercial
license_link: https://huggingface.co/vynly/CAEL-0.3.9.1/blob/main/LICENSE
pipeline_tag: text-generation
tags:
- cael
- non-neural
- cellular-automata
- symbolic-reasoning
- custom-code
inference: false
---

# CAEL 0.3.9.1

A source-available Python assistant built from non-neural symbolic, count and automaton engines. This patch adds native interpretation of supported standalone tasks to the Assistant itself. No neural network, external LLM, new learned weights or benchmark-answer table is used at runtime.

## What changed

Complete supported arithmetic, rule chains, precedence constraints, location updates, string pipelines and table reductions now route to bounded symbolic operations before unrelated spelling, topic or count fallbacks. Arithmetic uses exact values and checking; logic and state tasks use the existing engines. Unsupported clauses or ambiguous constraints can cause clarification or abstention. These are finite readers, not arbitrary English or Python understanding.

Questions about CAEL's version and changes use installed, version-bound product facts. Existing conversation and bounded Python functionality remains, with known gaps.

The application is **0.3.9.1**. The public resource bundle is still the **byte-identical 0.3.7** archive, with unchanged inherited weights, protected solvers and CA kernels. Picture/portrait weights are excluded from this public package.

## Run locally

Use Python 3.11 or 3.12 with the declared dependencies. Download and extract [CAEL-0.3.9.1.zip](./CAEL-0.3.9.1.zip), then run inside the extracted folder:

```bash
python -m pip install -r requirements-unified.txt
python -m cael_unified --download
python -m cael_unified --ui
```

Open http://127.0.0.1:8765. For terminal chat use `python -m cael_unified --mode chat`. Set `CAEL_WEB_SEARCH=0` to disable public lookup. Do not use a shared demo for sensitive information.

This is a custom runtime, **not a Transformers-compatible checkpoint**. Both the source ZIP and approximately 563 MB resource archive are required. The installer checks the pinned archive and preserves existing local selections. See `release_manifest.json` and `SHA256SUMS.json` for exact bytes and hashes.

## Fresh study: measured scope

The source was frozen before 900 new synthetic multiple-choice questions were written. Six known task families contain 150 questions each; 450 use familiar formats with new instances and 450 use newly authored wording on different instances. There was zero exact overlap against 235,677 declared prior/train/development text guards. Undisclosed third-party pretraining cannot be exhaustively checked.

| Same 900 questions | Unchanged 0.3.9 baseline | Evaluated native candidate |
|---|---:|---:|
| Overall | 414/900 (46.0%) | 777/900 (86.3%) |
| Familiar-format new instances | 322/450 (71.6%) | 450/450 (100%) |
| Newly worded instances | 92/450 (20.4%) | 327/450 (72.7%) |

All 123 candidate abstentions count as wrong, including all unsupported-wording outputs. All nine engines completed 8,100 predictions with no response errors. The evaluated candidate had no active language selection, so its inherited count fallback was inactive; the baseline had it active. Fresh installation activates the old count fallback. All 777 endorsed replies remain exact, but 105 former abstentions become statistical guesses. The 777/900 score describes the frozen configuration, not every fresh installation. See [the configuration amendment](./benchmarks/native_interpretation_0391/CONFIGURATION_AND_RELEASE_NOTE.md). The release retains the exact evaluated task modules and Assistant change; only version metadata, installed product facts and documentation differ. Packaging replay is not new test evidence.

Seven other engines were evaluated with their previously fixed readouts. Neural models used a single bare A/B/C/D next-token logit readout, with no free-form generation or chain of thought. This is **not a best-chat comparison**, a standard published benchmark score, a Qwen result, or evidence of general superiority. Qwen was not evaluated here. Task families were known, development was adaptive, and question authoring/review was maintainer-led and AI-assisted. The 100% familiar half does not establish broad competence.

[Full results and all nine scores](https://vynly-non-neural-ai-leaderboard.hf.space/fresh-transfer.html) В· [Questions, references, raw outputs, readouts, audits and hashes](https://huggingface.co/datasets/vynly/nnai-bench/tree/main/fresh-transfer/2026-11-07-native). The fresh study is a separate supplement, not a replacement for older leaderboard scores.

## Remaining limits and validation

Finite wording coverage still fails: 123/900 final questions produced no scored answer. Richer conversations, option switches, dictionary follow-ups and source retrieval can still fail. A link or exact calculation does not prove the surrounding interpretation is correct. Supported forgetting is not whole-transcript erasure.

Authored development and inherited regressions are separate from final scores. The inherited suite had eight pre-existing baseline failures and four additional intentional route assertions in the candidate; these are disclosed rather than claimed as a fully green suite. See the release verification for archive import, installed self-information and saved-reply reproduction checks.

## Licence and attribution

**CAEL by Vovala14** is source-available under the [CAEL Non-Commercial License](./LICENSE), not an OSI open-source licence. Personal/non-commercial research use is allowed under its terms; commercial use requires separate permission. Third-party resources keep their own licences and attribution in `NOTICE.md` and `licenses/`. Benchmark tooling and authored question data have separate licences; this does not relicense CAEL or peer models.

[Source and release](https://github.com/Vovala14/CAEL/releases/tag/v0.3.9.1) В· [Release notes](./RELEASE_0_3_9_1.md)
