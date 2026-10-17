# Non-neural image training — completed 2026-10-16

The shared worker now uses a new 128×128 student for 19 reviewed general-image categories. It retains the released 64×64 generator for 13 other categories and the existing v15 adult-female portrait route. This is a local runtime override; the published 0.2.1 bundle, release copies and GitHub tag were not changed.

## Data and model

Generated 2,048 new synthetic examples with the installed Stable Diffusion 1.5 teacher, across 32 subject categories (64 each). Teacher renders were 384×384, 16 steps, with 128×128 training inputs and matching text captions. No private photos were read or viewed. The owned teacher server was stopped after generation completed.

Teacher checkpoint SHA-256: `6ce0161689b3853acaa03779ec93eafe75a02f4ced659bee03f50797806fa2fa`. Existing CreativeML OpenRAIL-M terms apply. The old 1,024-example experiment remains a baseline; its images were not silently counted in this fit.

The new fit used 1,496 synthetic images. It reserved 256 development and 256 confirmation images, excluded from fitting and the similarity guard. Forty additional synthetic face images failed the fitting-set alignment criteria and were excluded. Pixel/file hashes freeze the inputs and reject duplicates. The final evaluation verified the source hashes remained unchanged.

The student uses grouped classical shape/appearance statistics, optical-flow registration, and learned integer-count factor cellular automata. Joint factor-bin configurations seed local count-based updates; the warp is bounded to reduce folds. This is a hybrid statistical/CA model, not a pure pixel automaton. It has no neural-network student or text encoder. The separately implemented luminance-patch CA is disabled in the selected settings because it added texture without improving shapes. Stable Diffusion is only the synthetic-data teacher.

Model: `models/cael-general-128-v2-synthetic/model_general.pt`

SHA-256: `d43ac82f858a9a25c262cb2c80c4826d10be67a53aa4e5db24ef104085ad05ce`

## Results and deployment decision

Compared all 32 categories, four generated images per category, using fixed predeclared seeds shared with the old generator. Only generated student outputs were displayed. All four complete comparison pages are in `results/general-0.2.2/`.

- Median edge sharpness at equal 64-pixel resolution: **1.339× baseline**.
- Crude confirmation RGB-centroid category separation: **27/128 candidate vs 31/128 baseline**. This declined; sharper output is not evidence of better general semantic understanding.
- Smallest generated-to-fitting-reference normalized RMS: **0.128164**, above the configured 0.04 guard. This limited pixel-distance check does not establish originality, privacy guarantees or realism.
- Visual review found clearer recognizable contours in selected categories, but warping, overlapping objects and malformed faces persist. Outputs remain painterly; normal photorealistic generation has not been achieved.

Enabled: car, motorcycle, truck, phone, camera, watch, woman, man, dog, cat, dragon, tree, house, city, mountain, forest, burger, chair, shoe.

Kept baseline: bicycle, airplane, boat, laptop, headphones, robot, horse, bird, flower, beach, pizza, cup, spaceship. Reasons are recorded individually in `results/general-0.2.2/visual_review.json`. This is a single-reviewer development choice, not blinded independent preference testing. Four fixed samples do not establish consistency across all seeds.

The previous portrait route was visibly better than the synthetic face candidate in a separate generated-output comparison, so it was retained. Generic woman/man image requests can use the new generator; explicit adult-female portraits still use v15.

The finite vocabulary remains 32 categories. Arbitrary combinations, caption attributes, precise text, reliable anatomy and arbitrary prompt composition are not trained controls. More unstructured images alone are unlikely to remove the remaining averaging and registration artifacts. The next useful image change would address object correspondence and coherent geometry rather than simply extending this training run.

## Evidence and activation

- `research/general_image_022/dataset/manifest.json`: 2,048 frozen synthetic records and captions.
- `models/cael-general-128-v2-synthetic/report.json` / `split.json`: exact fitting/held-out records and parameters.
- `results/general-0.2.2/report.json`: fixed-sample comparison diagnostics.
- `results/general-0.2.2/generated_comparison_page_1.png` through `_4.png`: old outputs on the left, new outputs on the right. These contain generated outputs only.
- `research/active_models.json`: checksum-verified runtime selection and retained fallback.
- `research/request_policy_022/public_verification.json`: public worker text routing, actual PNG dimensions and cross-session ownership checks after restart.

The bounded experiment is complete. The GPU teacher and fitting jobs are no longer needed; the shared worker and its existing tunnel remain running.
