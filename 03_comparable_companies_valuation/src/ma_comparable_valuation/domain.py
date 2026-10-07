"""Provider-neutral value objects for comparable-company valuation."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Self

_CURRENCY_PATTERN = re.compile(r"[A-Z]{3}")
_FISCAL_YEAR_END_PATTERN = re.compile(r"(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])")


def _text(value: str, name: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"{name} must not be blank")
    return normalized


def _optional_text(value: str | None, name: str) -> str | None:
    return None if value is None else _text(value, name)


def _decimal(value: Decimal | int | str, name: str) -> Decimal:
    try:
        normalized = Decimal(value)
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{name} must be a decimal value") from error
    if not normalized.is_finite():
        raise ValueError(f"{name} must be finite")
    return normalized


def _aware(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _unique_text(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    normalized = tuple(_text(value, name) for value in values)
    if len({value.casefold() for value in normalized}) != len(normalized):
        raise ValueError(f"{name} must not contain duplicates")
    return normalized


class PeriodKind(StrEnum):
    FISCAL_YEAR = "fiscal_year"
    CALENDAR_YEAR = "calendar_year"
    LTM = "ltm"
    NTM = "ntm"
    CALENDARIZED = "calendarized"


class EstimateStatus(StrEnum):
    ACTUAL = "actual"
    ESTIMATE = "estimate"


class MetricBasis(StrEnum):
    REPORTED = "reported"
    ADJUSTED = "adjusted"


class FinancialUnit(StrEnum):
    UNITS = "units"
    THOUSAND = "thousand"
    MILLION = "million"
    BILLION = "billion"
    LAKH = "lakh"
    CRORE = "crore"
    PER_SHARE = "per_share"


class FinancialMetricName(StrEnum):
    REVENUE = "revenue"
    GROSS_PROFIT = "gross_profit"
    EBITDA = "ebitda"
    EBIT = "ebit"
    NET_INCOME = "net_income"
    EPS = "eps"
    CAPEX = "capex"


class MarketMetricKind(StrEnum):
    SHARE_PRICE = "share_price"
    MARKET_CAPITALIZATION = "market_capitalization"
    DILUTED_SHARES = "diluted_shares"
    BASIC_SHARES = "basic_shares"
    DEBT = "debt"
    CASH_AND_EQUIVALENTS = "cash_and_equivalents"
    PREFERRED_STOCK = "preferred_stock"
    MINORITY_INTEREST = "minority_interest"
    LEASE_LIABILITIES = "lease_liabilities"
    PENSION_DEFICIT = "pension_deficit"


class DataQualityFlag(StrEnum):
    VERIFIED = "verified"
    SOURCE_BACKED = "source_backed"
    ESTIMATED = "estimated"
    STALE = "stale"
    PARTIAL = "partial"
    MISSING = "missing"
    INCOMPLETE = "incomplete"
    CONFLICTING = "conflicting"
    NOT_COMPARABLE = "not_comparable"


class ShareCountBasis(StrEnum):
    BASIC_END_OF_PERIOD = "basic_end_of_period"
    DILUTED_END_OF_PERIOD = "diluted_end_of_period"
    BASIC_WEIGHTED_AVERAGE = "basic_weighted_average"
    DILUTED_WEIGHTED_AVERAGE = "diluted_weighted_average"


class ProfileCompletenessStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"


class ProfileIssueKind(StrEnum):
    INVALID = "invalid"
    UNSUPPORTED = "unsupported"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"
    MISSING = "missing"
    PROVIDER_FAILURE = "provider_failure"


class SelectionDecision(StrEnum):
    INCLUDE = "include"
    EXCLUDE = "exclude"
    REVIEW = "review"


class SimilarityMethod(StrEnum):
    DETERMINISTIC = "deterministic"
    SEMANTIC = "semantic"


class MultipleKind(StrEnum):
    EV_REVENUE = "ev_revenue"
    EV_EBITDA = "ev_ebitda"
    EV_EBIT = "ev_ebit"
    PRICE_EARNINGS = "price_earnings"


class ValueFamily(StrEnum):
    ENTERPRISE_VALUE = "enterprise_value"
    EQUITY_VALUE = "equity_value"
    SHARE_PRICE = "share_price"


class MultipleStatus(StrEnum):
    INCLUDED = "included"
    EXCLUDED = "excluded"
    NOT_MEANINGFUL = "not_meaningful"
    MISSING_INPUT = "missing_input"


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    """One source observation supporting an input or qualitative decision."""

    evidence_id: str
    source_type: str
    source_name: str
    observed_at: datetime
    source_locator: str | None = None
    document_id: str | None = None
    chunk_id: str | None = None
    page_numbers: tuple[int, ...] = ()
    excerpt: str | None = None
    published_at: datetime | None = None
    section: str | None = None
    extraction_method: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("evidence_id", "source_type", "source_name"):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), field_name))
        for field_name in (
            "source_locator",
            "document_id",
            "chunk_id",
            "excerpt",
            "section",
            "extraction_method",
        ):
            object.__setattr__(
                self, field_name, _optional_text(getattr(self, field_name), field_name)
            )
        object.__setattr__(self, "observed_at", _aware(self.observed_at, "observed_at"))
        if self.published_at is not None:
            object.__setattr__(self, "published_at", _aware(self.published_at, "published_at"))
        if any(page < 1 for page in self.page_numbers):
            raise ValueError("page_numbers must be positive")
        if len(set(self.page_numbers)) != len(self.page_numbers):
            raise ValueError("page_numbers must be unique")


@dataclass(frozen=True, slots=True)
class FinancialPeriod:
    """Explicit observation window and actual/estimate status for a financial metric."""

    kind: PeriodKind
    label: str
    estimate_status: EstimateStatus
    start_date: date | None = None
    end_date: date | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", _text(self.label, "period label"))
        compact_label = self.label.upper().replace(" ", "")
        patterns = {
            PeriodKind.FISCAL_YEAR: r"FY\d{4}[AE]?",
            PeriodKind.CALENDAR_YEAR: r"CY\d{4}[AE]?",
            PeriodKind.LTM: r"LTM.*",
            PeriodKind.NTM: r"NTM.*",
            PeriodKind.CALENDARIZED: r"CAL(?:ENDARIZED)?.+",
        }
        if re.fullmatch(patterns[self.kind], compact_label) is None:
            raise ValueError(f"period label is invalid for {self.kind.value}")
        if compact_label.endswith("E") and self.estimate_status is not EstimateStatus.ESTIMATE:
            raise ValueError("an E-suffixed period must be an estimate")
        if compact_label.endswith("A") and self.estimate_status is not EstimateStatus.ACTUAL:
            raise ValueError("an A-suffixed period must be actual")
        if (self.start_date is None) != (self.end_date is None) and (
            self.kind not in {PeriodKind.LTM, PeriodKind.NTM} or self.end_date is None
        ):
            raise ValueError("period start_date and end_date must be supplied together")
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError("period start_date must not be after end_date")
        if self.kind in {PeriodKind.LTM, PeriodKind.NTM} and self.end_date is None:
            raise ValueError("LTM and NTM periods require an end_date")


@dataclass(frozen=True, slots=True)
class CompanyIdentity:
    """Provider-neutral legal/listing identity used by targets and comparable companies."""

    company_id: str
    name: str
    ticker: str | None = None
    exchange: str | None = None
    country: str | None = None
    identifiers: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "company_id", _text(self.company_id, "company_id"))
        object.__setattr__(self, "name", _text(self.name, "company name"))
        for field_name in ("ticker", "exchange", "country"):
            object.__setattr__(
                self, field_name, _optional_text(getattr(self, field_name), field_name)
            )
        normalized = tuple(
            (_text(scheme, "identifier scheme"), _text(value, "identifier value"))
            for scheme, value in self.identifiers
        )
        keys = {(scheme.casefold(), value.casefold()) for scheme, value in normalized}
        if len(keys) != len(normalized):
            raise ValueError("identifiers must not contain duplicates")
        object.__setattr__(self, "identifiers", normalized)


@dataclass(frozen=True, slots=True)
class TargetCompany:
    identity: CompanyIdentity
    industry: str | None = None
    sub_industry: str | None = None
    fiscal_year_end: str | None = None
    reporting_currency: str | None = None
    business_description: str | None = None
    customer_type: str | None = None
    business_model: str | None = None
    evidence: tuple[EvidenceReference, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "industry",
            "sub_industry",
            "business_description",
            "customer_type",
            "business_model",
        ):
            object.__setattr__(
                self, field_name, _optional_text(getattr(self, field_name), field_name)
            )
        if self.fiscal_year_end is not None:
            normalized = self.fiscal_year_end.strip()
            if _FISCAL_YEAR_END_PATTERN.fullmatch(normalized) is None:
                raise ValueError("fiscal_year_end must use MM-DD")
            object.__setattr__(self, "fiscal_year_end", normalized)
        if self.reporting_currency is not None:
            currency = self.reporting_currency.strip().upper()
            if _CURRENCY_PATTERN.fullmatch(currency) is None:
                raise ValueError("reporting_currency must be a three-letter ISO-style code")
            object.__setattr__(self, "reporting_currency", currency)


@dataclass(frozen=True, slots=True)
class ComparableCompany:
    identity: CompanyIdentity
    industry: str | None = None
    sub_industry: str | None = None
    business_description: str | None = None
    evidence: tuple[EvidenceReference, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("industry", "sub_industry", "business_description"):
            object.__setattr__(
                self, field_name, _optional_text(getattr(self, field_name), field_name)
            )


@dataclass(frozen=True, slots=True)
class FinancialMetric:
    """A source-backed metric whose value and semantic qualifiers cannot be separated."""

    metric_id: str
    name: FinancialMetricName
    value: Decimal
    currency: str
    unit: FinancialUnit
    period: FinancialPeriod
    basis: MetricBasis
    evidence: tuple[EvidenceReference, ...]
    quality_flags: tuple[DataQualityFlag, ...] = ()
    as_of: datetime | None = None
    adjustment_label: str | None = None
    notes: str | None = None
    source_observation_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "metric_id", _text(self.metric_id, "metric_id"))
        object.__setattr__(self, "value", _decimal(self.value, "metric value"))
        currency = self.currency.strip().upper()
        if not _CURRENCY_PATTERN.fullmatch(currency):
            raise ValueError("currency must be a three-letter ISO-style code")
        object.__setattr__(self, "currency", currency)
        if self.name is FinancialMetricName.EPS and self.unit is not FinancialUnit.PER_SHARE:
            raise ValueError("EPS must use the per_share unit")
        if self.name is not FinancialMetricName.EPS and self.unit is FinancialUnit.PER_SHARE:
            raise ValueError("only EPS may use the per_share unit")
        if not self.evidence:
            raise ValueError("financial metrics require evidence")
        if len(set(self.quality_flags)) != len(self.quality_flags):
            raise ValueError("quality_flags must not contain duplicates")
        if self.as_of is not None:
            object.__setattr__(self, "as_of", _aware(self.as_of, "as_of"))
        for field_name in ("adjustment_label", "notes"):
            object.__setattr__(
                self, field_name, _optional_text(getattr(self, field_name), field_name)
            )
        if self.basis is MetricBasis.ADJUSTED and self.adjustment_label is None:
            raise ValueError("adjusted metrics require an adjustment_label")
        if self.basis is MetricBasis.REPORTED and self.adjustment_label is not None:
            raise ValueError("reported metrics must not have an adjustment_label")
        object.__setattr__(
            self,
            "source_observation_ids",
            _unique_text(self.source_observation_ids, "source_observation_ids"),
        )

    def to_dict(self) -> dict[str, object]:
        """Return precise schema-versioned primitives suitable for JSON."""

        return {
            "schema_version": 1,
            "metric_id": self.metric_id,
            "name": self.name.value,
            "value": str(self.value),
            "currency": self.currency,
            "unit": self.unit.value,
            "period": {
                "kind": self.period.kind.value,
                "label": self.period.label,
                "estimate_status": self.period.estimate_status.value,
                "start_date": (
                    None if self.period.start_date is None else self.period.start_date.isoformat()
                ),
                "end_date": (
                    None if self.period.end_date is None else self.period.end_date.isoformat()
                ),
            },
            "basis": self.basis.value,
            "evidence": [_evidence_to_dict(item) for item in self.evidence],
            "quality_flags": [item.value for item in self.quality_flags],
            "as_of": None if self.as_of is None else self.as_of.isoformat(),
            "adjustment_label": self.adjustment_label,
            "notes": self.notes,
            "source_observation_ids": list(self.source_observation_ids),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> Self:
        """Reconstruct a metric from its versioned primitive representation."""

        if data.get("schema_version") != 1:
            raise ValueError("financial metric schema_version must be 1")
        try:
            period_data = _mapping(data["period"], "period")
            evidence_data = _sequence(data["evidence"], "evidence")
            flags_data = _sequence(data.get("quality_flags", []), "quality_flags")
            return cls(
                metric_id=_string(data["metric_id"], "metric_id"),
                name=FinancialMetricName(_string(data["name"], "name")),
                value=Decimal(_string(data["value"], "value")),
                currency=_string(data["currency"], "currency"),
                unit=FinancialUnit(_string(data["unit"], "unit")),
                period=FinancialPeriod(
                    kind=PeriodKind(_string(period_data["kind"], "period.kind")),
                    label=_string(period_data["label"], "period.label"),
                    estimate_status=EstimateStatus(
                        _string(period_data["estimate_status"], "period.estimate_status")
                    ),
                    start_date=_optional_date(period_data.get("start_date"), "period.start_date"),
                    end_date=_optional_date(period_data.get("end_date"), "period.end_date"),
                ),
                basis=MetricBasis(_string(data["basis"], "basis")),
                evidence=tuple(
                    _evidence_from_dict(_mapping(item, "evidence item")) for item in evidence_data
                ),
                quality_flags=tuple(
                    DataQualityFlag(_string(item, "quality flag")) for item in flags_data
                ),
                as_of=_optional_datetime(data.get("as_of"), "as_of"),
                adjustment_label=_none_or_string(data.get("adjustment_label"), "adjustment_label"),
                notes=_none_or_string(data.get("notes"), "notes"),
                source_observation_ids=tuple(
                    _string(item, "source_observation_id")
                    for item in _sequence(
                        data.get("source_observation_ids", []), "source_observation_ids"
                    )
                ),
            )
        except (KeyError, InvalidOperation, TypeError, ValueError) as error:
            raise ValueError(f"invalid financial metric: {error}") from error

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, value: str) -> Self:
        try:
            data = json.loads(value)
        except json.JSONDecodeError as error:
            raise ValueError("invalid financial metric JSON") from error
        return cls.from_dict(_mapping(data, "financial metric JSON"))


@dataclass(frozen=True, slots=True)
class MarketMetric:
    """A non-negative market or capital-structure observation at a precise time."""

    metric_id: str
    kind: MarketMetricKind
    value: Decimal
    unit: FinancialUnit
    as_of: datetime
    evidence: tuple[EvidenceReference, ...]
    currency: str | None = None
    quality_flags: tuple[DataQualityFlag, ...] = ()
    share_basis: ShareCountBasis | None = None
    notes: str | None = None
    source_observation_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "metric_id", _text(self.metric_id, "metric_id"))
        normalized_value = _decimal(self.value, "market metric value")
        if normalized_value < 0:
            raise ValueError("market metric value must not be negative")
        object.__setattr__(self, "value", normalized_value)
        object.__setattr__(self, "as_of", _aware(self.as_of, "as_of"))
        if self.kind in {MarketMetricKind.DILUTED_SHARES, MarketMetricKind.BASIC_SHARES}:
            if self.currency is not None:
                raise ValueError("share counts must not have a currency")
            if self.unit is FinancialUnit.PER_SHARE:
                raise ValueError("share counts cannot use the per_share unit")
            if self.share_basis is None:
                raise ValueError("share counts require share_basis")
            diluted_bases = {
                ShareCountBasis.DILUTED_END_OF_PERIOD,
                ShareCountBasis.DILUTED_WEIGHTED_AVERAGE,
            }
            if (
                self.kind is MarketMetricKind.DILUTED_SHARES
                and self.share_basis not in diluted_bases
            ):
                raise ValueError("diluted shares require a diluted share_basis")
            if self.kind is MarketMetricKind.BASIC_SHARES and self.share_basis in diluted_bases:
                raise ValueError("basic shares require a basic share_basis")
        else:
            if self.share_basis is not None:
                raise ValueError("only share counts may have share_basis")
            if self.currency is None:
                raise ValueError("monetary market metrics require currency")
            currency = self.currency.strip().upper()
            if not _CURRENCY_PATTERN.fullmatch(currency):
                raise ValueError("currency must be a three-letter ISO-style code")
            object.__setattr__(self, "currency", currency)
        if self.kind is MarketMetricKind.SHARE_PRICE and self.unit is not FinancialUnit.PER_SHARE:
            raise ValueError("share price must use the per_share unit")
        if self.kind is not MarketMetricKind.SHARE_PRICE and self.unit is FinancialUnit.PER_SHARE:
            raise ValueError("only share price may use the per_share market unit")
        if not self.evidence:
            raise ValueError("market metrics require evidence")
        if len(set(self.quality_flags)) != len(self.quality_flags):
            raise ValueError("quality_flags must not contain duplicates")
        object.__setattr__(self, "notes", _optional_text(self.notes, "notes"))
        object.__setattr__(
            self,
            "source_observation_ids",
            _unique_text(self.source_observation_ids, "source_observation_ids"),
        )


@dataclass(frozen=True, slots=True)
class CapitalStructure:
    """Auditable collection of capital-structure observations under a named policy."""

    snapshot_id: str
    as_of: datetime
    policy_id: str
    components: tuple[MarketMetric, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", _text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "policy_id", _text(self.policy_id, "policy_id"))
        object.__setattr__(self, "as_of", _aware(self.as_of, "as_of"))
        if not self.components:
            raise ValueError("capital structure requires components")
        if len({item.metric_id for item in self.components}) != len(self.components):
            raise ValueError("capital structure component IDs must be unique")
        if any(item.as_of > self.as_of for item in self.components):
            raise ValueError("capital structure components must not post-date the snapshot")


@dataclass(frozen=True, slots=True)
class EnterpriseValueSnapshot:
    """Future deterministic EV output with complete input lineage."""

    snapshot_id: str
    as_of: datetime
    equity_value: Decimal
    enterprise_value: Decimal
    currency: str
    unit: FinancialUnit
    capital_structure_id: str
    input_metric_ids: tuple[str, ...]
    policy_id: str

    def __post_init__(self) -> None:
        for field_name in ("snapshot_id", "capital_structure_id", "policy_id"):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), field_name))
        object.__setattr__(self, "as_of", _aware(self.as_of, "as_of"))
        equity_value = _decimal(self.equity_value, "equity_value")
        if equity_value < 0:
            raise ValueError("equity_value must not be negative")
        object.__setattr__(self, "equity_value", equity_value)
        object.__setattr__(
            self, "enterprise_value", _decimal(self.enterprise_value, "enterprise_value")
        )
        currency = self.currency.strip().upper()
        if not _CURRENCY_PATTERN.fullmatch(currency):
            raise ValueError("currency must be a three-letter ISO-style code")
        object.__setattr__(self, "currency", currency)
        if self.unit is FinancialUnit.PER_SHARE:
            raise ValueError("enterprise value cannot use per_share unit")
        object.__setattr__(
            self, "input_metric_ids", _unique_text(self.input_metric_ids, "input_metric_ids")
        )
        if not self.input_metric_ids:
            raise ValueError("enterprise value requires input_metric_ids")


@dataclass(frozen=True, slots=True)
class FinancialObservation:
    """A parsed but source-aligned fact before canonical name and unit normalization."""

    observation_id: str
    raw_metric_name: str
    value: Decimal
    unit: str | None
    evidence: tuple[EvidenceReference, ...]
    currency: str | None = None
    period: FinancialPeriod | None = None
    as_of: datetime | None = None
    basis: MetricBasis | None = None
    adjustment_label: str | None = None
    notes: str | None = None
    quality_flags: tuple[DataQualityFlag, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "observation_id", _text(self.observation_id, "observation_id"))
        object.__setattr__(self, "raw_metric_name", _text(self.raw_metric_name, "raw_metric_name"))
        object.__setattr__(self, "value", _decimal(self.value, "observation value"))
        object.__setattr__(self, "unit", _optional_text(self.unit, "unit"))
        if self.currency is not None:
            currency = self.currency.strip().upper()
            if _CURRENCY_PATTERN.fullmatch(currency) is None:
                raise ValueError("currency must be a three-letter ISO-style code")
            object.__setattr__(self, "currency", currency)
        if self.as_of is not None:
            object.__setattr__(self, "as_of", _aware(self.as_of, "as_of"))
        for field_name in ("adjustment_label", "notes"):
            object.__setattr__(
                self, field_name, _optional_text(getattr(self, field_name), field_name)
            )
        if not self.evidence:
            raise ValueError("financial observations require evidence")
        if len(set(self.quality_flags)) != len(self.quality_flags):
            raise ValueError("quality_flags must not contain duplicates")


@dataclass(frozen=True, slots=True)
class NormalizationDecision:
    observation_id: str
    output_metric_id: str
    raw_metric_name: str
    normalized_name: str
    source_unit: str
    target_unit: FinancialUnit
    conversion_factor: Decimal
    policy_id: str
    note: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "observation_id",
            "output_metric_id",
            "raw_metric_name",
            "normalized_name",
            "source_unit",
            "policy_id",
        ):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), field_name))
        factor = _decimal(self.conversion_factor, "conversion_factor")
        if factor <= 0:
            raise ValueError("conversion_factor must be positive")
        object.__setattr__(self, "conversion_factor", factor)
        object.__setattr__(self, "note", _optional_text(self.note, "note"))


@dataclass(frozen=True, slots=True)
class ProfileIssue:
    kind: ProfileIssueKind
    message: str
    observation_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "message", _text(self.message, "issue message"))
        object.__setattr__(
            self, "observation_ids", _unique_text(self.observation_ids, "observation_ids")
        )


@dataclass(frozen=True, slots=True)
class ProfileConflict:
    conflict_id: str
    field: str
    observation_ids: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "conflict_id", _text(self.conflict_id, "conflict_id"))
        object.__setattr__(self, "field", _text(self.field, "conflict field"))
        object.__setattr__(self, "reason", _text(self.reason, "conflict reason"))
        object.__setattr__(
            self, "observation_ids", _unique_text(self.observation_ids, "observation_ids")
        )
        if len(self.observation_ids) < 2:
            raise ValueError("a conflict requires at least two observations")


@dataclass(frozen=True, slots=True)
class ProfileCompleteness:
    present: tuple[str, ...]
    missing: tuple[str, ...]
    status: ProfileCompletenessStatus

    def __post_init__(self) -> None:
        object.__setattr__(self, "present", _unique_text(self.present, "present fields"))
        object.__setattr__(self, "missing", _unique_text(self.missing, "missing fields"))
        if {item.casefold() for item in self.present} & {item.casefold() for item in self.missing}:
            raise ValueError("a completeness field cannot be both present and missing")
        if self.status is ProfileCompletenessStatus.COMPLETE and self.missing:
            raise ValueError("complete status cannot contain missing fields")
        if self.status is ProfileCompletenessStatus.INSUFFICIENT and self.present:
            raise ValueError("insufficient status cannot contain present fields")


@dataclass(frozen=True, slots=True)
class DerivedFinancialValue:
    name: str
    value: Decimal
    currency: str
    unit: FinancialUnit
    as_of: datetime
    input_metric_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _text(self.name, "derived value name"))
        object.__setattr__(self, "value", _decimal(self.value, "derived value"))
        currency = self.currency.strip().upper()
        if _CURRENCY_PATTERN.fullmatch(currency) is None:
            raise ValueError("currency must be a three-letter ISO-style code")
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "as_of", _aware(self.as_of, "as_of"))
        object.__setattr__(
            self, "input_metric_ids", _unique_text(self.input_metric_ids, "input_metric_ids")
        )
        if not self.input_metric_ids:
            raise ValueError("derived values require input_metric_ids")


@dataclass(frozen=True, slots=True)
class TargetFinancialProfile:
    target: TargetCompany
    metrics: tuple[FinancialMetric, ...]
    capital_structure: CapitalStructure | None = None
    observations: tuple[FinancialObservation, ...] = ()
    normalization_decisions: tuple[NormalizationDecision, ...] = ()
    conflicts: tuple[ProfileConflict, ...] = ()
    completeness: ProfileCompleteness | None = None
    issues: tuple[ProfileIssue, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if len({item.metric_id for item in self.metrics}) != len(self.metrics):
            raise ValueError("target metric IDs must be unique")
        if len({item.observation_id for item in self.observations}) != len(self.observations):
            raise ValueError("target observation IDs must be unique")
        decision_ids = [item.output_metric_id for item in self.normalization_decisions]
        all_output_ids = {item.metric_id for item in self.metrics}
        if self.capital_structure is not None:
            all_output_ids.update(item.metric_id for item in self.capital_structure.components)
        if any(item not in all_output_ids for item in decision_ids):
            raise ValueError("normalization decisions must reference profile output metrics")
        if any(not item.strip() for item in self.warnings):
            raise ValueError("warnings must not contain blank values")

    def net_debt(self) -> DerivedFinancialValue | None:
        """Return debt minus cash only when one compatible, non-conflicting pair exists."""

        if self.capital_structure is None:
            return None
        debt = tuple(
            item
            for item in self.capital_structure.components
            if item.kind is MarketMetricKind.DEBT
            and DataQualityFlag.CONFLICTING not in item.quality_flags
        )
        cash = tuple(
            item
            for item in self.capital_structure.components
            if item.kind is MarketMetricKind.CASH_AND_EQUIVALENTS
            and DataQualityFlag.CONFLICTING not in item.quality_flags
        )
        if len(debt) != 1 or len(cash) != 1:
            return None
        debt_item, cash_item = debt[0], cash[0]
        if (
            debt_item.currency != cash_item.currency
            or debt_item.unit is not cash_item.unit
            or debt_item.as_of != cash_item.as_of
            or debt_item.currency is None
        ):
            return None
        return DerivedFinancialValue(
            name="net_debt",
            value=debt_item.value - cash_item.value,
            currency=debt_item.currency,
            unit=debt_item.unit,
            as_of=debt_item.as_of,
            input_metric_ids=(debt_item.metric_id, cash_item.metric_id),
        )

    def to_dict(self) -> dict[str, object]:
        from ma_comparable_valuation.serialization import target_profile_to_dict

        return target_profile_to_dict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> TargetFinancialProfile:
        from ma_comparable_valuation.serialization import target_profile_from_dict

        return target_profile_from_dict(data)

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, value: str) -> TargetFinancialProfile:
        try:
            data = json.loads(value)
        except json.JSONDecodeError as error:
            raise ValueError("invalid target financial profile JSON") from error
        return cls.from_dict(_mapping(data, "target financial profile JSON"))


@dataclass(frozen=True, slots=True)
class ComparableCompanySnapshot:
    company: ComparableCompany
    as_of: datetime
    financial_metrics: tuple[FinancialMetric, ...]
    market_metrics: tuple[MarketMetric, ...]
    enterprise_value: EnterpriseValueSnapshot | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", _aware(self.as_of, "as_of"))
        ids = tuple(
            [item.metric_id for item in self.financial_metrics]
            + [item.metric_id for item in self.market_metrics]
        )
        if len(set(ids)) != len(ids):
            raise ValueError("snapshot metric IDs must be unique")
        if any(item.as_of > self.as_of for item in self.market_metrics):
            raise ValueError("market metrics must not post-date the company snapshot")
        if self.enterprise_value is not None and self.enterprise_value.as_of > self.as_of:
            raise ValueError("enterprise value must not post-date the company snapshot")


@dataclass(frozen=True, slots=True)
class ComparableUniverse:
    universe_id: str
    target_id: str
    companies: tuple[ComparableCompany, ...]
    provider_name: str
    observed_at: datetime

    def __post_init__(self) -> None:
        for field_name in ("universe_id", "target_id", "provider_name"):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), field_name))
        object.__setattr__(self, "observed_at", _aware(self.observed_at, "observed_at"))
        ids = [item.identity.company_id for item in self.companies]
        if len(set(ids)) != len(ids):
            raise ValueError("comparable universe company IDs must be unique")


@dataclass(frozen=True, slots=True)
class SimilarityObservation:
    dimension: str
    method: SimilarityMethod
    assessment: str
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "dimension", _text(self.dimension, "dimension"))
        object.__setattr__(self, "assessment", _text(self.assessment, "assessment"))
        if not self.evidence:
            raise ValueError("similarity observations require evidence")


@dataclass(frozen=True, slots=True)
class PeerSelectionDecision:
    company_id: str
    decision: SelectionDecision
    rationale: str
    observations: tuple[SimilarityObservation, ...]
    evidence: tuple[EvidenceReference, ...]
    confidence: Decimal
    policy_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "company_id", _text(self.company_id, "company_id"))
        object.__setattr__(self, "rationale", _text(self.rationale, "rationale"))
        object.__setattr__(self, "policy_id", _text(self.policy_id, "policy_id"))
        confidence = _decimal(self.confidence, "confidence")
        if confidence < 0 or confidence > 1:
            raise ValueError("confidence must be between 0 and 1")
        object.__setattr__(self, "confidence", confidence)
        if not self.evidence:
            raise ValueError("peer selection decisions require evidence")


@dataclass(frozen=True, slots=True)
class ComparableSelectionResult:
    universe_id: str
    decisions: tuple[PeerSelectionDecision, ...]
    policy_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "universe_id", _text(self.universe_id, "universe_id"))
        object.__setattr__(self, "policy_id", _text(self.policy_id, "policy_id"))
        ids = [item.company_id for item in self.decisions]
        if len(set(ids)) != len(ids):
            raise ValueError("selection decisions must contain one decision per company")

    @property
    def selected_company_ids(self) -> tuple[str, ...]:
        return tuple(
            item.company_id for item in self.decisions if item.decision is SelectionDecision.INCLUDE
        )

    @property
    def rejected_company_ids(self) -> tuple[str, ...]:
        return tuple(
            item.company_id for item in self.decisions if item.decision is SelectionDecision.EXCLUDE
        )


@dataclass(frozen=True, slots=True)
class PeerSet:
    peer_set_id: str
    universe_id: str
    snapshots: tuple[ComparableCompanySnapshot, ...]
    decisions: tuple[PeerSelectionDecision, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "peer_set_id", _text(self.peer_set_id, "peer_set_id"))
        object.__setattr__(self, "universe_id", _text(self.universe_id, "universe_id"))
        snapshot_ids = {item.company.identity.company_id for item in self.snapshots}
        included_ids = {
            item.company_id for item in self.decisions if item.decision is SelectionDecision.INCLUDE
        }
        if snapshot_ids != included_ids:
            raise ValueError("peer snapshots must exactly match included selection decisions")


@dataclass(frozen=True, slots=True)
class MultipleDefinition:
    kind: MultipleKind
    numerator_family: ValueFamily
    denominator_metric: FinancialMetricName

    def __post_init__(self) -> None:
        allowed = {
            MultipleKind.EV_REVENUE: {
                (
                    ValueFamily.ENTERPRISE_VALUE,
                    FinancialMetricName.REVENUE,
                )
            },
            MultipleKind.EV_EBITDA: {
                (
                    ValueFamily.ENTERPRISE_VALUE,
                    FinancialMetricName.EBITDA,
                )
            },
            MultipleKind.EV_EBIT: {(ValueFamily.ENTERPRISE_VALUE, FinancialMetricName.EBIT)},
            MultipleKind.PRICE_EARNINGS: {
                (ValueFamily.EQUITY_VALUE, FinancialMetricName.NET_INCOME),
                (ValueFamily.SHARE_PRICE, FinancialMetricName.EPS),
            },
        }[self.kind]
        if (self.numerator_family, self.denominator_metric) not in allowed:
            raise ValueError(f"invalid numerator/denominator for {self.kind.value}")


@dataclass(frozen=True, slots=True)
class TradingMultiple:
    """Future calculated observation; M0 defines lineage and treatment, not arithmetic."""

    multiple_id: str
    company_id: str
    definition: MultipleDefinition
    numerator_id: str
    denominator_id: str
    status: MultipleStatus
    policy_id: str
    value: Decimal | None = None
    treatment_reason: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "multiple_id",
            "company_id",
            "numerator_id",
            "denominator_id",
            "policy_id",
        ):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), field_name))
        object.__setattr__(
            self, "treatment_reason", _optional_text(self.treatment_reason, "treatment_reason")
        )
        if self.status is MultipleStatus.INCLUDED:
            if self.value is None:
                raise ValueError("included multiples require a value")
            if self.treatment_reason is not None:
                raise ValueError("included multiples must not have a treatment_reason")
        else:
            if self.treatment_reason is None:
                raise ValueError("non-included multiples require a treatment_reason")
        if self.value is not None:
            normalized = _decimal(self.value, "multiple value")
            if normalized < 0:
                raise ValueError("multiple value must not be negative")
            object.__setattr__(self, "value", normalized)


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{name} must be an object with string keys")
    return value


def _sequence(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    return value


def _string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return value


def _optional_date(value: object, name: str) -> date | None:
    return None if value is None else date.fromisoformat(_string(value, name))


def _optional_datetime(value: object, name: str) -> datetime | None:
    return None if value is None else datetime.fromisoformat(_string(value, name))


def _evidence_to_dict(value: EvidenceReference) -> dict[str, object]:
    return {
        "evidence_id": value.evidence_id,
        "source_type": value.source_type,
        "source_name": value.source_name,
        "observed_at": value.observed_at.isoformat(),
        "source_locator": value.source_locator,
        "document_id": value.document_id,
        "chunk_id": value.chunk_id,
        "page_numbers": list(value.page_numbers),
        "excerpt": value.excerpt,
        "published_at": None if value.published_at is None else value.published_at.isoformat(),
        "section": value.section,
        "extraction_method": value.extraction_method,
    }


def _evidence_from_dict(data: Mapping[str, object]) -> EvidenceReference:
    pages = _sequence(data.get("page_numbers", []), "page_numbers")
    return EvidenceReference(
        evidence_id=_string(data["evidence_id"], "evidence_id"),
        source_type=_string(data["source_type"], "source_type"),
        source_name=_string(data["source_name"], "source_name"),
        observed_at=datetime.fromisoformat(_string(data["observed_at"], "observed_at")),
        source_locator=_none_or_string(data.get("source_locator"), "source_locator"),
        document_id=_none_or_string(data.get("document_id"), "document_id"),
        chunk_id=_none_or_string(data.get("chunk_id"), "chunk_id"),
        page_numbers=tuple(_positive_int(item, "page number") for item in pages),
        excerpt=_none_or_string(data.get("excerpt"), "excerpt"),
        published_at=_optional_datetime(data.get("published_at"), "published_at"),
        section=_none_or_string(data.get("section"), "section"),
        extraction_method=_none_or_string(data.get("extraction_method"), "extraction_method"),
    )


def _none_or_string(value: object, name: str) -> str | None:
    return None if value is None else _string(value, name)


def _positive_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value
