# CAEL unified Tiny ToM training — 2026-10-17

**The requested leading score was not achieved.** The latest independently
selected non-neural CAEL unified candidate scores **627/2,000 = 31.35%** per
model word token and **594/2,000 = 29.70%** per character. Its word-score 95%
Wilson interval is 29.35%–33.42%. It remains experimental and is not selected
in `research/active_models.json`; the shared worker is healthy.

## Full benchmark results

| System | Per word | Per character |
| --- | --- | --- |
| First trained CAEL unified candidate | 29.90% (598) | 28.20% (564) |
| Second trained CAEL unified candidate | 31.35% (627) | 29.70% (594) |
| MICA Flame-W 0.3.6, earlier fresh local full-config run | 33.20% (664) | 32.70% (654) |

All use the same 2,000 pinned Tiny Theory of Mind items, revision
`ba4c644ea7ace67e096305fe2c9f87c4cf4879ad`, input SHA-256
`58827a0361597ae4d5ffa79ddbab0936d1509cafcfc02cbb731e4d7a7f3584b8`.
The publisher currently lists 47.20% for its leading small-model baseline and
51.70% for its leading LLM baseline; those reference results were not rerun here:
https://huggingface.co/datasets/AxiomicLabs/Tiny_Theory_of_Mind
These are local measurements, not a submitted or independently verified ranking.

The earlier CAEL all-abstention result used a generated-answer instruction
protocol. It is not a comparable likelihood baseline; do not describe this
experiment as a fair numerical improvement from 0% to 31.35%.

## What was actually trained

These are components of the existing **CAEL unified assistant**, not a MICA
replacement or an unrelated chatbot. `Assistant.score_endings()` loads the
selected experimental language checkpoint through the same assistant class.
Explicit multiple-choice chat requests can use the same component when it is
selected. Ordinary knowledge, helper, story, emoji and photo components remain
available, but these weak language candidates were not promoted to the public
worker or packaged as a new published release.

The model is a statistical retrieval/count hybrid, **non-neural** and CPU-only.
It fits sparse lexical features, correct/contrast answer-token cooccurrence
counts and prefix counts. Normalized token probabilities are scored for each
ending independently. No attention, neural layers, gradient optimizer or neural
teacher inference is used. This component is not a pure cellular automaton;
the unified assistant's existing bounded observer automaton remains separate.

Six checkpoint variants were fitted across two rounds: conditional counts,
contrastive associations and a WordNet lexical variant in each round.

- Round 1: **39,640 training rows**: official Social IQa 33,410 plus 6,230
  authored variations. The selected WordNet candidate scored 830/1,954
  (42.48%) on Social IQa dev and 644/726 on authored dev.
- Round 2: **34,487 training rows**: Social IQa 33,410 plus 1,077 canonical
  authored scenarios after consistent entity binding. Capitalized names are
  mapped to context-local addresses before fitting/scoring. This parser is
  authored and approximate; it is not learned general entity understanding.
  Selection used Social IQa dev only. Associations and WordNet tied at
  843/1,954 (43.14%); the earlier, simpler association variant won the
  deterministic tie. Its canonical authored diagnostic was only 49/96.

The selected second checkpoint is
`models/cael-language-0.2.8-association/model.json`, SHA-256
`1bd02953812d5a8787687890ca8ac717851ee07e850ad1e77898b8db0ae3ef27`.
The WordNet tables are not in that selected checkpoint. All failed variants,
source hashes, data notices and pre-correction metadata remain preserved.

## Data and evaluation separation

Social IQa uses its official training/development split, CC BY 4.0; notices credit
Maarten Sap, Hannah Rashkin, Derek Chen, Ronan LeBras and Yejin Choi. WordNet 3.0
lexical experiments use Princeton's permission for commercial use without fee,
with the full licence retained. Additional situations were authored in this
coding session. Source cards, archive hashes, licences and transformations are
recorded under `research/tom_027/sources/`, `research/tom_027/sources.json` and
`licenses/TOM_027_TRAINING_NOTICES.md`. Each checkpoint carries attribution files.

No Tiny ToM questions, labels, answers or metadata supplied fitted counts or
hyperparameter selection. Input-context hashes checked contamination without
using labels. Round 2 also audited entity-normalized target contexts: zero
overlap. Development contexts were protected; the reported 1,930 protected
context keys are not 1,930 removed training rows. No official training rows
overlapped those keys. One constant authored scenario overlapped the initial
name-only split; its validation contribution was removed before first-round
selection was finalized, preserving the original report as evidence.

There were **two disclosed target evaluations**. The first aggregate result
informed the decision to continue. Separate counterfactual controls motivated
the second round's entity binding. Target item-level errors/per-topic answers
were not used to engineer the change. This is a repeated public-benchmark
experiment, not a fresh blinded confirmation. Source and model hashes were
frozen before each target evaluation; exact source copies are retained.

## Why this is a stall

The latest candidate beats its own unconditional-token ablation, 25.80%, but
does not beat MICA's point score or approach the publisher's leading results.
The second-round increase is 29 additional answers out of 2,000; exact matched
comparison statistics are retained in `research/tom_028/summary.json` rather
than presenting the increase as a demonstrated large gain.

Previously seen wording/counterfactual diagnostics decline from **9/14 to 7/14**.
Passing a mechanical consistent-renaming test does not prove understanding of
who knows what. The model still relies on shallow lexical associations, does
not reliably compose beliefs/roles, and ties on 149 benchmark items. About
17.49% of candidate-ending tokens are outside its fitted vocabulary after
binding. Word-token scoring uses the model's own tokenizer; round 2 includes
entity address tokens, while character normalization uses original text lengths.

**162 tests pass, one obsolete FLUX module is skipped** (163 run). Checks cover
normalized probability mass, extreme numerical values, independent choices,
checksums before deserialization, consistent name binding, unified-interface
integration, existing reasoning/helper/story/image routes and visitor ownership.
The isolated training environment could not run the whole product suite because
it lacked image dependencies; the final full suite ran in the actual production
Python environment with its existing image libraries and the added CPU-only
statistical dependencies. That earlier failed check is retained in the logs.

No new language candidate was deployed. Private photos were never viewed, image
training remains paused, the tunnel and existing model selections are preserved,
and no GitHub release was pushed. Repeating the same data is not a demonstrated
route to the requested leading score. Stronger compositional grounding remains
unresolved within these experiments.

## Reproduction and experimental use

Original first-round sources are under `research/tom_027/frozen_sources/`;
second-round sources are under `research/tom_028/frozen_sources/`. Per-item native
likelihoods, paired comparisons and source/model fingerprints are retained in
the two research directories. Existing target reports are not silently overwritten.

To try the experimental component through CAEL unified:

```python
from cael_unified.assistant import Assistant

assistant = Assistant(language_checkpoint=r"C:\Users\vlavrik\PycharmProjects\CAEL\models\cael-language-0.2.8-association\model.json")
scores = assistant.score_endings(
    "A person is preparing flour, eggs and a cake tin. They plan to",
    [" bake a cake.", " repair a bicycle.", " swim.", " paint a room."],
)
```

This explicitly loads a research candidate; it does not imply that the goal was
achieved or that its choices are reliable general answers.
