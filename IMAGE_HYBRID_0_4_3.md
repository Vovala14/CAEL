# Hybrid image model 0.4.3 (released in CAEL 0.2.4)

## What changed since 0.3.9

| Step | Result |
| --- | --- |
| 0.4.0: more data (10,260 overnight renders, 114 topics) | recognised 58.3% → 64.0% on the shared topics; pre-set rule passed |
| 0.4.1: best of 8 sketches + 256 px detail pass + seam blending (packed JPEG detail images, 909 → 410 MB) | all 114 topics: recognised 64.3% → 73.0%, sharper, closer to real photos; rule passed |
| Photo style by default; stricter copy check (64 px, mirrors counted, farthest attempt kept) | development topics: recognised 80.6% → 84.5%, fidelity 5.27 → 5.03 |
| 0.4.2: landmark face morphing for head-and-shoulders portraits | coherent faces instead of mixed patches |
| 0.4.3: 22,110 renders including 2,400 varied portraits (873 with landmarks) | faces far more varied; failed the strict rule overall (recognised 69.2% → 66.3%) |
| **Option C, chosen by the owner**: one real structure per picture, copy floor 15; rigid objects repainted, never bent | clean shapes in every topic (see `research/image_hybrid_043/options.png`) |

## How a picture is made now

1. Pick a training render close to a sampled layout, in the style asked for (photo by default).
2. **Living things:** bend it with a smooth random warp, sometimes mirrored, into a new pose.
   **Rigid things** (vehicles, furniture, devices, buildings): mirror it, shift and scale it slightly, and give it
   a new paint colour on the bodywork only. Paint is applied only to pixels near the body's own hue, so floors,
   shadows, tyres, glass and chrome keep their colour; grey or silver bodies keep theirs.
3. Rebuild the texture coarse-to-fine from two similar renders, following that structure. Keep the best of 8
   sketches (least ghosting relative to detail). Add detail at 256 px and blend the seams.
4. **People's portraits:** morph three similar-looking people through 68 facial landmarks.
5. **Copy check:** at least 15 RMSE (0–255 scale, compared at 64 px, mirrors included) from every training
   render. Otherwise redraw; after three tries, keep the most different attempt.

## Honest limits

- Pictures can be recognisably a reworked version of one training render. The owner accepted this trade for
  coherent shapes. The copy floor was lowered from 25 to 15 on purpose.
- Most cars and many objects come out grey or silver, because the training renders are mostly studio shots.
  A better training set is planned.
- One topic's training data contains mislabelled images, such as a helmet among the motorcycles.
- 128 × 128 output. Multi-object scenes are still composed from separate cut-outs.
