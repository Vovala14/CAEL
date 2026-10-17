# Subject and historical-date retrieval fix

The reported question, `When the light blob was invented?`, previously fetched
Lava lamp and could not answer. This was a topic/answer-selection failure,
not evidence that the reasoning-training scores measured general chat accuracy.

Changes:

- Parse both `When was X invented?` and `When X was invented?`, and extract
  the subject from `Who invented X?`.
- Compare a possible multiword typo against phrases in licensed local article
  titles. Only suggest a unique candidate with one changed word and a close
  spelling. Mark uncertainty in the reply; avoid single-word guessing and tied
  candidates. User conversations do not become spelling-training data.
- Recognize sufficiently specific multiword subjects inside longer titles,
  such as light bulb within Incandescent light bulb.
- Require an actual dated event passage. A History heading alone is insufficient.
  Prefer the article overview; retain century/decade precision and distinguish
  invention milestones from later upgrades, unrelated institutions and nationality
  adjectives such as German-born. Preserve explicit multiple-inventor evidence.
- Search online using the extracted subject. Reject unrelated search hits before
  downloading or caching their articles, rather than automatically citing the
  first result.

The new logic is non-neural lexical and extractive code, not a new general language
model or an additional reasoning-training run. It uses the existing licensed
Wikipedia text snapshot (CC BY-SA 4.0), retaining revision links and attribution.
No private photos were accessed; release copies were not changed.

Validation: 116 unit tests pass. Ten targeted questions were checked offline
with zero provider calls and through the running public worker, including the
exact reported wording and other inventions/birth dates. The public URL is
unchanged. Full responses: `research/accuracy_024/verification.json`.

These are targeted regression checks, not a general factual-accuracy benchmark.
Some broad invention questions still lack a reliable direct answer and should
abstain rather than supply a date for a subsidiary technology. Source excerpts
also inherit limitations of their underlying reference revision.
