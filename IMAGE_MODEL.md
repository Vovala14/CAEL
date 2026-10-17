# CAEL Image — female-character 64×64 research branch

The image option and training pipeline are prepared. **No character model is bundled.** The existing CAEL text models do not already know how to draw; this option requires a separate image checkpoint trained from your folder.

Stage one accepts and produces **64×64** images. It is a **non-neural hybrid layout prior and integer cellular baseline**, with learned coarse shapes, categorical color/neighbor tables and caption words. It is not a Stable Diffusion wrapper, neural CA, or external image service. Female-character specialization comes from your images and captions; it is not a pretrained capability.

## v2 correction after the first real run

The first local v1 run produced unusable previews. Sparse neighbor evidence could overpower the color prior and collapse to fluorescent colors, even without noise. Color histograms also lacked a coherent face/pose layout. The teacher-forced pixel score did not establish usable image generation.

v2 uses averaged nonpositive neighbor evidence, annealed sampling noise, and a **learned coarse layout prior**. Offline k-means groups training-only 16x16 thumbnails, merges small clusters and stores their means. Caption-word counts select a coarse layout. Integer interpolation supplies a local shape-conditioning field to the cellular pixel refiner. This is a non-neural **hybrid layout prior plus CA**, not pixel-local rules alone learning all geometry. Stored layouts are low-resolution means, not full source images.

The v1 checkpoint is preserved. The updated config writes to **`models/cael-image-female-64-v2`**; your dataset path stays as entered. **v2 quality is unvalidated until you train and inspect it.** The stable sampler removed green collapse in the inspected v1 diagnostic, but the result remains a blob. `--sampler legacy` reproduces the original sampling when explicitly used with a v1 checkpoint.

## 1. Add your folder path

Edit **`train_image_config.json`**, replacing only this placeholder first:

```json
"dataset_dir": "D:/YOUR_DATA/female_characters_64"
```

Use forward slashes in JSON, or escape Windows backslashes. Relative paths are resolved against the config file's directory, not the terminal's working directory.

Use matching UTF-8 `.txt` captions next to each image:

```text
female_characters_64/
  character_001.png           # exactly 64x64
  character_001.txt
  character_002.png
  character_002.txt
```

Example caption:

```text
female character, black hair, blue dress, front view, standing, pale background, pixel art
```

Describe visible attributes consistently: hair, clothing, pose, framing, background and style. Keep captions distinct where the images differ. PNG/JPEG/WebP/BMP and nested folders are supported. Every image needs a nonempty matching caption. Transparency is composited over white. Wrong image sizes are rejected by default; explicitly setting `resize_mode` to `fit` enables a centered crop/resize to 64×64. Consistent composition and a coherent style are useful for this limited model.

## 2. Install and validate

From the CAEL folder:

```powershell
python -m pip install -r requirements-image.txt
python -m cael_image.train --config train_image_config.json --dry-run
```

The dry run validates files/captions, makes a deterministic duplicate-safe split, derives vocabulary from the training split only and estimates RAM. It **does not train or create model files**. Your source folder is read only.

## 3. Start training yourself

```powershell
python -m cael_image.train --config train_image_config.json
```

Or use the Windows launcher:

```powershell
.\train_images.ps1 -DryRun
.\train_images.ps1
```

If your Python is in a specific virtual environment:

```powershell
.\train_images.ps1 -Python 'C:/path/to/venv/Scripts/python.exe'
```

This is a **one-pass count/program fit**, not gradient training. There is no meaningful epoch count: repeatedly adding the same images mainly repeats counts, rather than learning new concepts. Add useful new captioned images and choose a new `output_dir` to fit a later candidate. An existing nonempty run folder is preserved. Interrupted runs report failure; automatic resume is not implemented.

Layout defaults are 32 clusters, 16x16 coarse shape means, 12 offline clustering iterations, minimum 8 images per cluster, and integer layout weight 8. These are distinct from neural epochs. Defaults use CPU, 256 caption words, an 8×8 conditioning grid, 10% validation, and 256 fixed RGB332 colors. `max_vocabulary` can be increased for more learned attribute words at a RAM cost. `min_token_images` controls how many training images must mention a word. If none qualify, the script stops with a clear message. The preflight reports storage and a rough peak-memory estimate. No GPU or PyTorch is required.

The output folder (default `models/cael-image-female-64-v2`) contains:

- `model.npz`: integer inference tables, palette and metadata, no source images.
- `data_manifest.json`: input/caption/pixel hashes, complete train/validation records and source-code hashes.
- `training_report.json`: checkpoint SHA, size and held-out local diagnostics.
- `status.json`: fitting, validation, finished or failed.
- Optional 64×64 generated previews with their captions/seeds in JSON.

Identical decoded RGB images remain in the same split even if their filenames/captions differ. This does not detect near-duplicate images. Validation is not used to fit tables or vocabulary. Metrics are capped by `validation_max_images`, and the evaluated/skipped filenames are listed. Local metrics supply **ground-truth neighbor pixels**: their pseudo bits/color and palette accuracy are not image quality, actual generative likelihood, compression performance or prompt-following accuracy. Inspect the generated previews separately.

## 4. Generate after training

```powershell
python chat.py 'female character, black hair, blue dress, front view, pixel art' --image --model models/cael-image-female-64-v2/model.npz --output outputs/character_001.png --seed 42
```

Standalone equivalent:

```powershell
python -m cael_image.generate 'female character, black hair, blue dress' --model models/cael-image-female-64-v2/model.npz --output outputs/character_002.png --seed 8
```

Optional `--steps 64` and `--noise 24` control cellular updates and integer sampling noise. Zero noise is deterministic; fixed model/prompt/seed/settings reproduce pixels. Results are exactly 64×64 PNG, with a JSON sidecar containing matched/unmatched words, layout ID, sampler, settings and model SHA. Existing image/metadata files are preserved: choose a new filename for another sample. Unknown-only prompts are rejected; unmatched words in otherwise recognized prompts are recorded, not silently presented as understood.

## Architecture and realistic limits

```text
Caption words → learned coarse layout + local position/color evidence
             → seeded 64×64 categorical color grid
             → synchronous radius-one integer cell rewrites
             → RGB332 palette → 64×64 PNG
```

Training fits coarse cluster means, then counts colors at each position, caption-conditioned colors in spatial bins, and directed adjacent color pairs. Floating-point logarithms compile those statistics into quantized integer lookup scores. Inference uses integer additions, table lookups, neighboring old cell states, checkerboard phases, argmax and a precomputed integer noise table. Each cell has a static coordinate/text-conditioning field; there is no nonlocal attention, convolutional neural layer, backpropagation or learned text embedding. The authored tokenizer and color quantizer are explicit hybrid components. This is a new 2D image branch, not the original MICA byte/word engine.

**This is an unvalidated research baseline.** It may learn broad layouts/colors/textures while failing faces, anatomy, pose, compositional requests and consistent identity. It has bag-of-words conditioning, not full English semantics, and no negative-prompt interface. More data alone does not guarantee convincing characters. No realism, likeness, diversity or instruction-following score is claimed. The fixed 256-color palette limits fidelity; outputs are not upscaled. Future improvements require real held-out images and human review after you train it.

Implementation references: [Pillow image I/O](https://pillow.readthedocs.io/en/stable/reference/Image.html), [NumPy loading without pickle](https://numpy.org/doc/stable/reference/generated/numpy.load.html). Neither supplies a pretrained model.
