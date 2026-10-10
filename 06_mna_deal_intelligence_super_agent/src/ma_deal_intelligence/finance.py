"""Cross-project financial, valuation, and diligence references."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from ma_deal_intelligence.evidence import ProjectId


class MetricBasis(StrEnum):
    REPORTED = "reported"
    ADJUSTED = "adjusted"
    NORMALIZED = "normalized"
    OTHER = "other"
    UNKNOWN = "unknown"


class EstimateStatus(StrEnum):
    ACTUAL = "actual"
    FORECAST = "forecast"
    OTHER = "other"
    UNKNOWN = "unknown"


class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    SOURCE_BACKED = "source_backed"
    SINGLE_SOURCE = "single_source"
    CONFLICTING = "conflicting"
    DERIVED = "derived"
    UNVERIFIED = "unverified"
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class FinancialPeriodReference:
    label: str
    start_date: date | None = None
    end_date: date | None = None

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("period label must not be blank")
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError("period dates must be supplied together")
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError("period start must not follow period end")


@dataclass(frozen=True, slots=True)
class FinancialMetricReference:
    metric_id: str
    metric_type: str
    value: Decimal
    currency: str | None
    unit: str
    period: FinancialPeriodReference
    basis: MetricBasis
    estimate_status: EstimateStatus
    source_project: ProjectId
    source_record_id: str
    entity_id: str | None = None
    evidence_refs: tuple[str, ...] = ()
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED

    def __post_init__(self) -> None:
        if not self.value.is_finite():
            raise ValueError("financial metric value must be finite")
        if self.currency is not None:
            object.__setattr__(self, "currency", self.currency.upper())


class ValuationMethod(StrEnum):
    TRADING_COMPARABLES = "trading_comparables"
    PRECEDENT_TRANSACTIONS = "precedent_transactions"
    OTHER = "other"


class ValuationBasis(StrEnum):
    ENTERPRISE_VALUE = "enterprise_value"
    EQUITY_VALUE = "equity_value"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class ValuationReference:
    valuation_id: str
    method: ValuationMethod
    low: Decimal
    midpoint: Decimal
    high: Decimal
    valuation_basis: ValuationBasis
    metric_basis: str
    currency: str
    unit: str
    as_of_date: date
    source_project: ProjectId
    source_record_id: str
    input_metric_ids: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    warning_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.low <= self.midpoint <= self.high:
            raise ValueError("valuation values must be ordered low <= midpoint <= high")
        object.__setattr__(self, "currency", self.currency.upper())


class FindingSeverity(StrEnum):
    UNASSESSED = "unassessed"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingStatus(StrEnum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    CONFIRMED = "confirmed"
    MITIGATED = "mitigated"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class DiligenceFindingReference:
    finding_id: str
    workstream: str
    title: str
    severity: FindingSeverity
    materiality: str
    deal_impacts: tuple[str, ...]
    status: FindingStatus
    source_project: ProjectId
    source_record_id: str
    evidence_refs: tuple[str, ...] = ()
    analyst_decision_id: str | None = None


@dataclass(frozen=True, slots=True)
class MetricConflict:
    conflict_id: str
    metric_ids: tuple[str, ...]
    description: str
    requires_analyst_review: bool
    resolved_by_decision_id: str | None = None

    def __post_init__(self) -> None:
        if len(self.metric_ids) < 2:
            raise ValueError("a metric conflict requires at least two metrics")
