"""Semantic retrieval orchestration over the M3 embedding and store interfaces."""

from __future__ import annotations

import math

from ma_company_intelligence.domain import (
    EmbeddingVector,
    RetrievalFilters,
    RetrievalResult,
)
from ma_company_intelligence.embeddings import Embedder
from ma_company_intelligence.indexing.base import VectorStore
from ma_company_intelligence.retrieval.errors import InvalidQueryError, QueryVectorError


class SemanticRetriever:
    """Embed one query and return ranked, provenance-complete chunks."""

    def __init__(self, embedder: Embedder, vector_store: VectorStore) -> None:
        if embedder.dimension != vector_store.dimension:
            raise QueryVectorError(
                f"embedder dimension {embedder.dimension} does not match "
                f"store dimension {vector_store.dimension}"
            )
        if embedder.provider_name != vector_store.provider_name:
            raise QueryVectorError("embedder and vector store providers do not match")
        if embedder.model_name != vector_store.model_name:
            raise QueryVectorError("embedder and vector store models do not match")
        self._embedder = embedder
        self._vector_store = vector_store

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> tuple[RetrievalResult, ...]:
        """Return top-k chunks ordered by descending cosine similarity."""

        if not query.strip():
            raise InvalidQueryError("query must contain non-whitespace text")
        if top_k <= 0:
            raise InvalidQueryError("top_k must be positive")

        values = self._embedder.embed_text(query)
        if len(values) != self._embedder.dimension:
            raise QueryVectorError(
                f"query embedding has dimension {len(values)}; expected {self._embedder.dimension}"
            )
        if not all(math.isfinite(value) for value in values):
            raise QueryVectorError("query embedding contains a non-finite value")
        if math.sqrt(sum(value * value for value in values)) == 0.0:
            raise QueryVectorError("query embedding has zero magnitude")

        query_vector = EmbeddingVector(
            provider=self._embedder.provider_name,
            model=self._embedder.model_name,
            dimension=self._embedder.dimension,
            values=values,
        )
        matches = self._vector_store.similarity_search(
            query_vector,
            top_k=top_k,
            filters=filters,
        )
        return tuple(
            RetrievalResult(rank=rank, score=match.score, chunk=match.record.chunk)
            for rank, match in enumerate(matches, start=1)
        )
