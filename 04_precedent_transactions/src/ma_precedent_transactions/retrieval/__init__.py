"""Offline semantic, lexical, and hybrid retrieval."""

from ma_precedent_transactions.retrieval.embedding import (
    EmbeddingProvider,
    HashingEmbeddingProvider,
)
from ma_precedent_transactions.retrieval.index import IndexingReport, InMemoryDealIndex
from ma_precedent_transactions.retrieval.models import (
    ChannelMatch,
    DealRetrievalResult,
    RetrievalFilters,
    RetrievalResponse,
    RetrievalWarning,
    RetrievalWarningCode,
)
from ma_precedent_transactions.retrieval.service import (
    HybridDealRetriever,
    HybridRetrievalConfig,
)

__all__ = [
    "ChannelMatch",
    "DealRetrievalResult",
    "EmbeddingProvider",
    "HashingEmbeddingProvider",
    "HybridDealRetriever",
    "HybridRetrievalConfig",
    "InMemoryDealIndex",
    "IndexingReport",
    "RetrievalFilters",
    "RetrievalResponse",
    "RetrievalWarning",
    "RetrievalWarningCode",
]
