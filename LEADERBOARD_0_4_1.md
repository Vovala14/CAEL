# CAEL vs SmolLM2-360M on the Open SLM Leaderboard tests (round 2, 0.4.1)

Goal set on 2026-10-17: score better than SmolLM2-360M, the overall #1 on the
[Open SLM Leaderboard](https://huggingface.co/spaces/AxiomicLabs/Open_SLM_Leaderboard). That leaderboard uses exactly
CAEL's five local tests. The owner chose to **beat it where possible** without neural networks, and approved
downloading the ARC Corpus.

## Result

| Test | CAEL live 0.3.2 | Round 1 | **Round 2** | SmolLM2-360M | Difference |
| --- | ---: | ---: | ---: | ---: | ---: |
| HellaSwag | 27.97% | 27.74% | **27.93%** | 56.30% | −28.37 |
| ARC-Easy | 26.60% | 53.24% | **62.12%** | 68.48% | −6.36 |
| ARC-Challenge | 22.18% | 28.75% | **31.66%** | 38.31% | −6.65 |
| PIQA | 48.91% | 53.21% | **58.65%** | 71.60% | −12.95 |
| ArithMark-3 | 37.80% | 55.10% | **69.50%** | 59.60% | **+9.90** |
| Mean | 32.69% | 43.61% | **49.97%** | 58.86% | |
| Intelligence Index (estimate) | 3.4 | ~18.6 | **27.8** | 41.4 (listed 41.86) | |

- **ArithMark-3 beats SmolLM2-360M**, by 9.9 points. It is the leaderboard's primary math benchmark.
- **ARC-Easy and ARC-Challenge** are now within about 6.5 points of SmolLM2.
- **HellaSwag and PIQA** remain far behind. They need everyday-world knowledge that the non-neural components lack.
- **Overall index (estimated):** 27.8 against SmolLM2's ~41.4. The estimate is the mean gain over chance as a share of
  the possible gain; it reproduces SmolLM2's listed 41.86 to within 0.5. Among the listed models this would place
  about **6th of 238**, between Boris-2-Preview-1 (27.91) and cagliostro-v3.5 (27.49).

## What this is and is not

- **A local comparison on the same test files, not a leaderboard entry.** The leaderboard accepts open-weight language
  models under 400M parameters, run through the LM-eval harness. CAEL is a non-neural system that uses an offline
  Wikipedia snapshot, the ARC Corpus and an exact word-problem solver while answering. SmolLM2's numbers are a
  language model on its own. The comparison is legitimate as a task result but not like-for-like, and is labelled as
  such.
- **No test answers were trained on, and all settings were chosen on development data.** The test sets were scored
  **twice** in total, once per round; each round's settings were fixed before its test run. Separately, inspecting the
  ArithMark format showed four test items with their labels; they were not used for development.

## Method changes in round 2

- **Word-problem solver (`cael_unified/wordmath.py`):** extended to the 17 topics listed in the ArithMark README
  (measurement, money, clock time, patterns, area, perimeter, fractions, data, comparisons, two-step problems). It
  reads numbers, money, times and fractions from options, and commits only when its solvers agree and exactly one
  option matches.
  - **Development:** four authored problem sets in different wordings; each set used for tuning was replaced by a fresh
    one for checking.
  - **Final authored check (never tuned on):** 400 of 600 answered, **100% correct**.
  - **On the real test:** 680 of 1,000 answered, 585 correct (86.0%). The real wording still trips it up about 1 time
    in 7.
- **ARC Corpus evidence (`cael_unified/choice.py`):** BM25 search over a local FTS5 index of 13.9 million ARC Corpus
  sentences (AI2, CC BY-SA 4.0), combined with the Wikipedia evidence.
  - **Weights chosen on development:** Wikipedia 2, ARC Corpus 6, options up to 25 words. The ARC weight is at the edge
    of the grid.
  - **Confirmation, checked once:** ARC-Easy 64.3%, ARC-Challenge 32.6%, PIQA 54.2%.
- **Multiple-choice detection in chat:** three or more inline A–D options count as a question even without "?", so
  continuation-style questions such as "It ends at A) 3:55 B) 4:05 C) 3:45" are answered.

## Deployment

- **Live:** the `choice` entry in `research/active_models.json` records the weights, cut-off and SHA-256 of the
  evaluated `choice.py` and `wordmath.py`. Earlier selections are backed up in `research/leaderboard_040/`.
- **Local data only:** the ARC Corpus index (`data/arc_corpus/arc_corpus.sqlite`, 2.6 GB) exists only on this machine.
  It is git-ignored and not in the 0.2.2 bundle. Without it, the chooser falls back to Wikipedia evidence alone.
- **Tests:** 248 pass in `../.venv-rocm`, which the live worker uses.

Evidence: `research/leaderboard_040/` (`development2_report.json`, `test_report2.json`, per-question
`test2_*.rows.jsonl`, the authored problem sets and their result files, `arc_index.log`).

## What would close the remaining gap

- **ArithMark:** the solver's misses on the real test show phrasing it doesn't cover. More authored wordings per topic
  would help, written without looking at test items.
- **ARC:** try higher ARC Corpus weights or better query construction on development data. The current weight is at
  the grid edge.
- **HellaSwag and PIQA:** non-neural methods historically plateau far below SmolLM2 here. Matching it on these two
  would need a neural model, which is the one option the owner has ruled out.
