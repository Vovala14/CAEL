# CAEL 0.4.0 core upgrade and CellARC evaluation

7 November 2026. **Isolated frozen candidate, not published or deployed.** This is a substantial core-engine change with a demonstrated finite-task gain. It is not a demonstrated general-chat breakthrough.

## What changed in the actual engines

The source starts from the exact public 0.3.9.1 ZIP (SHA256 `7e6e51f1a9247cfcb24df66c5ead85492d6af08db5593bd66255a49805980748`). Twelve existing runtime/metadata files changed and two runtime modules were added. `CORE_0_4.patch` contains the reviewable change. Dirty root/user files and the live worker were not edited.

- **Rule graph automaton:** indexed fact-to-rule propagation replaces full rescans and a fixed 24-round cutoff. Proof improvements reach the same fixed point as truth values. Bounds are on actual transition work. Direct graph-engine tests include 110-hop proofs. The full old Assistant already solved our fresh long-chain cases via its SAT fallback, so this is not reported as a new unified-answer gain in that family.
- **World automaton:** events visit the actor and affected carried objects through ownership edges. Complete ownership/location transactions are validated before mutation. Negative observations refine a set of possible locations; causal evidence and dropped-object state are retained.
- **Ordering engine:** finite-domain propagation and bounded complete backtracking replace factorial enumeration. Supported explicit puzzles can use twelve items. Search exhaustion refuses rather than emitting a partial proof. The ordinary checked-task route uses the same engine.
- **Live state memory:** iterative dependency resolution replaces the arbitrary 128-link/recursion ceiling. Historical reads use version indexes; copies stay snapshots while live links track later changes.
- **Count-language retrieval:** requested neighbour count is part of the cache key, and tie boundaries use deterministic document IDs. This fixes retrieval correctness; it is not newly trained language weights or demonstrated broad language improvement.
- **New local transition learner:** input/output demonstrations induce ordered or aggregate neighbourhood maps. Whole-pair cross-validation selects hypotheses. A generic structured Assistant route accepts `Infer discrete transition:` plus examples/query JSON. Unsupported contexts retain explicit backoff/empirical guesses and ambiguity diagnostics. This is finite statistical/symbolic induction, not a neural model or unrestricted program synthesis.
- **Engine interoperability:** the bounded checker wrapper again accepts the documented `record` argument, without enabling native generated-code execution or persistent recording. This fixes 25 inherited failing orchestration/tool checks.

Inherited weights, protected `choice.py`/`wordmath.py`, public image/CA kernels and 80 available immutable public resources remain byte-identical. The resource archive still has version 0.3.7; the new core algorithms live in 0.4 source and fit request-local transition tables. No external LLM supplies runtime or training answers.

## Core qualification, before CellARC

The final 28 authored development cases produced 20/20 positive answers and 8/8 focused boundaries, versus 4/20 and 0/8 for 0.3.9.1. These repeats/iterations are development only.

After exact source freeze, a separate seed produced 76 fresh authored instances with no exact development-prompt matches:

| Category | 0.3.9.1 | 0.4 candidate |
|---|---:|---:|
| Positive answers | 12/60 | 60/60 |
| Focused boundary clarification | 0/16 | 16/16 |
| Minimal safe boundary handling, separate leniency | 4/16 | 16/16 |
| Response errors | 0 | 0 |

The baseline's four generic “Tell me more about that” replies get equal minimal-safe credit in the alternate; original automatic flags remain unchanged. Twelve baseline ownership replies instead silently give an already-held object to a different person. The candidate identifies that conflict.

These cases use known development families and finite readers. Names, relations, values and example rows are new; authoring and evaluation are maintainer-led/AI-assisted. **60/60 is a scoped engineering confirmation, not broad unseen-English accuracy.** It satisfies the predeclared +25 percentage-point positive-answer gate (+80 points here) and no-boundary-regression requirement.

Inherited relevant regressions: baseline **631 passed, 29 failed**; candidate **671 passed, 4 failed**, with 12 subtests in each. The candidate has 15 additional core unit tests, not 40 newly created abilities. Twenty-five old failures are fixed; no new inherited failure appears. The four remaining baseline failures concern quantity-conversation follow-ups and a possessive/pronoun recall case. All failures/initial drafts are retained. The independent constraint oracle checks small problems against exhaustive permutations; tests also cover transaction rollback, provenance, live/copy isolation, limits and retrieval ties.

## CellARC: full official test splits

Source: Miroslav Lžičař's [CellARC](https://github.com/mireklzicar/cellarc), supervision-only [dataset](https://huggingface.co/datasets/mireklzicar/cellarc_100k), revision `76040e6aef0edc4982e53c13a85ef227378ed171`.

