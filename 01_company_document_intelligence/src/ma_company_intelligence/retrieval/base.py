"""Provider-neutral retrieval contract consumed by the RAG layer."""

from __future__ import annotations

from typing import Protocol

from ma_company_intelligence.domain import RetrievalFilters, RetrievalResult


class Retriever(Protocol):
    """Return ranked evidence for a validated natural-language query."""

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> tuple[RetrievalResult, ...]: ...
