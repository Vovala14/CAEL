# CAEL Story 0.1.0 — first trained release

CAEL expands to **Cellular Automaton Event Language**. It is a separate non-neural **hybrid symbolic** family; it is not the pure native MICA language architecture. Handwritten English parsing and slot formatting, an authored world schema, and template-like phrase examples remain part of the design.

## Training

30,000 distinct canonical training frames and 5,000 sequences of 2–4 training frames; 279,314 labelled event instances. Integer opcode choices are learned by consistency with teacher field changes; plan and regular-grammar transitions are counted. No neural model, gradients or external language service. Training seed 2026101317, CPU fit 28.859 seconds. This timing excludes evaluation/dependency installation and is machine-specific.

180 learned local update rules (earlier model 137), 486 grammar states, 77,300-byte JSON model. Model size excludes interpreter, dependency and source code.

Candidate SHA-256: `8be954c2de4a09cf36f45b97de387e799a1abbe4757c63415f810c3226cbebc9`.

Frozen earlier symbolic model SHA-256: `25bf1c55aff6198640799f8f860b031f2b693d7ef67eae3647d1916aa83ce363`.

## Held-out event/state evidence

Canonical semantic-frame splits are disjoint: 30,000 train / 2,000 development / 2,000 confirmation. Eighteen supported historical natural-request frames are excluded from training. Training cumulative episodes use only training frames; evaluation episodes use only their held-out split. Exact hashes in model manifest and split audit.

| Test | Earlier symbolic prototype | CAEL Story 0.1 |
|---|---:|---:|
| Cumulative development episodes |172/200|200/200|
| Cumulative confirmation episodes |169/200|200/200|
| Pooled cumulative episodes |341/400 (85.25%)|400/400 (100%)|
| Single-story exact plan/state trajectories |not rerun|4,000 / 4,000|
| Supported single-story fact questions |not rerun|13,029 / 13,029|

The paired cumulative gain is +14.75 percentage points; episode bootstrap 95% interval[11.50,18.25]. All 59 baseline failures were missing learned rules in cumulative worlds, rather than state mismatches before failure. The candidate had no missing-rule failures or state mismatches. There are 647,738 successful single-story row comparisons and 194,948 cumulative candidate row comparisons; these are repeated local checks, not independent samples.

These are structured, synthetic program/state tests using the same authored teacher semantics. The interval describes sampled episodes under that schema; it does not measure general-English, real-world or cross-domain uncertainty. Reused entities/frames within an evaluation pool also limit independence. No Tiny ToM/leaderboard score or independent human language-quality gain is claimed.

## Natural requests and interface changes

18/20 historical prompts are supported and two are explicitly rejected. Support is not a new 18/20 quality rating. All supported frames and exact complete responses are absent from training; outputs are retained in raw_examples.json. The prior prototype's same-agent blinded 18/20 result is historical and not re-used as a CAEL blind score.

The grammar still has rigid sentence structures. The deterministic formatter now uses some bread/cheese rather than a bread/cheese. Supported questions have explicit closed forms; negative, temporal or compound questions outside them are rejected. The structured API can retain a world across several frames with reset=False; natural-language story requests still reset by default.

## Unedited example

Prompt: Tell me a story about a dog helping a bird find a lost ball.

> Once upon a time, the dog lived near the park. The dog met the bird near the park. The bird had lost a ball and needed help. The dog looked around the park for the ball. At last, the dog found the ball. The dog gave the ball back to the bird. The bird smiled and thanked the dog.

- Where is the dog? The dog is in the park.
- Who has the ball? The bird has the ball.
- Who found the ball? The dog found the ball.
- Who helped the bird? The dog helped the bird.

## Verification and reproducibility

11 tests pass: cell-local synchronous packet update, planner/grammar interior translation, fork/session isolation, cumulative retention/reset, model hash, seeded replay, supported factual answers, unsupported prompt/question rejection, mass-noun formatting and no teacher/neural runtime imports. The training/evaluation/CLI scripts are portable and use only Python+NumPy. The initial evaluator attempt hit the legacy module's distinct Unsupported exception class; the scorer was corrected to count it explicitly as a baseline failure, with no model or protocol change.

LICENSE retains the existing non-commercial terms and attribution; NOTICE identifies the separate family and source provenance. No original MICA model/code/GPU job or preserved prototype was changed. Only synthetic examples and project code are included for publication. See PROTOCOL.md, MODEL_CARD.md, machine-readable results and manifest for exact identities.

## Portability

Two initial deterministic fits and the final portable fit produce identical parsed model parameters. Public model/source files use deterministic UTF-8 LF serialization; the reference model preserves its original bytes. SHA sums cover the release. GitHub CI additionally retrains and checks byte identity on Linux/Python 3.12. CI completion is separate from local verification.
