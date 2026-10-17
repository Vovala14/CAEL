# CAEL additional benchmark-skill training 0.3.4

One bounded non-neural training experiment; runtime architecture unchanged.
Training partitions: ARC, PIQA, QASC, AQuA, plus retained licensed earlier data.
No five-test answers, HellaSwag training, ArithMark training, MICA data, private photos or neural teachers.

Fresh confirmation before target rerun:

| Source | Incumbent | Candidate |
| --- | ---: | ---: |
| AQuA | 25.59% | 30.31% |
| ARC-Challenge | 21.74% | 28.26% |
| ARC-Easy | 25.59% | 36.36% |
| PIQA | 47.67% | 57.33% |
| QASC | 14.59% | 17.76% |

Fresh-source accuracy macro gain: +6.97 percentage points.
Answer-frequency-only controls are retained in confirmation.json; choice accuracy is not proof of general math reasoning.

All 16,428 target questions scored once using the development-selected checkpoint through the native unified API.
Same pinned inputs and character/token normalizations as 0.3.3. No calculator, web lookup or per-task model choice.

| Test | Incumbent CAEL | Candidate | Difference |
| --- | ---: | ---: | ---: |
| HellaSwag | 27.97% | 28.48% | +0.51 pp |
| ARC-Easy | 26.60% | 40.03% | +13.43 pp |
| ARC-Challenge | 22.18% | 26.79% | +4.61 pp |
| PIQA | 48.91% | 57.62% | +8.71 pp |
| ArithMark-3 | 37.80% | 34.80% | -3.00 pp |

Five-test mean gain: +4.85 percentage points.
This is a disclosed repeated public evaluation using the custom native runner, not an official LM-eval/organizer result.

Promoted through existing language override: False.
Requested dramatic benchmark improvement achieved: False.
No automatic retraining or external submission. Existing story/helper/image/portrait/emoji selections retained.
Evidence: data_report.json, optimizer_data.json, coefficient traces, selection.json, confirmation.json, summary.json.

Final review passed: all data/source/runtime hashes and 16,428 benchmark row counts verified. The native development replay differed on two numerical ties; per-choice likelihood discrepancies were below 6e-13, and the original optimizer selection score was reconstructed exactly. Target and confirmation scores used the actual native API throughout. The selected checkpoint is the newly trained count-table refit (iteration 0); 12 and 23 additional accepted coefficient steps lowered training loss but did not improve development selection. The initial failed attempt and its 28 unsupported training rows remain documented in the earlier experiment folder. Current selected unified checkpoint remains 0.3.2 because this candidate missed the predeclared 5-point mean promotion threshold (actual +4.85 points) and regressed in arithmetic. No further job or automatic retraining remains.
