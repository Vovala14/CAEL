# Reasoning upgrade (0.4.2): "or", contradiction, all 20 bAbI types, explained chat answers

On 2026-10-17 the owner asked to improve the reasoning system and picked three parts:
logic with "or" and contradiction, all 20 bAbI task types, and better reasoning in chat.
Everything is still non-neural: authored algorithms over the stated premises, plus one table
counted from bAbI training stories.

## Results (each test split scored once, after development was fixed)

| Test | Before | **0.4.2** |
| --- | ---: | ---: |
| bAbI (en, 1k), all 20 tasks, test split | 12 of 20 task types supported | **19,964 / 20,000 = 99.82%** |
| PrOntoQA + PrOntoQA-OOD, test examples | 5,550 / 7,900 = 70.3% | **7,848 / 7,900 = 99.34%** |

- PrOntoQA: every family is 100% except Composed, at 848/900. The Composed misses come from demonstration premises
  that contradict each other. After the final change (see below) CAEL reports those as "premises conflict" instead of
  giving an answer. The development score did not change: 57,014 / 57,200 = 99.67%.
- bAbI development (first 1,000 training stories per task): 19,970 / 20,000 = 99.85%.
- Evaluators: `research/reasoning_042/evaluate_babi.py` and `evaluate_logic.py`.

## What was added

- **Case analysis** (`cael_unified/reasoning_sat.py`). Premises become true/false constraints, and a small DPLL solver
  checks them.
  - A conclusion follows when "premises + not conclusion" is impossible. That covers "or" (checking every case) and
    proof by contradiction without separate rules.
  - It handles "Everything that is A or B is C", "No A is B", "A can X / cannot X", negated facts, and questions about
    a whole class ("Is every whale a fish?").
  - It refuses problems with more than 400 atoms.
  - It is used when rule chaining can't decide. Every chained proof is also checked for contradictory premises.
- **Story types** (`cael_unified/reasoning_babi.py`):
  - pairs and pronouns ("Sandra and Daniel… then they… she…")
  - time order (yesterday / morning / afternoon / evening)
  - induction by analogy ("What colour is Bernhard?")
  - 2-D positions
  - compass relations
  - motivations
  - The motivation table (tired→bedroom, hungry→kitchen…) is counted from the bAbI task 20 **training** split only:
    `models/cael-reasoning-v1/motivations.json`.
- **Chat** (`cael_unified/reasoning.py`):
  - **Natural question wordings:** it accepts "Does it follow that…", "Can we conclude that…", "Is it true that…",
    "Must it be that…".
  - **Full-sentence answers:** answers read like "Lily is in the office." instead of "office.", followed by
    "Based on:" and the numbered premises used.
  - **Labelled answers:** answers from case analysis say so. Guesses by analogy or by typical behaviour are labelled as
    guesses. Contradictory premises are reported as such.
  - **Ordinary messages pass through:** messages that only look like a puzzle ("I went to the store yesterday. What
    should I cook?") now go to normal chat instead of getting a "cannot parse" reply. That reply is kept only for
    explicit `Given:` / `Premises:` inputs.

## Tests

- `tests/test_reasoning_extended.py` has 18 new tests.
- The full suite passes: 266 tests, 1 skipped, run with `.venv-rocm`.

## Limits

- The input has to use the simple sentence shapes these solvers read: "X is a Y", "Every/All/No X…", "X went to the
  Y", "The A is left of the B".
- Free-form puzzles in other wording go to normal chat.
- Answers from the motivation table and from induction are guesses from typical patterns, and they are labelled that
  way.
