from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from ma_precedent_transactions.domain import MultipleKind
from ma_precedent_transactions.precedent import (
    FixtureValuationExplanationProvider,
    PrecedentAnalysisService,
    PrecedentValuationOutput,
    precedent_fixture_inputs,
)


def _output() -> PrecedentValuationOutput:
    comparable, target, transactions = precedent_fixture_inputs()
    return PrecedentAnalysisService().analyze(
        comparable,
        target,
        transactions,
        explanation_provider=FixtureValuationExplanationProvider(),
    )


def test_peer_statistics_use_r7_percentiles_and_flag_outliers_transparently() -> None:
    output = _output()
    revenue = next(
        item for item in output.multiple_sets if item.key.kind is MultipleKind.EV_REVENUE
    )

    assert revenue.statistics.count == 4
    assert revenue.statistics.percentile_method == "linear_interpolation_r7"
    assert revenue.statistics.minimum == Decimal("250") / Decimal("60")
    assert revenue.statistics.median == Decimal("4.463541666666666666666666666")
    assert revenue.statistics.outlier_multiple_ids == (
        "multiple:txn-outlier:ev_revenue:LTM Dec-2023:reported",
    )
    assert any("IQR" in warning for warning in revenue.statistics.warnings)


def test_implied_ev_bridge_equity_and_per_share_are_traced() -> None:
    output = _output()
    revenue = next(item for item in output.ranges if item.key.kind is MultipleKind.EV_REVENUE)

    assert revenue.mid.implied_enterprise_value == Decimal("446.3541666666666666666666666")
    assert revenue.mid.implied_equity_value == revenue.mid.implied_enterprise_value - Decimal("28")
    assert revenue.mid.implied_per_share == revenue.mid.implied_equity_value / Decimal("50")
    assert "Target Metric" in revenue.mid.trace.formula
    assert revenue.mid.bridge_trace is not None
    assert revenue.mid.bridge_trace.result == revenue.mid.implied_equity_value
    assert revenue.mid.trace.inputs[0].evidence_ids


def test_multi_method_output_does_not_average_methods() -> None:
    output = _output()
    kinds = {item.key.kind for item in output.ranges}

    assert kinds == {
        MultipleKind.EV_REVENUE,
        MultipleKind.EV_EBITDA,
        MultipleKind.EV_EBIT,
        MultipleKind.EQUITY_VALUE_NET_INCOME,
    }
    assert len(output.ranges) >= 4


def test_reported_and_adjusted_ranges_are_separate() -> None:
    output = _output()
    ebitda = [item for item in output.ranges if item.key.kind is MultipleKind.EV_EBITDA]

    assert {item.key.basis.value for item in ebitda} == {"reported", "adjusted"}


def test_missing_capital_structure_returns_partial_ev_result() -> None:
    comparable, target, transactions = precedent_fixture_inputs()
    target = replace(target, capital=replace(target.capital, snapshot=None))
    output = PrecedentAnalysisService().analyze(comparable, target, transactions)
    revenue = next(item for item in output.ranges if item.key.kind is MultipleKind.EV_REVENUE)

    assert revenue.mid.implied_enterprise_value is not None
    assert revenue.mid.implied_equity_value is None
    assert revenue.mid.status.value == "partial"
    assert "capital structure" in revenue.mid.warnings[0]


def test_weighted_average_or_unknown_share_basis_is_not_used() -> None:
    comparable, target, transactions = precedent_fixture_inputs()
    target = replace(target, capital=replace(target.capital, share_count_basis="weighted_average"))
    output = PrecedentAnalysisService().analyze(comparable, target, transactions)
    revenue = next(item for item in output.ranges if item.key.kind is MultipleKind.EV_REVENUE)

    assert revenue.mid.implied_equity_value is not None
    assert revenue.mid.implied_per_share is None
    assert any("Diluted end-of-period" in warning for warning in revenue.mid.warnings)


def test_low_sample_warning_is_exposed() -> None:
    output = _output()
    one_deal = next(item for item in output.multiple_sets if item.statistics.count == 1)

    assert "Only one valid deal" in one_deal.statistics.warnings[0]


def test_no_eligible_deals_returns_warnings_instead_of_failure() -> None:
    comparable, target, transactions = precedent_fixture_inputs()
    output = PrecedentAnalysisService().analyze(comparable, target, (transactions[-1],))

    assert output.multiple_sets == ()
    assert output.ranges == ()
    assert "No eligible precedent transactions were selected." in output.warnings


def test_grounded_fixture_explanation_cannot_change_numeric_results() -> None:
    output = _output()

    assert output.explanation is not None
    assert output.explanation.status.value == "available"
    assert "No separate control premium is inferred." in output.explanation.valuation_caveats
    assert output.ranges


class _FailingExplanation:
    def explain(self, context: object) -> object:
        raise TimeoutError("offline fixture failure")


def test_explanation_failure_is_isolated_from_deterministic_valuation() -> None:
    comparable, target, transactions = precedent_fixture_inputs()
    output = PrecedentAnalysisService().analyze(
        comparable,
        target,
        transactions,
        explanation_provider=_FailingExplanation(),  # type: ignore[arg-type]
    )

    assert output.ranges
    assert output.explanation is not None
    assert output.explanation.status.value == "unavailable"
    assert "deterministic results remain valid" in output.explanation.precedent_set_assessment
