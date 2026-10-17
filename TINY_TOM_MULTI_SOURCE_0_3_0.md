# CAEL unified: cumulative multi-source training

Owner request: continue on different sources until learning improves, while
retaining the non-neural architecture. Started 2026-10-17. Prior best Tiny ToM
is 31.35%; the preceding expansion scored 31.00%, and was not deployed.

New sources: Cosmos QA (CC BY 4.0), WinoGrande dataset v1.1 (CC BY 2.0),
CommonsenseQA (MIT). Publisher cards, owner declarations, exact revisions,
SHA256 hashes and full licence terms are retained under `research/tom_030`.
SciQ (non-commercial) and OpenBookQA (unclear dataset terms) were excluded.
No image generation, private-photo access, new neural teacher or MICA training.

The prepared corpus contains 199,754 deduplicated training rows:

| Source | Training rows |
|---|---:|
| Social IQa | 33,374 |
| ATOMIC human annotations | 89,933 |
| Original authored scenarios | 1,077 |
| Cosmos QA | 25,241 |
| WinoGrande | 40,394 |
| CommonsenseQA | 9,735 |

All CAEL unified runtime sources plus root chat/story runtime files are frozen
by SHA256. Feature families, inference algorithms, entity rules, model format
and normalized likelihood scoring stay unchanged. Only fitted data/vocabulary,
existing table coefficients and existing settings change.

Four sequential stages: add Cosmos QA to retained earlier data; add WinoGrande;
add CommonsenseQA; continue the third stage's selected coefficients with
balanced replay across labelled sources. At most twenty passes/stage; five
non-improving checks end that stage and advance to the next source. One weak
source stage does not stop the entire curriculum.

Selection uses 1,700 development questions across four sources. A separate
2,747-question new source confirmation set is held out by whole-story hash:
1,469 Cosmos QA, 656 WinoGrande, 622 CommonsenseQA. The two preceding controls
are measured first; the ONE development-selected new winner is measured once
after all stages. It must improve macro accuracy by >=3 points over the stronger
control, improve two cohorts and avoid a >3-point cohort regression before
another Tiny ToM check is allowed. No target-labelled data enters fitting.
Any fourth target evaluation is a disclosed repeat, not a fresh blinded test.

Exact/near story overlaps were filtered using input text only; those filters
cannot prove complete semantic independence. Source-task accuracy is not proof
of ToM reasoning. No leading-score promise or weak-model live promotion.

Preflight: 960 native probability/ranking comparisons passed, including
two/three/four/five-choice cases and extreme-logit probability floors. Batched
recall matches uncached native scoring. All 18 targeted runtime tests passed.

Live state: `research/tom_030/status.json`, `training.log`, `process.json`.
A separate owned one-shot completion supervisor records `completion_process.json`
and `completion.log`, verifies selection, runs the permitted target evaluation,
checks source/runtime/model hashes, and writes `summary.json`. No automatic
benchmark-guided retraining, publication, live-worker restart or image work.


## Completed results

All four data stages completed. Selected model: C:\Users\vlavrik\PycharmProjects\CAEL\models\cael-language-0.3.0-cosmos-pass12\model.json

Fresh source-confirmation macro accuracy: 35.72%. Best preceding control: 35.37%.

Confirmation gate not met; Tiny ToM was not rerun. Previous best remains 31.35%.

Architecture unchanged; checkpoints not deployed. Full evidence: research/tom_030/summary.json, selection.json, audit.json.
