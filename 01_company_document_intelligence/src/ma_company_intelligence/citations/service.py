"""Deterministic mapping from generated evidence IDs to source citations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from ma_company_intelligence.citations.errors import CitationReferenceError
from ma_company_intelligence.domain import Citation, RetrievalResult


@dataclass(frozen=True, slots=True)
class CitationMapping:
    """A global citation list and lookup by model-visible evidence ID."""

    citations: tuple[Citation, ...]
    by_evidence_id: Mapping[str, Citation]

    def __post_init__(self) -> None:
        object.__setattr__(self, "by_evidence_id", MappingProxyType(dict(self.by_evidence_id)))

    def citations_for(self, evidence_ids: tuple[str, ...]) -> tuple[Citation, ...]:
        """Return unique citations in first-reference order."""

        selected: list[Citation] = []
        seen_numbers: set[int] = set()
        for evidence_id in evidence_ids:
            try:
                citation = self.by_evidence_id[evidence_id]
            except KeyError as error:
                raise CitationReferenceError(
                    f"unknown evidence reference {evidence_id!r}"
                ) from error
            if citation.reference_number not in seen_numbers:
                selected.append(citation)
                seen_numbers.add(citation.reference_number)
        return tuple(selected)


class CitationBuilder:
    """Validate selected evidence IDs and create stable, deduplicated citations."""

    def __init__(self, *, max_excerpt_characters: int = 500) -> None:
        if max_excerpt_characters <= 0:
            raise ValueError("max_excerpt_characters must be positive")
        self._max_excerpt_characters = max_excerpt_characters

    def build(
        self,
        referenced_evidence_ids: tuple[str, ...],
        evidence_by_id: Mapping[str, RetrievalResult],
    ) -> CitationMapping:
        """Number only referenced chunks and reject IDs absent from supplied context."""

        citations: list[Citation] = []
        by_evidence_id: dict[str, Citation] = {}
        by_chunk_id: dict[str, Citation] = {}

        for evidence_id in referenced_evidence_ids:
            if evidence_id in by_evidence_id:
                continue
            try:
                result = evidence_by_id[evidence_id]
            except KeyError as error:
                raise CitationReferenceError(
                    f"generated output referenced unknown evidence ID {evidence_id!r}"
                ) from error

            existing = by_chunk_id.get(result.chunk_id)
            if existing is not None:
                by_evidence_id[evidence_id] = existing
                continue

            citation = self._from_result(result, reference_number=len(citations) + 1)
            citations.append(citation)
            by_chunk_id[result.chunk_id] = citation
            by_evidence_id[evidence_id] = citation

        return CitationMapping(tuple(citations), by_evidence_id)

    def _from_result(self, result: RetrievalResult, *, reference_number: int) -> Citation:
        chunk = result.chunk
        text = chunk.text
        if len(text) > self._max_excerpt_characters:
            text = text[: self._max_excerpt_characters].rstrip() + "…"
        return Citation(
            reference_number=reference_number,
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            source_filename=chunk.source.filename,
            source_title=chunk.metadata.document_title,
            canonical_page_numbers=tuple(ref.page_number for ref in chunk.page_references),
            physical_pdf_page_indexes=tuple(ref.pdf_page_index for ref in chunk.page_references),
            printed_page_labels=tuple(ref.printed_page_label for ref in chunk.page_references),
            excerpt=text,
            metadata=chunk.metadata,
        )
