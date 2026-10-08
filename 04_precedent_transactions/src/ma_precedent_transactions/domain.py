"""Provider-neutral domain contracts for precedent transaction research."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from ma_precedent_transactions.errors import DomainValidationError

_CURRENCY_PATTERN = re.compile(r"[A-Z]{3}")


def _text(value: str, name: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise DomainValidationError(f"{name} must not be blank")
    return normalized


def _optional_text(value: str | None, name: str) -> str | None:
    return None if value is None else _text(value, name)


def _decimal(value: Decimal | int | str, name: str) -> Decimal:
    try:
        normalized = Decimal(value)
    except (InvalidOperation, ValueError) as error:
        raise DomainValidationError(f"{name} must be a decimal value") from error
    if not normalized.is_finite():
        raise DomainValidationError(f"{name} must be finite")
    return normalized


def _currency(value: str) -> str:
    normalized = value.strip().upper()
    if _CURRENCY_PATTERN.fullmatch(normalized) is None:
        raise DomainValidationError("currency must be a three-letter ISO-style code")
    return normalized


def _aware(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DomainValidationError(f"{name} must be timezone-aware")
    return value


def _unique_text(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    normalized = tuple(_text(value, name) for value in values)
    if len({value.casefold() for value in normalized}) != len(normalized):
        raise DomainValidationError(f"{name} must not contain duplicates")
    return normalized


class DealStatus(StrEnum):
    ANNOUNCED = "announced"
    PENDING = "pending"
    COMPLETED = "completed"
    WITHDRAWN = "withdrawn"
    TERMINATED = "terminated"
    UNKNOWN = "unknown"


class TransactionType(StrEnum):
    STOCK_ACQUISITION = "stock_acquisition"
    ASSET_ACQUISITION = "asset_acquisition"
    MERGER = "merger"
    MAJORITY_STAKE_ACQUISITION = "majority_stake_acquisition"
    MINORITY_INVESTMENT = "minority_investment"
    REMAINING_STAKE_ACQUISITION = "remaining_stake_acquisition"
    DIVESTITURE = "divestiture"
    BUSINESS_UNIT_ACQUISITION = "business_unit_acquisition"
    OTHER = "other"
    UNKNOWN = "unknown"


class BuyerType(StrEnum):
    STRATEGIC = "strategic"
    FINANCIAL = "financial"
    CONSORTIUM = "consortium"
    UNKNOWN = "unknown"


class ControlType(StrEnum):
    CONTROL = "control"
    MINORITY = "minority"
    UNKNOWN = "unknown"


class PublicStatus(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"
    GOVERNMENT = "government"
    OTHER = "other"
    UNKNOWN = "unknown"


class SourceReliability(StrEnum):
    REGULATORY = "regulatory"
    PRIMARY_COMPANY = "primary_company"
    CONTRACTUAL = "contractual"
    TRUSTED_SECONDARY = "trusted_secondary"
    OTHER = "other"
    UNKNOWN = "unknown"


class ExtractionMethod(StrEnum):
    MANUAL = "manual"
    RULE_BASED = "rule_based"
    LLM = "llm"
    IMPORTED = "imported"
    UNKNOWN = "unknown"


class FactStatus(StrEnum):
    DIRECTLY_DISCLOSED = "directly_disclosed"
    DERIVED_FROM_DISCLOSED = "derived_from_disclosed"
    EXTRACTED_UNVERIFIED = "extracted_unverified"
    CONFLICTING = "conflicting"
    UNKNOWN = "unknown"


class ValuationMeasure(StrEnum):
    HEADLINE_DEAL_VALUE = "headline_deal_value"
    EQUITY_PURCHASE_PRICE = "equity_purchase_price"
    TRANSACTION_ENTERPRISE_VALUE = "transaction_enterprise_value"
    PER_SHARE_OFFER_PRICE = "per_share_offer_price"


class ValuationBasis(StrEnum):
    EXPLICITLY_DISCLOSED = "explicitly_disclosed"
    INDEPENDENTLY_CALCULATED = "independently_calculated"
    ESTIMATED = "estimated"
    AMBIGUOUS = "ambiguous"
    UNAVAILABLE = "unavailable"


class ConsiderationKind(StrEnum):
    CASH = "cash"
    SHARES = "shares"
    CONTINGENT = "contingent"
    EARNOUT = "earnout"
    ASSUMED_LIABILITIES = "assumed_liabilities"
    OTHER = "other"
    UNKNOWN = "unknown"


class FinancialUnit(StrEnum):
    UNITS = "units"
    THOUSAND = "thousand"
    MILLION = "million"
    BILLION = "billion"
    LAKH = "lakh"
    CRORE = "crore"
    PER_SHARE = "per_share"
    PERCENT = "percent"


class PeriodKind(StrEnum):
    FISCAL_YEAR = "fiscal_year"
    CALENDAR_YEAR = "calendar_year"
    LTM = "ltm"
    POINT_IN_TIME = "point_in_time"


class EstimateStatus(StrEnum):
    HISTORICAL = "historical"
    FORECAST = "forecast"


class MetricBasis(StrEnum):
    REPORTED = "reported"
    ADJUSTED = "adjusted"


class FinancialMetricName(StrEnum):
    REVENUE = "revenue"
    EBITDA = "ebitda"
    EBIT = "ebit"
    NET_INCOME = "net_income"
    EPS = "eps"
    REVENUE_GROWTH = "revenue_growth"
    EBITDA_MARGIN = "ebitda_margin"


class CapitalComponentKind(StrEnum):
    CASH = "cash"
    DEBT = "debt"
    PREFERRED_STOCK = "preferred_stock"
    NONCONTROLLING_INTEREST = "noncontrolling_interest"
    OTHER_ADJUSTMENT = "other_adjustment"


class CriterionMode(StrEnum):
    HARD_FILTER = "hard_filter"
    QUALITATIVE_JUDGMENT = "qualitative_judgment"


class ComparableCriterionKind(StrEnum):
    INDUSTRY = "industry"
    BUSINESS_MODEL = "business_model"
    GEOGRAPHY = "geography"
    ANNOUNCEMENT_PERIOD = "announcement_period"
    TRANSACTION_SIZE = "transaction_size"
    TARGET_REVENUE = "target_revenue"
    EBITDA_MARGIN = "ebitda_margin"
    TRANSACTION_TYPE = "transaction_type"
    OWNERSHIP_CONTROL = "ownership_control"
    BUYER_TYPE = "buyer_type"
    GROWTH = "growth"


class MultipleKind(StrEnum):
    EV_REVENUE = "ev_revenue"
    EV_EBITDA = "ev_ebitda"
    EV_EBIT = "ev_ebit"
    EQUITY_VALUE_NET_INCOME = "equity_value_net_income"


class MultipleStatus(StrEnum):
    PENDING = "pending"
    INCLUDED = "included"
    EXCLUDED = "excluded"
    NOT_MEANINGFUL = "not_meaningful"
    MISSING_INPUT = "missing_input"


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    """A source locator that supports one or more transaction facts."""

    evidence_id: str
    source_type: str
    document_title: str
    retrieved_at: datetime
    reliability: SourceReliability
    extraction_method: ExtractionMethod
    source_url: str | None = None
    publisher: str | None = None
    publication_date: date | None = None
    document_id: str | None = None
    page: int | None = None
    section: str | None = None
    table: str | None = None
    chunk_id: str | None = None
    text_location: str | None = None
    excerpt_id: str | None = None
    excerpt: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("evidence_id", "source_type", "document_title"):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), field_name))
        for field_name in (
            "source_url",
            "publisher",
            "document_id",
            "section",
            "table",
            "chunk_id",
            "text_location",
            "excerpt_id",
            "excerpt",
        ):
            object.__setattr__(
                self, field_name, _optional_text(getattr(self, field_name), field_name)
            )
        object.__setattr__(self, "retrieved_at", _aware(self.retrieved_at, "retrieved_at"))
        if self.page is not None and self.page < 1:
            raise DomainValidationError("page must be positive")


@dataclass(frozen=True, slots=True)
class ExternalIdentifier:
    scheme: str
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "scheme", _text(self.scheme, "identifier scheme"))
        object.__setattr__(self, "value", _text(self.value, "identifier value"))


@dataclass(frozen=True, slots=True)
class TransactionParty:
    """An acquirer or target; optional fields remain explicitly unknown as ``None``."""

    party_id: str
    legal_name: str | None
    alternative_names: tuple[str, ...] = ()
    ticker: str | None = None
    exchange: str | None = None
    country: str | None = None
    industry: str | None = None
    business_description: str | None = None
    public_status: PublicStatus = PublicStatus.UNKNOWN
    external_identifiers: tuple[ExternalIdentifier, ...] = ()
    evidence: tuple[EvidenceReference, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "party_id", _text(self.party_id, "party_id"))
        object.__setattr__(self, "legal_name", _optional_text(self.legal_name, "legal_name"))
        object.__setattr__(
            self, "alternative_names", _unique_text(self.alternative_names, "alternative_names")
        )
        for field_name in ("ticker", "exchange", "country", "industry", "business_description"):
            object.__setattr__(
                self, field_name, _optional_text(getattr(self, field_name), field_name)
            )
        for field_name in ("ticker", "exchange"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, value.upper())
        identifier_keys = {
            (identifier.scheme.casefold(), identifier.value.casefold())
            for identifier in self.external_identifiers
        }
        if len(identifier_keys) != len(self.external_identifiers):
            raise DomainValidationError("external_identifiers must not contain duplicates")


@dataclass(frozen=True, slots=True)
class TransactionIdentity:
    """Stable identity independent of article count and target name alone."""

    transaction_id: str
    acquirer_party_id: str
    target_party_id: str
    transaction_type: TransactionType
    announcement_date: date | None = None
    identity_qualifier: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("transaction_id", "acquirer_party_id", "target_party_id"):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), field_name))
        object.__setattr__(
            self,
            "identity_qualifier",
            _optional_text(self.identity_qualifier, "identity_qualifier"),
        )
        if self.acquirer_party_id == self.target_party_id:
            raise DomainValidationError("acquirer and target must be distinct parties")


@dataclass(frozen=True, slots=True)
class DealLifecycle:
    status: DealStatus
    status_as_of: date
    announcement_date: date | None = None
    completion_date: date | None = None
    evidence: tuple[EvidenceReference, ...] = ()

    def __post_init__(self) -> None:
        if (
            self.completion_date is not None
            and self.announcement_date is not None
            and self.completion_date < self.announcement_date
        ):
            raise DomainValidationError("completion_date must not precede announcement_date")
        for known_date in (self.announcement_date, self.completion_date):
            if known_date is not None and self.status_as_of < known_date:
                raise DomainValidationError("status_as_of must not precede a known lifecycle date")
        if self.status is DealStatus.COMPLETED and self.completion_date is None:
            raise DomainValidationError("completed transactions require completion_date")
        if self.status in {DealStatus.WITHDRAWN, DealStatus.TERMINATED} and self.completion_date:
            raise DomainValidationError(
                "withdrawn or terminated transactions cannot have completion_date"
            )


@dataclass(frozen=True, slots=True)
class TransactionStructure:
    transaction_type: TransactionType
    buyer_type: BuyerType = BuyerType.UNKNOWN
    control_type: ControlType = ControlType.UNKNOWN
    jurisdiction: str | None = None
    description: str | None = None
    evidence: tuple[EvidenceReference, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "jurisdiction", _optional_text(self.jurisdiction, "jurisdiction"))
        object.__setattr__(self, "description", _optional_text(self.description, "description"))


@dataclass(frozen=True, slots=True)
class MonetaryAmount:
    value: Decimal
    currency: str
    unit: FinancialUnit
    measurement_date: date | None = None

    def __post_init__(self) -> None:
        value = _decimal(self.value, "monetary value")
        if value < 0:
            raise DomainValidationError("monetary value must not be negative")
        if self.unit is FinancialUnit.PERCENT:
            raise DomainValidationError("monetary amounts cannot use percent")
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "currency", _currency(self.currency))


@dataclass(frozen=True, slots=True)
class ConsiderationComponent:
    component_id: str
    kind: ConsiderationKind
    fact_status: FactStatus
    evidence: tuple[EvidenceReference, ...]
    amount: MonetaryAmount | None = None
    quantity: Decimal | None = None
    quantity_unit: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "component_id", _text(self.component_id, "component_id"))
        object.__setattr__(
            self, "quantity_unit", _optional_text(self.quantity_unit, "quantity_unit")
        )
        object.__setattr__(self, "description", _optional_text(self.description, "description"))
        if self.quantity is not None:
            quantity = _decimal(self.quantity, "quantity")
            if quantity < 0:
                raise DomainValidationError("quantity must not be negative")
            object.__setattr__(self, "quantity", quantity)
            if self.quantity_unit is None:
                raise DomainValidationError("quantity requires quantity_unit")
        if not self.evidence and self.fact_status is not FactStatus.UNKNOWN:
            raise DomainValidationError("known consideration components require evidence")
        if self.amount is None and self.quantity is None and self.description is None:
            raise DomainValidationError(
                "consideration requires an amount, quantity, or description"
            )


@dataclass(frozen=True, slots=True)
class ValuationObservation:
    observation_id: str
    measure: ValuationMeasure
    basis: ValuationBasis
    fact_status: FactStatus
    evidence: tuple[EvidenceReference, ...]
    amount: MonetaryAmount | None = None
    assumptions: tuple[str, ...] = ()
    notes: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "observation_id", _text(self.observation_id, "observation_id"))
        object.__setattr__(self, "assumptions", _unique_text(self.assumptions, "assumptions"))
        object.__setattr__(self, "notes", _optional_text(self.notes, "notes"))
        if self.basis is ValuationBasis.UNAVAILABLE and self.amount is not None:
            raise DomainValidationError("unavailable valuation observations cannot have an amount")
        if self.basis is not ValuationBasis.UNAVAILABLE and self.amount is None:
            raise DomainValidationError("available valuation observations require an amount")
        if self.basis is ValuationBasis.INDEPENDENTLY_CALCULATED and not self.assumptions:
            raise DomainValidationError("independently calculated values require assumptions")
        if self.amount is not None and not self.evidence:
            raise DomainValidationError("valuation observations with amounts require evidence")


@dataclass(frozen=True, slots=True)
class OwnershipObservation:
    observation_id: str
    fact_status: FactStatus
    evidence: tuple[EvidenceReference, ...]
    pre_deal_percent: Decimal | None = None
    acquired_percent: Decimal | None = None
    post_deal_percent: Decimal | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "observation_id", _text(self.observation_id, "observation_id"))
        object.__setattr__(self, "notes", _optional_text(self.notes, "notes"))
        values = (self.pre_deal_percent, self.acquired_percent, self.post_deal_percent)
        if all(value is None for value in values) and self.fact_status is not FactStatus.UNKNOWN:
            raise DomainValidationError("known ownership observations require a percentage")
        for field_name in ("pre_deal_percent", "acquired_percent", "post_deal_percent"):
            value = getattr(self, field_name)
            if value is not None:
                normalized = _decimal(value, field_name)
                if not Decimal("0") <= normalized <= Decimal("100"):
                    raise DomainValidationError(f"{field_name} must be between 0 and 100")
                object.__setattr__(self, field_name, normalized)
        if not self.evidence and self.fact_status is not FactStatus.UNKNOWN:
            raise DomainValidationError("known ownership observations require evidence")


@dataclass(frozen=True, slots=True)
class CapitalStructureComponent:
    component_id: str
    kind: CapitalComponentKind
    amount: MonetaryAmount
    as_of: date
    fact_status: FactStatus
    evidence: tuple[EvidenceReference, ...]
    notes: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "component_id", _text(self.component_id, "component_id"))
        object.__setattr__(self, "notes", _optional_text(self.notes, "notes"))
        if not self.evidence:
            raise DomainValidationError("capital structure components require evidence")


@dataclass(frozen=True, slots=True)
class CapitalStructureSnapshot:
    snapshot_id: str
    as_of: date
    components: tuple[CapitalStructureComponent, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", _text(self.snapshot_id, "snapshot_id"))
        ids = [component.component_id for component in self.components]
        if len(set(ids)) != len(ids):
            raise DomainValidationError("capital structure component IDs must be unique")
        if any(component.as_of > self.as_of for component in self.components):
            raise DomainValidationError("capital structure component must not post-date snapshot")


@dataclass(frozen=True, slots=True)
class FinancialPeriod:
    kind: PeriodKind
    label: str
    estimate_status: EstimateStatus
    start_date: date | None = None
    end_date: date | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", _text(self.label, "period label"))
        if (self.start_date is None) != (self.end_date is None):
            raise DomainValidationError("period start_date and end_date must be supplied together")
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise DomainValidationError("period start_date must not follow end_date")
        if self.kind is PeriodKind.LTM and self.end_date is None:
            raise DomainValidationError("LTM periods require dates")


@dataclass(frozen=True, slots=True)
class FinancialMetric:
    metric_id: str
    name: FinancialMetricName
    value: Decimal
    unit: FinancialUnit
    period: FinancialPeriod
    basis: MetricBasis
    measurement_date: date
    fact_status: FactStatus
    evidence: tuple[EvidenceReference, ...]
    currency: str | None = None
    adjustment_label: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "metric_id", _text(self.metric_id, "metric_id"))
        value = _decimal(self.value, "metric value")
        object.__setattr__(self, "value", value)
        ratio_names = {FinancialMetricName.REVENUE_GROWTH, FinancialMetricName.EBITDA_MARGIN}
        if self.name in ratio_names:
            if self.unit is not FinancialUnit.PERCENT or self.currency is not None:
                raise DomainValidationError(
                    "growth and margin metrics require percent and no currency"
                )
        else:
            if self.currency is None:
                raise DomainValidationError("monetary financial metrics require currency")
            object.__setattr__(self, "currency", _currency(self.currency))
            if self.unit is FinancialUnit.PERCENT:
                raise DomainValidationError("monetary financial metrics cannot use percent")
        if self.name is FinancialMetricName.EPS and self.unit is not FinancialUnit.PER_SHARE:
            raise DomainValidationError("EPS must use per_share")
        if self.name is not FinancialMetricName.EPS and self.unit is FinancialUnit.PER_SHARE:
            raise DomainValidationError("only EPS may use per_share")
        if self.name is FinancialMetricName.REVENUE and value < 0:
            raise DomainValidationError("revenue must not be negative")
        if not self.evidence:
            raise DomainValidationError("financial metrics require evidence")
        object.__setattr__(
            self,
            "adjustment_label",
            _optional_text(self.adjustment_label, "adjustment_label"),
        )
        object.__setattr__(self, "notes", _optional_text(self.notes, "notes"))
        if self.basis is MetricBasis.ADJUSTED and self.adjustment_label is None:
            raise DomainValidationError("adjusted metrics require adjustment_label")
        if self.basis is MetricBasis.REPORTED and self.adjustment_label is not None:
            raise DomainValidationError("reported metrics cannot have adjustment_label")


@dataclass(frozen=True, slots=True)
class ComparableCriterion:
    criterion_id: str
    kind: ComparableCriterionKind
    mode: CriterionMode
    description: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "criterion_id", _text(self.criterion_id, "criterion_id"))
        object.__setattr__(self, "description", _text(self.description, "description"))


@dataclass(frozen=True, slots=True)
class ComparableSelectionPolicy:
    policy_id: str
    criteria: tuple[ComparableCriterion, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", _text(self.policy_id, "policy_id"))
        ids = [criterion.criterion_id for criterion in self.criteria]
        if len(set(ids)) != len(ids):
            raise DomainValidationError("criterion IDs must be unique")


@dataclass(frozen=True, slots=True)
class TransactionMultipleDefinition:
    kind: MultipleKind
    numerator: ValuationMeasure
    denominator: FinancialMetricName

    def __post_init__(self) -> None:
        valid = {
            MultipleKind.EV_REVENUE: (
                ValuationMeasure.TRANSACTION_ENTERPRISE_VALUE,
                FinancialMetricName.REVENUE,
            ),
            MultipleKind.EV_EBITDA: (
                ValuationMeasure.TRANSACTION_ENTERPRISE_VALUE,
                FinancialMetricName.EBITDA,
            ),
            MultipleKind.EV_EBIT: (
                ValuationMeasure.TRANSACTION_ENTERPRISE_VALUE,
                FinancialMetricName.EBIT,
            ),
            MultipleKind.EQUITY_VALUE_NET_INCOME: (
                ValuationMeasure.EQUITY_PURCHASE_PRICE,
                FinancialMetricName.NET_INCOME,
            ),
        }
        if valid[self.kind] != (self.numerator, self.denominator):
            raise DomainValidationError("invalid numerator and denominator for multiple kind")


@dataclass(frozen=True, slots=True)
class TransactionMultipleContract:
    """Future M4/5 output contract; M0 never computes ``value``."""

    multiple_id: str
    transaction_id: str
    definition: TransactionMultipleDefinition
    status: MultipleStatus
    numerator_observation_id: str | None = None
    denominator_metric_id: str | None = None
    value: Decimal | None = None
    calculation_trace: tuple[str, ...] = ()
    treatment_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "multiple_id", _text(self.multiple_id, "multiple_id"))
        object.__setattr__(self, "transaction_id", _text(self.transaction_id, "transaction_id"))
        for field_name in (
            "numerator_observation_id",
            "denominator_metric_id",
            "treatment_reason",
        ):
            object.__setattr__(
                self, field_name, _optional_text(getattr(self, field_name), field_name)
            )
        object.__setattr__(
            self,
            "calculation_trace",
            _unique_text(self.calculation_trace, "calculation_trace"),
        )
        if self.value is not None:
            object.__setattr__(self, "value", _decimal(self.value, "multiple value"))
        if (
            self.status in {MultipleStatus.NOT_MEANINGFUL, MultipleStatus.MISSING_INPUT}
            and self.treatment_reason is None
        ):
            raise DomainValidationError("non-usable multiples require treatment_reason")


@dataclass(frozen=True, slots=True)
class TransactionRecord:
    identity: TransactionIdentity
    acquirer: TransactionParty
    target: TransactionParty
    lifecycle: DealLifecycle
    structure: TransactionStructure
    valuations: tuple[ValuationObservation, ...] = ()
    consideration: tuple[ConsiderationComponent, ...] = ()
    ownership: tuple[OwnershipObservation, ...] = ()
    target_financials: tuple[FinancialMetric, ...] = ()
    capital_structure: tuple[CapitalStructureSnapshot, ...] = ()
    evidence: tuple[EvidenceReference, ...] = ()

    def __post_init__(self) -> None:
        if self.identity.acquirer_party_id != self.acquirer.party_id:
            raise DomainValidationError("identity acquirer_party_id must match acquirer")
        if self.identity.target_party_id != self.target.party_id:
            raise DomainValidationError("identity target_party_id must match target")
        if self.identity.transaction_type is not self.structure.transaction_type:
            raise DomainValidationError("identity and structure transaction types must match")
        if (
            self.identity.announcement_date is not None
            and self.lifecycle.announcement_date is not None
            and self.identity.announcement_date != self.lifecycle.announcement_date
        ):
            raise DomainValidationError("identity and lifecycle announcement dates must match")
        for collection_name, identifiers in (
            ("valuation observation", [item.observation_id for item in self.valuations]),
            ("consideration component", [item.component_id for item in self.consideration]),
            ("ownership observation", [item.observation_id for item in self.ownership]),
            ("financial metric", [item.metric_id for item in self.target_financials]),
            ("capital snapshot", [item.snapshot_id for item in self.capital_structure]),
        ):
            if len(set(identifiers)) != len(identifiers):
                raise DomainValidationError(f"{collection_name} IDs must be unique")
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(set(evidence_ids)) != len(evidence_ids):
            raise DomainValidationError("record evidence IDs must be unique")
