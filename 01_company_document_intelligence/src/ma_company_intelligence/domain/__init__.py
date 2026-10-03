"""Provider-neutral document and chunk models."""

from ma_company_intelligence.domain.answers import RAGAnswer
from ma_company_intelligence.domain.chunks import (
    ChunkedDocument,
    ChunkPageReference,
    DocumentChunk,
    DocumentMetadata,
)
from ma_company_intelligence.domain.documents import (
    DocumentSource,
    ParsedDocument,
    ParsedPage,
    ParsingWarning,
    ParsingWarningCode,
    SourceProvenance,
)
from ma_company_intelligence.domain.retrieval import (
    RetrievalFilters,
    RetrievalResult,
    VectorSearchMatch,
)
from ma_company_intelligence.domain.vectors import EmbeddingVector, VectorRecord

__all__ = [
    "ChunkedDocument",
    "ChunkPageReference",
    "DocumentChunk",
    "DocumentMetadata",
    "DocumentSource",
    "EmbeddingVector",
    "ParsedDocument",
    "ParsedPage",
    "ParsingWarning",
    "ParsingWarningCode",
    "RetrievalFilters",
    "RetrievalResult",
    "RAGAnswer",
    "SourceProvenance",
    "VectorRecord",
    "VectorSearchMatch",
]
