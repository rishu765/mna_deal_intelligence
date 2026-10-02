"""Tests for metadata propagation and provenance-aware chunking."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ma_company_intelligence.chunk_cli import main as chunk_cli_main
from ma_company_intelligence.chunking import ChunkingConfig, chunk_document
from ma_company_intelligence.domain import (
    DocumentMetadata,
    DocumentSource,
    ParsedDocument,
    ParsedPage,
    ParsingWarning,
    ParsingWarningCode,
    SourceProvenance,
)


def _parsed_document(
    tmp_path: Path,
    page_texts: list[str],
    *,
    warnings: tuple[ParsingWarning, ...] = (),
) -> ParsedDocument:
    source_path = tmp_path / "Annual Report.pdf"
    source_path.write_bytes(b"synthetic-test-source")
    document_id = "sha256:" + "a" * 64
    source = DocumentSource(
        filename=source_path.name,
        path=source_path,
        media_type="application/pdf",
        size_bytes=source_path.stat().st_size,
        sha256="a" * 64,
    )
    pages = tuple(
        ParsedPage(
            text=text,
            provenance=SourceProvenance(
                document_id=document_id,
                source_filename=source.filename,
                source_path=source.path,
                pdf_page_index=index,
                page_number=index + 1,
                printed_page_label=None,
            ),
        )
        for index, text in enumerate(page_texts)
    )
    return ParsedDocument(
        document_id=document_id,
        source=source,
        pages=pages,
        warnings=warnings,
    )


def test_short_document_becomes_one_provenance_aware_chunk(tmp_path: Path) -> None:
    document = _parsed_document(tmp_path, ["Revenue was $125 million."])

    result = chunk_document(document)

    assert len(result.chunks) == 1
    chunk = result.chunks[0]
    assert chunk.text == "Revenue was $125 million."
    assert chunk.document_id == document.document_id
    assert chunk.source == document.source
    assert chunk.chunk_index == 0
    assert chunk.chunk_number == 1
    assert chunk.page_numbers == (1,)
    assert chunk.page_references[0].pdf_page_index == 0


def test_chunk_order_content_and_ids_are_deterministic(tmp_path: Path) -> None:
    document = _parsed_document(tmp_path, ["A" * 260])
    config = ChunkingConfig(max_characters=100, overlap_characters=20, min_chunk_characters=40)

    first = chunk_document(document, config=config)
    second = chunk_document(document, config=config)

    assert [chunk.chunk_index for chunk in first.chunks] == list(range(len(first.chunks)))
    assert [(chunk.chunk_id, chunk.text) for chunk in first.chunks] == [
        (chunk.chunk_id, chunk.text) for chunk in second.chunks
    ]


def test_character_overlap_and_maximum_size_are_enforced(tmp_path: Path) -> None:
    document = _parsed_document(tmp_path, ["0123456789" * 30])
    config = ChunkingConfig(max_characters=100, overlap_characters=20, min_chunk_characters=40)

    chunks = chunk_document(document, config=config).chunks

    assert len(chunks) > 1
    assert all(chunk.character_count <= 100 for chunk in chunks)
    for previous, current in zip(chunks, chunks[1:], strict=False):
        assert previous.text[-20:] == current.text[:20]


def test_chunk_can_span_pages_and_records_every_contributing_page(tmp_path: Path) -> None:
    document = _parsed_document(tmp_path, ["A" * 30, "B" * 30])
    config = ChunkingConfig(max_characters=50, overlap_characters=10, min_chunk_characters=15)

    chunks = chunk_document(document, config=config).chunks

    spanning_chunks = [chunk for chunk in chunks if chunk.page_numbers == (1, 2)]
    assert spanning_chunks
    assert spanning_chunks[0].page_references[0].pdf_page_index == 0
    assert spanning_chunks[0].page_references[1].pdf_page_index == 1


def test_empty_pages_do_not_create_chunks_and_warnings_survive(tmp_path: Path) -> None:
    warning = ParsingWarning(
        code=ParsingWarningCode.EMPTY_PAGE_TEXT,
        message="No extractable text found on physical PDF page 2.",
        page_number=2,
    )
    document = _parsed_document(tmp_path, ["Useful text", "   "], warnings=(warning,))

    result = chunk_document(document)

    assert len(result.chunks) == 1
    assert result.chunks[0].page_numbers == (1,)
    assert result.parser_warnings == (warning,)


def test_all_empty_pages_produce_no_useless_chunks(tmp_path: Path) -> None:
    document = _parsed_document(tmp_path, ["", " \n "])

    result = chunk_document(document)

    assert result.chunks == ()


def test_supplied_metadata_propagates_without_inference(tmp_path: Path) -> None:
    document = _parsed_document(tmp_path, ["Business overview"])
    metadata = DocumentMetadata(
        company="Example plc",
        document_title="Annual Report 2025",
        document_type="annual_report",
        fiscal_year=2025,
        reporting_period="Year ended 31 December 2025",
        source_url="https://example.com/report.pdf",
        filing_type="20-F",
    )

    supplied = chunk_document(document, metadata)
    unknown = chunk_document(document)

    assert supplied.metadata == metadata
    assert supplied.chunks[0].metadata == metadata
    assert unknown.metadata == DocumentMetadata()
    assert unknown.chunks[0].metadata.company is None


@pytest.mark.parametrize(
    "values",
    [
        (0, 0, 1),
        (100, -1, 20),
        (100, 20, 0),
        (100, 20, 101),
        (100, 20, 20),
    ],
)
def test_invalid_chunking_configuration_is_rejected(values: tuple[int, int, int]) -> None:
    with pytest.raises(ValueError):
        ChunkingConfig(
            max_characters=values[0],
            overlap_characters=values[1],
            min_chunk_characters=values[2],
        )


def test_chunk_ids_change_when_configuration_changes(tmp_path: Path) -> None:
    document = _parsed_document(tmp_path, ["A" * 240])
    first = chunk_document(
        document,
        config=ChunkingConfig(100, 20, 40),
    )
    second = chunk_document(
        document,
        config=ChunkingConfig(100, 10, 40),
    )

    assert first.chunks[0].chunk_id != second.chunks[0].chunk_id


def test_chunk_cli_output_is_bounded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    document = _parsed_document(tmp_path, ["A" * 260])
    monkeypatch.setattr(
        "ma_company_intelligence.chunk_cli.parse_pdf",
        lambda _path: document,
    )

    exit_code = chunk_cli_main(
        [
            str(tmp_path / "Annual Report.pdf"),
            "--chunk-size",
            "100",
            "--overlap",
            "20",
            "--min-chunk-size",
            "40",
            "--max-chunks",
            "1",
            "--preview-chars",
            "12",
            "--company",
            "Example plc",
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["chunk_count"] > 1
    assert output["chunks_displayed"] == 1
    assert output["chunks_truncated"] is True
    assert output["metadata"]["company"] == "Example plc"
    assert len(output["chunks"][0]["text_preview"]) == 12
