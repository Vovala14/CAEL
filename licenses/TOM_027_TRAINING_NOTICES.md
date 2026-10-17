# CAEL unified count-language training data

Social IQa: Maarten Sap, Hannah Rashkin, Derek Chen, Ronan LeBras and Yejin Choi,
2019, SocialIQA: Commonsense Reasoning about Social Interactions, EMNLP.
Publisher: https://maartensap.com/social-iqa/
Publisher-hosted card: https://huggingface.co/datasets/allenai/social_i_qa
Data licence: CC BY 4.0, https://creativecommons.org/licenses/by/4.0/
Full terms: LICENSE-CC-BY-4.0.txt in this directory.
Only official training rows supply fitted counts. Official development rows
supply parameter selection. The publisher describes human-curated answers and
some adversarially filtered machine-generated alternatives; the complete
published dataset is used under its CC BY 4.0 terms. The normalized model compiles sparse context
features, correct/contrast answer-token counts and prefix transitions; raw
training examples are not stored in its runtime checkpoint. These transformations
do not imply that the data authors endorse CAEL. Pinned hashes/cards are retained
in research/tom_027/sources.json and research/tom_027/sources/.

WordNet 3.0, Copyright 2006 Princeton University. Permission to use, copy, modify
and distribute for any purpose without fee or royalty, subject to retaining the
full licence and disclaimer. Full licence: LICENSE-WordNet-3.0.txt, copied unchanged
from the distribution. Primary terms:
https://wordnet.princeton.edu/license-and-commercial-use
The candidate compiles single-word synset relations into a normalized token-mass
transfer table and lexical query expansion. All relations remain authored lexical
knowledge, not concepts discovered by a cellular automaton. NLTK distribution
revision and archive checksum are retained in research/tom_027/wordnet_source.json.

Original social-situation templates and their slot-filled variations were
authored in this coding session. They are synthetic schemas, not independently
collected human conversations. No separate neural teacher was run to generate
training material. No private user conversations, images, MICA weights/outputs,
FLUX outputs, non-commercial-only ExploreToM data or Tiny ToM examples supply fits.

Tiny Theory of Mind by Axiomic Labs is Apache-2.0, evaluation only. Full terms:
LICENSE-Tiny-Theory-of-Mind-Apache-2.0.txt. Contexts/endings are used for scoring;
labels and metadata are used only afterward for evaluation reports. Exact-context
hashes are also used to check training contamination, without reading labels.

scikit-learn and SciPy are BSD-licensed computational libraries; their installed
distribution notices are retained. No neural layers/attention/gradient optimizer
are used. This notice does not alter CAEL's existing software licence.
