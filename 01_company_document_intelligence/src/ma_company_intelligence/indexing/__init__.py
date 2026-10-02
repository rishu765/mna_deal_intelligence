"""Vector indexing interfaces and local persistence."""

from ma_company_intelligence.indexing.base import VectorStore
from ma_company_intelligence.indexing.errors import (
    DuplicateChunkError,
    IndexCompatibilityError,
    IndexingError,
    InvalidChunkError,
    VectorDimensionError,
    VectorStoreError,
)
from ma_company_intelligence.indexing.service import ChunkIndexingService, IndexingReport
from ma_company_intelligence.indexing.sqlite_store import SQLiteVectorStore

__all__ = [
    "ChunkIndexingService",
    "DuplicateChunkError",
    "IndexCompatibilityError",
    "IndexingError",
    "IndexingReport",
    "InvalidChunkError",
    "SQLiteVectorStore",
    "VectorDimensionError",
    "VectorStore",
    "VectorStoreError",
]
