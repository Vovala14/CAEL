# Chat and helper runtime update — 0.4.4

Updated 18 October 2026 (local time). The running app and published bundle remain
**CAEL 0.2.3**. This is a local runtime update, not a new published release.

## Project status after Claude's updates

- The public worker now serves 0.2.3; its old process metadata still said 0.2.2.
  The recorded metadata has been corrected against the actual worker health and
  verified 0.2.3 bundle hash.
- Claude extended the existing symbolic reasoner with case analysis, contradiction
  handling and more story/event reasoning. See `REASONING_0_4_2.md`.
- The latest saved five-test whole-system results are HellaSwag 27.93%, ARC Easy
  62.12%, ARC Challenge 31.66%, PIQA 58.65%, ArithMark-3 69.50%; mean 49.97%.
  See `research/leaderboard_040/test_report2.json`. These use local evidence and
  exact word-problem arithmetic alongside the count language model. They are
  neither a fresh run for this update nor directly comparable to older pure
  language-likelihood scores. No official leaderboard submission is claimed.
- Claude's overnight image expansion was healthy and reached 37/342 units at
  01:09:42 local time. Its supervisor processes (2988/8016) and public tunnel
  process (25420) were preserved. This work did not modify image generation,
  view training images, or assess image quality.

## Added behavior

1. **Conservative typo interpretation.** A fitted word/bigram model repairs
   one-character errors and adjacent transpositions in supported chat controls.
   For example, `cna yuo caluclate 20 percnt of 50?` now yields 10.
   The interpretation is disclosed under **About this result**. Names in subject
   positions, quoted text, code, paths, URLs, numbers and negation receive
   conservative protection. Image, emoji and multiple-choice requests bypass
   this new preprocessing, and `score_endings` is unchanged.
2. **Multi-turn premise reasoning.** Start with `Facts:`, append with `Add:`,
   ask a question and then `why?`. Existing proof/state/constraint algorithms
   solve the reconstructed scenario and cite supporting premises. `Clear
   premises` and a new `Facts:` scenario reset the context. Premises exist only
   in the supplied conversation; no shared per-user training state was added.
   Unrelated factual questions can still reach normal knowledge lookup.
3. **Exact helpers in natural wording.** Polite arithmetic requests, percentage
   parts/changes/discounts, simple unit conversions and one-variable linear
   equations use bounded parsers and exact rational arithmetic. Calculations
   support `multiply that by 4`, `divide that by 5` and `why?`, using only a
   verified preceding calculation. Explanations list operations in dependency
   order. Unsupported nonlinear equations and undefined operations get a clear
   response rather than an invented numeric answer.

Examples tested through the public worker:

```text
Could you calculate (17 + 8) * 3?  -> 75
divide that by 5                  -> 15
why?                             -> calculation steps
Solve 7x + 4 = 53                -> x = 7

Facts: Mira is a rover.
Add: All rovers are machines.
Add: All machines are physical.
Is Mira physical?                -> Yes, with the three supporting premises
why?                            -> the supporting proof is replayed
```

`What year was Metallica formed?` also returned a sourced local-knowledge answer
containing 1981 through the live worker. This confirms the existing lookup route
still works; the band fact was not hardcoded into this update.

## Fitting, sources and limitations

The new checkpoint is `models/cael-text-repair-0.4.4-r1/model.json`, SHA-256:

```text
077156ba3be0ced1c471a1ca7d645052445b674253a717daf39aaf9a7c4410f1
```

Its correction targets/counts come from 116 authored phrase observations (112
distinct). A guard of 17,332 common alphabetic words, derived from the existing
FrequencyWords/OpenSubtitles 2018 list, prevents rewriting valid words such as
`want` into `went`. The publisher declares CC BY-SA 4.0 for the content:
<https://github.com/hermitdave/FrequencyWords#license>. The derived checkpoint
retains attribution, the source hash, modification description and full licence;
the public sources page credits it. No paid or non-commercial-only data was added.

This is a small non-neural count model and authored helper/context code. No
neural network, transformer, new language architecture, private conversation
training or benchmark-answer training was introduced. Existing language,
story, prompt, choice and image selections are unchanged.

It does **not** correct arbitrary spelling or understand every question. It
deliberately leaves ambiguous valid-word substitutions alone (`tried`/`tired`),
protects code-like calls, and misses some multi-edit and factual-noun typos.
Premises still need to fit the existing reasoner's supported grammar. Helpers
are bounded exact solvers, not unrestricted programming or general algebra.

## Verification and deployment evidence

- **235 regression tests passed**, including conversation, memory, explanation,
  code generation, reasoning, knowledge, lookup, count language, choice, unified
  routing and shared-worker/session tests. See
  `research/chat_044/tests_selected.log` and `tests/test_chat_044.py`.
- Authored development diagnostics: 120/120 added helper cases, 6/6 multi-turn
  deduction/why sequences, 16/20 typo cases, 64/64 valid controls unchanged.
  These are focused development checks, not an independent benchmark or a
  general intelligence score. Names/numbers vary; phrase counts were not fitted
  on the cases. The vocabulary guard was refined after the initial development
  run, which is preserved as `evaluation_initial.json`.
- The original low-level arithmetic parser alone handled 0/120 of those newly
  phrased helper cases; that comparison measures the added parser coverage,
  not the entire old unified model's overall accuracy.
- Twelve synthetic text-only requests passed through the public HTTPS job API.
  Thinking GIF and source attribution are served, and another browser session
  receives 404 for the test job. See
  `research/chat_044/public_verification.json`.
- Only the recorded, ownership-checked worker was reloaded. The existing tunnel
  URL and session key were retained. Worker PID after reload: 25792.
  See `research/chat_044/deployment.json`.
- Active selections were archived before adding only `text_repair`. The two
  benchmark chooser source hashes still match the selected configuration.
- All failed/initial experiments, strong checkpoints, published bundles and
  release copies remain available. No Git commit, push or new release was made.

Public link: <https://zen-changing-stock-jason.trycloudflare.com>

Reproduce the bounded checks with the configured scientific Python environment:

```powershell
& 'C:\Users\vlavrik\PycharmProjects\.venv-rocm\Scripts\python.exe' -m unittest tests.test_chat_044 -v
& 'C:\Users\vlavrik\PycharmProjects\.venv-rocm\Scripts\python.exe' -m research.chat_044.evaluate
```
