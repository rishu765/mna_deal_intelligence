"""Deterministic transaction-aware character chunking."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from ma_precedent_transactions.discovery.models import CandidateTransaction
from ma_precedent_transactions.documents.models import (
    ChunkedDealDocument,
    DealDocumentChunk,
    ParsedDealDocument,
)


@dataclass(frozen=True, slots=True)
class DealChunkingConfig:
    max_characters: int = 900
    overlap_characters: int = 100
    min_chunk_characters: int = 120

    def __post_init__(self) -> None:
        if self.max_characters <= 0 or self.min_chunk_characters <= 0:
            raise ValueError("chunk sizes must be positive")
        if self.min_chunk_characters > self.max_characters:
            raise ValueError("min_chunk_characters cannot exceed max_characters")
        if not 0 <= self.overlap_characters < self.min_chunk_characters:
            raise ValueError("overlap must be non-negative and smaller than minimum chunk size")


class TransactionAwareChunker:
    def __init__(self, config: DealChunkingConfig | None = None) -> None:
        self.config = config or DealChunkingConfig()

    def chunk(
        self, document: ParsedDealDocument, transaction: CandidateTransaction
    ) -> ChunkedDealDocument:
        if document.source.transaction_id != transaction.candidate_id:
            raise ValueError("document source and transaction IDs must match")
        chunks: list[DealDocumentChunk] = []
        for page in document.pages:
            for start, end in self._intervals(page.text):
                text = page.text[start:end]
                chunk_index = len(chunks)
                identity = "\0".join(
                    (
                        "deal-character-v1",
                        document.document_id,
                        str(chunk_index),
                        str(page.page_number),
                        text,
                    )
                )
                chunks.append(
                    DealDocumentChunk(
                        chunk_id=f"sha256:{sha256(identity.encode()).hexdigest()}",
                        transaction_id=transaction.candidate_id,
                        document_id=document.document_id,
                        chunk_index=chunk_index,
                        text=text,
                        source=document.source,
                        page_numbers=(page.page_number,),
                        section=page.section,
                        acquirer_name=transaction.acquirer_name,
                        target_name=transaction.target_name,
                    )
                )
        return ChunkedDealDocument(
            document.document_id,
            document.source,
            tuple(chunks),
            document.warnings,
        )

    def _intervals(self, text: str) -> tuple[tuple[int, int], ...]:
        intervals = []
        start = 0
        while start < len(text):
            hard_end = min(start + self.config.max_characters, len(text))
            end = hard_end if hard_end == len(text) else self._boundary(text, start, hard_end)
            intervals.append((start, end))
            if end == len(text):
                break
            start = end - self.config.overlap_characters
        return tuple(intervals)

    def _boundary(self, text: str, start: int, hard_end: int) -> int:
        earliest = start + self.config.min_chunk_characters
        for delimiter in ("\n\n", "\n", ". ", " "):
            position = text.rfind(delimiter, earliest, hard_end)
            if position >= earliest:
                return position + len(delimiter)
        return hard_end
