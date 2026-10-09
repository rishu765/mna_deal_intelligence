"""Concrete offline services injected into the orchestration layer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ma_precedent_transactions.extraction import (
    StructuredTransactionService,
    VerifiedTransactionRecord,
)
from ma_precedent_transactions.pipeline import DealResearchPipeline
from ma_precedent_transactions.precedent import PrecedentAnalysisService
from ma_precedent_transactions.precedent.valuation import ValuationExplanationProvider

TransactionPreparer = Callable[
    [dict[str, VerifiedTransactionRecord]], tuple[VerifiedTransactionRecord, ...]
]


@dataclass(frozen=True, slots=True)
class WorkflowServices:
    research: DealResearchPipeline
    extraction: StructuredTransactionService
    precedent: PrecedentAnalysisService
    transaction_preparer: TransactionPreparer
    explanation: ValuationExplanationProvider | None = None
