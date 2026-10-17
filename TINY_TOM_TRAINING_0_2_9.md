# CAEL unified: fixed-architecture training continuation

Owner request: train for substantially better results, without changing the
architecture. Started 2026-10-17. Current best preceding result is 627/2000
(31.35%) on Tiny ToM, with no experimental language model promoted to live chat.

All existing `cael_unified` Python sources are frozen by SHA256 in
`research/tom_029/architecture_frozen.json`. Training changes only datasets,
fitted vocabulary/counts, sparse association coefficients and existing settings.
The existing sparse linear table is refit by regularized multiclass likelihood;
this adds no runtime layer or feature family. The student remains non-neural.

Two sequential data runs use 33,410 Social IQa training questions and 1,077
deduplicated authored examples. The second adds 90,000 human ATOMIC annotations
(10,000 per relation). Official train partitions only; sixteen ATOMIC events
were excluded by lexical similarity to development stories. The two datasets
share ancestry, so this filter does not prove complete semantic independence.
Publisher sources permit commercial reuse under CC BY 4.0; notices and full
terms accompany derived checkpoints. No MICA outputs or private photos used.

Selection uses the same 1,954-question Social IQa development split as previous
rounds, so improvement on that split alone is not new independent confirmation.
The run considers existing count fitting and at most twelve linear coefficient
passes per data run, stopping after three non-improving development checks.
Only the final development-selected model may receive one additional Tiny ToM
evaluation, and only after improving development by at least thirty questions.
The target remains excluded from training and calibration. Further target
evaluation is disclosed as repeated testing, not a fresh hidden test.

Live progress: `research/tom_029/status.json` and `training.log`.
Owned process: `research/tom_029/process.json` (the Windows virtualenv launcher
also has a Python child). Do not duplicate a healthy job.
Detailed protocol: `research/tom_029/PROTOCOL.md`.

No success is claimed while this job runs. Five percentage points above 31.35%
is the recorded material-progress threshold for this round, distinct from the
harder request to lead the benchmark. Current live chat, story, helper and image
routes and shared tunnel remain unchanged. Image generation stays paused.

An exact scoring replay caught an evaluator error after the first data run:
fast calibration incorrectly cancelled a log-normalizer despite the existing
post-normalization probability floor. The initial development figures are
invalid and retained in `existing_report_before_evaluator_fix.json`. Inference
code was correct and remains unchanged. `resume.py` rechecks saved fits using
the full probability distribution, confirms the winner through the actual
runtime on all development questions, then runs the expanded dataset. Corrected
work is recorded in `resume_process.json` and `resume.log`. No Tiny ToM data had
been evaluated in this round when the error was caught.

Corrected first-run result confirmed through the actual runtime on every
development question: **899/1954 (46.01%)**, versus **843/1954 (43.14%)** before
this round. This is development progress, not a new Tiny ToM result.

The expanded run has compiled **124,487 training rows** and **13,134 fitted
answer tokens**. It is still fitting/validating. A recorded one-shot completion
supervisor (`completion_process.json`, `completion.log`, `complete_run.py`)
waits for development selection, runs the single permitted target evaluation
only if its gate passes, then audits and writes `summary.json`. It never retrains
on target failures, edits runtime architecture, publishes or promotes models.


## Verified result

Selected development result: 927/1954 (previous 843/1954).

Tiny ToM: 620/2000 = 31.00% per word; 29.00% per character. Previous: 31.35% per word. Change: -0.35 percentage points.

Matched-item exact p-value versus preceding candidate: 0.797922. This is a third disclosed evaluation, not a fresh blinded test.

Requested material benchmark progress was not established in this bounded fixed-architecture experiment.

All 44 unified runtime Python files stayed unchanged. 162 tests passed; one obsolete FLUX module skipped. Models remain experimental; live routing/tunnel unchanged. No private photos viewed.

Full evidence, source/model hashes, corrected selection and uncertainty: `research/tom_029/summary.json`, `selection.json`, `audit.json`.
