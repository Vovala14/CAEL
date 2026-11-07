# CAEL 0.4.0 core-engine candidate

Unpublished and not deployed. Source starts from the exact 0.3.9.1 release. This candidate changes actual inference algorithms, not only task readers or UI.

- `reasoning_logic.py`: indexed monotone graph-CA propagation with proof updates and a bounded transition agenda.
- `reasoning_world.py`: sparse ownership-neighbour updates, atomic interaction validation, uncertainty refinement and causal evidence.
- `constraint_automaton.py`, `reasoning_order.py`, `checked_tasks.py`: finite-domain constraint propagation and exact bounded ordering search, up to twelve items. Exhausted budgets refuse instead of returning partial proofs.
- `event_memory.py`: iterative live-reference resolution and version-indexed historical reads.
- `count_language.py`: cache keys include requested neighbour limits; equal-score retrieval is deterministic. This is a correctness change, not newly trained language weights.
- `local_automata.py`: finite local transition induction from demonstration pairs. Ordered and aggregate neighbourhood hypotheses are ranked by whole-pair cross-validation. Unseen contexts are explicit statistical guesses. This learns ephemeral transition tables; it is not a neural model or a general program learner.
- `_bounded_python_help.py`: preserves the checker call signature for multi-engine orchestration while retaining bounded execution/no-record policy.

The normal Assistant accepts `Infer discrete transition:` followed by JSON with `examples` (input/output pairs), `query`, and optional `boundary` (`wrap` or `zero`). No benchmark IDs, hidden rule tables, metadata families or solutions are accepted.

Inherited weights and the resource bundle remain byte-identical. The new transition learner fits new per-request tables from supplied examples; no private data or external LLM answers are training material. Development examples/oracles are authored CC0. Existing CAEL non-commercial and third-party licences remain in force.

The evaluation area one directory above contains failed attempts, exact source hashes, authored development, later fresh confirmation and the separate CellARC protocol. Broad chat ability, arbitrary English/Python understanding and an external-model win are not established by these core mechanisms.
