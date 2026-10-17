# CAEL 0.2.1 model bundle

One checksum-verified archive with a shared application interface. Components
keep their own parameters; this is not jointly learned multimodal reasoning.

## Components

- Chat: legacy CA routing, trained small-talk tables and a previously published
  small factual store. The current remote worker and web lookup are absent.
- Helper: authored arithmetic/writing programs and original Story 0.1 event
  memory. See `STORY_MODEL_CARD.md` for its separate results.
- Emoji: v7 integer patch CA trained on Noto Emoji and Blobmoji with Unicode
  captions. Offline silhouette guidance and speckle cleanup are retained.
- Portrait: v15 joint registered appearance/deformation parameters from 76
  fitting photos, in populations of 39 and 37. No source photos, individual
  coefficient vectors, filenames or private alignments ship. Source-photo
  licensing/provenance was not independently verified in this packaging pass;
  these owner-supplied research parameters retain existing terms.
- General pictures: 32 subject-specific registered appearance/deformation
  models fitted on synthetic SD1.5 outputs. They reuse portrait architecture,
  not private portrait pixels or a neural decoder.

## Synthetic teacher and training

Local Stable Diffusion 1.5 checkpoint SHA-256:
`6ce0161689b3853acaa03779ec93eafe75a02f4ced659bee03f50797806fa2fa`.
The user's installed stable-diffusion.cpp renders 384×384 at 12 Euler-a steps,
CFG 7, then downsamples to 64×64. Four lighting prompts per category with fixed
batches/seeds form the first 1,024-image dataset. No private photos or external
image service are used. The teacher is neural; the statistical student is not.

The student fits one population per subject, rank eight, variation 0.85,
sharpen 0.3 and warp strength 0.6. Pixel-group splitting protects held-out
images globally across labels. They never enter fitting or guard references.
The frozen report records actual final training/held-out counts.

The general-image student is treated as an SD1.5 derivative because it learns
from teacher outputs. Its use and redistribution must comply with the included
CreativeML OpenRAIL-M license, paragraph 5 and Attachment A, in addition to the
existing non-commercial terms for owned modifications. Prominent changes from
the teacher: diffusion and text encoders are replaced by a categorical 64×64
statistical sampler trained on synthetic outputs only. Original teacher
weights are not redistributed.

## Limits and evaluation

Personal experimentation and non-commercial research only. This is not a
foundation model, reliable knowledge assistant, identity-preserving editor or
diffusion-quality image generator. Categories are finite; arbitrary caption
composition and general colour/style controls are not learned.

The local chat fallback does not provide the latest remote chat quality or
live web lookup. The public portrait sampler cannot run its original private
source-photo similarity guard; it checks against synthetic references only.
That heuristic does not guarantee anonymity or absence of memorization.

Generated-only review and synthetic held-out diagnostics are recorded under
`results/general-0.2.1/`. Nearest-training-mean category classification measures
teacher-domain separation, not semantic generalization or realism. No
independent human study or broad image benchmark was performed.

CAEL/MICA attribution remains in LICENSE and NOTICE.md. Third-party emoji and
teacher notices are retained under `licenses/` and inside the model archive.
