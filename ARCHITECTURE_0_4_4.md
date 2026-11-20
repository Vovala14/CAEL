# CAEL 0.4.4 architecture

CAEL is a chat and reasoning system built without neural networks. This document describes release 0.4.4: how a
message is answered, the swarm layers, the think-first swarm and the answer guard (section 2a), the ARC solver
(section 2b), and how the swarm layer was tested during development.

Written by the developer, so there is a conflict of interest. The development scores in section 4 are the developer's
own. The ARC numbers can be reproduced with `evaluate_arc.py`.

## 2a. Think first, as a swarm (new in the release)

`team.run` first asks `think.run`:
1. **Readings.** The question is read as asked, with all of the user's turns as one message, with number words as
   digits, and with statements apart from the question.
2. **The swarm.** Nine exact readers propose answers to every reading in parallel:
   - `everyday_exact`, `everyday_more`, `constraint_logic` and `explain_more`;
   - `word_math`, `recall_did` and the labelled-account swarm desk;
   - `solve_logic` and `solve_math`.
3. **Checks.** Each proposal is checked for answer type; for word problems, a search finds the derivation that uses the
   most of the user's stated numbers.
4. **Vote and decide.**
   - Proposals vote by answer, and the best-supported checked answer is returned with a trace.
   - Two fully checked answers that disagree make CAEL ask which reading was meant.
   - When nothing passes, the pipeline below answers.

After the team, `answer_guard.check` replaces a loose reply (a web thread, an advice template, or a sum about
something else) to a question about the user's own situation with an honest "I can't work this out".

## 2b. The ARC solver

`arc_solver.attempts(train, test_input)` runs 53 solver programs.
- **Fitting:** every candidate rule must reproduce every demonstration pair before it may predict.
- **Ranking:** candidates are ranked by description length plus a small prior per family.
- **Views:** the task is solved under the 8 symmetries, each answer is mapped back, and equal answers pool their votes.
- **Self-check:** when answers compete, a leave-one-out check re-learns each leading rule without one demonstration,
  and the rule must predict it.
- **Answer:** the two best different grids are returned.
- **Union swarm:** different specialists can explain different added colours.
- **Speed:** a fit cache reuses learned rules across a task's test inputs.

## 1. What CAEL is, and is not

- **No neural network and no transformer:**
  - there are no learned layers, no embeddings model, no attention and no gradient training anywhere in the chat path;
  - every answer comes from hand-written rules, small fitted tables (counts, frequencies, frames) and exact solvers;
  - search over stored question-and-answer threads uses BM25F, a classic word-statistics ranking;
  - free public web sources (Wikipedia, Wikidata) supply facts.
- **Two libraries that might look neural, but are not used that way:**
  - `torch` appears only in the image and emoji tools, as an array library for count tables, cellular-automaton
    sweeps and sampling. There is no `nn.Module`, no training loop and no learned weights. The `.pt` files hold count
    tables.
  - `sklearn` is used once, to scale vectors to unit length.
- **Runs on one CPU core.** A turn usually takes a fraction of a second; turns that look something up on the web wait
  for the network. For 0.4.2, memory use was measured at about 100–230 MB and the disk footprint at about 2.6 GB,
  mostly data. The chat code (`cael_unified/`) is about 8 MB of Python.
- **No other model's output is used to train CAEL.** No paid services are used.

## 2. How one message is answered

```
Assistant.respond(messages)
  └─ team.run
       1. "Why?" after a short fact      -> asked again in full ("Why is Rome the capital of Italy?"), and the answer
                                            is kept only if it is about that fact (common_asks.py)
       2. Swarm desk                      -> labelled accounts or parts ("Witness 1: … Witness 2: …"), the user's own
                                            facts, "Why?" after a swarm answer (swarm.py)
       3. Task split                      -> a message with several separate tasks gets one team per task, at most
                                            six at a time (meesix.py)
       4. Swarm compute                   -> when the message can be read more than one way, several agents answer
                                            at once and fixed rules pick the reply (swarm_compute.py)
       5. team.single                     -> the desk pipeline below, then the coherence check
```

