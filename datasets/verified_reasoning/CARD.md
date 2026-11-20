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

**2,000,000 reasoning problems whose answers are computed, not guessed**, plus a **1,427-item hard evaluation split**
and the generator and verifier that made them.

Every example is built by a small program that sets up the situation, **computes the answer exactly** and writes the
working. No neural network wrote any of it, so every answer is correct by construction, and every answer can be checked
automatically with the included `verify.py`.

The generators come from the exact solvers of [CAEL](https://github.com/Vovala14/CAEL), a reasoning system built
without neural networks.

## What it is for

- **RL with verifiable rewards.** `verify.check(model_reply, row)` returns True/False, so it can be used directly as a
  reward function. It reads the final answer and accepts different formats of the same answer.
- **Calibration and refusal training.** About 2% of the problems (roughly 37,000) have the correct answer **"Cannot be
  determined"**, or say that a premise is contradictory or was never stated. These come from:
  - broken comparison chains;
  - invalid if-then inferences (affirming the consequent, denying the antecedent);
  - missing journey times;
  - hidden random outcomes;
  - too few clues.

  Models should learn to say so instead of guessing.
- **Evaluation.** The `hard` split is fixed and balanced across 8 areas, and none of its problems appear in train or
  test.
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

from verify import check            # verify.py is in this repository
check("Working... Answer: fourth", ds["train"][0])   # -> True / False
```

**Generate as much as you want:**

```
python generate.py --out mydata --n 5000000 --seed 123
```

The output is deterministic for a given seed. A new seed gives fresh problems, which is useful for contamination-free
evaluation.

## How it was checked

- **Verifier against the gold answers:** every gold answer passes `verify.check`.
- **Verifier against wrong answers:** wrong answers swapped in from other rows of the same task are rejected. The only
  exceptions are answers that are genuinely equivalent, such as the same amount with a different currency symbol, or a
  list in a different order.
- **Independent cross-check:** CAEL's own solvers re-answered a random sample. They answered 251 of 800 sampled test problems (they stay silent on wording they do not cover) and agreed on 232. Every one of the 19 disagreements was traced to a reading error in CAEL or a verifier phrasing case (since fixed); none was a wrong dataset answer.
- **Exact duplicates removed:** duplicates are judged on the problem text, before the extra wording is added.

## Limitations

- **Templated language.** Each problem type has a limited set of sentence patterns (with varied names, items,
  numbers, lead-ins and closing requests). It teaches reasoning patterns, not broad language; mix it with natural data.
- **Moderate difficulty.** Mostly grade-school arithmetic, calendar and logic puzzles, plus composite multi-step
  problems. There is no proof-style mathematics and no code.
- **ARC-style grids are generated.** They are not ARC-AGI tasks and contain none of them, and they use 14 common
  transformations. They are useful for training and probing program induction, not as an ARC-AGI score.
- **English only.**
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
