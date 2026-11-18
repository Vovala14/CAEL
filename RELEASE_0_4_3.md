# CAEL 0.4.3: new chat desks for Python, explanations, tips and support, and an ARC grid solver

CAEL 0.4.3 is a conversation release on top of the 0.4.0 core engines and the 0.4.2 conversation team. It is still
**non-neural**: no neural network or transformer produces its replies. The team gains new desks with authored, checked
answers. Each desk answers its kind of question and its follow-ups before any web search, so short follow-ups no longer
drift into unrelated forum quotes.

## What is new

### The Host: honest answers about CAEL itself (`cael_unified/about_me.py`)

- "Can you search the internet?" gets a true answer about CAEL's web lookups, not the dictionary definition of the
  internet.
- "What time is it?", "What's the date?", "What day of the week is it?" and "What time is it in Tokyo?" are answered
  from the clock. Times in about 100 cities include daylight saving rules for Europe, the US, Australia, New Zealand and
  Chile.
- CAEL answers questions about what it is, who made it, how it works, what it remembers and whether it can see images,
  truthfully. Asked whether it is a person or a program, it says it is a program.

### The Programmer: Python answers (`cael_unified/python_answers.py`)

- **83 authored Python topics**, each with a short explanation and a code example that the tests run. Topics include
  files, CSV, JSON, sorting, dictionaries, strings, loops, comprehensions, classes, exceptions, decorators and
  comparisons (list vs dictionary, list vs tuple, list vs set, `==` vs `is`).
- **31 error messages explained**, for example `NameError`, `TypeError`, `IndentationError` and `KeyError`: what each
  means, the usual cause and the fix.
- **Changes to the code just written:** "make it recursive", "add a docstring", "add type hints" and "what if the list is
  empty?".
- **Rewordings are found** by word overlap with each topic's text (BM25 with stemming and a synonym table, no model). A
  short follow-up takes its subject from the previous question.
- **A library of scripts CAEL wrote and verified itself.** There are 106 of them, all checked against an AST whitelist.
  The code writer uses them when its plain search finds nothing. The search also gains `zip(a, b)` and adjacent-pair
  loops.
- Lettered multiple-choice questions are no longer treated as sums.

### The Explainer and the Coach

- **18 concepts explained in plain words** (`concepts.py`), such as inflation, interest, mortgages, credit scores, pensions, recessions, vaccines and DNA.
  Each covers what it is, why it matters, an example and how it affects you, with follow-ups.
- **22 everyday-science explanations** (`everyday_science.py`): rain, snow, hail, thunder and lightning, fog, dew and
  frost, sky colour and sunsets, the seasons, Moon phases, autumn leaves, earthquakes, volcanoes, rust, bread and more.
  Each has the follow-ups someone who knows the subject would answer next: "Why is it sometimes snow instead?", "How far
  away is the storm?", "Why is it summer in Australia at Christmas?".
- **Beginner guides for 11 hobbies, plus habits** (`beginner.py`): procrastination, sleep and focus. They answer "What do
  I need?", "How long does it take?" and "What if it still doesn't work?".
- **Ranked tips** (`tips.py`) for groceries, energy bills, fuel, phone bills, eating healthier, screen time, keeping a home
  cool, studying and saving water. The tips are ordered by how much they usually help, so CAEL can answer "Which of those
  helps the most?", "Tell me more about the second one" and "Any others?" from the list it just gave.
- **The Ideas desk** (`ideas.py`) has ideas for children's and adults' parties, gifts, rainy days, dates, dinners and
  weekends, plus fun facts. Follow-ups such as "The second one, what do we need?" refer to the right idea.

### The calculator

- **Deposits and the rest:** "I pay 30% up front" is a share of the price. "What's left?" gives the remainder, and "Over
  4 months?" splits it.
- **New sums:**
  - paying an amount over several months, and tips added after a split;
  - stated rates ("my gym costs $45 a month") converted to a week or a year;
  - what's saved from earnings minus spending, and how long until a savings goal.

### The Supporter

The Supporter now takes the conversation when the situation itself is serious, even without a feeling word:

- someone close in hospital or having an operation;
- a death, including how to tell children and dreading a funeral;
- waiting for news (a job, a test result, an application);
- nerves before a flight, a drive or an interview, with answers to the hard interview questions;
- a friend moving away;
- a tradesperson who took the money;
- a child starting a new school;
- putting something off.

