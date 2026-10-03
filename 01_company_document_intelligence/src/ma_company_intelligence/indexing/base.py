"""Provider-neutral vector-record store interface."""

from __future__ import annotations

from typing import Protocol

from ma_company_intelligence.domain import (
    EmbeddingVector,
    RetrievalFilters,
    VectorRecord,
    VectorSearchMatch,
)


class VectorStore(Protocol):
    """Persist vector records without defining retrieval behavior."""

    @property
    def dimension(self) -> int: ...

    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    def upsert(self, records: tuple[VectorRecord, ...]) -> int: ...

    def count(self) -> int: ...

    def get(self, record_id: str) -> VectorRecord | None: ...

    def similarity_search(
        self,
        query_vector: EmbeddingVector,
        *,
        top_k: int,
        filters: RetrievalFilters | None = None,
    ) -> tuple[VectorSearchMatch, ...]: ...
