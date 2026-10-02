"""Provider-neutral domain models for retrieval-ready document chunks."""

from __future__ import annotations

from dataclasses import dataclass, field

from ma_company_intelligence.domain.documents import DocumentSource, ParsingWarning


def _validate_optional_text(field_name: str, value: str | None) -> None:
    if value is not None and not value.strip():
        raise ValueError(f"{field_name} must be non-blank when supplied")


@dataclass(frozen=True, slots=True)
class DocumentMetadata:
    """Optional research metadata supplied by a trusted external source.

    None means that the value is unknown. The ingestion and chunking layers do
    not infer these fields from filenames or extracted text.
    """

    company: str | None = None
    document_title: str | None = None
    document_type: str | None = None
    fiscal_year: int | None = None
    reporting_period: str | None = None
    source_url: str | None = None
    filing_type: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "company",
            "document_title",
            "document_type",
            "reporting_period",
            "source_url",
            "filing_type",
        ):
            _validate_optional_text(field_name, getattr(self, field_name))

        if self.fiscal_year is not None and not 1000 <= self.fiscal_year <= 9999:
            raise ValueError("fiscal_year must be a four-digit year when supplied")


@dataclass(frozen=True, slots=True)
class ChunkPageReference:
    """A page that contributed source text to a chunk."""

    pdf_page_index: int
    page_number: int
    printed_page_label: str | None = None

    def __post_init__(self) -> None:
        if self.pdf_page_index < 0:
            raise ValueError("pdf_page_index must be zero-based and non-negative")
        if self.page_number != self.pdf_page_index + 1:
            raise ValueError("page_number must equal pdf_page_index + 1")
        _validate_optional_text("printed_page_label", self.printed_page_label)


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    """An ordered text unit ready for embedding in a later milestone."""

    chunk_id: str
    document_id: str
    chunk_index: int
    text: str
    source: DocumentSource
    page_references: tuple[ChunkPageReference, ...]
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)
    section: str | None = None

    def __post_init__(self) -> None:
        if not self.chunk_id:
            raise ValueError("chunk_id must not be empty")
        if not self.document_id:
            raise ValueError("document_id must not be empty")
        if self.chunk_index < 0:
            raise ValueError("chunk_index must be zero-based and non-negative")
        if not self.text.strip():
            raise ValueError("chunk text must contain non-whitespace content")
        if not self.page_references:
            raise ValueError("a chunk must reference at least one contributing page")

        page_indexes = tuple(ref.pdf_page_index for ref in self.page_references)
        if page_indexes != tuple(sorted(set(page_indexes))):
            raise ValueError("page_references must be unique and in physical page order")
        _validate_optional_text("section", self.section)

    @property
    def chunk_number(self) -> int:
        """Return a one-based chunk number for human-facing displays."""

        return self.chunk_index + 1

    @property
    def character_count(self) -> int:
        return len(self.text)

    @property
    def page_numbers(self) -> tuple[int, ...]:
        return tuple(ref.page_number for ref in self.page_references)


@dataclass(frozen=True, slots=True)
class ChunkedDocument:
    """Ordered chunk output plus document metadata and parser warnings."""

    document_id: str
    source: DocumentSource
    metadata: DocumentMetadata
    chunks: tuple[DocumentChunk, ...]
    parser_warnings: tuple[ParsingWarning, ...] = ()

    def __post_init__(self) -> None:
        expected_indexes = tuple(range(len(self.chunks)))
        actual_indexes = tuple(chunk.chunk_index for chunk in self.chunks)
        if actual_indexes != expected_indexes:
            raise ValueError("chunks must be ordered with contiguous zero-based indexes")

        for chunk in self.chunks:
            if chunk.document_id != self.document_id:
                raise ValueError("all chunks must belong to this document")
            if chunk.source != self.source:
                raise ValueError("all chunks must retain this document's source")
            if chunk.metadata != self.metadata:
                raise ValueError("all chunks must retain this document's metadata")
