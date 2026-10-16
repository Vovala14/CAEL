# CAEL 0.2.1

**One assistant, one model bundle: chat, helpers, emoji, portraits and small
general pictures.** The release routes between existing CAEL engines and the
new subject-conditioned image experiment. It is one portable archive, not a
single jointly trained neural model.

## Start

Use Python 3.11 or later. Runtime works on CPU; no image service, teacher
checkpoint or private training folder is needed.

```bash
git clone https://github.com/Vovala14/CAEL.git
cd CAEL
python -m pip install -r requirements-unified.txt
python -m cael_unified --download
python -m cael_unified --ui
```

Open **http://127.0.0.1:8765**. On Windows, `SETUP.bat` installs dependencies
and downloads the checksum-verified bundle; `RUN.bat` starts the local UI.
The portable release ZIP includes `models/cael-0.2.1.cael`.

```bash
python -m cael_unified "Calculate (12 + 3) * 4"
python -m cael_unified "Make an emoji of fire" --seed 42
python -m cael_unified "Make a picture of a car" --seed 42
python -m cael_unified "Create a portrait of an adult woman" --seed 42
```

Images are saved under `outputs/unified/`. True resolution is **64×64**;
the UI enlarges them. `--mode chat`, `--mode emoji` and `--mode image` override
automatic routing. `--json` returns structured results and paths.

```python
from cael_unified import Assistant

assistant = Assistant()
result = assistant.respond([{"role": "user", "content": "Make a picture of a bicycle"}], seed=42)
print(result["response"], result.get("paths"))
```

## Model components

| Component | Implementation | Limits |
|---|---|---|
| Chat | Legacy CA routing/small-talk models and a small factual store | Limited fallback; current remote worker absent |
| Helper | Exact bounded arithmetic, existing authored writing programs, story/event memory | Handwritten task programs; no general tool execution |
| Emoji | v7 integer patch CA, silhouette guidance, speckle cleanup | Finite vocabulary; unfamiliar words may be ignored; offline |
| Portrait | v15 registered shape/appearance statistics | Unconditional adult-woman portraits; averaged faces and artifacts |
| General picture | Subject-conditioned statistics based on portrait code | 32 categories; rough images; no arbitrary composition or learned colour/style controls |

General subjects: **car, bicycle, motorcycle, truck, airplane, boat, phone,
laptop, camera, headphones, watch, robot, woman, man, dog, cat, horse, bird,
dragon, flower, tree, house, city, mountain, beach, forest, pizza, burger, cup,
chair, shoe and spaceship**. Aliases such as "bike" and "smartphone" work.
Multi-category or unseen subjects return the supported vocabulary rather than
pretending the requested composition was learned.

The eight stored emoji entries (harp, hedgehog, kiwi bird, lighthouse, make,
saxophone, snowflake and tractor) are retained for offline reuse, with their
original source attribution. Reference-derived outputs carry attribution and,
where applicable, CC BY-SA terms in `attribution.json` beside the images.

The latest chat worker and web lookup run on another computer and were not
available here. This release includes a working portable legacy fallback and
preserves older v6.7 source in `chat_v6_7/`; its optional large stores still
require rebuilding. It does **not** contain the missing remote worker or private
credentials. Offline chat has no live web lookup.

## General-image training

The student reuses portrait registration and appearance code. Data come from
**local neural Stable Diffusion 1.5 generation**, not the private portrait
collection. Runtime sampling uses statistical modes and deformation fields,
without the teacher. Do not describe this as "no neural networks in training."

The first curriculum contains 1,024 synthetic images, 32 per subject. Pixel
groups are split before fitting and held-out groups are protected across all
categories. Models learn from fitting images only. Frozen results and
generated-only examples are under `results/general-0.2.1/`.

Install `requirements-training.txt`, start a local `stable-diffusion.cpp` server
with an SD1.5 checkpoint, and run:

```bash
python cael_image/generate_general_dataset.py --out research/general_synthetic --model-sha256 CHECKPOINT_SHA256
python cael_image/train_general_appearance.py --dataset research/general_synthetic --out models/general-reproduction
```

The generator accepts only localhost and resumes frozen batches. It records
prompts, seeds, settings and hashes. Training images are processed in code;
source previews are not produced.

## Privacy and evaluation

No private source photo, private alignment record, credential or teacher
checkpoint ships. Portrait weights contain aggregate learned statistics.
Emoji guard references are public Noto/Blobmoji pixels; general-image guard
references are synthetic fitting pixels. These support numerical rejection and
emoji shape statistics, not retrieval as finished photo outputs.

Stored learned emoji entries additionally include their licensed OpenMoji,
Twemoji, Emojitwo, Fluent and Commons references. Their separate terms and
credits are preserved in the bundle and `licenses/LEARNED-EMOJI-NOTICE.md`.

The original portrait guard needs private source photos, which are not
redistributed. Public portrait generation checks only against synthetic
references, not private portraits. This does not guarantee anonymity or absence
of memorization. The synthetic-image cutoff is 0.04; portrait sampling retains
a 0.12 cutoff against public references. Neither similarity nor synthetic
category separation measures realism.

```bash
python -m unittest discover -s tests -v
```

Tests cover story memory, routing, arithmetic, subject matching, bundle/cache
integrity, path traversal and the local HTTP boundary. Original Story 0.1
training and evaluation remain: [documentation](STORY_MODEL.md),
[model card](STORY_MODEL_CARD.md).

## Licenses

CAEL code and owned modifications retain the [non-commercial license](LICENSE)
and [provenance notices](NOTICE.md). Public emoji references retain Apache and
Unicode notices. Synthetic-data-derived general-image weights are also subject
to [CreativeML OpenRAIL-M](licenses/LICENSE-stable-diffusion-v1-5.txt), including
paragraph 5 and Attachment A. Those restrictions apply to use and redistribution
of these weights and downstream derivatives. Notices are inside the bundle.

This first general-image model is a limited experiment. It cannot generate
everything a modern diffusion model can, or promise photorealistic outputs.
