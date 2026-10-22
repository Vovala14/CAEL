# CAEL 0.2.9

Chat, helper, reasoning, math, Python, stories, prompt helper and emoji in one
checksum-verified bundle. Picture/portrait generation checkpoints and their model
selections are excluded. Existing workspace image models are not deleted.

This release includes the verified local 2026-10-22 improvements: exact fraction
propagation, decimal source precision, independent arithmetic verification,
percentage chains, ambiguous-root clarification, Python explanation routing and
conservative explicit-premise multiple-choice reasoning. It retains the existing
prompt composer, spelling interpretation, helper tools, bounded Python interpreter
and non-neural language checkpoint. The language architecture and CA kernels are
unchanged. Python support remains bounded; it is not general Python understanding.
The portable dictionary now includes the licensed frequency list used by spelling,
synonym ranking and spelling-based rhymes, instead of relying on a local data folder.

Experimental event parsing improved on local parsing diagnostics, but its
HellaSwag scorer reached 27.74%, below the unchanged native baseline 27.97% and
the prior experimental 28.06%. The learned compatibility follow-up failed its
independent development gate. These experimental scorers/checkpoints are not
selected or shipped. These are repeated local validation results, not a new
official leaderboard submission or a claim of improved HellaSwag performance.

Installation: install requirements-unified.txt, then run
`python -m cael_unified --download` and `python -m cael_unified --ui`.
The GitHub source ZIP and model archive are separate downloads. `--download`
fetches and installs the checksum-verified model automatically. Install into a
fresh directory to use the release selections: installation deliberately
preserves differing local files/selections.

The software licence is unchanged. Dataset-specific licences and attribution
remain inside the bundle and licenses/; they do not relicense CAEL. Private
photos, conversations, credentials and research datasets are not included.

Release regression validation: 266 tests and 6 subtests passed, including
arithmetic chains, Python tools, explicit-premise reasoning, image-prompt
composition, bundle validation and anonymous session isolation. This is
functional regression evidence, not a benchmark performance claim.
The full existing CI unittest suite also passed in a fresh extracted installation:
514 tests, with two optional integrations skipped. These suites overlap.
