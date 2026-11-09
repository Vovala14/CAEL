# CAEL provenance bridge

Optional source-linked reasoning tools for **LangGraph and CrewAI**. This
adapter returns the actual local CAEL response, exact source quotes and IDs,
input and engine hashes, CAEL's parsed interpretation, and a finite Horn-rule
proof. A separate checker validates the derivation and replay against trusted
original input.

The adapter glue is **MIT-licensed**. The external **CAEL 0.4.0 engine and model
retain their separate non-commercial personal/research licence**. They are
not included in this package, and its MIT licence does not change their terms.

## Installation

```sh
python -m pip install 'cael-provenance-bridge[langgraph,crewai]==0.1.0'
```

Use Python 3.10–3.13 when installing both frameworks. Provide a trusted CAEL
checkout containing the exact engine/model files pinned by the adapter:

```sh
git clone https://github.com/Vovala14/CAEL.git cael-runtime
git -C cael-runtime checkout 49359eae9aa197d5b92631c16efb74085180a27c
export CAEL040_ROOT="$PWD/cael-runtime"
export OTEL_SDK_DISABLED=true
export CREWAI_TELEMETRY_ENABLED=false
export CREWAI_DISABLE_VERSION_CHECK=true
export LANGSMITH_TRACING=false
```

No external model/provider, API key, embedding service or network fetch is
needed to compute an answer. Installing the optional frameworks installs
their own dependencies; this is separate from invoking a neural model.

## Framework entry points

```python
import os
from cael_provenance import CAELRuntime, verify
from cael_provenance.crewai import CAELProofTool, provenance_flow
from cael_provenance.langgraph import graph_builder, proof_tool

runtime = CAELRuntime(os.environ["CAEL040_ROOT"])
```

- LangGraph: a `StateGraph` builder, checkpoint/resume support and a standard
  tool retaining the complete certificate in `ToolMessage.artifact`.
- CrewAI: a typed `BaseTool` returning the complete Pydantic envelope and a
  deterministic `Flow`, without Agent/LLM planning.
- `verify(certificate, original_request, runtime)` binds the certificate to
  the original trusted source text and independently checks the finite proof.

See the [complete usage examples and API limits](https://github.com/Vovala14/CAEL/tree/codex/agent-provenance/examples/agent_provenance).

## Scope and measured results

The installed wheel passes **79 checks with zero skips** on Windows; the
same bridge source also passes all 79 on Linux with the real frameworks.
The 17 distinct requests include 12 new ordinary cases, three unsupported
boundaries and two retained historical parser misses. Intended answer
agreement is **12/14** outside the boundaries, including unknown/conflicting
answers. These are integration and integrity checks, not a benchmark or a
claim of general reasoning ability. Full outputs and failures are retained in
the [validation report](https://github.com/Vovala14/CAEL/blob/codex/agent-provenance/examples/agent_provenance/validation/REPORT.md).

Verification is **relative to CAEL's parsed premises**. It does not establish
external truth, authenticate source authorship, sign documents or prove
correct interpretation of arbitrary English. Origins are caller-declared;
hashes are not signatures. Keep the original request separately as the trust
anchor. Unknown, false, conflicting, unsupported and unverified results are
distinct. Downstream prose rewritten by another model is not automatically
covered by the certificate. The two known parser misses remain unfixed.
