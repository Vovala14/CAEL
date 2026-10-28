# CAEL 0.3.7 release/evaluation notes

This release packages frozen cael-session-affect-python-r2-20261028 with only
version/packaging labels and LF source normalization changed. Full source
equivalence is recorded in benchmarks/cael_cmp_r2_20261028/source_equivalence.json.
No image/portrait weights, opponents, private training data or conversations
are shipped. Existing CAEL and resource licences are retained.

All80 replies/system on the named local confirmation were reviewed. Reviewed
scores: CAEL57, Qwen3-0.6B43, Qwen3.5-0.8B41. Raw flags54,43,42 are preserved.
Candidate-only/opponent-only pairs:24/10 and27/11; exploratory exact paired
p-values .0243065 and .0138530. Lead after omitting a category stays positive:
+8.33..+28.33pp and+6.67..+33.33pp. These calculations assume independence;
authored capability-family correlation and unblinded author judgments limit
that assumption. They meet the prespecified scoped release criterion, not a
general superiority claim.

CAEL/Qwen3 had no caught errors, caps or VM-ungraded code cases. Qwen3.5 had
zero caught errors, one1024-token cap (failed repair) and two VM-ungraded
programs: correct list.sort code credited after inspection/manual traces,
invalid bracket code independently demonstrated wrong. No generated model
source ran natively. Post-hoc line/word diagnostic cases were applied equally
to all three unchanged functions; original primary flags and cases stay intact.
An unspecified correct two-sum argument order was credited to Qwen3 without
repairing its code. Minimal listening/unknown/negative-location leniencies
and all contradictory explanations are disclosed per item.

Development qualification:68 focused checks,12/12 new unified probes,
468 broader regressions+117 subtests (two native generated-repair execution
tests excluded), then12/12 full-portable preflight checks. Final artifact
checks are packaging regressions, not additional unseen capability evidence.
All failed development attempts remain in local research; no test was
replaced or source retuned against these viewed final questions.

Weights/CA kernels/selected choice.py and wordmath.py are unchanged. No
picture/portrait generator weights or excluded old previews are packaged.
The original167MiB source-only r1 result is separate; full-portable r2 peak
is558.648MiB. All performance numbers are one shared-host run, precision and
runtime settings differ, and model/archive/installed sizes are disk, not RAM.
