# CAEL whole-system multiple choice 0.4.0

Requested on 2026-10-17: train CAEL for the leaderboard tests. CAEL cannot be submitted to public LLM leaderboards (they
require neural models in a standard format), so this targets the five public benchmarks run locally: HellaSwag
validation, ARC-Easy test, ARC-Challenge test, PIQA validation and ArithMark-3.

## Rules (owner's decisions)

- CAEL may use all its built-in modules when answering: the count language model, its **local offline Wikipedia
  snapshot** and an **exact word-problem arithmetic engine**. This is a **whole-system** score, not a pure
  language-model score. There is no internet access, no test labels in anything fitted or chosen, and no neural
  networks.
- **Promotion gate:** +5 points mean over the live 0.3.2 configuration, with no test worse by more than 3 points.

## Method (`cael_unified/choice.py`, `cael_unified/wordmath.py`)

1. **Language model:** the live 0.3.2 count model scores every option (character-normalised log-likelihood).
2. **Evidence:** for options of up to 15 words, a BM25 search of CAEL's local Wikipedia passages (349,568 passages, FTS5)
   for text containing both the question's and that option's own words — the classic information-retrieval solver.
   Language and evidence scores are standardised within the question and combined as `lm + 3 × evidence`.
3. **Exact arithmetic:** authored rules for short word problems (add, subtract, compare, multiply, divide, two-step).
   The engine answers only when exactly one option states its computed number; otherwise it abstains.

## Protocol

- **Arithmetic engine:** developed on 300 authored problems and checked on 300 differently worded authored problems:
  265 right, 35 abstained, **0 wrong**. No benchmark text was used. Disclosure: inspecting the file format showed four
  ArithMark-3 test items with their labels; they were not used for development.
- **Evidence weight and option-length cut-off:** chosen on development data only (official ARC validation, held-out PIQA
  training groups, QASC/AQuA validation; the 0.3.2 model was not fitted on these). The choice was weight 3, cut-off 15,
  which is the edge of the searched grid; gains had flattened (+0.15 points between weights 2 and 3).
- **Confirmation (checked once):** ARC-Easy 25.6% → 52.5%, ARC-Challenge 21.7% → 27.5%, QASC 14.6% → 38.1%,
  PIQA 47.7% → 48.5%, AQuA 24.0% → 22.8%.
- **Test sets, scored once:** used the language-model likelihoods recorded by the 0.3.3 evaluation, verified to come from
  the same live model (SHA-256 `b2e27bb7…`).

## Results (`research/leaderboard_040/test_report.json`)

| Test | Live 0.3.2 | Whole system | Change |
| --- | ---: | ---: | ---: |
| HellaSwag (10,042) | 27.97% | 27.74% | −0.23 |
| ARC-Easy (2,376) | 26.60% | **53.24%** | +26.64 |
| ARC-Challenge (1,172) | 22.18% | **28.75%** | +6.57 |
| PIQA (1,838) | 48.91% | **53.21%** | +4.30 |
| ArithMark-3 (1,000) | 37.80% | **55.10%** | +17.30 |
| **Mean** | **32.69%** | **43.61%** | **+10.92** |

**Gate passed** (+10.92 mean; worst change −0.23).

- **Exact arithmetic engine on ArithMark-3:** it answered 466 of the 1,000 questions and was right on 376 (80.7%); it
  was 100% on authored problems, so ArithMark's wording defeats it about 1 time in 5. The remaining 534 questions use
  the language model and evidence path (32.8%).
- **HellaSwag** is essentially unchanged. Evidence helps the 1,620 short-ending items (33.1% vs 26.7%), but the overall
  score is flat. PIQA's gain comes from items with short options.
- **Scope of these numbers:** they are local custom-runner scores for the whole system, not official leaderboard results
  and not comparable to pure language-model scores. Large neural models score 85–95%+ on these tests.

## Deployment

- `choice` entry in `research/active_models.json`: weight, cut-off and the SHA-256 of the evaluated `choice.py` and
  `wordmath.py`. Changed code is refused. Earlier selections are backed up in `research/leaderboard_040/`.
- In chat, multiple-choice questions now use the chooser, with options on separate lines or inline ("…? A) x B) y").
- The live worker now runs under `../.venv-rocm`. The system Python lacks `joblib` and `scikit-learn`, so the language
  model could not load there.
- 248 tests pass, including new `tests/test_choice.py`.

## Next

- Raise the arithmetic engine's coverage and precision using new authored or training-split problems, never ArithMark
  items.
- Add a larger science corpus (for example the CC BY-SA ARC Corpus) for evidence, which needs a download.
- Try the stronger 0.3.6 language candidate as the language component.
