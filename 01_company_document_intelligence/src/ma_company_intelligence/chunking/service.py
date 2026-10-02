"""Deterministic, provenance-aware character chunking."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from ma_company_intelligence.domain.chunks import (
    ChunkedDocument,
    ChunkPageReference,
    DocumentChunk,
    DocumentMetadata,
)
from ma_company_intelligence.domain.documents import ParsedDocument, ParsedPage

_ALGORITHM_VERSION = "character-v1"


@dataclass(frozen=True, slots=True)
class ChunkingConfig:
    """Character-based chunking limits."""

    max_characters: int = 1_800
    overlap_characters: int = 200
    min_chunk_characters: int = 300

    def __post_init__(self) -> None:
        if self.max_characters <= 0:
            raise ValueError("max_characters must be greater than zero")
        if self.min_chunk_characters <= 0:
            raise ValueError("min_chunk_characters must be greater than zero")
        if self.min_chunk_characters > self.max_characters:
            raise ValueError("min_chunk_characters cannot exceed max_characters")
        if self.overlap_characters < 0:
            raise ValueError("overlap_characters cannot be negative")
        if self.overlap_characters >= self.min_chunk_characters:
            raise ValueError("overlap_characters must be less than min_chunk_characters")


@dataclass(frozen=True, slots=True)
class _PageTextSpan:
    start: int
    end: int
    page: ParsedPage


class ProvenanceAwareChunker:
    """Split parsed documents while retaining all contributing page references."""

    def __init__(self, config: ChunkingConfig | None = None) -> None:
        self.config = config or ChunkingConfig()

    def chunk(
        self,
        document: ParsedDocument,
        metadata: DocumentMetadata | None = None,
    ) -> ChunkedDocument:
        """Return deterministic ordered chunks for ``document``."""

        resolved_metadata = metadata or DocumentMetadata()
        text, page_spans = self._join_nonempty_pages(document.pages)
        chunks: list[DocumentChunk] = []

        for chunk_index, (start, end) in enumerate(self._split_intervals(text)):
            chunk_text = text[start:end]
            page_references = self._page_references(page_spans, start, end)
            chunks.append(
                DocumentChunk(
                    chunk_id=self._make_chunk_id(
                        document.document_id,
                        chunk_index,
                        chunk_text,
                        page_references,
                    ),
                    document_id=document.document_id,
                    chunk_index=chunk_index,
                    text=chunk_text,
                    source=document.source,
                    page_references=page_references,
                    metadata=resolved_metadata,
                )
            )

        return ChunkedDocument(
            document_id=document.document_id,
            source=document.source,
            metadata=resolved_metadata,
            chunks=tuple(chunks),
            parser_warnings=document.warnings,
        )

    @staticmethod
    def _join_nonempty_pages(
        pages: tuple[ParsedPage, ...],
    ) -> tuple[str, tuple[_PageTextSpan, ...]]:
        parts: list[str] = []
        spans: list[_PageTextSpan] = []
        cursor = 0

        for page in pages:
            if not page.text.strip():
                continue
            if parts:
                separator = "\n\n"
                parts.append(separator)
                cursor += len(separator)

            start = cursor
            parts.append(page.text)
            cursor += len(page.text)
            spans.append(_PageTextSpan(start=start, end=cursor, page=page))

        return "".join(parts), tuple(spans)

    def _split_intervals(self, text: str) -> tuple[tuple[int, int], ...]:
        if not text:
            return ()

        intervals: list[tuple[int, int]] = []
        start = 0
        while start < len(text):
            hard_end = min(start + self.config.max_characters, len(text))
            if hard_end == len(text):
                end = hard_end
            else:
                end = self._preferred_boundary(text, start, hard_end)
                trailing_characters = len(text) - end
                if 0 < trailing_characters < self.config.min_chunk_characters:
                    tail_balanced_end = len(text) - self.config.min_chunk_characters
                    if tail_balanced_end > start:
                        end = tail_balanced_end

            intervals.append((start, end))
            if end == len(text):
                break
            start = end - self.config.overlap_characters

        return tuple(intervals)

    def _preferred_boundary(self, text: str, start: int, hard_end: int) -> int:
        earliest = start + self.config.min_chunk_characters
        for delimiter in ("\n\n", "\n", " "):
            position = text.rfind(delimiter, earliest, hard_end)
            if position >= earliest:
                return position + len(delimiter)
        return hard_end

    @staticmethod
    def _page_references(
        page_spans: tuple[_PageTextSpan, ...],
        chunk_start: int,
        chunk_end: int,
    ) -> tuple[ChunkPageReference, ...]:
        references: list[ChunkPageReference] = []
        for span in page_spans:
            if chunk_start < span.end and chunk_end > span.start:
                provenance = span.page.provenance
                references.append(
                    ChunkPageReference(
                        pdf_page_index=provenance.pdf_page_index,
                        page_number=provenance.page_number,
                        printed_page_label=provenance.printed_page_label,
                    )
                )
        return tuple(references)

    def _make_chunk_id(
        self,
        document_id: str,
        chunk_index: int,
        text: str,
        page_references: tuple[ChunkPageReference, ...],
    ) -> str:
        page_indexes = ",".join(str(ref.pdf_page_index) for ref in page_references)
        identity = "\0".join(
            (
                _ALGORITHM_VERSION,
                document_id,
                str(self.config.max_characters),
                str(self.config.overlap_characters),
                str(self.config.min_chunk_characters),
                str(chunk_index),
                page_indexes,
                text,
            )
        )
        return f"sha256:{sha256(identity.encode('utf-8')).hexdigest()}"


def chunk_document(
    document: ParsedDocument,
    metadata: DocumentMetadata | None = None,
    config: ChunkingConfig | None = None,
) -> ChunkedDocument:
    """Convenience entry point for provenance-aware document chunking."""

    return ProvenanceAwareChunker(config).chunk(document, metadata)
