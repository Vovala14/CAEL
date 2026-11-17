# CAEL 0.4.2: conversation team, fielded retrieval and the Supporter

CAEL 0.4.2 is a conversation release on top of the 0.4.0 core engines. It is still **non-neural**: no neural network or
transformer produces its replies. A team of small agents (planner, researchers, calculator, memory, writer, critic and a
new Supporter) answers each turn from authored knowledge, CAEL's own local index of human-written answers, exact solvers
and checked web lookups.

## What is new

### Fielded retrieval index v2 (`cael_unified/retrieval.py`)

A new search index over the same 285,000 stored questions and answers in the open-chat resource. It finds a thread about
the same problem far more often than 0.4.1's two-key-word search:

- **Four separate fields.** Title, tags, question body and answer are indexed apart, and ranked with BM25F (per-field
  length normalisation and field weights).
- **The whole conversation as the query.** Every word the user said counts, weighted by turn and by how rare it is, not
  just two key words.
- **Learned word associations.** A table counted from the index itself links the words people use to describe a problem
  to the words used to name it ("trickle" → shower, pressure; "dripping" → leak, faucet).
- **British to American English.** About 110 words and phrases: lead/leash, windscreen/windshield, flatmate/roommate,
  nursery/daycare, washing up/dishes.
- **The thing and the trouble.** The ranker knows what the user's problem is with ("our dog") and what is wrong ("pulls
  on the lead"). A stored question that never names the user's thing ranks lower.
- **A confidence gate.** A thread is only quoted when its title names both the thing and the trouble.

On two development sets of real conversation openings, a fitting thread is ranked first 71–76% of the time, against 41%
before (strict labels: the title must name both the thing and the problem).

### Conversation coherence (`cael_unified/coherence.py`)

Follow-up questions are short and name nothing ("Should I feed it?", "How much liquid should I add?"), so a search on
their own words used to drift. Now:

- Every reply in a multi-turn conversation must stay on the thing the user is talking about.
- Pages about films, characters or people that only share a word are rejected (no more cartoon called Flapjack for a
  flapjack question).
- Advice for the wrong kind of thing is rejected (gadget repair for a headache, pet advice for a plumber).
- A rejected reply is replaced by threads about the user's thing that ask the same question, then by advice for the
  right class of problem.

### The Supporter (`cael_unified/support.py`)

Emotional conversations are now handled over several turns, not one reply:

- **Situations covered:** loneliness, grief, a setback (a job, an exam, a place), a child who is upset (left out, or after
  a setback), self-doubt, nerves before an event, someone moving away, a dispute with a tradesperson or landlord,
  overwhelm and anger.
- **Each kind of turn gets its own answer:**
  - a feeling told is acknowledged;
  - more of the story is reflected back, with the first things that help;
  - "Is it normal to feel this?" gets an honest answer;
  - "What can I do?" and "How do I help her?" get practical steps.
- **It respects the user's wishes.** When the user asks for no advice or no questions, the Supporter stays out.

### Stories (`cael_unified/story_agent.py`)

- Stories about a character who is afraid of something, keeps doing something or can't do something get their own plots.
- "Make it funnier", "sillier", "happier" or "sadder" really change the ending.
- Verb forms are correct ("kept digging", not "keeped digging").

### Calculator, memory and writing

- **Shares of an amount:** 75% of a quote, then 40% of what was paid; "kept 25%" means 75% back; "90% of the full deposit".
- **Discounts:** "10% off the full price" uses the price, not the deposit worked out before it.
- **Recipe scaling in one turn:** "250 g of oats for 12 bars … for 30 bars?", and the follow-up ingredient is named.
- **Moved bookings:** "She just texted to say she'll come on Thursday at 4 pm instead" updates the booking. CAEL answers
  with the new time and notes the old one.
- **Thank-you notes:** "a message to my neighbour thanking her for …" now writes the note.
- **Symptoms told without a question** ("I've been getting headaches every afternoon") get help, and follow-ups stay with
  them.

### Clean-up

- The old `chat_v6_7` engine and ten modules that no route loads any more were removed.
- CAEL now runs without the optional open-chat index (for example on CI): word weights fall back instead of failing.

## Measured result

A sealed comparison against **Gemma 3 270M IT**: 20 fresh conversations, written after the build was frozen, covering
chat, advice, explanations, how-to, emotional conversations, long chats, maths, time, logic, memory updates, scheduling,
plan comparison and writing.

| Opponent | CAEL wins | Opponent wins | Ties |
|---|---:|---:|---:|
| Gemma 3 270M IT | **12** | 7 | 1 |

**Where CAEL won:** maths, time, logic, scheduling, plan comparison, emotional support, how-to steps and recalling what the
user said.

**Where Gemma won:** some practical multi-turn chats, a short thank-you note and one memory update. The memory update was
fixed for this release.

How it was run:
- CAEL ran with web lookups on, as it does live; Gemma ran offline with Google's recommended sampling.
- Each whole conversation was judged by the developer of CAEL. That is a conflict of interest, and the judging was not
  blind.
- 20 conversations is a small sample.

## Size and resources

- **Disk:** about 2.6 GB, nearly all of it data: the model bundle, the knowledge base and the open-chat index. The code is
  about 20 MB.
- **Memory:** about 100 MB after start-up and about 200–230 MB in a chat.
- **CPU:** typical turns take a fraction of a second on one core. A few turns that need several searches take longer.
- **Hardware:** no GPU.

## Install and run

Use Python 3.12. Download and extract `CAEL-0.4.2.zip`. For full chat, also extract `cael-open-chat-v1.1.zip` into
`models/`, so that `models/cael-open-chat-v1/` holds `open.sqlite` and the new `fielded.sqlite`. Then:

```bash
python -m pip install -r requirements-unified.txt
python -m cael_unified --download
python -m cael_unified --ui
```

Open http://127.0.0.1:8765. Set `CAEL_WEB_SEARCH=0` to turn off public web lookup.

The integrity-checked resource bundle is unchanged (byte-identical 0.3.7). This is custom Python code, not a
Transformers checkpoint.

## Honest limits

- Practical how-to follow-ups can still fall back to general advice that is the right kind but not specific.
- Facts outside CAEL's knowledge depend on the web.
- Some inherited tests outside the CI set still fail.
