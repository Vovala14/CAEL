# Reasoning about picture requests (0.4.3, released in CAEL 0.2.3)

On 2026-10-18 the owner asked to bring the text reasoner's logic to pictures. Before this, a picture request was read
as a single subject:
- "a cat next to a dog" drew only a cat.
- "a poodle" and "the animal that says moo" were rejected.
- "make it blue" after a picture went to the weather lookup.

Everything here is authored code and an authored knowledge table. No neural network or learning is involved.

## What it understands

| Request | Reading |
| --- | --- |
| "a red car to the left of a tree" | car (red) left-of tree |
| "a dog between a cat and a horse" | cat, dog, horse, left to right |
| "a cat on a sofa", "a man riding a horse", "a bird above a house" | stacked in one column |
| "a car on the left and a tree on the right" | anchors, not "on top of" |
| "a cat to the left of a dog and the dog to the left of the cat" | "the dog" is the same dog; the contradiction is reported and the second placement ignored |
| "a big elephant and a small cat" | real sizes (square-root scaled), adjusted by big/small |
| "a poodle", "a kitten", "a dolphin" | kind of dog; cat; closest stand-in, a whale, said explicitly |
| "the animal that says moo", "a yellow fruit", "an animal with a long neck", "the biggest animal" | cow, banana, giraffe, whale; each choice is explained |
| "a car that is not red" | if the drawing comes out red, it is recoloured |
| "a fish in the sky", "a penguin in the desert" | drawn as asked, with a note; no desert background yet, said so |

Follow-ups edit the conversation's last picture. The picture is rebuilt by replaying the requests that made it, so
nothing is stored between messages. Supported edits:
- colour
- add, optionally with a placement relative to an existing object
- remove
- replace
- move or swap
- bigger or smaller
- style
- count
- background
- draw again

Two-part requests ("make the cat orange and add a dog to the left of the sofa") apply both parts in order.

## How it is drawn

- **Layout:** a solver like the text reasoner's 2-D position solver.
  - on/above/below/front/behind put objects in one column.
  - left/right/between give an order of the columns. A placement that would make a cycle is rejected and reported.
  - Sizes come from typical real-world sizes in `cael_image/concepts.py`.
  - Flying things go to the sky when the scene has ground objects.
- **Drawing:** each object is drawn by the 102-topic hybrid model, cut out with its training-image mask, recoloured if
  asked, and pasted onto a background topic or a plain backdrop.
- **Single objects:** a single object with no placements still uses the earlier single-subject path, so its quality is
  unchanged.

## Limits

- The composed scenes look rough: cut-out edges are patchy, and lighting and scale perspective are not matched.
- People are head-and-shoulders portraits only, so they look odd in scenes.
- There are 102 topics. Backgrounds are limited to beach, city, forest, mountain, waterfall, volcano and castle.
- There are at most 3 of one thing and 6 objects per picture.

## Tests

- `tests/test_image_scene.py` has 14 tests: parsing, coreference, contradictions, anchors, layout order and sizes,
  stacking, edits, and the follow-up detector. It also draws a real scene with a toy model.
- The full suite passes: 280 tests, 1 skipped.
