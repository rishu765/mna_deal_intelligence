"""Tests for deterministic citation construction and provenance safety."""

from __future__ import annotations

from pathlib import Path

import pytest

from ma_company_intelligence.citations import CitationBuilder, CitationReferenceError
from ma_company_intelligence.domain import (
    ChunkPageReference,
    Citation,
    DocumentChunk,
    DocumentMetadata,
    DocumentSource,
    RetrievalResult,
)


def _result(tmp_path: Path, *, number: int, pages: tuple[int, ...]) -> RetrievalResult:
    source_path = (tmp_path / f"report-{number}.pdf").resolve()
    source_path.write_bytes(b"synthetic")
    digest = f"{number:x}".zfill(64)
    return RetrievalResult(
        rank=number,
        score=0.9,
        chunk=DocumentChunk(
            chunk_id=f"sha256:{number:064x}",
            document_id=f"sha256:{digest}",
            chunk_index=number - 1,
            text=f"Evidence text {number} with a disclosed metric.",
            source=DocumentSource(
                filename=f"report-{number}.pdf",
                path=source_path,
                media_type="application/pdf",
                size_bytes=source_path.stat().st_size,
                sha256=digest,
            ),
            page_references=tuple(
                ChunkPageReference(pdf_page_index=page - 1, page_number=page) for page in pages
            ),
            metadata=DocumentMetadata(document_title="Annual Report FY2025"),
        ),
    )


def test_selected_evidence_is_numbered_stably_and_duplicate_chunks_are_deduplicated(
    tmp_path: Path,
) -> None:
    first = _result(tmp_path, number=1, pages=(84, 85))
    second = _result(tmp_path, number=2, pages=(17, 19))
    mapping = CitationBuilder().build(
        ("E2", "E1", "E2", "E3"),
        {"E1": first, "E2": second, "E3": second},
    )

    assert tuple(citation.chunk_id for citation in mapping.citations) == (
        second.chunk_id,
        first.chunk_id,
    )
    assert mapping.citations[0].format_reference() == ("[1] Annual Report FY2025 — pp. 17, 19")
    assert mapping.citations[1].format_reference() == ("[2] Annual Report FY2025 — pp. 84–85")
    assert mapping.citations_for(("E3", "E2")) == (mapping.citations[0],)


def test_unknown_generated_evidence_reference_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(CitationReferenceError, match="unknown evidence ID"):
        CitationBuilder().build(("E99",), {"E1": _result(tmp_path, number=1, pages=(1,))})


def test_missing_page_metadata_is_exposed_without_fabrication() -> None:
    citation = Citation(
        reference_number=1,
        chunk_id="chunk-1",
        document_id="document-1",
        source_filename="filing.pdf",
        source_title=None,
        canonical_page_numbers=(),
        physical_pdf_page_indexes=(),
        printed_page_labels=(),
        excerpt="A source excerpt.",
    )

    assert citation.format_reference() == "[1] filing.pdf — page unavailable"


def test_excerpt_is_bounded_without_changing_source_provenance(tmp_path: Path) -> None:
    result = _result(tmp_path, number=1, pages=(3,))
    mapping = CitationBuilder(max_excerpt_characters=10).build(("E1",), {"E1": result})

    assert mapping.citations[0].excerpt.endswith("…")
    assert mapping.citations[0].canonical_page_numbers == (3,)
    assert mapping.citations[0].physical_pdf_page_indexes == (2,)
