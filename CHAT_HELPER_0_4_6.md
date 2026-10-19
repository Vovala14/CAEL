> Deadline run closed: experiments stopped and the specific heartbeat is
> PAUSED. The live site stays running on internal runtime 0.4.13 / app 0.2.3.
> Final evidence and limitations: research/chat_045/FINAL_REPORT.md.

# Overnight chat/helper work: runtime 0.4.5–0.4.6

Latest follow-up: **0.4.13 factual topic-boundary guards are live**. A comparison
or question about the literal word “it” now clears stale subject context before
a later ambiguous follow-up. 334 regression tests, 20 authored checks and six
public jobs passed; see `research/chat_0413/REPORT.md`. The current verified
overnight summary is `research/chat_045/OVERNIGHT_VERIFIED.md`.
Prior 0.4.12 rates, 0.4.11 source integrity, 0.4.10 groups, 0.4.9 source focus,
0.4.8 news scope and 0.4.7 quantity continuity retain their own evidence.
No language fitting or new leaderboard result is claimed. Coverage remains
bounded. The older apparent photosynthesis corruption was a console-display
error; stored Unicode was healthy and no corpus repair was performed.
The report below preserves earlier 0.4.6 evidence.

Owner deadline: **18 October 2026, 06:00 Asia/Jerusalem (03:00 UTC)**.
Work remains authorized until that fixed deadline. The app/bundle is still
**CAEL 0.2.3**; these are local runtime improvements, not new published releases.

## Live improvements

- **Typed quantity reasoning.** Exact quantities are tracked separately for each
  person and item type. Transfers debit the giver and credit the receiver.
  Unknown starting amounts stay unknown. Unsupported clauses, conflicting
  amounts, negative inventories, ambiguous pronouns and missing units ask for
  clarification. `why?` can show the steps for the supported problem.
  Starting quantities must precede events; late starting declarations are
  rejected rather than being silently applied at the wrong time. Money/prices
  and general multi-step algebra are outside this item-count parser.
- **Multiline chat box and New chat.** Pasted scenarios and Python examples
  preserve line breaks. Shift+Enter adds a line; desktop Enter or Ctrl/Command
  Enter sends. Mobile plain Enter remains a newline. New chat clears the draft
  and local conversation; it is disabled while a response is pending. Thinking
  animation, source links, ownership checks and the responsive layout remain.
- **Factual follow-ups.** A named public topic can carry across questions such
  as `Tell me about Metallica`, `When was it formed?`, `Who formed it?`.
  Topic resolution uses this conversation's user questions, not remembered
  assistant assertions. Every answer still goes through source lookup. Current
  questions retain their freshness controls. With no usable topic, `What is it?`
  asks for clarification. Personal/task interruptions and comparisons break
  this context; quoted pronouns and titles/acronyms such as `It` and `IT` are
  protected from substitution. Interpretations appear in About this result.
- **Better spelling controls.** Polite numeric calls such as
  `Could you calclate (137 + 9) * 4?`, `please hlpe me`, and weather/time typos
  now work within narrow contexts. Names before inventory/event verbs and real
  words remain protected. `I feel tried` is deliberately left unchanged;
  deciding that `tried` meant `tired` would change a valid word.
- **Routing/evidence fixes.** `please help me` gets a helpful chat response.
  The news classifier requires a current-event cue before an out-of-domain
  positive score can trigger news lookup. A date-only passage is no longer
  enough for a question asking who founded/formed something.

## Verification

- **258 regression tests passed** in `research/chat_046/tests_deploy.log`.
- **300/300 authored quantity development cases passed** through Assistant's
  real unified entry point: five positive families and five refusal/ambiguity
  families, varied names, numbers and item types. See
  `research/chat_046/quantity_verification.json`. These templates are targeted
  development checks, not independent broad reasoning accuracy.
- The **same reused spelling development set improved from 16/20 to 19/20**;
  all 64 valid controls stayed unchanged. This reused set helped development
  and is not an independent evaluation. New name/code/weather/help controls
  are in `tests/test_typo_context.py`.
- Two three-turn factual chains (Metallica and photosynthesis) used the actual
  local licensed snapshot with **zero network attempts** in
  `research/chat_046/local_factual_chains.json`. Responses can still repeat an
  introductory passage; topic binding is not unrestricted comprehension.
- **11 synthetic public HTTPS job checks passed**, including factual chains,
  typo/help/weather clarification, multiline quantity reasoning, unknown
  inventories and late-start refusal. Another session received 404 for the test
  job. GIF/source attribution and updated composer HTML were checked. See
  `research/chat_046/public_verification.json`.
- Real browser interaction checked multiline paste, Shift+Enter, keyboard send,
  New chat/reset, pending-state disabling and final explanations. Screenshot:
  `research/chat_046/live_helper_ui.png`. This was a desktop browser check;
  no claim of an actual iPhone/device test is made. The temporary synthetic UI
  preview server was stopped after verification.

## Preservation and deployment

Only the ownership-checked recorded public worker was reloaded; the tunnel,
session key and URL stayed intact. Latest recorded worker PID: **30612**;
tunnel PID: **25420**. Read `research/shared_021/processes.json` for current
ownership before any later action. Deployment evidence and source hashes are
in `research/chat_046/deployment.json`.

All active model selections, including Claude's image selections, are unchanged
from 0.4.4. The spelling checkpoint remains the same checked
`cael-text-repair-0.4.4-r1`; this phase extended its bounded runtime interpretation
and authored exact solvers, and did **not** retrain the count language model.
No neural network/transformer or core architecture change was introduced.
Only authored code/cases and existing licensed public text/word statistics were
used. Existing licences and attribution remain.

The selected choice.py and wordmath.py hashes are unchanged. No new leaderboard
run or score gain is claimed. Published bundles, release_0_2 and CAEL_push were
not edited; no commit/push/release was made. Exact previous helper sources and
other changed sources are preserved under research/chat_045 and chat_046.

Claude's image supervisor processes **2988/8016** were still running; its named
log reached **55/342 units at 01:32:29 local time**. This work did not change
that job, render images or view private training photos/crops.

## Remaining work until the deadline

See `research/chat_045/NEXT.md` and `STATUS.json`. A thread heartbeat continues
bounded work at aligned 20-minute intervals, with an explicit 06:00 deadline
check. Fewer than ten minutes before the deadline, only verification/reporting
should proceed. At the deadline, report verified results and pause the heartbeat.

Public site: <https://zen-changing-stock-jason.trycloudflare.com>
