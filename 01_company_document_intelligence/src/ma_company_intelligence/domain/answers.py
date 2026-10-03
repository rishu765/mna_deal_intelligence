"""Provider-neutral answer models for grounded document research."""

from __future__ import annotations

from dataclasses import dataclass

from ma_company_intelligence.domain.retrieval import RetrievalResult


@dataclass(frozen=True, slots=True)
class RAGAnswer:
    """A generated answer and the exact retrieved evidence supplied to it."""

    question: str
    answer: str
    supporting_results: tuple[RetrievalResult, ...]
    insufficient_evidence: bool
    generator_provider: str
    generator_model: str
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.question.strip():
            raise ValueError("answer question must contain non-whitespace text")
        if not self.answer.strip():
            raise ValueError("answer text must contain non-whitespace text")
        if not self.generator_provider.strip():
            raise ValueError("generator_provider must not be blank")
        if not self.generator_model.strip():
            raise ValueError("generator_model must not be blank")

    @property
    def supporting_chunk_ids(self) -> tuple[str, ...]:
        """Return stable chunk IDs in the order used for generation."""

        return tuple(result.chunk_id for result in self.supporting_results)
