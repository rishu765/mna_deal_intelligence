"""Provider-neutral answer models for grounded document research."""

from __future__ import annotations

from dataclasses import dataclass

from ma_company_intelligence.domain.citations import Citation
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
    citations: tuple[Citation, ...] = ()
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
        expected_numbers = tuple(range(1, len(self.citations) + 1))
        if tuple(citation.reference_number for citation in self.citations) != expected_numbers:
            raise ValueError("answer citations must have contiguous one-based numbering")
        if self.insufficient_evidence and self.citations:
            raise ValueError("an insufficient answer cannot contain citations")
        supporting_chunks = {result.chunk_id: result for result in self.supporting_results}
        for citation in self.citations:
            result = supporting_chunks.get(citation.chunk_id)
            if result is None or result.document_id != citation.document_id:
                raise ValueError("every answer citation must map to a supporting result")

    @property
    def supporting_chunk_ids(self) -> tuple[str, ...]:
        """Return stable chunk IDs in the order used for generation."""

        return tuple(result.chunk_id for result in self.supporting_results)
