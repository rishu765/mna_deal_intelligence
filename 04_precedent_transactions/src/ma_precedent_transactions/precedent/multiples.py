"""Deterministic transaction-multiple calculation with strict value and period semantics."""

from __future__ import annotations

from dataclasses import dataclass

from ma_precedent_transactions.domain import (
    EstimateStatus,
    FinancialMetric,
    FinancialMetricName,
    FinancialUnit,
    MultipleKind,
    MultipleStatus,
    TransactionMultipleContract,
    TransactionMultipleDefinition,
    ValuationBasis,
    ValuationMeasure,
    ValuationObservation,
)
from ma_precedent_transactions.extraction import VerifiedTransactionRecord, convert_unit
from ma_precedent_transactions.precedent.models import (
    ComparableTransactionDecision,
    SelectionDecision,
    TransactionMultipleResult,
)

DEFINITIONS = (
    TransactionMultipleDefinition(
        MultipleKind.EV_REVENUE,
        ValuationMeasure.TRANSACTION_ENTERPRISE_VALUE,
        FinancialMetricName.REVENUE,
    ),
    TransactionMultipleDefinition(
        MultipleKind.EV_EBITDA,
        ValuationMeasure.TRANSACTION_ENTERPRISE_VALUE,
        FinancialMetricName.EBITDA,
    ),
    TransactionMultipleDefinition(
        MultipleKind.EV_EBIT,
        ValuationMeasure.TRANSACTION_ENTERPRISE_VALUE,
        FinancialMetricName.EBIT,
    ),
    TransactionMultipleDefinition(
        MultipleKind.EQUITY_VALUE_NET_INCOME,
        ValuationMeasure.EQUITY_PURCHASE_PRICE,
        FinancialMetricName.NET_INCOME,
    ),
)


@dataclass(frozen=True, slots=True)
class TransactionMultiplePolicy:
    policy_id: str = "transaction-multiples-v1"
    maximum_financial_age_days: int = 550
    allow_forecast_periods: bool = True

    def __post_init__(self) -> None:
        if self.maximum_financial_age_days < 0:
            raise ValueError("maximum_financial_age_days must be non-negative")


