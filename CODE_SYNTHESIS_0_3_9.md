# CAEL Python code writing 0.3.9: self-training (no measurable gain)

Goal (2026-10-17): make the trained part of `cael_unified/codegen/` measurably improve held-out MBPP results. In 0.3.8
trained and untrained search tied (development 32 vs 32 of 88, test 192 vs 191 of 498).

**Result: still no measurable gain.** The selected self-trained method scored 192/498 on the test split against
191/498 for the hand-set search (12 tasks gained, 11 lost). With all three tests given it scored 298 against 295. Both
differences are well inside run-to-run noise. Everything stays non-neural: counted naive-Bayes tables and search.

## What changed in the code

- `synth.py` now records which tokens each program is built from: operations, comprehension forms, constants
  (`const:2`, `const:number`, …) and loop sources (`iter:each`, `iter:range`, …). Results report them in
  `stats['tokens']`.
- `uniform_costs()` plus `hand=False` give a search with nothing hand-tuned: every operation costs 2, every pool
  constant costs 3, and there are no keyword rules (vowel → `'aeiou'`, even → 2, circle → pi).
- `collect=k` keeps searching k cost levels past the first fit and returns every fit in `stats['candidates']`.
- `train.py`: `fit_self` builds the naive-Bayes count table from CAEL's own verified programs instead of human code.
  `self_costs` turns its probabilities into costs (cost = offset + scale × bits). `lift_costs` keeps the hand-set base
  costs and shifts each one by log2 P(token | words) / P(token).
- Chat behaviour is unchanged. `chat.py` still uses the 0.3.8 model; the live worker was not reloaded.

## Two bugs found in 0.3.8 (results unaffected, now documented in code)

1. The hand-set constant table listed `True: 4, False: 4`. As dict keys, True equals 1 and False equals 0, so this
   only raised 0 and 1 to cost 4, and booleans were never offered. `HAND_CONSTANTS` now writes out the effective
   costs, so the baseline reproduces exactly (191/498 again).
2. The iteration-2 ranker never searched the two extra levels. `check()` stopped at the first fit that used every
   argument whether or not ranking was on, so the ranker had almost nothing to choose from. `collect=k` fixes this.

## Protocol

- **Self-training data** came from the training split only (tasks 1–10 and 601–974, 381 usable). In round 0 the
  uniform search ran at 8 s per task. A program was kept if it fitted tests 1–2 and passed the unseen test 3, or if it
  fitted all three. Round 1 searched again with the round-0 model. In total, 452 programs for 229 tasks.
  Downloaded MBPP code was never executed: tests are read with `ast.literal_eval`, and only CAEL's own programs ran.
- **Tuning.** The development split cannot tell methods apart: hand-set, uniform, 0.3.8 model and learned prior all
  scored 32/88, and the solved sets differ only by reshuffling (39 tasks in the union). So I added 5-fold
  cross-validation on the training split (`cv.py`, 381 tasks). Each fold is searched with a model fitted only on the
  other folds' solutions. Development was used as a second check.
- **Selection rule** (`selection.json`, written before the test run): best CV score plus development score.
- **Test split**: one run per condition, all in the same session under the same load. **This is a further look at the
  same test split that 0.3.8 used** (`research/codegen_038/report.json`); that report was not overwritten.

## Development and cross-validation (held-out: built from tests 1–2, must pass test 3)

| Condition | Training CV /381 | Development /88 |
| --- | ---: | ---: |
| Hand-set costs (0.3.8 untrained) | 146–147 | 32 |
| Uniform costs, no keyword rules | 141 | 32 |
| 0.3.8 model (P(tag \| words) from human MBPP code) | – | 32 |
| Learned base costs (self-trained prior only) | 139 | 28–32 |
| Self-trained prior + words | 131–141 | 30–32 |
| Counted re-ranker over all fits (offline, stored candidates) | 148–149 | – |
| **Hand base + self-trained lift (selected)** | **150** | **35** (3 gained, 0 lost) |

- Learning base costs from CAEL's own solutions made things worse. Self-training rewards the operations of programs
  the search already finds, so it pushes rarer operations, which the unsolved tasks need, further back.
- Re-ranking has little real headroom. If the right fit were always chosen, training would go from 146 to 174, but
  most of the alternative fits that pass test 3 are coincidences too (`round(math.sqrt(math.factorial(n)))` for
  Jacobsthal numbers).

## Test split (tasks 11–510, 498 usable, 4 s per task) — `research/codegen_039/report_0_3_9.json`

| Condition | Held-out | Fits all three given tests |
| --- | ---: | ---: |
| Hand-set (rerun, same conditions) | 191 (38.4%) | 295 (59.2%) |
| Uniform, nothing hand-tuned or learned | 185 (37.1%) | – |
| **Self-trained (selected)** | **192 (38.6%)** | **298 (59.8%)** |

- Self-trained vs hand-set, held-out: 12 gained, 11 lost. The +3 on development and +4 on cross-validation did not
  carry over.
- Self-trained vs uniform: 22 gained, 15 lost (+7, two-sided sign test p ≈ 0.32). Hand-set vs uniform is +6. So the
  self-trained table recovers about what the hand-written costs and keyword rules give, but adds nothing beyond them.
- Copies: 2 solved programs match a training solution's structure after renaming (`len(s)`, `[x[-1] for x in
  items]`), against 3 for hand-set.

## Why the trained part cannot show a gain here

From two examples the search finds a fit for about two thirds of tasks, but 44% of those fits fail the third test
(0.3.8: 151 of 342).
The rest of the failures are tasks the one-expression DSL cannot express within 4 s. Reordering which operations come
first only shuffles which borderline tasks succeed. Raising the score probably needs (a) more expressive programs
(statements, loops with state) or (b) a better check than two examples. A model that only sets costs gets no signal
from MBPP's three-test tasks.

Files: `research/codegen_039/` (`common.py`, `collect.py`, `cv.py`, `develop.py`, `candidates.py`,
`explore_rank.py`, `run_test.py`, logs `cv_log.jsonl`, `development_log.jsonl`, `selection.json`,
`report_0_3_9.json`, per-condition `test_*.json`). Model: `models/cael-code-0.3.9/model.json` (SHA-256 `ba7d8121…0c883f16`),
counts only.
