# CAEL 0.4.4: a thinking swarm and an extended ARC solver

**Chat thinks before it answers, as a swarm** (`think.py`):
- Nine exact readers each propose an answer to several readings of the question (as asked, all turns as one, number
  words as digits, statements apart).
- Each proposal is checked: the answer type must fit, and a word problem's number must be derivable from the stated
  numbers.
- The checked proposals vote; when two fully checked answers disagree, CAEL asks which reading was meant.

**New readers:**
- `everyday_exact` and `everyday_more`: about 65 everyday shapes, such as money, rates, clocks, calendars,
  corrections, newer or retracted sources, and the latest value of a fact.
- `constraint_logic`: line-ups by exhaustive search, and if-then rules.
- `explain_more`: about 60 short explanations.

**A final answer guard** replaces off-topic replies to the user's own situation with an honest "I can't work this out".

**ARC:**
- 37 new families in `arc_solver.py`;
- a union swarm of drawing specialists, a leave-one-out self-check, wider two-step search, and a fit cache.
- Results: ARC-AGI-1 evaluation **62/400** (pass@2, 10 s per task, CPU), ARC-AGI-1 training 152/400, ARC-AGI-2
  evaluation 0/120.
- New `evaluate_arc.py` reproduces the ARC numbers, and the per-task results are in `results/`.

Details: RELEASE_0_4_4.md.

**Fix after release (same version, 2026-11-21):** a follow-up that moves the last clock time ("delayed by 20 minutes")
could go the wrong way. Any "earlier", "less" or "sooner" anywhere in the message made it subtract, so 10:25 became
10:05 instead of 10:45. The reader now:
- takes the direction from the word nearest the amount;
- ignores negated words ("not earlier") and descriptive ones ("the earlier 09:40");
- asks only when the user leaves the direction open.

Regression tests are in `tests/test_time_followup_direction.py`.

**Fixes after release (same version, 2026-11-22 to 23):**

*Chat follow-ups* (`followups.py`):
- **Corrections:** "Sorry, it was 5, not 3" and "Actually it leaves at 09:10" are applied to the earlier turn.
- **What-if:** "And for 14 people?" and "What about 20%?" rework the previous question.
- **Questions about the last answer:** "How did you get that?", "Are you sure?", "In one sentence" and "More simply".
- **Questions about the chat:** "What was my first question?".
- **Statements:** plain statements get "Got it: …".
- **Settings:** "Set my … to …", "Scratch that, change it to …" and "Update that, use X as my … instead" are
  confirmed.
- **Next-message instructions:** "Summarize my next message in one sentence" and "State the main problem in my next
  message in five words or fewer".
- **Venting:** "Just let me vent, no questions or advice" gets a reply that only listens.
- **Small talk:** thanks, good-luck wishes, tips for an upcoming event, and reassurance after a setback.

*New solvers* (trusted readers in the thinking swarm):
- **`relations.py`:** orders, schedules, races, round tables (including clockwise) and who-has-what matching.
- **`staffing.py`:** gives each job to a different person from what each can do.
- **`time_engine.py`:**
  - the next departure;
  - the latest or earliest of listed times;
  - free windows across time zones, and two clocks on different offsets;
  - the time between two clock times;
  - "move it back / forward N hours", with "I meant earlier / later";
  - ordinal weekdays, working days, and ages on a later date.
- **`state_tracker.py`:**
  - ordered-list edits, statuses that flip, and swapped values;
  - counts per place, including named places ("Bay A", "top shelf"), "moves 9 to the bottom shelf" with no "from", and
    removals such as "borrows" and "checks out";
  - who has what after "X lent Y her bike" or "X lent his charger to Y";
  - the latest instruction in a chat;
  - the latest email, web address or phone number given.
- **`story_math.py`:**
  - word problems replayed on a running amount with units;
  - count stories such as "3 boxes with 12 bolts each, used 9" or "Out of four 15-roll trays, twenty-two were sold".
- **`number_puzzle.py`:** codes and numbers from bounds, kind and digit rules.
- **`missing_info.py`:** says what is missing when only comparisons are given, when a random choice hasn't happened
  yet, when records hide who it was, or when a count doesn't fit the shape.
- **`scoped_facts.py`:** the latest statement that applies to the case asked about, with scoped and withdrawn notices.
- **`everyday_choice.py`:** the option that meets every requirement, pay per use or a pass, the smallest unused
  number, and per-batch rounding.
- **`consistency.py`:** "All X are …" against one member, using an opposites table plus "non-", "un-" and "not".
- **`everyday_hard.py`:** 39 readers for everyday sums, calendar questions, puzzles, chat memory, sources and trick
  questions.
- **`induced_readers.py`:** 52 readers learned from verified examples (`induced_readers.json`).
- **`learned_rewrites.py`:** 3 learned rewording rules (`learned_rewrites.json`).

*Changes to existing readers:*
- Linear equations with coefficients are solved exactly ("3x - 7 = 20" gives x = 9), and the result feeds a following
  "then …" step.
- The line-up solver reads colours as the things in a row, "X won" and "the far right".
- The rate reader no longer answers questions about time.
- Seven new short explanations.
- Haiku, limerick and sonnet requests are read even with a style or word count, and a word count a form can't have
  gets a note.

