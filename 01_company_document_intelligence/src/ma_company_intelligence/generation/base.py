"""Provider-neutral text-generation contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """A bounded model request assembled by application code."""

    instructions: str
    input_text: str
    max_output_tokens: int

    def __post_init__(self) -> None:
        if not self.instructions.strip():
            raise ValueError("generation instructions must not be blank")
        if not self.input_text.strip():
            raise ValueError("generation input must not be blank")
        if self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")


@dataclass(frozen=True, slots=True)
class GenerationOutput:
    """Validated semantic output returned by a generator adapter."""

    answer: str
    insufficient_evidence: bool
    cited_evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.answer.strip():
            raise ValueError("generated answer must not be blank")
        if any(not evidence_id.strip() for evidence_id in self.cited_evidence_ids):
            raise ValueError("cited evidence IDs must not be blank")
        if self.insufficient_evidence and self.cited_evidence_ids:
            raise ValueError("an insufficient answer cannot cite evidence")


class Generator(Protocol):
    """Generate one structured answer without exposing provider response types."""

    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    def generate(self, request: GenerationRequest) -> GenerationOutput: ...
