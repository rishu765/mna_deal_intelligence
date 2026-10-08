from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from conftest import FIXTURE_ROOT, ResearchHarness
from ma_precedent_transactions.discovery import CandidateTransaction
from ma_precedent_transactions.documents import (
    DealDocumentIngestor,
    DealDocumentSource,
    DealSourceType,
    DocumentFormat,
    FixtureDocumentCatalog,
    ParsedDealDocument,
    TransactionAwareChunker,
)
from ma_precedent_transactions.domain import SourceReliability
from ma_precedent_transactions.errors import (
    DocumentUnavailableError,
    MalformedDocumentError,
    UnsupportedDocumentFormatError,
)


def source(
    location: str,
    document_format: DocumentFormat,
    *,
    source_id: str = "source-1",
) -> DealDocumentSource:
    return DealDocumentSource(
        source_id=source_id,
        transaction_id="txn-cash",
        source_type=DealSourceType.ACQUISITION_PRESS_RELEASE,
        title="Synthetic source",
        location=location,
        publisher="Fictitious issuer",
        publication_date=date(2024, 2, 1),
        jurisdiction="United States",
        document_format=document_format,
        retrieved_at=datetime(2026, 10, 9, tzinfo=UTC),
        reliability=SourceReliability.PRIMARY_COMPANY,
        official_source=True,
    )


def test_document_catalog_maps_sources_to_transactions() -> None:
    catalog = FixtureDocumentCatalog(FIXTURE_ROOT / "document_catalog.json")
    sources = catalog.find_for_transactions(("txn-cash", "txn-stock"))

    assert len(sources) == 3
    assert {item.transaction_id for item in sources} == {"txn-cash", "txn-stock"}


def test_text_and_html_ingestion_preserve_source_and_section() -> None:
    catalog = FixtureDocumentCatalog(FIXTURE_ROOT / "document_catalog.json")
    ingestor = DealDocumentIngestor(FIXTURE_ROOT)
    sources = catalog.find_for_transactions(("txn-cash",))
    parsed = tuple(ingestor.ingest(item) for item in sources)

    assert {item.source.document_format for item in parsed} == {
        DocumentFormat.HTML,
        DocumentFormat.TEXT,
    }
    assert {item.pages[0].section for item in parsed} == {
        "Transaction consideration",
        "Offer terms",
    }
    assert all(item.pages[0].page_number == 1 for item in parsed)


def test_chunk_metadata_retains_transaction_and_party_context(
    research_harness: ResearchHarness,
) -> None:
    chunk = next(
        item for item in research_harness.corpus.chunks if item.transaction_id == "txn-cash"
    )

    assert chunk.document_id.startswith("doc-cash")
    assert chunk.page_numbers == (1,)
    assert chunk.section is not None
    assert chunk.acquirer_name == "Northstar Payments plc"
    assert chunk.target_name == "Ledgerlane Technologies Ltd."
    assert chunk.source.official_source is True


def test_malformed_text_document_is_reported(tmp_path: Path) -> None:
    bad = tmp_path / "bad.txt"
    bad.write_bytes(b"\xff\xfe\x00")
    ingestor = DealDocumentIngestor(tmp_path)

    with pytest.raises(MalformedDocumentError, match="UTF-8"):
        ingestor.ingest(source("bad.txt", DocumentFormat.TEXT))


def test_unavailable_document_is_reported(tmp_path: Path) -> None:
    with pytest.raises(DocumentUnavailableError, match="unavailable"):
        DealDocumentIngestor(tmp_path).ingest(source("missing.txt", DocumentFormat.TEXT))


def test_pdf_requires_explicit_project1_or_other_adapter(tmp_path: Path) -> None:
    (tmp_path / "deal.pdf").write_bytes(b"%PDF-invalid")
    ingestor = DealDocumentIngestor(tmp_path)

    with pytest.raises(UnsupportedDocumentFormatError, match="Project 1 adapter"):
        ingestor.ingest(source("deal.pdf", DocumentFormat.PDF))


def test_malformed_pdf_adapter_failure_is_preserved(tmp_path: Path) -> None:
    class MalformedPdfParser:
        def parse(self, document_source: DealDocumentSource, path: Path) -> ParsedDealDocument:
            del document_source, path
            raise MalformedDocumentError("synthetic malformed PDF")

    (tmp_path / "deal.pdf").write_bytes(b"%PDF-invalid")
    ingestor = DealDocumentIngestor(tmp_path, pdf_parser=MalformedPdfParser())

    with pytest.raises(MalformedDocumentError, match="malformed PDF"):
        ingestor.ingest(source("deal.pdf", DocumentFormat.PDF))


def test_duplicate_catalog_sources_are_deduplicated(tmp_path: Path) -> None:
    item = {
        "source_id": "doc-1",
        "transaction_id": "txn-cash",
        "source_type": "official_announcement",
        "title": "Title",
        "location": "documents/a.txt",
        "publisher": "Issuer",
        "publication_date": "2024-01-01",
        "jurisdiction": "United States",
        "document_format": "text",
        "retrieved_at": "2026-10-09T00:00:00+00:00",
        "reliability": "primary_company",
        "official_source": True,
    }
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps([item, item]), encoding="utf-8")

    result = FixtureDocumentCatalog(path).find_for_transactions(("txn-cash",))

    assert len(result) == 1


def test_chunker_rejects_document_transaction_mismatch(
    research_harness: ResearchHarness,
) -> None:
    document = research_harness.corpus.parsed_documents[0]
    wrong_transaction: CandidateTransaction = next(
        item
        for item in research_harness.corpus.discovery.transactions
        if item.candidate_id != document.source.transaction_id
    )

    with pytest.raises(ValueError, match="transaction IDs"):
        TransactionAwareChunker().chunk(document, wrong_transaction)
