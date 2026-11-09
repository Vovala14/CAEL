"""LangGraph nodes and a LangChain tool preserving the full proof artifact."""

import json
from typing import Any, TypedDict

from .core import CAELRuntime, verify
from .schema import ProofRequest, Source


class ProvenanceState(TypedDict):
    request: dict[str, Any]
    certificate: dict[str, Any]
    verified: bool


def graph_builder(runtime: CAELRuntime) -> Any:
    """Build a fixed workflow; callers choose checkpoint/interrupt settings."""
    from langgraph.graph import END, START, StateGraph

    def evaluate(state: ProvenanceState) -> dict[str, Any]:
        return {"certificate": runtime.answer(state["request"]), "verified": False}

    def validate(state: ProvenanceState) -> dict[str, bool]:
        return {"verified": verify(state["certificate"], state["request"], runtime)}

    builder = StateGraph(ProvenanceState)
    builder.add_node("evaluate", evaluate)
    builder.add_node("validate", validate)
    builder.add_edge(START, "evaluate")
    builder.add_edge("evaluate", "validate")
    builder.add_edge("validate", END)
    return builder


def proof_tool(runtime: CAELRuntime) -> Any:
    """Return a tool whose ToolMessage.artifact retains the complete certificate."""
    from langchain_core.tools import tool

    @tool(
        "cael_provenance",
        args_schema=ProofRequest,
        response_format="content_and_artifact",
    )
    def check_claim(
        episode_id: str,
        sources: list[Source],
        entity: str,
        predicate: str,
        negated: bool = False,
    ) -> tuple[str, dict[str, Any]]:
        """Check one logical claim against explicit, source-identified premises.

        Returns a bounded CAEL answer and proof relative to its parse, not
        external truth. Unknown/conflict/unsupported results remain explicit.
        """
        request = ProofRequest(
            episode_id=episode_id,
            sources=sources,
            entity=entity,
            predicate=predicate,
            negated=negated,
        )
        certificate = runtime.answer(request.model_dump())
        reply = certificate["reported"]
        summary = {
            "answer": reply["answer"],
            "status": reply["status"],
            "verified": verify(certificate, request.model_dump(), runtime),
            "source_ids": [item["source_id"] for item in certificate["evidence"]],
            "certificate_sha256": certificate["certificate_sha256"],
            "scope": "derivation relative to supplied, CAEL-parsed premises",
        }
        return json.dumps(summary, sort_keys=True), certificate

    return check_claim
