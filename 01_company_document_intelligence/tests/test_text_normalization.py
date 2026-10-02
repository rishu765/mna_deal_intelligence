"""Tests for conservative parser-text normalization."""

from ma_company_intelligence.ingestion.normalization import normalize_extracted_text


def test_normalization_preserves_financial_text_and_spacing() -> None:
    raw = "Revenue\r\n  FY25\t$1,250 (10.5%)\rMargin: −2%\x00\x07"

    normalized = normalize_extracted_text(raw)

    assert normalized == "Revenue\n  FY25\t$1,250 (10.5%)\nMargin: −2%"
