# Provenance and separation

CAEL (Cellular Automaton Event Language) is a separate model family owned by Vovala14. Version0.1 derives from the locally preserved constrained symbolic event-CA experiment of2026-10-13. It is not the native MICA architecture or a MICA foundation-model release.

The original experiment is retained unchanged outside this repository. Source license terms are preserved verbatim in LICENSE; they are non-commercial and include attribution to MICA Ember / MICA Flame by Vovala14, https://github.com/Vovala14/Mica-Ai. This attribution records code provenance, not architectural identity. CAEL is not released under an OSI open-source license.

Changes: standalone portable training/evaluation, CAEL naming, cumulative event-memory training, explicit multi-event API, stricter supported-question handling, reports and public packaging. Runtime includes handwritten parsing and slot formatting plus learned cellular event rules, plans and a template-like regular grammar. No neural model is used for training or inference; the curriculum is expert-authored synthetic data.

## CAEL 0.2 emoji model and data attribution
- models/cael-emoji-64-v2 was trained on Noto Emoji (Copyright Google Inc., Apache License 2.0, github.com/googlefonts/noto-emoji @ e20cbc2b, 2D/png/128)
  and Blobmoji (C1710 and contributors, based on Noto Emoji, Apache License 2.0, github.com/C1710/blobmoji @ 7dd14d2b, SVGs rendered to 128x128 PNG).
  The model stores learned counts, not the images. Licences in licenses/.
- Captions: Unicode emoji-test.txt short names + Unicode CLDR English annotations (Unicode License).
- Transparent pixels were composited on white before training.

