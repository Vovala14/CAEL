# CAEL v6.7 - frozen before the panel_sc1 run and the check-set run
v6.6 unchanged, wrapped by cael_v67.V6: safety first; then for single-turn prompts the integer CA router (V4M.route) decides:
- not small talk/greeting/creative writing -> math67 (rule extraction -> SymPy, verified by substitution / back-differentiation; word problems: rate x time and relative-quantity chains, strict refusal words);
- also not code, and not a dated/current question -> kg67 (hand-written grammar -> structured query: relation, multi-hop chain, comparison, count, age at death) over a Wikidata truthy integer-ID graph (CC0); refuses on ambiguous/unknown entities.
Tuning: panel_v2 (dev), hand-made examples, GSM8K TRAIN items ranked 50-2050 by hash (never the 50 check items). See TWEAKS.log.
Check set check67.jsonl (sha256 in check67.sha256): 100 NQ-open TRAIN + 50 GSM8K TRAIN by hash; the NQ items are excluded from the QA store at runtime. Auto-scored (string / final number match).
panel_sc1 has been seen before; author labels, not blind.