It still stays out when the user asks for no advice.

### The ARC grid solver (`cael_unified/arc_solver.py`)

A new non-neural solver for ARC-style grid puzzles, built only on ideas and puzzle data from Looped mdlARC (no model and no
generator code):

- it keeps every hypothesis that reproduces all the demonstrations;
- it ranks them by description length plus a small learned prior;
- it solves each puzzle under all 8 symmetries and pools the votes;
- it gives two different attempts.

New solver families include split-and-combine, tilings, mirrors, object cropping and recolouring, rays, counting,
denoising, fills, symmetry completion, local rules, periodic patterns, object gravity, lattices and two-stage programs.
The older grid engines use it when they cannot answer.

### Experimental: a terminal agent (`cael_unified/terminal_agent/`)

A small rule-based agent that plans and runs shell steps for simple file and text tasks, with a Harbor adapter. It has not
yet been run on Terminal-Bench (that needs Docker), so no score is claimed.

## Measured results

### Blind-shuffled comparison against LFM2-700M

24 new mixed conversations (43 turns) were written and sealed before either system ran. They covered Python, everyday
questions, emotional support, maths and follow-ups. CAEL ran with web lookups on, as it does live; LFM2-700M ran offline
with its makers' recommended sampling.

| Opponent | CAEL wins | Opponent wins | Ties |
|---|---:|---:|---:|
| LFM2-700M (LiquidAI) | **13** | 5 | 6 |

- **Where CAEL won:** the clock and questions about itself, all six everyday conversations, four of six emotional
  conversations (two ties), and the mortgage explanation.
- **Where LFM2 won:** a deposit sum, a Python comparison, a weather follow-up and a tips follow-up. All four were fixed for
  this release, and the fixes were then checked on a new sealed set (see below).

How it was run:
- Each whole conversation was judged with the system names hidden and the A/B order shuffled. The verdicts were saved
  before the key was opened.
- The judge is the developer of CAEL, which is a conflict of interest, and CAEL's style is recognisable even when hidden.
- 24 conversations is a small sample. The sign test on the 18 decided conversations gives p ≈ 0.10, a clear lead that is
  not significant at the 5% level.
- The comparison ran on the candidate before the last round of fixes.

### Checks of the last fixes

The fixes were checked once on a new sealed set of 16 conversations, with new wordings and scored by the developer:
**22 of 32**. The gaps it found ("how much remains", "a dictionary *instead of* a list", "the final element", and two
science wordings) were then fixed in general form. That check no longer measures those fixes.

### ARC-AGI-1

| Split | Before | 0.4.3 |
|---|---:|---:|
| ARC-AGI-1 evaluation (400, held out, run once, two attempts) | 5 | **34 (8.5%)** |
| ARC-AGI-1 training (400, used for development) | 43 | 113 |

Later development reached 44 of 400 on the evaluation split. That figure was measured after the split had been viewed, so
it is not a held-out result. ARC-AGI-2 evaluation stays at 0 of 120.

### Regression tests

The full suite has the same failures as 0.4.2 (24 inherited cases) and no new ones. The new tests cover each desk.

## Size and resources

Unchanged from 0.4.2:
- **Disk:** about 2.6 GB, nearly all data; the code is about 20 MB.
- **Memory:** about 100–230 MB.
- **Hardware:** CPU only, no GPU.

The new desks are authored text and small tables. The ARC prior file and the script library add about 60 KB.

## Install and run

Use Python 3.12. Download and extract `CAEL-0.4.3.zip`. For full chat, also extract `cael-open-chat-v1.1.zip` into
`models/` (unchanged from 0.4.2). Then:

```bash
python -m pip install -r requirements-unified.txt
python -m cael_unified --download
python -m cael_unified --ui
```

Open http://127.0.0.1:8765. Set `CAEL_WEB_SEARCH=0` to turn off public web lookup.

The resource bundle is unchanged (byte-identical 0.3.7). This is custom Python code, not a Transformers checkpoint.

## Honest limits

- Subjects outside the authored desks still depend on the index and the web, and a follow-up there can drift.
- ARC-AGI-2 puzzles remain beyond these solver families (0 of 120).
- The terminal agent is untested on Terminal-Bench.
- Some inherited tests outside the CI set still fail.
