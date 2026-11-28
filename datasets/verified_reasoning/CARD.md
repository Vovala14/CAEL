---
license: cc-by-4.0
language:
- en
pretty_name: CAEL Verified Reasoning
size_categories:
- 1M<n<10M
task_categories:
- question-answering
- text-generation
tags:
- reasoning
- math
- logic
- synthetic
- verifiable
- rlvr
- arc
- calibration
configs:
- config_name: default
  data_files:
  - split: train
    path: data/train-*.parquet
  - split: test
    path: data/test-*.parquet
  - split: hard
    path: data/hard-*.parquet
---

# CAEL Verified Reasoning

**2,000,000 synthetic reasoning problems with programmatically computed references**, plus a **1,427-item hard split**,
a reproducible generator and a bounded final-answer checker.

**Data revision 1.1.1, checker 1.2.0 (28 November 2026):** this correction fixes **142 negative-money answers** and
their worked solutions, and **30,763 comparison explanations** with a reversed direction. All question texts, IDs,
split memberships and schema are preserved. See [CHANGELOG.md](CHANGELOG.md), the per-row [errata](https://huggingface.co/datasets/vynly/cael-verified-reasoning/blob/main/errata.jsonl),
[data revision manifest](data_revision.json) and [validation report](validation_report.json).

The generator constructs each situation, calculates a reference and renders a worked solution without a neural
model. Generator and rendering bugs are possible: computed references are not a proof that every reference or
explanation is correct. The included checker recognizes supported final-answer formats; it does not verify arbitrary
English reasoning or establish that an explanation justifies its answer.

The generators come from the exact solvers of [CAEL](https://github.com/Vovala14/CAEL), a reasoning system built
without neural networks.

## What it is for

- **Reward-engineering experiments.** `verify.check(model_reply, row)` keeps its True/False interface. The new
  `verify.judge(model_reply, row)` separates `correct`, `incorrect`, `ambiguous` and `unparseable`. Only `correct`
  returns True from `check`; False does not prove an answer is semantically wrong. Audit false accepts/rejects and
  uncertainty on your own completions before using it for RL. It is not a secure, complete standalone reward.
- **Calibration and refusal training.** About 2% of the problems (roughly 37,000) have the correct answer **"Cannot be
  determined"**, or say that a premise is contradictory or was never stated. These come from:
  - broken comparison chains;
  - invalid if-then inferences (affirming the consequent, denying the antecedent);
  - missing journey times;
  - hidden random outcomes;
  - too few clues.

  Models should learn to say so instead of guessing.
- **Same-family evaluation.** The `hard` split uses another seed and excludes exact core-question duplicates, but
  shares the underlying generators and language patterns with train/test. It is not independently authored
  natural-language transfer evidence. The [robustness protocol](ROBUSTNESS_PROTOCOL.md) describes separate wording
  pairs and changed-fact controls.
- **Curricula.** Every row has a `difficulty` from 1 to 5.

## Contents

| Area | Rows | Examples |
|---|---:|---|
| Multi-step arithmetic | 557,513 | change, discounts then tax, pack sizes, shares owed, rates with idle time, unit prices, corrected tallies |
| Dates and times | 478,409 | days between dates, weekday of a date, date plus months, time zones, durations, ages |
| ARC-style grids | 261,445 | 14 grid transformations with 3 demonstrations and a test (generated, not ARC-AGI tasks) |
| Composite (2–3 areas chained) | 259,936 | shift times into pay, rental dates into money due, flight plus time zone, trip budgets |
| Logic and constraints | 250,398 | line-ups by exhaustive search, if-then (valid and invalid forms), comparison chains, syllogisms |
| Conflicting or changing information | 117,280 | disagreeing reports, priority rules, corrections, withdrawals, first-hand vs hearsay, newest source |
| Memory over a chat | 67,934 | multi-turn chats with distractors: latest value, moved times, set changes, declined offers |
| Unanswerable or trick | 7,085 | missing information, hidden outcomes, contradictions, too few clues, future counts |

**Splits:**

| Split | Rows |
|---|---:|
| `train` | 1,980,000 |
| `test` | 20,000 |
| `hard` | 1,427 |

`hard` uses a different seed, keeps only difficulty ≥ 3, is about 200 per area (the small "unanswerable" area contributes only 27, because nearly all of its distinct problems are already in train), and is deduplicated against
train and test.

## Fields

| Field | Meaning |
|---|---|
| `id` | Stable identifier |
| `category`, `task` | Area and problem type (for example `logic` / `lineup`) |
| `difficulty` | 1 (one step) to 5 (several steps, or a large search) |
| `messages` | The conversation, as a list of `{role, content}` user turns. Some problems span several turns with distractors. |
| `answer` | The exact answer |
| `solution` | Step-by-step working |
| `verification` | How the answer was computed, for example "exhaustive search over 720 orders; exactly one survives" |
| `grids` | For ARC-style rows: JSON with the train pairs and the test input and output |
| `rule` | For ARC-style rows: the transformation name |
| `generator` | Generator version |

Rows corrected in this patch carry `cael-verified-reasoning-1.1.1`; unchanged rows retain their original `1.1`
provenance. Category counts, split sizes, question text and difficulty values are unchanged. Difficulty is an authored
heuristic, not a calibrated empirical measure.

`grids` contains reference test outputs. Do not include `answer`, `solution`, `verification`, `rule`, or reference grid
outputs in an inference prompt. They are supervision/evaluation metadata, not model inputs.

### Example

```json
{
 "category": "logic",
 "task": "lineup",
 "difficulty": 4,
 "messages": [
  {
   "role": "user",
   "content": "Five people stand in a queue: Dara, Felix, Hugo, Ines, Nina. Dara is directly behind Ines. Hugo is directly behind Dara. Ines is not next to Nina. Nina is last. Hugo is not next to Nina. Who is in position 2, counting from the front? Just give me the answer."
  }
 ],
 "answer": "Dara",
 "solution": "Trying every order of the 5 people, only one satisfies all the statements: Ines, Dara, Hugo, Felix, Nina. So the answer is Dara.",
 "verification": "exhaustive search over 120 orders; exactly one survives"
}
```

## Use

```python
from datasets import load_dataset
ds = load_dataset("vynly/cael-verified-reasoning")

from verify import check, judge     # download verify.py from this dataset repository
row = ds["test"][0]
result = judge("Answer: ...", row)
print(result["status"], result["reason"])
# check(reply, row) is True only when judge(...) reports "correct".
```

### Training format

`messages` contains user turns only. To construct a supervised conversation, append an assistant target; the dataset
does not already contain one:

```python
def sft_messages(row):
    target = row["solution"] + "\nAnswer: " + row["answer"]
    return list(row["messages"]) + [{"role": "assistant", "content": target}]
```

This is one possible formatting choice, not a measured training recipe. Use your model's chat template and check the
loss mask so prompt/user tokens are excluded from assistant-completion loss. Evaluation should supply only the problem
messages. No new fine-tuning, transfer experiment or model-performance result is claimed by this patch.

### Checker contract

- Prefer one explicit `Answer:` line, or an `Output:` block for a grid. `Final answer:` or `Correction:` can explicitly
  supersede earlier working. Conflicting final claims are `ambiguous`; the checker does not search for whichever one
  matches the reference.
- Supported forms include signed scalars/money, a bounded set of unit conversions, times and Gregorian dates,
  yes/no decisions, supported uncertainty/absence phrases, whole names/codes, unordered lists with multiplicities,
  source-attributed claims, and rectangular 2-D colour grids. It does not treat a matching number or keyword alone as
  proof of matching meaning.
- Numeric signs, explicit currencies/units, remainder/budget/refund direction, negation and source attribution matter.
  Numeric-only amounts can omit currency; an explicitly different currency is rejected. List ordering is ignored only
  for the documented list format. Grid shape and cells both matter.
- Unrecognized wording, conditional/hedged claims and unsupported formats can require manual review. A finite parser
  can reject a valid paraphrase or miss an adversarial phrasing. `correct` concerns the supported final-answer contract,
  not the truth of every sentence in a completion. Judge worked reasoning separately.
- `verify_legacy_v1_1.py` preserves the previous checker for reproducing historical results. Its known false positives
  make it unsuitable as an unaudited reward. Scores produced with the two versions should not be silently mixed.

CPU regression suite: `python test_verify.py`. The [checker audit](checker_regression_audit.json) includes **136
targeted cases**, pairing accepted equivalents with wrong-polarity/negation/source/shape cases. This failure-seeking
suite is not a measured error rate on real model completions, and is not John6666's separate 29-case audit.

**Generate as much as you want:**

```
python generate.py --out mydata --n 5000000 --seed 123
```

The output is deterministic for a given generator version and seed. Different seeds can still repeat questions or
underlying programs. Exclude prior questions explicitly and reserve genuinely separate wording/families if you want
transfer evidence; a new seed alone does not establish contamination-free evaluation.

## How it was checked

- **Full logical before/after audit:** all 2,001,427 rows checked. Only the 142 confirmed answer/solution repairs,
  30,763 comparison-explanation repairs and corrected-row generator labels differ. Every question message, ID, split
  membership, schema and other field is preserved.
- **Independent targeted recomputation:** all 54,541 pay-minus-spending rows recomputed directly from their prompts
  using Decimal arithmetic; all 76,506 comparison graphs checked independently from their stated relations.
- **Self-consistency:** every reference passes the revised checker, and all 261,645 grid answer representations match
  their stored test-output grids. These are consistency checks, not independent proof of all reference answers or
  transformations. The signed-money formatter is also checked across 100,001 cent values.
- **Duplicate audit:** 2,001,427 unique IDs and unique core-question texts after removing the known lead-in/closing
  wrappers. This does not remove template, semantic, program-family or possible pretraining overlap.
- **Checker regressions:** all 136 targeted cases pass, including the two published minimal counterexamples and positive
  equivalents. Historical acceptance checks did not establish semantic correctness; earlier universal-correctness and
  direct-RL-reward claims have been withdrawn.

The Parquet shards now use row groups of at most 8,192 rows for bounded reads. This is not a guarantee that an external
dataset-viewer job will recover from a service failure.

## Limitations

- **Templated language.** Each problem type has a limited set of sentence patterns (with varied names, items,
  numbers, lead-ins and closing requests). It teaches reasoning patterns, not broad language; mix it with natural data.
- **Moderate difficulty.** Mostly grade-school arithmetic, calendar and logic puzzles, plus composite multi-step
  problems. There is no proof-style mathematics and no code.
- **ARC-style grids are generated.** They are not ARC-AGI tasks and contain none of them, and they use 14 common
  transformations. They are useful for training and probing program induction, not as an ARC-AGI score.
- **English only.**
- **References and explanations can contain undiscovered defects.** The targeted audit above does not independently
  recompute every task family. Please report counterexamples with row ID and dataset/checker revision.
- **Checker coverage is bounded.** Treat ambiguous/unparseable results separately; perform manual audits and assess
  explanations independently of final-answer acceptance.
- **Uneven area sizes.** Some areas (memory, unanswerable) have fewer distinct problems, because their templates allow
  fewer combinations. They were capped rather than padded with near-duplicates.

## Licence and citation

CC BY 4.0. You may use it commercially, with attribution:

```
@misc{cael_verified_reasoning_2026,
  title  = {CAEL Verified Reasoning: computed-answer reasoning problems with a verifier},
  author = {Vovala14 (CAEL)},
  year   = {2026},
  url    = {https://huggingface.co/datasets/vynly/cael-verified-reasoning}
}
```

Made with the exact solvers of [CAEL](https://github.com/Vovala14/CAEL) (non-neural reasoning, source-available). If
you use it, I'd like to hear how it went.

Thanks to **John6666** for the [wording-sensitivity observations and concrete checker counterexamples](https://discuss.huggingface.co/t/2m-reasoning-examples-for-fine-tuning-small-models-with-worked-solutions-and-a-python-answer-checker/192328/2).
His small Qwen/LoRA pilot did not establish the effect of full-dataset fine-tuning or transfer to independently authored
questions. This correction does not claim to have replicated that training experiment or obtained an endorsement.
