# Local-first knowledge update — 2026-10-16

The active shared worker now tries a licensed local text memory for stable factual questions before making internet requests. Current information and explicit web searches bypass the snapshot. This changes the local runtime; it does not overwrite the released 0.2.1 bundle, release copies or GitHub tag.

## What was collected and trained

The text-only collector followed Wikipedia's Level 4 core-topic sublists across history, geography, people, arts, everyday life, philosophy/religion, society, biology/health, physical sciences, mathematics and technology. It collected 10,026 records, which became **10,025 unique articles and 349,568 passages** after canonical-page deduplication.

Only public Wikipedia text was fetched. No image URLs were downloaded, no private photos were read or viewed, and no user conversations became training data. The collector is resumable, spaces requests, respects provider backoff/maxlag, records revision IDs and hashes, and parses text locally. Source media, templates, reference lists and markup are removed. That removal can damage prose or quantities; runtime checks reject detectable damaged/incomplete excerpts and can fetch rendered public text on a miss. The checks do not detect every possible text-cleaning defect.

Text and derived excerpts retain **CC BY-SA 4.0**, contributor credit, specific article/revision URLs, collection timestamps and modification notices. The sources page exposes the snapshot notice. The source licence does not change CAEL's software licence.

The student remains non-neural. Its local memory uses SQLite FTS5/BM25, corpus token statistics, title/redirect aliases, and a small learned linear passage selector. The final passage selector trained on **49,783 examples** weakly labelled from section headings, with topic-separated development/confirmation splits. Section-label agreement was 6,378/6,383 and 6,480/6,481. Those near-perfect label scores are largely a section-heading task and **are not answer correctness or general intelligence scores**.

A separate question-form classifier trained on **972 authored examples** for definitions, causes, mechanisms, locations, times and comparisons. It scored 162/162 on topic holdouts and 61/72 on new authored phrasings. Request parsing and output checks are a disclosed hybrid of learned classifiers and authored grammar/evidence rules. The existing weather/sports router is retained, with specific sports-result cues preventing unrelated questions from being treated as live-score requests.

## Runtime behavior

- Stable questions first search locally. Definitions use introductory material; more specific questions require evidence matching the requested answer type. Matching a related article alone is insufficient.
- Multiple known meanings prompt for clarification. Unknown entities are not discarded just to match a nearby known topic.
- Causal checks require the causal language near the topic; selected sentence windows must retain the requested property. Comparisons need an explicit source contrast. Text remains extractive, sometimes using two non-adjacent sentences from the same paragraph.
- Short pronoun follow-ups can reuse the immediately preceding factual topic from the current conversation. Conversation state remains isolated between visitors.
- News, current officeholders, forecasts, prices, versions and other freshness-sensitive requests bypass stored answers. Practical medical/legal/financial guidance is also excluded from the static snapshot. Existing unsupported live-score/fixture/price feeds remain unsupported.
- An explicit request to search, browse or verify on the web bypasses local memory. A question *about* the Internet can still be static.
- On a miss, verified Wikipedia text can be fetched and retained in `data/knowledge_online_023.sqlite`. Only canonical public article content/metadata is stored, not the visitor's prompt/history. This on-demand store expires references after 30 days and is capped at 5,000 articles. A current-information result is not silently saved as a stable fact.
- Provider allowlists and the prior free-commercial source audit remain in force. This is broad-topic Wikimedia retrieval plus the existing specialized sources, not an unrestricted crawler for arbitrary sites or a connector to every live dataset.

## Verification and actual limits

With transport disabled, **97/100 systematically sampled known-title questions** were answered locally. These are coverage probes over stored topics, not independent correctness tests, arbitrary-user questions or a real traffic cache-hit estimate. Six controls confirmed current questions, explicit web requests, unknown subjects and practical guidance bypassed the static memory. The local 100-question check took about 0.06 seconds after adding passage row-range indexes; public round trips include worker/tunnel overhead.

A real long-tail lookup for a Rydberg polaron made two provider calls. A fresh engine instance then answered the same stable question with network access deliberately disabled, demonstrating persistent reuse beyond a transient HTTP cache.

All **86 automated tests** pass, including zero-network local answers, attribution, ambiguous terms, stale references, refreshed-source precedence, conversation follow-ups, HTML media/script/reference exclusion, damaged-text rejection and incidental-cause rejection. Public worker verification exercised local definitions, the sky's colour, bicycle mechanics, ambiguity, the persisted long-tail reference, live weather, current officeholders and explicit web search, with cross-session result access denied.

Development probes informed the evidence rules. Some process/comparison answers remain incomplete or overly technical; unsupported questions can still abstain or fall back to the internet. No large language model was trained, and arbitrary reasoning, coding, recommendations, multi-hop questions and unrestricted data-source coverage are not solved. More text increases stored coverage; it does not by itself establish reliable understanding of every request.

## Files

- `models/cael-knowledge-v1/knowledge.sqlite`: frozen local text index.
- `models/cael-knowledge-v1/ranker.json`: token statistics, passage weights and row-range lookup index.
- `models/cael-knowledge-v1/query_policy.json`, `query_report.json`, `report.json`: question model and reports.
- `research/knowledge_023/manifest.json`, `batches/`: frozen public-text provenance.
- `research/knowledge_023/offline_verification.json`, `persistent_live_verification.json`, `public_verification.json`: verification evidence.
- `cael_unified/collect_knowledge.py`, `train_knowledge.py`, `calibrate_knowledge.py`, `knowledge.py`, `knowledge_query.py`, `knowledge_html.py`: collection, training and runtime.

Index SHA-256: `67d6cfc619156651eb1b6269c1925bc065a99a713d36dfb60579e1dba866d948`.

Collection and fitting have completed. The shared worker and existing tunnel remain running; no GPU job was needed for this text update.
