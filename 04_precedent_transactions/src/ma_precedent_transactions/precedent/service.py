"""Straight-line M4/5 application service; orchestration remains reserved for M6/7."""

from __future__ import annotations

from ma_precedent_transactions.extraction import VerifiedTransactionRecord
from ma_precedent_transactions.precedent.models import (
    ManualOverride,
    PrecedentValuationOutput,
    TargetComparabilityProfile,
    TargetValuationProfile,
)
from ma_precedent_transactions.precedent.multiples import TransactionMultipleEngine
from ma_precedent_transactions.precedent.selection import ComparableTransactionSelector
from ma_precedent_transactions.precedent.valuation import (
    PrecedentValuationEngine,
    ValuationExplanationProvider,
)


class PrecedentAnalysisService:
    def __init__(
        self,
        selector: ComparableTransactionSelector | None = None,
        multiple_engine: TransactionMultipleEngine | None = None,
        valuation_engine: PrecedentValuationEngine | None = None,
    ) -> None:
        self.selector = selector or ComparableTransactionSelector()
        self.multiple_engine = multiple_engine or TransactionMultipleEngine()
        self.valuation_engine = valuation_engine or PrecedentValuationEngine()

    def analyze(
        self,
        comparable_target: TargetComparabilityProfile,
        valuation_target: TargetValuationProfile,
        transactions: tuple[VerifiedTransactionRecord, ...],
        *,
        overrides: tuple[ManualOverride, ...] = (),
        explanation_provider: ValuationExplanationProvider | None = None,
    ) -> PrecedentValuationOutput:
        selection = self.selector.select(comparable_target, transactions, overrides)
        decision_by_id = {item.transaction_id: item for item in selection.decisions}
        multiples = tuple(
            multiple
            for transaction in transactions
            for multiple in self.multiple_engine.calculate(
                transaction, decision_by_id[transaction.record.identity.transaction_id]
            )
        )
        return self.valuation_engine.build_output(
            valuation_target, selection, multiples, explanation_provider
        )
