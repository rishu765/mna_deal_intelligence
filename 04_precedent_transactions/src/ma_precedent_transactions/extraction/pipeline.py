"""Deal-scoped retrieval bundle feeding M3 structured extraction."""

from __future__ import annotations

from ma_precedent_transactions.retrieval import (
    DealRetrievalResult,
    HybridDealRetriever,
    RetrievalFilters,
)

EXTRACTION_QUERIES = (
    "Who are the acquirer, target, seller, and parent in this transaction?",
    "What are the announcement, signing, completion, termination, and status dates?",
    "What transaction type, cash, stock, offer price, ownership, and deal values were disclosed?",
    "What revenue EBITDA EBIT net income debt and cash were disclosed near announcement?",
)


def retrieve_extraction_context(
    retriever: HybridDealRetriever,
    transaction_id: str,
    *,
    top_k_per_query: int = 10,
) -> tuple[DealRetrievalResult, ...]:
    """Retrieve a bounded, transaction-filtered union for extraction."""

    by_chunk: dict[str, DealRetrievalResult] = {}
    filters = RetrievalFilters(transaction_id=transaction_id)
    for query in EXTRACTION_QUERIES:
        response = retriever.retrieve(query, top_k=top_k_per_query, filters=filters)
        for result in response.results:
            existing = by_chunk.get(result.chunk_id)
            if existing is None or result.fused_score > existing.fused_score:
                by_chunk[result.chunk_id] = result
    return tuple(sorted(by_chunk.values(), key=lambda item: item.chunk_id))
