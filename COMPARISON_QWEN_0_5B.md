# CAEL 0.2.7 vs Qwen2.5-0.5B-Instruct

A side-by-side run on the same prompts, made on 2026-10-21 to find where CAEL still needs to improve.

| | CAEL 0.2.7 | Qwen2.5-0.5B-Instruct |
|---|---|---|
| Kind | Non-neural: rules, counts, WordNet, LSA, full-text search, symbolic solvers | Transformer language model, 494M parameters |
| Download | 1.37 GB bundle (text engines plus a 139-subject picture model) | 0.99 GB weights, plus PyTorch and transformers |
| Licence | Code and models as in this repository; knowledge base CC BY-SA 4.0 | Apache 2.0 |
| Internet | Uses Wikipedia, Wikidata, weather and news lookups | None |
| Pictures | Yes (128 × 128, 139 subjects) | No |

## How it was run

- **Same prompts, same turns.** Multi-turn cases feed each model its own earlier replies.
- **Qwen:** its own chat template and default system prompt, greedy decoding, up to 384 new tokens, on an
  AMD RX 9070 XT GPU (bf16). The CPU timing below is a separate run.
- **CAEL:** the full assistant in chat mode, exactly as the live worker serves it.
- **Grading:** each case has a regular expression or a check written before either model was run. Code answers
  are graded by running the function on tests. After the first run, four checks were corrected for **both**
  models:
  - a joke containing "can't" counted as a refusal;
  - "Well done, you must be so pleased!" didn't count as a reaction to a puppy;
  - "I apologize" didn't count as declining an email;
  - the Mars news question passed both models although neither gave any current news.

  Every failure and the live/honesty/code passes were read by hand.
- **Scripts and raw answers:** `research/compare_qwen/` (`prompts.py`, `run.py`, `answers_*.jsonl`,
  `report.json`).

## Results

| Test | CAEL 0.2.7 | Qwen 0.5B |
|---|---|---|
| **Neutral set** (76 prompts, 12 areas, new) | **51 / 76** | **65 / 76** |
| Held-out advice questions (110) | 106 / 110 | 106 / 110 |
| CAEL's own labelled set (home ground) | 102 / 102 | 63 / 88 gradable* |
| NNAI-Bench v0.1, 900 multiple-choice (chance 25%) | 23.0% | 28.4% |
| Median answer time, GPU (Qwen) / CPU (CAEL) | 0.01 s | 1.8 s |
| Median answer time, both on the CPU (10 prompts) | 0.04 s | 53.5 s |
| Peak memory, CPU run | 0.13 GB** | 2.7 GB |

\* 14 home cases only check which CAEL engine answered, so they can't be graded for Qwen.
\*\* For text answers. CAEL loads its larger models (pictures, the knowledge index) only when they're needed.

### Neutral set by area

| Area | CAEL | Qwen | Notes |
|---|---|---|---|
| Facts | 6 / 10 | 9 / 10 | CAEL: "largest planet", "year WW2 ended" not found; "tallest mountain", "how many continents" answered with a definition |
| Maths | **3 / 10** | **10 / 10** | CAEL misses: powers, fractions as decimals, speed × time, "3 times as many", change from $5, % off, unit conversion |
| Logic | **7 / 8** | 3 / 8 | Qwen: "51 is prime", "next after 16 is 16", "Monday + 10 days is Monday", bat and ball $0.10, a syllogism answered "no" |
| Language | 5 / 8 | 8 / 8 | CAEL: opposite of "ancient" = "present, future"; passive voice and its/it's gap phrasings not recognised |
| Code | 3 / 6 | 6 / 6 | CAEL asks for examples for 2 tasks and wrote a wrong sum-of-evens function |
| Advice | 6 / 6 | 5 / 6 | |
| Multi-step | 5 / 6 | 5 / 6 | CAEL counted the letters of "it" (fixed before release); Qwen said Tokyo has 7 letters |
| Writing | **2 / 6** | **6 / 6** | CAEL can't summarise, write an email, suggest names or explain photosynthesis |
| Conversation | 6 / 6 | 5 / 6 | Qwen answers "I just got a puppy!" with "As an AI language model…" |
| Live info | 1 / 2 | 0 / 2 | CAEL gives London's weather; neither gave current Mars news |
| Honesty (should not invent) | 4 / 4 | 4 / 4 | |
| Explanation | 3 / 4 | 4 / 4 | CAEL sent "weather vs climate" to the weather lookup |