class TransactionMultipleEngine:
    def __init__(self, policy: TransactionMultiplePolicy | None = None) -> None:
        self.policy = policy or TransactionMultiplePolicy()

    def calculate(
        self,
        transaction: VerifiedTransactionRecord,
        decision: ComparableTransactionDecision,
    ) -> tuple[TransactionMultipleResult, ...]:
        results = []
        for definition in DEFINITIONS:
            denominators = tuple(
                item
                for item in transaction.record.target_financials
                if item.name is definition.denominator
            )
            if not denominators:
                results.append(
                    self._missing(transaction, definition, "Required denominator is unavailable.")
                )
                continue
            results.extend(
                self._calculate_one(transaction, decision, definition, item)
                for item in denominators
            )
        return tuple(results)

    def _calculate_one(
        self,
        transaction: VerifiedTransactionRecord,
        decision: ComparableTransactionDecision,
        definition: TransactionMultipleDefinition,
        denominator: FinancialMetric,
    ) -> TransactionMultipleResult:
        transaction_id = transaction.record.identity.transaction_id
        multiple_id = (
            f"multiple:{transaction_id}:{definition.kind.value}:"
            f"{denominator.period.label}:{denominator.basis.value}"
        )
        if decision.decision is not SelectionDecision.INCLUDE:
            return self._excluded(
                transaction,
                definition,
                denominator,
                multiple_id,
                f"Transaction selection decision is {decision.decision.value}.",
                MultipleStatus.EXCLUDED,
            )
        numerator = _numerator(transaction, definition.numerator)
        if numerator is None or numerator.amount is None:
            return self._excluded(
                transaction,
                definition,
                denominator,
                multiple_id,
                "Compatible disclosed or derived numerator is unavailable.",
                MultipleStatus.MISSING_INPUT,
            )
        if _field_conflicting(transaction, definition.numerator):
            return self._excluded(
                transaction,
                definition,
                denominator,
                multiple_id,
                "Numerator has unresolved source conflicts.",
                MultipleStatus.EXCLUDED,
                numerator,
            )
        if _financial_conflicting(transaction, denominator):
            return self._excluded(
                transaction,
                definition,
                denominator,
                multiple_id,
                "Denominator has unresolved source conflicts.",
                MultipleStatus.EXCLUDED,
                numerator,
            )
        if (
            denominator.period.estimate_status is EstimateStatus.FORECAST
            and not self.policy.allow_forecast_periods
        ):
            return self._excluded(
                transaction,
                definition,
                denominator,
                multiple_id,
                "Forecast denominators are disabled by policy.",
                MultipleStatus.EXCLUDED,
                numerator,
            )
        announced = transaction.record.lifecycle.announcement_date
        if announced is not None:
            if denominator.measurement_date > announced:
                return self._excluded(
                    transaction,
                    definition,
                    denominator,
                    multiple_id,
                    "Financial period post-dates transaction announcement.",
                    MultipleStatus.EXCLUDED,
                    numerator,
                )
            age = (announced - denominator.measurement_date).days
            if age > self.policy.maximum_financial_age_days:
                return self._excluded(
                    transaction,
                    definition,
                    denominator,
                    multiple_id,
                    f"Financial denominator is stale by {age} days.",
                    MultipleStatus.EXCLUDED,
                    numerator,
                )
        if denominator.value <= 0:
            return self._excluded(
                transaction,
                definition,
                denominator,
                multiple_id,
                "Zero or negative denominator is not meaningful.",
                MultipleStatus.NOT_MEANINGFUL,
                numerator,
            )
        if numerator.amount.currency != denominator.currency:
            return self._excluded(
                transaction,
                definition,
                denominator,
                multiple_id,
                "Numerator and denominator currencies differ; no FX conversion is configured.",
                MultipleStatus.EXCLUDED,
                numerator,
            )
        if denominator.unit is FinancialUnit.PER_SHARE:
            return self._excluded(
                transaction,
                definition,
                denominator,
                multiple_id,
                "Aggregate transaction value cannot use a per-share denominator.",
                MultipleStatus.EXCLUDED,
                numerator,
            )
        comparable_denominator, _ = convert_unit(
            denominator.value, denominator.unit, numerator.amount.unit
        )
        value = numerator.amount.value / comparable_denominator
        evidence = tuple(dict.fromkeys((*numerator.evidence, *denominator.evidence)))
        trace = (
            f"{definition.kind.value} = {numerator.amount.value} "
            f"{numerator.amount.currency} {numerator.amount.unit.value} / "
            f"{comparable_denominator} {denominator.currency} {numerator.amount.unit.value} "
            f"({denominator.period.label}, {denominator.basis.value}) = {value}",
        )
        contract = TransactionMultipleContract(
            multiple_id,
            transaction_id,
            definition,
            MultipleStatus.INCLUDED,
            numerator.observation_id,
            denominator.metric_id,
            value,
            trace,
        )
        warnings = list(transaction.warnings)
        if numerator.basis.value == "independently_calculated":
            warnings.append("Numerator is derived from disclosed inputs.")
        return TransactionMultipleResult(
            contract,
            numerator.amount.value,
            numerator.amount.currency,
            numerator.amount.unit,
            numerator.basis,
            denominator.value,
            denominator.currency,
            denominator.unit,
            denominator.period,
            denominator.basis,
            evidence,
            tuple(dict.fromkeys(warnings)),
        )

    def _missing(
        self,
        transaction: VerifiedTransactionRecord,
        definition: TransactionMultipleDefinition,
        reason: str,
    ) -> TransactionMultipleResult:
        transaction_id = transaction.record.identity.transaction_id
        contract = TransactionMultipleContract(
            f"multiple:{transaction_id}:{definition.kind.value}:missing",
            transaction_id,
            definition,
            MultipleStatus.MISSING_INPUT,
            treatment_reason=reason,
        )
        return TransactionMultipleResult(
            contract, None, None, None, None, None, None, None, None, None, (), (reason,)
        )

    def _excluded(
        self,
        transaction: VerifiedTransactionRecord,
        definition: TransactionMultipleDefinition,
        denominator: FinancialMetric,
        multiple_id: str,
        reason: str,
        status: MultipleStatus,
        numerator: ValuationObservation | None = None,
    ) -> TransactionMultipleResult:
        amount = None if numerator is None else numerator.amount
        contract = TransactionMultipleContract(
            multiple_id,
            transaction.record.identity.transaction_id,
            definition,
            status,
            None if numerator is None else numerator.observation_id,
            denominator.metric_id,
            calculation_trace=(reason,),
            treatment_reason=reason,
        )
        evidence = tuple(
            dict.fromkeys(
                (
                    *(numerator.evidence if numerator else ()),
                    *denominator.evidence,
                )
            )
        )
        return TransactionMultipleResult(
            contract,
            None if amount is None else amount.value,
            None if amount is None else amount.currency,
            None if amount is None else amount.unit,
            None if numerator is None else numerator.basis,
            denominator.value,
            denominator.currency,
            denominator.unit,
            denominator.period,
            denominator.basis,
            evidence,
            (reason,),
        )


def _numerator(
    transaction: VerifiedTransactionRecord, measure: ValuationMeasure
) -> ValuationObservation | None:
    eligible = [
        item
        for item in transaction.record.valuations
        if item.measure is measure
        and item.amount is not None
        and item.basis
        in {ValuationBasis.EXPLICITLY_DISCLOSED, ValuationBasis.INDEPENDENTLY_CALCULATED}
    ]
    disclosed = [item for item in eligible if item.basis is ValuationBasis.EXPLICITLY_DISCLOSED]
    candidates = disclosed or eligible
    return candidates[0] if candidates else None


def _field_conflicting(transaction: VerifiedTransactionRecord, measure: ValuationMeasure) -> bool:
    field = f"valuation.{measure.value}"
    return any(item.field == field for item in transaction.conflicts)


def _financial_conflicting(
    transaction: VerifiedTransactionRecord, denominator: FinancialMetric
) -> bool:
    prefix = f"financial.{denominator.name.value}."
    return any(item.field.startswith(prefix) for item in transaction.conflicts)
