# CAEL provenance bridges

This optional MIT-licensed glue runs the exact CAEL 0.4 logical engine from a
trusted local checkout. It provides LangGraph nodes and a tool artifact, plus
a CrewAI typed tool and deterministic Flow. No model/provider, embedding
service, API key, or network fetch is needed to compute an answer.

The external CAEL engine and model retain their separate **non-commercial
personal/research licence**. They are not bundled into this adapter's wheel,
and the MIT glue licence does not change their terms.

## What the certificate establishes

Each request supplies source IDs, exact single-statement text, optional
caller-declared origins, and a structured entity/property/polarity query. The
result contains:

- The actual CAEL answer and flags, without repairing them.
- Exact cited text, source IDs, original statement indices, and SHA256 hashes.
- The full input hash and pinned engine/model identity.
- CAEL's parsed facts/rules and a finite proof DAG.
- An independent Horn-rule check of each fact/rule application, including
  both sides of a conflict and absence of a derivation for unknown results.

`verify(certificate, original_request, runtime)` requires the trusted original
request, checks the binding, and reconstructs the pinned result and proof.
Editing an answer, quote, citation, rule, or engine identity fails, including
when an attacker recomputes the public checksum.

The certificate is **relative to CAEL's parsed premises**. It does not verify
external truth, authenticate source authorship, sign a document, or prove that
CAEL interpreted arbitrary English correctly. An origin URI is caller-declared;
the bridge does not retrieve or authenticate it. Keep the original sources
outside the certificate as the trust anchor. Downstream prose rewritten by
another model is not automatically covered by the certificate.

Unknown, false, conflicting, unsupported, and unverified results are distinct.
A verified `unknown` means no derivation in the checked finite theory. It is
not a negative fact. Unsupported inputs return no verified answer or citations.

## Install and configure

Use Python 3.10–3.13 for both frameworks. From this bridge's source checkout:

```sh
uv pip install './examples/agent_provenance[langgraph,crewai,test]'
export CAEL040_ROOT=/path/to/trusted/CAEL-checkout
export OTEL_SDK_DISABLED=true
export CREWAI_TELEMETRY_ENABLED=false
export CREWAI_DISABLE_VERSION_CHECK=true
export LANGSMITH_TRACING=false
```

`CAEL040_ROOT` must contain the exact files listed in `core.PINS`. The loader
hash-checks them before importing only the logical engine in a private module
namespace. It does not load an Assistant, reuse learned conversation stores,
or import an unrelated global CAEL installation.

The qualification used LangGraph 1.2.20, langchain-core 1.7.6, CrewAI 1.15.39,
Pydantic 2.12.5, and Python 3.12.9. Wider version ranges are not a claim that
every future release has been tested. The framework packages have their own
dependencies; installing them is separate from calling a neural model.

## Run a source-linked claim

```python
import os

from cael_provenance import CAELRuntime, verify

runtime = CAELRuntime(os.environ["CAEL040_ROOT"])
request = {
    "episode_id": "bird-claim",
    "sources": [
        {"id": "s1", "text": "Aria is a wren", "origin": "authored:test"},
        {"id": "s2", "text": "Every wren is a bird", "origin": "authored:test"},
        {"id": "s3", "text": "Every bird is visible", "origin": "authored:test"},
    ],
    "entity": "Aria",
    "predicate": "visible",
    "negated": False,
}
certificate = runtime.answer(request)
assert certificate["reported"]["answer"] == "true"
assert [item["source_id"] for item in certificate["evidence"]] == ["s1", "s2", "s3"]
assert verify(certificate, request, runtime)
```

The complete tested certificate is in `validation/chain.json`, not a made-up
output fragment. One source must contain exactly one premise; 64 sources and
32,000 total text characters are the bridge bounds. The query is one property,
with negation expressed by the Boolean field. Unsupported grammar is explicit.

## Use LangGraph

```python
from langgraph.checkpoint.memory import InMemorySaver

from cael_provenance.langgraph import graph_builder

graph = graph_builder(runtime).compile(checkpointer=InMemorySaver())
config = {"configurable": {"thread_id": "source-linked-example"}}
result = graph.invoke({"request": request}, config)
assert result["verified"]
assert verify(result["certificate"], request, runtime)
```

The builder uses ordinary `StateGraph` nodes. Evaluation and verification are
separate nodes; checkpoints preserve the full JSON certificate. Tests also
pause after evaluation, resume into verification, and reject a modified
checkpoint. Use distinct thread IDs for independent workflow histories.

`cael_provenance.langgraph.proof_tool(runtime)` provides a standard LangChain
tool with `response_format="content_and_artifact"`. A `ToolMessage` carries a
short JSON summary as content and the full certificate in `artifact`. Preserve
that artifact when checking provenance; the summary alone is not the proof.
The ToolNode integration test uses an explicitly authored tool call, not a
claim of autonomous model tool selection.

## Use CrewAI

```python
from cael_provenance.crewai import CAELProofTool, provenance_flow

tool = CAELProofTool(runtime)
envelope = tool.run(**request)
assert verify(envelope.model_dump(mode="json"), request, runtime)

result = provenance_flow(runtime).kickoff(inputs={"request": request})
assert result["verified"]
```

The tool returns a typed Pydantic envelope and sets `result_as_answer=True`.
The Flow evaluates and verifies deterministically without an Agent or an LLM.
This qualifies actual tool/Flow execution, not autonomous Crew planning or
downstream agents' compliance with an arbitrary task.

## Reproduce the validation

```sh
export CAEL_PROVENANCE_ARTIFACT_DIR=/new/output/directory
python -m pytest examples/agent_provenance/tests -q
```

The Python socket guard blocks external and arbitrary loopback clients during
tests. Only the standard library's synchronous local socket-pair construction
is permitted for Windows asyncio IPC. Framework telemetry/version checks are
disabled through their normal settings; neither framework is mocked.

There are 17 distinct episode requests: 12 newly authored ordinary cases,
three unsupported-boundary cases, and two retained historical parser misses.
The same requests are repeated through both frameworks and do not become new
capability cases. Intended answers match in 12/14 non-boundary cases; the
two historical `glimmering thing` chain questions still return `unknown`.
The 79 test checks mainly cover exchange, integrity, proof rules, isolation,
and tampering. They are not benchmark accuracy or a general chatbot score.

The validation report and source-bound receipt retain the failed initial
framework-test attempts, the Windows socket-pair fixture correction, and the
CrewAI version-check opt-out. No CAEL engine, weights, protected solvers, or
live worker changed to obtain the result.
