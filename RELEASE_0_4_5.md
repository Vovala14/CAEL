# CAEL 0.4.5: chess, story reasoning, word problems, and 83/400 on ARC-AGI-1

CAEL is a chat and reasoning system with **no neural network**: no transformer, no embeddings model, no learned layers
and no gradient training anywhere in the reply path. It runs on a CPU.

**0.4.5 brings four things:**
- **Chess in chat**, against CAEL's own non-neural engine. It won every game recorded below.
- **A story world model** for "who is where, who has what, what happened before" questions: bAbI test 241 → 494/500.
- **Question-guided arithmetic** for everyday word problems with distracting numbers: SVAMP test 58 → 70/300, with no
  previously correct answer lost.
- **A broader ARC solver:**
  - It now has a compositional program search and a per-cell rule learner.
  - ARC-AGI-1 evaluation went from 62 to **83/400**.

---

## 1. Chess: play, analyse and review in chat (`chess_skill.py`)

Things you can type:

| You type | CAEL does |
|---|---|
| `let's play chess` / `play chess as black` | Starts a game; moves can be typed as `e4`, `Nf3`, `O-O` or `e2e4` |
| `hint`, `take back`, `resign` | During a game |
| `best move: <FEN>` | Gives the best move, its evaluation and the expected line |
| `rank all moves: <FEN>` | Scores every legal move |
| `review this game: 1. e4 e5 ...` | Lists the biggest mistakes in the game |

The game lives in the chat itself: every reply ends with the game record, so nothing is stored elsewhere.

**The engine** (`cael_unified/chess_engine/`) is non-neural:
- It is an alpha-beta search with iterative deepening, a transposition table and null-move pruning.
- It adds late-move reductions, singular extensions, ProbCut, and countermove and continuation history.
- It uses Lazy SMP to search on several cores.
- Its evaluation is a hand-written formula of about 100 chess terms. The weights are fitted to CAEL's own self-play
  games.
- An opening book is built from master games.

Each improvement was kept only if it won a sequential match (SPRT) against the previous version:

| Change | Elo in self-play (95% interval) |
|---|---|
| Richer evaluation (about 100 terms) | +32.5 [+18, +47] |
| Countermove + continuation history | +25.7 [+13, +38] |
| Singular extensions | +21.6 [+11, +33] |
| ProbCut | +10.2 [+3, +17] |
| 4 threads vs 1 thread (0.2 s per move) | +165 [+128, +206] |

These are CAEL-vs-CAEL gains. Against other engines they are usually smaller.

**Wins:**

| Opponent | Result | Notes |
|---|---|---|
| Cyber Chess AI, "Hard Pro" level ([freeonlinegames.win](https://freeonlinegames.win/play/chess-cyber-ai)) | **1–0, checkmate in 28 moves** | Played by CAEL 0.4.5 at 5 s per move, recorded move by move |
| ChatGPT 6.1 Terra | **2–0** | Played by the developer on the CAEL Chess Space. ChatGPT resigned both games |
| Grok 4.7 | **1–0** | Grok resigned at move 12 in a main-line Najdorf |
| Stockfish 19 limited to 2850 Elo (`UCI_LimitStrength`) | **4–2** | 6 games at 5 s per move, earlier version of the engine |

The game records are in `results/chess_0.4.5/`.

These are small samples, and the games against chat models were not played under controlled conditions:
- The ChatGPT and Grok games were played and recorded by the developer.
- Grok resigned a position that was still equal.
- In the ChatGPT game, CAEL was winning by move 17, let much of that advantage slip, and won again after ChatGPT
  blundered.

**Play it in your browser:** [huggingface.co/spaces/vynly/cael-chess](https://huggingface.co/spaces/vynly/cael-chess).
The same engine runs there, as JavaScript, on your own device. When the page is opened directly it uses several cores.

## 2. Stories: a world model (`world_model.py`)

CAEL reads a short story into a state:
- who moved where, and who took, dropped or gave what (with many verb synonyms);
- "he", "she" and "they", "then", and time words;
- facts such as "cats are afraid of dogs", colours, a direction map, and motivations.

It then answers questions about that state: where, where before, either/or, carrying, how many, who gave, deduction,
induction, route and why. **It answers only when it understood every statement and the question**; otherwise the
normal pipeline answers.

| bAbI (Facebook, 20 tasks), test split, 25 questions per task | 0.4.4 behaviour | 0.4.5 |
|---|---|---|
| Correct | 241/500 | **494/500** |

The test split was measured once, with web search off. The 6 misses are size comparisons answered by an older reader.

## 3. Word problems: question-guided arithmetic (`question_math.py`)

Everyday word problems often carry numbers that don't matter. The new solver:
1. Reads what the question asks for: a difference, a share per group, how many groups, a count from "each", or "X did N
   more than Y".
2. Uses only the numbers whose words and unit match the question.

Each rule kind may answer only if it was right at least about 85% of the time on the SVAMP training split. The other
kinds stay silent.

| SVAMP, test split (300) | 0.4.4 behaviour | 0.4.5 |
|---|---|---|
| Correct | 58 | **70** (12 gained, 0 lost) |

Harder free-form problems (GSM8K style) remain weak. A wider equation search was tried, gave more wrong answers than
right ones, and was not shipped.

## 4. ARC: a program search and a cell-rule learner

New in `arc_solver.py`:
- **`arc_dsl.py`, a compositional program search:**
  - About 350 general grid operations, chained up to 3 deep, with a learned colour mapping at the end.
  - Lookups, per-part mapping, period repair, and a reshape step followed by cell rules.
- **`arc_cellrules.py`, per-cell rule learning:**
  - A small decision tree over about 110 hand-written cell features learns each output cell.
  - Splits are copy-aware, and the search looks for the smallest tree.
  - A leave-one-out check applies when there are at least 3 demonstrations.

| Set | 0.4.4 (10 s per task) | **0.4.5 (60 s per task)** |
|---|---:|---:|
| ARC-AGI-1 evaluation | 62/400 | **83/400 (20.75%)** |
| ARC-AGI-1 training | 152/400 | 192/400 |
| ARC-AGI-2 evaluation | 0/120 | **1/120** (the first ARC-AGI-2 task CAEL solves) |

**Rules:**
- pass@2, CPU only, the solver never sees the answers, and each task runs in its own process.
- Development used the training set only. The evaluation set was run as a measurement, with nothing tuned on its
  failures.
- The time limit per task is now 60 s, still well within the ARC Prize allowance.

Reproduce with `python evaluate_arc.py --data ARC-AGI/data/evaluation`. Per-task results are in `results/`.

## Reproducing the reasoning numbers

`results/reasoning_0.4.5.json` holds the bAbI and SVAMP counts. Set `CAEL_EXACT_SKILLS=0` to switch the new early skills
off and get the 0.4.4 behaviour.

## Requirements

The chess skill adds `numba` and `chess` (python-chess). Both are in `requirements-unified.txt`; without them, the chess
skill says so and the rest of CAEL works as before.
