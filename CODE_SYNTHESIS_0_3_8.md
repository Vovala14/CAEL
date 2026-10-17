# CAEL Python code writing 0.3.8

Requested on 2026-10-17: CAEL should write new Python code itself rather than repeat code it has seen.

## How it writes code

`cael_unified/codegen/` adds a non-neural **program search**. Given a short description and two or more examples
(`f(args) == result`), CAEL composes small Python operations — about 100 list, string, number, comparison and
comprehension building blocks — in order of increasing cost. It runs each candidate on the examples and returns the
cheapest one that produces every expected result. A candidate that ignores an input is only accepted if no candidate
using all inputs appears within two more cost levels.

There are no stored solutions to copy. The output is a new composition, checked by running it. Only CAEL's own
generated expressions are executed, on literal example values, with size guards. Downloaded MBPP code (solutions and
test lines) is parsed with `ast` but never executed. Test lines are read with `ast.literal_eval`.

The trained part, `models/cael-code-0.3.8/model.json` (SHA-256 `846c2860…264fb919e`), is a Bernoulli naive-Bayes
count table. It holds P(operation used | description words), learned from the syntax trees of the 384 MBPP training
solutions (tasks 1–10 and 601–974; CC BY 4.0, source commit `3ef52111`). It stores counts per word and operation, not
solution text. At search time those probabilities shift each operation's cost, so likely operations are tried first.

## Results (MBPP test tasks 11–510, run once per condition, 4 s per task)

Protocol: train on the training split, choose the cost strength on development tasks 511–600, then run the test
split once. Seven tasks whose tests are not literal calls were excluded, leaving 498.

| Condition | Untrained search | Trained search (strength 1.0) |
| --- | ---: | ---: |
| **Held-out**: built from tests 1–2, also passes unseen test 3 | **191 (38.4%)** | **192 (38.6%)** |
| Fits all three visible tests | 296 (59.4%) | 294 (59.0%) |

- **The training adds nothing measurable yet.** Training gained 29 held-out tasks and lost 28. Development showed the
  same tie (32 vs 32 of 88). The search itself does the work; the learned costs only reshuffle which tasks succeed.
- **Passing a hidden test is not proof of correctness.** Some passes are coincidences (`2 + items.index(n)`). 38% is an
  upper bound on correct programs. Code is often clumsy, e.g. `(n + n) * (n + (n + n))` for 6n².
- **Not copied.** After identifier normalisation, three solved programs match a training solution's structure: `len(s)`
  and two `[x[-1] for x in items]`. The untrained search, which never reads training code, produced the same three.
- Failures: 151 fitted the given tests but failed the hidden one; 155 found nothing within the limit (126 hit the
  time limit).
- Limits: one-expression functions only. No loops with state, recursion, multi-statement algorithms or imports beyond
  `math`. This is not MBPP pass@1 as published for language models, which see the description and all tests and are
  scored on all tests.

### Iteration 2 (development only)

After a live check showed fits that ignored the description, I tried using the trained model to choose among all fitting
programs (`train.ranker`, two extra cost levels). On development it scored 31/88 at every weight, against 32/88 for
search alone, so it was stopped **before** any second test run (`iteration2_development.json`). It stays in the code,
unused by chat.

The chat uses the evaluated configuration with two changes:
- **Description fix.** The description is now the text before the first example. Previously, examples written on the
  same line removed the whole description, which caused both bad live answers.
- **Deeper loop bodies** (inner cost 10 instead of 8). This scored the same on development (32/88) and makes filters
  such as "keep the even numbers" reachable.

Evidence: `research/codegen_038/` (`run_eval.py` protocol, `report.json`, per-task `test_*.json`, `selection.json`,
`analyze.py`). The copy check in the original run treated builtins as variables. `analyze.py` recomputes it with the
corrected normaliser; solve counts are unaffected.

## In chat

Ask with examples, on one line or several:

    Write a python function that counts vowels. count_vowels("hello") == 2, count_vowels("sky") == 0, count_vowels("aeiou") == 5

CAEL replies with the function and says it was checked against your examples. It warns when the function ignores an
argument. Without examples it asks for some rather than guessing code from the description alone.
