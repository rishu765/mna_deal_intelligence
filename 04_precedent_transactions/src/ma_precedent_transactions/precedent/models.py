"""Selection, multiple, statistics, valuation, and explanation contracts for M4/5."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from ma_precedent_transactions.domain import (
    CapitalStructureSnapshot,
    EvidenceReference,
    FinancialMetric,
    FinancialPeriod,
    FinancialUnit,
    MetricBasis,
    MultipleKind,
    TransactionMultipleContract,
    TransactionType,
    ValuationBasis,
)


class SelectionDecision(StrEnum):
    INCLUDE = "include"
    EXCLUDE = "exclude"
    SEPARATE = "separate"
    REVIEW = "review"


class CriterionMode(StrEnum):
    HARD = "hard"
    SOFT = "soft"


class CriterionOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


class MinorityTreatment(StrEnum):
    EXCLUDE = "exclude"
    SEPARATE = "separate"
    LOW_COMPARABILITY = "low_comparability"


class OverrideAction(StrEnum):
    FORCE_INCLUDE = "force_include"
    FORCE_EXCLUDE = "force_exclude"


class CalculationStatus(StrEnum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class TargetComparabilityProfile:
    target_id: str
    industry: str
    business_model: str
    products: tuple[str, ...]
    customer_types: tuple[str, ...]
    geographies: tuple[str, ...]
    revenue: FinancialMetric | None = None


@dataclass(frozen=True, slots=True)
class PrecedentSelectionPolicy:
    policy_id: str = "precedent-selection-v1"
    as_of: date = date.max
    announced_from: date | None = None
    announced_to: date | None = None
    minority_treatment: MinorityTreatment = MinorityTreatment.EXCLUDE
    require_completed: bool = True
    require_usable_value: bool = True
    minimum_soft_score: Decimal = Decimal("0.45")
    max_revenue_ratio: Decimal = Decimal("4")
    min_revenue_ratio: Decimal = Decimal("0.25")
    eligible_transaction_types: tuple[TransactionType, ...] = (
        TransactionType.STOCK_ACQUISITION,
        TransactionType.MERGER,
        TransactionType.MAJORITY_STAKE_ACQUISITION,
        TransactionType.REMAINING_STAKE_ACQUISITION,
    )

    def __post_init__(self) -> None:
        if not Decimal("0") <= self.minimum_soft_score <= Decimal("1"):
            raise ValueError("minimum_soft_score must be between zero and one")
        if self.min_revenue_ratio <= 0 or self.max_revenue_ratio < self.min_revenue_ratio:
            raise ValueError("revenue-ratio bounds must be positive and ordered")
        if self.announced_from and self.announced_to and self.announced_from > self.announced_to:
            raise ValueError("announcement window must be ordered")


@dataclass(frozen=True, slots=True)
class CriterionAssessment:
    criterion: str
    mode: CriterionMode
    outcome: CriterionOutcome
    rationale: str
    score: Decimal | None = None
    missing_information: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ManualOverride:
    transaction_id: str
    action: OverrideAction
    rationale: str
    actor: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not self.rationale.strip() or not self.actor.strip():
            raise ValueError("manual overrides require rationale and actor")
        if self.recorded_at.tzinfo is None:
            raise ValueError("manual override timestamp must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ComparableTransactionDecision:
    transaction_id: str
    decision: SelectionDecision
    assessments: tuple[CriterionAssessment, ...]
    rationale: str
    soft_score: Decimal | None
    evidence: tuple[EvidenceReference, ...]
    missing_information: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    override: ManualOverride | None = None


@dataclass(frozen=True, slots=True)
class ComparableTransactionSet:
    set_id: str
    policy_id: str
    decisions: tuple[ComparableTransactionDecision, ...]
    selected_transaction_ids: tuple[str, ...]
    separate_transaction_ids: tuple[str, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TransactionMultipleResult:
    contract: TransactionMultipleContract
    numerator_value: Decimal | None
    numerator_currency: str | None
    numerator_unit: FinancialUnit | None
    numerator_basis: ValuationBasis | None
    denominator_value: Decimal | None
    denominator_currency: str | None
    denominator_unit: FinancialUnit | None
    denominator_period: FinancialPeriod | None
    denominator_basis: MetricBasis | None
    evidence: tuple[EvidenceReference, ...]
    warnings: tuple[str, ...] = ()
    outlier: bool = False


@dataclass(frozen=True, slots=True)
class MultipleSetKey:
    kind: MultipleKind
    currency: str
    period_kind: str
    basis: MetricBasis


@dataclass(frozen=True, slots=True)
class PeerStatistics:
    statistics_id: str
    key: MultipleSetKey
    count: int
    excluded_count: int
    minimum: Decimal | None
    percentile_25: Decimal | None
    median: Decimal | None
    percentile_75: Decimal | None
    maximum: Decimal | None
    mean: Decimal | None
    included_multiple_ids: tuple[str, ...]
    excluded: tuple[tuple[str, str], ...]
    outlier_multiple_ids: tuple[str, ...]
    percentile_method: str = "linear_interpolation_r7"
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TransactionMultipleSet:
    set_id: str
    key: MultipleSetKey
    multiples: tuple[TransactionMultipleResult, ...]
    statistics: PeerStatistics
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TargetCapitalProfile:
    snapshot: CapitalStructureSnapshot | None
    diluted_shares: Decimal | None
    share_unit: FinancialUnit | None
    share_count_date: date | None
    share_count_basis: str | None = None
    share_count_evidence: tuple[EvidenceReference, ...] = ()

    def __post_init__(self) -> None:
        if self.diluted_shares is not None and self.diluted_shares <= 0:
            raise ValueError("diluted_shares must be positive")
        if (self.diluted_shares is None) != (self.share_unit is None):
            raise ValueError("diluted shares and share unit must be supplied together")


@dataclass(frozen=True, slots=True)
class TargetValuationProfile:
    target_id: str
    metrics: tuple[FinancialMetric, ...]
    capital: TargetCapitalProfile
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CalculationInput:
    input_id: str
    label: str
    value: Decimal
    unit: FinancialUnit
    currency: str | None
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CalculationTrace:
    trace_id: str
    formula: str
    inputs: tuple[CalculationInput, ...]
    result: Decimal | None
    policy_id: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ImpliedValuationCase:
    anchor: str
    multiple: Decimal
    implied_enterprise_value: Decimal | None
    implied_equity_value: Decimal | None
    implied_per_share: Decimal | None
    currency: str
    unit: FinancialUnit
    status: CalculationStatus
    trace: CalculationTrace
    bridge_trace: CalculationTrace | None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ImpliedValuationRange:
    range_id: str
    key: MultipleSetKey
    target_metric_id: str
    low: ImpliedValuationCase
    mid: ImpliedValuationCase
    high: ImpliedValuationCase
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValuationExplanation:
    status: CalculationStatus
    precedent_set_assessment: str
    strongest_precedents: tuple[str, ...]
    weakest_precedents: tuple[str, ...]
    key_valuation_drivers: tuple[str, ...]
    outlier_commentary: tuple[str, ...]
    recommended_multiple_focus: tuple[str, ...]
    valuation_caveats: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PrecedentValuationOutput:
    output_id: str
    target_id: str
    selection: ComparableTransactionSet
    multiple_sets: tuple[TransactionMultipleSet, ...]
    ranges: tuple[ImpliedValuationRange, ...]
    explanation: ValuationExplanation | None
    warnings: tuple[str, ...] = ()
