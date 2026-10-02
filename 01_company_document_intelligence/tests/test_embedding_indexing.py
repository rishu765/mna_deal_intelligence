"""Tests for embedding contracts, indexing, and SQLite persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pymupdf
import pytest

from ma_company_intelligence.domain import (
    ChunkPageReference,
    DocumentChunk,
    DocumentMetadata,
    DocumentSource,
)
from ma_company_intelligence.embeddings import (
    EmbeddingConfigurationError,
    EmbeddingProviderError,
    EmbeddingSettings,
    OpenAIEmbedder,
)
from ma_company_intelligence.indexing import (
    ChunkIndexingService,
    IndexCompatibilityError,
    InvalidChunkError,
    SQLiteVectorStore,
    VectorDimensionError,
)
from ma_company_intelligence.index_cli import main as index_cli_main


def _chunk(tmp_path: Path, index: int, text: str | None = None) -> DocumentChunk:
    source_path = (tmp_path / "Annual Report.pdf").resolve()
    source_path.write_bytes(b"synthetic source")
    return DocumentChunk(
        chunk_id=f"sha256:{index:064x}",
        document_id="sha256:" + "a" * 64,
        chunk_index=index,
        text=text or f"Financial discussion for chunk {index}",
        source=DocumentSource(
            filename=source_path.name,
            path=source_path,
            media_type="application/pdf",
            size_bytes=source_path.stat().st_size,
            sha256="a" * 64,
        ),
        page_references=(
            ChunkPageReference(
                pdf_page_index=index,
                page_number=index + 1,
                printed_page_label=None,
            ),
        ),
        metadata=DocumentMetadata(
            company="Example plc",
            document_title="Annual Report 2025",
            fiscal_year=2025,
        ),
    )


class _FakeEmbedder:
    provider_name = "test"
    model_name = "deterministic-test-model"
    dimension = 3

    def __init__(self, *, fail_on_call: int | None = None, wrong_dimension: bool = False) -> None:
        self.calls: list[tuple[str, ...]] = []
        self._fail_on_call = fail_on_call
        self._wrong_dimension = wrong_dimension

    def embed_text(self, text: str) -> tuple[float, ...]:
        return self.embed_batch((text,))[0]

    def embed_batch(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        self.calls.append(texts)
        if self._fail_on_call == len(self.calls):
            raise EmbeddingProviderError("synthetic provider failure")
        dimension = 2 if self._wrong_dimension else self.dimension
        return tuple(
            tuple(float(position + offset) for offset in range(dimension))
            for position, _text in enumerate(texts)
        )


def _store(path: Path) -> SQLiteVectorStore:
    return SQLiteVectorStore(
        path,
        provider_name="test",
        model_name="deterministic-test-model",
        dimension=3,
    )


def _write_pdf(path: Path, text: str) -> None:
    document = pymupdf.open()  # type: ignore[no-untyped-call]
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)  # type: ignore[no-untyped-call]
    document.close()  # type: ignore[no-untyped-call]


def test_indexing_batches_in_order_and_preserves_chunk_provenance(tmp_path: Path) -> None:
    chunks = tuple(_chunk(tmp_path, index) for index in range(5))
    embedder = _FakeEmbedder()
    with _store(tmp_path / "vectors.sqlite3") as store:
        report = ChunkIndexingService(embedder, store, batch_size=2).index(chunks)
        stored = store.get(chunks[3].chunk_id)

    assert embedder.calls == [
        tuple(chunk.text for chunk in chunks[0:2]),
        tuple(chunk.text for chunk in chunks[2:4]),
        (chunks[4].text,),
    ]
    assert report.chunks_received == 5
    assert report.unique_chunks == 5
    assert report.embedding_batches == 3
    assert report.records_upserted == 5
    assert report.total_records == 5
    assert stored is not None
    assert stored.chunk == chunks[3]
    assert stored.record_id == chunks[3].chunk_id
    assert stored.chunk.page_numbers == (4,)
    assert stored.chunk.metadata.company == "Example plc"
    assert stored.embedding.dimension == 3


def test_reindexing_same_chunk_uses_upsert_without_duplicates(tmp_path: Path) -> None:
    chunk = _chunk(tmp_path, 0)
    embedder = _FakeEmbedder()
    with _store(tmp_path / "vectors.sqlite3") as store:
        service = ChunkIndexingService(embedder, store)
        first = service.index((chunk,))
        second = service.index((chunk, chunk))

        assert first.total_records == 1
        assert second.chunks_received == 2
        assert second.unique_chunks == 1
        assert second.total_records == 1
        assert store.count() == 1


def test_provider_failure_does_not_leave_partial_index_writes(tmp_path: Path) -> None:
    chunks = tuple(_chunk(tmp_path, index) for index in range(3))
    embedder = _FakeEmbedder(fail_on_call=2)
    with _store(tmp_path / "vectors.sqlite3") as store:
        with pytest.raises(EmbeddingProviderError, match="synthetic provider failure"):
            ChunkIndexingService(embedder, store, batch_size=2).index(chunks)

        assert store.count() == 0


def test_dimension_mismatch_is_rejected_before_writing(tmp_path: Path) -> None:
    embedder = _FakeEmbedder(wrong_dimension=True)
    with _store(tmp_path / "vectors.sqlite3") as store:
        with pytest.raises(VectorDimensionError, match="has dimension 2"):
            ChunkIndexingService(embedder, store).index((_chunk(tmp_path, 0),))

        assert store.count() == 0


def test_empty_input_is_a_successful_no_op(tmp_path: Path) -> None:
    embedder = _FakeEmbedder()
    with _store(tmp_path / "vectors.sqlite3") as store:
        report = ChunkIndexingService(embedder, store).index(())

    assert embedder.calls == []
    assert report.chunks_received == 0
    assert report.records_upserted == 0
    assert report.total_records == 0


def test_malformed_chunk_is_rejected_with_its_position(tmp_path: Path) -> None:
    invalid = cast(DocumentChunk, object())
    with (
        _store(tmp_path / "vectors.sqlite3") as store,
        pytest.raises(InvalidChunkError, match="position 0"),
    ):
        ChunkIndexingService(_FakeEmbedder(), store).index((invalid,))


def test_sqlite_store_persists_records_across_reopen(tmp_path: Path) -> None:
    index_path = tmp_path / "vectors.sqlite3"
    chunk = _chunk(tmp_path, 0)
    with _store(index_path) as store:
        ChunkIndexingService(_FakeEmbedder(), store).index((chunk,))

    with _store(index_path) as reopened:
        restored = reopened.get(chunk.chunk_id)
        assert reopened.count() == 1
        assert restored is not None
        assert restored.chunk == chunk
        assert restored.embedding.values == (0.0, 1.0, 2.0)


def test_existing_store_rejects_incompatible_embedding_manifest(tmp_path: Path) -> None:
    index_path = tmp_path / "vectors.sqlite3"
    with _store(index_path):
        pass

    with pytest.raises(IndexCompatibilityError, match="incompatible"):
        SQLiteVectorStore(
            index_path,
            provider_name="test",
            model_name="different-model",
            dimension=3,
        )


def test_settings_require_api_key_and_validate_integer_environment() -> None:
    with pytest.raises(EmbeddingConfigurationError, match="OPENAI_API_KEY"):
        EmbeddingSettings.from_environment({})
    with pytest.raises(EmbeddingConfigurationError, match="must be integers"):
        EmbeddingSettings.from_environment(
            {"OPENAI_API_KEY": "secret", "MADI_EMBEDDING_DIMENSION": "not-an-integer"}
        )


@dataclass
class _EmbeddingItem:
    index: int
    embedding: list[float]


@dataclass
class _EmbeddingResponse:
    data: list[_EmbeddingItem]


class _FakeEmbeddingsResource:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.request: dict[str, object] | None = None

    def create(self, **kwargs: object) -> _EmbeddingResponse:
        self.request = kwargs
        if self.should_fail:
            raise RuntimeError("provider detail containing no credential")
        return _EmbeddingResponse(
            data=[
                _EmbeddingItem(index=1, embedding=[3.0, 4.0]),
                _EmbeddingItem(index=0, embedding=[1.0, 2.0]),
            ]
        )


class _FakeOpenAIClient:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.embeddings = _FakeEmbeddingsResource(should_fail=should_fail)


def test_openai_adapter_preserves_input_order_and_request_configuration() -> None:
    client = _FakeOpenAIClient()
    embedder = OpenAIEmbedder(
        api_key="test-key",
        model="text-embedding-3-small",
        dimension=2,
        client=client,
    )

    vectors = embedder.embed_batch(("first", "second"))

    assert vectors == ((1.0, 2.0), (3.0, 4.0))
    assert client.embeddings.request == {
        "input": ["first", "second"],
        "model": "text-embedding-3-small",
        "dimensions": 2,
        "encoding_format": "float",
    }


def test_openai_adapter_wraps_provider_failure_without_exposing_key() -> None:
    embedder = OpenAIEmbedder(
        api_key="super-secret-key",
        dimension=2,
        client=_FakeOpenAIClient(should_fail=True),
    )

    with pytest.raises(EmbeddingProviderError) as captured:
        embedder.embed_text("Revenue increased")

    assert "super-secret-key" not in str(captured.value)


def test_build_index_cli_runs_complete_pipeline_with_bounded_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pdf_path = tmp_path / "report.pdf"
    index_path = tmp_path / "vectors.sqlite3"
    _write_pdf(pdf_path, "Revenue increased to $125 million in 2025.")
    embedder = _FakeEmbedder()
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "ma_company_intelligence.index_cli.OpenAIEmbedder",
        lambda **_arguments: embedder,
    )

    exit_code = index_cli_main(
        [
            str(pdf_path),
            "--index-path",
            str(index_path),
            "--company",
            "Example plc",
        ]
    )
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["page_count"] == 1
    assert summary["chunk_count"] == 1
    assert summary["embedding_dimension"] == 3
    assert summary["records_upserted"] == 1
    assert summary["total_index_records"] == 1
    assert summary["sample_record"]["company"] == "Example plc"
    assert "vector" not in summary["sample_record"]
    assert index_path.exists()
