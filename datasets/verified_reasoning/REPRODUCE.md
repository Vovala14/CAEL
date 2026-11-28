# Reproduce this correction on CPU

Use Python 3.10+ and `pyarrow`; downloading snapshots also uses `huggingface_hub`.
The checker and its regression tests themselves use only the standard library.

1. Download this corrected dataset snapshot, recording its immutable revision.
2. Download the original snapshot separately:

```python
from huggingface_hub import snapshot_download
original = snapshot_download(
    "vynly/cael-verified-reasoning",
    repo_type="dataset",
    revision="31780cd0fed31c04a50deafd3c27f75f33a84825",
)
print(original)
```

3. From the corrected snapshot, run:

```text
python test_verify.py
python audit_checker.py
python audit_dataset.py --original PATH_PRINTED_ABOVE --corrected .
```

`audit_dataset.py` checks every row and writes `validation_report.reproduced.json`.
Expected counts are 2,001,427 preserved rows, 30,905 changed rows (142 money answer/solution repairs plus 30,763
comparison-explanation repairs), 54,541 independent pay recomputations, 76,506 independent comparison graphs and
261,645 grid-representation consistency checks. These are distinct validation scopes, not model capability tests or a
proof that every natural-language reference/explanation is correct. Runtime will vary; hashes and counts should agree.

To reconstruct the data correction into a new directory, without changing either input snapshot:

```text
python repair_data.py --source PATH_PRINTED_ABOVE --out NEW_EMPTY_DIRECTORY
```

This repair helper targets only the pinned original revision and checks the expected correction counts. It does not
silently generalize to other dataset versions. It writes the corrected shards, stats, `errata.jsonl` and
`data_revision.json`; use the corrected snapshot's checker and documentation alongside them. Original row order,
question messages, IDs, split membership and schema are retained. Compression-library versions can affect Parquet
byte hashes; the full logical row audit is authoritative for a reconstruction with a different PyArrow version.

The old checker is available as `verify_legacy_v1_1.py`; retain the original dataset revision when reproducing old
model scores. No model inference, GPU, training, external answer API or paid service is required for these audits.
