# CAEL 0.4.0: exact official CellARC harness reproduction

The source checkpoint was frozen before the original full test inference. The subsequent official-harness run is a reproduction on already-viewed tasks, with no fitting, tuning or replacement of the original evidence. All 2,000 predictions AND full replies are identical. Interpolation: 6361/11099 cells, 79/1000 puzzles. Extrapolation: 3815/10918 cells, 5/1000 puzzles.

The unmodified official `scripts/eval_symbolic.py`, its original loader, factory, clone/zip_longest handling, denominators and JSON output are used. The exact adapter only registers a new SymbolicSolver and builds a whitelist task from five `train` pairs and `query`. IDs, `solution`, metadata and hidden-rule information never enter the Assistant prompt. Invalid/clarification replies become `[]`, so every target cell counts wrong; none are dropped.

Official pins: dataset package `mireklzicar/cellarc@2a317a6f78025f67d0666e0ce7ad10436a18a807`; baselines `mireklzicar/cellarc_baselines@add0b574dd25e586263bbb516cb819da1dc6a3f8`; supervision-only dataset `mireklzicar/cellarc_100k@76040e6aef0edc4982e53c13a85ef227378ed171`. Original sources, licences, input files, checksums, results and adapter are included. The vendored source subset contains the original Python modules and evaluation config, without changing any file.

## Run from the extracted CAEL release root

Use **Python 3.12**. Install `requirements-unified.txt` and `benchmarks/core_040/official/requirements-harness.txt`, and run `python -m cael_unified --download` first. The installer uses the unchanged, pinned 0.3.7 resource archive. Then:

```bash
python benchmarks/core_040/official/run_official_cellarc.py --cael-root . --source-manifest benchmarks/core_040/official/release_source_binding.json --upstream benchmarks/core_040/official/official_upstream --upstream-manifest benchmarks/core_040/official/official_sources.json --dataset-root benchmarks/core_040/official/dataset --dataset-manifest benchmarks/core_040/official/dataset_manifest.json --output cellarc-reproduction
```

Each output directory must be new. Inference is offline; the official loader reads only the byte-preserved local test files. `official_metrics.json` is produced by the official harness, not a rewritten scorer. `predictions.jsonl` retains every actual reply and error. `receipt.json` hashes source/input/harness/results and records runtime versions.

The original official run used exact frozen candidate bytes with Python 3.12.9, CPU Torch 2.9.1 (imported by the official package), and the dependency versions in its receipt. No neural baseline is instantiated; CAEL's transition route remains non-neural. Its original Python 3.14 evaluation produced identical replies. Three setup attempts made zero model calls: missing einops, Hydra/Python-3.14 incompatibility, missing pydantic. They are retained under `official/setup_attempts`; no upstream code was patched to work around them.

The release changes only product identity facts/documentation relative to the frozen inference source; `release_source_binding.json` verifies those declared bytes. Original metadata is retained in `frozen_metadata`. The CellARC algorithm, Assistant route, thresholds and settings are exact evaluated bytes. No claim of accepted leaderboard placement or other-model reproduction is made. Published LLM rows use smaller subsets and other protocols; no general chatbot/Qwen superiority follows.

The 109.13 MiB original process peak and 1.498 s original 2,000-task inference belong to the original minimal structured run. The official harness imports extra Torch/neural class definitions and has separate overhead; do not relabel those measurements as its full-process footprint. Data: Miroslav Lžičař, CC BY 4.0; see `cellarc/LICENCE_NOTE.md` and the retained original licences. Upstream source: Apache-2.0. CAEL's own non-commercial licence remains unchanged.
