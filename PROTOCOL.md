# CAEL Story0.1: frozen training/evaluation protocol

Separate hybrid symbolic model family, not native MICA. No neural network. Handwritten closed English parser and slot formatting, expert-authored ontology/event plans and template-like regular grammar; learned integer local field-update rules, plan transitions and grammar counts.

Train30000unique single canonical frames and5000multi-event episodes (2–4frames from TRAIN only), seed2026101317. Fixed ontology12actors/14objects/8places/8goals/4skills. Canonical semantic frame SHA determinesTRAIN90%/development5%/confirmation5%. Exclude all supported20legacy natural prompt frames from training. Match baseline to preserved model SHA25bf1c55aff6198640799f8f860b031f2b693d7ef67eae3647d1916aa83ce363.

Development2000frames and confirmation2000frames; disjoint canonical frames, single and multi training use onlyTRAIN. Evaluate200held-out2–4-event development sequences and200confirmation sequences. The baseline and candidate get exactly the same event streams. Score event-state arrays after each event against the independent teacher function; missing learned rule is an explicit failure. Do not adjust on confirmation.

Acceptance: all4000single-frame plans/state trajectories correct, no candidate state mismatch/missing rule across400cumulative sequences, and candidate no worse than baseline. Report baseline failures and candidate successes descriptively. State checks verify generalization within the same authored world schema; they are not general reasoning, Tiny ToM or language-understanding benchmarks.

Generate20legacy natural requests; report support/rejection, full raw text, four query forms where facts are established. Historical18/20same-agent blinded quality result belongs only to the old prototype. No new independent blind quality score claimed. Additional parser-negative/locality/fork tests must pass.

Publish full model SHA, training/data/code identities, size, deterministic scripts and limitations. Training frames/episodes are reproducible from seeds; raw generated examples and machine metrics shipped. No user private data, external language model, benchmark questions, MICA artifacts or credentials in repository/release.
