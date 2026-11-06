# CAEL conversation gap upgrade

An isolated **0.3.9-conversation-r3-candidate** improves rechecking, choices and user-evidence handling while keeping CAEL's non-neural symbolic/count/automaton architecture. Protected solvers, inherited weights/CA kernels, the act-count model, 114 public assets and 251 dependency files remain unchanged. Six inherited sources change and five finite-reader modules are added. No neural model, new learned parameters, Qwen answers, deployment or publication.

## Measured result

Both systems received the same newly authored conversations, with independently evolving visible histories and fresh per-conversation stores. The baseline is the exact previous **conversation R2 candidate**, not the public worker or Qwen. All **186 formal replies** were fully reviewed, including failed turns, code, extra assertions and internal definition attempts.

| Measure | Previous R2 candidate | New R3 candidate |
|---|---:|---:|
| Authored development useful answers | 8/32 | 29/32 |
| Development boundary handling | 14/20 | 20/20 |
| Fresh authored transfer useful answers | **10/29** | **22/29** |
| Fresh transfer boundary handling | 7/12 | 12/12 |
| Fresh whole conversations, including boundaries | 4/16 | 11/16 |
| Fresh whole conversations containing positive work | **2/14** | **9/14** |

This is limited same-author, adaptive/unblinded family transfer, not standard benchmark accuracy, neural parity, or a claim that all remaining gaps are fixed. Boundary successes include safe clarification/uncertainty and must not be presented as solved positive tasks. Source froze before the 41 fresh questions per system were authored; 1,642 normalized prior/development/test-string guards exclude exact matches. No source or primary judgment was changed from transfer outcomes.

Strict focused boundary handling gives 5/12 versus 11/12. Requiring actual visible politeness improvement and a full biological comparison instead of minimal sourced definitions reduces positive totals to 9/29 versus 20/29. All marginal interpretations, actual per-ID reasons and raw/input/review hashes are in SENSITIVITIES.md/json and the full semantic reviews.

## Implemented improvements

- **Typed visible-request references.** Arithmetic rechecks now locate and recalculate the actual preceding request even when a count classifier labels the original wording as an instruction. Number-only follow-ups use the recomputed value. A later substantive/private topic or reset blocks reuse of old arithmetic. Year-only answers require one unnegated birth/opening/etc. anchor in the visible answer; no incidental citation/year guessing.
- **Complete Python rechecks.** The original literal Examples section is parsed as a whole, preserving positional calls, keyword calls and exact expected results. Missing/extra clauses stay ungraded. Both original examples are actually interpreted, rather than silently checking only one. Boolean output is not coerced from numeric 0/1. A follow-up requirement changes the contract and prompts for the complete request; it does not execute file/server side effects or claim a partial solution.
- **Option references and guarded decisions.** Cardinal/ordinal/literal option names resolve. Conditional choices retain the full condition and explicit fallback. User-supplied prices use exact rational comparisons with units; missing/unsupported values, unspecified fees or mixed currencies clarify. An unless clause does not invent an unstated alternative. A later explicit unconditional choice can supersede the guard.
- **Bounded dictionary workflows.** Initial items/keys/values guides and supported literal examples run through the existing VM. Empty mappings produce no output. Unsupported filters are not silently removed from an emitted example. Some initial phrasings are still lost on subsequent turns; see failures below.
- **Attributed personal evidence.** More provenance forms quote only matching actual user assertions. Supported forgetting removes the current profile value/provenance. Private claims remain unverified and out of public search. This does not certify every inherited fallback against every forgotten-fact phrasing.
- **Source-linked definition composition.** A general comparison is split into two literal definition queries, using existing licensed local resources and public-page readers. Generic field/pronunciation prefixes are recognized without rewriting quotes. An unknown term is retried literally when the old delegate changes its spelling. Missing definitions remain missing; authored page instructions to claim verification are ignored. Excerpts and links are limited source support, not a general semantic proof or generated analogy.

## Remaining failures, preserved

The fresh `first instead` turn repeats the second option. This is a wrong stale choice, not a pass because the selected-option route ran. Some dictionary follow-ups fail after a correct initial `How can I` or `Show me how to` guide because the separate topic reader does not retain those forms; literal examples, empty mapping and switching values to keys then fail. A comparison can present correct source-linked definitions but still fail a requested practical example or the full follow-up check of both definitions. A qualified public-notes request remains unresolved. The development compiler/interpreter comparison lacks a reliable, disambiguated second definition. None was silently repaired after transfer.

An old fallback exposed a forgotten editor as a supposed conflicting value; the new supported provenance route avoids it on the tested case. That is bounded evidence, not general transcript erasure. The old source and the original failure remain intact. REVIEW_SCOPE_NOTE.md clarifies the execution/documentation/forgetting scope; no whole-runtime security certification is claimed.

## Qualification and evidence

All **332 inherited tests**, **18 subtests**, and **124 focused checks** pass. The 124 comprise 90 inherited focused cases and 34 new checks, not repeated runs counted as new abilities. All 238 actual JSONL response records, including the first development draft, remain saved. The final development/fresh-transfer subset is 186 fully reviewed replies. Four additional interactive smoke replies demonstrated calculation, actual recheck, bare-result formatting and reset without stale answer reuse; the empty-context response after reset remains awkward and is not scored as useful ability.

The first draft's missing initial dictionary guides, overly strict definition-prefix rejection, subject-altering delegated lookup and all replies/sources are archived under development_history/candidate_1. Pre-response overlap guards caught one development and two transfer exact-text collisions; drafts were retained and replacements happened before any replies. No grammar/outcome filtering was used. 3,619 integrity checks verify hashes, IDs, source/resource preservation and full review coverage; they are not additional capability tests.

The unchanged inline compiler already checked both supplied calls at generation. New literal_cases is used by the independent rechecker; the docstring's broader shared-compiler wording is corrected in REVIEW_SCOPE_NOTE.md without modifying frozen source. Unaltered recorded programs from both systems also pass both original calls in separate VM review. Original replies, flags and check counts remain unchanged.

No new live-web benchmark, peak RAM or optimized latency measurement was made. Authored public-page fixtures are CC0 and isolated from real internet accuracy. Local snapshot content keeps source/licence metadata; general retrieval is still lexical and incomplete. Public/pretraining/family overlap and shared-host cached-bundle execution limit claims. The local candidate requires installed Python, runtime_deps, the inherited public bundle and read-only CAEL_038_wt library plus the policy adapter; it is not a standalone release.

Source freeze: `6b66428369ec45953472820e6039f7f7137e5e856b2874eda2ab6651e853119f`. Full reports, reviews and receipts are hash-bound. Root/user/Claude/image/private files and prior experiments/releases were untouched; live Vynly, worker/tunnel/session selections and GH/HF publications were not changed.

## Try locally

```powershell
C:\Python314\python.exe C:\Users\vlavrik\PycharmProjects\CAEL\research\conversation_r3_039_20261106\run_chat.py --offline
```

`/reset` clears visible conversation and `/quit` exits. Default without `--offline` retains the existing free public-source reader, with private-query gates. This is an unpublished local candidate.
