# Provenance and separation

CAEL (Cellular Automaton Event Language) is a separate model family owned by Vovala14. Version0.1 derives from the locally preserved constrained symbolic event-CA experiment of2026-10-13. It is not the native MICA architecture or a MICA foundation-model release.

The original experiment is retained unchanged outside this repository. Earlier CAEL releases (up to 0.2.9 / 0.3) carried that experiment's licence text verbatim, which named MICA Ember / MICA Flame. CAEL and MICA have the same copyright holder (Vovala14), who now licenses CAEL under its own CAEL Non-Commercial License (LICENSE): free for personal and research use, with commercial use reserved to the copyright holder. CAEL is a separate model family and contains no MICA code, weights or outputs. CAEL is not released under an OSI open-source license.

## Commercial-use policy for third-party material

CAEL only uses third-party data, software and graphics whose licence allows commercial use (MIT, Apache, BSD, CC BY, CC BY-SA, WordNet, Unicode, CreativeML OpenRAIL-M). Removed in 0.3.1: the 0.2.1 small-talk reply models (`chat/model_v1.json.gz`, `chat/model_v2.json.gz`), which were fitted on EmpatheticDialogues (CC BY-NC 4.0). The ARC Corpus is never used at runtime (its terms forbid redistribution); a local research reproduction can opt in only with `CAEL_RESEARCH_ARC=1`.

Changes: standalone portable training/evaluation, CAEL naming, cumulative event-memory training, explicit multi-event API, stricter supported-question handling, reports and public packaging. Runtime includes handwritten parsing and slot formatting plus learned cellular event rules, plans and a template-like regular grammar. No neural model is used for training or inference; the curriculum is expert-authored synthetic data.

## CAEL 0.2 emoji model and data attribution
- models/cael-emoji-64-v2 was trained on Noto Emoji (Copyright Google Inc., Apache License 2.0, github.com/googlefonts/noto-emoji @ e20cbc2b, 2D/png/128)
  and Blobmoji (C1710 and contributors, based on Noto Emoji, Apache License 2.0, github.com/C1710/blobmoji @ 7dd14d2b, SVGs rendered to 128x128 PNG).
  The model stores learned counts, not the images. Licences in licenses/.
- Captions: Unicode emoji-test.txt short names + Unicode CLDR English annotations (Unicode License).
- Transparent pixels were composited on white before training.

## CAEL 0.2.1 changes and synthetic-image teacher

0.2.1 adds a shared application, one integrity-checked model bundle, portable
legacy chat fallback, exact arithmetic, the current v7 emoji engine, sanitized
v15 aggregate portrait parameters, and a new categorical general-image student.
The preceding description of expert-authored training and no neural model
applies to Story 0.1, not the new synthetic-image training pipeline.

The general-image student is trained on outputs generated locally by neural
Stable Diffusion 1.5 through stable-diffusion.cpp. It is treated as a derivative
under CreativeML OpenRAIL-M. Original diffusion/text-encoder weights are replaced
by subject-specific registered 64x64 statistical appearance/deformation modes.
Use and redistribution must comply with the included teacher license, paragraph
5 and Attachment A, in addition to the CAEL Non-Commercial License for owned
modifications. Full teacher license: licenses/LICENSE-stable-diffusion-v1-5.txt.
Primary sources: https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-v1-5
and https://github.com/CompVis/stable-diffusion/blob/main/LICENSE.

stable-diffusion.cpp is a separate locally installed MIT-licensed teacher tool:
https://github.com/leejet/stable-diffusion.cpp. Neither its binary nor the neural
teacher checkpoint is redistributed in this release. Runtime student sampling
is non-neural, but its neural teacher's contribution is explicit.

v7 emoji data sources remain Noto Emoji and Blobmoji, with the same Apache and
Unicode attribution above. Public fitting references are included for numerical
rejection and silhouette statistics. Private portrait photos and alignments,
endpoint credentials and private chat logs are not included.