`team.single` runs desks in a fixed order. The first desk that is sure of its answer wins. Each desk is a plain
function: a "Mr. Meesix" agent that holds nothing after its job.

| Order | Desk | What it does |
|---|---|---|
| 1 | Host | Questions about CAEL itself and the clock, time in a city, and converting a given time between cities (`about_me.py`). Also jokes, recipe steps, common myths (`common_asks.py`). |
| 2 | Reasoner | Exact work (`reasoner.py`): sums said in words, primes, bat-and-ball puzzles, work rates, chained steps, legs counts, rules about individuals, and follow-ups on its own last result. |
| 3 | Coach | Authored everyday situations whose follow-ups keep the subject (`situations.py`): family arguments, declining invitations, a visit, budget dinners and others. |
| 4 | Specialists | Rates, support, listening, Python help, ideas, tips, explanations, follow-up knowledge. |
| 5 | Solver | Arithmetic word problems and logic (`solve_math`, `solve_logic`). |
| 6 | Generalist | The full older pipeline: memory, skills, local knowledge, conversation. |
| 7 | Researchers | Exact values from Wikidata and Wikipedia (`exact_web.py`), and checked page passages (`web_check.py`). |
| 8 | Critic, Editor | Reject dead ends (a missing number, yes/no to "how many", an echo of the user's words), then pick a draft or write an honest last resort. |
| 9 | Late fallbacks | Story sums (only after every other desk), then advice templates. |

After the pipeline, `coherence.py` checks that a follow-up's answer stays on the conversation's subject. For example,
plumbing advice to a plumbing question, not pet advice. A drifting reply is replaced by a retrieval that names the
user's subject.

Older parts that are still central:

- `event_memory.py`: reads state updates from text ("Ana gains 2 apples"), with live references and the history of
  each value.
- `reasoning_sat.py`: a DPLL case checker for "or" and proof by contradiction. It reports contradictory premises
  instead of guessing.
- `retrieval.py`: BM25F over about 285,000 stored Q&As, with a confidence gate.

## 3. The swarm layer

### 3.1 The three problems it answers

The design responds to three problems in scaling CAEL as a swarm of small agents:

1. **Referent binding:** merging partial context from many agents without losing who is who.
2. **Consensus:** fixed tie-breaking rules instead of drifting votes.
3. **Shared state:** a long-term state with no central database, summarised level by level.

### 3.2 The data model (`swarm.py`)

The shared state consists of three grow-only sets:

- **Claims:** "entity, attribute, value". Each claim also records:
  - the agent that sent it;
  - the agent's clock;
  - the evidence kind;
  - a position (a timeline step, or the minute of a sighting);
  - the operation: set, add or subtract;
  - the words it came from.
- **Links:** "these two names are the same thing" or "these are different things".
- **Rules:** if-then statements ("whatever is a cat is black").

Merging two states is set union, so it is commutative, associative and idempotent. The agreed view is computed from
the sets on reading, so the order in which agents send or receive things never changes the result.

### 3.3 Who is who (binding)

Binding is deterministic. It is computed from the whole set each time:

- An explicit "same" link always joins two names, whether it comes from an agent ("The driver was Sam") or from the
  user. A "distinct" link vetoes a join made only from names.
- A short name joins the one longer name it is part of: "Sam" joins "Dr. Sam Lee". When two longer names fit, the short
  name stays apart and the view reports it as ambiguous.
- A description ("the man in the red hat") is never taken as a longer name for one of its own words ("hat").
- **Corrections withdraw links.** Each link carries the agent's clock, and an agent's later link about the same
  description replaces its earlier one: "Actually the driver was Tom", or "the driver was not Sam". Binding uses only
  these live links, and the view is recomputed from them. Everything that rested on the withdrawn link is therefore
  recomputed: "Where is Sam?" becomes "Nobody places Sam now. Witness 1 first said the driver was Sam, then corrected
  it", and "Why?" lists the old link as withdrawn.
- Pronouns are refused on the wire. An agent resolves "she" itself before sending a claim. In the chat desk, a leading
  "it" is filled in only when the other accounts name exactly one thing.

### 3.4 Consensus rules (`resolve`)

There is no voting. A hundred copies of a mistake do not beat one statement. The rules, in order:

1. An agent's own correction (same position, higher clock) replaces its earlier claim.
2. Evidence kind ranks next:
   - **confirmed** (what the user knows first-hand);
   - **trusted** (a source the user said to trust);
   - **stated**;
   - **derived**;
   - **retrieved** or **doubted** (equal);
   - **default**.
3. A later position beats an earlier one, because the world changed.
4. Changes ("gains 2") apply on top of the latest value before them, whichever agent saw which part.
5. Two different values at the same rank and position are a **conflict**. The view reports both sides with their
   agents and never picks one.

Rules from one agent apply to facts from another. A derived value never overrides a stated one; when the two differ,
the view reports a rule exception. Derived values are rebuilt from the stated values every round until nothing changes,
so a value whose premise falls away is withdrawn. For example, a premise can turn into a conflict, and an explanation
never cites a conclusion that is no longer accepted.

**"Last confirmed" and "last seen" are different questions.** Rank comes before time, but the reply never hides newer
evidence of lower rank:

- "Where is the van?" gives "**Haifa** (what you told me). That is as of 9am. A later sighting ranks lower: **Acre** at
  11am (Witness 1)."
- "Where was the van last seen?" gives "Last seen at 11am: **Acre** (Witness 1)." This looks only at time, whatever the
  rank.
- "Where was the van last confirmed?" gives "**Haifa** (what you told me)." This uses only what the user confirmed.

When the later sighting comes from separate sources, the reply says so.

### 3.5 Summaries, shards and gossip

- **Summary.** `State.summary()` drops a claim only when the claims beside it rule it out for good:
  - an agent's superseded claim;
  - a value below a higher-ranked value under the same name;
  - a change made before a later top-ranked value.

  More claims never bring a dropped claim back. Summaries can therefore be taken in any order or grouping, and a tree
  of nodes merging and summarising level by level gives the same view as merging everything flat.
- **Shards.** Claims are filed on one of many nodes by the name they were made under. Every node keeps a small shared
  directory of names, links and rules, so who-is-who is computed the same way everywhere. A question about one entity
  fetches only that entity's claims. Rules look only at one entity's own attributes, so this per-entity view equals
  the merged view.
- **Delta gossip.** Nodes compare fingerprints of 256 buckets. For buckets that differ the peer sends item ids, and the
  puller then receives only the items it lacks.

### 3.6 The swarm desk in chat

The swarm desk is how users meet the swarm layer: each labelled part of a message gets its own reader agent. It
supports:

- **Accounts and parts.** Accounts (witness, source, report, sensor, camera, log and so on) describe the same moment, so
  accounts that differ conflict. Timeline parts (part, day, chapter, step) follow one another, so the latest part wins
  and changes add up.
- **Accounts over several messages.** A message that is only accounts, with no question yet, is acknowledged with what
  was read.
- **Trust, said by the user:**
  - "trust Document 2";
  - "Witness 2 was drunk";
  - "ignore Report C".
- **Track record.** When the user states a fact ("It turns out Sam was in the kitchen"), a source that contradicted it
  is doubted on everything else it said. The reply says why.
- **Sightings at times.** Sightings at 2pm and 3pm are not a conflict, and "Where was Mia at 8am?" works.
- **Description links.** "The driver was Sam" binds the two, and the answer names the link it rests on.
- **Reported speech.** "Sam said the van was white" is not taken as a sighting.
- **Reader coverage.** Every reader records the clauses it could not read, and the reply carries them in
  `swarm.unread`. When an unread clause is about the thing asked, the reply says so and quotes it: "I could not read
  this sentence, which may change the answer". That covers any of the thing's names, or a "he", "it" or "they" in a
  part about it. "Why?" lists unread clauses as "not read".
- **Questions it answers:**
  - yes/no;
  - "how did X seem";
  - "at first", "on Day 2";
  - "when is…", "which is right?".
- **"Why?"** It lists each source's own words, what happened to each (used, earlier sighting, set aside and why), and
  the rule that decided.
- **The user's own facts.** "My car is red." gets "Noted…", and "What colour is my car?" then gets "**red**, as you told
  me". This covers places, colours, days, times and states only. It refuses rather than answer from an older statement
  when the user said something unread about the same thing.

### 3.7 Swarm compute (`swarm_compute.py`)

One CAEL reads a message one way. A greeting in front, "can you … please", or a "how many X is N Y" phrasing can send it
down the wrong path. Swarm compute gives each reading its own agent, and the agents run in parallel:

| Reading | What it is |
|---|---|
| as asked | The message as written; this is what a single CAEL answers. |
| core | Greetings, thanks and filler removed. |
| request | "Can you convert … please?" becomes "Convert …". |
| convert | "How many miles is 10 kilometers?" becomes "Convert 10 kilometers to miles." |
| standalone | A follow-up's "it" or "them" replaced by the thing named earlier. |

The pick is by rules, not votes:

1. **Evidence class:**
   - exact work;
   - a checked lookup;
   - guidance;
   - a single quoted thread;
   - a fallback.
2. **Off-topic** replies drop one class.
3. **Corroboration.** Two readings reaching the same answer break a tie within a class.
4. **Default.** The message as asked wins any remaining tie; another reading must be strictly better to replace it.

A rewrite may drop greetings and politeness, never what the question asks. A reading is not run unless it keeps:

- every number;
- the unit after each number;
- every operation word ("more", "left", "need", "per", "than", "each" and so on).

For example, "How many more miles do I need to reach 10 miles if I've walked 10 km?" can never become "Convert 10 km to
miles.". That rewrite's exact answer, 6.2, would answer a different question.

A reading runs inside a whole CAEL, including its entry helpers, with swarm compute switched off inside it, so no
reading starts a swarm of its own. Most messages have only one reading and cost nothing extra.

Switches: `CAEL_SWARM_DESK=0` and `CAEL_SWARM_COMPUTE=0` turn the swarm off and give a single CAEL.

### 3.8 Added after the blind test

- **The evidence check (`evidence.py`).** A looked-up passage, an advice template or a fallback may answer only when it
  supplies what was asked about the thing named. It runs after the coherence check, and never on exact desks. Three
  rules:
  1. A property only the user can see ("the serial number on my clock") is never answered from the web. The reply is
     "I can't see your kitchen clock…".
  2. A question about something the user told earlier needs an answer from the conversation. A quoted thread or advice
     is replaced with "You mentioned the keys, but…", quoting what was said.
  3. "How many X" needs a reply that states a number of X. Otherwise the reply is "I couldn't find a source that
     states how many…".
- **Sums said in words (`word_math.py`), a Reasoner solver:**
  - comparisons, including negatives;
  - spoken numbers ("three dozen minus five");
  - unit conversions, and what is left to reach a target;
  - differences ("how many more … than");
  - sharing, with the amount from the previous turn;
  - weekdays ("yesterday was Monday");
  - sorting;
  - a membership rule ("all the marbles in this bag are glass");
  - a table of shapes and solids.
- **Count extraction** (`exact_web.py`): "one" counts only directly after a verb like "has", "with" or "contains", never
  in "the length of one side".
- **Swarm readers:**
  - correction labels ("Log B correction:", "Correction to Report B:");
  - retractions ("Witness 2 retracts the identification", stored as a retract link);
  - first-person sightings ("I saw Jo in the lobby", including the user's own words before the first label);
  - moves ("I moved it to the porch");
  - "X and Y are different people" (a distinct link).
- **Swarm questions:**
  - "where does that leave X";
  - "do the logs still disagree";
  - "the remaining reports";
  - "and according to whom", "exactly";
  - a time between two sightings, answered "not known exactly";
  - "did either witness see it themselves", and "how many independent sightings" (hearsay and copied accounts do not
    count);
  - "it" in a question, resolved to the one thing it can mean, or "Which one do you mean?" when two fit;
  - "definitely" when an unread hedged sentence is about the thing, answered "**Not for certain.**".

## 4. Testing

### 4.1 Unit and regression tests

- `tests/test_swarm.py` has 39 tests, and `tests/test_common_asks.py` plus `tests/test_reasoner_044.py` add more.
- The swarm tests include 40 random worlds. Each world has:
  - overlapping names;
  - links and rules;
  - changes;
  - all seven evidence kinds;
  - corrections.

  Every world must give the same view and the same summary set under:
  - shuffled merges;
  - repeated merges;
  - trees with fan-out 2, 3 and 8;
  - early summaries.

  A separate test gossips 40 nodes until they agree.
- Mutation checks: each of these breaks at least one test:
  - the old summary rule;
  - ignoring the clock;
  - removing the description guard;
  - removing the track record;
  - ignoring sighting times;
  - ignoring trust.
- Full regression suite on the final code: 2,025 passed and 24 failed. These are the same 24 inherited failures as
  0.4.3, with none new.

### 4.2 Scale (one core, pure Python)

- **Merging:** 500 agents and 100,000 claims merge flat in 0.7 s, or in 0.8 s through a tree with summaries, and the
  two views are equal.
- **Shards:** 50 shards hold 268–1,135 items per node, against 33,277 on one node. The shared directory has 700
  entries, and one entity lookup takes 0.35 ms.
- **Gossip:** 200 nodes converge in 19 rounds. Delta gossip sends 7.4 times fewer items than full-state gossip, but
  takes about the same wall time.

### 4.3 Swarm vs single CAEL (sealed)

The 40 conversations were written before any run, then sealed: `swarm_vs_single.sha256` holds the inputs' hash, and a
second hash records the source at run time. Each conversation has objective expected patterns. The set has four
groups:

| Group | Conversations | Contents |
|---|---|---|
| Sources | 12 | Multi-source accounts |
| Wrapped | 14 | Questions wrapped in greetings or filler |
| Follow-up | 6 | Follow-ups with "it" |
| Plain | 8 | Plain controls |

Each configuration ran once.

| Group | Single CAEL | Swarm |
|---|---|---|
| Sources (12) | 2 | 6 |
| Wrapped (14) | 7 | 12 |
| Follow-up (6) | 6 | 6 |
| Plain (8) | 6 | 6 |
| **Total (40)** | **21** | **30** |

- No conversation went from right (single) to wrong (swarm).
- Total time was 290 s for single and 294 s for swarm.
- Two of the swarm's misses are scorer errors. A reject pattern also matched the sentence naming the outranked source,
  although the answer itself was right (s05 "**Friday** (Document 2)", s09 "**9am**").

### 4.4 After test-informed fixes

The failures seen in the sealed run were then fixed, so this rerun is **test-informed and not a fresh test**. The fixes:

- sums in words ("9 times 6" had returned a newspaper article);
- counts with had/spent/found;
- up/down states;
- "Then it was empty";
- "Where did Zoe go?";
- "by the lake";
- request and convert readings.

| Group | Single CAEL | Swarm |
|---|---|---|
| Sources (12) | 2 | 9 |
| Wrapped (14) | 7 | 13 |
| Follow-up (6) | 6 | 6 |
| Plain (8) | 7 | 7 |
| **Total (40)** | **22** | **35** |

- Three of the swarm's five misses are the same scorer error (s05, s09, s12).
- The polite-conversion miss (c13) was fixed after this rerun and has not been re-scored.
- The remaining miss is k04, an anxious-interview message. Both configurations gave a supportive reply that did not
  name the interview.

### 4.5 Which layer earns the gain (four-way ablation, test-informed)

This follows an outside review. The same 40 conversations ran four ways on the final code, with swarm compute in
both, either or neither of the two layers. Each reply is classed as one of:

- **correct**;
- **refusal**: it declines, asks to clarify, or says the sources don't settle it;
- **confidently wrong**: anything else.

The scorer was corrected after the sealed run: a reject pattern now applies only to the reply's first sentence, where
the answer is given. This set had already been seen and used for fixes, so the table shows what each layer does. It is
not a fresh score.

| Configuration | Correct | Refusal | Confidently wrong | Median turn | 95th-percentile turn | Peak memory |
|---|---|---|---|---|---|---|
| Both swarm layers off (single CAEL) | 23 | 3 | 14 | 2.8 s | 23.2 s | 542 MB |
| Swarm desk only | 33 | 1 | 6 | 0.3 s | 23.2 s | 534 MB |
| Swarm compute only | 29 | 2 | 9 | 3.5 s | 18.8 s | 551 MB |
| Both on | 39 | 0 | 1 | 0.9 s | 23.5 s | 543 MB |

What the table shows:

- **The two layers fix different conversations, and their gains add up.**
  - The desk fixes the multi-source ones.
  - Compute fixes the wrapped questions.
  - Together they cut confident errors from 14 to 1.
- **Neither layer added a confidently wrong answer that a single CAEL got right.**
- **Latency:**
  - Swarm compute ran several readings for 19 of the 40 conversations.
  - The 95th-percentile turn is dominated by web lookups in every configuration.
  - The median turn is lower whenever the swarm desk is on, because it answers its own conversations without searching.
- **Memory:** peak memory, the Windows peak working set of the whole test process, was 534–551 MB in all four
  configurations. Swarm compute adds about 10–17 MB.
- **This peak is well above the 100–230 MB measured for 0.4.2.** The two figures were not measured the same way: this
  is one long process that answered 50 turns with every module loaded. Measuring one chat session like for like is
  still to do.
- **The one remaining error, k04**, is an anxious-interview message. All four configurations gave a supportive reply
  that did not mention the interview, which the expected pattern required.

### 4.6 Blind test by ASTRA 6.2 (the result to quote)

ASTRA 6.2 wrote 40 new conversations and an answer key, and scored the results. The developer froze the build first
(`24117ba7…0cc1`), ran each of the four setups once, never opened the key, and kept which setup was which private until
the scores were locked.

| Setup | Correct | Unneeded refusal | Confidently wrong | Off-topic | Partial |
|---|---|---|---|---|---|
| Single CAEL (both off) | 11 | 7 | 5 | 11 | 6 |
| Swarm compute only | 11 | 6 | 6 | 11 | 6 |
| Swarm desk only | 14 | 6 | 4 | 10 | 6 |
| Both on | 14 | 5 | 5 | 10 | 6 |

What it showed:

- **The swarm desk carried over to fresh wording, a little:** +3, all multi-source.
- **Swarm compute added nothing on unseen wording.**
- **All four setups shared 37 of the 40 outcomes.** Most failures were in the base pipeline:
  - off-topic retrieval or advice;
  - refusals of answerable sums;
  - follow-up turns not reaching memory.
- **Several documented behaviours missed on new wording** because the reader and question patterns were too narrow.
- **Traces of B03, B04 and B09** showed that no correct answer ever reached the ranking step. Each failure was in
  reading or retrieval, not in the ranking table.

### 4.7 After the blind test (test-informed)

The fixes followed the reviewer's priorities: reader coverage first, then one shared evidence check. The details are in
section 3.8. On the same 40 conversations, already seen and scored by the developer against the reviewer's key column,
the full assistant now gets **38/40 with both layers on and 23/40 with both off**. This is a development check, not a
result to quote. A fresh blind test on the newly frozen build (`5eac61cc…a5a0`) is the open question. The full
regression suite has 2,027 passing and the same 24 inherited failures, with none new.

## 5. Known limits and open questions

- **Binding:**
  - It uses names and explicit links only. A description with no "X was Y" statement stays its own entity.
  - Short names bind by first or last word only.
- **Readers:** They understand event-memory wording plus about a dozen added forms. Other sentences are now tracked
  and flagged when they are about the thing asked, but they are still not read.
- **Trust:**
  - It comes from what the user says, and from contradicting the user's own facts.
  - Sources do not earn trust by being right.
  - Sources cannot rate each other.
- **Not implemented yet:**
  - multi-valued attributes;
  - negated or disjunctive rules;
  - a swarm-wide DPLL consistency check.
- **Gossip:** It still sends an id for every item in a differing bucket. A deeper fingerprint tree would send fewer.
- **Swarm compute:**
  - Its readings are hand-written rewrites.
  - The evidence classes are a fixed table of route names.
  - A wrong exact desk can still win over a right lookup when only one reading reaches it. Corroboration helps only
    when two readings agree.
- **Evaluation:**
  - The 40-conversation test is small.
  - The developer wrote and scored it.
  - The expected patterns are strict in places; the scorer errors above come from that.
  - The next test should be blind: a frozen build, conversations written by someone else, the same four
    configurations, and correct answers, refusals and confident errors scored separately.
- **Memory:** the peak memory for 0.4.4 has not been measured the same way as the 0.4.2 figure yet.

### First outside review (ASTRA 6.2) and what changed

| What the review asked for | What was done |
|---|---|
| Use the sealed 30/40 as the headline and the later score as a development result | Done |
| Check that a rewrite keeps the operation before its exact answer can win | Done (section 3.7) |
| Keep "last confirmed" and "last seen" apart | Done (section 3.4) |
| Let a correction invalidate the conclusions that rested on it | Done (section 3.3; rule chains are recomputed) |
| Put reader coverage first and track unread clauses | Done (section 3.6); widening the readers themselves is still to do |
| Measure peak memory and 95th-percentile latency on turns with several readings | Done (section 4.5) |
| Run a four-way ablation scoring correct answers, refusals and confident errors | Done on the seen set (section 4.5); a blind run is still to do |
| Defer sharding across machines until a measured workload needs it | Agreed |

Questions still open:

- Should corroboration by independent sources ever outrank a single higher-trust source, or only be reported as it is
  now?
- For the next blind test: a paired design, with the same task bare and polite, copied and independent, corrected and
  repeated, on build `5eac61cc6fca195866807ac8a567183ae8d3d1e59ac89f6d6427fd66498a5a0a` (frozen 2026-11-20 00:08 UTC).

## 6. Files

| File | Role |
|---|---|
| `cael_unified/team.py` | Entry of the team. The swarm desk, task split, swarm compute and desk order. |
| `cael_unified/swarm.py` | Claims, links, rules, binding, consensus, summary, shards, gossip, readers and the chat desk. |
| `cael_unified/swarm_compute.py` | Parallel readings and the pick rules. |
| `cael_unified/reasoner.py` | Exact reasoning desk. |
| `cael_unified/situations.py` | Authored everyday situations with follow-ups. |
| `cael_unified/common_asks.py` | Jokes, recipe steps, myths, "Why?" after a fact. |
| `cael_unified/evidence.py` | The evidence check for looked-up and advice replies. |
| `cael_unified/word_math.py` | Sums, comparisons, conversions, weekdays, sorting and shapes said in words. |
| `cael_unified/about_me.py` | CAEL itself, clocks, and city time conversion. |
| `cael_unified/event_memory.py`, `reasoning_sat.py`, `coherence.py`, `retrieval.py` | Older reasoning, memory and retrieval parts the swarm builds on. |
| `tests/test_swarm.py`, `tests/test_common_asks.py`, `tests/test_reasoner_044.py`, `tests/test_blind_astra.py` | Tests for the new parts (the last one is test-informed). |

The evidence for section 4 is in the main CAEL folder, under `research/release_044_20261119/`:

- `swarm_vs_single.json` and its `.sha256`;
- `run_swarm_vs_single.py`;
- `sealed_swarm_vs_single_*.jsonl` (the sealed run);
- `swarm_vs_single_*.jsonl` (the test-informed rerun);
- `SWARM.md`.
