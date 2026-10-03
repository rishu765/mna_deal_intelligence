"""Provider-neutral citation models for evidence-backed research."""

from __future__ import annotations

from dataclasses import dataclass, field

from ma_company_intelligence.domain.chunks import DocumentMetadata


@dataclass(frozen=True, slots=True)
class Citation:
    """One stable reference from generated content to a source chunk."""

    reference_number: int
    chunk_id: str
    document_id: str
    source_filename: str
    source_title: str | None
    canonical_page_numbers: tuple[int, ...]
    physical_pdf_page_indexes: tuple[int, ...]
    printed_page_labels: tuple[str | None, ...]
    excerpt: str
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)

    def __post_init__(self) -> None:
        if self.reference_number < 1:
            raise ValueError("citation reference_number must be positive")
        for field_name in ("chunk_id", "document_id", "source_filename", "excerpt"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"citation {field_name} must not be blank")
        if self.source_title is not None and not self.source_title.strip():
            raise ValueError("citation source_title must be non-blank when supplied")
        if any(page < 1 for page in self.canonical_page_numbers):
            raise ValueError("canonical page numbers must be positive")
        if any(index < 0 for index in self.physical_pdf_page_indexes):
            raise ValueError("physical PDF page indexes must be non-negative")
        page_count = len(self.canonical_page_numbers)
        if self.physical_pdf_page_indexes and len(self.physical_pdf_page_indexes) != page_count:
            raise ValueError("physical page indexes must align with canonical page numbers")
        if self.printed_page_labels and len(self.printed_page_labels) != page_count:
            raise ValueError("printed page labels must align with canonical page numbers")

    @property
    def citation_id(self) -> str:
        return str(self.reference_number)

    @property
    def marker(self) -> str:
        return f"[{self.reference_number}]"

    @property
    def source_display_name(self) -> str:
        return self.source_title or self.source_filename

    def format_reference(self) -> str:
        """Return a deterministic analyst-facing source reference."""

        return f"{self.marker} {self.source_display_name} — {self._format_pages()}"

    def _format_pages(self) -> str:
        pages = self.canonical_page_numbers
        if not pages:
            return "page unavailable"
        if len(pages) == 1:
            return f"p. {pages[0]}"
        if pages == tuple(range(pages[0], pages[-1] + 1)):
            return f"pp. {pages[0]}–{pages[-1]}"
        return "pp. " + ", ".join(str(page) for page in pages)
