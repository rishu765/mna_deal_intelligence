"""Tests for PDF ingestion, provenance, and failure behavior."""

from __future__ import annotations

import json
from pathlib import Path

import pymupdf
import pytest

from ma_company_intelligence.cli import main
from ma_company_intelligence.domain import ParsingWarningCode
from ma_company_intelligence.ingestion import (
    EmptyPdfError,
    EncryptedPdfError,
    InvalidDocumentSourceError,
    InvalidPdfError,
    PdfParsingError,
    SourceNotFoundError,
    UnsupportedDocumentTypeError,
    parse_pdf,
)


def _write_pdf(path: Path, page_texts: list[str]) -> None:
    """Create a tiny deterministic PDF without committing a binary fixture."""

    document = pymupdf.open()  # type: ignore[no-untyped-call]
    for text in page_texts:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
    document.save(path)  # type: ignore[no-untyped-call]
    document.close()  # type: ignore[no-untyped-call]


def _write_encrypted_pdf(path: Path) -> None:
    document = pymupdf.open()  # type: ignore[no-untyped-call]
    page = document.new_page()
    page.insert_text((72, 72), "Confidential financial results")
    document.save(  # type: ignore[no-untyped-call]
        path,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner-password",
        user_pw="user-password",
    )
    document.close()  # type: ignore[no-untyped-call]


class _FakePage:
    def get_text(self, _format: str) -> str:
        raise RuntimeError("synthetic extraction failure")


class _FakeDocument:
    is_pdf = True
    needs_pass = False

    def __init__(self, page_count: int) -> None:
        self.page_count = page_count

    def __enter__(self) -> _FakeDocument:
        return self

    def __exit__(
        self,
        _exception_type: type[BaseException] | None,
        _exception: BaseException | None,
        _traceback: object | None,
    ) -> None:
        return None

    def load_page(self, _page_index: int) -> _FakePage:
        return _FakePage()


def test_parse_pdf_preserves_page_order_text_and_provenance(tmp_path: Path) -> None:
    pdf_path = tmp_path / "Annual Report.pdf"
    _write_pdf(pdf_path, ["Revenue 2025: $125 million", "Adjusted EBITDA: $30 million"])

    parsed = parse_pdf(pdf_path)

    assert parsed.page_count == 2
    assert parsed.document_id == f"sha256:{parsed.source.sha256}"
    assert parsed.source.filename == "Annual Report.pdf"
    assert parsed.source.path == pdf_path.resolve()
    assert parsed.source.media_type == "application/pdf"
    assert parsed.source.size_bytes == pdf_path.stat().st_size
    assert "Revenue 2025: $125 million" in parsed.pages[0].text
    assert "Adjusted EBITDA: $30 million" in parsed.pages[1].text
    assert [page.page_number for page in parsed.pages] == [1, 2]
    assert [page.provenance.pdf_page_index for page in parsed.pages] == [0, 1]
    assert all(page.provenance.document_id == parsed.document_id for page in parsed.pages)
    assert all(page.provenance.printed_page_label is None for page in parsed.pages)
    assert parsed.warnings == ()


def test_document_id_is_stable_for_identical_content(tmp_path: Path) -> None:
    pdf_path = tmp_path / "report.pdf"
    _write_pdf(pdf_path, ["Stable content"])

    first = parse_pdf(pdf_path)
    second = parse_pdf(pdf_path)

    assert first.document_id == second.document_id
    assert first.source.sha256 == second.source.sha256


def test_empty_text_page_is_preserved_with_warning(tmp_path: Path) -> None:
    pdf_path = tmp_path / "presentation.pdf"
    _write_pdf(pdf_path, ["Company overview", ""])

    parsed = parse_pdf(pdf_path)

    assert parsed.page_count == 2
    assert parsed.pages[1].text == ""
    assert len(parsed.warnings) == 1
    assert parsed.warnings[0].code is ParsingWarningCode.EMPTY_PAGE_TEXT
    assert parsed.warnings[0].page_number == 2


def test_missing_source_raises_specific_error(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.pdf"

    with pytest.raises(SourceNotFoundError, match="does not exist"):
        parse_pdf(missing_path)


def test_unsupported_extension_is_rejected(tmp_path: Path) -> None:
    text_path = tmp_path / "report.txt"
    text_path.write_text("not a PDF", encoding="utf-8")

    with pytest.raises(UnsupportedDocumentTypeError, match="expected .pdf"):
        parse_pdf(text_path)


def test_directory_with_pdf_suffix_is_rejected(tmp_path: Path) -> None:
    directory = tmp_path / "directory.pdf"
    directory.mkdir()

    with pytest.raises(InvalidDocumentSourceError, match="not a regular file"):
        parse_pdf(directory)


def test_corrupt_pdf_raises_specific_error(tmp_path: Path) -> None:
    corrupt_path = tmp_path / "corrupt.pdf"
    corrupt_path.write_bytes(b"%PDF-1.7\nthis is not a valid PDF")

    with pytest.raises(InvalidPdfError, match="Invalid or unreadable PDF"):
        parse_pdf(corrupt_path)


def test_encrypted_pdf_raises_specific_error(tmp_path: Path) -> None:
    encrypted_path = tmp_path / "encrypted.pdf"
    _write_encrypted_pdf(encrypted_path)

    with pytest.raises(EncryptedPdfError, match="requires a password"):
        parse_pdf(encrypted_path)


def test_zero_page_pdf_raises_specific_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "zero-pages.pdf"
    pdf_path.write_bytes(b"%PDF synthetic test placeholder")

    def open_zero_page_pdf(_path: Path) -> _FakeDocument:
        return _FakeDocument(page_count=0)

    monkeypatch.setattr(pymupdf, "open", open_zero_page_pdf)

    with pytest.raises(EmptyPdfError, match="contains no pages"):
        parse_pdf(pdf_path)


def test_page_extraction_failure_includes_page_number(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "extraction-failure.pdf"
    pdf_path.write_bytes(b"%PDF synthetic test placeholder")

    def open_failing_pdf(_path: Path) -> _FakeDocument:
        return _FakeDocument(page_count=1)

    monkeypatch.setattr(pymupdf, "open", open_failing_pdf)

    with pytest.raises(PdfParsingError, match="Failed to parse page 1"):
        parse_pdf(pdf_path)


def test_inspection_cli_prints_bounded_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pdf_path = tmp_path / "results.pdf"
    _write_pdf(pdf_path, ["Revenue grew by 12 percent", "This page is not previewed"])

    exit_code = main([str(pdf_path), "--max-pages", "1", "--preview-chars", "12"])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["page_count"] == 2
    assert len(output["page_previews"]) == 1
    assert output["page_previews"][0]["text_preview"] == "Revenue grew"


def test_inspection_cli_bounds_warning_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pdf_path = tmp_path / "scanned-report.pdf"
    _write_pdf(pdf_path, ["", "", ""])

    exit_code = main([str(pdf_path), "--max-warnings", "1"])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["warning_count"] == 3
    assert output["warnings_displayed"] == 1
    assert output["warnings_truncated"] is True
    assert len(output["warnings"]) == 1


def test_inspection_cli_reports_ingestion_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing_path = tmp_path / "missing.pdf"

    with pytest.raises(SystemExit) as exit_info:
        main([str(missing_path)])

    assert exit_info.value.code == 2
    assert "Document source does not exist" in capsys.readouterr().err
