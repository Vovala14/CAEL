# Dataset corrections

## 1.1.1 data / 1.2.0 checker — 28 November 2026

Original dataset revision: `31780cd0fed31c04a50deafd3c27f75f33a84825`.

- Corrected 142 negative-money reference answers and the corresponding solution equations. The old money formatter
  used negative floor division/modulo: for example, -250 cents rendered as `$-3.50` rather than `$-2.50`.
- Corrected 30,763 explanations for shortest/youngest/lightest/slowest comparisons: the unique minimum is never on the
  *winning* side of a stated comparison. Reference names were already correct and remain unchanged.
- Preserved every question, ID, split membership and schema. The changed row IDs and old/new fields are fully recorded
  in `errata.jsonl`. Corrected rows have a `1.1.1` generator label; unchanged rows keep their original `1.1` provenance.
- Updated the generator's signed-money formatter and comparison explanation renderer. No neural model, training data
  expansion, test-specific CAEL routing change or additional model evaluation is part of this correction.
- Replaced permissive numeric/keyword containment with a bounded final-answer checker and structured `judge` API.
  The boolean `check` API remains. Explicit negation, sign/currency/units, remainder/budget/refund direction, source
  attribution, conflicting final claims and exact grid shape/cells now have regression coverage. Unsupported or
  ambiguous text is not automatically labelled semantically wrong.
- Added 136 targeted CPU cases with positive equivalents. Counts are software validation, not model capability or a
  random real-completion error rate. The prior checker is retained as `verify_legacy_v1_1.py` for reproducibility.
- Audited all 2,001,427 rows for preservation, unique core texts and reference self-consistency; independently
  recomputed all 54,541 pay-minus-spending rows and 76,506 comparison graphs. Other task families are not claimed to
  have a complete independent correctness proof.
- Reduced Parquet row-group size to at most 8,192 rows. Split sizes and shard names remain unchanged.
- Removed unsupported universal-correctness, currency-equivalence and direct-RL-reward claims; documented SFT target
  construction, checker uncertainty and the same-family nature of the hard split.

Feedback: [John6666's forum reply](https://discuss.huggingface.co/t/2m-reasoning-examples-for-fine-tuning-small-models-with-worked-solutions-and-a-python-answer-checker/192328/2).
The 29-case audit and LoRA pilot described there are separate from this patch's CPU tests. The original immutable
snapshot remains available for reproducing historical runs; do not silently compare scores from different revisions.
