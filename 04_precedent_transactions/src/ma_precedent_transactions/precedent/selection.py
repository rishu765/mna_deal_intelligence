"""Deterministic eligibility plus provider-neutral soft comparability assessment."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from ma_precedent_transactions.domain import (
    DealStatus,
    FinancialMetricName,
    TransactionType,
    ValuationBasis,
    ValuationMeasure,
)
from ma_precedent_transactions.extraction import VerifiedTransactionRecord, convert_unit
from ma_precedent_transactions.precedent.models import (
    ComparableTransactionDecision,
    ComparableTransactionSet,
    CriterionAssessment,
    CriterionMode,
    CriterionOutcome,
    ManualOverride,
    MinorityTreatment,
    OverrideAction,
    PrecedentSelectionPolicy,
    SelectionDecision,
    TargetComparabilityProfile,
)


class SoftComparabilityProvider(Protocol):
    def assess(
        self, target: TargetComparabilityProfile, transaction: VerifiedTransactionRecord
    ) -> tuple[CriterionAssessment, ...]: ...


@dataclass(frozen=True, slots=True)
class DeterministicFixtureComparabilityProvider:
    """Offline semantic stand-in using transparent token overlap."""

    def assess(
        self, target: TargetComparabilityProfile, transaction: VerifiedTransactionRecord
    ) -> tuple[CriterionAssessment, ...]:
        record = transaction.record
        target_text = " ".join((target.industry, target.business_model, *target.products))
        deal_text = " ".join(
            value or ""
            for value in (
                record.target.industry,
                record.target.business_description,
                record.structure.description,
            )
        )
        similarity = _jaccard(target_text, deal_text)
        business = CriterionAssessment(
            "business_model_product_similarity",
            CriterionMode.SOFT,
            CriterionOutcome.PASS if similarity >= Decimal("0.15") else CriterionOutcome.FAIL,
            f"Deterministic fixture token overlap is {similarity}.",
            similarity,
            evidence_ids=tuple(item.evidence_id for item in record.evidence),
        )
        geography_match = any(
            geography.casefold() == (record.structure.jurisdiction or "").casefold()
            for geography in target.geographies
        )
        geography = CriterionAssessment(
            "geography",
            CriterionMode.SOFT,
            CriterionOutcome.PASS if geography_match else CriterionOutcome.FAIL,
            "Transaction jurisdiction is within the target comparison geography."
            if geography_match
            else "Transaction jurisdiction is outside the target comparison geography.",
            Decimal("1") if geography_match else Decimal("0"),
        )
        buyer = CriterionAssessment(
            "buyer_type",
            CriterionMode.SOFT,
            CriterionOutcome.PASS,
            f"Buyer type retained as {record.structure.buyer_type.value}; no premium is assumed.",
            Decimal("0.5"),
        )
        return business, geography, buyer


class ComparableTransactionSelector:
    def __init__(
        self,
        policy: PrecedentSelectionPolicy | None = None,
        soft_provider: SoftComparabilityProvider | None = None,
    ) -> None:
        self.policy = policy or PrecedentSelectionPolicy()
        self.soft_provider = soft_provider or DeterministicFixtureComparabilityProvider()

    def select(
        self,
        target: TargetComparabilityProfile,
        transactions: tuple[VerifiedTransactionRecord, ...],
        overrides: tuple[ManualOverride, ...] = (),
    ) -> ComparableTransactionSet:
        override_by_id = {item.transaction_id: item for item in overrides}
        if len(override_by_id) != len(overrides):
            raise ValueError("only one manual override is allowed per transaction")
        decisions = tuple(
            self._assess(target, item, override_by_id.get(item.record.identity.transaction_id))
            for item in transactions
        )
        return ComparableTransactionSet(
            f"precedent-set:{target.target_id}:{self.policy.policy_id}",
            self.policy.policy_id,
            decisions,
            tuple(
                item.transaction_id
                for item in decisions
                if item.decision is SelectionDecision.INCLUDE
            ),
            tuple(
                item.transaction_id
                for item in decisions
                if item.decision is SelectionDecision.SEPARATE
            ),
            tuple(
                f"{item.transaction_id}: {warning}"
                for item in decisions
                for warning in item.warnings
            ),
        )

    def _assess(
        self,
        target: TargetComparabilityProfile,
        transaction: VerifiedTransactionRecord,
        override: ManualOverride | None,
    ) -> ComparableTransactionDecision:
        record = transaction.record
        transaction_id = record.identity.transaction_id
        hard: list[CriterionAssessment] = []
        hard.append(
            _hard(
                "status",
                not self.policy.require_completed
                or record.lifecycle.status is DealStatus.COMPLETED,
                f"Transaction status is {record.lifecycle.status.value}.",
            )
        )
        announced = record.lifecycle.announcement_date
        in_window = announced is not None and announced <= self.policy.as_of
        if announced is not None and self.policy.announced_from is not None:
            in_window = in_window and announced >= self.policy.announced_from
        if announced is not None and self.policy.announced_to is not None:
            in_window = in_window and announced <= self.policy.announced_to
        hard.append(_hard("announcement_window", in_window, f"Announcement date is {announced}."))
        eligible_type = record.structure.transaction_type in self.policy.eligible_transaction_types
        hard.append(
            _hard(
                "transaction_type",
                eligible_type,
                f"Transaction type is {record.structure.transaction_type.value}.",
            )
        )
        minority = _is_minority(transaction)
        minority_failed = minority and self.policy.minority_treatment is MinorityTreatment.EXCLUDE
        hard.append(
            _hard(
                "ownership_control",
                not minority_failed,
                "Minority or partial-stake transaction."
                if minority
                else "Transaction is treated as a control acquisition.",
            )
        )
        usable_value = any(
            item.amount is not None
            and item.basis
            in {ValuationBasis.EXPLICITLY_DISCLOSED, ValuationBasis.INDEPENDENTLY_CALCULATED}
            and item.measure
            in {
                ValuationMeasure.TRANSACTION_ENTERPRISE_VALUE,
                ValuationMeasure.EQUITY_PURCHASE_PRICE,
            }
            for item in record.valuations
        )
        hard.append(
            _hard(
                "usable_transaction_value",
                usable_value or not self.policy.require_usable_value,
                "Compatible EV or equity value is available."
                if usable_value
                else "No compatible EV or equity value is available.",
            )
        )
        hard.extend(self._size_assessment(target, transaction))
        soft = self.soft_provider.assess(target, transaction)
        scores = [item.score for item in soft if item.score is not None]
        soft_score = sum(scores, Decimal("0")) / Decimal(len(scores)) if scores else None
        hard_failed = any(item.outcome is CriterionOutcome.FAIL for item in hard)
        missing = tuple(value for item in (*hard, *soft) for value in item.missing_information)
        warnings = list(transaction.warnings)
        if transaction.conflicts:
            warnings.append("M3 source conflicts remain attached to this transaction.")
        if minority and self.policy.minority_treatment is MinorityTreatment.SEPARATE:
            decision = SelectionDecision.SEPARATE
        elif minority and self.policy.minority_treatment is MinorityTreatment.LOW_COMPARABILITY:
            decision = SelectionDecision.REVIEW
            warnings.append("Minority transaction retained only as a low-comparability candidate.")
        elif hard_failed:
            decision = SelectionDecision.EXCLUDE
        elif soft_score is None or soft_score < self.policy.minimum_soft_score:
            decision = SelectionDecision.REVIEW
        else:
            decision = SelectionDecision.INCLUDE
        if override is not None:
            decision = (
                SelectionDecision.INCLUDE
                if override.action is OverrideAction.FORCE_INCLUDE
                else SelectionDecision.EXCLUDE
            )
            warnings.append(f"Manual {override.action.value} applied by {override.actor}.")
        rationale = _rationale(decision, hard, soft, override)
        return ComparableTransactionDecision(
            transaction_id,
            decision,
            (*hard, *soft),
            rationale,
            soft_score,
            record.evidence,
            missing,
            tuple(dict.fromkeys(warnings)),
            override,
        )

    def _size_assessment(
        self, target: TargetComparabilityProfile, transaction: VerifiedTransactionRecord
    ) -> tuple[CriterionAssessment, ...]:
        target_revenue = target.revenue
        deal_revenue = next(
            (
                item
                for item in transaction.record.target_financials
                if item.name is FinancialMetricName.REVENUE
            ),
            None,
        )
        if target_revenue is None or deal_revenue is None:
            return (
                CriterionAssessment(
                    "revenue_size",
                    CriterionMode.HARD,
                    CriterionOutcome.UNKNOWN,
                    "Revenue size could not be compared.",
                    missing_information=("target or transaction revenue",),
                ),
            )
        if target_revenue.currency != deal_revenue.currency:
            return (
                CriterionAssessment(
                    "revenue_size",
                    CriterionMode.HARD,
                    CriterionOutcome.UNKNOWN,
                    "Revenue currencies differ and no FX policy is configured.",
                    missing_information=("compatible revenue currency",),
                ),
            )
        target_value, _ = convert_unit(target_revenue.value, target_revenue.unit, deal_revenue.unit)
        ratio = deal_revenue.value / target_value
        passes = self.policy.min_revenue_ratio <= ratio <= self.policy.max_revenue_ratio
        return (
            _hard("revenue_size", passes, f"Transaction target/target revenue ratio is {ratio}."),
        )


def _hard(name: str, passes: bool, rationale: str) -> CriterionAssessment:
    return CriterionAssessment(
        name,
        CriterionMode.HARD,
        CriterionOutcome.PASS if passes else CriterionOutcome.FAIL,
        rationale,
    )


def _is_minority(transaction: VerifiedTransactionRecord) -> bool:
    record = transaction.record
    if record.structure.transaction_type is TransactionType.MINORITY_INVESTMENT:
        return True
    return any(
        item.acquired_percent is not None and item.acquired_percent < Decimal("50")
        for item in record.ownership
    )


def _rationale(
    decision: SelectionDecision,
    hard: list[CriterionAssessment],
    soft: tuple[CriterionAssessment, ...],
    override: ManualOverride | None,
) -> str:
    if override is not None:
        return f"{override.action.value} override: {override.rationale}"
    failures = [item.criterion for item in hard if item.outcome is CriterionOutcome.FAIL]
    if failures:
        return "Excluded by hard criteria: " + ", ".join(failures) + "."
    return (
        f"{decision.value.title()} after hard eligibility and "
        f"{len(soft)} documented soft-comparability assessments."
    )


def _jaccard(left: str, right: str) -> Decimal:
    def tokenize(value: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", value.casefold()))

    first, second = tokenize(left), tokenize(right)
    if not first or not second:
        return Decimal("0")
    return Decimal(len(first & second)) / Decimal(len(first | second))
