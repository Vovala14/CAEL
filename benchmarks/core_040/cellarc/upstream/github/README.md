# cellarc

This repository contains dataset generation pipeline for CellARC:
- Model training and baselines: https://github.com/mireklzicar/cellarc_baselines 
- Website: https://cellarc.mireklzicar.com/

![](assets/ca_demo.png)

## Installation

```bash
pip install cellarc
```

For generation and simulation features (JAX/CAX-based rule runners, automatic
dataset synthesis) install the full extra:

```bash
pip install cellarc[all]
```

> **Python 3.11+ required:** The `cax` package only publishes wheels for Python
> 3.11 and newer, so `cellarc[all]` (and any extra that pulls in `cax`) must be
> installed from a 3.11+ interpreter. On older Python releases the base package
> still works, but the CA generation helpers remain unavailable.

Dataset snapshots are fetched directly from the Hugging Face Hub and cached in
`~/.cache/cellarc` (override with the `CELLARC_HOME` environment variable).
There are no repository fallbacks; if a download fails, the loader raises an
error so the issue can be fixed explicitly.

## Working with datasets

```python
from cellarc import EpisodeDataset, EpisodeDataLoader

# Load the supervision-only split shipped in ``mireklzicar/cellarc_100k``.
train = EpisodeDataset.from_huggingface("train", include_metadata=False)

# Iterate over metadata-enriched episodes (``mireklzicar/cellarc_100k_meta``).
val = EpisodeDataset.from_huggingface("val", include_metadata=True)

print(len(train), len(val))

# Batch episodes with optional augmentation.
loader = EpisodeDataLoader(
    val,
    batch_size=8,
    shuffle=True,
    seed=1234,
)

first_batch = next(iter(loader))
print(first_batch[0]["meta"]["fingerprint"])
```

The available remote splits are `train`, `val`, `test_interpolation`, and
`test_extrapolation`. Each split is stored as `data/<split>.jsonl` (the default
loader) and `data/<split>.parquet`; set `fmt="parquet"` when using
`datasets`/`pyarrow` for faster IO.

### Listing splits and sizes

Use the Hub manifest to enumerate every split (including the fixed 100-episode
subsets) and their record counts without iterating over the payload:

```python
from cellarc import available_remote_splits, download_benchmark, load_manifest

repo = download_benchmark(name="cellarc_100k", include_metadata=True)
manifest = load_manifest(repo / "data_files.json")

for split in available_remote_splits():
    artifacts = manifest.get(split)
    if not artifacts:
        continue
    records = artifacts["jsonl"]["records"]
    size_mb = artifacts["jsonl"]["bytes"] / 1_000_000
    print(f"{split:<22} {records:>7} episodes | {size_mb:5.1f} MB JSONL")
```

`data_files.json` ships with every snapshot and stores counts for both the JSONL
and Parquet artifacts, so the snippet prints immediately even before installing
`datasets`.

### Quick 100-episode subsets

For faster iteration, the dataset repositories provide fixed 100-episode
subsets for every split: `train_100`, `val_100`, `test_interpolation_100`, and
`test_extrapolation_100`. You can access them via the same loader API:

```python
from cellarc import EpisodeDataset

# Load the 100-episode training subset (with metadata merged in).
train_small = EpisodeDataset.from_huggingface("train_100", include_metadata=True)
print(len(train_small))  # -> 100

# Iterate or batch as usual...
for episode in train_small:
    print(episode["id"])  # first few IDs
    break
```

### Visualising CA episode cards

`cellarc.visualization.episode_cards.show_episode_card` reconstructs the
underlying automaton and renders ARC-style grids with the CA rollout:

```python
import matplotlib.pyplot as plt
from cellarc import EpisodeDataset
from cellarc.visualization.episode_cards import show_episode_card

val = EpisodeDataset.from_huggingface("val", include_metadata=True)
episode = next(iter(val))

fig = show_episode_card(
    episode,
    tau_max=16,
    show_metadata=True,
    metadata_fields=("split", "family", "alphabet_size", "radius", "steps", "lambda"),
)
fig.suptitle(f"Episode {episode['id']}")
plt.show()  # or fig.savefig("episode_card.png", dpi=200)
```

Tune `metadata_fields`/`metadata_formatter` for the footer and use `tau_max` or
`rng_seed` to explore deeper or stochastic rollouts. The helper lives in
`cellarc/visualization/episode_cards.py`.

### Refreshing the cache

Force-refresh a snapshot when you need a clean copy:

```bash
python - <<'PY'
from cellarc import download_benchmark
download_benchmark(name="cellarc_100k", include_metadata=True, force_download=True)
PY
```

## Optional generation stack

With the `all` extra installed you gain access to the sampling and simulation
utilities:

```python
import random
from pathlib import Path

from cellarc import generate_dataset_jsonl, sample_task

task = sample_task(rng=random.Random(0))
generate_dataset_jsonl(Path("episodes.jsonl"), count=128, include_rule_table=True)
```

These helpers depend on `jax`, `flax`, and `cax`. If the import fails, install
the extra or vendor the required frameworks manually.

## Dataset anatomy (HF card highlights)

