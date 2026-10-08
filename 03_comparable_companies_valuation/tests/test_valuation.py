from dataclasses import replace
from decimal import Decimal

from ma_comparable_valuation import (
    CalculationStatus,
    FinancialMetricName,
    FinancialUnit,
    MetricBasis,
    MultipleDefinition,
    MultipleKind,
    MultipleRequest,
    MultipleStatus,
    ShareCountBasis,
    ValuationEngine,
    ValuationPolicy,
    ValueFamily,
)
from ma_comparable_valuation.valuation_fixtures import (
    demo_multiple_requests,
    demo_peer_set,
    demo_target_profile,
)


def _request(kind: MultipleKind, period: str = "LTM Jun-2026") -> MultipleRequest:
    definitions = {
        MultipleKind.EV_REVENUE: MultipleDefinition(
            MultipleKind.EV_REVENUE,
            ValueFamily.ENTERPRISE_VALUE,
            FinancialMetricName.REVENUE,
        ),
        MultipleKind.EV_EBITDA: MultipleDefinition(
            MultipleKind.EV_EBITDA,
            ValueFamily.ENTERPRISE_VALUE,
            FinancialMetricName.EBITDA,
        ),
        MultipleKind.EV_EBIT: MultipleDefinition(
            MultipleKind.EV_EBIT,
            ValueFamily.ENTERPRISE_VALUE,
            FinancialMetricName.EBIT,
        ),
        MultipleKind.PRICE_EARNINGS: MultipleDefinition(
            MultipleKind.PRICE_EARNINGS,
            ValueFamily.SHARE_PRICE,
            FinancialMetricName.EPS,
        ),
    }
    return MultipleRequest(definitions[kind], period, MetricBasis.REPORTED)


def test_equity_and_enterprise_value_are_traced() -> None:
    peer = demo_peer_set().snapshots[0]
    engine = ValuationEngine()

    equity = engine.equity_value("peer-a", peer.market_metrics)
    enterprise = engine.enterprise_value(peer)

    assert equity.status is CalculationStatus.AVAILABLE
    assert equity.value == Decimal("25000")
    assert equity.unit is FinancialUnit.MILLION
    assert len(equity.trace.inputs) == 2
    assert enterprise.value == Decimal("25700")
    assert len(enterprise.included_component_ids) == 2
    assert enterprise.omitted_components
    assert "Preferred Stock" in enterprise.trace.formula


def test_equity_value_rejects_weighted_average_or_incompatible_dates() -> None:
    peer = demo_peer_set().snapshots[0]
    shares = next(item for item in peer.market_metrics if item.kind.value == "diluted_shares")
    weighted = replace(shares, share_basis=ShareCountBasis.DILUTED_WEIGHTED_AVERAGE)
    metrics = tuple(weighted if item is shares else item for item in peer.market_metrics)

    result = ValuationEngine().equity_value("peer-a", metrics)

    assert result.status is CalculationStatus.UNAVAILABLE
    assert result.value is None
    assert "end-of-period" in result.warnings[0]


def test_enterprise_value_requires_debt_and_does_not_fabricate_zero() -> None:
    peer = demo_peer_set().snapshots[-1]

    result = ValuationEngine().enterprise_value(peer)

    assert result.status is CalculationStatus.UNAVAILABLE
    assert result.value is None
    assert any("Debt and cash" in warning for warning in result.warnings)


def test_supported_multiples_use_exact_numerator_and_denominator() -> None:
    peer = demo_peer_set().snapshots[0]
    engine = ValuationEngine()
    values = {
        kind: engine.multiple(peer, _request(kind))
        for kind in (
            MultipleKind.EV_REVENUE,
            MultipleKind.EV_EBITDA,
            MultipleKind.EV_EBIT,
            MultipleKind.PRICE_EARNINGS,
        )
    }

    assert values[MultipleKind.EV_REVENUE].value == Decimal("25700") / Decimal("4200")
    assert values[MultipleKind.EV_EBITDA].value == Decimal("25700") / Decimal("680")
    assert values[MultipleKind.EV_EBIT].value == Decimal("25700") / Decimal("510")
    assert values[MultipleKind.PRICE_EARNINGS].value == Decimal("125") / Decimal("7")
    assert all(item.status is MultipleStatus.INCLUDED for item in values.values())
    assert all(item.evidence for item in values.values())


def test_period_labels_keep_historical_and_forecast_separate() -> None:
    peer = demo_peer_set().snapshots[0]
    engine = ValuationEngine()
    historical = engine.multiple(peer, _request(MultipleKind.EV_REVENUE))
    forecast = engine.multiple(peer, _request(MultipleKind.EV_REVENUE, "FY2027E"))
    wrong = engine.multiple(peer, _request(MultipleKind.EV_REVENUE, "FY2028E"))

    assert historical.denominator_period is not None
    assert historical.denominator_period.label == "LTM Jun-2026"
    assert forecast.denominator_period is not None
    assert forecast.denominator_period.label == "FY2027E"
    assert wrong.status is MultipleStatus.MISSING_INPUT
    assert wrong.value is None


