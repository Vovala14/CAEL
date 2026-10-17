# v13: visible progress in face structure

Later continuation: [v15](PORTRAIT_V15.md) produces cleaner, clearer portraits
using registered statistical appearance and continuous rendering. It is a
separate non-neural branch that replaces the pixel CA renderer; v13 is preserved.

Saved checkpoint: `models/cael-portrait-64-v13-structure/model_v13.pt`.
This candidate produces recognisable eye/nose/mouth arrangements that were
largely absent from v12. It remains blurry, grainy and sometimes distorted;
photorealism and reliable prompt control have not been achieved.

The experiment stopped after visible progress and verification, within the
30-minute bound. No private source image or source crop was displayed. Only
generated portraits were visually inspected. All source image hashes and the
v12 checkpoint hash were verified unchanged; releases remain untouched.

## What changed

v13 is a **non-neural statistical whole-face prior plus count-based cellular
sampler**. It is not a purely local CA learning geometry by itself. No neural
network, backpropagation, pretrained image generator or external service is used.

The existing v12 training manifest contains 470 fitting photos and 52 excluded
evaluation photos. A classical Haar detector identified faces in 192 fitting
photos, which were aligned blindly in code. These 192 fitting faces train three
statistical populations, containing 60, 65 and 67 photos. Each population stores
an aggregate mean and eight principal-component variation directions. No source
photo, patch bank or individual source coefficient vector is stored by this
prior.

Generation samples a population and random variation coefficients. One complete
Lab structure field persists through scales 4, 8, 16, 32 and 64. The inherited
v12 cellular count rules sample/refine colours with this field as guidance. The
selected sampling mix is 0.95 structure mass before temperature, bandwidth 6
Lab units, variation 0.85. The old independent position prior and separate
brightness tilt are not applied in this sampler. Existing v12 rules and palette
are embedded unchanged in the checkpoint.

An unquantized PCA control already produced recognisable faces. This establishes
that the whole-face prior supplies the main structural improvement; the cellular
sampler quantizes/refines it and adds visible grain. Alignment and the new
statistical prior changed together, so the experiment does not isolate their
individual contributions. The earlier patch-only experiments were reviewed:
their numerical texture checks could pass despite diversity loss and poor faces.

## Generated-output evidence

Development used 16 fixed generated samples per variant: v12, a PCA control,
and two strengths of structural CA guidance. The stronger guide was selected
from generated portraits, with no source-image viewing or held-out fitting.

The first new-seed check generated 32 samples. Diversity remained high, but
one sample missed the preset nearest-source RMS cutoff of 0.12 (minimum 0.1144).
That failed result is retained in
`research/portrait_structure_v13_confirmation/`; the cutoff was not relaxed.

A numerical rejection/resampling rule was then added. It compares outputs with
the 470 fitting photos under the base preprocessing and the 192 aligned fitting
crops, transiently in memory. References are used only to reject samples, not
to synthesize pixels or retrieve replacement images. Up to eight retries are
allowed; an exhausted guard raises instead of returning rejected outputs.
This distance rule is a heuristic, not proof of privacy or absence of likeness.
Original i16 source photos outside this folder were not audited.

With that rule frozen, a further 32 generated samples used new seeds:

| Diagnostic | v12 | v13 |
|---|---:|---:|
| Pairwise RGB L1 diversity | 51.7997 | 45.3554 |
| Edge density | 0.2499 | 0.1810 |
| Minimum nearest-fitting RMS | 0.2095 | 0.1219 |

All 32 passed the distance cutoff without resampling on these particular seeds.
The earlier failing seed was separately replayed through the saved model: one
sample was rejected/resampled and the returned batch passed the cutoff.

Conservative same-author, nonblind review of the fixed **first 16** final
samples found a recognisable complete eye/nose/mouth arrangement in 11 v13
outputs versus 0 v12 outputs. Five v13 cases failed due to shadow, blur,
stretching or doubled features. The other 16 generated samples receive no
numerical visual-quality credit. This is a limited development screen, not an
independent accuracy estimate, identity test or realism benchmark. Per-case
reasons and output hashes are saved in `visual_review.json`.

`comparison.png` shows the fixed first eight outputs: v12 above, v13 below.
There was no selection of attractive examples from the batch.

## Use the saved candidate

From the CAEL project directory:

```powershell
& ..\.venv-rocm\Scripts\python.exe cael_assistant\portrait_structure_cli.py --out outputs\portrait_v13_example --seed 42 --n 4
```

Choose a new output directory each time. True outputs are 64x64; preview grids
use nearest-neighbour enlargement. Sampling is CPU-only with fixed four-image
batches. Model weights are self-contained, but guarded inference needs the
unchanged local fitting photos for blind numerical comparisons. The CLI does
not display those photos and does not accept caption prompts; this version
focuses on unconditional face structure.

The running web assistant remains on its previous i16 route. v13 is available
through the separate CLI, preserving existing colour-steering behaviour in the
live assistant until that interface is adapted explicitly.

## Verification and artifacts

All **37 software tests passed**. Checks cover deterministic aggregate-prior
sampling, finite structural probabilities, exact compact CA lookups, continued
holdout exclusion, rejection/resampling and failure without returning a rejected
batch. The actual saved checkpoint reloaded, reproduced seed-42 pixels exactly,
and successfully handled the previously rejected real seed.

- `models/cael-portrait-64-v13-structure/report.json`: frozen generated diagnostics.
- `models/cael-portrait-64-v13-structure/visual_review.json`: first-16 review.
- `models/cael-portrait-64-v13-structure/verification.json`: hashes and reload checks.
- `models/cael-portrait-64-v13-structure/comparison.png`: generated before/after.
- `research/portrait_structure_v13_a/`: development outputs, controls and structure fit.
- `research/portrait_structure_v13_confirmation/`: retained first distance-check failure.

Checkpoint SHA256:
`43c37d6198395015f5f22e5031bcf92af4276490e8ce89d24a2b8d1bc6527ba3`.

The next useful work is reducing grain and ghosting while retaining this
structure and diversity. Additional photos are not needed for that next step.