Key facts pulled from `artifacts/hf_cellarc/hf-cellarc_100k_meta/README.md`:

### Episode layout

- CellARC 100k Meta mirrors the supervision-only `cellarc_100k` splits but keeps the metadata-rich JSONL files; the Parquet shards remain byte-identical between both repositories.
- Each JSON line contains `id`, five `train` pairs, a `query`/`solution` pair, and a `meta` block. The metadata variant serializes the CA `rule_table` and propagates the deterministic fingerprint (`id == meta["fingerprint"]`).
- Alphabets use digits `0..k-1` with `k` in `[2, 6]` (global union `{0,1,2,3,4,5}`) and exactly five supervision pairs per episode.
- Train/query lengths `L` fall in `[5, 21]` (median 11), so a full episode spans roughly `12 * L` tokens.

### Split summary

| split | episodes | parquet bytes |
|-------|----------|---------------|
| train | 95,317 | 12,378,645 |
| val | 1,000 | 128,117 |
| test_interpolation | 1,000 | 128,271 |
| test_extrapolation | 1,000 | 130,303 |

Parquet sizes match `cellarc_100k`; JSONL variants are larger because they carry metadata.

### Rule-space & coverage stats

- Window size `W` in `{3, 5, 7}`, radius `r` in `{1, 2, 3}`, steps `t` in `{1, 2, 3}` with ~95.3% of episodes using a single rollout step.
- Global coverage fraction: mean 0.402 (min 0.069, max 0.938); Langton's lambda: mean 0.565 (min 0.016, max 1.000); average cell entropy: mean 1.110 bits (max 2.585).
- Window distribution: `W=3` (74.1%), `W=5` (13.3%), `W=7` (12.6%); radius distribution: `r=1` (78.7%), `r=2` (8.7%), `r=3` (12.5%).
- Family mix: random 25.3%, totalistic 24.8%, outer-totalistic 18.7%, outer-inner totalistic 18.7%, threshold 11.9%, linear mod(k) 0.7%.

### Repository contents & subsets

```
cellarc_100k_meta/
|-- data/
|   |-- train.{jsonl,parquet}
|   |-- val.{jsonl,parquet}
|   |-- test_interpolation.{jsonl,parquet}
|   `-- test_extrapolation.{jsonl,parquet}
|-- subset_ids/
|-- data_files.json
|-- dataset_stats.json
|-- features.json
|-- LICENSE
`-- CITATION.cff
```

- Every split also has a fixed 100-episode subset (`data/<split>_100.*`) with the selected IDs recorded under `subset_ids/{split}_100.txt`.
- Use `dataset_stats.json` for precise JSONL byte counts per split if you need more detail than `data_files.json`.

## Repository scripts

- `scripts/dataset/create_subset_splits.py`: samples deterministic ID lists per split from the Hugging Face checkout, writes `data/<split>_100.{jsonl,parquet}`, records IDs under `subset_ids/`, updates `data_files.json`, and can optionally commit/push via `--push`.
- `scripts/plots/plot_dataset_stats.py`: loads the metadata JSONL shards (downloading them if needed), aggregates coverage/lambda/morphology signals with pandas, and emits figures such as `figures/dataset_stats/rule_space_histograms.png` plus per-split family mixes.
- `scripts/plots/plot_top10_ca_squares.py`: given `figures/episode_difficulty_top10.csv` (or the full per-episode accuracy CSV), reconstructs rule tables and saves hardest/easiest CA square PNGs under `figures/episode_difficulty_ca_squares/{easiest,hardest}`.
- `figures/generate_ca_squares.sh`: headless helper that ensures the metadata repo is cached, then runs `scripts/plots/ca_squares.py` across `train/val/test_*` to render batches of CA thumbnails and JSON summaries in `figures/ca_squares/`.

## Further reading

- Dataset cards live at https://huggingface.co/datasets/mireklzicar/cellarc_100k
  and https://huggingface.co/datasets/mireklzicar/cellarc_100k_meta.
- Solver experiments: `SOLVER_RESULTS.md`.

## Development & release

Install development dependencies with the `dev` extra:

```bash
pip install -e ".[dev,all]"
```

Because the development install also pulls in `cax`, run the above from Python
3.11+ to ensure the simulator dependencies resolve correctly. Use `pip install
-e ".[dev]"` on older interpreters if you only need the core test/tooling stack.

If you have unrelated pytest plugins installed globally, disable auto-loading to
match the CI environment:

```bash
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
pytest
```

The GitHub Actions workflow (`.github/workflows/python-package.yml`) mirrors the
`lineindex` release automation: every push or PR to `main` runs formatting
checks, installs the package from source, and executes the test suite. When a
push lands on `main`, the workflow automatically bumps the patch version via
`bump2version`, tags the commit, builds wheels/sdists with Hatchling, and
publishes them to PyPI using the `PYPI_API_TOKEN` secret. Add `[skip version bump]`
to the commit message if you need CI without publishing. To run the same release
steps locally:

```bash
pip install build bump2version twine
bump2version patch  # or minor / major
python -m build
python -m twine upload dist/*
```
