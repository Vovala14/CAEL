# CAEL 0.4.4: a thinking swarm without a neural network, and 62/400 on ARC-AGI-1

CAEL is a chat and reasoning system that contains **no neural network**: no transformer, no embeddings model, no
learned layers, and no gradient training anywhere in the reply path. It runs on a CPU. Its answers come from small
programs that read, compute, check and vote.

**0.4.4 brings two things:**
- **A "think before answering" swarm for chat.** Many small exact readers each propose an answer to several readings of
  the question; every proposal is checked, and the checked answers vote.
- **A larger, self-checking ARC grid solver.** It solves **62 of the 400 ARC-AGI-1 evaluation tasks (15.5%, pass@2)** in
  10 seconds per task on a CPU, with no neural network and no task-specific code.

Everything here can be checked on your own machine, as shown below.

---

## 1. ARC-AGI-1: 62 / 400 with a non-neural solver

| Set | Tasks | Solved (pass@2) | Notes |
|---|---:|---:|---|
| ARC-AGI-1 **evaluation** | 400 | **62 (15.5%)** | 10 s per task, CPU only, one run |
| ARC-AGI-1 training | 400 | 152 (38.0%) | the set the solver was developed on |
| ARC-AGI-2 evaluation | 120 | 0 | still out of reach |

**Rules:**
- **Two attempts per test input.** A task counts only if every one of its test outputs is matched exactly by one of the
  two grids.
- **The solver never sees the answers.** It gets only the demonstrations and the test inputs; the answers are compared
  in a separate parent process.
- **Ten seconds per task.** Each task runs in its own process with a 10-second limit, and running over counts as a
  failure.
- **Ordinary hardware.** The published run used 16 tasks side by side on a desktop CPU (Ryzen 9 9900X).
- **Per-task results ship with the release:**
  - [`results/arc_agi_1_evaluation_0.4.4.jsonl`](results/arc_agi_1_evaluation_0.4.4.jsonl)
  - [`results/arc_agi_1_training_0.4.4.jsonl`](results/arc_agi_1_training_0.4.4.jsonl)

### Reproduce it

```bash
git clone https://github.com/Vovala14/CAEL && cd CAEL && git checkout v0.4.4
python -m pip install -r requirements-unified.txt
git clone https://github.com/fchollet/ARC-AGI
python evaluate_arc.py --data ARC-AGI/data/evaluation --out results/my_arc_eval
```

Neither the solver nor the evaluation script needs the resource bundle. A full run takes about 3 to 5 minutes
with 14 to 16 workers. Your count may differ by a task or two:
- a task near the 10-second limit can finish or time out depending on the machine;
- a slower CPU or more parallel workers will push borderline tasks over the limit.

Compare your file task by task with ours. `--seconds 30` shows how much of the gap is time rather than reasoning.

### How the solver works (`cael_unified/arc_solver.py`)

Every candidate rule must reproduce **all** demonstration pairs exactly before it may predict anything. Among the rules
that do:

- **Description length decides.** Rules are ranked by a rough step count, plus a small prior per family taken from how
  often that family was right on practice puzzles.
- **Augment and vote.** The task is solved under all 8 rotations and reflections, each answer is mapped back, and equal
  answers pool their votes (one vote per view).
- **Think before answering: a leave-one-out self-check.** When different answers compete, each leading rule is learned
  again with one demonstration held out and must predict that demonstration. Rules that generalise beat rules that only
  memorised.
- **A swarm of drawing specialists.** When the output adds several colours, a different family (stamps, spans, boxes,
  rays) may explain each colour. Each is fitted on its own colour, and their drawings are merged.
- **Two-step composition.** A shape-changing first step (crop, lattice, grammar operation) can be followed by a
  same-shape rule.
- **Two answers, never the input.** The two best different answers are returned. Copying the test input is never
  offered.

There are **53 solver programs** in all, many with several variants. The ones new in 0.4.4 are:

| Kind | Families |
|---|---|
| Drawing | stamps around cells and around whole objects; spans between same-coloured cells (with crossing priority); rays from every coloured cell; alternating-colour rays; bounding-box and corner-box fills; rectangle interiors by size rank |
| Rules with a parameter read from the input | scale or tile by the number of colours; fill with the commonest or rarest colour; a one-property classifier (symmetry, object count, connectedness, ...); per-row and per-column rules; edge padding; recolour by a lone marker; shift with a colour map |
| Picking and cropping | the odd, asymmetric or densest block; corner and centre crops; corner and block overlays with a learned priority; new object selectors (symmetric, asymmetric, touching a marker, with a hole) |
| Repairing patterns | fill the hole in a periodic pattern, or output only the missing patch; repeating-unit extraction |
| Counting and sorting | count bars and count lines; sort bars by length; size-rank recolouring |
| Swarm and thinking | union of specialists by colour; leave-one-out self-check; fit cache across a task's test inputs |

**Honest notes:**
- **All solver families were developed on the ARC-AGI-1 training set.** Each new family was written after looking at
  unsolved training tasks, then kept only if it lost no previously solved task on training and on an ARC-AGI-2
  training split.
