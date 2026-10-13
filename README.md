# CAEL — Cellular Automaton Event Language

**CAEL Story 0.1 is a small, non-neural hybrid for constrained stories and event memory.**

It generates stories about a defined set of characters, objects and goals, then
answers supported factual questions about the resulting world. It can also keep
world state across a sequence of events through its Python API.

CAEL is a **separate model family from MICA**. Its handwritten English parser,
authored world schema and template-like grammar are intentional parts of this
hybrid. It is neither a general chatbot nor the original pure MICA architecture.

## Try it

Python 3.10 or later and NumPy are required. CPU only; no model service or GPU.

```bash
git clone https://github.com/Vovala14/CAEL.git
cd CAEL
python -m pip install -r requirements.txt
python chat.py "Tell me a story about a dog helping a bird find a lost ball." --ask "Who found the ball?" --ask "Who has the ball?"
```

Example factual answers:

```text
The dog found the ball.
The bird has the ball.
```

Run `python chat.py` for the interactive interface, or use `--seed 42` to vary
the learned grammar choices reproducibly. A new story resets the world by default.
Requests outside the closed interface are rejected.

### Cumulative event memory

```python
from cael import CAEL

model = CAEL()
# Slot IDs index actors/objects/places in model.model.
share = dict(a=0, b=1, i=0, p=1, s=0, intent="share")
find = dict(a=2, b=3, i=1, p=2, s=0, intent="find")
model.story_frame(share)                  # Cat gives ball to dog.
model.story_frame(find, reset=False)      # Rabbit finds another object.
print(model.ask("Who has the ball?")["response"])
# The dog has the ball.
```

This structured API accepts labelled frames. It does not imply that CAEL can
parse arbitrary English event streams or carry out general reasoning.

## Architecture

```text
English request
  → handwritten closed parser
  → learned integer event-plan transitions
  → radius-one cellular entity-memory updates
  → learned regular grammar + handwritten slot formatting
  → story / supported factual answer
```

- Entity cells hold integer ownership, location, finder, helper and status fields.
- Event packets move to immediate neighbors; updates read the previous state.
- Training learns integer field-copy programs from labelled teacher transitions.
- A cellular planner follows learned event transitions.
- A cellular grammar packet follows learned terminal/slot transitions.
- No neural network, external language model, embeddings or full-answer retrieval
  is used. The finite ontology, opcode vocabulary, plan examples, phrase templates
  and parsing rules are supplied by the author.

The first variant has **180 learned entity-update rules**, **486 grammar states**,
12 characters, 14 objects, 8 places, 8 goals and 4 skills. Its model JSON is
**77,300 bytes**. That size excludes Python, NumPy and source code.

## Results

Trained on **30,000 unique synthetic frames + 5,000 cumulative episodes**, using
279,314 labelled event instances. Training took about 30 seconds on the development
CPU; hardware and load affect timings.

| Authored-schema evaluation | Earlier symbolic prototype | CAEL Story 0.1 |
|---|---:|---:|
| Cumulative development episodes without missing rules/state errors | 172/200 | **200/200** |
| Cumulative confirmation episodes without missing rules/state errors | 169/200 | **200/200** |
| Single-story plan/state trajectories | — | **4,000/4,000** |
| Supported single-story factual queries | — | **13,029/13,029** |

The cumulative comparison uses identical event streams. The candidate has zero
measured state mismatches or missing-rule failures in those 400 sequences. Eleven
structural/interface tests also pass, including local updates and session isolation.

**These are synthetic, closed-domain program/state tests against the same authored
world semantics. They are not ToM, a general language benchmark or evidence of
human-level understanding.** Of 20 historical natural prompts, 18 are supported
and 2 are rejected; support is not a new independent quality rating. All raw
outputs, hashes and protocol are included under [results](results/cael-story-0.1)
and in the [report](REPORT.md).

## Reproduce training and evaluation

The released checkpoint and frozen baseline are included. No data download is
needed. Training creates synthetic data under the ignored `research/` folder.

```bash
python train.py --out models/reproduction
python evaluate.py --model models/reproduction/model.json --out results/reproduction
python -m unittest discover -s tests -v
```

Training refuses to overwrite an existing model. Default seed and dataset sizes
are fixed in `train.py`. Splits use canonical semantic-frame hashes; training,
development and confirmation frames are disjoint. Related irrelevant slot values
cannot manufacture novelty. Supported natural-prompt frames are excluded from
training. See [PROTOCOL.md](PROTOCOL.md) and [MODEL_CARD.md](MODEL_CARD.md).

## Current limits

- Only the declared characters, objects, places, goals and question forms work.
- English parsing and formatting are handwritten; the grammar is template-like.
- Generated phrasing is repetitive and represents a small taught world.
- Cumulative state is exposed through the structured API; natural-language story
  requests still start a fresh world.
- There is no learned broad knowledge, general instruction following, arbitrary
  event-language understanding, belief reasoning or open-ended conversation.
- The teacher also supplies evaluation semantics; external evaluation remains
  needed. No claim that CAEL is the first or only system of its kind.

## Family and license

The family is **CAEL**; this first variant is **CAEL Story 0.1.0**. Future variants
must report their scope and architecture separately.

Code and model are available for **personal and non-commercial research use**
under the preserved [license](LICENSE). This is not an OSI open-source license.
See [NOTICE.md](NOTICE.md) for provenance and required attribution to
[MICA Ember / MICA Flame by Vovala14](https://github.com/Vovala14/Mica-Ai).
