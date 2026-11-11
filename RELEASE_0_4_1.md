# CAEL 0.4.1: conversation skills, chat memory and checked web answers

CAEL 0.4.1 keeps the 0.4.0 core engines and adds conversation upgrades made while comparing CAEL with
Qwen3.5-0.8B in blind, self-judged chat rounds. CAEL is still non-neural: no neural weights and no LLM
produce its replies.

## What is new

- **Exact conversation skills** (`cael_unified/chat_skills.py`):
  - quantities with transfers and pronouns;
  - rates and speeds, including "what if" follow-ups;
  - price multiples;
  - clock times with delays;
  - syllogisms, and the converse question ("does that mean every … ?");
  - weekly schedules with cancellations;
  - values the user changed;
  - short notes and tone rewrites;
  - replies about feelings, plans, birthdays and interests.
- **Chat memory** (`cael_unified/chat_memory.py`):
  - answers questions about what the user said earlier in the conversation;
  - acknowledges new facts and goals;
  - re-answers a question when the user adds a detail.
- **Checked web answers** (`cael_unified/web_check.py`):
  - when CAEL does not know, it searches the web, not only Wikipedia;
  - it answers only when a second, independent publisher agrees;
  - names and distances are chosen by agreement among sources;
  - calculations over the user's own numbers never go to the web;
  - private turns are never sent in a search.
- **Open-chat index** (`cael_unified/open_chat.py`, optional resource `cael-open-chat-v1`):
  - about 285,000 human-written answers from Stack Exchange (CC BY-SA 4.0), OpenAssistant (Apache 2.0) and databricks-dolly-15k (CC BY-SA 3.0);
  - it is also used to weigh how informative each word is;
  - without it, CAEL falls back to simpler weights and fewer open answers.

The 0.4.0 input validation and checked helper routes are kept and run alongside the new layers.

## Measured result (honest limits)

| Round | Opponent | CAEL Elo (Qwen3.5-0.8B = 1000) | 95% interval | CAEL wins / losses / ties |
|---|---|---:|---:|---|
| 4 | Qwen3.5-0.8B | 747 | 561–878 | 2 / 15 / 3 |
| 5 (this build) | Qwen3.5-0.8B | **796** | 611–915 | 3 / 14 / 3 |

How the comparison was run:
- Each round used 20 fresh conversations, written after the build was sealed.
- The pairs were judged blind and rated with Bradley–Terry with a bootstrap.

Caveats:
- The same agent developed CAEL, wrote the conversations and judged them. That is a conflict of interest.
- Blinding is weak, because the two styles are easy to recognise.
- CAEL ran with web lookups on; Qwen ran offline.
- 20 conversations is a small sample, and the two rounds' intervals overlap.

**CAEL 0.4.1 does not match Qwen3.5-0.8B at general chat.** The main remaining losses:
- web lookups that decline on advice and how-to questions;
- generic acknowledgements;
- some follow-up questions are missed;
- off-topic retrieved answers.

The round-5 inputs, replies, blind packets, votes and ratings are attached as `chat-round5-evidence.zip`.

## Install

Use Python 3.12. Download `CAEL-0.4.1.zip` and extract it. Then, from the extracted folder:

```bash
python -m pip install -r requirements-unified.txt
python -m cael_unified --download
```

`--download` fetches the unchanged 0.3.7 resource bundle. For the full chat behaviour, also extract
`cael-open-chat-v1.zip` into `models/`, so that `models/cael-open-chat-v1/open.sqlite` exists.
