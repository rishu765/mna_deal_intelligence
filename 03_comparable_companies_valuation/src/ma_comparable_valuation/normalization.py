"""Deterministic metric-name and unit normalization for target observations."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ma_comparable_valuation.domain import (
    DataQualityFlag,
    EstimateStatus,
    FinancialMetric,
    FinancialMetricName,
    FinancialObservation,
    FinancialUnit,
    MarketMetric,
    MarketMetricKind,
    MetricBasis,
    NormalizationDecision,
    ShareCountBasis,
)

NORMALIZATION_POLICY_ID = "target-financial-normalization-v1"

_UNIT_ALIASES = {
    "unit": FinancialUnit.UNITS,
    "units": FinancialUnit.UNITS,
    "one": FinancialUnit.UNITS,
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
    "lac": FinancialUnit.LAKH,
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


@dataclass(frozen=True, slots=True)
class MetricNameResolution:
    normalized_name: FinancialMetricName | MarketMetricKind
    implied_basis: MetricBasis | None = None
    share_basis: ShareCountBasis | None = None
    note: str | None = None


@dataclass(frozen=True, slots=True)
class NormalizedObservation:
    metric: FinancialMetric | MarketMetric
    decision: NormalizationDecision


_NAME_POLICY: dict[str, MetricNameResolution] = {
    "revenue": MetricNameResolution(FinancialMetricName.REVENUE),
    "net revenue": MetricNameResolution(FinancialMetricName.REVENUE),
    "net sales": MetricNameResolution(FinancialMetricName.REVENUE),
    "sales": MetricNameResolution(
        FinancialMetricName.REVENUE,
        note="Mapped 'sales' to revenue under the explicit V1 synonym policy.",
    ),
    "gross profit": MetricNameResolution(FinancialMetricName.GROSS_PROFIT),
    "ebitda": MetricNameResolution(FinancialMetricName.EBITDA),
    "adjusted ebitda": MetricNameResolution(
        FinancialMetricName.EBITDA,
        implied_basis=MetricBasis.ADJUSTED,
    ),
    "ebit": MetricNameResolution(FinancialMetricName.EBIT),
    "operating income": MetricNameResolution(
        FinancialMetricName.EBIT,
        note="Mapped operating income to EBIT under the V1 policy; review unusual presentations.",
    ),
    "net income": MetricNameResolution(FinancialMetricName.NET_INCOME),
    "net profit": MetricNameResolution(FinancialMetricName.NET_INCOME),
    "earnings per share": MetricNameResolution(FinancialMetricName.EPS),
    "eps": MetricNameResolution(FinancialMetricName.EPS),
    "capital expenditure": MetricNameResolution(FinancialMetricName.CAPEX),
    "capital expenditures": MetricNameResolution(FinancialMetricName.CAPEX),
    "capex": MetricNameResolution(FinancialMetricName.CAPEX),
    "cash": MetricNameResolution(MarketMetricKind.CASH_AND_EQUIVALENTS),
    "cash and cash equivalents": MetricNameResolution(MarketMetricKind.CASH_AND_EQUIVALENTS),
    "debt": MetricNameResolution(MarketMetricKind.DEBT),
    "total debt": MetricNameResolution(MarketMetricKind.DEBT),
    "preferred stock": MetricNameResolution(MarketMetricKind.PREFERRED_STOCK),
    "minority interest": MetricNameResolution(MarketMetricKind.MINORITY_INTEREST),
    "non-controlling interest": MetricNameResolution(MarketMetricKind.MINORITY_INTEREST),
    "diluted shares outstanding": MetricNameResolution(
        MarketMetricKind.DILUTED_SHARES,
        share_basis=ShareCountBasis.DILUTED_END_OF_PERIOD,
    ),
    "diluted weighted average shares": MetricNameResolution(
        MarketMetricKind.DILUTED_SHARES,
        share_basis=ShareCountBasis.DILUTED_WEIGHTED_AVERAGE,
    ),
    "basic shares outstanding": MetricNameResolution(
        MarketMetricKind.BASIC_SHARES,
        share_basis=ShareCountBasis.BASIC_END_OF_PERIOD,
    ),
    "basic weighted average shares": MetricNameResolution(
        MarketMetricKind.BASIC_SHARES,
        share_basis=ShareCountBasis.BASIC_WEIGHTED_AVERAGE,
    ),
}


def normalize_metric_name(raw_name: str) -> MetricNameResolution:
    """Resolve only documented exact synonyms; do not use fuzzy semantic collapsing."""

    key = " ".join(raw_name.casefold().replace("&", "and").split())
    try:
        return _NAME_POLICY[key]
    except KeyError as error:
        raise ValueError(f"unsupported financial metric name: {raw_name}") from error


def parse_financial_unit(raw_unit: str | None) -> FinancialUnit:
    if raw_unit is None:
        raise ValueError("financial observation is missing unit")
    key = " ".join(raw_unit.casefold().split())
    try:
        return _UNIT_ALIASES[key]
    except KeyError as error:
        raise ValueError(f"unsupported financial unit: {raw_unit}") from error


def convert_unit(
    value: Decimal, source: FinancialUnit, target: FinancialUnit
) -> tuple[Decimal, Decimal]:
    """Convert scale deterministically without crossing currencies."""

    if source is target:
        return value, Decimal("1")
    if source is FinancialUnit.PER_SHARE or target is FinancialUnit.PER_SHARE:
        raise ValueError("per-share values cannot be converted to or from money scales")
    factor = _TO_MILLION[source] / _TO_MILLION[target]
    return value * factor, factor


def normalize_observation(observation: FinancialObservation) -> NormalizedObservation:
    resolution = normalize_metric_name(observation.raw_metric_name)
    source_unit = parse_financial_unit(observation.unit)
    output_id = f"normalized:{observation.observation_id}"
    flags = list(observation.quality_flags)
    if DataQualityFlag.SOURCE_BACKED not in flags:
        flags.append(DataQualityFlag.SOURCE_BACKED)

    if isinstance(resolution.normalized_name, FinancialMetricName):
        if observation.currency is None:
            raise ValueError("financial statement metrics require currency")
        if observation.period is None:
            raise ValueError("financial statement metrics require period")
        basis = resolution.implied_basis or observation.basis
        if basis is None:
            raise ValueError("financial statement metrics require reported/adjusted basis")
        if resolution.implied_basis is not None and observation.basis not in {
            None,
            resolution.implied_basis,
        }:
            raise ValueError("metric name and reported/adjusted basis conflict")
        if (
            observation.period.estimate_status is EstimateStatus.ESTIMATE
            and DataQualityFlag.ESTIMATED not in flags
        ):
            flags.append(DataQualityFlag.ESTIMATED)
        if resolution.normalized_name is FinancialMetricName.EPS:
            if source_unit is not FinancialUnit.PER_SHARE:
                raise ValueError("EPS observations require a per-share unit")
            normalized_value, factor = observation.value, Decimal("1")
            target_unit = FinancialUnit.PER_SHARE
        else:
            normalized_value, factor = convert_unit(
                observation.value, source_unit, FinancialUnit.MILLION
            )
            target_unit = FinancialUnit.MILLION
        adjustment_label = observation.adjustment_label
        if basis is MetricBasis.ADJUSTED and adjustment_label is None:
            adjustment_label = observation.raw_metric_name
        metric: FinancialMetric | MarketMetric = FinancialMetric(
            metric_id=output_id,
            name=resolution.normalized_name,
            value=normalized_value,
            currency=observation.currency,
            unit=target_unit,
            period=observation.period,
            basis=basis,
            evidence=observation.evidence,
            quality_flags=tuple(flags),
            as_of=observation.as_of,
            adjustment_label=adjustment_label,
            notes=_join_notes(observation.notes, resolution.note),
            source_observation_ids=(observation.observation_id,),
        )
    else:
        if observation.as_of is None:
            raise ValueError("capital structure observations require as_of")
        if source_unit is FinancialUnit.PER_SHARE:
            raise ValueError("capital structure observations cannot use per-share unit")
        normalized_value, factor = convert_unit(
            observation.value, source_unit, FinancialUnit.MILLION
        )
        is_share_count = resolution.normalized_name in {
            MarketMetricKind.DILUTED_SHARES,
            MarketMetricKind.BASIC_SHARES,
        }
        if is_share_count and observation.currency is not None:
            raise ValueError("share-count observations must not have currency")
        if not is_share_count and observation.currency is None:
            raise ValueError("monetary capital structure observations require currency")
        metric = MarketMetric(
            metric_id=output_id,
            kind=resolution.normalized_name,
            value=normalized_value,
            unit=FinancialUnit.MILLION,
            as_of=observation.as_of,
            evidence=observation.evidence,
            currency=observation.currency,
            quality_flags=tuple(flags),
            share_basis=resolution.share_basis,
            notes=_join_notes(observation.notes, resolution.note),
            source_observation_ids=(observation.observation_id,),
        )

    return NormalizedObservation(
        metric=metric,
        decision=NormalizationDecision(
            observation_id=observation.observation_id,
            output_metric_id=output_id,
            raw_metric_name=observation.raw_metric_name,
            normalized_name=resolution.normalized_name.value,
            source_unit=observation.unit or "<missing>",
            target_unit=metric.unit,
            conversion_factor=factor,
            policy_id=NORMALIZATION_POLICY_ID,
            note=resolution.note,
        ),
    )


def _join_notes(first: str | None, second: str | None) -> str | None:
    values = tuple(value for value in (first, second) if value is not None)
    return " ".join(values) or None
