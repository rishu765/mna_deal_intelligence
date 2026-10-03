"""Deterministic construction of bounded evidence context."""

from __future__ import annotations

from dataclasses import dataclass

from ma_company_intelligence.domain import RetrievalResult


@dataclass(frozen=True, slots=True)
class EvidenceContext:
    """Formatted evidence plus the exact results that fit the context budget."""

    text: str
    included_results: tuple[RetrievalResult, ...]
    omitted_result_count: int

    @property
    def character_count(self) -> int:
        return len(self.text)


class ContextBuilder:
    """Format whole ranked chunks into a deterministic character budget."""

    def __init__(self, *, max_characters: int = 12_000, max_chunks: int = 5) -> None:
        if max_characters <= 0:
            raise ValueError("max_characters must be positive")
        if max_chunks <= 0:
            raise ValueError("max_chunks must be positive")
        self._max_characters = max_characters
        self._max_chunks = max_chunks

    @property
    def max_characters(self) -> int:
        return self._max_characters

    @property
    def max_chunks(self) -> int:
        return self._max_chunks

    def build(self, results: tuple[RetrievalResult, ...]) -> EvidenceContext:
        """Include the longest ranked prefix that fits without truncating a chunk."""

        blocks: list[str] = []
        included: list[RetrievalResult] = []
        for result in results[: self._max_chunks]:
            block = _format_result(result, evidence_number=len(included) + 1)
            candidate = "\n\n".join((*blocks, block))
            if len(candidate) > self._max_characters:
                break
            blocks.append(block)
            included.append(result)

        return EvidenceContext(
            text="\n\n".join(blocks),
            included_results=tuple(included),
            omitted_result_count=len(results) - len(included),
        )


def _format_result(result: RetrievalResult, *, evidence_number: int) -> str:
    chunk = result.chunk
    canonical_pages = ", ".join(str(reference.page_number) for reference in chunk.page_references)
    physical_indexes = ", ".join(
        str(reference.pdf_page_index) for reference in chunk.page_references
    )
    printed_labels = ", ".join(
        reference.printed_page_label or "unknown" for reference in chunk.page_references
    )
    lines = [
        f"[EVIDENCE {evidence_number}]",
        f"retrieval_rank: {result.rank}",
        f"similarity_score: {result.score:.6f}",
        f"chunk_id: {chunk.chunk_id}",
        f"document_id: {chunk.document_id}",
        f"source_filename: {chunk.source.filename}",
        f"canonical_page_numbers: {canonical_pages}",
        f"physical_pdf_page_indexes: {physical_indexes}",
        f"printed_page_labels: {printed_labels}",
    ]
    optional_metadata = (
        ("company", chunk.metadata.company),
        ("document_title", chunk.metadata.document_title),
        ("document_type", chunk.metadata.document_type),
        ("fiscal_year", chunk.metadata.fiscal_year),
        ("reporting_period", chunk.metadata.reporting_period),
        ("source_url", chunk.metadata.source_url),
        ("filing_type", chunk.metadata.filing_type),
        ("section", chunk.section),
    )
    lines.extend(f"{name}: {value}" for name, value in optional_metadata if value is not None)
    lines.extend(("text:", chunk.text, f"[/EVIDENCE {evidence_number}]"))
    return "\n".join(lines)
