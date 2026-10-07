from dataclasses import replace
from decimal import Decimal

from ma_comparable_valuation import (
    ComparableSelectionResult,
    ComparableUniverse,
    DataQualityFlag,
    FinancialUnit,
    ManualOverrideAction,
    ManualPeerOverride,
    MarketMetricKind,
)
from ma_comparable_valuation.fixtures import FixtureTargetProfileProvider
from ma_comparable_valuation.ingestion import ComparableSnapshotService
from ma_comparable_valuation.peer_fixtures import (
    FIXTURE_VALUATION_TIME,
    FixtureComparableUniverseProvider,
    FixtureFinancialDataProvider,
    FixtureForecastDataProvider,
    FixtureMarketDataProvider,
    FixtureSemanticSimilarityEvaluator,
)
from ma_comparable_valuation.selection import ComparableSelectionService


def _inputs() -> tuple[ComparableUniverse, ComparableSelectionResult]:
    from pathlib import Path

    target_provider = FixtureTargetProfileProvider(
        Path(__file__).parents[1] / "data" / "targetco_profile.json"
    )
    target, _ = target_provider.load()
    profile = target_provider.get_target_profile(target)
    universe = FixtureComparableUniverseProvider().get_universe(profile.target)
    financial = FixtureFinancialDataProvider()
    selection = ComparableSelectionService(
        semantic_evaluator=FixtureSemanticSimilarityEvaluator()
    ).select(
        profile,
        universe,
        candidate_financials={
            item.identity.company_id: financial.get_financial_metrics(item.identity.company_id)
            for item in universe.companies
        },
        overrides=(
            ManualPeerOverride(
                "peer-e",
                ManualOverrideAction.FORCE_INCLUDE,
                "Adjacent platform.",
                "analyst",
                FIXTURE_VALUATION_TIME,
                universe.companies[-1].evidence,
            ),
        ),
    )
    return universe, selection


def test_full_selection_to_ingestion_flow_preserves_periods_and_as_of() -> None:
    universe, selection = _inputs()
    peer_set = ComparableSnapshotService(
        FixtureFinancialDataProvider(),
        FixtureMarketDataProvider(),
        FixtureForecastDataProvider(),
    ).build_peer_set(universe, selection, valuation_time=FIXTURE_VALUATION_TIME)

    assert {item.company.identity.company_id for item in peer_set.snapshots} == {
        "peer-a",
        "peer-c",
        "peer-e",
    }
    peer_a = peer_set.snapshots[0]
    assert peer_a.as_of == FIXTURE_VALUATION_TIME
    assert {item.period.label for item in peer_a.financial_metrics} == {
        "LTM Jun-2026",
        "FY2027E",
    }
    assert all(
        item.unit in {FinancialUnit.MILLION, FinancialUnit.PER_SHARE}
        for item in peer_a.financial_metrics
    )
    assert DataQualityFlag.COMPLETE_ENOUGH_FOR_VALUATION in peer_a.quality_flags
    assert peer_a.capital_structure is not None
    assert all(item.evidence for item in peer_a.financial_metrics)
    assert all(item.evidence for item in peer_a.market_metrics)


def test_stale_market_data_and_negative_profitability_are_preserved() -> None:
    universe, selection = _inputs()
    peer_set = ComparableSnapshotService(
        FixtureFinancialDataProvider(), FixtureMarketDataProvider()
    ).build_peer_set(universe, selection, valuation_time=FIXTURE_VALUATION_TIME)
    by_id = {item.company.identity.company_id: item for item in peer_set.snapshots}

    assert DataQualityFlag.STALE_MARKET_DATA in by_id["peer-c"].quality_flags
    assert any(
        DataQualityFlag.STALE in item.quality_flags
        for item in by_id["peer-c"].market_metrics
        if item.kind is MarketMetricKind.SHARE_PRICE
    )
    assert DataQualityFlag.NEGATIVE_EBITDA in by_id["peer-e"].quality_flags
    assert DataQualityFlag.NEGATIVE_EBIT in by_id["peer-e"].quality_flags
    assert DataQualityFlag.MISSING_MARKET_DATA in by_id["peer-e"].quality_flags
    assert any(item.value < 0 for item in by_id["peer-e"].financial_metrics)
    assert not any(item.kind is MarketMetricKind.DEBT for item in by_id["peer-e"].market_metrics)


def test_provider_failure_produces_partial_snapshot() -> None:
    universe, selection = _inputs()
    peer_set = ComparableSnapshotService(
        FixtureFinancialDataProvider(fail_company_ids=("peer-a",)),
        FixtureMarketDataProvider(fail_company_ids=("peer-a",)),
    ).build_peer_set(universe, selection, valuation_time=FIXTURE_VALUATION_TIME)
    peer_a = next(
        item for item in peer_set.snapshots if item.company.identity.company_id == "peer-a"
    )

    assert DataQualityFlag.MISSING_FINANCIALS in peer_a.quality_flags
    assert DataQualityFlag.MISSING_MARKET_DATA in peer_a.quality_flags
    assert any(item.kind.value == "provider_failure" for item in peer_a.issues)


def test_same_currency_units_are_normalized_and_market_conflicts_retained() -> None:
    universe, selection = _inputs()
    base_financial = FixtureFinancialDataProvider().get_financial_metrics("peer-a")
    crore_revenue = replace(
        base_financial[0],
        metric_id="crore-revenue",
        value=Decimal("420"),
        unit=FinancialUnit.CRORE,
    )

    class FinancialProvider:
        @property
        def provider_name(self) -> str:
            return "test"

        def get_financial_metrics(self, company_id: str):  # type: ignore[no-untyped-def]
            return (crore_revenue,) if company_id == "peer-a" else ()

    market_values = FixtureMarketDataProvider().get_market_metrics(
        "peer-a", valuation_time=FIXTURE_VALUATION_TIME
    )
    debt = next(item for item in market_values if item.kind is MarketMetricKind.DEBT)
    conflicting_debt = replace(debt, metric_id="second-debt", value=debt.value + 1)

    class MarketProvider:
        @property
        def provider_name(self) -> str:
            return "test"

        def get_market_metrics(self, company_id: str, *, valuation_time):  # type: ignore[no-untyped-def]
            del valuation_time
            return (*market_values, conflicting_debt) if company_id == "peer-a" else ()

    peer_set = ComparableSnapshotService(FinancialProvider(), MarketProvider()).build_peer_set(
        universe, selection, valuation_time=FIXTURE_VALUATION_TIME
    )
    peer_a = next(
        item for item in peer_set.snapshots if item.company.identity.company_id == "peer-a"
    )

    assert peer_a.financial_metrics[0].value == Decimal("4200")
    assert peer_a.financial_metrics[0].unit is FinancialUnit.MILLION
    assert len(peer_a.conflicts) == 1
    assert DataQualityFlag.CONFLICTING in peer_a.quality_flags
