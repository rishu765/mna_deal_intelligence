"""Atomic in-memory vector and BM25 index for deal document chunks."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from ma_precedent_transactions.documents.models import DealDocumentChunk
from ma_precedent_transactions.errors import EmbeddingError, IndexingError
from ma_precedent_transactions.retrieval.embedding import EmbeddingProvider, lexical_tokens
from ma_precedent_transactions.retrieval.models import ChannelMatch, RetrievalFilters


@dataclass(frozen=True, slots=True)
class IndexingReport:
    chunks_received: int
    unique_chunks: int
    chunks_indexed: int
    duplicate_chunks: int
    total_chunks: int
    embedding_provider: str
    embedding_model: str


class InMemoryDealIndex:
    """A small offline index; indexing validates everything before mutation."""

    def __init__(self, embedder: EmbeddingProvider) -> None:
        self._embedder = embedder
        self._chunks: dict[str, DealDocumentChunk] = {}
        self._vectors: dict[str, tuple[float, ...]] = {}
        self._term_frequencies: dict[str, Counter[str]] = {}
        self._document_lengths: dict[str, int] = {}

    @property
    def count(self) -> int:
        return len(self._chunks)

    def index(self, chunks: tuple[DealDocumentChunk, ...]) -> IndexingReport:
        unique: dict[str, DealDocumentChunk] = {}
        duplicate_count = 0
        for chunk in chunks:
            existing = unique.get(chunk.chunk_id) or self._chunks.get(chunk.chunk_id)
            if existing is not None:
                if existing != chunk:
                    raise IndexingError(f"chunk ID {chunk.chunk_id!r} has conflicting content")
                duplicate_count += 1
                continue
            unique[chunk.chunk_id] = chunk
        pending_vectors: dict[str, tuple[float, ...]] = {}
        pending_terms: dict[str, Counter[str]] = {}
        pending_lengths: dict[str, int] = {}
        try:
            for chunk_id, chunk in unique.items():
                vector = self._embedder.embed(chunk.text)
                if len(vector) != self._embedder.dimension:
                    raise EmbeddingError("embedding provider returned the wrong dimension")
                terms = lexical_tokens(chunk.text)
                pending_vectors[chunk_id] = vector
                pending_terms[chunk_id] = Counter(terms)
                pending_lengths[chunk_id] = len(terms)
        except (EmbeddingError, ValueError) as error:
            raise IndexingError(f"indexing failed before commit: {error}") from error
        self._chunks.update(unique)
        self._vectors.update(pending_vectors)
        self._term_frequencies.update(pending_terms)
        self._document_lengths.update(pending_lengths)
        return IndexingReport(
            chunks_received=len(chunks),
            unique_chunks=len(unique),
            chunks_indexed=len(unique),
            duplicate_chunks=duplicate_count,
            total_chunks=self.count,
            embedding_provider=self._embedder.provider_name,
            embedding_model=self._embedder.model_name,
        )

    def semantic_search(
        self, query: str, *, filters: RetrievalFilters | None = None
    ) -> tuple[ChannelMatch, ...]:
        query_vector = self._embedder.embed(query)
        matches = [
            ChannelMatch(chunk, _cosine(query_vector, self._vectors[chunk_id]))
            for chunk_id, chunk in self._chunks.items()
            if filters is None or filters.matches(chunk)
        ]
        return tuple(sorted(matches, key=lambda item: (-item.score, item.chunk.chunk_id)))

    def lexical_search(
        self, query: str, *, filters: RetrievalFilters | None = None
    ) -> tuple[ChannelMatch, ...]:
        query_terms = lexical_tokens(query)
        eligible = {
            chunk_id: chunk
            for chunk_id, chunk in self._chunks.items()
            if filters is None or filters.matches(chunk)
        }
        if not eligible:
            return ()
        average_length = sum(self._document_lengths[x] for x in eligible) / len(eligible)
        document_frequency = Counter(
            term for chunk_id in eligible for term in self._term_frequencies[chunk_id]
        )
        matches = []
        for chunk_id, chunk in eligible.items():
            score = _bm25(
                query_terms,
                self._term_frequencies[chunk_id],
                self._document_lengths[chunk_id],
                average_length,
                document_frequency,
                len(eligible),
            )
            matches.append(ChannelMatch(chunk, score))
        return tuple(sorted(matches, key=lambda item: (-item.score, item.chunk.chunk_id)))


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _bm25(
    query_terms: list[str],
    term_frequency: Counter[str],
    document_length: int,
    average_length: float,
    document_frequency: Counter[str],
    document_count: int,
) -> float:
    if not query_terms or average_length == 0:
        return 0.0
    score = 0.0
    k1 = 1.5
    b = 0.75
    for term in set(query_terms):
        frequency = term_frequency[term]
        if frequency == 0:
            continue
        inverse_frequency = math.log(
            1 + (document_count - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5)
        )
        numerator = frequency * (k1 + 1)
        denominator = frequency + k1 * (1 - b + b * document_length / average_length)
        score += inverse_frequency * numerator / denominator
    return score