All 1,000 interpolation and 1,000 extrapolation tasks were evaluated once per engine after core qualification and source freeze. Each actual Assistant sees only five example pairs and the query. Solutions, IDs, hidden rules, family/radius/window/alphabet metadata and step counts are excluded. No benchmark training/validation fitting is performed; the rule class/protocol was known during engineering. Public TRAIN previews were visible in documentation browsing, not used as development data. All guesses/invalid replies remain in the denominator.

| 0.4 candidate | Interpolation | Extrapolation |
|---|---:|---:|
| Correct query cells / all cells | 6,361/11,099 | 3,815/10,918 |
| Aggregate cell accuracy | **57.31%** | **34.94%** |
| Mean of episode cell accuracies | **57.69%** | **36.38%** |
| Entire puzzles correct | **79/1,000 (7.9%)** | **5/1,000 (0.5%)** |
| Clarifications / invalid grid replies | 8 | 0 |
| Runtime exceptions | 0 | 0 |

The old 0.3.9.1 Assistant emitted no valid output grids through this structured request interface (0/2,000 exact; no exceptions). That establishes the absence of this native interface/capability in that baseline, not zero ability on other phrasings or a competitive chat comparison.

Eight interpolation tasks were rejected because identical input demonstrations have differing outputs under the learner's stationary deterministic-row assumption. They count fully wrong. This is a compatibility/assumption finding, **not a proved dataset defect**, and nothing was repaired.

Most cells are not covered by the selected hypothesis: only 1,688 interpolation and 1,040 extrapolation cells have that diagnostic flag. Backoff maps/empirical guesses still contribute to the primary score. 224 interpolation and 29 extrapolation tasks use empirical-only predictions. Few-shot fitting cannot establish a unique hidden rule; long/multistep effects and unseen neighbourhoods remain weak.

For context, **post-hoc diagnostic controls**, not replacement scores or predeclared competing models, on the same data:

| Simple control | Interpolation cell accuracy | Extrapolation cell accuracy | Exact puzzles, I/E |
|---|---:|---:|---:|
| Repeat most frequent support-output symbol | 51.42% | 29.73% | 14 / 1 |
| Copy the query unchanged | 32.71% | 18.02% | 0 / 0 |

The candidate exceeds our frequency control by 5.89 and 5.21 percentage points, much less dramatic than comparing to an unsupported input interface. Whole-puzzle extrapolation remains poor. We did not rerun published leaderboard models. Their metadata access, prompts, subsets, compute and averaging can differ, so **no direct leaderboard rank, Qwen win or general architectural superiority is established**.

The official helper returns per-episode cell accuracy; both its mean and the token-weighted aggregate are shown. The 57.31%/34.94% aggregate scores must not be called exact puzzle success. Exploratory episode-cluster bootstrap 95% ranges are 55.81–58.84% and 33.76–36.17% for aggregate cells; family dependence and benchmark-aware engineering limit interpretation.

## Resources and reproducibility

Same installed inherited model selection in both engines, Python 3.14.0, fixed seed 401107, CPU, one BLAS/OMP thread, request-local learning, network/DNS disabled. Native inference imports no neural model/checkpoint for this route.

Candidate load: 0.973 s; inference over all 2,000 tasks: 1.498 s; peak full-process working set: **109.13 MiB**. Baseline load: 1.001 s; inference: 12.495 s; peak process: **163.13 MiB**. These are this structured route on one shared Windows host, not an optimized-neural comparison or an efficiency ranking. They exclude the separate scoring/bootstrap process. Inherited archive size is 562,714,794 bytes and is not RAM. Do not substitute historical source-only memory measurements.

`SOURCE_FREEZE.json`, `CORE_QUALIFICATION.json`, `cellarc/INPUT_SEAL.json`, per-engine receipts, original full reply streams, separate gold/grades and `FINAL_AUDIT.json` bind the evidence. Independent scoring reproduces every cell and episode; **10,298 integrity checks are not capability questions**. Candidate source remained exact through all test inference and auditing.

The original dataset files, pinned licences and metadata discrepancy are preserved. Actual dataset `LICENSE` is **CC BY 4.0**, despite an MIT dataset-card tag and the earlier sealed protocol description; see `cellarc/LICENCE_NOTE.md` for attribution and the explicit correction. Upstream code is Apache-2.0. CAEL remains non-commercial source-available; these licences are not conflated.

## Remaining work and release status

This is a real upgrade to the core engines, with a new transferable discrete-transition capability and better state/constraint execution. It is not yet a general conversational leap. The four inherited conversation failures, unsupported wording, sparse transition evidence and low exact extrapolation accuracy remain material gaps.

No source, settings or benchmark grader were changed after CellARC test access. No new training/tuning loop was started on viewed tests. No Git/HF release, commit/push, leaderboard submission, Vynly worker or tunnel change occurred. A future release decision should use this evidence and the remaining gaps, not the authored perfect score alone.
