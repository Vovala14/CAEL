# v18: retraining with 38 accepted older photos

Candidate checkpoint: `models/cael-portrait-64-v18-older-fit/model_v18.pt`.

The registered statistical portrait generator was refitted on 163 eye-aligned
photos: all 125 used by v17 plus all 38 accepted older alignments. Two fitted
populations contain 62 and 101 images. Rank, variation, sharpening and warp
strength were unchanged. Population initialization used v17 aggregate templates.
This is the existing non-neural shape/appearance branch, not a retraining of
the original i16 cellular model or a pretrained neural generator.

All 52 current validation files and 177 available older validation-related
files were protected. File hashes and decoded 64x64 pixel hashes were checked
across both sources before fitting; no accepted image was removed by these
checks. Existing fitting images were retained once each. The guard references
include the newly added older photos both before and after eye alignment. No
private source photo, crop or alignment preview was viewed, saved or uploaded.
Training reads source pixels blindly in local memory.

After freezing the protocol, 32 generated samples from each of v15, v17 and
v18 used the same new seed schedule and common fitting-only similarity guard.
Every generated sample is retained. The comparison shows the fixed first eight
from each model, in order; no attractive subset was selected.

| Diagnostic | v15 | v17 | v18 |
|---|---:|---:|---:|
| Pairwise RGB L1 diversity | 47.4371 | 43.3187 | 42.1476 |
| Edge density | 0.0991 | 0.0731 | 0.0559 |
| Minimum nearest-fitting RMS | 0.172713 | 0.142500 | 0.154653 |
| Similarity-guard replacements | 0 | 0 | 0 |

The frozen numeric checks passed, but they do not measure face quality.
Same-author review of the generated comparison and complete v17/v18 grids
found no clear overall improvement: v18 is generally blurrier, with more
averaged facial features, residual eye artifacts and similar identities.
This is qualitative development evidence, not an independent realism benchmark.
The older historical identities remain uncertain because only filename-based
copies were available, as documented in the older preprocessing run.

The v18 checkpoint remains a separate experiment. The v15 CLI default, live
i16 UI, release directories, original photos and earlier checkpoints were not
changed. All 45 software tests passed. CPU CLI generation from the reloaded
checkpoint exactly matched the first four generated comparison samples in the
same PyTorch runtime and fixed batch schedule.

Artifacts alongside the checkpoint include `protocol.json`, `alignment.json`,
`additional_training_manifest.json`, `report.json`, `verification.json`,
`visual_review.json`, the complete generated grids and individual 64x64 outputs.

Generate into a new output directory:

```powershell
& ..\.venv-rocm\Scripts\python.exe cael_assistant\portrait_appearance_cli.py --model models\cael-portrait-64-v18-older-fit\model_v18.pt --out outputs\portrait_v18_example --seed 42 --n 4
```

Reproduce the fit into a new directory:

```powershell
& C:\Python314\python.exe -u cael_image\train_portrait_combined_appearance.py --older-run research\portrait_older_alignment_retry_20261016_085425 --out models\cael-portrait-64-v18-repeat
```
