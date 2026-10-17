# CAEL hybrid image model 0.3.9

Requested on 2026-10-17: train CAEL's image generator on images from the owner's local Stable Diffusion 1.5 (the
Portrait64 tool), with as many topics as possible. The generator must stay free of neural networks and transformers;
the owner asked for a hybrid approach.

## Data

- **New set:** 3,060 renders, 102 topics × 3 styles × 10 images, made with `portrait64.py` at 512 px and 18 steps. The
  styles are studio photo on a plain background, side-view product photo, and flat illustration. Scenes (city,
  mountain, beach…) use wide views instead. Prompts are in `research/image_hybrid_039/prompts.txt`; run time was about
  2 hours at about 25 images a minute.
- **Earlier set:** the 1,992 renders of the paused 0.2.5 run were reused, with duplicates and blank renders dropped.
- **Held out:** the last image of every 10-image prompt and every tenth 0.2.5 image (492 images). These are never
  fitted.
- **Licence:** Stable Diffusion 1.5 outputs under CreativeML OpenRAIL-M.

## Method (`cael_image/hybrid.py`, `request.py`, `compose.py`, `draw.py`)

1. **Layout:** a per-topic PCA model of 16×16 training images samples a new arrangement of shape and colour.
2. **Donors:** the 2 training images whose layout is closest, both of one style. Mixing a photo with an illustration
   produced the worst seams.
3. **Detail:** coarse-to-fine texture optimisation at 32, 64 and 128 px (Kwatra-style patch synthesis). Matching is
   done on blurred copies while sharp originals are pasted ("detail transfer"); without this the synthesis kept
   choosing flat, featureless patches.
4. **Novelty guard:** a picture closer than RMSE 25 (0–255 scale, at 128 px) to any single training render is
   discarded and redrawn.
5. **Request understanding:** subject, colour, style (photo, illustration, side view), count (up to 3) and scene. Style
   uses the labelled donors. Colour, count and scene edits use object masks synthesised from the clean training
   renders; they are marked as experimental in replies.

## Results (`research/image_hybrid_039/train_eval_final.log`, `report.json`)

A ridge classifier on colour and edge features, trained on the training renders, checks whether the intended topic is
recognisable. All metrics are computed at 64 px.

| Model / setting | Recognised (top-1) | Top-5 | Sharpness | Nearest training RMSE (mean / min) |
| --- | ---: | ---: | ---: | ---: |
| Held-out real SD renders | 35.8% | 64.2% | 0.058 | 67.9 (new real images) |
| 1 source | 58.8% | 86.1% | 0.046 | 41.9 / 14.4 |
| 2 sources | 57.4% | 86.1% | 0.045 | 49.7 / 20.2 |
| **2 same-style sources (live)** | **63.9%** | **89.9%** | 0.044 | 43.3 / 11.3 before the guard |
| 4 sources | 56.9% | 88.7% | 0.042 | 53.1 / 22.4 |
| Previous live model, its 19 topics | 3.5% | 14.9% | 0.066 (texture noise) | 76.5 |
| Hybrid on those 19 topics | 53.5% | 86.8% | 0.047 | 49.4 |

- **Recognisable, not better than SD.** Generated pictures are classified more reliably than real held-out renders
  because they are built from training patches and are therefore very typical. This shows they are recognisable, not
  that they are better than Stable Diffusion.
- **More data alone does not help.** Fitting on evenly spaced ⅓, ⅔ and all of each topic's renders gave 61%, 55% and
  57% top-1, with sharpness 0.050, 0.046 and 0.045. Getting closer to Stable Diffusion's look needs method changes
  (aligned donors, seamless blending, best-of-N selection, renders designed for blending), not simply more of the
  same renders.
- **Known weak topics:** ball, rocket, balloon and kite. The edits (colour, count, scene) look rough for some subjects.

The live selection is `hybrid_image` in `research/active_models.json`, pointing to
`models/cael-image-hybrid-0.3.9/final_102_topics.npz`. Earlier selections are backed up as
`research/image_hybrid_039/active_models_before_*.json`. Topics the hybrid lacks fall back to the previous model.
Sample sheets are `interim_samples.png` and `final_samples.png`; the 1/2/4/8-source comparison is
`tradeoff_sources.png`.

## Next steps (owner's goal: SD-like quality at lower resolution, still non-neural)

- **Best-of-N selection:** draw several candidates and keep the ones that score best on a classic seam and edge
  quality measure.
- **Aligned donors:** centre and scale each object by its mask before mixing, so the donors line up.
- **Seamless joins:** gradient-domain (Poisson) blending and minimum-error cuts between donor regions.
- **Renders made for blending:** one fixed view on a pure white background for topics added by the owner.
- **Output at 64–96 px.**
- **Unseen topics:** fetch only public-domain or CC0 images (owner's decision) and redraw them on demand.
