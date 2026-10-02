"""Provider-neutral models for embedded document chunks."""

from __future__ import annotations

import math
from dataclasses import dataclass

from ma_company_intelligence.domain.chunks import DocumentChunk


@dataclass(frozen=True, slots=True)
class EmbeddingVector:
    """A fixed-dimensional vector plus the model identity that produced it."""

    provider: str
    model: str
    dimension: int
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("embedding provider must not be blank")
        if not self.model.strip():
            raise ValueError("embedding model must not be blank")
        if self.dimension <= 0:
            raise ValueError("embedding dimension must be positive")
        if len(self.values) != self.dimension:
            raise ValueError(
                f"embedding contains {len(self.values)} values; expected {self.dimension}"
            )
        if not all(math.isfinite(value) for value in self.values):
            raise ValueError("embedding values must all be finite")


@dataclass(frozen=True, slots=True)
class VectorRecord:
    """A chunk and its embedding, ready for provider-neutral persistence."""

    record_id: str
    chunk: DocumentChunk
    embedding: EmbeddingVector

    def __post_init__(self) -> None:
        if self.record_id != self.chunk.chunk_id:
            raise ValueError("record_id must equal the stable chunk_id")
