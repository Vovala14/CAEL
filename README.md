# CAEL 0.3.8

A CPU assistant built from non-neural symbolic, count and automaton engines.
It is a custom Python runtime; Qwen and Transformers are not part of CAEL.
CAEL is source-available, non-commercial software (see LICENSE).

0.3.8 is a code-only update. It reuses the unchanged published 0.3.7 model
bundle (cael-0.3.7.cael, same checksum); see CHANGELOG.md.

Picture and portrait generator weights are excluded. Chat, helper, math,
stories, prompt writing, retrieval and emoji remain available. Image requests
can produce a prompt for an external image tool.

## Start

Use Python3.11 or later. Extract the source archive or clone this repository,
then run in its folder:

```bash
python -m pip install -r requirements-unified.txt
python -m cael_unified --download
python -m cael_unified --ui
```

Open http://127.0.0.1:8765. Windows SETUP.bat and RUN.bat provide the same flow.
The checksum-verified no-images resource download is about563MB; source and
resource archives are separate. Existing local models/selections are preserved
by the installer. The licence is unchanged; see LICENSE and NOTICE.md.

## Changes in 0.3.8

- Personal facts: a question about your own details (birthplace, address and
  similar) that you never stated is answered with "you have not told me",
  instead of a fact borrowed from retrieval or another person.
- Requests to just listen ("no advice", "don't ask me questions", and
  paraphrases) are kept on every conversational route, not only some phrasings.
- Word problems: a checked quantity-event graph, exact fractions/decimals and
  stricter clause handling. Unsupported clauses lead to a clarifying question.
  The older inventory helper still answers first when it is exact.
- Python: requested function names and declared signatures are kept, and
  rules that cannot be resolved lead to a question, not to simpler code.
- Safety: arithmetic-expression and recurrence checks no longer use Python's
  native eval. They run in the bounded AST VM or a closed +, -, * evaluator.
- The model weights and bundle are unchanged.

## Changes in 0.3.7

- Session-local explicit facts/preferences, corrections, conflict clarification,
  forgetting and provenance. Quoted/hypothetical statements are treated cautiously.
- A larger authored vocabulary for mixed/negated feelings, speaker attribution,
  bereavement and requests to listen. These are bounded rules, not human experience.
- Natural-language ordered numeric/text/record workflows compose existing Python
  operations; simple list/array chunk contracts are restored. Generated functions
  are checked in a bounded AST VM. Unsupported clauses need clarification.
- The learned model weights, protected choice/word-math solvers and CA kernels
  are unchanged. These upgrades are implementation changes.

## Named local confirmation

CAEL-CMP-R2-20261028 contains 80 locally authored synthetic items, 20 per category.
Every full reply was reviewed by AI coding agents (unblinded), including apparent
automatic passes and code.
The source, inputs and primary grading were frozen before final answers.

| System | Memory | Conversation | Python | Controls | Reviewed total |
|---|---:|---:|---:|---:|---:|
| CAEL 0.3.7 | 16/20 | 10/20 | 15/20 | 16/20 | 57/80 |
| Qwen3-0.6B | 8/20 | 13/20 | 6/20 | 16/20 | 43/80 |
| Qwen3.5-0.8B | 12/20 | 14/20 | 3/20 | 12/20 | 41/80 |

Functional Python: CAEL15/18, Qwen3 6/18, Qwen3.5 3/18. Original automatic totals
were54,43,42; full-review totals differ because regex matches can miss correct
answers or accept incorrect explanations. All raw replies/flags and every
adjudication are included under benchmarks/cael_cmp_r2_20261028/.

0.3.8 offline replay of the same 80 frozen inputs (automatic grader, no
re-review, no Qwen rerun): 59/80 automatic, versus 54/80 for the recorded 0.3.7
replies (memory 17, conversation 10, Python 16, controls 16). Seven replies
changed, listed in CHANGELOG.md. One of them (an invented birthplace) is also the
bug in a public report fixed in this release, so that item is not a clean
held-out test any more. The table above remains the 0.3.7 reviewed result.

This is an authored family-overlap test with unblinded review by AI coding
agents, not an independent leaderboard or evidence of general superiority. Qwen is stronger
on the conversation category here. On an older, broader 400-question test,
Qwen3.5 leads clearly: CAEL 121/400 versus Qwen3.5 181/400 original phrase
passes (Qwen3 116/400), with phrase-grading flaws disclosed. The targeted result
must not erase that limitation.

CAEL's measured full-portable process peak was558.648MiB in this shared-host
run. Qwen3 float32/eager peaked5896.336MiB; Qwen3.5 bfloat16/SDPA peaked2668.309MiB.
These are different runtimes/precisions, not an equal-size or optimized quantized
comparison. Disk size, model bytes, load time and median latency are separate
quantities recorded in the report. The earlier167MiB source-only run is not
this portable-build measurement.

## Remaining weaknesses

CAEL still misses factual/emotional paraphrases and fails tracing, leftmost
binary search under a no-imports rule, and much reasoning. It solves few
ordinary grade-school word problems: on a 400-problem GSM8K training sample
(a development check, not a release benchmark) it gave very few correct answers
and asked for clarification on most. Qwen is better at open conversation.
It does not understand arbitrary Python or replace a general LLM.
Do not enter personal information into shared demos. This release does not
change any running Vynly site or shared worker.

Read CHANGELOG.md, RELEASE_0_3_7.md and benchmarks/cael_cmp_r2_20261028/REPRODUCE.md for exact
settings, uncertainty, disclosures and the offline CAEL reply-regression replay.
