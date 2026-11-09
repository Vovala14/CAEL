# Actual framework/provenance results

The **installed adapter wheel**, not an editable checkout or framework mock,
passes **79/79 tests with zero skips** on Python 3.12.9. LangGraph 1.2.20,
langchain-core 1.7.6, CrewAI 1.15.39 and Pydantic 2.12.5 are the actual installed
frameworks. Each of the 17 requests produces the same complete certificate
through direct CAEL evaluation, LangGraph and CrewAI.

These are 12 new ordinary requests, three new unsupported-boundary requests and
two historical regression requests. Intended answer agreement is **12/14**
outside the three boundaries. Some intended answers are unknown/conflicting,
so this is not 12 positive problem solutions. Repeating the same cases across
frameworks does not create more capability cases. The 79 checks primarily test
the contract, exchange, isolation, proof steps and tampering; no benchmark or
general chatbot ranking is established.

| Case | Actual CAEL status | Intended answer / boundary |
| --- | --- | --- |
| chain | true | true |
| conflict | conflicting | conflicting |
| conjunction | true | true |
| derived-conflict | conflicting | conflicting |
| direct | true | true |
| distractor | true | true |
| historical-thing-chain-negative | unknown | false |
| historical-thing-chain-positive | unknown | true |
| missing-conjunct | unknown | unknown |
| multiple-statements-in-source | unsupported | boundary |
| negative-query | true | true |
| negative | false | false |
| shorter-proof | true | true |
| unconnected-cycle | unknown | unknown |
| unknown | unknown | unknown |
| unsupported-condition | unsupported | boundary |
| unsupported-disjunction | unsupported | boundary |

All source records, parsed interpretations, evidence quotes and proof DAGs are
retained in [all_episodes.json](all_episodes.json). The
[source-bound receipt](receipt.json) binds the tested source, wheel and all 51
complete case outputs. The [full test log](pytest.log) is retained. Individual
examples include [chain](chain.json), [unknown](unknown.json),
[conflict](conflict.json) and [unsupported](unsupported-condition.json).

## What was exercised

- Real pinned CAEL 0.4.0 logical-engine/model files, unmodified.
- Independent rule-application checking against CAEL's explicit parse.
- Exact quote/ID/hash checks and replay against trusted original input.
- Seven kinds of certificate alteration, each with and without recomputed hashes.
- Changed original input under the same human episode label.
- Conflict proofs on both polarities, missing derivations, irrelevant source
  exclusion, request isolation and concurrent calls.
- Actual LangGraph workflow, ToolNode artifact, checkpoint pause/resume and
  rejection of modified checkpoint evidence.
- Actual CrewAI typed BaseTool and deterministic Flow, without Agent/LLM planning.
- External/arbitrary-loopback Python clients blocked during tests. Only the
  standard-library Windows asyncio socket-pair IPC construction is allowed.
  Telemetry/version checks are disabled through ordinary framework settings.

## Failures and limits retained

The first attempt had 61 passes, 18 failures and 17 fixture errors: direct
ToolNode invocation lacked graph runtime context, and the initial socket guard
also blocked Windows asyncio's internal loopback pair. The second diagnostic
attempt recorded that exact stdlib IPC stack. The third had 79 assertion passes
but 17 guard errors from CrewAI's automatic PyPI version check. The fixture was
corrected for stdlib IPC only, and `CREWAI_DISABLE_VERSION_CHECK=true` disables
that check without allowing arbitrary network calls. Attempts 4 through 7 pass;
repetitions do not inflate the 17 distinct requests. All prior full logs and
exact draft source snapshots remain in the local research evidence.

The two historical `glimmering thing` chain queries remain wrong on their
intended reading: the released parser produces an unmatched property, and
CAEL returns unknown. The proof correctly describes that parsed theory, which
does not establish a correct natural-language interpretation. No failure is
replaced by the independent checker or an external model.

Origins are caller-declared. Hashes are not signatures, author authentication,
or verification of external truth. Preserve trusted original input separately.
The MIT adapter wheel contains no CAEL engine/model files; those remain an
external, separately licensed non-commercial personal/research dependency.
No live worker, CAEL release, protected solver, weight or CA kernel changed.

Tested wheel: `cael_provenance_bridge-0.1.0-py3-none-any.whl`

SHA256: `ce93d97464f164b88f17dde9f05335a43e14e28e167fdf2b1b631cb85dfb3c55`
