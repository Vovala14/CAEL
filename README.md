---
language:
- en
license: other
license_name: cael-non-commercial
license_link: https://huggingface.co/vynly/CAEL-0.3.9/blob/main/LICENSE
pipeline_tag: text-generation
tags:
- cael
- non-neural
- cellular-automata
- symbolic-reasoning
- conversation-memory
- code-generation
inference: false
---

# CAEL 0.3.9

A custom Python assistant built from non-neural symbolic, count and automaton
engines. This release improves conversation follow-ups, explicit state tracking,
checked arithmetic/Python rechecks, personal-evidence attribution and bounded
source lookup. It does not use Transformers, a neural model or Qwen at runtime.

The 0.3.9 source includes the qualified symbolic dialogue/state tables. The larger
public resource archive remains the byte-identical `cael-0.3.7.cael`; its version
is reported separately from the 0.3.9 application. Picture/portrait weights are
excluded from this public package. Chat can prepare an image prompt instead.

## Run

Use Python 3.11 or later. Extract [CAEL-0.3.9.zip](./CAEL-0.3.9.zip), then run in
the extracted folder:

```bash
python -m pip install -r requirements-unified.txt
python -m cael_unified --download
python -m cael_unified --ui
```

Open http://127.0.0.1:8765. For a terminal conversation use
`python -m cael_unified --mode chat`. A reset starts a new visible conversation;
do not use the shared demo for sensitive information. Public lookup uses free
search/page readers and can be disabled with `CAEL_WEB_SEARCH=0`.

This is a custom runtime, not a Transformers-compatible checkpoint. Both the
source archive and the approximately 563 MB resource archive are required.
The installer preserves existing local model selections and reports conflicts.
Licences and attribution are retained in LICENSE, NOTICE.md and licenses/.

## Improvements

- Follow-up requests retain supported task, style, option and user-evidence state.
  Arithmetic rechecks recalculate the original request; unrelated tasks block stale reuse.
- Complete literal Python examples, including keyword calls, are checked through
  the existing bounded AST interpreter. The checker policy used in qualification
  is installed automatically by the public Assistant entry point.
- Finite readers handle exact quantities, explicit owners/units/times, conditional
  options and dictionary workflows. Unsupported or incomplete contracts clarify.
- Definition comparisons can retain two source-linked definitions. Public search
  extends beyond Wikipedia; retrieved text is evidence, not proof of truth.
- Request learning is ephemeral by default. Explicit supplied histories retain
  within-conversation context; unrelated sessions do not share learned rules.

## Measured scope

The latest authored conversation study compares this candidate with the preceding
**conversation R2 development candidate**, not the published worker or Qwen.
Source froze before fresh transfer questions were written. All 186 formal replies
were fully inspected, including failures, code and extra assertions.

| Fresh authored transfer | Previous conversation R2 | Conversation R3 / 0.3.9 source |
|---|---:|---:|
| Useful answers | 10/29 | 22/29 |
| Boundary handling (clarification/refusal included) | 7/12 | 12/12 |
| Complete conversations containing positive work | 2/14 | 9/14 |

The candidate passed 332 inherited tests, 18 subtests and 124 focused checks.
Repeated runs are not additional unique abilities. These are same-author,
adaptive/unblinded development-family results, not standard benchmark accuracy,
an independent Qwen win, or complete runtime/security certification.
Evidence and all reviewed transfer failures are under
`benchmarks/conversation_039_r3/`. Release packaging/integration checks are
reported separately in RELEASE_0_3_9.md and the release manifest.

## Remaining limits

Some selection wording repeats a stale choice. Some dictionary guides lose their
topic on follow-up; richer examples and multi-definition rechecks can still fail.
Source retrieval is lexical and incomplete. A link does not make an answer verified.
Supported forgetting is not whole-transcript erasure or a general privacy guarantee.
Finite grammar/VM coverage does not establish arbitrary English/Python understanding.

Earlier broad comparisons did not establish general superiority over Qwen; an
earlier execution-policy deviation and session-contamination findings remain
disclosed in their original evidence. State tracking development is not a clean
StateBench victory. No new external benchmark score or live-web accuracy score
is claimed for this release. AI-assisted development and unblinded review apply.
