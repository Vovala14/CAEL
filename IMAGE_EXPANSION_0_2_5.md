# Non-neural image expansion — paused by owner

**Paused 2026-10-17 (Asia/Jerusalem):** the user judged the synthetic dataset
quality insufficient and asked to handle it themselves. Stopped the owned
general generator, teacher and both supervisors; paused the follow-up. The
portrait generation had not started. Existing data/models and the live web
worker are preserved. No fitting or promotion from this pending dataset is
authorized until the user explicitly resumes. `USER_PAUSED.json` markers block
automatic supervisor restarts; exact preserved counts are in `status.json`.
The plan below is historical and is not currently running.

Started 2026-10-17 (Asia/Jerusalem). The prior image run had completed; no
synthetic image generation continued while the recent text fixes were made.
This new bounded run resumes the user's requested image work.

The CAEL student stays non-neural: grouped classical shape/appearance statistics
and integer-count factor cellular automata. Local Stable Diffusion 1.5 is only
the synthetic-data teacher. No private training photos or crops are discovered,
read, displayed or sent anywhere by this pipeline.

## Data

Generate **2,048 new synthetic images**: 64 for each of 24 new topics and eight
renewed old topics. Each render has a saved caption, seed, generation settings
and file/pixel hashes. Teacher resolution is 384×384 at 16 steps; student inputs
are 128×128. Generation is resumable with a checked protocol.

New topics: bus, train, helicopter, tractor, tablet, monitor, keyboard, computer
mouse, television, sofa, table, bed, lamp, bottle, book, apple, banana, cake,
guitar, elephant, lion, fish, castle and waterfall.

Renewed topics: bicycle, airplane, boat, laptop, headphones, horse, pizza and cup.

Combine these with the previous 2,048 synthetic inputs for **4,096 total images
across 56 topics**. Preserve every old development/confirmation partition and
every previously excluded synthetic face. Separately reserve new development
and confirmation examples before fitting. Do not train on earlier held-out data.
Reject duplicate pixels across the datasets rather than silently leak examples.

Teacher checkpoint SHA-256:
`6ce0161689b3853acaa03779ec93eafe75a02f4ced659bee03f50797806fa2fa`.
Existing free-commercial CreativeML OpenRAIL-M terms and notices apply; see
`licenses/LICENSE-stable-diffusion-v1-5.txt`. No new external service or model
download is used.

## Bounded experiment

After generation completes, the supervisor automatically freezes the combined
dataset and fits two students on identical partitions:

- Control: up to four appearance/shape populations, eight latent factors.
- Candidate: up to eight smaller populations, four latent factors, to test
  whether less averaging preserves object geometry better.

Both retain joint CA seeding and the synthetic-fitting-reference similarity
guard. Detail texture is disabled because the earlier experiment did not show
that it improved shapes. This is an experiment, not evidence of improvement yet.

The next stage generates comparison pages containing **student outputs only**.
It checks hashes and records sharpness/guard diagnostics without treating these
as semantic or realism scores. Existing stronger live models remain selected
until generated-only review supports a change. New topic names in a curriculum
do not imply that the live model has already learned them.

The teacher is bound to localhost and stopped after generation or pipeline
failure. Generation is capped at three hours; each fitting/evaluation stage at
30 minutes. Only recorded owned child processes are managed.

## Tracking and follow-up

- Supervisor: `research/general_image_025/supervisor_process.json`.
- Current stage: `research/general_image_025/status.json`.
- Actual generated count: `research/general_image_025/new_dataset/progress.json`.
- Logs: `research/general_image_025/pipeline.log`, `generation.log`, and named
  fitting/evaluation logs when those stages start.
- Planned models: `models/cael-general-128-v3-control/` and
  `models/cael-general-128-v3-expanded/`.
- Planned generated-only evaluation: `results/general-0.2.5/`.

An active thread follow-up, **Finish CAEL image expansion**, checks this bounded
run every 30 minutes, stays quiet while healthy and unchanged, and resumes
generated-only review/deployment work when ready. It reports meaningful
completion/failure and pauses after this expansion is handled.

Validation before launch: synthetic curriculum/alias tests pass. Subsequent
tests verify nested compound aliases, preservation of held-outs/exclusions and
cross-dataset duplicate rejection. No new model has been declared improved or
activated at the start of the run.

## Added portrait requirement

The user expects clear portraits at the end of this run. The general expansion
alone did not add portrait data, so a separate focused portrait experiment is
now queued in the same run. Its supervisor is
`research/general_image_025/run_portrait_pipeline.py`; tracking is under
`research/general_image_025/portraits/`.

After the general experiment releases the GPU, generate 1,024 new synthetic
studio headshots: 512 adult women and 512 adult men, with consistent front pose,
open eyes, neutral expressions and plain backgrounds. Render at 512×512/24 steps
for **native 256×256 student inputs**. Save captions and hashes. Do not open any
private source photos. Freeze a separate fit/development/confirmation split
before fitting; estimate classical eye alignment from fitting examples only.

Fit an eight-population/rank-eight continuous Gaussian statistical control and
a sixteen-population/rank-four count-based factor CA candidate. Both are
non-neural, with variation 0.85, deformation strength 0.6 and conventional
luminance sharpening 0.3. This comparison changes grouping/rank/sampling jointly;
it can identify a useful candidate, not isolate one causal improvement.
The continuous control retains the sampling approach of the stronger historical
portrait branch rather than assuming that the factor CA must win.

Retain **all 16 fixed generated samples per gender and model**, compare with the
actual current generator, and save eight generated-only comparison pages to
`results/portrait-0.2.5/`. Native resolution, edge sharpness and Haar face/eye
detection counts are diagnostics only. Required review: coherent eyes, nose,
mouth, jaw and face shape, with visibly reduced blur across the fixed samples.
Do not claim clear portraits or replace the stronger v15 route based on
resolution alone. If clarity is not achieved, report that result and the stall.

The optional checksum-checked `portrait_image` runtime override now supports
reviewed native 128/256px woman/man models, but **no portrait override is active**.
Per-subject sampling settings can preserve the reviewed control/candidate choice
when combining compatible portrait priors. Keep existing routes until review.

The existing follow-up now covers both general and portrait stages; it must not
stop after only the general experiment. This additional portrait work extends
the run and does not guarantee photorealism. All 122 software tests pass.
