# CAEL 0.3.6

**One assistant, one model bundle: chat, reasoning, math, Python, stories,
prompt writing and emoji.** This release excludes picture and portrait generation
weights. Image requests produce a prompt for an external image tool. CAEL routes
between distinct non-neural engines in one portable archive.

## Start

Use Python 3.11 or later. Runtime works on CPU; no image service, teacher
checkpoint or private training folder is needed.

```bash
git clone https://github.com/Vovala14/CAEL.git
cd CAEL
python -m pip install -r requirements-unified.txt
python -m cael_unified --download
python -m cael_unified --ui
```

Open **http://127.0.0.1:8765**. On Windows, `SETUP.bat` installs dependencies
and downloads the checksum-verified bundle; `RUN.bat` starts the local UI.
`--download` fetches `models/cael-0.3.6.cael` (about 563 MB), verifies every file
and installs its model folders under `models/`. It also records the reviewed model
selections in `research/active_models.json` unless that file already exists.

## New in 0.3.6

- **Conversation reasoning:** compact clause records, fact updates and corrections, conflicting sources,
  paraphrased recall, and bounded operations over values in the current conversation.
- **Lower-memory word lookups:** spelling counts and word groups can use compact, memory-mapped NumPy tables.
- **No neural runtime:** the symbolic/count architecture is retained. Picture and portrait model weights
  remain excluded; emoji and image-prompt writing remain available.

On the locally authored 400-question context benchmark, frozen 0.3.6 answered **122/400 (30.50%)**, versus
0.3.5 at 53/400 (13.25%), Qwen2.5-0.5B at 102/400 (25.50%) and Qwen3-0.6B at 121/400 (30.25%).
The Qwen3 difference is one answer, effectively a tie. These are heuristic-graded local conversation tests,
not a general capability ranking or a new HellaSwag/Tiny ToM leaderboard score. References, planning and
unsupported questions remain weak. See [release and evaluation notes](RELEASE_0_3_6.md) for conditions,
limitations, source freeze and reproducible evidence.

## New in 0.3.4

Understands misspellings, answers far more everyday questions, writes and checks everyday Python, reasons through
everyday problems, and plays Sudoku. Every engine is still non-neural.

- **Spelling and chat shorthand** ([spelling.py](cael_unified/spelling.py)): "whats the captial of australia",
  "wich planet", "r u smart", "ur funny" are read as meant. Word and word-pair counts come from CAEL's own Wikipedia
  snapshot and chat corpus (new model folder `models/cael-spelling-v1`, CC BY-SA 4.0), plus spoken-English
  frequencies and WordNet; the neighbouring words decide between candidates. Names, code and correct text are left
  alone. If the corrected message still gets no answer, the original and other likely readings are tried.
- **Fewer refusals:** abbreviations ("what does CPU stand for"), jobs ("what does a nurse do"), stories about any
  subject, occasion messages (birthday, thanks, get well ...), pet names, tips, riddles, compliments, more everyday
  facts, a country's languages and "where is X" with the city.
- **Everyday Python** ([python_help.py](cael_unified/python_help.py)): 60 tested functions for common requests, a
  composer that builds small functions from the request's wording (number and string checks, transforms, filtered
  list totals, positions, counts), and a guide to Python basics (lists, dictionaries, files, pip, input, loops ...).
  Every function shown has been run on its examples.
- **Everyday reasoning** ([everyday_reasoning.py](cael_unified/everyday_reasoning.py)): word problems, "at the same
  time" trick questions, days of the week, clock times, ages, comparing numbers, counting letters, sequences, odd one
  out, where things are, family relations and "all/some" logic, each with its working.
- **Sudoku** ([sudoku.py](cael_unified/sudoku.py)): "play sudoku" (easy, medium, hard, expert or highest) gives a new
  puzzle with exactly one solution, played move by move in the chat (`r3c4=7`, "put 7 in row 3 column 4", undo,
  check, hint, solve it). It solves any pasted grid, including the hardest known puzzles, in milliseconds (Knuth's
  Algorithm X); the highest level is a reshuffled famous hardest puzzle with the same difficulty.
