# Brief given to independent question writers (CAEL 0.3.6)

The same brief is used for the 0.3.6 **development** set (written before development) and for the 0.3.6 **final
evaluation** set (written by a separate writer after the 0.3.6 freeze), with a different output folder and the
instruction to invent new names, places, wordings and plans. Writers never see CAEL's source, rules, earlier questions
or results; they work in a sealed folder and use a different model from the CAEL developer.

Format: one JSON object per line
`{"id", "category", "features", "history": [{"role","content"}...], "question", "criteria": {"any","none","clarify","no_clarify","abstain"}}`
graded by `benchmarks/context_035/grade.py` (case-insensitive whole-word matching; `any` = every group needs one match;
`none` = outdated/wrong values that must not be given as current; `clarify` = genuine conflict must be flagged;
`no_clarify` = control, answer directly; `abstain` = never stated, must say so without guessing a distractor).

Categories (400 items): memory 50, update 50, reference 40, conflict 50 (about 30 genuine, 20 controls), planning 50,
reasoning 80 (compositional: combine two or more stated facts or rules), unsupported 80 (never stated; plausible
distractors present).

Conversation length: 5–50 messages, except at least 25% of every category are **long** conversations of 100–200
messages (tag "long") with the key facts spread across the whole conversation, and corrections/updates far from the
original statement.

Required features across categories: passive voice, negation, indirect/reported statements, unusual structures
(clefts, fronting, parentheticals, lists), paraphrased questions that share no content wording with the statement,
multi-step reasoning. Tag each item honestly.
