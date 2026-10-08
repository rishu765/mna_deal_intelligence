"""Deterministic numeric, unit, period, and financial observation normalization."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from ma_precedent_transactions.domain import (
    CapitalStructureComponent,
    ConsiderationComponent,
    EstimateStatus,
    EvidenceReference,
    FactStatus,
    FinancialMetric,
    FinancialPeriod,
    FinancialUnit,
    MonetaryAmount,
    OwnershipObservation,
    PeriodKind,
    ValuationBasis,
    ValuationMeasure,
    ValuationObservation,
)
from ma_precedent_transactions.errors import NormalizationError
from ma_precedent_transactions.extraction.models import (
    CapitalFactObservation,
    ConsiderationObservation,
    FinancialFactObservation,
    OwnershipFactObservation,
    RawMoney,
    ValuationFactObservation,
)

_UNIT_ALIASES = {
    "unit": FinancialUnit.UNITS,
    "units": FinancialUnit.UNITS,
    "thousand": FinancialUnit.THOUSAND,
    "thousands": FinancialUnit.THOUSAND,
    "k": FinancialUnit.THOUSAND,
    "million": FinancialUnit.MILLION,
    "millions": FinancialUnit.MILLION,
    "mn": FinancialUnit.MILLION,
    "mm": FinancialUnit.MILLION,
    "billion": FinancialUnit.BILLION,
    "billions": FinancialUnit.BILLION,
    "bn": FinancialUnit.BILLION,
    "lakh": FinancialUnit.LAKH,
    "lakhs": FinancialUnit.LAKH,
    "crore": FinancialUnit.CRORE,
    "crores": FinancialUnit.CRORE,
    "cr": FinancialUnit.CRORE,
    "per share": FinancialUnit.PER_SHARE,
    "per_share": FinancialUnit.PER_SHARE,
}

_TO_MILLION = {
    FinancialUnit.UNITS: Decimal("0.000001"),
    FinancialUnit.THOUSAND: Decimal("0.001"),
    FinancialUnit.MILLION: Decimal("1"),
    FinancialUnit.BILLION: Decimal("1000"),
    FinancialUnit.LAKH: Decimal("0.1"),
    FinancialUnit.CRORE: Decimal("10"),
}

_FY = re.compile(r"^FY\s*(\d{4})(E|A)?$", re.IGNORECASE)
_LTM = re.compile(r"^LTM\s+([A-Za-z]{3,9})[- ](\d{4})$", re.IGNORECASE)
_MONTHS = {
    name: month
    for month, names in enumerate(
        (
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ),
        start=1,
    )
    for name in names
}


@dataclass(frozen=True, slots=True)
class NormalizationDecision:
    observation_id: str
    output_id: str
    source_unit: str
    target_unit: FinancialUnit
    conversion_factor: Decimal
    source_period: str | None = None
    normalized_period: str | None = None


def parse_decimal(raw: str, *, allow_negative: bool) -> Decimal:
    value = raw.strip().replace(",", "")
    if value.startswith("(") and value.endswith(")"):
        value = f"-{value[1:-1]}"
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError) as error:
        raise NormalizationError(f"invalid decimal value: {raw}") from error
    if not parsed.is_finite():
        raise NormalizationError("numeric value must be finite")
    if parsed < 0 and not allow_negative:
        raise NormalizationError("negative value is not allowed for this fact")
    return parsed


def parse_unit(raw: str) -> FinancialUnit:
    key = " ".join(raw.casefold().replace("-", " ").split())
    try:
        return _UNIT_ALIASES[key]
    except KeyError as error:
        raise NormalizationError(f"unsupported financial unit: {raw}") from error


def convert_unit(
    value: Decimal, source: FinancialUnit, target: FinancialUnit
) -> tuple[Decimal, Decimal]:
    if source is target:
        return value, Decimal("1")
    if source is FinancialUnit.PER_SHARE or target is FinancialUnit.PER_SHARE:
        raise NormalizationError("per-share amounts cannot be converted to aggregate units")
    try:
        factor = _TO_MILLION[source] / _TO_MILLION[target]
    except KeyError as error:
        raise NormalizationError("unsupported unit conversion") from error
    return value * factor, factor


def normalize_money(
    raw: RawMoney, *, target_unit: FinancialUnit | None = None
) -> tuple[MonetaryAmount, Decimal]:
    source_unit = parse_unit(raw.unit)
    value = parse_decimal(raw.value, allow_negative=False)
    desired = target_unit or source_unit
    normalized, factor = convert_unit(value, source_unit, desired)
    return MonetaryAmount(normalized, raw.currency, desired, raw.measurement_date), factor


def normalize_period(raw: str) -> FinancialPeriod:
    label = " ".join(raw.strip().split())
    fy = _FY.fullmatch(label)
    if fy:
        year = int(fy.group(1))
        suffix = (fy.group(2) or "A").upper()
        return FinancialPeriod(
            PeriodKind.FISCAL_YEAR,
            f"FY{year}{suffix}",
            EstimateStatus.FORECAST if suffix == "E" else EstimateStatus.HISTORICAL,
            date(year, 1, 1),
            date(year, 12, 31),
        )
    ltm = _LTM.fullmatch(label)
    if ltm:
        month_name, year_text = ltm.groups()
        try:
            month = _MONTHS[month_name.casefold()]
        except KeyError as error:
            raise NormalizationError(f"unsupported LTM month: {month_name}") from error
        year = int(year_text)
        next_month = date(year + (month == 12), month % 12 + 1, 1)
        end = next_month.fromordinal(next_month.toordinal() - 1)
        start_next = date(year - 1 + (month == 12), month % 12 + 1, 1)
        start = start_next
        return FinancialPeriod(
            PeriodKind.LTM,
            f"LTM {end.strftime('%b-%Y')}",
            EstimateStatus.HISTORICAL,
            start,
            end,
        )
    raise NormalizationError(f"unsupported financial period: {raw}")


class FinancialNormalizationService:
    def __init__(self, evidence: tuple[EvidenceReference, ...]) -> None:
        self._evidence = {item.evidence_id: item for item in evidence}

    def evidence_for(self, evidence_ids: tuple[str, ...]) -> tuple[EvidenceReference, ...]:
        try:
            return tuple(self._evidence[value] for value in evidence_ids)
        except KeyError as error:
            raise NormalizationError(f"unknown evidence ID: {error.args[0]}") from error

    def consideration(
        self, observation: ConsiderationObservation
    ) -> tuple[ConsiderationComponent, NormalizationDecision | None]:
        amount = None
        decision = None
        if observation.amount is not None:
            amount, factor = normalize_money(observation.amount)
            decision = NormalizationDecision(
                observation.observation_id,
                f"consideration:{observation.observation_id}",
                observation.amount.unit,
                amount.unit,
                factor,
            )
        quantity = (
            None
            if observation.quantity is None
            else parse_decimal(observation.quantity, allow_negative=False)
        )
        return (
            ConsiderationComponent(
                component_id=f"consideration:{observation.observation_id}",
                kind=observation.kind,
                fact_status=FactStatus.DIRECTLY_DISCLOSED,
                evidence=self.evidence_for(observation.evidence_ids),
                amount=amount,
                quantity=quantity,
                quantity_unit=observation.quantity_unit,
                description=observation.source_wording,
            ),
            decision,
        )

    def ownership(self, observation: OwnershipFactObservation) -> OwnershipObservation:
        def parse(value: str | None) -> Decimal | None:
            return None if value is None else parse_decimal(value, allow_negative=False)

        return OwnershipObservation(
            observation_id=f"ownership:{observation.observation_id}",
            fact_status=FactStatus.DIRECTLY_DISCLOSED,
            evidence=self.evidence_for(observation.evidence_ids),
            pre_deal_percent=parse(observation.pre_deal_percent),
            acquired_percent=parse(observation.acquired_percent),
            post_deal_percent=parse(observation.post_deal_percent),
            notes=observation.notes,
        )

    def valuation(
        self, observation: ValuationFactObservation
    ) -> tuple[ValuationObservation, NormalizationDecision | None]:
        if observation.amount is None:
            return (
                ValuationObservation(
                    observation_id=f"valuation:{observation.observation_id}",
                    measure=observation.measure,
                    basis=ValuationBasis.UNAVAILABLE,
                    fact_status=FactStatus.UNKNOWN,
                    evidence=self.evidence_for(observation.evidence_ids),
                    notes=observation.notes or observation.source_wording,
                ),
                None,
            )
        amount, factor = normalize_money(observation.amount)
        basis = (
            ValuationBasis.AMBIGUOUS
            if observation.ambiguous_basis
            else ValuationBasis.EXPLICITLY_DISCLOSED
        )
        return (
            ValuationObservation(
                observation_id=f"valuation:{observation.observation_id}",
                measure=observation.measure,
                basis=basis,
                fact_status=FactStatus.DIRECTLY_DISCLOSED,
                evidence=self.evidence_for(observation.evidence_ids),
                amount=amount,
                notes=observation.notes,
            ),
            NormalizationDecision(
                observation.observation_id,
                f"valuation:{observation.observation_id}",
                observation.amount.unit,
                amount.unit,
                factor,
            ),
        )

    def financial(
        self, observation: FinancialFactObservation
    ) -> tuple[FinancialMetric, NormalizationDecision]:
        source_unit = parse_unit(observation.unit)
        value = parse_decimal(observation.value, allow_negative=True)
        value, factor = convert_unit(value, source_unit, FinancialUnit.MILLION)
        period = normalize_period(observation.period)
        measurement_date = observation.measurement_date or period.end_date
        if measurement_date is None:
            raise NormalizationError("financial observation requires a measurement date")
        metric = FinancialMetric(
            metric_id=f"financial:{observation.observation_id}",
            name=observation.name,
            value=value,
            unit=FinancialUnit.MILLION,
            period=period,
            basis=observation.basis,
            measurement_date=measurement_date,
            fact_status=FactStatus.DIRECTLY_DISCLOSED,
            evidence=self.evidence_for(observation.evidence_ids),
            currency=observation.currency,
            adjustment_label=observation.adjustment_label,
            notes=observation.notes,
        )
        return metric, NormalizationDecision(
            observation.observation_id,
            metric.metric_id,
            observation.unit,
            FinancialUnit.MILLION,
            factor,
            observation.period,
            period.label,
        )

    def capital(self, observation: CapitalFactObservation) -> CapitalStructureComponent:
        if observation.amount is None:
            raise NormalizationError("capital observation has no amount")
        amount, _ = normalize_money(observation.amount, target_unit=FinancialUnit.MILLION)
        return CapitalStructureComponent(
            component_id=f"capital:{observation.observation_id}",
            kind=observation.kind,
            amount=amount,
            as_of=observation.as_of,
            fact_status=FactStatus.DIRECTLY_DISCLOSED,
            evidence=self.evidence_for(observation.evidence_ids),
            notes=observation.notes,
        )


def derive_enterprise_value(
    *,
    equity: ValuationObservation,
    debt: CapitalStructureComponent,
    cash: CapitalStructureComponent,
    observation_id: str,
) -> tuple[ValuationObservation, str]:
    if equity.measure is not ValuationMeasure.EQUITY_PURCHASE_PRICE or equity.amount is None:
        raise NormalizationError("EV bridge requires an available equity purchase price")
    amounts = (equity.amount, debt.amount, cash.amount)
    currencies = {item.currency for item in amounts}
    if len(currencies) != 1:
        raise NormalizationError("EV bridge inputs must use the same currency")
    normalized = []
    for item in amounts:
        value, _ = convert_unit(item.value, item.unit, FinancialUnit.MILLION)
        normalized.append(value)
    value = normalized[0] + normalized[1] - normalized[2]
    if value < 0:
        raise NormalizationError("derived enterprise value cannot be negative")
    evidence = tuple(dict.fromkeys((*equity.evidence, *debt.evidence, *cash.evidence)))
    trace = (
        f"EV = equity value {normalized[0]} + debt {normalized[1]} - cash {normalized[2]} "
        f"= {value} {equity.amount.currency} million"
    )
    return (
        ValuationObservation(
            observation_id=observation_id,
            measure=ValuationMeasure.TRANSACTION_ENTERPRISE_VALUE,
            basis=ValuationBasis.INDEPENDENTLY_CALCULATED,
            fact_status=FactStatus.DERIVED_FROM_DISCLOSED,
            evidence=evidence,
            amount=MonetaryAmount(
                value, equity.amount.currency, FinancialUnit.MILLION, equity.amount.measurement_date
            ),
            assumptions=(
                "Equity value, debt, and cash are explicitly disclosed in the same currency.",
                "No preferred stock, noncontrolling interest, or other adjustment is included.",
            ),
            notes=trace,
        ),
        trace,
    )
