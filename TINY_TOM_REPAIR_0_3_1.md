# CAEL unified: non-neural fitting repair

Owner approves automata and other non-neural hybrid methods. Neural networks
and transformers are prohibited. All unified runtime Python files, root cael.py
and chat.py stay byte-for-byte unchanged; hashes are recorded. The same existing
statistical count/association architecture and model format remain in use.

The earlier fitter used a surrogate objective and unstable updates. This repair
uses analytic gradients of the ACTUAL native mean-word continuation likelihood,
including context retrieval, full-vocabulary normalization, probability floors
and the existing prefix-count mixture. A bounded L-BFGS-B line search rejects
worsening trial updates; every accepted step is checked for non-increasing
regularized loss. No neural/autograd package, embedding or attention is used.

Small bounded experiment: 930 original paired training cases plus 1,024 public
training-only replay questions. Seven curriculum families cover roles, nested
belief statements, observation access, event order, absence, negation and private
recipients. Training/development/confirmation prose structures and fillers are
separate. Development has 306 original questions plus 320 SEEN external regression
questions. Original confirmation has 312 questions, grouped in 156 pairs. This
is project-authored structural testing, not an independently curated benchmark.

Existing context/answer/global/prefix count tables receive TRAIN rows only.
Retriever, vocabulary, feature families and inference algorithms stay fixed.
Only a training-selected block of existing association coefficients is fitted;
three arms use existing prefix_weight settings 0, .25 and .5, with at most 30
accepted iterations each. Same-word role reversals remain a declared capacity
stress test; passing them is not promised.

Preflight passed: 180 finite-difference checks, maximum gradient discrepancy
2.8e-11, native synthetic score error below 4e-15; real public/authored texts at
all three prefix settings matched uncached native scores within 2.6e-13. Extreme
logits, two-to-five choices and oversized rejected steps were checked. All 18
targeted runtime tests passed. None of these checks were project-model training.

The new training run is now owned/recorded in research/tom_031/process.json.
Live state: status.json and training.log. A one-shot completion supervisor
records completion_process.json/completion.log, audits hashes, evaluates the
development-selected winner once on original confirmation, and allows one more
disclosed Tiny ToM check only after >=10-point robust pair improvement with no
>2-point seen external regression. No benchmark-driven retraining or deployment.

Only retained free commercial CC BY/MIT data and original authored scenarios
are used. No MICA data, private photos, image generation, release edits, live
worker restart, neural networks or transformers. Attribution accompanies models.


## Completed evidence

Prefix setting 0.0: native regularized training loss 0.478987 → 0.400864; 22 accepted iterations, all non-increasing. Optimizer: CONVERGENCE: NORM OF PROJECTED GRADIENT <= PGTOL.

Prefix setting 0.25: native regularized training loss 0.526787 → 0.449920; 30 accepted iterations, all non-increasing. Optimizer: STOP: TOTAL NO. OF ITERATIONS REACHED LIMIT.

Prefix setting 0.5: native regularized training loss 0.558957 → 0.488745; 25 accepted iterations, all non-increasing. Optimizer: CONVERGENCE: NORM OF PROJECTED GRADIENT <= PGTOL.

Structural confirmation robust-pair macro gain: +9.52%. Seen external regression gate: False.

Fresh structural/regression gate not met. Tiny ToM not rerun; prior best remains 31.35%.

No neural networks/transformers or architecture changes. Experimental checkpoints not deployed. Full evidence: research/tom_031/summary.json and audit.json.
