# CAEL 0.2.4

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
`--download` fetches `models/cael-0.2.4.cael` (about 1.1 GB), verifies every file
and installs its model folders under `models/`. It also records the reviewed model
selections in `research/active_models.json` unless that file already exists.

## New in 0.2.4

Every engine is still non-neural at runtime.

- **Pictures, rebuilt (image model 0.4.3).**
  - **Training data:** 22,110 local Stable Diffusion 1.5 renders across 114 subjects, including 2,400 varied
    head-and-shoulders portraits.
  - **One structure per picture:** each picture takes its shape from one real render, bent into a new pose,
    with the texture rebuilt from two sources. The old two-source mixing produced two-headed or broken
    subjects; this doesn't.
  - **Rigid things:** cars, chairs, phones and houses are never bent. They're mirrored, shifted, scaled and
    repainted on the bodywork only, with tyres, glass and chrome kept.
  - **Other improvements:** best of 8 sketches, a 256-pixel detail pass, seam blending, and photo style unless
    you ask for an illustration.
  - **Copy check:** every picture must stay at least 15 RMSE away from any single training render, measured at
    64 px and including mirror images. This is a deliberate trade of novelty for coherent shapes; previously
    the floor was 25.
  - See [IMAGE_HYBRID_0_4_3.md](IMAGE_HYBRID_0_4_3.md).
- **Faces.**
  - Portrait requests use the main model.
  - Faces are landmark morphs of three similar-looking people, using 68 facial landmarks found offline with
    OpenCV LBF. OpenCV isn't needed at runtime.
  - The result is varied, coherent faces with no smeared or doubled features.
- **Picture requests understand more:** new subjects and backgrounds (mouse, fox, wolf, deer, dolphin, desert,
  snow, sky, ocean, park, field, room), and "make a portrait of a man" right after another picture starts a
  new picture.
- **Prompt helper:** "make image of a dog" becomes a detailed, ready-to-use image prompt. CAEL keeps your words
  and adds subject detail, setting, light, framing and finish suited to the subject; things to avoid are
  listed separately.
- **Vynly helper:** CAEL answers questions about vynly.co (posting, provenance, Sparks, Trails, agents, account,
  privacy, rules), each with a link to the page. Its knowledge comes from the public site and owner-approved
  documents. A server-side site proxy can mark its requests with the `site_proxy` setting.
- **Chat and helper:** negated feelings ("I don't feel so good") get sympathy instead of cheer. The fallback no
  longer guesses emotions. Spelling repair, quantities, rates, groups, source-quality and factual-boundary work
  is included (see [CHAT_HELPER_0_4_6.md](CHAT_HELPER_0_4_6.md)).

## New in 0.2.3

Every engine is still non-neural.

- **Reasoning with "or" and contradiction.** Premises become true/false constraints
  and a small SAT solver checks every case. It covers "Rex is a cat or a dog",
  "No mammal is a fish", "Birds can fly" and contradictory premises.
  - PrOntoQA test: **99.34%**, up from 70.3%.
  - All 20 bAbI story tasks are supported: **99.82%** on the test split, up from 12
    task types. That includes pronouns, time order, analogy, positions, compass
    directions and motivations.
  - See [REASONING_0_4_2.md](REASONING_0_4_2.md).
- **Reasoning answers in chat.** Answers are full sentences followed by the numbered
  premises they rest on. Guesses are labelled as guesses, and contradictory premises
  are reported.
  - It accepts natural wordings such as "Does it follow that…".
  - Ordinary messages that only look like puzzles go to normal chat.
- **Reasoning about pictures.**
  - Several objects per picture, placed as asked: left/right of, between, on, above,
    under, in front of, behind.
  - Sizes follow real life, so an elephant is drawn larger than a cat.
  - Subjects can be described indirectly: "the animal that says moo" draws a cow, "a
    poodle" draws a dog, "a yellow fruit" draws a banana. Each choice is explained.
  - Follow-ups edit the last picture: "make it blue", "add a dog to the left of the
    sofa", "put them on a beach", "remove the cat".
  - It says plainly what it cannot draw and when a request breaks common sense.
  - See [IMAGE_REASONING_0_4_3.md](IMAGE_REASONING_0_4_3.md).
- **Multiple-choice questions in chat:** the count language model, local evidence
  retrieval and an exact word-problem solver work together. Local Open SLM Leaderboard
  tests: five-test mean 49.97%, against 32.69% before. ArithMark-3 scores 69.5%,
  against 59.6% for SmolLM2-360M. See [LEADERBOARD_0_4_1.md](LEADERBOARD_0_4_1.md).
  This is not an official leaderboard entry. The optional ARC Corpus index is not
  bundled.

## New in 0.2.2

Every engine is still non-neural (no neural networks or transformers at runtime).

- **Pictures:** a new hybrid image model with **102 topics**. A per-topic PCA layout
  is filled in by patch synthesis from two same-style training renders, at 128×128.
  It understands colour, style (photo, illustration, side view), count (up to three)
  and scene in a request. Colour, count and scene edits are experimental. See
  [IMAGE_HYBRID_0_3_9.md](IMAGE_HYBRID_0_3_9.md).
- **Teaching answers:** "explain the rules of chess", "how do I make bread" and "how
  does a jet engine work" are answered from the relevant sections and lists of the
  matching Wikipedia article, not a one-line definition.
- **Conversation:** authored small-talk rules (greetings, thanks, feelings, questions
  about CAEL) and memory of facts said earlier in the same chat window ("where do I
  live?"). Factual questions it cannot verify get an honest "I cannot answer that"
  instead of small talk.
- **Lookup fixes:** misspelled subjects ("megadeath"), founding dates anchored to the
  right entity, weather for remembered or misspelled places.
- **Python from examples:** describe a small function and give two or three examples
  (`double(2) == 4`). CAEL searches over small Python operations for code that fits.
  See [CODE_SYNTHESIS_0_3_8.md](CODE_SYNTHESIS_0_3_8.md) for the held-out results
  and limits.
- **Language, knowledge and creative models** from the 0.3.x research runs, as
  selected for the live assistant (count language 0.3.2, local knowledge, story and
  prompt writer 0.3.7-r2).

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
| Picture (0.2.4) | Hybrid 0.4.3: one real structure per picture, texture rebuilt from two SD1.5 training renders; landmark face morphing; scene reasoning composes cut-outs | 114 topics; pictures can stay recognisably close to one training render (copy floor 15); multi-object scenes look rough; most cars are grey/silver (training data) |
| Reasoning | Rule chaining, SAT case analysis, event/position/time tracking | Simple sentence forms ("X is a Y", "Every X…", "X went to the Y") |
| General picture (0.2.1) | Subject-conditioned statistics based on portrait code | Fallback only; 32 categories; rough images |
| Explanations | Section selection from the matching Wikipedia article | Quoted text (CC BY-SA); encyclopedic, not recipes |
| Code | Example-guided search over small Python operations | One-line functions; needs examples |

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
