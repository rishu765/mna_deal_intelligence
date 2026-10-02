"""Canonical representations produced by document ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DocumentSource:
    """Facts about a local source file that are known during ingestion."""

    filename: str
    path: Path
    media_type: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        if not self.filename:
            raise ValueError("filename must not be empty")
        if not self.path.is_absolute():
            raise ValueError("source path must be absolute")
        if self.size_bytes < 0:
            raise ValueError("size_bytes must not be negative")
        if len(self.sha256) != 64:
            raise ValueError("sha256 must be a 64-character hexadecimal digest")
        try:
            int(self.sha256, 16)
        except ValueError as error:
            raise ValueError("sha256 must contain only hexadecimal characters") from error


@dataclass(frozen=True, slots=True)
class SourceProvenance:
    """Location of one parsed page in its source document."""

    document_id: str
    source_filename: str
    source_path: Path
    pdf_page_index: int
    page_number: int
    printed_page_label: str | None = None

    def __post_init__(self) -> None:
        if self.pdf_page_index < 0:
            raise ValueError("pdf_page_index must be zero-based and non-negative")
        if self.page_number != self.pdf_page_index + 1:
            raise ValueError("page_number must equal pdf_page_index + 1")


@dataclass(frozen=True, slots=True)
class ParsedPage:
    """Text and provenance for one physical PDF page."""

    text: str
    provenance: SourceProvenance

    @property
    def page_number(self) -> int:
        """Return the one-based canonical page number."""

        return self.provenance.page_number


class ParsingWarningCode(StrEnum):
    """Stable warning identifiers emitted during parsing."""

    EMPTY_PAGE_TEXT = "empty_page_text"


@dataclass(frozen=True, slots=True)
class ParsingWarning:
    """A recoverable parsing condition that callers should inspect."""

    code: ParsingWarningCode
    message: str
    page_number: int | None = None


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    """Ordered parsed pages plus reliable source-level facts."""

    document_id: str
    source: DocumentSource
    pages: tuple[ParsedPage, ...]
    warnings: tuple[ParsingWarning, ...] = ()

    def __post_init__(self) -> None:
        if self.document_id != f"sha256:{self.source.sha256}":
            raise ValueError("document_id must be derived from the source SHA-256 digest")
        if not self.pages:
            raise ValueError("parsed document must contain at least one page")
        expected_numbers = tuple(range(1, len(self.pages) + 1))
        actual_numbers = tuple(page.page_number for page in self.pages)
        if actual_numbers != expected_numbers:
            raise ValueError("pages must be ordered and numbered consecutively from 1")
        if any(page.provenance.document_id != self.document_id for page in self.pages):
            raise ValueError("every page must reference this document_id")

    @property
    def page_count(self) -> int:
        """Return the number of physical PDF pages."""

        return len(self.pages)
