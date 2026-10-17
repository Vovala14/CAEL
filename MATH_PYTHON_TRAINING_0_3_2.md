# CAEL math and Python training 0.3.2

The owner requested this run on 2026-10-17. This is one bounded training and
evaluation job for the existing unified conditional-count language component.
No runtime architecture changes, neural networks, transformers, private photos,
image jobs, deployment or release publication are involved.

Training and review completed on 2026-10-17 at approximately 11:55 Jerusalem
time. Status and log are `research/math_python_032/status.json` and
`research/math_python_032/training.log`. Process ownership and exact command
are recorded in `research/math_python_032/process.json`. No rerun is queued.

Prepared 217,546 training rows:

- 6,713 human-written GSM8K problems, each contributing its original worked
  solution and a final-number contrast training row (13,426 rows).
- 366 eligible MBPP Python training solutions after held-out duplicate removal.
- 2,000 authored arithmetic and 2,000 authored Python-output examples.
- 199,754 retained licensed earlier language training rows.

GSM8K is MIT; MBPP is CC BY 4.0. Publisher commit revisions, byte hashes,
licence texts, attribution and exclusions are saved in the experiment folder.
GSM8K official test is never used for fitting or model selection. MBPP follows
its publisher's training/development/test ID ranges. Downloaded Python code is
parsed but never executed; only our bounded authored programs are executed to
verify their output labels.

The run refits the existing word/character TF-IDF and sparse statistical count
tables. It selects among six existing sampler settings on development data,
then evaluates once against the previous 0.2.8 association checkpoint.
Runtime sources are checksum-frozen, and vectorized scoring is checked against
the native CAEL scorer. The existing exact arithmetic helper is authored code;
this run does not pretend to train that helper.

Evaluation is deliberately limited: final-number choice questions, reference
Python solution matching, and authored arithmetic/Python-output questions.
These are not free-response GSM8K scores, MBPP pass@1, or proof that CAEL can
generate working code. See the frozen protocol and eventual summary for actual
results. The fresh model is `models/cael-language-0.3.2-math-python/model.json`.
Existing models and live configuration are preserved.

## Results and limits

The run completed in approximately 97 seconds. Selected existing settings:
96 neighbours, recall power 3, recall weight .9, association strength 1,
prefix weight 0. All runtime source hashes stayed unchanged. Eighteen relevant
runtime tests passed, and 16 additional native unified-API checks across all
four confirmation groups matched the recorded scores (maximum error below
4e-15). Checkpoint SHA-256:
`b2e27bb7c5c6e720e0cfdc7e8d58cdb71b5a3462ba7553b238778b193b6d6b45`.

Each row below contains 128 held-out questions, with the same four alternatives
for both models. The previous checkpoint is the 0.2.8 association model.

| Derived diagnostic | Previous | New | New answer-frequency-only control |
| --- | ---: | ---: | ---: |
| GSM8K final-number selection | 23/128 (18.0%) | 74/128 (57.8%) | 81/128 (63.3%) |
| MBPP reference-code matching | 35/128 (27.3%) | 56/128 (43.8%) | 38/128 (29.7%) |
| Authored arithmetic choices | 31/128 (24.2%) | 40/128 (31.3%) | 38/128 (29.7%) |
| Authored Python-output choices | 34/128 (26.6%) | 43/128 (33.6%) | 40/128 (31.3%) |

The answer-frequency control is a post-fit diagnostic, not a selected setting
or another fitting run. It scores the identical answers using only the new
global token distribution. The previous model tied on 120/128 GSM8K cases;
much of the apparent numerical gain reflects vocabulary/answer-prior coverage.
The new model loses to its answer-only control on GSM8K choices. Consequently,
**improved general math reasoning is not demonstrated**. Authored arithmetic and
Python-output context gains over answer priors are only 2 and 3 questions.

Python reference matching shows useful contextual recognition on this derived
task, but does not establish synthesis or functional correctness. No downloaded
code was executed, and no pass@1 or published GSM8K benchmark score is claimed.
The 160-question seen-development regression sample passed the fixed gate;
this is not a fresh general-language benchmark. The candidate is saved for
experiments and has **not been made live**.

Full evidence: `research/math_python_032/summary.json`,
`answer_prior_control.json`, `verification.json`, `development_selection.json`,
`confirmation_scores.json` and `data_report.json` in the same folder.
