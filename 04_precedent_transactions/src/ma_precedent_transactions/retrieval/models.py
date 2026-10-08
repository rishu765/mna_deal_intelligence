"""Structured, provenance-complete retrieval contracts."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from ma_precedent_transactions.documents.models import (
    DealDocumentChunk,
    DealSourceType,
    DocumentFormat,
)
from ma_precedent_transactions.domain import EvidenceReference, ExtractionMethod
from ma_precedent_transactions.errors import DomainValidationError


@dataclass(frozen=True, slots=True)
class RetrievalFilters:
    transaction_id: str | None = None
    source_types: tuple[DealSourceType, ...] = ()
    published_from: date | None = None
    published_to: date | None = None
    acquirer: str | None = None
    target: str | None = None
    jurisdiction: str | None = None
    document_formats: tuple[DocumentFormat, ...] = ()

    def __post_init__(self) -> None:
        if self.published_from and self.published_to and self.published_from > self.published_to:
            raise DomainValidationError("published_from must not follow published_to")
        for name in ("transaction_id", "acquirer", "target", "jurisdiction"):
            value = getattr(self, name)
            if value is not None and not value.strip():
                raise DomainValidationError(f"{name} must not be blank")

    def matches(self, chunk: DealDocumentChunk) -> bool:
        published = chunk.source.publication_date
        return (
            (self.transaction_id is None or chunk.transaction_id == self.transaction_id)
            and (not self.source_types or chunk.source.source_type in self.source_types)
            and (
                self.published_from is None
                or (published is not None and published >= self.published_from)
            )
            and (
                self.published_to is None
                or (published is not None and published <= self.published_to)
            )
            and (
                self.acquirer is None or self.acquirer.casefold() in chunk.acquirer_name.casefold()
            )
            and (self.target is None or self.target.casefold() in chunk.target_name.casefold())
            and (
                self.jurisdiction is None
                or (
                    chunk.source.jurisdiction is not None
                    and self.jurisdiction.casefold() in chunk.source.jurisdiction.casefold()
                )
            )
            and (not self.document_formats or chunk.source.document_format in self.document_formats)
        )


@dataclass(frozen=True, slots=True)
class ChannelMatch:
    chunk: DealDocumentChunk
    score: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.score):
            raise DomainValidationError("channel score must be finite")


class RetrievalWarningCode(StrEnum):
    NO_RESULTS = "no_results"
    LOW_SCORE_RESULTS = "low_score_results"
    NO_SEMANTIC_RESULTS = "no_semantic_results"
    NO_LEXICAL_RESULTS = "no_lexical_results"
    UNOFFICIAL_SOURCES_ONLY = "unofficial_sources_only"
    CONFLICTING_PASSAGES = "conflicting_passages"


@dataclass(frozen=True, slots=True)
class RetrievalWarning:
    code: RetrievalWarningCode
    message: str


@dataclass(frozen=True, slots=True)
class DealRetrievalResult:
    query: str
    rank: int
    transaction_id: str
    chunk_id: str
    semantic_score: float
    lexical_score: float
    fused_score: float
    evidence: EvidenceReference
    text: str
    source_type: DealSourceType
    document_format: DocumentFormat
    official_source: bool

    def __post_init__(self) -> None:
        if not self.query.strip() or not self.text.strip():
            raise DomainValidationError("retrieval query and text must not be blank")
        if self.rank < 1:
            raise DomainValidationError("retrieval rank must be positive")
        for name in ("semantic_score", "lexical_score", "fused_score"):
            if not math.isfinite(getattr(self, name)):
                raise DomainValidationError(f"{name} must be finite")


@dataclass(frozen=True, slots=True)
class RetrievalResponse:
    query: str
    results: tuple[DealRetrievalResult, ...]
    warnings: tuple[RetrievalWarning, ...] = ()


def evidence_from_chunk(chunk: DealDocumentChunk) -> EvidenceReference:
    source = chunk.source
    return EvidenceReference(
        evidence_id=f"retrieval:{chunk.chunk_id}",
        source_type=source.source_type.value,
        document_title=source.title,
        source_url=source.location,
        publisher=source.publisher,
        publication_date=source.publication_date,
        retrieved_at=source.retrieved_at,
        reliability=source.reliability,
        extraction_method=ExtractionMethod.RULE_BASED,
        document_id=chunk.document_id,
        page=chunk.page_numbers[0],
        section=chunk.section,
        chunk_id=chunk.chunk_id,
        text_location=f"chunk {chunk.chunk_index + 1}",
        excerpt_id=chunk.chunk_id,
        excerpt=chunk.text,
    )
