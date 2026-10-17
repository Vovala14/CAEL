# Connected unified CAEL selection and five-task evaluation

The owner requested connecting the best checkpoints after math training and
running the five tests used for FLAME-W. This is local integration/evaluation,
not a new training round or a release publication.

Four existing language candidates were compared on the same 490 math/Python
development questions and 160 earlier external development questions. The
selection used an equal-source, chance-normalized score across eight groups,
with a three-point external regression limit. These development sets have been
used previously and are not fresh benchmark confirmation. No five-task labels
or scores were used to select a model.

The selected shared language checkpoint is
`models/cael-language-0.3.2-math-python/model.json`, SHA-256
`b2e27bb7c5c6e720e0cfdc7e8d58cdb71b5a3462ba7553b238778b193b6d6b45`.
It is connected through the existing checksum-checked `language` entry in
`research/active_models.json`. All other existing entries were preserved.
One shared language checkpoint handles every benchmark; there is no
benchmark-specific expert selection or mixing of best scores from different
checkpoints. This is the strongest candidate under the recorded development
tradeoff, not a claim that it wins every individual capability.

| Unified component | Connected selection |
| --- | --- |
| Language continuation / multiple choice | Development-selected 0.3.2 math/Python count model |
| Ordinary free-text fallback | Existing installed legacy chat component |
| Story | Reviewed 0.2.6 story override |
| Exact arithmetic / conversions | Existing bounded authored helper |
| State, logic and observer beliefs | Existing fitted reasoning/social models and authored solvers |
| Local knowledge, news, weather and request policies | Existing installed knowledge/policy components |
| Emoji | Existing bundled v7 automaton |
| General pictures | Existing reviewed general-image v2 override and bundle fallback |
| Adult-woman portraits | Existing bundled v15 route |

Inventory and hashes: `research/unified_033/connected_components.json`.
Previous configuration: `research/unified_033/active_models_before.json`.
Candidate comparisons: `research/unified_033/selection.json`.
No source photographs or crops were viewed or discovered, no pictures were
generated and no neural networks or transformers were introduced.

107 relevant automated tests passed. Real integration checks verified helper,
conversion, logic, false belief, story, multiple-choice and loopback HTTP worker
routing, including health metadata and data attribution. The multiple-choice
check verifies connectivity, not general answer correctness: it selected 2 for
the example 2+3, whereas the exact-expression helper correctly computed its
separate arithmetic check. Training has not made native choice scoring a
reliable calculator or Python executor.

The five frozen, zero-shot tests are HellaSwag validation (10,042), ARC-Easy
test (2,376), ARC-Challenge test (1,172), PIQA validation (1,838), and ArithMark-3
(1,000). They run through the actual configured `Assistant.score_endings`,
with no calculator, web lookup, authored symbolic answer overrides, task-name
router, few-shot examples or benchmark training. Primary scores use standard
choice-character normalization for the first four and native token
normalization for ArithMark, matching the historical FLAME-W metric families.
Exact historical prompt/data snapshots were not available, so comparisons
with its saved 0.3.6 table are historical, not paired reproductions.

All datasets/revisions and prepared byte hashes are retained in
`research/unified_033/benchmark_sources_completed.json`. HellaSwag is local
evaluation-only under its publisher card's MIT declaration; the upstream
provenance caveat and initial conservative hold are retained. None of the
benchmark data enters model fitting, runtime weights or dataset redistribution.

Evaluation progress: `research/unified_033/status.json`. Full per-item evidence
is written under `research/unified_033/results_csc`. The first partial run was
resumed without changing scores/model using an equivalent sparse storage
layout; initial outputs and freeze are preserved. See
`research/unified_033/PROTOCOL_STORAGE_LAYOUT_ADDENDUM.md`.

The public tunnel/service was not restarted; loopback verification used a
temporary local server that was closed afterward. The installed unified
configuration is connected for subsequent CLI/UI instances. This task does not
claim that the previously stopped public link has become live.

Final results will be recorded in `research/unified_033/summary.json` and
`research/unified_033/LEADERBOARD_REPORT.md`. Nothing is submitted externally.

## Completed results

| Test | Questions | CAEL unified | Historical FLAME-W 0.3.6 |
| --- | ---: | ---: | ---: |
| HellaSwag | 10,042 | 27.97% | 27.64% |
| ARC-Easy | 2,376 | 26.60% | 27.27% |
| ARC-Challenge | 1,172 | 22.18% | 20.22% |
| PIQA | 1,838 | 48.91% | 52.18% |
| ArithMark-3 | 1,000 | 37.80% | 27.10% |

All 16,428 rows completed; final_audit.json passed. The FLAME-W column is historical, not a paired rerun. No external submission.
