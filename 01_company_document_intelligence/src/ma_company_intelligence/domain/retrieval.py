"""Provider-neutral models for vector search and semantic retrieval."""

from __future__ import annotations

import math
from dataclasses import dataclass

from ma_company_intelligence.domain.chunks import DocumentChunk
from ma_company_intelligence.domain.vectors import VectorRecord


@dataclass(frozen=True, slots=True)
class RetrievalFilters:
    """Optional exact-match filters over metadata that M2/M3 actually store."""

    document_id: str | None = None
    source_filename: str | None = None
    company: str | None = None
    document_type: str | None = None
    fiscal_year: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("document_id", "source_filename", "company", "document_type"):
            value = getattr(self, field_name)
            if value is not None and not value.strip():
                raise ValueError(f"{field_name} must be non-blank when supplied")
        if self.fiscal_year is not None and not 1000 <= self.fiscal_year <= 9999:
            raise ValueError("fiscal_year must be a four-digit year when supplied")

    def matches(self, chunk: DocumentChunk) -> bool:
        """Return whether a chunk satisfies every supplied exact-match filter."""

        return (
            (self.document_id is None or chunk.document_id == self.document_id)
            and (
                self.source_filename is None
                or chunk.source.filename == self.source_filename
            )
            and (self.company is None or chunk.metadata.company == self.company)
            and (
                self.document_type is None
                or chunk.metadata.document_type == self.document_type
            )
            and (
                self.fiscal_year is None
                or chunk.metadata.fiscal_year == self.fiscal_year
            )
        )


@dataclass(frozen=True, slots=True)
class VectorSearchMatch:
    """A persisted vector record and its provider-neutral similarity score."""

    record: VectorRecord
    score: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.score):
            raise ValueError("vector-search score must be finite")
        if not -1.0 <= self.score <= 1.0:
            raise ValueError("cosine-similarity score must be between -1 and 1")


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """A ranked evidence chunk returned by semantic retrieval."""

    rank: int
    score: float
    chunk: DocumentChunk

    def __post_init__(self) -> None:
        if self.rank < 1:
            raise ValueError("retrieval rank must be one-based and positive")
        if not math.isfinite(self.score) or not -1.0 <= self.score <= 1.0:
            raise ValueError("retrieval score must be finite and between -1 and 1")

    @property
    def chunk_id(self) -> str:
        return self.chunk.chunk_id

    @property
    def document_id(self) -> str:
        return self.chunk.document_id

    @property
    def text(self) -> str:
        return self.chunk.text
