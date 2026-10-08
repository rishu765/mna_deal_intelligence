"""Offline-first composition of the complete Project 3 valuation workflow."""

from __future__ import annotations

from dataclasses import dataclass

from ma_comparable_valuation.domain import (
    ComparableCompany,
    ComparableCompanySnapshot,
    ComparableSelectionResult,
    ComparableUniverse,
    EstimateStatus,
    FinancialMetric,
    MarketMetric,
    PeerSet,
    TargetFinancialProfile,
)
from ma_comparable_valuation.errors import NoMeaningfulValuationError
from ma_comparable_valuation.ingestion import ComparableSnapshotService
from ma_comparable_valuation.peer_fixtures import FixtureSemanticSimilarityEvaluator
from ma_comparable_valuation.selection import ComparableSelectionService
from ma_comparable_valuation.valuation import (
    FixtureValuationExplanationProvider,
    MultipleRequest,
    ValuationEngine,
    ValuationOutput,
)
from ma_comparable_valuation.valuation_fixtures import (
    VALUATION_TIME,
    demo_multiple_requests,
    demo_peer_set,
    demo_target_profile,
)


@dataclass(frozen=True, slots=True)
class EndToEndValuationResult:
    target_profile: TargetFinancialProfile
    universe: ComparableUniverse
    selection: ComparableSelectionResult
    peer_set: PeerSet
    valuation: ValuationOutput


@dataclass(frozen=True, slots=True)
class _FixtureFinancialProvider:
    peers: PeerSet

    @property
    def provider_name(self) -> str:
        return "m6_offline_fixture"

    def get_financial_metrics(self, company_id: str) -> tuple[FinancialMetric, ...]:
        snapshot = _snapshot(self.peers, company_id)
        return tuple(
            item
            for item in snapshot.financial_metrics
            if item.period.estimate_status is EstimateStatus.ACTUAL
        )


@dataclass(frozen=True, slots=True)
class _FixtureForecastProvider:
    peers: PeerSet

    @property
    def provider_name(self) -> str:
        return "m6_offline_fixture"

    def get_forecasts(self, company_id: str) -> tuple[FinancialMetric, ...]:
        snapshot = _snapshot(self.peers, company_id)
        return tuple(
            item
            for item in snapshot.financial_metrics
            if item.period.estimate_status is EstimateStatus.ESTIMATE
        )


@dataclass(frozen=True, slots=True)
class _FixtureMarketProvider:
    peers: PeerSet

    @property
    def provider_name(self) -> str:
        return "m6_offline_fixture"

    def get_market_metrics(
        self, company_id: str, *, valuation_time: object
    ) -> tuple[MarketMetric, ...]:
        del valuation_time
        return _snapshot(self.peers, company_id).market_metrics


@dataclass(frozen=True, slots=True)
class OfflineValuationService:
    """Compose existing M1-M5 services using public-safe fixture providers."""

    valuation_engine: ValuationEngine = ValuationEngine()

    def run(
        self,
        *,
        target_profile: TargetFinancialProfile | None = None,
        requests: tuple[MultipleRequest, ...] | None = None,
        include_explanation: bool = True,
        require_range: bool = True,
    ) -> EndToEndValuationResult:
        target = target_profile or demo_target_profile()
        source_peers = demo_peer_set()
        universe = _universe(target, source_peers)
        financial = _FixtureFinancialProvider(source_peers)
        selection = ComparableSelectionService(
            semantic_evaluator=FixtureSemanticSimilarityEvaluator()
        ).select(
            target,
            universe,
            candidate_financials={
                item.identity.company_id: financial.get_financial_metrics(item.identity.company_id)
                for item in universe.companies
            },
        )
        peer_set = ComparableSnapshotService(
            financial,
            _FixtureMarketProvider(source_peers),
            _FixtureForecastProvider(source_peers),
        ).build_peer_set(universe, selection, valuation_time=VALUATION_TIME)
        valuation = self.valuation_engine.build_output(
            target,
            peer_set,
            requests or demo_multiple_requests(),
            FixtureValuationExplanationProvider() if include_explanation else None,
        )
        if require_range and not valuation.ranges:
            raise NoMeaningfulValuationError(
                "no requested valuation method has a compatible positive target metric"
            )
        return EndToEndValuationResult(target, universe, selection, peer_set, valuation)


def _universe(target: TargetFinancialProfile, peers: PeerSet) -> ComparableUniverse:
    companies: tuple[ComparableCompany, ...] = tuple(item.company for item in peers.snapshots)
    evidence = tuple(dict.fromkeys(item for company in companies for item in company.evidence))
    return ComparableUniverse(
        "m6-offline-universe",
        target.target.identity.company_id,
        companies,
        "m6_offline_fixture",
        VALUATION_TIME,
        evidence,
    )


def _snapshot(peers: PeerSet, company_id: str) -> ComparableCompanySnapshot:
    return next(item for item in peers.snapshots if item.company.identity.company_id == company_id)
