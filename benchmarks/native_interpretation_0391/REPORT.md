# CAEL native interpretation upgrade — measured results

The isolated candidate now routes complete arithmetic, rule, ordering, state, string and table requests through native bounded symbolic operations. The non-neural symbolic/count/automaton architecture, inherited model weights, protected solvers and CA kernels are unchanged. Assistant routing and five new interpreter modules form the six-file patch.

All nine engines completed the same 900 fresh questions: **8,100 actual predictions**, with zero response errors. The final audit verified all frozen source/model assets, reproduced every fixed readout and checked all 900 reference keys independently from question text.

## Same-item improvement

| Scope | Unchanged CAEL 0.3.9 | Native candidate | Gain |
| --- | ---: | ---: | ---: |
| All 900 | 414/900 (46.00%) | 777/900 (86.33%) | +40.33 percentage points |
| New wording, 450 | 92/450 (20.44%) | 327/450 (72.67%) | +52.22 points |
| Familiar format, new instances, 450 | 322/450 (71.56%) | 450/450 (100.00%) | +28.44 points |

All three improvement gates declared before final selection passed: overall gain at least 10 points, new-wording gain at least 15 points, and no family dropping more than 5 points. The candidate improved in every family. There were 123 candidate abstentions; all remain wrong in the accuracy denominator. Every endorsed candidate answer agreed with the independently checked key. The unchanged baseline correctly guessed 19 of the abstained-on items; the paired comparison retains those losses.

## Complete comparison

| Engine | Correct / 900 | Overall | New wording / 450 |
| --- | ---: | ---: | ---: |
| CAEL native candidate | 777/900 | 86.33% | 327/450 (72.67%) |
| CAEL 0.3.9 unchanged | 414/900 | 46.00% | 92/450 (20.44%) |
| Falcon3-Mamba-7B-Base | 353/900 | 39.22% | 179/450 (39.78%) |
| Griot Nano 1 KenLM | 273/900 | 30.33% | 136/450 (30.22%) |
| xLSTM-7B | 273/900 | 30.33% | 125/450 (27.78%) |
| RWKV-7 G1d 0.1B | 247/900 | 27.44% | 114/450 (25.33%) |
| Bigram | 225/900 | 25.00% | 106/450 (23.56%) |
| LFM2-350M | 224/900 | 24.89% | 115/450 (25.56%) |
| MICA Flame-W 0.3.6 | 216/900 | 24.00% | 90/450 (20.00%) |

These rankings describe this synthetic test and the fixed native leaderboard readouts. The neural models used one-token A/B/C/D logit scoring without free-form reasoning; this is not a comparison against their best chat or tool-assisted settings.

## Task families

| Family (150 each) | Baseline | Candidate | Candidate abstentions |
| --- | ---: | ---: | ---: |
| arithmetic | 95/150 | 131/150 | 19 |
| logic | 75/150 | 127/150 | 23 |
| ordering | 81/150 | 127/150 | 23 |
| state_tracking | 90/150 | 132/150 | 18 |
| strings | 41/150 | 128/150 | 22 |
| tables | 32/150 | 132/150 | 18 |

The remaining gaps are unsupported expressions of otherwise familiar tasks. Their complete questions, replies and routes are retained in confirmation/CAEL_RESPONSE_REVIEW.json. They were not patched or rerun after the final set was generated.

## Freshness and scope

- Candidate/source/readout freeze: 2026-11-07T02:54:54.990006+00:00. New question freeze: 2026-11-07T02:57:01.377248+00:00. No final-question fitting or source changes followed.
- New cryptographic seed and opaque identifiers; zero exact prompt overlaps against 235,677 declared known prior/train/development strings and no reused reference programs. Checkpoint pretraining is not fully available, so universal absence from third-party pretraining cannot be certified.
- Task families were known, development was adaptive and implementation-aware, and wording was authored by the maintainer with AI assistance. This is evidence of transfer within six bounded synthetic families, not general chatbot competence.
- The familiar-format 100% applies to exact computations in supported formats of these known families. New-wording accuracy is 72.67%, including all 123 unsupported cases.
- Arithmetic operands and string lengths differ from the previous test. The baseline and candidate above ran on exactly the same new items; scores from different test sets are not treated as paired progress.
- The exact-match scoring rule and error/abstention policy were fixed in the pre-test protocol. Independent reference/report auditors were implemented afterward as unsealed tools; their hashes and initial diagnostic failures are retained in SCORING_SCOPE.json and the audit notes. No key, reply, model readout or scoring criterion was changed.
- Exploratory paired exact McNemar p vs baseline: 6.259928406628576e-89. Authoring/family dependence limits statistical generalization; Wilson intervals and all paired comparisons are in confirmation/report.json.

## Development and existing limitations

Before freeze, 108 authored specs were each tested in direct chat and MC form: candidate 72/72 positive answers and 36/36 focused boundary replies per form. A further 231 unified development requests plus four parser-isolation checks passed independent computations. Those authored checks are separate from the fresh comparison.

Inherited suite: 525 tests plus 78 subtests. Eight old baseline failures persist. Four additional candidate assertions concern three changed successful route names and one deliberate clarification replacing an unsupported statistical guess; the unchanged original tests and full failure evidence are retained. This does not claim all conversation issues are fixed.

## Resources and artifacts

Per-process setup/inference times, host peaks, neural GPU allocation/reservation and pinned model revisions/settings are in confirmation/report.json and runs/. CPU/GPU queues overlapped on a shared host, so these are implementation measurements, not a hardware-efficiency ranking. A whole-process host peak is distinct from GPU memory, total assets or installed environment size.

- Code: candidate_runtime/cael_unified/interpretation*.py and assistant.py; portable native_interpretation.patch with PATCH_MANIFEST.json.
- Architecture/qualification: ARCHITECTURE_NOTES.md, QUALIFIED_DEVELOPMENT.md and DEVELOPMENT_REVIEW.json.
- Frozen evidence: confirmation/source_freeze.json, test_freeze.json, questions.jsonl, gold.jsonl and reference_programs.jsonl.
- Complete results: confirmation/report.json, REPORT.md, COMPLETION_RECEIPT.json, text_reference_audit.json and runs/.

**Deployment:** this candidate is local and unpublished. No Git/HF/leaderboard publication, version bump, Vynly reload, worker/tunnel change or protected resource write occurred.


## Publication and release note

This is the unchanged completed evaluation report. Statements that the candidate was unpublished describe completion time. The owner subsequently authorized publication and release as CAEL 0.3.9.1. The five interpretation modules and Assistant changes are exact evaluated bytes. Version constants, product facts and release documentation differ; packaging replay is a reproduction check, not an additional unseen test. Full public evidence: https://huggingface.co/datasets/vynly/nnai-bench/tree/main/fresh-transfer/2026-11-07-native.
