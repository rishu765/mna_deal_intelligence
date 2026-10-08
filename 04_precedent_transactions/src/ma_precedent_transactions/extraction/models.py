"""Validated source-observation and verified-record contracts for M3."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from ma_precedent_transactions.domain import (
    BuyerType,
    CapitalComponentKind,
    ConsiderationKind,
    DealStatus,
    FactStatus,
    FinancialMetricName,
    MetricBasis,
    TransactionRecord,
    TransactionType,
    ValuationMeasure,
)
from ma_precedent_transactions.errors import ExtractionValidationError


def _required(value: str, name: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ExtractionValidationError(f"{name} must not be blank")
    return normalized


def _evidence(values: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(_required(value, "evidence_id") for value in values)
    if not normalized:
        raise ExtractionValidationError("extracted observations require evidence IDs")
    if len(set(normalized)) != len(normalized):
        raise ExtractionValidationError("evidence IDs must be unique")
    return normalized


class PartyRole(StrEnum):
    ACQUIRER = "acquirer"
    TARGET = "target"
    SELLER = "seller"
    PARENT = "parent"


class DealDateKind(StrEnum):
    ANNOUNCEMENT = "announcement"
    SIGNING = "signing"
    COMPLETION = "completion"
    TERMINATION = "termination"


class RevisionKind(StrEnum):
    ORIGINAL = "original"
    AMENDED = "amended"
    CURRENT = "current"
    UNSPECIFIED = "unspecified"


class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    SOURCE_BACKED = "source_backed"
    SINGLE_SOURCE = "single_source"
    CONFLICTING = "conflicting"
    DERIVED = "derived"
    UNVERIFIED = "unverified"
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class RawMoney:
    value: str
    currency: str
    unit: str
    measurement_date: date | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _required(self.value, "money value"))
        object.__setattr__(self, "currency", _required(self.currency, "currency").upper())
        object.__setattr__(self, "unit", _required(self.unit, "unit"))


@dataclass(frozen=True, slots=True)
class ExtractedObservation:
    observation_id: str
    evidence_ids: tuple[str, ...]
    source_wording: str
    effective_date: date | None = None
    revision: RevisionKind = RevisionKind.UNSPECIFIED
    notes: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "observation_id", _required(self.observation_id, "observation_id"))
        object.__setattr__(self, "evidence_ids", _evidence(self.evidence_ids))
        object.__setattr__(self, "source_wording", _required(self.source_wording, "source_wording"))


@dataclass(frozen=True, slots=True)
class PartyObservation(ExtractedObservation):
    role: PartyRole = PartyRole.TARGET
    legal_name: str = ""
    aliases: tuple[str, ...] = ()
    relationship: str | None = None

    def __post_init__(self) -> None:
        super(PartyObservation, self).__post_init__()
        object.__setattr__(self, "legal_name", _required(self.legal_name, "legal_name"))


@dataclass(frozen=True, slots=True)
class DateObservation(ExtractedObservation):
    kind: DealDateKind = DealDateKind.ANNOUNCEMENT
    value: date = date.min


@dataclass(frozen=True, slots=True)
class StatusObservation(ExtractedObservation):
    status: DealStatus = DealStatus.UNKNOWN


@dataclass(frozen=True, slots=True)
class StructureObservation(ExtractedObservation):
    transaction_type: TransactionType = TransactionType.UNKNOWN
    buyer_type: BuyerType = BuyerType.UNKNOWN
    jurisdiction: str | None = None


@dataclass(frozen=True, slots=True)
class ConsiderationObservation(ExtractedObservation):
    kind: ConsiderationKind = ConsiderationKind.UNKNOWN
    amount: RawMoney | None = None
    quantity: str | None = None
    quantity_unit: str | None = None
    per_share: bool = False

    def __post_init__(self) -> None:
        super(ConsiderationObservation, self).__post_init__()
        if self.amount is None and self.quantity is None and not self.source_wording:
            raise ExtractionValidationError("consideration requires value or wording")
        if (self.quantity is None) != (self.quantity_unit is None):
            raise ExtractionValidationError("quantity and quantity_unit must be supplied together")


@dataclass(frozen=True, slots=True)
class OwnershipFactObservation(ExtractedObservation):
    pre_deal_percent: str | None = None
    acquired_percent: str | None = None
    post_deal_percent: str | None = None

    def __post_init__(self) -> None:
        super(OwnershipFactObservation, self).__post_init__()
        if all(
            value is None
            for value in (self.pre_deal_percent, self.acquired_percent, self.post_deal_percent)
        ):
            raise ExtractionValidationError("ownership observation requires a percentage")


@dataclass(frozen=True, slots=True)
class ValuationFactObservation(ExtractedObservation):
    measure: ValuationMeasure = ValuationMeasure.HEADLINE_DEAL_VALUE
    amount: RawMoney | None = None
    disclosed: bool = True
    ambiguous_basis: bool = False


@dataclass(frozen=True, slots=True)
class FinancialFactObservation(ExtractedObservation):
    name: FinancialMetricName = FinancialMetricName.REVENUE
    value: str = ""
    currency: str = ""
    unit: str = ""
    period: str = ""
    basis: MetricBasis = MetricBasis.REPORTED
    adjustment_label: str | None = None
    measurement_date: date | None = None

    def __post_init__(self) -> None:
        super(FinancialFactObservation, self).__post_init__()
        for field_name in ("value", "currency", "unit", "period"):
            object.__setattr__(self, field_name, _required(getattr(self, field_name), field_name))
        if self.basis is MetricBasis.ADJUSTED and not self.adjustment_label:
            raise ExtractionValidationError("adjusted financials require adjustment_label")


@dataclass(frozen=True, slots=True)
class CapitalFactObservation(ExtractedObservation):
    kind: CapitalComponentKind = CapitalComponentKind.DEBT
    amount: RawMoney | None = None
    as_of: date = date.min

    def __post_init__(self) -> None:
        super(CapitalFactObservation, self).__post_init__()
        if self.amount is None:
            raise ExtractionValidationError("capital observation requires an amount")


@dataclass(frozen=True, slots=True)
class ExtractionBatch:
    transaction_id: str
    parties: tuple[PartyObservation, ...] = ()
    dates: tuple[DateObservation, ...] = ()
    statuses: tuple[StatusObservation, ...] = ()
    structures: tuple[StructureObservation, ...] = ()
    consideration: tuple[ConsiderationObservation, ...] = ()
    ownership: tuple[OwnershipFactObservation, ...] = ()
    valuations: tuple[ValuationFactObservation, ...] = ()
    financials: tuple[FinancialFactObservation, ...] = ()
    capital_structure: tuple[CapitalFactObservation, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "transaction_id", _required(self.transaction_id, "transaction_id"))
        ids = [item.observation_id for item in self.observations]
        if len(ids) != len(set(ids)):
            raise ExtractionValidationError("observation IDs must be unique")

    @property
    def observations(self) -> tuple[ExtractedObservation, ...]:
        return (
            *self.parties,
            *self.dates,
            *self.statuses,
            *self.structures,
            *self.consideration,
            *self.ownership,
            *self.valuations,
            *self.financials,
            *self.capital_structure,
        )


@dataclass(frozen=True, slots=True)
class FieldVerification:
    field: str
    status: VerificationStatus
    selected_observation_id: str | None
    supporting_observation_ids: tuple[str, ...]
    conflicting_observation_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    rationale: str


@dataclass(frozen=True, slots=True)
class FactConflict:
    field: str
    observation_ids: tuple[str, ...]
    values: tuple[str, ...]
    summary: str


@dataclass(frozen=True, slots=True)
class ExtractionTrace:
    final_field: str
    observation_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    calculation: str | None = None


@dataclass(frozen=True, slots=True)
class VerifiedTransactionRecord:
    record: TransactionRecord
    related_parties: tuple[PartyObservation, ...]
    verification: tuple[FieldVerification, ...]
    conflicts: tuple[FactConflict, ...]
    traces: tuple[ExtractionTrace, ...]
    warnings: tuple[str, ...]
    fact_status: FactStatus = FactStatus.EXTRACTED_UNVERIFIED
