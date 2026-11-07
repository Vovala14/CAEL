# 0.3.9.1 — 2026-11-07

Native bounded task interpretation and installed product metadata. Unchanged non-neural architecture and resource bundle. Fresh 900-question study: 777 correct, 123 abstentions; scope and limitations in RELEASE_0_3_9_1.md.

# Changelog

## 0.3.9 (2026-11-07)

Conversation follow-ups, explicit state, exact task rechecks, guarded choices,
complete literal positional/keyword examples, personal evidence attribution and
bounded source-linked comparisons. The tested legacy checker adapter is included
in the runtime entry point. No neural architecture or inherited resource-weight
change. Resource bundle remains byte-identical 0.3.7. Authored fresh useful
answers 10/29 -> 22/29 against the previous conversation development candidate;
this is not a standard benchmark or Qwen win. All remaining failures retained.
See RELEASE_0_3_9.md and the full reviewed evidence.

## 0.3.8

Code-only release. It loads the unchanged published `cael-0.3.7.cael` model bundle
(same SHA-256 checksum); no weights or bundle files changed. AI-assisted.

### Fixed

- Personal facts: CAEL no longer invents a personal fact it was never told (for example a
  birthplace). It answers from what the user said in the conversation, or says it has not
  been told.
- Listening requests: an emotional message that asks for no advice and no questions now gets
  a short reflection without advice or questions, for more phrasings than before.
- Word problems: a checked quantity graph handles more multi-step quantity problems
  (receive, give away, buy, share). The older exact inventory helper still answers first
  when it can, so its worked steps and multi-turn "Add:" state are kept. A leading
  "and"/"then" in a step is handled; "to" is no longer taken as part of a quantity noun.
- Linear equations such as `Solve 6*x + 5 = 47` are solved exactly.
- Python generation: the requested function name and signature are kept; a single function
  stub is checked against the request; prompts that contain real code plus extra steps are
  left to the task and data tools instead of being asked to clarify.
- Code execution: generated specs and recurrences run only inside the restricted Python VM
  (no native `eval`). The VM gained a bounded `dict.fromkeys`.

### Evaluation (read-only, no tuning on evaluation items)

- 80-item read-only replay, raw automatic grading: 59/80, against 54/80 recorded for 0.3.7
  (memory 17/20, conversation 10/20, Python 16/20, controls 16/20). Seven replies changed:
  memory-20, conversation-04, python-15 and controls-05 now pass; controls-16 now passes the
  automatic check (it had been accepted in review before); python-05 and python-19 still fail.
  Memory-20 is the item from the public bug report, so it is no longer a clean held-out item.
  Review of the replies was done by AI coding agents (unblinded).
- Public 128-question comparison: math 0/32 and Python 1/32, the same as 0.3.7. CAEL does
  not pass the competitive math gate and 0.3.8 makes no math improvement claim.
- GSM8K train split, 400-question development check (informational only): 1 correct, 17 wrong, 382 abstained. Coverage is very low and the 17 wrong answers come from routes that should have abstained.
- The 400-question comparison is unchanged: Qwen3.5 leads clearly (181/400 original phrase
  passes against CAEL 121/400; Qwen3 116/400). Qwen is also better at open conversation.

### Known limitations

- Bundle builds still name the bundle after the code version; 0.3.8 ships the 0.3.7 bundle.
- The restricted VM refuses `math.*` expressions.
- Word-problem coverage is still low; some routes give wrong numbers instead of abstaining.
- Python-19 still uses an import although the prompt asks for no imports.