### Wrong vs "not sure"

Of CAEL's 25 neutral misses, 19 are honest "I'm not sure", "can't find" or "give me examples" replies; 6 are
wrong or off-target:
- two definitions instead of an answer;
- a poor antonym;
- a wrong sum-of-evens function;
- counting "it";
- weather for "weather vs climate".

Of Qwen's 11 misses, 7 are confident wrong answers ("51 is prime", "Tokyo has 7 letters", "50 countries make up
the continents"…), 2 are generic replies, and 2 lack current information. CAEL answers less, but is rarely
confidently wrong. Qwen answers almost everything, and its mistakes look as sure as its right answers.

### NNAI-Bench by category (150 each)

| Category | CAEL | Qwen |
|---|---|---|
| Logic | **0** | 46 |
| Strings | 48 | 45 |
| State tracking | 37 | 38 |
| Tables | 36 | 53 |
| Ordering | 42 | 35 |
| Arithmetic | 44 | 39 |

Both are close to chance (37.5 per category). CAEL's 0 on logic comes from routing, not from its logic engine.
Multiple-choice questions go straight to the count language model and never reach the symbolic logic solver,
which handles exactly this "Every X is a Y … true, false or unknown?" form.

## Where CAEL needs to improve, in order

1. **Maths word problems (3/10 vs 10/10).** Add a general quantity reader: rates (speed × time, price ×
   count), "N times as many", change from a payment, percent off, powers, fractions to decimals and unit
   conversions. This is the largest gap, and symbolic solvers can do it exactly.
2. **Writing (2/6 vs 6/6).** Add:
   - extractive one-sentence summaries (rank sentences, keep the main facts);
   - email templates (decline, accept, thank, apologise);
   - a name generator (combinations of words);
   - "explain X to a child" from dictionary and encyclopedia sentences rewritten into simpler words.
3. **Multiple choice through the reasoning engines.** Try the symbolic solvers (logic, ordering, state
   tracking, arithmetic) on a question first, map their answer to an option, and use the language model only
   when none applies. This is the quickest NNAI-Bench gain (logic 0/150).
4. **Common facts.** "Largest", "tallest", "how many", "what year" questions should read the Wikidata property
   (for example, the highest point) instead of returning the first Wikipedia definition.
5. **Code without examples.** Write default tests from the description for common tasks (count vowels, reverse
   words), and never answer with a function that fails the description (sum of evens).
6. **Language phrasings.** Accept "Put this sentence in the passive voice: …" and fill-the-gap its/it's
   questions. Rank antonyms by everyday use (ancient → modern).
7. **Routing slips.** Send "difference between X and Y" to explanation, not the weather lookup. Make story state
   tracking read present tense ("Mary goes to the bedroom"). Answer recent-news questions from the news source.

## Where CAEL is ahead

- **It doesn't confidently invent.** Logic 7/8 vs 3/8, and most of its misses are honest "not sure" replies.
- **Speed and size.** About 1,000 times faster on the same CPU, at a twentieth of the memory, with no GPU.
- **Live information and sources.** Weather, Wikipedia and Wikidata answers come with source links. The advice
  answers link the discussions that backed them.
- **It shows its reasoning.** Steps, the grammar rule behind each correction, checked arithmetic and tested
  code.
- **Pictures**, which a 0.5B text model doesn't do at all.

## Limits of this comparison

- One run, one machine, 76 neutral prompts: a guide to what to improve, not a leaderboard.
- Regex grading can miss good answers worded differently. Failures were read by hand, and four checks were
  corrected for both models, as listed above.
- Qwen was run with plain PyTorch. Optimised runtimes such as llama.cpp would make its CPU time several times
  faster.
- The held-out advice sets were written for CAEL's evaluation, so they're not fully neutral. Qwen tied there
  anyway.
