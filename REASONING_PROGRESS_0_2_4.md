# Non-neural reasoning update — 2026-10-16

The shared worker now handles bounded premise-based deductions, chronological locations/ownership, counting and lists, transfers, size comparisons, ordering and shortest routes locally. It returns a short answer with supporting premises in the result details. Unknown or inconsistent conclusions are explicit. Normal knowledge, weather/news and image/emoji routes remain available. This changes the local runtime, not the released 0.2.1 archive/tag or release copies.

## Free commercial-use data only

- **PrOntoQA/PrOntoQA-OOD:** Apache 2.0, verified from the author's repository and licence. No licence fee; notices retained. https://github.com/asaparov/prontoqa
- **Facebook/Meta bAbI:** CC BY 3.0, verified from the publisher's dataset card. No licence fee; contributor credit, licence URL and transformation notices retained. https://huggingface.co/datasets/facebook/babi_qa
- **BIG-bench logical deduction:** Apache 2.0 as supplied by its repository, used only for evaluation. The benchmark canary is retained. Its schema was inspected during implementation, so this is not a blinded test of language understanding. https://github.com/google/BIG-bench/tree/main/bigbench/benchmark_tasks/logical_deduction

The original bAbI download returned 403; the archive uses the mirror named in the official Keras example. Its first 100 stories exactly matched the publisher-hosted sample. Sources with unclear dataset permissions, including the examined ProofWriter/OpenBookQA options, were not used.

No paid model/API or private photos were used. Full licences and credits are in `licenses/REASONING_DATA_NOTICES.md`, the adjacent Apache licence files and the public `/sources` page. These data permissions do not change CAEL's existing software licence.

## What was trained

- Event-word counts from **10,000 bAbI movement questions**, **10,000 carrying questions**, **10,000 transfer questions** and **10,000 ontology questions**. These fit movement, pickup/drop/give vocabulary and irregular plurals from the official training split. Task statistics also audit 120,000 available training questions; that larger number is not the count supplying semantic supervision.
- Grammatical-category counts from **4,746 distinct PrOntoQA contexts / 56,880 sentences**, from one-/two-hop in-context shelves. All test-context hashes were excluded before fitting; evaluation confirms zero train/test context overlap.
- **126 authored Boolean transition examples** complete the local AND table, including missing-premise combinations absent from the positive-proof corpus.

The runtime is a disclosed hybrid. Learned integer counts control event vocabulary, plural normalization and local truth-table transitions. The parsing schema, binding, proof procedure, chronological updates, ordering constraint search and path search are authored algorithms. It is non-neural and does not learn unrestricted reasoning from raw text. The proof engine uses local rule/fact neighbours in a bipartite graph automaton; the event engine uses neighbouring packet propagation as in the story CA. Ordering/path routines are classical symbolic solvers.

The runtime model stores counts, tables, provenance and context hashes, not dataset stories. Visitors' premises are not saved as training data or sent to the internet by the reasoning route. Each request reconstructs its own state; follow-ups use only the supplied conversation.

## Results

Official bAbI test split, twelve selected tasks, case-insensitive exact matching (set matching for item lists): **11,980 / 12,000 (99.83%)**. Ten tasks scored 1,000/1,000; transfers scored 998/1,000; indefinite locations scored 982/1,000. The other eight bAbI tasks are not claimed as supported.

The two transfer misses contain multiple distinct objects given between the queried pair; the runtime reports ambiguity. The eighteen indefinite-location mismatches contain duplicate alternatives ("either in the school or the school"); the benchmark labels them "maybe", while the runtime keeps the logically certain "yes". These remain counted as benchmark misses.

PrOntoQA positive proof tasks:

| Family | Correct / total | Direct-fact-only ablation |
|---|---:|---:|
| Horn-style conjunction/elimination/chaining | 5,300 / 5,300 | 200 / 5,300 |
| Other/OOD logic | 250 / 2,600 | 2 / 2,600 |
| All supplied test tasks | 5,550 / 7,900 | 202 / 7,900 |

Disjunction, proof by contradiction and other logic remain outside the solver. Positive-only proof targets cannot establish reliable false/unknown handling; separate tests cover missing premises, false converse, failed conjunctions, cycles, negation and contradiction. The direct-fact ablation is not a measured score for the previous chat worker.

Evaluation-only BIG-bench ordering scored **1,500/1,500** over three-, five- and seven-item puzzles. This measures the implemented bounded constraint language, not arbitrary English comprehension or general intelligence.

**107 automated tests pass.** Public checks passed for multi-hop deduction, unknown/conflicting facts, transfer followed by movement, ordering, route finding, size transitivity, ordinary local knowledge and live weather. Another visitor could not access those jobs. Independent new-name/deeper-chain tests reach twelve hops, beyond the one-/two-hop fitting contexts.

## Try it

`Facts: Alice is a bird. All birds are animals. All animals are alive. Is Alice alive?`

`Given: Alice moved to the kitchen. Alice grabbed the key. Alice moved to the garden. Where is the key?`

`Given: Items: A, B, C. B is after A. C is after B. Who is first?`

Premises must use supported simple language and are assumed for the hypothetical scenario; the engine does not verify their real-world truth. Counts refer only to listed events. Complex exceptions, arbitrary arithmetic word problems, induction and general multi-source factual reasoning remain unsolved. Unsupported scenarios abstain rather than being sent online or partially parsed.

## Artifacts and reproduction

- `models/cael-reasoning-v1/model.json`, `sources.json`, `report.json`.
- `research/reasoning_024/`: frozen source hashes, public archives, training records, provenance comparison and public verification.
- `cael_unified/collect_reasoning.py`, `train_reasoning.py`, `evaluate_reasoning.py`: collection, fitting and evaluation.
- `cael_unified/reasoning*.py`, `tests/test_reasoning.py`: runtime and controls.

Reproduce with `python -m cael_unified.collect_reasoning`, `python -m cael_unified.train_reasoning`, and `python -m cael_unified.evaluate_reasoning`. No upstream neural experiment runner is executed.
