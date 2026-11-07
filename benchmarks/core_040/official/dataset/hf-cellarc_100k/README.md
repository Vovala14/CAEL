---
language:
- en
license: mit
annotations_creators:
- machine-generated
size_categories:
- 100K<n<1M
task_categories:
- other
- text-generation
- visual-question-answering
- image-to-image
- reinforcement-learning
task_ids:
- language-modeling
- visual-question-answering
- image-inpainting
pretty_name: CellARC 100k
tags:
- cellular-automata
- arc
- reasoning
---

# cellarc_100k
CellARC 100k a cellular-automata benchmark dataset introduced in Lzicar, M. (2025). CellARC: Measuring Intelligence with Cellular Automata. Each episode exposes five support pairs plus a held-out query/solution pair.

## Data quick facts
- Alphabet size `k` in [2, 6]; window size `W` in {3, 5, 7}; radius `r` in {1, 2, 3}; steps `t` in {1, 2, 3} (≈95% have `t = 1`).
- Values (digits) are integers in `0..k-1` per episode; across the full dataset the union of symbols is `{0,1,2,3,4,5}`.
- Five training exemplars per episode (`len(train) = 5`).
- Sample length `L` ∈ [5, 21] (median 11). Episode total length is `12 × L` (5 train pairs + query + solution), median 132.
- JSON layout: `id`, `train[].input`, `train[].output`, `query`, `solution`.

### Example record
```
{
  "id": "…",
  "train": [
    {"input": [0, 1, …], "output": [2, 0, …]},
    …
  ],
  "query": [3, 0, …],
  "solution": [4, 5, …]
}
```

## Contents
```
cellarc_100k/
├── data/
│   ├── train.{jsonl,parquet}
│   ├── val.{jsonl,parquet}
│   ├── test_interpolation.{jsonl,parquet}
│   └── test_extrapolation.{jsonl,parquet}
├── subset_ids/          # text files listing episode IDs for predefined subsets
├── data_files.json      # byte counts + record tallies
├── dataset_stats.json   # aggregate statistics captured during export
├── features.json        # Hugging Face feature schema
├── LICENSE
└── CITATION.cff
```
The JSONL exports support streaming; the Parquet exports are ready for analytics or Hub upload.

## Split summary
| split | episodes | parquet bytes |
|-------|----------|---------------|
| train | 95,317   | 12,378,645    |
| val | 1,000 | 128,117 |
| test_interpolation | 1,000 | 128,271 |
| test_extrapolation | 1,000 | 130,303 |

(See `artifacts/hf_cellarc/hf-cellarc_100k/data_files.json` for authoritative sizes.)

## Subset splits and ID lists
- Predefined 100-episode subsets are included for all splits as
  `data/{train,val,test_interpolation,test_extrapolation}_100.{jsonl,parquet}`.
- The exact episode selections are recorded under `subset_ids/` as
  `{split}_100.txt` (one ID per line). These lists allow reproducible sampling
  and enable efficient evaluation workflows.
- Motivation: Smaller, fixed subsets facilitate quick iteration and reduce
  evaluation costs when using API‑metered large language models or other
  pay‑per‑call services, while preserving representativeness of the full splits.

## Coverage & dynamics
- Coverage fraction (global): mean 0.402, min 0.069, max 0.938.
- Langton’s λ (global): mean 0.565, min 0.016, max 1.000.
- Avg. cell entropy (global): mean 1.110 bits, max 2.585.
- Steps: 1 (95.3%), 2 (4.6%), 3 (0.1%).
- Window size: W=3 (74.1%), W=5 (13.3%), W=7 (12.6%).
- Radii: r=1 (78.7%), r=2 (8.7%), r=3 (12.5%).
- Families (share of episodes): random 25.3%, totalistic 24.8%, outer‑totalistic 18.7%, outer‑inner totalistic 18.7%, threshold 11.9%, linear mod(k) 0.7%.

Details per split in `artifacts/hf_cellarc/hf-cellarc_100k/dataset_stats.json`.

## Loading examples
```python
from datasets import load_dataset

# Parquet (recommended)
parquet_files = {
    split: "data/" + f"{split}.parquet"
    for split in ("train", "val", "test_interpolation", "test_extrapolation")
}
ds = load_dataset("parquet", data_files=parquet_files)

# JSONL for quick inspection
jsonl_files = {split: "data/" + f"{split}.jsonl" for split in parquet_files}
raw = load_dataset("json", data_files=jsonl_files)
```
When uploaded to the Hub, replace local paths with the dataset ID (e.g. `load_dataset("mireklzicar/cellarc_100k", split="train")`).

## Resources
- Leaderboard: https://cellarc.mireklzicar.com
- Dataset repo: https://github.com/mireklzicar/cellarc
- Baselines repo: https://github.com/mireklzicar/cellarc_baselines
- HF dataset: https://huggingface.co/datasets/mireklzicar/cellarc_100k
- HF meta: https://huggingface.co/datasets/mireklzicar/cellarc_100k_meta

## Companion metadata package
`cellarc_100k_meta` shares the same Parquet assets but retains the metadata-rich JSONL lines (rule tables, morphology signatures, coverage diagnostics, etc.). Use it when you need full provenance.

## Reproduction
```
python scripts/resample_highcov.py \
  --input artifacts/deprecated/pool_downsampled/downsampled_enriched.jsonl \
  --output artifacts/processing/resampled_highcov/downsampled_enriched.jsonl \
  --target-coverage 0.5 --overwrite
python scripts/split_pool.py --input artifacts/processing/resampled_highcov/downsampled_enriched.jsonl \
  --output-dir artifacts/processing/resampled_highcov/splits --train-count 100000 --val-count 1000 \
  --test-interp-count 1000 --test-extra-count 1000 --coverage-threshold 0.0
python scripts/build_hf_dataset.py --source-dir artifacts/processing/resampled_highcov/splits \
  --target-root artifacts/hf_cellarc --dataset-name hf-cellarc_100k --extended-suffix _meta --overwrite
```

## License & citation
- License: MIT (repository default).
- Cite the CellARC project when reporting results (`CITATION.cff`).
