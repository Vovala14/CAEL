# CAEL chat, story and helper pass — 2026-10-17

The local shared worker now has a bounded non-neural observer-belief solver,
a freshly fitted story surface grammar and expanded exact-arithmetic helpers.
No GitHub release or published 0.2.1 bundle was changed. The existing shared
tunnel URL is preserved. Image generation/training remains paused.

## What improved

- The observer automaton keeps beliefs separate from actual object locations.
  Explicit absence preserves an earlier belief; observation or a report can
  update it. Returning to a room alone does not reveal a hidden object. Reports
  can be false. Missing or unsupported information yields an abstention.
- It fitted integer update counts from **20,000 abstract state observations**
  under an original authored schema. These are not 20,000 natural-language
  stories. The parser, concept vocabulary and permitted state operations are
  authored. Runtime remains non-neural and offline for these scenarios.
- The separate story checkpoint has **76 authored surface templates**, 18 more
  than before, counted over 7,600 repeated surface observations. Event programs
  and plans are unchanged. New questions cover object location, recipient and
  inventory; bedtime tales/fables route through the story engine. This improves
  wording variety and interface coverage, not unrestricted story generation.
- Helpers handle percentages, percentage increases/decreases, arithmetic words
  and exact compatible length, mass, time and volume conversions. Currency,
  temperatures and mismatched dimensions are outside this interface.

New checkpoints are `models/cael-social-v1/model.json` and
`models/cael-story-0.2.6/model.json`. `research/active_models.json` selects the
checksum-verified story model while preserving the previous image selection.

## Requested Tiny Theory of Mind comparison

All **2,000** pinned benchmark items were reserved for evaluation. None supplied
training questions, labels, answers or topic IDs. The dataset is Apache-2.0;
the publisher card, revision and hashes are retained in
`research/language_026/benchmark_manifest.json`. A few public preview examples
were visible during planning, so this is not a blinded study. No fitting or
solver tuning followed the full benchmark result in this pass.

| System/protocol | Result on all 2,000 |
| --- | --- |
| MICA Flame-W 0.3.6, official per-word likelihood | **664 correct, 33.20%** |
| MICA Flame-W 0.3.6, official per-character likelihood | **654 correct, 32.70%** |
| Actual CAEL Assistant, offline four-choice instruction | **0 valid choices; 2,000 abstentions** |
| CAEL belief continuation adapter | **0 supported continuations; 2,000 abstentions** |

Abstentions count as incorrect in the CAEL decision report. CAEL has no comparable
general language-model token-likelihood interface: these rows are different
protocols, not a fair shared likelihood leaderboard or a measured numerical
before/after language-model gain. Web/knowledge lookup was disabled for the
offline full-assistant evaluation. MICA was rerun unchanged, with every file in
its upstream manifest verified. Its non-commercial licence permits this personal
research comparison; its code, weights and outputs are not CAEL training data.

**The requested broad ToM capability was not achieved.** A narrow state solver
does not understand the benchmark's varied social situations and English.
More repetitions of the same abstract state curriculum would not address this
gap. No benchmark-specific answer rules or guessed fallback choices were added.

## Verification and scope

- **360/360** independently authored novel-name location/belief questions pass
  against **0/360** for the prior solver families. This is a supported-schema
  control, not general English accuracy or a substitute for Tiny ToM.
- **192/192** candidate story event/state trajectories match the prior model;
  wording changes in 189. Eight paired generated examples were read. This
  verifies state preservation and variety, not independent human story quality.
- **151 automated tests pass**, including absence/observation, false reports,
  unknown observers, unsupported events, visitor isolation, checksum rejection,
  exact arithmetic bounds, original logic and image routing regressions.
- **11 public checks pass**, covering the new routes, story follow-ups, existing
  local knowledge/logic and denial of access from a second visitor's session.

Try:

`Given: Alice and Bob entered the room. Alice put the key in the drawer. Alice left the room. Bob moved the key to the cupboard. Where will Alice look for the key?`

Answer: `drawer.` Ask `Where is the key really?` with the same premises for `cupboard.`

`What is 15% of 240?` or `Convert 2.5 km to meters`.

`Tell a bedtime tale about a dog sharing a ball with a bird in the park.`
Then `Who received the ball?`, `Where is the ball?`, or `What does the bird have?`.

Detailed per-item results, provenance, hashes and public verification are under
`research/language_026/`. Credits are in `licenses/LANGUAGE_026_NOTICES.md`.
Private photos were never viewed, and FLUX/SD outputs were not used.
