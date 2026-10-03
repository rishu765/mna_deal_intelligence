"""Deterministic tests for semantic ranking, filters, and provenance."""

from __future__ import annotations

import json
from pathlib import Path

import pymupdf
import pytest

from ma_company_intelligence.domain import (
    ChunkPageReference,
    DocumentChunk,
    DocumentMetadata,
    DocumentSource,
    RetrievalFilters,
)
from ma_company_intelligence.embeddings import EmbeddingProviderError
from ma_company_intelligence.indexing import ChunkIndexingService, SQLiteVectorStore
from ma_company_intelligence.retrieval import (
    InvalidQueryError,
    QueryVectorError,
    SemanticRetriever,
)
from ma_company_intelligence.retrieval_cli import main as retrieval_cli_main


class _MappedEmbedder:
    provider_name = "test"
    model_name = "retrieval-test-model"
    dimension = 3

    def __init__(
        self,
        vectors: dict[str, tuple[float, ...]],
        *,
        fail_query: str | None = None,
    ) -> None:
        self._vectors = vectors
        self._fail_query = fail_query

    def embed_text(self, text: str) -> tuple[float, ...]:
        if text == self._fail_query:
            raise EmbeddingProviderError("synthetic query embedding failure")
        return self._vectors[text]

    def embed_batch(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple(self._vectors[text] for text in texts)


def _chunk(
    tmp_path: Path,
    *,
    index: int,
    text: str,
    company: str = "Example plc",
    document_type: str = "annual_report",
    fiscal_year: int = 2025,
) -> DocumentChunk:
    source_path = (tmp_path / f"report-{company}-{fiscal_year}.pdf").resolve()
    source_path.write_bytes(b"synthetic source")
    return DocumentChunk(
        chunk_id=f"sha256:{index:064x}",
        document_id="sha256:" + f"{fiscal_year:064x}",
        chunk_index=index,
        text=text,
        source=DocumentSource(
            filename=source_path.name,
            path=source_path,
            media_type="application/pdf",
            size_bytes=source_path.stat().st_size,
            sha256=f"{fiscal_year:064x}",
        ),
        page_references=(
            ChunkPageReference(
                pdf_page_index=index,
                page_number=index + 1,
                printed_page_label=None,
            ),
        ),
        metadata=DocumentMetadata(
            company=company,
            document_title=f"{company} Annual Report {fiscal_year}",
            document_type=document_type,
            fiscal_year=fiscal_year,
        ),
    )


def _store(path: Path, *, dimension: int = 3) -> SQLiteVectorStore:
    return SQLiteVectorStore(
        path,
        provider_name="test",
        model_name="retrieval-test-model",
        dimension=dimension,
    )


def _indexed_fixture(
    tmp_path: Path,
) -> tuple[tuple[DocumentChunk, ...], _MappedEmbedder, SQLiteVectorStore]:
    chunks = (
        _chunk(
            tmp_path,
            index=0,
            text="FY25 revenue increased to $125 million due to subscription growth.",
        ),
        _chunk(
            tmp_path,
            index=1,
            text="The company employed 850 people at year end.",
        ),
        _chunk(
            tmp_path,
            index=2,
            text="Material risks include foreign exchange and customer concentration.",
        ),
    )
    vectors = {
        chunks[0].text: (1.0, 0.0, 0.0),
        chunks[1].text: (0.0, 1.0, 0.0),
        chunks[2].text: (0.0, 0.0, 1.0),
        "What was FY25 revenue?": (0.95, 0.05, 0.0),
        "Which risks were disclosed?": (0.0, 0.05, 0.95),
    }
    embedder = _MappedEmbedder(vectors)
    store = _store(tmp_path / "vectors.sqlite3")
    ChunkIndexingService(embedder, store).index(chunks)
    return chunks, embedder, store


def test_relevant_financial_chunk_ranks_first_with_provenance(tmp_path: Path) -> None:
    chunks, embedder, store = _indexed_fixture(tmp_path)
    with store:
        results = SemanticRetriever(embedder, store).retrieve(
            "What was FY25 revenue?",
            top_k=2,
        )

    assert [result.rank for result in results] == [1, 2]
    assert results[0].chunk_id == chunks[0].chunk_id
    assert results[0].score > results[1].score
    assert results[0].text == chunks[0].text
    assert results[0].chunk.source == chunks[0].source
    assert results[0].chunk.page_references == chunks[0].page_references
    assert results[0].chunk.metadata == chunks[0].metadata


def test_top_k_limits_results_and_scores_use_descending_cosine_similarity(
    tmp_path: Path,
) -> None:
    chunks, embedder, store = _indexed_fixture(tmp_path)
    with store:
        results = SemanticRetriever(embedder, store).retrieve(
            "Which risks were disclosed?",
            top_k=1,
        )

    assert len(results) == 1
    assert results[0].chunk_id == chunks[2].chunk_id
    assert 0.99 < results[0].score <= 1.0


@pytest.mark.parametrize("query", ["", "   ", "\n\t"])
def test_blank_query_is_rejected_without_embedding(query: str, tmp_path: Path) -> None:
    chunks, embedder, store = _indexed_fixture(tmp_path)
    with store, pytest.raises(InvalidQueryError, match="non-whitespace"):
        SemanticRetriever(embedder, store).retrieve(query)
    assert chunks


@pytest.mark.parametrize("top_k", [0, -1])
def test_nonpositive_top_k_is_rejected(top_k: int, tmp_path: Path) -> None:
    _chunks, embedder, store = _indexed_fixture(tmp_path)
    with store, pytest.raises(InvalidQueryError, match="top_k"):
        SemanticRetriever(embedder, store).retrieve("What was FY25 revenue?", top_k=top_k)


def test_empty_index_returns_no_results(tmp_path: Path) -> None:
    embedder = _MappedEmbedder({"What was FY25 revenue?": (1.0, 0.0, 0.0)})
    with _store(tmp_path / "empty.sqlite3") as store:
        results = SemanticRetriever(embedder, store).retrieve("What was FY25 revenue?")

    assert results == ()


def test_exact_metadata_filters_are_applied_before_ranking(tmp_path: Path) -> None:
    first = _chunk(tmp_path, index=0, text="Revenue was $100 million.")
    second = _chunk(
        tmp_path,
        index=1,
        text="Revenue was $200 million.",
        company="Other plc",
        fiscal_year=2024,
    )
    vectors = {
        first.text: (0.9, 0.1, 0.0),
        second.text: (1.0, 0.0, 0.0),
        "What was revenue?": (1.0, 0.0, 0.0),
    }
    embedder = _MappedEmbedder(vectors)
    with _store(tmp_path / "filters.sqlite3") as store:
        ChunkIndexingService(embedder, store).index((first, second))
        results = SemanticRetriever(embedder, store).retrieve(
            "What was revenue?",
            filters=RetrievalFilters(company="Example plc", fiscal_year=2025),
        )

    assert [result.chunk_id for result in results] == [first.chunk_id]


def test_equal_scores_use_stable_chunk_id_tie_break(tmp_path: Path) -> None:
    chunks = (
        _chunk(tmp_path, index=2, text="Second stable identifier."),
        _chunk(tmp_path, index=1, text="First stable identifier."),
    )
    vectors = {
        chunks[0].text: (1.0, 0.0, 0.0),
        chunks[1].text: (1.0, 0.0, 0.0),
        "tie": (1.0, 0.0, 0.0),
    }
    embedder = _MappedEmbedder(vectors)
    with _store(tmp_path / "ties.sqlite3") as store:
        ChunkIndexingService(embedder, store).index(chunks)
        results = SemanticRetriever(embedder, store).retrieve("tie")

    assert [result.chunk_id for result in results] == sorted(chunk.chunk_id for chunk in chunks)


def test_provider_failure_propagates_without_searching(tmp_path: Path) -> None:
    embedder = _MappedEmbedder({}, fail_query="provider failure")
    with (
        _store(tmp_path / "failure.sqlite3") as store,
        pytest.raises(EmbeddingProviderError, match="synthetic"),
    ):
        SemanticRetriever(embedder, store).retrieve("provider failure")


def test_unexpected_query_dimension_is_rejected(tmp_path: Path) -> None:
    embedder = _MappedEmbedder({"bad dimension": (1.0, 0.0)})
    with (
        _store(tmp_path / "dimension.sqlite3") as store,
        pytest.raises(QueryVectorError, match="dimension 2"),
    ):
        SemanticRetriever(embedder, store).retrieve("bad dimension")


def test_zero_magnitude_query_vector_is_rejected(tmp_path: Path) -> None:
    embedder = _MappedEmbedder({"zero": (0.0, 0.0, 0.0)})
    with (
        _store(tmp_path / "zero.sqlite3") as store,
        pytest.raises(QueryVectorError, match="zero magnitude"),
    ):
        SemanticRetriever(embedder, store).retrieve("zero")


def _write_pdf(path: Path, text: str) -> None:
    document = pymupdf.open()  # type: ignore[no-untyped-call]
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)  # type: ignore[no-untyped-call]
    document.close()  # type: ignore[no-untyped-call]