- **The evaluation set is not untouched.** It was scored at five development milestones, and nothing was changed with
  its results in view. So 62/400 is a repeated look, not a single blind shot. That is one more reason to rerun it, and
  to try a set CAEL has never seen, such as [ConceptARC](https://github.com/victorvikram/ConceptARC). We would like to
  hear what you get.
- **The solver is hand-written search,** and each family adds a few tasks. The big remaining groups:
  - object-correspondence rules: move or copy each object to its marker;
  - multi-step compositions beyond two steps.

---

## 2. Chat: thinking with a swarm

A reply is not generated word by word. It is **found, checked and agreed on**:

```
question ──► readings ──► swarm of exact readers ──► checks ──► vote ──► answer guard ──► reply
               │                 │                       │           │            │
   as asked, all turns   nine readers, each      answer type;   readers that   a reply that is not about
   as one, number words  reads one kind of       sums must be   agree, across  the user's own situation
   as digits, statements problem completely      derivable from readings, win; becomes an honest "I can't
   split from question   or stays silent         the stated     two checked    work this out" instead of
                                                 numbers        answers that   an off-topic one
                                                                disagree → ask
```

- **Readings** (`think.py`). The same question is read several ways: as asked; with all of the user's turns as one
  message; with number words turned into digits; and with the statements split from the question.
- **The swarm.** Each reading goes to every exact reader:
  - `everyday_exact` and `everyday_more`: about 65 everyday shapes, such as pack sizes and change, discounts then tax,
    rates with idle time, clock and calendar arithmetic, ages, time zones, weekday of a date, corrections ("make that
    21"), newest notice wins, retractions, the latest value of a fact, and items added to or removed from a set;
  - `constraint_logic`: queues, rows, races and line-ups, solved by trying **every** order and keeping those that
    satisfy all the statements. It answers only what all surviving orders agree on, or says it can't be determined. It
    also handles if-then rules, flagging the two invalid forms;
  - `word_math` (story sums), `recall_did` ("Where did I park?") and the labelled-account swarm desk (sources that
    disagree, correct or copy each other);
  - `explain_more`: about 60 authored short explanations.
- **Checks.** Each proposal is checked on its own:
  - the answer type must fit the question (a number, a clock time, a weekday, a yes or no);
  - for word problems, a search finds the derivation of the proposed number that uses the most of the user's stated
    numbers. An answer that leaves numbers unused, or can't be derived at all, is marked down.
- **Vote.** Proposals are grouped by answer, and independent readers and readings that agree add support. When two
  fully checked answers disagree, CAEL asks which reading was meant instead of picking one.
- **Answer guard** (`answer_guard.py`). After the whole team has answered, one last check runs. If the question is
  about a situation the user set up, and the reply is a web quote, an advice template, or a sum about something else,
  the reply is replaced by an honest "I can't work this one out reliably", which quotes what was asked.

Every reader shows its working ("21 (corrected) + 17 − 10 = 28"), and every reply carries a trace of which readers
agreed.

**Limits:** the readers are hand-written. They cover the phrasings and problem types they were written for, and new
types of problem fall back to CAEL's general pipeline, or now to an honest "I can't work this out". Wider coverage is
the main open problem, and it is where outside help is most welcome.

## 3. Footprint

- **Code and data:** the code is 7.5 MB of Python. The data is about 2.6 GB of tables and indexes, with no neural
  weights.
- **Resources:** one chat turn uses well under a second of CPU, except when it waits for a web lookup. Peak memory in a
  48-conversation run was 568 MB, and no GPU is used.
- **Web lookups:** public web sources (Wikipedia, Wikidata) are used for facts. Set `CAEL_WEB_SEARCH=0` for fully
  offline, repeatable runs.

## 4. Tests

- **The repository's tests:** `python -m unittest discover -s tests`, which is what CI runs.
- **New test files in 0.4.4:**
  - `tests/test_everyday_exact.py`
  - `tests/test_general_readers.py`
  - `tests/test_think.py`
  - `tests/test_answer_guard.py`
  - `tests/test_word_math_round6.py`
  - `tests/test_swarm.py`
- **ARC:** `evaluate_arc.py` as above.

## 5. Files

- **New:**
  - `cael_unified/think.py`
  - `cael_unified/everyday_exact.py`
  - `cael_unified/everyday_more.py`
  - `cael_unified/constraint_logic.py`
  - `cael_unified/explain_more.py`
  - `cael_unified/answer_guard.py`
  - `cael_unified/swarm.py`
  - `cael_unified/swarm_compute.py`
  - `cael_unified/evidence.py`
  - `cael_unified/word_math.py`
  - `cael_unified/recall_did.py`
  - `evaluate_arc.py`
- **Extended:** `cael_unified/arc_solver.py`, `team.py`, `assistant.py`, `advice_schemas.py` and `smalltalk.py`.
- **Architecture:** [ARCHITECTURE_0_4_4.md](ARCHITECTURE_0_4_4.md).
- **Resources:** the resource bundle is unchanged (byte-identical 0.3.7), and `python -m cael_unified --download`
  fetches it as before.

CAEL is [source-available, non-commercial](LICENSE). ARC-AGI is by François Chollet (Apache-2.0); this is our
evaluation, not an official leaderboard entry.