- **Results on fresh questions written after the changes:** everyday questions 85% -> 93% spelled correctly and
  35% -> 87% misspelled; Python questions 5/10 -> 10/10; reasoning 3/20 -> 19/20; function requests 10/10 on the
  last untouched set.

## New in 0.3.3

Unlimited web search with no API key. Every engine is still non-neural.

- **Free web search first.** CAEL now searches with the open-source [ddgs](https://pypi.org/project/ddgs/)
  metasearch library (MIT): no API key and no monthly quota. The order is a SearxNG instance if you set
  `CAEL_SEARXNG_URL`, then ddgs, DuckDuckGo Instant Answers and Wikipedia. The paid Brave Search API is used
  only when none of the free web searches answered. On the fresh question sets it scores the same as Brave:
  36 of 44 and 27 of 40 (Brave: 38 and 29). CAEL still makes at most 30 searches a minute.
- **Finishes well-known lines.** "Complete: roses are red", "roses are red, violets are" or "an apple a day" are
  finished from a hand-written list of about 85 traditional rhymes, proverbs and famous lines (public domain).
  CAEL says when it doesn't know a line instead of inventing one.
- **Vynly help.** "Why does an AI-art site check for AI?" (also written "A.I." or "a I") and "How do I check if
  an image is AI?" get Vynly's own answers.
- Install the new requirement with `python -m pip install -r requirements-unified.txt`.

## New in 0.3.2

Internet search when CAEL does not know. Every engine is still non-neural.

- **Web search fallback** ([web_search.py](cael_unified/web_search.py)). When a factual question has no local
  answer, CAEL searches the web, reads the pages and quotes the sentence that answers it.
  - It searches Brave Search when `BRAVE_API_KEY` is set, then a SearxNG instance (`CAEL_SEARXNG_URL`), then
    DuckDuckGo Instant Answers, then Wikipedia. When one fails or its free tier runs out, the next is used.
  - Pages are read as clean text through Jina Reader or a direct fetch that only reaches public addresses.
  - Every web answer links where it came from. When two or more different websites agree, the answer says so.
    Otherwise it says it is not sure and asks you to check the source.
  - A sentence that only names the subject ("Scotland is a country ...") is not taken as the answer.
  - "Write a Python script that searches the web for ..." returns the same search as a runnable script.
  - Turn it off with `CAEL_WEB_SEARCH=0`. Your question is sent to the search services and Jina Reader.
- **More Wikidata facts:** currency, boiling and melting points, height, length, opening and release dates,
  founding dates and creators (written, painted, directed, composed, invented, founded, designed).
- **Multiple choice:** a question with A-D options always goes to the multiple-choice engines, even when it
  says "then" or mentions posts and followers.
- **Results on new questions written for this test:** 86% (38/44) with web search, 59% with
  Wikipedia/Wikidata only and 23% with no internet. On a second fresh set written after the fixes,
  73% (29/40) with web search, 35% with Wikipedia/Wikidata only and 10% with no internet. A web answer
  takes about 5-25 seconds. Web search does not help with theory-of-mind stories: on Tiny Theory of Mind,
  CAEL scores about 24%.
- **NNAI-Bench:** 68.11% macro accuracy in a maintainer run of 0.3.1, marked test-adapted on the
  [leaderboard](https://huggingface.co/spaces/vynly/non-neural-ai-leaderboard).

## New in 0.3.1

Smarter, text-only and under CAEL's own licence. Every engine is still non-neural.

- **Everyday maths** ([quantities.py](cael_unified/quantities.py)): powers, fractions as decimals or percentages,
  unit and temperature conversions, average speed, "3 times as many", shopping totals and change, "% off", with
  exact fractions and steps.
- **World facts** ([world_facts.py](cael_unified/world_facts.py), [answer_finder.py](cael_unified/answer_finder.py)):
  well-known facts, plus superlatives, counts and years read from Wikipedia opening sentences only when a
  sentence really says it (linked); capitals from Wikidata.
- **Everyday writing** ([compose_text.py](cael_unified/compose_text.py)): one-sentence summaries, emails for
  common purposes, name ideas, "explain X simply", "difference between X and Y".
- **Language and reasoning:** fill-the-gap (its/it's, their/there/they're…), passive phrasing, better opposites,
  present-tense stories and hand-overs; common text and list functions in code.
- **Codex's 0.3 work** (multiple-choice through the solvers, small talk, writing help, Python task tools).
- **Results:** 75 of 76 on the neutral set used to compare with Qwen2.5-0.5B (Qwen 65; this set guided the work),
  49 of 50 on a fresh set written beforehand, 102/102 on the labelled set, 0 wrong on 110 held-out advice questions.
- **Licence:** CAEL now has its own [CAEL Non-Commercial License](LICENSE) (personal and research use free;
  commercial use by separate licence). Third-party parts that did not allow commercial use were removed
  (EmpatheticDialogues-trained reply models, ARC Corpus evidence). See [NOTICE.md](NOTICE.md).
- **Text-only:** picture models are not part of 0.3.1.

## New in 0.2.9

- Exact fractions carry between plan steps; decimal arithmetic retains the input
  digits. Chained percentage changes and tripling work through the orchestrator.
- Equations with several solutions request clarification before dependent steps.
- "Explain this Python code" reaches the bounded interpreter, with no native
  execution or file access granted to pasted code.
- Explicit multiple-choice state/transfer and logic questions use the existing
  symbolic engines when premises and answers can be checked unambiguously.
  Ambiguous questions retain the existing chooser.
- No image-generation checkpoints are included; emoji and detailed image prompts
  remain available. The thinking animation is retained.

The selected language checkpoint is unchanged. Experimental syntax and event
scorers did not improve HellaSwag reliably and are not activated or bundled as
models. No new leaderboard score is claimed. See [release notes](RELEASE_0_2_9.md).
The sections below describe earlier releases; their image features are absent
from the 0.2.9 bundle.

## New in 0.2.8

Exact maths, a bounded Python interpreter, tool building and local file tools, all chained by the orchestrator.
Still non-neural at runtime.

- **Exact maths** ([helper_math.py](cael_unified/helper_math.py)): equations with several solutions, geometry with
  exact values (9π, about 28.27) and rate problems.
- **Bounded Python interpreter** ([python_vm.py](cael_unified/codegen/python_vm.py)): functions and short scripts
  are interpreted step by step with limits, never run natively; "what will this code print?" shows checked output.
- **Code review and repair, function and tool building**: composed functions, stateful functions from examples,
  multi-step task tools from a "Steps:" list.
- **Local file, PDF and media-review tools** for the owner's own computer: see [LOCAL_TOOLS.md](LOCAL_TOOLS.md).
- **Orchestrator chaining**: "Solve 2x + 3 = 11, then square it"; "What is the area of a circle with radius 3?
  Then divide it by 2"; "Write a function that counts vowels, then run it on 'banana'" (run in the interpreter).

## New in 0.2.7

One bundle with everything, and the orchestrator chains all the new engines. Still non-neural at runtime.

- **One unified bundle** with the picture model from the first nightly growth run: **139 subjects** (114 before),
  including koala, panda, kangaroo, piano, violin, windmill, pineapple and watermelon.
- **Engines chained by the orchestrator** ([orchestrator.py](cael_unified/orchestrator.py)): dictionary,
  grammar, translation, trip, advice and reasoning steps pass results on ("What is the opposite of brave? Then
  define that word", "What is the capital of France? Then what is the weather there?"). "Explain why" after a
  step gives that step's reasoning.
- **New small engines:** number facts (prime, even, factors, divisibility), word tools (spell backwards, count
  letters or vowels), per-item word problems and syllogisms with a named member.
- **Grammar:** a past time word now gives the past tense ("she go to school yesterday" becomes "She went to
  school yesterday"), and contractions are handled when changing tense.
- **Side-by-side with Qwen2.5-0.5B-Instruct**, a transformer of similar size: see
  [COMPARISON_QWEN_0_5B.md](COMPARISON_QWEN_0_5B.md) for the results and the improvement list.

## New in 0.2.6

CAEL talks more, knows more and works out its own answers. Every engine is still non-neural at runtime: rules,
counts, WordNet, LSA and full-text search.

- **Own advice answers** ([thinking.py](cael_unified/thinking.py)). For "how do I…" questions CAEL finds related
  discussions by meaning, pulls out the advice and reasons, groups advice that says the same thing, counts how
  many separate answers agree, and writes the answer in its own order and words. It does not copy a reply. When
  the answers do not agree enough, it says it is not sure.
- **Everyday knowledge** ([life_advice.py](cael_unified/life_advice.py), [life_knowledge.py](cael_unified/life_knowledge.py)):
  hand-written advice for 181 everyday topics. Discussions that agree move points up.
- **Recipes and trips.** Recipes compare the Wikibooks Cookbook versions of a dish; trip plans start from the
  Wikivoyage guide. Answers link the discussions, recipe or guide that backed them.
- **Chattier conversation** ([chat_extra.py](cael_unified/chat_extra.py), [chat_corpus.py](cael_unified/chat_corpus.py)):
  follow-up questions, reactions to news, small talk that asks back.
- **Dictionary and grammar** ([dictionary.py](cael_unified/dictionary.py), [grammar.py](cael_unified/grammar.py)):
  WordNet 3.0 definitions and synonyms; sentence corrections that name the rule.
- **More reasoning** ([reasoning_extra.py](cael_unified/reasoning_extra.py)) and Wikidata answers to "who
  wrote / painted / invented…".
- **Results:** 102 / 102 on the labelled chat, vocabulary, grammar and reasoning evaluation; on 50 fresh held-out
  advice questions, 43 answered in CAEL's own words, 3 got a labelled similar answer, 4 not sure, 0 wrong.
- **Licence of the new knowledge:** `models/cael-thinking-v2` contains material derived from Stack Exchange,
  Dolly, Wikibooks and Wikivoyage, so it is shared under **CC BY-SA 4.0**. Sources are listed in each model
  folder's `SOURCES.md`.

## New in 0.2.5

Engines that work together, check each other and learn. Every engine is still non-neural at runtime. The
model bundle has the same models as 0.2.4; everything new is code.

- **Engines work together** ([orchestrator.py](cael_unified/orchestrator.py)). A request with several parts
  ("What is 12 × 7? Then multiply it by 3") is split into steps. Each step goes to the right engine, and
  results pass between steps through a shared board: "it", "that" and "the result" mean the earlier answer,
  and "run it on 15" calls a function an earlier step wrote.
- **Multi-step reasoning** ([reasoning_compose.py](cael_unified/reasoning_compose.py)):
  - Questions inside questions: "Where is the person who has the football?" first asks who has it.
  - "Who is in the kitchen?" checks where each person is.
  - Hypotheticals: "If John goes to the garden, where is John?" uses a copy of the facts.
  - Several questions about the same facts are each answered.
  - "X, then Y" in a story is read as two events.
  - bAbI accuracy is unchanged at 99.9%.
- **Self-learning rules** ([rules.py](cael_unified/rules.py)):
  - A function learned from three or more examples is searched for again with each example hidden in turn,
    and it must predict the hidden one. Only rules that pass are kept, and they can be reused later
    ("run area on 6, 7").
  - "That's wrong" lowers a rule's confidence until it's forgotten.
  - Number sequences ("what comes next: 2, 6, 12, 20, 30?") are solved the same way: the rule must predict
    the last given number first.
- **Independent checks** ([verify.py](cael_unified/verify.py)). Each check works the answer out another way:
  arithmetic is recalculated, equation solutions are put back into the equation, code is run on your
  examples, and logic proofs are checked again with case analysis. A wrong answer is corrected or flagged.
  Looked-up facts are marked unchecked.
- **Long-term memory** ([ltm.py](cael_unified/ltm.py), `state/ltm.json`). Learned rules, confidence and
  per-engine check counts persist across conversations. Text people type is never stored; rule examples are
  kept only if they are plain numbers.
- **Python coding:**
  - Plain descriptions ("write a function that removes duplicates") get working code. The code is found by
    search and tested on held-out cases.
  - A small loop search covers Fibonacci, primes and similar.
  - "Fix this code" repairs common syntax errors, and "what does this code do?" explains code.
  - Python concepts are explained, and standard-library recipes cover file and web tasks.
- **Everyday chat:**
  - The time and date.
  - Day planning.
  - Meal, book and film ideas.
  - Short poems.
  - Well-known distances and figures.
  - "I have 3 apples and buy 5 more, how many do I have?".
- **Translation:** about 20 common phrases in 59 languages, plus "what does arigato mean?" and "say cheers in
  all languages". It's a hand-written phrase table, not a translator.

## New in 0.2.4

Every engine is still non-neural at runtime.

- **Pictures, rebuilt (image model 0.4.3).**
  - **Training data:** 22,110 local Stable Diffusion 1.5 renders across 114 subjects, including 2,400 varied
    head-and-shoulders portraits.
  - **One structure per picture:** each picture takes its shape from one real render, bent into a new pose,
    with the texture rebuilt from two sources. The old two-source mixing produced two-headed or broken
    subjects; this doesn't.
  - **Rigid things:** cars, chairs, phones and houses are never bent. They're mirrored, shifted, scaled and
    repainted on the bodywork only, with tyres, glass and chrome kept.
  - **Other improvements:** best of 8 sketches, a 256-pixel detail pass, seam blending, and photo style unless
    you ask for an illustration.
  - **Copy check:** every picture must stay at least 15 RMSE away from any single training render, measured at
    64 px and including mirror images. This is a deliberate trade of novelty for coherent shapes; previously
    the floor was 25.
  - See [IMAGE_HYBRID_0_4_3.md](IMAGE_HYBRID_0_4_3.md).
- **Faces.**
  - Portrait requests use the main model.
  - Faces are landmark morphs of three similar-looking people, using 68 facial landmarks found offline with
    OpenCV LBF. OpenCV isn't needed at runtime.
  - The result is varied, coherent faces with no smeared or doubled features.
- **Picture requests understand more:** new subjects and backgrounds (mouse, fox, wolf, deer, dolphin, desert,
  snow, sky, ocean, park, field, room), and "make a portrait of a man" right after another picture starts a
  new picture.
- **Prompt helper:** "make image of a dog" becomes a detailed, ready-to-use image prompt. CAEL keeps your words
  and adds subject detail, setting, light, framing and finish suited to the subject; things to avoid are
  listed separately.
- **Vynly helper:** CAEL answers questions about vynly.co (posting, provenance, Sparks, Trails, agents, account,
  privacy, rules), each with a link to the page. Its knowledge comes from the public site and owner-approved
  documents. A server-side site proxy can mark its requests with the `site_proxy` setting.
- **Chat and helper:** negated feelings ("I don't feel so good") get sympathy instead of cheer. The fallback no
  longer guesses emotions. Spelling repair, quantities, rates, groups, source-quality and factual-boundary work
  is included (see [CHAT_HELPER_0_4_6.md](CHAT_HELPER_0_4_6.md)).

## New in 0.2.3

Every engine is still non-neural.

- **Reasoning with "or" and contradiction.** Premises become true/false constraints
  and a small SAT solver checks every case. It covers "Rex is a cat or a dog",
  "No mammal is a fish", "Birds can fly" and contradictory premises.
  - PrOntoQA test: **99.34%**, up from 70.3%.
  - All 20 bAbI story tasks are supported: **99.82%** on the test split, up from 12
    task types. That includes pronouns, time order, analogy, positions, compass
    directions and motivations.
  - See [REASONING_0_4_2.md](REASONING_0_4_2.md).
- **Reasoning answers in chat.** Answers are full sentences followed by the numbered
  premises they rest on. Guesses are labelled as guesses, and contradictory premises
  are reported.
  - It accepts natural wordings such as "Does it follow that…".
  - Ordinary messages that only look like puzzles go to normal chat.
- **Reasoning about pictures.**
  - Several objects per picture, placed as asked: left/right of, between, on, above,
    under, in front of, behind.
  - Sizes follow real life, so an elephant is drawn larger than a cat.
  - Subjects can be described indirectly: "the animal that says moo" draws a cow, "a
    poodle" draws a dog, "a yellow fruit" draws a banana. Each choice is explained.
  - Follow-ups edit the last picture: "make it blue", "add a dog to the left of the
    sofa", "put them on a beach", "remove the cat".
  - It says plainly what it cannot draw and when a request breaks common sense.
  - See [IMAGE_REASONING_0_4_3.md](IMAGE_REASONING_0_4_3.md).
- **Multiple-choice questions in chat:** the count language model, local evidence
  retrieval and an exact word-problem solver work together. Local Open SLM Leaderboard
  tests: five-test mean 49.97%, against 32.69% before. ArithMark-3 scores 69.5%,
  against 59.6% for SmolLM2-360M. See [LEADERBOARD_0_4_1.md](LEADERBOARD_0_4_1.md).
  This is not an official leaderboard entry. The optional ARC Corpus index is not
  bundled.

## New in 0.2.2

Every engine is still non-neural (no neural networks or transformers at runtime).

- **Pictures:** a new hybrid image model with **102 topics**. A per-topic PCA layout
  is filled in by patch synthesis from two same-style training renders, at 128×128.
  It understands colour, style (photo, illustration, side view), count (up to three)
  and scene in a request. Colour, count and scene edits are experimental. See
  [IMAGE_HYBRID_0_3_9.md](IMAGE_HYBRID_0_3_9.md).
- **Teaching answers:** "explain the rules of chess", "how do I make bread" and "how
  does a jet engine work" are answered from the relevant sections and lists of the
  matching Wikipedia article, not a one-line definition.
- **Conversation:** authored small-talk rules (greetings, thanks, feelings, questions
  about CAEL) and memory of facts said earlier in the same chat window ("where do I
  live?"). Factual questions it cannot verify get an honest "I cannot answer that"
  instead of small talk.
- **Lookup fixes:** misspelled subjects ("megadeath"), founding dates anchored to the
  right entity, weather for remembered or misspelled places.
- **Python from examples:** describe a small function and give two or three examples
  (`double(2) == 4`). CAEL searches over small Python operations for code that fits.
  See [CODE_SYNTHESIS_0_3_8.md](CODE_SYNTHESIS_0_3_8.md) for the held-out results
  and limits.
- **Language, knowledge and creative models** from the 0.3.x research runs, as
  selected for the live assistant (count language 0.3.2, local knowledge, story and
  prompt writer 0.3.7-r2).

```bash
python -m cael_unified "Calculate (12 + 3) * 4"
python -m cael_unified "Make an emoji of fire" --seed 42
python -m cael_unified "Make a picture of a car" --seed 42
python -m cael_unified "Create a portrait of an adult woman" --seed 42
```

Images are saved under `outputs/unified/`. True resolution is **64×64**;
the UI enlarges them. `--mode chat`, `--mode emoji` and `--mode image` override
automatic routing. `--json` returns structured results and paths.

```python
from cael_unified import Assistant

assistant = Assistant()
result = assistant.respond([{"role": "user", "content": "Make a picture of a bicycle"}], seed=42)
print(result["response"], result.get("paths"))
```

## Model components

| Component | Implementation | Limits |
|---|---|---|
| Chat | Legacy CA routing/small-talk models and a small factual store | Limited fallback; current remote worker absent |
| Helper | Exact bounded arithmetic, existing authored writing programs, story/event memory | Handwritten task programs; no general tool execution |
| Emoji | v7 integer patch CA, silhouette guidance, speckle cleanup | Finite vocabulary; unfamiliar words may be ignored; offline |
| Portrait | v15 registered shape/appearance statistics | Unconditional adult-woman portraits; averaged faces and artifacts |
| Picture (0.2.4) | Hybrid 0.4.3: one real structure per picture, texture rebuilt from two SD1.5 training renders; landmark face morphing; scene reasoning composes cut-outs | 114 topics; pictures can stay recognisably close to one training render (copy floor 15); multi-object scenes look rough; most cars are grey/silver (training data) |
| Reasoning | Rule chaining, SAT case analysis, event/position/time tracking | Simple sentence forms ("X is a Y", "Every X…", "X went to the Y") |
| General picture (0.2.1) | Subject-conditioned statistics based on portrait code | Fallback only; 32 categories; rough images |
| Explanations | Section selection from the matching Wikipedia article | Quoted text (CC BY-SA); encyclopedic, not recipes |
| Code | Example-guided search over small Python operations | One-line functions; needs examples |

General subjects: **car, bicycle, motorcycle, truck, airplane, boat, phone,
laptop, camera, headphones, watch, robot, woman, man, dog, cat, horse, bird,
dragon, flower, tree, house, city, mountain, beach, forest, pizza, burger, cup,
chair, shoe and spaceship**. Aliases such as "bike" and "smartphone" work.
Multi-category or unseen subjects return the supported vocabulary rather than
pretending the requested composition was learned.

The eight stored emoji entries (harp, hedgehog, kiwi bird, lighthouse, make,
saxophone, snowflake and tractor) are retained for offline reuse, with their
original source attribution. Reference-derived outputs carry attribution and,
where applicable, CC BY-SA terms in `attribution.json` beside the images.

The latest chat worker and web lookup run on another computer and were not
available here. This release includes a working portable legacy fallback and
preserves older v6.7 source in `chat_v6_7/`; its optional large stores still
require rebuilding. It does **not** contain the missing remote worker or private
credentials. Offline chat has no live web lookup.

## General-image training

The student reuses portrait registration and appearance code. Data come from
**local neural Stable Diffusion 1.5 generation**, not the private portrait
collection. Runtime sampling uses statistical modes and deformation fields,
without the teacher. Do not describe this as "no neural networks in training."

The first curriculum contains 1,024 synthetic images, 32 per subject. Pixel
groups are split before fitting and held-out groups are protected across all
categories. Models learn from fitting images only. Frozen results and
generated-only examples are under `results/general-0.2.1/`.

Install `requirements-training.txt`, start a local `stable-diffusion.cpp` server
with an SD1.5 checkpoint, and run:

```bash
python cael_image/generate_general_dataset.py --out research/general_synthetic --model-sha256 CHECKPOINT_SHA256
python cael_image/train_general_appearance.py --dataset research/general_synthetic --out models/general-reproduction
```

The generator accepts only localhost and resumes frozen batches. It records
prompts, seeds, settings and hashes. Training images are processed in code;
source previews are not produced.

## Privacy and evaluation

No private source photo, private alignment record, credential or teacher
checkpoint ships. Portrait weights contain aggregate learned statistics.
Emoji guard references are public Noto/Blobmoji pixels; general-image guard
references are synthetic fitting pixels. These support numerical rejection and
emoji shape statistics, not retrieval as finished photo outputs.

Stored learned emoji entries additionally include their licensed OpenMoji,
Twemoji, Emojitwo, Fluent and Commons references. Their separate terms and
credits are preserved in the bundle and `licenses/LEARNED-EMOJI-NOTICE.md`.

The original portrait guard needs private source photos, which are not
redistributed. Public portrait generation checks only against synthetic
references, not private portraits. This does not guarantee anonymity or absence
of memorization. The synthetic-image cutoff is 0.04; portrait sampling retains
a 0.12 cutoff against public references. Neither similarity nor synthetic
category separation measures realism.

```bash
python -m unittest discover -s tests -v
```

Tests cover story memory, routing, arithmetic, subject matching, bundle/cache
integrity, path traversal and the local HTTP boundary. Original Story 0.1
training and evaluation remain: [documentation](STORY_MODEL.md),
[model card](STORY_MODEL_CARD.md).

## Licenses

CAEL code and owned models are under the [CAEL Non-Commercial License](LICENSE): free for personal and
research use; commercial use needs a separate licence from the copyright holder. CAEL only uses third-party
material that allows commercial use; see [provenance notices](NOTICE.md). Components derived from CC BY-SA
sources (Wikipedia, Stack Exchange, Dolly, Wikibooks, Wikivoyage) stay under CC BY-SA. Public emoji references retain Apache and
Unicode notices. Synthetic-data-derived general-image weights are also subject
to [CreativeML OpenRAIL-M](licenses/LICENSE-stable-diffusion-v1-5.txt), including
paragraph 5 and Attachment A. Those restrictions apply to use and redistribution
of these weights and downstream derivatives. Notices are inside the bundle.

This first general-image model is a limited experiment. It cannot generate
everything a modern diffusion model can, or promise photorealistic outputs.
