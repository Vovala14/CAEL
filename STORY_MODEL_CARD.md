# CAEL Story 0.1.0

- **Family:** CAEL — Cellular Automaton Event Language.
- **Owner:** Vovala14.
- **Architecture:** non-neural hybrid symbolic cellular system with handwritten
  English parsing/formatting, learned local integer event programs, event plans
  and a learned template-like regular grammar.
- **Model:** `models/cael-story-0.1/model.json`, 77,300 bytes.
- **SHA-256:** `8be954c2de4a09cf36f45b97de387e799a1abbe4757c63415f810c3226cbebc9`.
- **Runtime:** Python and NumPy on CPU. No external model or training-example
  bank loaded during inference. Source code and dependency sizes are excluded
  from the quoted model size.

## Training

The entire corpus is generated from an expert-authored synthetic world schema.
30,000 unique canonical frames and 5,000 sequences of 2–4 training frames teach
279,314 event instances. Programs are induced by intersecting integer opcode
choices compatible with labelled field changes. Plan and grammar choices are
counted. No neural model or gradient training is involved.

The parser, ontology, opcode set, reference plans, event phrase examples and
slot formatting are authored. The model does not discover these concepts from
unrestricted text. A larger synthetic corpus is not evidence of general English
learning.

## Evaluation

Canonical-frame hashes allocate training/development/confirmation at 90%/5%/5%.
The selected datasets contain 30,000/2,000/2,000 distinct frames. The 18 supported
historical natural-request frames are excluded. Cumulative training uses only
training frames; cumulative evaluation uses only its respective held-out split.

Results: 4,000 exact plan/state trajectories; 13,029 supported factual answers;
400/400 successful cumulative sequences against 341/400 for the frozen earlier
symbolic model. The same event streams and teacher semantics are used for both.
There were no measured candidate state mismatches or missing-rule failures.

The old model SHA is
`25bf1c55aff6198640799f8f860b031f2b693d7ef67eae3647d1916aa83ce363`.
This is not a comparison against MICA language models. Scores concern structured
frames under a shared authored schema. The historical 18/20 blinded self-review
quality score is not a new CAEL score. No independent human quality or general
language benchmark is claimed. No benchmark/test questions were used for training.

## Intended use and limits

Use for research into discrete program induction, local state updates and
constrained story-world generation. The system does not support general chat,
arbitrary language understanding, autonomous factual advice or broad reasoning.
Unsupported requests should be rejected rather than interpreted as successful
answers. Sessions reset on a new story unless the structured API explicitly
requests cumulative state.

## License and provenance

Personal/non-commercial research terms in [LICENSE](LICENSE); provenance and
required source attribution in [NOTICE.md](NOTICE.md). CAEL is a separate hybrid
family, not an original native MICA release.
