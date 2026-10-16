# First synthetic general-image student

Generated locally: 1,024 SD1.5 teacher outputs across 32 finite categories.
Fitted: 768 images, with 256 held out by decoded-pixel groups. No private
portrait photo was used for this student's training or evaluation.

The teacher checkpoint hash, prompts, seeds, render settings, student settings
and exact split are retained in protocol.json, report.json and split.json.
Teacher generation took 1,640.1 seconds in this run. Student fitting and
generated-output checks took 2.66 seconds; hardware/load affect timings.

The synthetic held-out nearest-training-mean category diagnostic scored
69/256 (26.95%) across 32 categories, with chance 3.125%. This is RGB mean
separation within the teacher domain, not a trained classifier, prompt-following
accuracy, generalization benchmark or realism score. Minimum generated RMS
distance to the synthetic fitting references was 0.120352 in the fixed generated
batch. No guard replacements were needed; the frozen synthetic cutoff was 0.04.

generated_summary.png contains the fixed first student draw of every category,
not a selected attractive subset. Visual review found recognizable broad cues
in several categories but many blurred, overlapping and malformed objects.
Faces and bicycles remain weak. See visual_review.json for the bounded finding.
Only student-generated images were viewed; teacher training images and private
source photos were never displayed.

bundle_smoke.json exercises chat, arithmetic, writing, cars, bikes, phones,
portrait generation, base emoji, stored learned emoji and an unsupported subject.
It verifies deterministic image replay and stored-emoji attribution. The
combined release's 21 unit tests passed. Additional release checks are recorded
in release_verification.json. Current remote chat/web lookup was unavailable;
the public bundle contains the explicitly documented local legacy fallback.