def test_reported_and_adjusted_metrics_are_not_mixed() -> None:
    peer = demo_peer_set().snapshots[0]
    request = replace(
        _request(MultipleKind.EV_EBITDA),
        basis=MetricBasis.ADJUSTED,
    )

    result = ValuationEngine().multiple(peer, request)

    assert result.status is MultipleStatus.MISSING_INPUT
    assert result.denominator_basis is None


def test_negative_zero_and_missing_denominators_are_explicit() -> None:
    peers = demo_peer_set().snapshots
    engine = ValuationEngine()
    request = _request(MultipleKind.EV_EBITDA)
    negative = engine.multiple(peers[3], request)
    missing = engine.multiple(peers[4], request)
    zero_metric = replace(
        next(
            item
            for item in peers[0].financial_metrics
            if item.name is FinancialMetricName.EBITDA and item.period.label == "LTM Jun-2026"
        ),
        value=Decimal("0"),
    )
    zero_peer = replace(
        peers[0],
        financial_metrics=tuple(
            zero_metric if item.metric_id == zero_metric.metric_id else item
            for item in peers[0].financial_metrics
        ),
    )
    zero = engine.multiple(zero_peer, request)

    assert negative.status is MultipleStatus.NOT_MEANINGFUL
    assert negative.denominator_value == Decimal("-100")
    assert zero.status is MultipleStatus.NOT_MEANINGFUL
    assert zero.denominator_value == 0
    assert missing.status is MultipleStatus.MISSING_INPUT


def test_peer_statistics_use_linear_percentiles_and_flag_outlier_without_deleting() -> None:
    multiple_set = ValuationEngine().multiple_set(
        demo_peer_set(), _request(MultipleKind.EV_REVENUE)
    )
    stats = multiple_set.statistics

    assert stats.count == 4
    assert stats.excluded_count == 1
    assert stats.minimum is not None
    assert stats.percentile_25 is not None
    assert stats.median is not None
    assert stats.percentile_75 is not None
    assert stats.maximum is not None
    assert stats.percentile_method == "linear_interpolation_r7"
    assert len(stats.outlier_multiple_ids) == 1
    assert stats.outlier_multiple_ids[0] in stats.included_multiple_ids


def test_configured_outlier_exclusion_is_transparent() -> None:
    engine = ValuationEngine(ValuationPolicy(exclude_iqr_outliers=True))
    stats = engine.multiple_set(demo_peer_set(), _request(MultipleKind.EV_REVENUE)).statistics

    assert stats.count == 3
    assert stats.excluded_count == 2
    assert any("excluded by configured policy" in item for item in stats.warnings)


def test_implied_ev_equity_and_per_share_range_are_auditable() -> None:
    target = demo_target_profile()
    multiple_set = ValuationEngine().multiple_set(demo_peer_set(), _request(MultipleKind.EV_EBITDA))

    result = ValuationEngine().valuation_range(target, multiple_set)

    assert result is not None
    assert result.low.multiple == multiple_set.statistics.percentile_25
    assert result.mid.implied_value == Decimal("820") * result.mid.multiple
    assert result.mid.bridge is not None
    assert result.mid.implied_equity_value == result.mid.implied_value - 1000 + 400
    assert result.mid.implied_per_share == result.mid.implied_equity_value / 50
    assert result.mid.trace.inputs[0].input_id == result.mid.target_metric_id


def test_missing_target_capital_structure_preserves_partial_implied_ev() -> None:
    target = replace(
        demo_target_profile(),
        capital_structure=None,
        normalization_decisions=(),
        completeness=None,
    )
    multiple_set = ValuationEngine().multiple_set(
        demo_peer_set(), _request(MultipleKind.EV_REVENUE)
    )

    result = ValuationEngine().valuation_range(target, multiple_set)

    assert result is not None
    assert result.mid.implied_value > 0
    assert result.mid.implied_equity_value is None
    assert result.mid.implied_per_share is None
    assert result.mid.bridge is not None
    assert result.mid.bridge.status is CalculationStatus.UNAVAILABLE


def test_multi_method_output_and_mocked_explanation() -> None:
    from ma_comparable_valuation import FixtureValuationExplanationProvider

    output = ValuationEngine().build_output(
        demo_target_profile(),
        demo_peer_set(),
        demo_multiple_requests(),
        FixtureValuationExplanationProvider(),
    )

    assert len(output.multiple_sets) == 7
    assert len(output.ranges) == 2
    assert output.explanation is not None
    assert output.explanation.status is CalculationStatus.AVAILABLE
    assert output.explanation.evidence_ids


def test_explanation_failure_does_not_break_deterministic_output() -> None:
    class FailingProvider:
        def explain(self, context):  # type: ignore[no-untyped-def]
            del context
            raise RuntimeError("offline failure")

    output = ValuationEngine().build_output(
        demo_target_profile(),
        demo_peer_set(),
        (_request(MultipleKind.EV_REVENUE),),
        FailingProvider(),
    )

    assert len(output.ranges) == 1
    assert output.explanation is not None
    assert output.explanation.status is CalculationStatus.UNAVAILABLE
    assert "deterministic results remain valid" in output.explanation.peer_set_assessment
