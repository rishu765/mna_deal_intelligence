"""Provider boundary for structured extraction over bounded retrieval context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ma_precedent_transactions.extraction.models import ExtractionBatch
from ma_precedent_transactions.retrieval import DealRetrievalResult


@dataclass(frozen=True, slots=True)
class ExtractionRequest:
    transaction_id: str
    evidence: tuple[DealRetrievalResult, ...]


class StructuredTransactionExtractor(Protocol):
    @property
    def provider_name(self) -> str: ...

    def extract(self, request: ExtractionRequest) -> ExtractionBatch: ...