class _PipelineEmbedder:
    provider_name = "test"
    model_name = "retrieval-test-model"
    dimension = 3

    def embed_text(self, _text: str) -> tuple[float, ...]:
        return (1.0, 0.0, 0.0)

    def embed_batch(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple((1.0, 0.0, 0.0) for _text in texts)


def test_retrieval_cli_runs_complete_pipeline_with_bounded_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pdf_path = tmp_path / "report.pdf"
    index_path = tmp_path / "retrieval.sqlite3"
    _write_pdf(pdf_path, "Subscription demand was the primary FY25 growth driver.")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "ma_company_intelligence.retrieval_cli.OpenAIEmbedder",
        lambda **_arguments: _PipelineEmbedder(),
    )

    exit_code = retrieval_cli_main(
        [
            str(pdf_path),
            "What were the main growth drivers?",
            "--index-path",
            str(index_path),
            "--top-k",
            "1",
            "--preview-chars",
            "24",
            "--company",
            "Example plc",
        ]
    )
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["query"] == "What were the main growth drivers?"
    assert summary["result_count"] == 1
    assert summary["results"][0]["rank"] == 1
    assert summary["results"][0]["score"] == 1.0
    assert summary["results"][0]["page_numbers"] == [1]
    assert summary["results"][0]["company"] == "Example plc"
    assert len(summary["results"][0]["text_preview"]) == 24
    assert "embedding" not in summary["results"][0]