*Answer guard:*
- **Kind of reply:** a reply of the wrong kind is replaced by an honest decline. That covers a template for a writing
  request, non-JSON for a JSON request, and "I can't access live data" for a question that needs no live data.
- **Topic:** template, forum and code replies must be about the request, sharing its distinctive words or the names in
  its code.
- **Statements:** a statement that mentions the weather no longer triggers a weather lookup.

Tests: `tests/test_followups.py`, `tests/test_everyday_hard.py`, `tests/test_induced_readers.py`, `tests/test_relations.py`,
`tests/test_time_engine.py`, `tests/test_state_tracker.py`, `tests/test_story_math.py`, `tests/test_number_puzzle.py`,
`tests/test_missing_info.py`, `tests/test_scoped_facts.py`, `tests/test_everyday_choice.py` and `tests/test_check_fixes_20261122.py`.

# CAEL 0.4.3: new chat desks and an ARC grid solver

Adds authored desks to the conversation team:

- the Host, with honest answers about CAEL, its web access and the time and date;
- the Programmer, with 83 Python topics, 31 error explanations, changes to the code just written and a library of 106 self-verified scripts;
- the Explainer, with 18 concepts and 22 everyday-science explanations, each with follow-ups;
- the Coach, with beginner guides, habits and ranked tips;
- the Ideas desk.

Also new: calculator sums for deposits, remainders, monthly splits, rates and savings goals; a wider Supporter that recognises serious situations without a feeling word; and a non-neural ARC solver.

Results:

- ARC-AGI-1 evaluation: 34 of 400 held out, up from 5.
- Sealed, blind-shuffled comparison against LFM2-700M on 24 conversations: CAEL 13 wins, 5 losses, 6 ties. Self-judged by the developer (a conflict of interest); p ≈ 0.10.

Details: RELEASE_0_4_3.md.

# CAEL 0.4.2: conversation team, fielded retrieval and the Supporter

Adds a fielded retrieval index (BM25F over title, tags, body and answer, a whole-conversation query with learned word associations and a British/American lexicon, and a confidence gate), conversation coherence that keeps follow-up answers on the user's thing, the Supporter for emotional conversations over several turns, story plots with real rewrites, shares and full-price discounts in the calculator, one-turn recipe scaling, moved bookings, and thank-you notes. Removes the unused chat_v6_7 engine and ten unloaded modules; CAEL now runs without the optional open-chat index. Sealed 20-conversation comparison against Gemma 3 270M IT: CAEL 12 wins, 7 losses, 1 tie (self-judged, not blind). Details: RELEASE_0_4_2.md.

# CAEL 0.4.1: conversation skills, chat memory and checked web answers

Adds exact conversation skills (quantities, rates, clock times, syllogisms, schedules, changed values, notes), chat memory over the conversation, and web answers that require a second independent source, on top of the unchanged 0.4.0 core engines and 0.3.7 resource bundle. Self-judged blind round against Qwen3.5-0.8B: CAEL about 796 Elo (Qwen 1000), 3 wins, 14 losses, 3 ties. Details: RELEASE_0_4_1.md.

# CAEL 0.4.0: core automata and rule induction

CAEL 0.4.0 upgrades actual non-neural symbolic/count/automaton engines: indexed rule propagation, validated sparse world transitions, finite-domain ordering up to twelve objects, iterative live references, deterministic count retrieval and bounded-checker interoperability. A new request-local learner infers finite discrete transitions from examples. Inherited weights, protected solvers, image/CA kernels and the public 0.3.7 resource bundle are byte-identical.

Fresh authored core confirmation: **60/60 positive answers versus 12/60** for 0.3.9.1; focused boundaries 16/16. These are known-family, maintainer/AI-assisted engineering cases, not broad English accuracy. Relevant regressions: 671 passed, four inherited conversation failures remain; 25 inherited failures fixed and 15 new unit tests added.

**Full official CellARC symbolic harness, same frozen checkpoint:**

| Metric | Interpolation (1000 tasks) | Extrapolation (1000 tasks) |
|---|---:|---:|
| Correct cells / total | 6361/11099 | 3815/10918 |
| Aggregate cell accuracy | **57.31%** | **34.94%** |
| Entire puzzles correct | **79/1000 (7.9%)** | **5/1000 (0.5%)** |

All 2,000 official-harness predictions and full replies reproduce the original run. No scorer/loader or checkpoint tuning; only support pairs/query reach CAEL. Eight interpolation clarifications count fully wrong. No runtime errors. The exact script, pinned sources, original outputs, input hashes, licences and reproduction command are in `benchmarks/core_040/REPRODUCE.md`. This harness rerun is a reproduction, not a new unseen confirmation. Most predictions include empirical/backoff guesses; exact extrapolation remains weak. Official leaderboard inclusion requires maintainer review; no accepted rank or general-chat/Qwen win is claimed.

The source ZIP and unchanged 562,714,794-byte `cael-0.3.7.cael` resource archive are both required. This is a custom Python runtime, not a Transformers checkpoint. Use Python 3.12 and the README instructions. CAEL remains non-commercial source-available; third-party data/code licences and attribution are retained. CellARC's actual dataset LICENSE is CC BY 4.0 despite its MIT card tag.

This publication does not change the Vynly worker or tunnel. Historic frozen reports describe their completion time; later owner-authorized publication does not rewrite them.


---

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
