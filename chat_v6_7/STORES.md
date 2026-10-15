# CAEL chat v6.7: big stores (not in the repo; rebuild with the scripts)
| store | size | built by |
|---|---|---|
| rs/v67/kg67.duckdb | ~4.1 GB | build_kg_facts.sh (Wikidata truthy dump, filtered by pats.txt) then build_kg.py, add_indeg.py, fill_labels.py |
| rs/v67/leads65.sqlite | large | build_leads.py (resume: build_leads_resume.py) |
| rs/v67/tatoeba66.sqlite | large | build_tatoeba.py |
| rs/v67/idx_qa.npz | ~106 MB | build.py (writes store65_raw.json.gz) then index.py |
Included small stores: answer_store_v64.json.gz, store65_meta.json.gz, thresholds65.json, wiki_cache.json, v4/knowledge_v4.json.gz, model.json.gz, v2/model_v2.json.gz.
Build scripts use absolute paths under /workspace/cael (edit B= / paths before running). Requires duckdb, pyarrow, numpy, sympy.
Data licences of the sources (OASST, Wikipedia/Wikidata, Tatoeba, NQ) must be checked before publishing the built stores.
