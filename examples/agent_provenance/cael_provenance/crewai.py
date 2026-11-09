"""CrewAI BaseTool and deterministic Flow; no model/provider is called."""

from typing import Any

from crewai.flow.flow import Flow, listen, start
from crewai.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr

from .core import CAELRuntime, verify
from .schema import ProofEnvelope, ProofRequest


class CAELProofTool(BaseTool):
    name: str = "cael_provenance"
    description: str = (
        "Check a logical claim against supplied source-identified premises. "
        "Returns the actual CAEL answer, exact citations and a checked proof "
        "relative to its parse. Does not establish external truth."
    )
    args_schema: type[BaseModel] = ProofRequest
    result_as_answer: bool = True
    _runtime: CAELRuntime = PrivateAttr()

    def __init__(self, runtime: CAELRuntime, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._runtime = runtime

    def _run(
        self,
        episode_id: str,
        sources: list[dict[str, Any]],
        entity: str,
        predicate: str,
        negated: bool = False,
    ) -> ProofEnvelope:
        request = ProofRequest(
            episode_id=episode_id,
            sources=sources,
            entity=entity,
            predicate=predicate,
            negated=negated,
        )
        certificate = self._runtime.answer(request.model_dump())
        verify(certificate, request.model_dump(), self._runtime)
        return ProofEnvelope.model_validate(certificate)


class ProofFlowState(BaseModel):
    request: dict[str, Any] = Field(default_factory=dict)
    certificate: dict[str, Any] | None = None
    verified: bool = False


def provenance_flow(runtime: CAELRuntime) -> Flow[ProofFlowState]:
    """Construct a fresh Flow instance; no Agent/LLM planning is simulated."""
    tool = CAELProofTool(runtime)

    class ProvenanceFlow(Flow[ProofFlowState]):
        @start()
        def evaluate(self) -> dict[str, Any]:
            self.state.verified = False
            envelope = tool.run(**self.state.request)
            self.state.certificate = envelope.model_dump(mode="json")
            return self.state.certificate

        @listen(evaluate)
        def validate(self, certificate: dict[str, Any]) -> dict[str, Any]:
            self.state.verified = verify(certificate, self.state.request, runtime)
            return {"certificate": certificate, "verified": self.state.verified}

    return ProvenanceFlow()
