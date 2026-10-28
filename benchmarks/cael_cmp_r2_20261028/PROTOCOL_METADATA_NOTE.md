# Frozen metadata count discrepancy

The sealed final_protocol.json retains a stale `distinct_inputs: 64` field
from the parent experiment. It also correctly declares 80 items and twenty
per category. The actual sealed final.jsonl contains **80 distinct exact
history/question pairs**, reproduced by audit.py; data_manifest.json records
80 rows and zero exact overlap with the three previous sets. No item is
excluded, duplicated, replaced or added because of this note.

Do not edit or reseal the original metadata. The frozen input SHA-256 remains
`7ba1ffa775c4dea496ae11f48ef65f054bc88ce3c59a94650033dc3de8dff51f`.
This is a disclosed clerical count discrepancy, not a grading change.
