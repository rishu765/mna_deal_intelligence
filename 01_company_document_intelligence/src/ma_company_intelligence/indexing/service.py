"""Batch embedding and atomic vector-record indexing."""

from __future__ import annotations

from dataclasses import dataclass

from ma_company_intelligence.domain import DocumentChunk, EmbeddingVector, VectorRecord
from ma_company_intelligence.embeddings import Embedder, EmbeddingResponseError
from ma_company_intelligence.indexing.base import VectorStore
from ma_company_intelligence.indexing.errors import (
    DuplicateChunkError,
    InvalidChunkError,
    VectorDimensionError,
)


@dataclass(frozen=True, slots=True)
class IndexingReport:
    """Small deterministic summary of one indexing operation."""

    chunks_received: int
    unique_chunks: int
    embedding_batches: int
    records_upserted: int
    total_records: int
    embedding_dimension: int
    embedding_provider: str
    embedding_model: str


class ChunkIndexingService:
    """Embed M2 chunks in batches, validate them, then atomically persist records."""

    def __init__(
        self,
        embedder: Embedder,
        vector_store: VectorStore,
        *,
        batch_size: int = 64,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if embedder.dimension != vector_store.dimension:
            raise VectorDimensionError(
                f"embedder dimension {embedder.dimension} does not match "
                f"store dimension {vector_store.dimension}"
            )
        if embedder.provider_name != vector_store.provider_name:
            raise ValueError("embedder and vector store providers do not match")
        if embedder.model_name != vector_store.model_name:
            raise ValueError("embedder and vector store models do not match")
        self._embedder = embedder
        self._vector_store = vector_store
        self._batch_size = batch_size

    def index(self, chunks: tuple[DocumentChunk, ...]) -> IndexingReport:
        """Embed and upsert chunks without leaving partially written batches."""

        unique_chunks = self._deduplicate(chunks)
        records: list[VectorRecord] = []
        batch_count = 0

        for offset in range(0, len(unique_chunks), self._batch_size):
            batch = unique_chunks[offset : offset + self._batch_size]
            vectors = self._embedder.embed_batch(tuple(chunk.text for chunk in batch))
            batch_count += 1
            if len(vectors) != len(batch):
                raise EmbeddingResponseError(
                    f"embedder returned {len(vectors)} vectors for {len(batch)} chunks "
                    f"in batch {batch_count}"
                )

            for chunk, vector in zip(batch, vectors, strict=True):
                if len(vector) != self._embedder.dimension:
                    raise VectorDimensionError(
                        f"embedding for chunk {chunk.chunk_id!r} has dimension {len(vector)}; "
                        f"expected {self._embedder.dimension}"
                    )
                try:
                    embedding = EmbeddingVector(
                        provider=self._embedder.provider_name,
                        model=self._embedder.model_name,
                        dimension=self._embedder.dimension,
                        values=vector,
                    )
                except ValueError as error:
                    raise VectorDimensionError(
                        f"invalid embedding for chunk {chunk.chunk_id!r}: {error}"
                    ) from error
                records.append(
                    VectorRecord(
                        record_id=chunk.chunk_id,
                        chunk=chunk,
                        embedding=embedding,
                    )
                )

        records_upserted = self._vector_store.upsert(tuple(records)) if records else 0
        return IndexingReport(
            chunks_received=len(chunks),
            unique_chunks=len(unique_chunks),
            embedding_batches=batch_count,
            records_upserted=records_upserted,
            total_records=self._vector_store.count(),
            embedding_dimension=self._embedder.dimension,
            embedding_provider=self._embedder.provider_name,
            embedding_model=self._embedder.model_name,
        )

    @staticmethod
    def _deduplicate(chunks: tuple[DocumentChunk, ...]) -> tuple[DocumentChunk, ...]:
        unique: dict[str, DocumentChunk] = {}
        for position, chunk in enumerate(chunks):
            if not isinstance(chunk, DocumentChunk):
                raise InvalidChunkError(f"item at position {position} is not a DocumentChunk")
            if not chunk.text.strip():
                raise InvalidChunkError(f"chunk {chunk.chunk_id!r} has blank text")
            existing = unique.get(chunk.chunk_id)
            if existing is not None and existing != chunk:
                raise DuplicateChunkError(
                    f"chunk ID {chunk.chunk_id!r} maps to conflicting chunk data"
                )
            unique.setdefault(chunk.chunk_id, chunk)
        return tuple(unique.values())
