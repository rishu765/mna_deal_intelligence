"""Tests for the deterministic, copyright-safe demonstration document."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from ma_company_intelligence.chunking import ChunkingConfig, chunk_document
from ma_company_intelligence.demo_document import DEMO_PAGES, create_demo_pdf, main
from ma_company_intelligence.ingestion import parse_pdf


def test_demo_pdf_is_deterministic_parseable_and_representative(tmp_path: Path) -> None:
    first = create_demo_pdf(tmp_path / "first.pdf")
    second = create_demo_pdf(tmp_path / "second.pdf")

    assert (
        hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(second.read_bytes()).digest()
    )
    parsed = parse_pdf(first)
    assert parsed.page_count == len(DEMO_PAGES) == 5
    assert parsed.warnings == ()
    combined_text = "\n".join(page.text for page in parsed.pages)
    assert "reported revenue was USD 125 million" in combined_text
    assert "Adjusted EBITDA was USD 18 million" in combined_text
    assert "cybersecurity incidents" in combined_text
    assert "acquired VectorSense" in combined_text
    chunked = chunk_document(
        parsed,
        config=ChunkingConfig(
            max_characters=600,
            overlap_characters=80,
            min_chunk_characters=200,
        ),
    )
    assert len(chunked.chunks) == 5
    assert [page.page_number for page in chunked.chunks[2].page_references] == [2, 3]


def test_demo_pdf_refuses_implicit_overwrite_and_non_pdf_output(tmp_path: Path) -> None:
    output = create_demo_pdf(tmp_path / "demo.pdf")

    with pytest.raises(FileExistsError):
        create_demo_pdf(output)
    with pytest.raises(ValueError, match=".pdf extension"):
        create_demo_pdf(tmp_path / "demo.txt")


def test_demo_cli_reports_bounded_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "demo.pdf"

    assert main([str(output)]) == 0

    summary = json.loads(capsys.readouterr().out)
    assert summary["document"] == str(output.resolve())
    assert summary["pages"] == 5
    assert summary["fictional"] is True
    assert "madi-build-index" in summary["next_step"]
