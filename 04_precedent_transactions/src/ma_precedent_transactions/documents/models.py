"""Transaction-aware document, page, and chunk contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from ma_precedent_transactions.domain import SourceReliability
from ma_precedent_transactions.errors import DomainValidationError


def _text(value: str, name: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise DomainValidationError(f"{name} must not be blank")
    return normalized


class DealSourceType(StrEnum):
    ACQUISITION_PRESS_RELEASE = "acquisition_press_release"
    REGULATORY_FILING = "regulatory_filing"
    MERGER_AGREEMENT = "merger_agreement"
    ANNUAL_REPORT = "annual_report"
    INVESTOR_PRESENTATION = "investor_presentation"
    EXCHANGE_DISCLOSURE = "exchange_disclosure"
    OFFICIAL_ANNOUNCEMENT = "official_announcement"
    FINANCIAL_NEWS = "financial_news"
    OTHER = "other"


class DocumentFormat(StrEnum):
    PDF = "pdf"
    HTML = "html"
    TEXT = "text"


@dataclass(frozen=True, slots=True)
class DealDocumentSource:
    source_id: str
    transaction_id: str
    source_type: DealSourceType
    title: str
    location: str
    publisher: str
    publication_date: date | None
    jurisdiction: str | None
    document_format: DocumentFormat
    retrieved_at: datetime
    reliability: SourceReliability
    official_source: bool
    checksum_sha256: str | None = None

    def __post_init__(self) -> None:
        for name in ("source_id", "transaction_id", "title", "location", "publisher"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        if self.jurisdiction is not None:
            object.__setattr__(self, "jurisdiction", _text(self.jurisdiction, "jurisdiction"))
        if self.retrieved_at.tzinfo is None or self.retrieved_at.utcoffset() is None:
            raise DomainValidationError("retrieved_at must be timezone-aware")
        if self.checksum_sha256 is not None:
            checksum = self.checksum_sha256.casefold()
            if len(checksum) != 64:
                raise DomainValidationError("checksum_sha256 must have 64 hexadecimal characters")
            try:
                int(checksum, 16)
            except ValueError as error:
                raise DomainValidationError("checksum_sha256 must be hexadecimal") from error
            object.__setattr__(self, "checksum_sha256", checksum)


@dataclass(frozen=True, slots=True)
class ParsedDealPage:
    page_number: int
    text: str
    section: str | None = None

    def __post_init__(self) -> None:
        if self.page_number < 1:
            raise DomainValidationError("page_number must be positive")
        if not self.text.strip():
            raise DomainValidationError("parsed page text must not be blank")
        if self.section is not None:
            object.__setattr__(self, "section", _text(self.section, "section"))


@dataclass(frozen=True, slots=True)
class ParsedDealDocument:
    document_id: str
    source: DealDocumentSource
    pages: tuple[ParsedDealPage, ...]
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "document_id", _text(self.document_id, "document_id"))
        if not self.pages:
            raise DomainValidationError("parsed documents require at least one page")
        if tuple(page.page_number for page in self.pages) != tuple(range(1, len(self.pages) + 1)):
            raise DomainValidationError("parsed pages must be consecutive and one-based")


@dataclass(frozen=True, slots=True)
class DealDocumentChunk:
    chunk_id: str
    transaction_id: str
    document_id: str
    chunk_index: int
    text: str
    source: DealDocumentSource
    page_numbers: tuple[int, ...]
    section: str | None
    acquirer_name: str
    target_name: str

    def __post_init__(self) -> None:
        for name in (
            "chunk_id",
            "transaction_id",
            "document_id",
            "acquirer_name",
            "target_name",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        if self.chunk_index < 0:
            raise DomainValidationError("chunk_index must be non-negative")
        if not self.text.strip():
            raise DomainValidationError("chunk text must not be blank")
        if not self.page_numbers or any(page < 1 for page in self.page_numbers):
            raise DomainValidationError("chunks require positive page numbers")
        if tuple(sorted(set(self.page_numbers))) != self.page_numbers:
            raise DomainValidationError("page_numbers must be unique and ordered")
        if self.transaction_id != self.source.transaction_id:
            raise DomainValidationError("chunk and source transaction IDs must match")
        if self.section is not None:
            object.__setattr__(self, "section", _text(self.section, "section"))


@dataclass(frozen=True, slots=True)
class ChunkedDealDocument:
    document_id: str
    source: DealDocumentSource
    chunks: tuple[DealDocumentChunk, ...]
    parser_warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if tuple(chunk.chunk_index for chunk in self.chunks) != tuple(range(len(self.chunks))):
            raise DomainValidationError("chunks must have contiguous zero-based indexes")
        if any(chunk.document_id != self.document_id for chunk in self.chunks):
            raise DomainValidationError("all chunks must belong to the document")
