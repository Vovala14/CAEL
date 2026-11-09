"""Optional framework schemas; the core itself has no third-party dependency."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=4000)
    origin: str | None = Field(default=None, max_length=1000)


class ProofRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    episode_id: str = Field(min_length=1, max_length=100)
    sources: list[Source] = Field(min_length=1, max_length=64)
    entity: str = Field(min_length=1, max_length=80)
    predicate: str = Field(min_length=1, max_length=80)
    negated: bool = False


class ProofEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    format: Literal["cael-provenance-v1"]
    inputs: ProofRequest
    input_sha256: str
    engine: dict[str, Any]
    reported: dict[str, Any]
    evidence: list[dict[str, Any]]
    parsed: dict[str, Any] | None
    proof: dict[str, Any] | None
    verification: dict[str, Any]
    certificate_sha256: str
