"""Public semantic retrieval interface."""

from ma_company_intelligence.retrieval.errors import (
    InvalidQueryError,
    QueryVectorError,
    RetrievalError,
    StoredVectorError,
)
from ma_company_intelligence.retrieval.service import SemanticRetriever

__all__ = [
    "InvalidQueryError",
    "QueryVectorError",
    "RetrievalError",
    "SemanticRetriever",
    "StoredVectorError",
]
