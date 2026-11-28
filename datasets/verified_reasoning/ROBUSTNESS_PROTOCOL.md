# Separate wording robustness from checker validation

The existing `hard` split shares generator/program families with training. Changing a seed or adding polite wrappers
does not make it an independently authored language-transfer test.

For a future evaluation, freeze a separate probe set before tuning or fine-tuning:

1. **A:** a problem with independently checked facts and a determinate gold (or a justified abstention).
2. **B:** a meaning-preserving rewording. Change one factor at a time where possible: date notation, clause order or an
   instruction verb. Check that no premise, scope, unit, chronology or answerability condition changed.
3. **C:** change a relevant fact so the expected answer changes. In an insufficient-information case, add an actual
   observation or missing premise; this is a changed-fact control, not another equivalent paraphrase.
4. Keep complete raw replies, caps/errors, generation settings and checkpoint revisions. Report the four A/B states
   separately: both correct, A-only, B-only, neither. Keep ambiguous/incomplete parser results separate from wrong.
5. Inspect checker disagreements and reasoning quality independently of the final label. Assess over-guessing and
   over-refusal separately. A correct result following a false explanation is not a sound worked solution.
6. To measure a training effect, use matched before/after checkpoints, a suitable no-training/alternative-data control,
   an appropriate sample and repeated seeds. A tiny adapter smoke test does not establish full-data transfer.

If published evaluation examples later become training templates, reserve genuinely distinct evaluation material and
disclose the exposure. The prompts John6666 published have been viewed during this correction; no such prompt was
added to this dataset's training rows, and this patch makes no new model-training or transfer-performance claim.

Reference: [John6666's feedback](https://discuss.huggingface.co/t/2m-reasoning-examples-for-fine-tuning-small-models-with-worked-solutions-and-a-python-answer-checker/192328/2).
