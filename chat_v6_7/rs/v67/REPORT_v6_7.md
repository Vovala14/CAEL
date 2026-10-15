# CAEL v6.7 (2026-10-15): v6.6 + symbolic layer (rule parser, Wikidata graph, SymPy maths)
## Results (author labels on panels, not blind; panel_sc1 was seen before)
| | panel_sc1 no big mistake | panel_sc1 helpful |
|---|---|---|
| v6.6 | 99/100 [94.6-99.8] | 10/100 [5.5-17.4] |
| v6.7 | 99/100 [94.6-99.8] | 10/100 [5.5-17.4] |
v6.7 changed 0/100 panel_sc1 replies, 1/150 on dev panel_v2 (Costa Rica languages -> Spanish, from Wikidata).
Fresh check set (auto-scored; 100 NQ-open TRAIN + 50 GSM8K TRAIN by hash, NQ items removed from the store):
| | NQ correct / refused / wrong | GSM8K correct / refused / wrong |
|---|---|---|
| v6.6 | 3 / 95 / 2 | 0 / 49 / 1 |
| v6.7 | 3 / 95 / 2 (identical) | 0 / 49 / 1 (identical) |
Per-engine hits on the check set: kg67 0 (11/100 NQ questions parsed, all refused: entity not found / not a single entity), math67 0/50.
The 3 NQ hits come from the v6.5 QA store; the GSM8K wrong answer comes from the v6.6 one-step word-problem skill, not math67.
On author-written demo prompts (demo67.log) the engines work: multi-hop capital-of-birth-country, comparisons, counts, age at death, equations, systems, calculus.
## Why no gain on the panels/check
OASST prompts are not factoid questions; NQ questions are lower-case trivia about films/TV/sports that the hand grammar does not parse or Wikidata lacks; GSM8K needs multi-step reasoning that the strict rule extractor refuses (tuning slice: 5 right / 3 wrong of 2,000 before the final guards).
## Store
Wikidata truthy dump streamed (71.08 of 71.68 GB compressed; mirror stalled at the very end, newest ~Q124.6M+ items missing), filtered to 64 core properties + English labels/aliases:
465M lines -> 215.7M facts, 61.6M entities, 51.8M label/alias rows, integer IDs, DuckDB 3.9 GB (kg67.duckdb, box only). 42 labels/1,386 aliases backfilled from the Wikidata API (CC0).
Prominence for disambiguation = own + incoming facts. Units are not in the truthy dump, so height/area/length comparisons are only made between items of the same class.
## Known issues
"Kapiolani Medical Center" for Obama's birthplace (Wikidata's value, correct but hospital-level); Georgia -> the country (Tbilisi) by prominence; "Hamlet", "Mona Lisa", "Pride and Prejudice" refused as ambiguous (editions/adaptations); single-name people refused.
## Hand-written
Grammar/patterns, relation table, domain checks, ambiguity rule, templates, word-problem rules, refusal lists, labels. SymPy does the algebra; Wikidata provides facts.
