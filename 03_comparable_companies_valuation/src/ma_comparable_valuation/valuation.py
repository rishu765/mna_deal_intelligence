"""Deterministic trading-comps arithmetic and auditable valuation outputs."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import ROUND_FLOOR, Decimal
from enum import StrEnum
from typing import Protocol

from ma_comparable_valuation.domain import (
    CapitalStructure,
    ComparableCompanySnapshot,
    DataQualityFlag,
    EvidenceReference,
    FinancialMetric,
    FinancialMetricName,
    FinancialUnit,
    MarketMetric,
    MarketMetricKind,
    MetricBasis,
    MultipleDefinition,
    MultipleKind,
    MultipleStatus,
    PeerSet,
    ShareCountBasis,
    TargetFinancialProfile,
    TradingMultiple,
    ValueFamily,
)
from ma_comparable_valuation.normalization import convert_unit


class CalculationStatus(StrEnum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class CalculationInput:
    input_id: str
    label: str
    value: Decimal
    unit: FinancialUnit
    currency: str | None
    as_of: datetime | None
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
class EquityValueCalculation:
    calculation_id: str
    status: CalculationStatus
    value: Decimal | None
    currency: str | None
    unit: FinancialUnit | None
    price_date: datetime | None
    share_count_date: datetime | None
    trace: CalculationTrace
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EnterpriseValueCalculation:
    calculation_id: str
    company_id: str
    status: CalculationStatus
    equity_value: EquityValueCalculation
    value: Decimal | None
    currency: str | None
    unit: FinancialUnit | None
    as_of: datetime | None
    included_component_ids: tuple[str, ...]
    omitted_components: tuple[MarketMetricKind, ...]
    trace: CalculationTrace
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MultipleRequest:
    definition: MultipleDefinition
    period_label: str
    basis: MetricBasis

    @property
    def label(self) -> str:
        names = {
            MultipleKind.EV_REVENUE: "EV/Revenue",
            MultipleKind.EV_EBITDA: "EV/EBITDA",
            MultipleKind.EV_EBIT: "EV/EBIT",
            MultipleKind.PRICE_EARNINGS: "P/E",
        }
        return f"{self.period_label} {names[self.definition.kind]} ({self.basis.value})"


@dataclass(frozen=True, slots=True)
class PeerStatistics:
    statistics_id: str
    request: MultipleRequest
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
class PeerMultipleSet:
    set_id: str
    request: MultipleRequest
    multiples: tuple[TradingMultiple, ...]
    statistics: PeerStatistics
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValuationBridge:
    bridge_id: str
    status: CalculationStatus
    implied_enterprise_value: Decimal
    implied_equity_value: Decimal | None
    currency: str
    unit: FinancialUnit
    component_ids: tuple[str, ...]
    omitted_components: tuple[MarketMetricKind, ...]
    trace: CalculationTrace
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ImpliedValuation:
    valuation_id: str
    anchor: str
    multiple: Decimal
    target_metric_id: str
    value_family: ValueFamily
    implied_value: Decimal
    currency: str
    unit: FinancialUnit
    bridge: ValuationBridge | None
    implied_equity_value: Decimal | None
    implied_per_share: Decimal | None
    trace: CalculationTrace
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValuationRange:
    range_id: str
    request: MultipleRequest
    low: ImpliedValuation
    mid: ImpliedValuation
    high: ImpliedValuation
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValuationExplanation:
    status: CalculationStatus
    peer_set_assessment: str
    preferred_metrics: tuple[str, ...]
    key_drivers: tuple[str, ...]
    outlier_commentary: tuple[str, ...]
    range_interpretation: str
    risks_and_caveats: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValuationOutput:
    output_id: str
    target_id: str
    peer_set_id: str
    multiple_sets: tuple[PeerMultipleSet, ...]
    ranges: tuple[ValuationRange, ...]
    explanation: ValuationExplanation | None
    warnings: tuple[str, ...] = ()


class ValuationExplanationProvider(Protocol):
    """Receives authoritative structured results and returns prose only."""

    def explain(self, context: ValuationOutput) -> ValuationExplanation: ...


@dataclass(frozen=True, slots=True)
class ValuationPolicy:
    policy_id: str = "trading-comps-v1"
    max_share_date_gap_days: int = 7
    max_capital_date_gap_days: int = 550
    flag_iqr_outliers: bool = True
    exclude_iqr_outliers: bool = False
    low_statistic: str = "percentile_25"
    mid_statistic: str = "median"
    high_statistic: str = "percentile_75"


class ValuationEngine:
    """Deterministic EV, multiple, statistics, bridge, and range engine."""

    def __init__(self, policy: ValuationPolicy | None = None) -> None:
        self.policy = policy or ValuationPolicy()

    def equity_value(
        self, company_id: str, market_metrics: tuple[MarketMetric, ...]
    ) -> EquityValueCalculation:
        price = _single_market(market_metrics, MarketMetricKind.SHARE_PRICE)
        shares = _single_market(
            market_metrics,
            MarketMetricKind.DILUTED_SHARES,
            ShareCountBasis.DILUTED_END_OF_PERIOD,
        )
        calculation_id = f"equity-value:{company_id}"
        warnings: list[str] = []
        if price is None or shares is None:
            if price is None:
                warnings.append("One non-conflicting share price is required.")
            if shares is None:
                warnings.append("Diluted end-of-period shares are required.")
            return _empty_equity(calculation_id, self.policy.policy_id, tuple(warnings))
        if price.currency is None:
            warnings.append("Share price currency is unavailable.")
            return _empty_equity(calculation_id, self.policy.policy_id, tuple(warnings))
        date_gap = abs((price.as_of.date() - shares.as_of.date()).days)
        if date_gap > self.policy.max_share_date_gap_days:
            warnings.append("Share price and diluted-share dates exceed the policy tolerance.")
            return _empty_equity(calculation_id, self.policy.policy_id, tuple(warnings))
        if DataQualityFlag.STALE in price.quality_flags:
            warnings.append("Share price is stale and cannot support a current equity value.")
            return _empty_equity(calculation_id, self.policy.policy_id, tuple(warnings))
        share_value, _ = convert_unit(shares.value, shares.unit, FinancialUnit.MILLION)
        value = price.value * share_value
        trace = CalculationTrace(
            f"trace:{calculation_id}",
            "Equity Value = Share Price * Diluted End-of-Period Shares",
            (_market_input(price), _market_input(shares)),
            value,
            self.policy.policy_id,
        )
        return EquityValueCalculation(
            calculation_id,
            CalculationStatus.AVAILABLE,
            value,
            price.currency,
            FinancialUnit.MILLION,
            price.as_of,
            shares.as_of,
            trace,
        )

    def enterprise_value(self, snapshot: ComparableCompanySnapshot) -> EnterpriseValueCalculation:
        company_id = snapshot.company.identity.company_id
        equity = self.equity_value(company_id, snapshot.market_metrics)
        calculation_id = f"enterprise-value:{company_id}"
        warnings = list(equity.warnings)
        debt = _single_market(snapshot.market_metrics, MarketMetricKind.DEBT)
        cash = _single_market(snapshot.market_metrics, MarketMetricKind.CASH_AND_EQUIVALENTS)
        if equity.value is None or debt is None or cash is None:
            if debt is None or cash is None:
                warnings.append("Debt and cash are required bridge components.")
            return _empty_enterprise(
                calculation_id,
                company_id,
                snapshot.as_of,
                equity,
                tuple(warnings),
                self.policy.policy_id,
            )
        assert equity.currency is not None and equity.unit is not None
        optionals = {
            kind: _single_market(snapshot.market_metrics, kind)
            for kind in (MarketMetricKind.PREFERRED_STOCK, MarketMetricKind.MINORITY_INTEREST)
        }
        present = (debt, cash, *(item for item in optionals.values() if item is not None))
        if not _compatible_money(
            equity.currency, equity.unit, equity.price_date, present, self.policy
        ):
            warnings.append("Bridge currencies, units, or as-of dates are incompatible.")
            return _empty_enterprise(
                calculation_id,
                company_id,
                snapshot.as_of,
                equity,
                tuple(warnings),
                self.policy.policy_id,
            )
        values = {
            item.kind: convert_unit(item.value, item.unit, equity.unit)[0] for item in present
        }
        omitted = tuple(kind for kind, item in optionals.items() if item is None)
        if omitted:
            warnings.append(
                "Optional bridge components not supplied and omitted: "
                + ", ".join(item.value for item in omitted)
                + "."
            )
        value = (
            equity.value
            + values[MarketMetricKind.DEBT]
            + values.get(MarketMetricKind.PREFERRED_STOCK, Decimal("0"))
            + values.get(MarketMetricKind.MINORITY_INTEREST, Decimal("0"))
            - values[MarketMetricKind.CASH_AND_EQUIVALENTS]
        )
        trace = CalculationTrace(
            f"trace:{calculation_id}",
            "EV = Equity Value + Debt + Preferred Stock + Minority Interest - Cash",
            equity.trace.inputs + tuple(_market_input(item) for item in present),
            value,
            self.policy.policy_id,
            tuple(warnings),
        )
        return EnterpriseValueCalculation(
            calculation_id,
            company_id,
            CalculationStatus.AVAILABLE,
            equity,
            value,
            equity.currency,
            equity.unit,
            snapshot.as_of,
            tuple(item.metric_id for item in present),
            omitted,
            trace,
            tuple(warnings),
        )

    def multiple(
        self, snapshot: ComparableCompanySnapshot, request: MultipleRequest
    ) -> TradingMultiple:
        company_id = snapshot.company.identity.company_id
        denominator = _single_financial(
            snapshot.financial_metrics,
            request.definition.denominator_metric,
            request.period_label,
            request.basis,
        )
        multiple_id = (
            f"multiple:{company_id}:{request.definition.kind.value}:"
            f"{request.period_label}:{request.basis.value}"
        )
        if denominator is None:
            return _excluded_multiple(
                multiple_id,
                company_id,
                request,
                "Compatible denominator is missing, duplicated, or conflicting.",
                MultipleStatus.MISSING_INPUT,
                policy_id=self.policy.policy_id,
            )
        if denominator.value <= 0:
            return _excluded_multiple(
                multiple_id,
                company_id,
                request,
                "Zero or negative denominator is not meaningful for a conventional multiple.",
                MultipleStatus.NOT_MEANINGFUL,
                denominator=denominator,
                policy_id=self.policy.policy_id,
            )
        numerator_id: str
        numerator_value: Decimal | None
        evidence: tuple[EvidenceReference, ...]
        warnings: tuple[str, ...]
        if request.definition.numerator_family is ValueFamily.ENTERPRISE_VALUE:
            ev = self.enterprise_value(snapshot)
            numerator_id = ev.calculation_id
            numerator_value = ev.value
            evidence = _evidence(snapshot.market_metrics)
            warnings = ev.warnings
            numerator_currency = ev.currency
            numerator_unit = ev.unit
        elif request.definition.numerator_family is ValueFamily.SHARE_PRICE:
            price = _single_market(snapshot.market_metrics, MarketMetricKind.SHARE_PRICE)
            numerator_id = "missing:share-price" if price is None else price.metric_id
            numerator_value = None if price is None else price.value
            evidence = () if price is None else price.evidence
            warnings = ()
            numerator_currency = None if price is None else price.currency
            numerator_unit = None if price is None else price.unit
        else:
            equity = self.equity_value(company_id, snapshot.market_metrics)
            numerator_id = equity.calculation_id
            numerator_value = equity.value
            evidence = _evidence(snapshot.market_metrics)
            warnings = equity.warnings
            numerator_currency = equity.currency
            numerator_unit = equity.unit
        if numerator_value is None or numerator_currency is None or numerator_unit is None:
            return _excluded_multiple(
                multiple_id,
                company_id,
                request,
                "Required numerator is unavailable.",
                MultipleStatus.MISSING_INPUT,
                denominator=denominator,
                numerator_id=numerator_id,
                warnings=warnings,
                policy_id=self.policy.policy_id,
            )
        if numerator_currency != denominator.currency:
            return _excluded_multiple(
                multiple_id,
                company_id,
                request,
                "Numerator and denominator currencies differ; no FX conversion is configured.",
                MultipleStatus.EXCLUDED,
                denominator=denominator,
                numerator_id=numerator_id,
                numerator_value=numerator_value,
                warnings=warnings,
                policy_id=self.policy.policy_id,
            )
        if request.definition.numerator_family is ValueFamily.SHARE_PRICE:
            if denominator.unit is not FinancialUnit.PER_SHARE:
                return _excluded_multiple(
                    multiple_id,
                    company_id,
                    request,
                    "Share-price P/E requires EPS in per-share units.",
                    MultipleStatus.EXCLUDED,
                    denominator=denominator,
                    numerator_id=numerator_id,
                    numerator_value=numerator_value,
                    policy_id=self.policy.policy_id,
                )
            comparable_denominator = denominator.value
        else:
            if denominator.unit is FinancialUnit.PER_SHARE:
                return _excluded_multiple(
                    multiple_id,
                    company_id,
                    request,
                    "Aggregate numerator cannot use a per-share denominator.",
                    MultipleStatus.EXCLUDED,
                    denominator=denominator,
                    numerator_id=numerator_id,
                    numerator_value=numerator_value,
                    policy_id=self.policy.policy_id,
                )
            comparable_denominator = convert_unit(
                denominator.value, denominator.unit, numerator_unit
            )[0]
        return TradingMultiple(
            multiple_id,
            company_id,
            request.definition,
            numerator_id,
            denominator.metric_id,
            MultipleStatus.INCLUDED,
            self.policy.policy_id,
            numerator_value / comparable_denominator,
            numerator_value=numerator_value,
            denominator_value=denominator.value,
            denominator_period=denominator.period,
            denominator_basis=denominator.basis,
            evidence=tuple(dict.fromkeys((*evidence, *denominator.evidence))),
            quality_flags=tuple(
                dict.fromkeys((*snapshot.quality_flags, *denominator.quality_flags))
            ),
            warnings=warnings,
        )

    def multiple_set(self, peer_set: PeerSet, request: MultipleRequest) -> PeerMultipleSet:
        multiples = tuple(self.multiple(snapshot, request) for snapshot in peer_set.snapshots)
        statistics = self.statistics(peer_set.peer_set_id, request, multiples)
        warnings = tuple(dict.fromkeys((*peer_set.warnings, *statistics.warnings)))
        return PeerMultipleSet(
            (
                f"multiple-set:{peer_set.peer_set_id}:{request.definition.kind.value}:"
                f"{request.period_label}:{request.basis.value}"
            ),
            request,
            multiples,
            statistics,
            warnings,
        )

    def statistics(
        self,
        peer_set_id: str,
        request: MultipleRequest,
        multiples: tuple[TradingMultiple, ...],
    ) -> PeerStatistics:
        valid = [item for item in multiples if item.status is MultipleStatus.INCLUDED]
        values = [item.value for item in valid if item.value is not None]
        excluded = tuple(
            (item.multiple_id, item.treatment_reason or "Excluded by policy.")
            for item in multiples
            if item.status is not MultipleStatus.INCLUDED
        )
        warnings: list[str] = []
        if len(values) < 3:
            warnings.append(f"Low valid peer count ({len(values)}); reliability is limited.")
        statistics_id = (
            f"statistics:{peer_set_id}:{request.definition.kind.value}:"
            f"{request.period_label}:{request.basis.value}"
        )
        if not values:
            return PeerStatistics(
                statistics_id,
                request,
                0,
                len(excluded),
                None,
                None,
                None,
                None,
                None,
                None,
                (),
                excluded,
                (),
                warnings=tuple(warnings),
            )
        ordered = sorted(values)
        q1 = _percentile(ordered, Decimal("0.25"))
        median = _percentile(ordered, Decimal("0.5"))
        q3 = _percentile(ordered, Decimal("0.75"))
        outlier_ids: tuple[str, ...] = ()
        if self.policy.flag_iqr_outliers and len(values) >= 4:
            iqr = q3 - q1
            low_fence = q1 - Decimal("1.5") * iqr
            high_fence = q3 + Decimal("1.5") * iqr
            outlier_ids = tuple(
                item.multiple_id
                for item in valid
                if item.value is not None and (item.value < low_fence or item.value > high_fence)
            )
            if outlier_ids:
                warnings.append("IQR outliers flagged at Q1 - 1.5*IQR and Q3 + 1.5*IQR.")
        stats_valid = valid
        stats_values = values
        if self.policy.exclude_iqr_outliers and outlier_ids:
            stats_valid = [item for item in valid if item.multiple_id not in outlier_ids]
            stats_values = [item.value for item in stats_valid if item.value is not None]
            ordered = sorted(stats_values)
            q1 = _percentile(ordered, Decimal("0.25"))
            median = _percentile(ordered, Decimal("0.5"))
            q3 = _percentile(ordered, Decimal("0.75"))
            warnings.append("Flagged IQR outliers were excluded by configured policy.")
        return PeerStatistics(
            statistics_id,
            request,
            len(stats_values),
            len(excluded) + (len(outlier_ids) if self.policy.exclude_iqr_outliers else 0),
            min(stats_values),
            q1,
            median,
            q3,
            max(stats_values),
            sum(stats_values, Decimal("0")) / Decimal(len(stats_values)),
            tuple(item.multiple_id for item in stats_valid),
            excluded,
            outlier_ids,
            warnings=tuple(warnings),
        )

    def valuation_range(
        self, target: TargetFinancialProfile, multiple_set: PeerMultipleSet
    ) -> ValuationRange | None:
        stats = multiple_set.statistics
        anchors = {
            "low": getattr(stats, self.policy.low_statistic),
            "mid": getattr(stats, self.policy.mid_statistic),
            "high": getattr(stats, self.policy.high_statistic),
        }
        if any(value is None for value in anchors.values()):
            return None
        metric = _single_financial(
            target.metrics,
            multiple_set.request.definition.denominator_metric,
            multiple_set.request.period_label,
            multiple_set.request.basis,
        )
        if metric is None or metric.value <= 0:
            return None
        cases = {
            name: self._implied_case(target, multiple_set, metric, name, value)
            for name, value in anchors.items()
            if value is not None
        }
        return ValuationRange(
            f"range:{target.target.identity.company_id}:{stats.statistics_id}",
            multiple_set.request,
            cases["low"],
            cases["mid"],
            cases["high"],
            tuple(dict.fromkeys((*stats.warnings, *target.warnings))),
        )

    def _implied_case(
        self,
        target: TargetFinancialProfile,
        multiple_set: PeerMultipleSet,
        metric: FinancialMetric,
        anchor: str,
        multiple: Decimal,
    ) -> ImpliedValuation:
        definition = multiple_set.request.definition
        implied_value = metric.value * multiple
        value_family = definition.numerator_family
        unit = FinancialUnit.PER_SHARE if value_family is ValueFamily.SHARE_PRICE else metric.unit
        trace = CalculationTrace(
            (
                f"trace:implied:{target.target.identity.company_id}:"
                f"{multiple_set.statistics.statistics_id}:{anchor}"
            ),
            (
                f"Implied {value_family.value} = Target {metric.period.label} "
                f"{metric.name.value} * Peer {anchor} multiple"
            ),
            (
                _financial_input(metric),
                CalculationInput(
                    multiple_set.statistics.statistics_id,
                    f"peer_{anchor}_multiple",
                    multiple,
                    FinancialUnit.UNITS,
                    None,
                    None,
                    (),
                ),
            ),
            implied_value,
            self.policy.policy_id,
        )
        bridge = None
        implied_equity: Decimal | None = None
        per_share: Decimal | None = None
        warnings: list[str] = []
        if value_family is ValueFamily.ENTERPRISE_VALUE:
            bridge = self.bridge_target(target, implied_value, metric.currency, metric.unit, anchor)
            implied_equity = bridge.implied_equity_value
            warnings.extend(bridge.warnings)
            if implied_equity is not None:
                shares = _target_shares(target.capital_structure)
                if shares is None:
                    warnings.append(
                        "Diluted end-of-period shares unavailable; per-share value omitted."
                    )
                else:
                    per_share = (
                        convert_unit(implied_equity, metric.unit, FinancialUnit.MILLION)[0]
                        / convert_unit(shares.value, shares.unit, FinancialUnit.MILLION)[0]
                    )
        elif value_family is ValueFamily.EQUITY_VALUE:
            implied_equity = implied_value
            shares = _target_shares(target.capital_structure)
            if shares is not None:
                per_share = (
                    convert_unit(implied_value, metric.unit, FinancialUnit.MILLION)[0]
                    / convert_unit(shares.value, shares.unit, FinancialUnit.MILLION)[0]
                )
        else:
            per_share = implied_value
        return ImpliedValuation(
            (
                f"implied:{target.target.identity.company_id}:"
                f"{multiple_set.statistics.statistics_id}:{anchor}"
            ),
            anchor,
            multiple,
            metric.metric_id,
            value_family,
            implied_value,
            metric.currency,
            unit,
            bridge,
            implied_equity,
            per_share,
            trace,
            tuple(warnings),
        )

    def bridge_target(
        self,
        target: TargetFinancialProfile,
        implied_ev: Decimal,
        currency: str,
        unit: FinancialUnit,
        anchor: str,
    ) -> ValuationBridge:
        bridge_id = f"target-bridge:{target.target.identity.company_id}:{anchor}"
        capital = target.capital_structure
        if capital is None:
            return _empty_bridge(bridge_id, implied_ev, currency, unit, self.policy.policy_id)
        debt = _single_market(capital.components, MarketMetricKind.DEBT)
        cash = _single_market(capital.components, MarketMetricKind.CASH_AND_EQUIVALENTS)
        if debt is None or cash is None:
            return _empty_bridge(
                bridge_id,
                implied_ev,
                currency,
                unit,
                self.policy.policy_id,
                ("Debt and cash are required for the target EV-to-equity bridge.",),
            )
        optionals = {
            kind: _single_market(capital.components, kind)
            for kind in (MarketMetricKind.PREFERRED_STOCK, MarketMetricKind.MINORITY_INTEREST)
        }
        present = (debt, cash, *(item for item in optionals.values() if item is not None))
        if not _compatible_money(currency, unit, capital.as_of, present, self.policy):
            return _empty_bridge(
                bridge_id,
                implied_ev,
                currency,
                unit,
                self.policy.policy_id,
                ("Target bridge currencies or units are incompatible.",),
            )
        values = {item.kind: convert_unit(item.value, item.unit, unit)[0] for item in present}
        omitted = tuple(kind for kind, item in optionals.items() if item is None)
        warnings: list[str] = []
        if omitted:
            warnings.append(
                "Optional target bridge components not supplied and omitted: "
                + ", ".join(item.value for item in omitted)
                + "."
            )
        equity = (
            implied_ev
            - values[MarketMetricKind.DEBT]
            - values.get(MarketMetricKind.PREFERRED_STOCK, Decimal("0"))
            - values.get(MarketMetricKind.MINORITY_INTEREST, Decimal("0"))
            + values[MarketMetricKind.CASH_AND_EQUIVALENTS]
        )
        trace = CalculationTrace(
            f"trace:{bridge_id}",
            (
                "Implied Equity Value = Implied EV - Debt - Preferred Stock "
                "- Minority Interest + Cash"
            ),
            (
                CalculationInput(
                    "implied-ev",
                    "implied_enterprise_value",
                    implied_ev,
                    unit,
                    currency,
                    None,
                    (),
                ),
                *(_market_input(item) for item in present),
            ),
            equity,
            self.policy.policy_id,
            tuple(warnings),
        )
        return ValuationBridge(
            bridge_id,
            CalculationStatus.AVAILABLE,
            implied_ev,
            equity,
            currency,
            unit,
            tuple(item.metric_id for item in present),
            omitted,
            trace,
            tuple(warnings),
        )

    def build_output(
        self,
        target: TargetFinancialProfile,
        peer_set: PeerSet,
        requests: tuple[MultipleRequest, ...],
        explanation_provider: ValuationExplanationProvider | None = None,
    ) -> ValuationOutput:
        sets = tuple(self.multiple_set(peer_set, request) for request in requests)
        ranges = tuple(
            value
            for value in (self.valuation_range(target, item) for item in sets)
            if value is not None
        )
        warnings = tuple(
            dict.fromkeys(
                (
                    *target.warnings,
                    *peer_set.warnings,
                    *(warning for item in sets for warning in item.warnings),
                )
            )
        )
        output = ValuationOutput(
            f"valuation-output:{target.target.identity.company_id}:{peer_set.peer_set_id}",
            target.target.identity.company_id,
            peer_set.peer_set_id,
            sets,
            ranges,
            None,
            warnings,
        )
        if explanation_provider is None:
            return output
        try:
            explanation = explanation_provider.explain(output)
        except Exception as error:
            explanation = ValuationExplanation(
                CalculationStatus.UNAVAILABLE,
                "AI-assisted explanation unavailable; deterministic results remain valid.",
                (),
                (),
                (),
                "Use the deterministic ranges with their peer-count and quality warnings.",
                (f"Explanation provider failed safely: {type(error).__name__}.",),
                (),
                ("Provider failure did not alter any calculation.",),
            )
        return replace(output, explanation=explanation)


@dataclass(frozen=True, slots=True)
class FixtureValuationExplanationProvider:
    """Offline stand-in demonstrating the constrained AI output contract."""

    def explain(self, context: ValuationOutput) -> ValuationExplanation:
        usable = sum(item.statistics.count for item in context.multiple_sets)
        exclusions = sum(item.statistics.excluded_count for item in context.multiple_sets)
        outliers = tuple(
            multiple_id
            for item in context.multiple_sets
            for multiple_id in item.statistics.outlier_multiple_ids
        )
        preferred = tuple(item.request.label for item in context.ranges)
        evidence_ids = tuple(
            dict.fromkeys(
                evidence.evidence_id
                for item in context.multiple_sets
                for multiple in item.multiples
                for evidence in multiple.evidence
            )
        )
        return ValuationExplanation(
            CalculationStatus.AVAILABLE,
            (
                f"The peer evidence supplies {usable} usable multiple observations and "
                f"{exclusions} explicit exclusions across the requested methods."
            ),
            preferred,
            (
                "Target operating-metric scale drives implied enterprise or equity value.",
                "Peer dispersion drives the interquartile valuation range.",
                "Net debt and diluted shares drive equity and per-share conversion.",
            ),
            tuple(f"{item} is flagged by the documented 1.5*IQR rule." for item in outliers),
            (
                "Low, mid, and high use the peer 25th percentile, median, and 75th "
                "percentile; none is an intrinsic or true value."
            ),
            tuple(dict.fromkeys(context.warnings))
            or ("Source data should be independently verified.",),
            evidence_ids,
        )


def _empty_equity(
    calculation_id: str, policy_id: str, warnings: tuple[str, ...]
) -> EquityValueCalculation:
    trace = CalculationTrace(
        f"trace:{calculation_id}",
        "Equity Value = Share Price * Diluted End-of-Period Shares",
        (),
        None,
        policy_id,
        warnings,
    )
    return EquityValueCalculation(
        calculation_id,
        CalculationStatus.UNAVAILABLE,
        None,
        None,
        None,
        None,
        None,
        trace,
        warnings,
    )


def _empty_enterprise(
    calculation_id: str,
    company_id: str,
    as_of: datetime,
    equity: EquityValueCalculation,
    warnings: tuple[str, ...],
    policy_id: str,
) -> EnterpriseValueCalculation:
    return EnterpriseValueCalculation(
        calculation_id,
        company_id,
        CalculationStatus.UNAVAILABLE,
        equity,
        None,
        equity.currency,
        equity.unit,
        as_of,
        (),
        (),
        CalculationTrace(
            f"trace:{calculation_id}",
            "EV = Equity Value + Debt + Preferred Stock + Minority Interest - Cash",
            equity.trace.inputs,
            None,
            policy_id,
            warnings,
        ),
        warnings,
    )


def _empty_bridge(
    bridge_id: str,
    implied_ev: Decimal,
    currency: str,
    unit: FinancialUnit,
    policy_id: str,
    warnings: tuple[str, ...] = ("Target capital structure is unavailable.",),
) -> ValuationBridge:
    trace = CalculationTrace(
        f"trace:{bridge_id}",
        ("Implied Equity Value = Implied EV - Debt - Preferred Stock - Minority Interest + Cash"),
        (
            CalculationInput(
                "implied-ev",
                "implied_enterprise_value",
                implied_ev,
                unit,
                currency,
                None,
                (),
            ),
        ),
        None,
        policy_id,
        warnings,
    )
    return ValuationBridge(
        bridge_id,
        CalculationStatus.UNAVAILABLE,
        implied_ev,
        None,
        currency,
        unit,
        (),
        (),
        trace,
        warnings,
    )


def _single_market(
    metrics: tuple[MarketMetric, ...],
    kind: MarketMetricKind,
    share_basis: ShareCountBasis | None = None,
) -> MarketMetric | None:
    values = [
        item
        for item in metrics
        if item.kind is kind
        and (share_basis is None or item.share_basis is share_basis)
        and DataQualityFlag.CONFLICTING not in item.quality_flags
    ]
    return values[0] if len(values) == 1 else None


def _single_financial(
    metrics: tuple[FinancialMetric, ...],
    name: FinancialMetricName,
    period_label: str,
    basis: MetricBasis,
) -> FinancialMetric | None:
    values = [
        item
        for item in metrics
        if item.name is name
        and item.period.label == period_label
        and item.basis is basis
        and DataQualityFlag.CONFLICTING not in item.quality_flags
    ]
    return values[0] if len(values) == 1 else None


def _target_shares(capital: CapitalStructure | None) -> MarketMetric | None:
    if capital is None:
        return None
    return _single_market(
        capital.components,
        MarketMetricKind.DILUTED_SHARES,
        ShareCountBasis.DILUTED_END_OF_PERIOD,
    )


def _compatible_money(
    currency: str,
    unit: FinancialUnit,
    reference_date: datetime | None,
    items: tuple[MarketMetric, ...],
    policy: ValuationPolicy,
    *,
    check_dates: bool = True,
) -> bool:
    if unit is FinancialUnit.PER_SHARE:
        return False
    for item in items:
        if item.currency != currency or item.unit is FinancialUnit.PER_SHARE:
            return False
        if (
            check_dates
            and reference_date is not None
            and abs((reference_date.date() - item.as_of.date()).days)
            > policy.max_capital_date_gap_days
        ):
            return False
    return True


def _market_input(metric: MarketMetric) -> CalculationInput:
    return CalculationInput(
        metric.metric_id,
        metric.kind.value,
        metric.value,
        metric.unit,
        metric.currency,
        metric.as_of,
        tuple(item.evidence_id for item in metric.evidence),
    )


def _financial_input(metric: FinancialMetric) -> CalculationInput:
    return CalculationInput(
        metric.metric_id,
        f"{metric.period.label} {metric.name.value} ({metric.basis.value})",
        metric.value,
        metric.unit,
        metric.currency,
        metric.as_of,
        tuple(item.evidence_id for item in metric.evidence),
    )


def _evidence(metrics: tuple[MarketMetric, ...]) -> tuple[EvidenceReference, ...]:
    return tuple(dict.fromkeys(item for metric in metrics for item in metric.evidence))


def _excluded_multiple(
    multiple_id: str,
    company_id: str,
    request: MultipleRequest,
    reason: str,
    status: MultipleStatus,
    *,
    policy_id: str,
    denominator: FinancialMetric | None = None,
    numerator_id: str = "unavailable:numerator",
    numerator_value: Decimal | None = None,
    warnings: tuple[str, ...] = (),
) -> TradingMultiple:
    return TradingMultiple(
        multiple_id,
        company_id,
        request.definition,
        numerator_id,
        "missing:denominator" if denominator is None else denominator.metric_id,
        status,
        policy_id,
        treatment_reason=reason,
        numerator_value=numerator_value,
        denominator_value=None if denominator is None else denominator.value,
        denominator_period=None if denominator is None else denominator.period,
        denominator_basis=None if denominator is None else denominator.basis,
        evidence=() if denominator is None else denominator.evidence,
        quality_flags=() if denominator is None else denominator.quality_flags,
        warnings=warnings,
    )


def _percentile(ordered: list[Decimal], probability: Decimal) -> Decimal:
    """Hyndman-Fan type 7 / linear percentile using exact Decimal arithmetic."""

    if not ordered:
        raise ValueError("percentile requires at least one value")
    position = Decimal(len(ordered) - 1) * probability
    lower = int(position.to_integral_value(rounding=ROUND_FLOOR))
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - Decimal(lower)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction
