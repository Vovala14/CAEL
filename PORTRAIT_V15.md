# v15: cleaner portraits, followed by a visible plateau

Best new checkpoint: `models/cael-portrait-64-v15-appearance/model_v15.pt`.
It gives substantially clearer eyes, noses and mouths than v13, removes most
pixel speckle, and reduces doubled features. The remaining averaged/doll-like
appearance, similar identities and background/shape artifacts mean consistent
photorealism has not been achieved. The last tested change did not produce a
clear visible gain, so this pass stopped at that plateau.

Only generated portraits were viewed. No private source photo, source crop or
alignment preview was displayed or exported. Source photo hashes and previous
checkpoints were checked unchanged. All 52 held-out images stayed excluded from
fitting; no additional photos were requested.

## Architecture and fitting

This best-performing branch is a **non-neural statistical shape/appearance
model with continuous rendering**. It replaces pixel CA rendering. It must not
be described as the cellular rules alone learning to produce these faces.
The earlier CA checkpoints remain available unchanged.

Among the 192 fitting faces detected for v13, a classical Haar eye detector
found 76 plausible eye pairs. These are a subset of the 470 allowed fitting
photos, disjoint from all 52 held-out photos. A similarity transform aligns
their eyes to positions derived from fitting-population medians.

Classical Farneback optical flow registers those eye-aligned images to aggregate
population templates, reducing feature misalignment before fitting appearance
variation. Joint principal-component statistics learn both registered Lab
appearance and displacement fields. Two populations contain 39 and 37 fitting
photos, each with eight aggregate variation directions. Sampling uses random
coefficients; no source photo or individual source coefficient vector is stored.
The sampled displacement is inverted numerically to render the sampled face.

Rendering uses continuous Lab colour instead of the 48-colour stochastic pixel
sampler. A conventional luminance unsharp mask of 0.3 is applied. The fixed
variation is 0.85 and deformation strength 0.6. There is no neural network,
backpropagation, pretrained image generator or external image service.

The checkpoint is 1,602,033 bytes. Weights are self-contained; the numerical
similarity guard still needs the unchanged local fitting photos. It reads them
blindly in memory and never uses them to retrieve replacement image pixels.

## Experiments and stopping decision

Three approaches were compared using fixed generated development batches:

1. Eye alignment and continuous appearance rendering: markedly cleaner and
   clearer than v13, but some double features and averaging remained.
2. Registered joint shape/appearance statistics: reduced feature ghosting and
   retained useful diversity. This is the selected version.
3. A learned integer CA over appearance-factor categories: changed which faces
   were sampled but did not show a clear further visual improvement. It was
   retained as a failed/neutral experiment and not included in the checkpoint.

The last experiment's stop rule was declared before generation: keep the prior
version and stop if the factor CA gave no clear visible improvement. This stop
does not establish that all future architectures would fail; it records a
plateau in this bounded line of experiments.

## Frozen generated-seed comparison

After selecting the registered version, 32 further samples used a new fixed
seed schedule. Same-seed v13 comparisons were generated in the same runtime.
No attractive examples were selected from a larger pool. `comparison.png`
shows the fixed first eight from each: v13 above, v15 below.

| Diagnostic | v13 | v15 |
|---|---:|---:|
| Pairwise RGB L1 diversity | 47.6891 | 47.0342 |
| Edge density | 0.1792 | 0.0962 |
| Minimum nearest-fitting RMS | 0.1208 | 0.1680 |
| Guard replacements | 2 | 0 |

All v15 samples passed the unchanged RMS cutoff of 0.12. References cover the
470 base-preprocessed fitting images, 192 face-aligned fitting crops and 76
eye-aligned fitting crops. This is a similarity heuristic, not an anonymity or
no-memorisation proof. Original i16 source photos outside this folder were not
audited. Held-out photos do not enter the guard.

Same-author, nonblind review of generated comparisons and the complete grids
found clearer facial features and less grain. Remaining examples include
unnatural forehead detail and illumination in samples 2 and 3, stretched hair
and necks, painted backgrounds and similar-looking faces. This is qualitative
development evidence, not an independent realism benchmark or a face-accuracy
percentage. All outputs and failure examples are retained.

## Generate locally

From the project folder, choose a new output directory:

```powershell
& ..\.venv-rocm\Scripts\python.exe cael_assistant\portrait_appearance_cli.py --out outputs\portrait_v15_example --seed 42 --n 4
```

Generation is CPU-only and does not need OpenCV. OpenCV was used only for blind
alignment/registration while fitting. True output resolution is 64x64; grids
use nearest-neighbour enlargement. Seed reproducibility is checked in the same
PyTorch runtime and fixed batch schedule. There is no caption/prompt control in
this branch. The running web UI still uses i16 and was not restarted or changed.

## Verification and artifacts

All **42 software tests passed**, covering alignment coordinates, inverse
deformation, seeded generation, checkpoint reload, exact count lookups,
holdout exclusion and failure without returning a source-like rejected batch.
The actual saved v15 checkpoint reloaded and reproduced its seed-42 pixels
exactly. All original source photo hashes and the v13 checkpoint hash remained
unchanged.

- `models/cael-portrait-64-v15-appearance/comparison.png`: generated before/after.
- `models/cael-portrait-64-v15-appearance/v15_grid.png`: all 32 final samples.
- `models/cael-portrait-64-v15-appearance/report.json`: frozen diagnostics.
- `models/cael-portrait-64-v15-appearance/visual_review.json`: qualitative limits.
- `models/cael-portrait-64-v15-appearance/verification.json`: hashes and checks.
- `research/portrait_appearance_v14_a/`: eye-alignment/rendering experiment.
- `research/portrait_deformation_v15_a/`: registered appearance experiment.
- `research/portrait_latent_ca_v16_a/`: unpromoted appearance-factor CA experiment.

Checkpoint SHA256:
`e13d03ef52589535b03cfda8181b82e6903b345dcbe72639c109d27b6a9389d7`.
