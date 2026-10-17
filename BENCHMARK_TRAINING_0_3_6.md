# CAEL math-balanced training 0.3.6

Existing non-neural count/recall/association architecture; one fresh count fit and two bounded coefficient fits.
New data: Apache-2.0 DeepMind Mathematics generator, TRAIN functions only. No neural models or teacher outputs.
New-source confirmation is exercise-instance holdout; numeric variants of a grammar can cross splits.
Old development/regression partitions are reused and disclosed. Public tests are never training data.

| Fresh math source | Current 0.3.2 | Candidate |
| --- | ---: | ---: |
| DeepMind add_or_sub | 30.00% | 31.25% |
| DeepMind div | 41.25% | 58.13% |
| DeepMind mixed | 35.62% | 58.13% |
| DeepMind mul | 29.38% | 45.62% |

Fresh confirmation macro gain: +14.22 percentage points.
Answer-frequency-only controls are in confirmation.json; these are choice tests, not verified general mathematical reasoning.

| Repeated local public benchmark | Current 0.3.2 | Candidate |
| --- | ---: | ---: |
| hellaswag | 27.97% | 28.26% |
| arc_easy | 26.60% | 39.90% |
| arc_challenge | 22.18% | 25.77% |
| piqa | 48.91% | 58.16% |
| arithmark3 | 37.80% | 35.20% |

Mean gain: +4.76 percentage points.
Custom native runner, not an official leaderboard submission. All 16,428 rows scored.

Promoted language checkpoint: False.
Lookup improvements are a separate validated conversational route; no benchmark uses web answers.
Original language, image/emoji/portrait/story checkpoints and failed experiments retained. Private photos were not accessed.
