"""Peer statistics, target implied valuation, bridges, and grounded explanation isolation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import ROUND_FLOOR, Decimal
from typing import Protocol

from ma_precedent_transactions.domain import (
    CapitalComponentKind,
    FinancialMetric,
    FinancialUnit,
    MultipleKind,
    MultipleStatus,
)
from ma_precedent_transactions.extraction import convert_unit
from ma_precedent_transactions.precedent.models import (
    CalculationInput,
    CalculationStatus,
    CalculationTrace,
    ComparableTransactionSet,
    ImpliedValuationCase,
    ImpliedValuationRange,
    MultipleSetKey,
    PeerStatistics,
    PrecedentValuationOutput,
    TargetValuationProfile,
    TransactionMultipleResult,
    TransactionMultipleSet,
    ValuationExplanation,
)


class ValuationExplanationProvider(Protocol):
    def explain(self, context: PrecedentValuationOutput) -> ValuationExplanation: ...


@dataclass(frozen=True, slots=True)
class PrecedentValuationPolicy:
    policy_id: str = "precedent-valuation-v1"
    flag_iqr_outliers: bool = True
    exclude_iqr_outliers: bool = False
    low_statistic: str = "percentile_25"
    mid_statistic: str = "median"
    high_statistic: str = "percentile_75"
    maximum_capital_age_days: int = 550
    maximum_share_age_days: int = 550

    def __post_init__(self) -> None:
        allowed = {"minimum", "percentile_25", "median", "percentile_75", "maximum"}
        if {self.low_statistic, self.mid_statistic, self.high_statistic} - allowed:
            raise ValueError("valuation anchors must name supported peer statistics")
        if self.maximum_capital_age_days < 0 or self.maximum_share_age_days < 0:
            raise ValueError("target data age limits must be non-negative")


class PrecedentValuationEngine:
    def __init__(self, policy: PrecedentValuationPolicy | None = None) -> None:
        self.policy = policy or PrecedentValuationPolicy()

    def multiple_sets(
        self, results: tuple[TransactionMultipleResult, ...]
    ) -> tuple[TransactionMultipleSet, ...]:
        groups: dict[MultipleSetKey, list[TransactionMultipleResult]] = {}
        for item in results:
            if (
                item.contract.status is MultipleStatus.INCLUDED
                and item.numerator_currency is not None
                and item.denominator_period is not None
                and item.denominator_basis is not None
            ):
                key = MultipleSetKey(
                    item.contract.definition.kind,
                    item.numerator_currency,
                    item.denominator_period.kind.value,
                    item.denominator_basis,
                )
                groups.setdefault(key, []).append(item)
        sets = []
        for key, included in sorted(groups.items(), key=lambda item: str(item[0])):
            relevant_excluded = [
                item
                for item in results
                if item.contract.definition.kind is key.kind
                and item.contract.status is not MultipleStatus.INCLUDED
            ]
            multiples, statistics = self._statistics(key, tuple(included), tuple(relevant_excluded))
            sets.append(
                TransactionMultipleSet(
                    f"multiple-set:{key.kind.value}:{key.currency}:"
                    f"{key.period_kind}:{key.basis.value}",
                    key,
                    (*multiples, *relevant_excluded),
                    statistics,
                    statistics.warnings,
                )
            )
        return tuple(sets)

    def _statistics(
        self,
        key: MultipleSetKey,
        included: tuple[TransactionMultipleResult, ...],
        excluded: tuple[TransactionMultipleResult, ...],
    ) -> tuple[tuple[TransactionMultipleResult, ...], PeerStatistics]:
        values = [item.contract.value for item in included if item.contract.value is not None]
        warnings = []
        if not values:
            warnings.append("No valid deals are available for this multiple set.")
        elif len(values) == 1:
            warnings.append("Only one valid deal is available; no distribution is implied.")
        elif len(values) < 4:
            warnings.append(f"Very small valid sample ({len(values)} deals).")
        labels = {
            item.denominator_period.label
            for item in included
            if item.denominator_period is not None
        }
        if len(labels) > 1:
            warnings.append("The set contains mixed exact periods within the same period kind.")
        ordered = sorted(values)
        if not ordered:
            stats = PeerStatistics(
                _statistics_id(key),
                key,
                0,
                len(excluded),
                None,
                None,
                None,
                None,
                None,
                None,
                (),
                tuple(
                    (item.contract.multiple_id, item.contract.treatment_reason or "Excluded.")
                    for item in excluded
                ),
                (),
                warnings=tuple(warnings),
            )
            return included, stats
        q1 = _percentile(ordered, Decimal("0.25"))
        q3 = _percentile(ordered, Decimal("0.75"))
        outlier_ids: tuple[str, ...] = ()
        if self.policy.flag_iqr_outliers and len(ordered) >= 4:
            iqr = q3 - q1
            low, high = q1 - Decimal("1.5") * iqr, q3 + Decimal("1.5") * iqr
            outlier_ids = tuple(
                item.contract.multiple_id
                for item in included
                if item.contract.value is not None
                and (item.contract.value < low or item.contract.value > high)
            )
            if outlier_ids:
                warnings.append("IQR outliers flagged using Q1 - 1.5*IQR and Q3 + 1.5*IQR.")
        marked = tuple(
            replace(item, outlier=item.contract.multiple_id in outlier_ids) for item in included
        )
        stats_items = marked
        if self.policy.exclude_iqr_outliers and outlier_ids:
            stats_items = tuple(item for item in marked if not item.outlier)
            warnings.append("Flagged IQR outliers were excluded by configured policy.")
        stats_values = [
            item.contract.value for item in stats_items if item.contract.value is not None
        ]
        stats_values.sort()
        stats = PeerStatistics(
            _statistics_id(key),
            key,
            len(stats_values),
            len(excluded) + (len(outlier_ids) if self.policy.exclude_iqr_outliers else 0),
            min(stats_values),
            _percentile(stats_values, Decimal("0.25")),
            _percentile(stats_values, Decimal("0.5")),
            _percentile(stats_values, Decimal("0.75")),
            max(stats_values),
            sum(stats_values, Decimal("0")) / Decimal(len(stats_values)),
            tuple(item.contract.multiple_id for item in stats_items),
            tuple(
                (item.contract.multiple_id, item.contract.treatment_reason or "Excluded.")
                for item in excluded
            ),
            outlier_ids,
            warnings=tuple(warnings),
        )
        return marked, stats

    def valuation_range(
        self,
        target: TargetValuationProfile,
        multiple_set: TransactionMultipleSet,
    ) -> ImpliedValuationRange | None:
        stats = multiple_set.statistics
        anchors = {
            "low": getattr(stats, self.policy.low_statistic),
            "mid": getattr(stats, self.policy.mid_statistic),
            "high": getattr(stats, self.policy.high_statistic),
        }
        if any(value is None for value in anchors.values()):
            return None
        metric = _target_metric(target, multiple_set.key)
        if metric is None or metric.value <= 0:
            return None
        if metric.currency != multiple_set.key.currency:
            return None
        cases = {
            anchor: self._case(target, multiple_set, metric, anchor, value)
            for anchor, value in anchors.items()
            if value is not None
        }
        return ImpliedValuationRange(
            f"range:{target.target_id}:{stats.statistics_id}",
            multiple_set.key,
            metric.metric_id,
            cases["low"],
            cases["mid"],
            cases["high"],
            tuple(dict.fromkeys((*stats.warnings, *target.warnings))),
        )

    def _case(
        self,
        target: TargetValuationProfile,
        multiple_set: TransactionMultipleSet,
        metric: FinancialMetric,
        anchor: str,
        multiple: Decimal,
    ) -> ImpliedValuationCase:
        metric_millions, _ = convert_unit(metric.value, metric.unit, FinancialUnit.MILLION)
        implied = metric_millions * multiple
        is_equity = multiple_set.key.kind is MultipleKind.EQUITY_VALUE_NET_INCOME
        formula = (
            "Implied Equity Value = Target Metric * Precedent Multiple"
            if is_equity
            else "Implied Enterprise Value = Target Metric * Precedent Multiple"
        )
        trace = CalculationTrace(
            f"trace:{target.target_id}:{multiple_set.key.kind.value}:{anchor}",
            formula,
            (
                CalculationInput(
                    metric.metric_id,
                    f"target_{metric.period.label}_{metric.name.value}",
                    metric_millions,
                    FinancialUnit.MILLION,
                    metric.currency,
                    tuple(item.evidence_id for item in metric.evidence),
                ),
                CalculationInput(
                    multiple_set.statistics.statistics_id,
                    f"precedent_{anchor}_multiple",
                    multiple,
                    FinancialUnit.UNITS,
                    None,
                    tuple(
                        evidence.evidence_id
                        for item in multiple_set.multiples
                        for evidence in item.evidence
                    ),
                ),
            ),
            implied,
            self.policy.policy_id,
        )
        if is_equity:
            equity: Decimal | None = implied
            bridge_trace: CalculationTrace | None = None
            warnings: tuple[str, ...] = ()
            enterprise = None
        else:
            enterprise = implied
            equity, bridge_trace, warnings = self._bridge(
                target, implied, metric.currency, metric.measurement_date
            )
        per_share = self._per_share(target, equity, metric.measurement_date)
        if equity is not None and per_share is None:
            warnings = (*warnings, "Diluted end-of-period shares are unavailable or incompatible.")
        status = CalculationStatus.AVAILABLE if equity is not None else CalculationStatus.PARTIAL
        return ImpliedValuationCase(
            anchor,
            multiple,
            enterprise,
            equity,
            per_share,
            metric.currency or multiple_set.key.currency,
            FinancialUnit.MILLION,
            status,
            trace,
            bridge_trace,
            tuple(warnings),
        )

    def _bridge(
        self,
        target: TargetValuationProfile,
        implied_ev: Decimal,
        currency: str | None,
        valuation_date: date,
    ) -> tuple[Decimal | None, CalculationTrace | None, tuple[str, ...]]:
        snapshot = target.capital.snapshot
        if snapshot is None or currency is None:
            return None, None, ("Target capital structure is unavailable.",)
        age = (valuation_date - snapshot.as_of).days
        if age < 0:
            return None, None, ("Target capital structure post-dates the valuation metric.",)
        if age > self.policy.maximum_capital_age_days:
            return None, None, (f"Target capital structure is stale by {age} days.",)
        components = {item.kind: item for item in snapshot.components}
        debt, cash = (
            components.get(CapitalComponentKind.DEBT),
            components.get(CapitalComponentKind.CASH),
        )
        if debt is None or cash is None:
            return None, None, ("Debt and cash are required for the EV-to-equity bridge.",)
        present = tuple(components.values())
        if any(item.amount.currency != currency for item in present):
            return None, None, ("Target bridge currencies differ; no FX policy is configured.",)
        values = {
            item.kind: convert_unit(item.amount.value, item.amount.unit, FinancialUnit.MILLION)[0]
            for item in present
        }
        equity = (
            implied_ev
            - values[CapitalComponentKind.DEBT]
            - values.get(CapitalComponentKind.PREFERRED_STOCK, Decimal("0"))
            - values.get(CapitalComponentKind.NONCONTROLLING_INTEREST, Decimal("0"))
            + values[CapitalComponentKind.CASH]
        )
        warnings = []
        for optional in (
            CapitalComponentKind.PREFERRED_STOCK,
            CapitalComponentKind.NONCONTROLLING_INTEREST,
        ):
            if optional not in values:
                warnings.append(f"Optional {optional.value} was not supplied and was omitted.")
        trace = CalculationTrace(
            f"trace:bridge:{target.target_id}:{implied_ev}",
            "Equity Value = EV - Debt - Preferred - NCI + Cash",
            (
                CalculationInput(
                    "implied-ev",
                    "implied_enterprise_value",
                    implied_ev,
                    FinancialUnit.MILLION,
                    currency,
                    (),
                ),
                *(
                    CalculationInput(
                        item.component_id,
                        item.kind.value,
                        values[item.kind],
                        FinancialUnit.MILLION,
                        item.amount.currency,
                        tuple(value.evidence_id for value in item.evidence),
                    )
                    for item in present
                ),
            ),
            equity,
            self.policy.policy_id,
            tuple(warnings),
        )
        return equity, trace, tuple(warnings)

    def _per_share(
        self,
        target: TargetValuationProfile,
        equity: Decimal | None,
        valuation_date: date,
    ) -> Decimal | None:
        capital = target.capital
        if (
            equity is None
            or capital.diluted_shares is None
            or capital.share_unit is None
            or capital.share_count_basis != "diluted_end_of_period"
            or capital.share_count_date is None
        ):
            return None
        age = (valuation_date - capital.share_count_date).days
        if age < 0 or age > self.policy.maximum_share_age_days:
            return None
        shares, _ = convert_unit(capital.diluted_shares, capital.share_unit, FinancialUnit.MILLION)
        return None if shares <= 0 else equity / shares

    def build_output(
        self,
        target: TargetValuationProfile,
        selection: ComparableTransactionSet,
        multiples: tuple[TransactionMultipleResult, ...],
        explanation_provider: ValuationExplanationProvider | None = None,
    ) -> PrecedentValuationOutput:
        sets = self.multiple_sets(multiples)
        ranges = tuple(
            result
            for result in (self.valuation_range(target, item) for item in sets)
            if result is not None
        )
        warnings = list(selection.warnings)
        if not selection.selected_transaction_ids:
            warnings.append("No eligible precedent transactions were selected.")
        if not sets:
            warnings.append("No compatible multiple set could be formed.")
        output = PrecedentValuationOutput(
            f"precedent-valuation:{target.target_id}:{selection.set_id}",
            target.target_id,
            selection,
            sets,
            ranges,
            None,
            tuple(dict.fromkeys(warnings)),
        )
        if explanation_provider is None:
            return output
        return self.attach_explanation(output, explanation_provider)

    @staticmethod
    def attach_explanation(
        output: PrecedentValuationOutput,
        explanation_provider: ValuationExplanationProvider,
    ) -> PrecedentValuationOutput:
        """Attach optional commentary without allowing provider failure to alter calculations."""

        try:
            explanation = explanation_provider.explain(output)
        except Exception as error:
            explanation = ValuationExplanation(
                CalculationStatus.UNAVAILABLE,
                "AI-assisted explanation unavailable; deterministic results remain valid.",
                (),
                (),
                (),
                (),
                (),
                (f"Explanation provider failed safely: {type(error).__name__}.",),
                (),
                ("Provider failure did not alter selection or calculations.",),
            )
        return replace(output, explanation=explanation)


@dataclass(frozen=True, slots=True)
class FixtureValuationExplanationProvider:
    """Offline grounded stand-in; it summarizes authoritative structured results only."""

    def explain(self, context: PrecedentValuationOutput) -> ValuationExplanation:
        included = context.selection.selected_transaction_ids
        excluded = tuple(
            item.transaction_id
            for item in context.selection.decisions
            if item.transaction_id not in included
        )
        outliers = tuple(
            multiple_id
            for item in context.multiple_sets
            for multiple_id in item.statistics.outlier_multiple_ids
        )
        evidence_ids = tuple(
            dict.fromkeys(
                evidence.evidence_id
                for item in context.multiple_sets
                for multiple in item.multiples
                for evidence in multiple.evidence
            )
        )
        buyer_types = tuple(
            dict.fromkeys(
                assessment.rationale
                for decision in context.selection.decisions
                for assessment in decision.assessments
                if assessment.criterion == "buyer_type"
            )
        )
        return ValuationExplanation(
            CalculationStatus.AVAILABLE,
            f"{len(included)} deals are included and {len(excluded)} are excluded or separate.",
            included[:3],
            excluded,
            (
                "Target metrics and the precedent interquartile distribution drive value.",
                *buyer_types,
            ),
            tuple(f"{item} is flagged under the documented IQR rule." for item in outliers),
            tuple(item.key.kind.value for item in context.multiple_sets if item.statistics.count),
            (
                "Precedent prices may include control and strategic considerations.",
                "No separate control premium is inferred.",
                *context.warnings,
            ),
            evidence_ids,
        )


def _target_metric(target: TargetValuationProfile, key: MultipleSetKey) -> FinancialMetric | None:
    name = {
        MultipleKind.EV_REVENUE: "revenue",
        MultipleKind.EV_EBITDA: "ebitda",
        MultipleKind.EV_EBIT: "ebit",
        MultipleKind.EQUITY_VALUE_NET_INCOME: "net_income",
    }[key.kind]
    matches = [
        item
        for item in target.metrics
        if item.name.value == name
        and item.period.kind.value == key.period_kind
        and item.basis is key.basis
    ]
    return max(matches, key=lambda item: item.measurement_date, default=None)


def _statistics_id(key: MultipleSetKey) -> str:
    return f"statistics:{key.kind.value}:{key.currency}:{key.period_kind}:{key.basis.value}"


def _percentile(values: list[Decimal], probability: Decimal) -> Decimal:
    if not values:
        raise ValueError("percentile requires values")
    if len(values) == 1:
        return values[0]
    index = probability * Decimal(len(values) - 1)
    lower = int(index.to_integral_value(rounding=ROUND_FLOOR))
    upper = min(lower + 1, len(values) - 1)
    fraction = index - Decimal(lower)
    return values[lower] + (values[upper] - values[lower]) * fraction
