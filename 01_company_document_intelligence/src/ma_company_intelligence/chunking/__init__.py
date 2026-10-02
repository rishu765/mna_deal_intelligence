"""Public interface for document chunking."""

from ma_company_intelligence.chunking.service import (
    ChunkingConfig,
    ProvenanceAwareChunker,
    chunk_document,
)

__all__ = ["ChunkingConfig", "ProvenanceAwareChunker", "chunk_document"]
