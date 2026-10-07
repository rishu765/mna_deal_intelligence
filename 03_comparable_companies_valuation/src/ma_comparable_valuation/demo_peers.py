"""Offline M2/3 selection-to-ingestion demonstration; no valuation is calculated."""

from __future__ import annotations

import json
from pathlib import Path

from ma_comparable_valuation.domain import (
    ManualOverrideAction,
    ManualPeerOverride,
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


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    target_provider = FixtureTargetProfileProvider(project_root / "data" / "targetco_profile.json")
    target, _ = target_provider.load()
    profile = target_provider.get_target_profile(target)
    universe = FixtureComparableUniverseProvider().get_universe(profile.target)
    financial_provider = FixtureFinancialDataProvider()
    selection = ComparableSelectionService(
        semantic_evaluator=FixtureSemanticSimilarityEvaluator()
    ).select(
        profile,
        universe,
        candidate_financials={
            item.identity.company_id: financial_provider.get_financial_metrics(
                item.identity.company_id
            )
            for item in universe.companies
        },
        overrides=(
            ManualPeerOverride(
                company_id="peer-e",
                action=ManualOverrideAction.FORCE_INCLUDE,
                rationale=(
                    "Analyst considers its financial-infrastructure product adjacency relevant."
                ),
                analyst="fixture-analyst",
                recorded_at=FIXTURE_VALUATION_TIME,
                evidence=universe.companies[-1].evidence,
            ),
        ),
    )
    peer_set = ComparableSnapshotService(
        financial_provider=financial_provider,
        market_provider=FixtureMarketDataProvider(),
        forecast_provider=FixtureForecastDataProvider(),
    ).build_peer_set(universe, selection, valuation_time=FIXTURE_VALUATION_TIME)

    output = {
        "notice": (
            "No enterprise values, trading multiples, statistics, or valuations are calculated."
        ),
        "target": profile.target.identity.name,
        "universe": [item.identity.name for item in universe.companies],
        "selection": [
            {
                "company_id": item.company_id,
                "decision": item.decision.value,
                "score": None if item.score is None else str(item.score),
                "coverage": str(item.confidence),
                "rationale": item.rationale,
                "manual_override": (
                    None if item.manual_override is None else item.manual_override.action.value
                ),
                "criteria": [
                    {
                        "criterion": value.criterion.value,
                        "method": value.method.value,
                        "outcome": value.outcome.value,
                        "rationale": value.rationale,
                    }
                    for value in item.evaluations
                ],
            }
            for item in selection.decisions
        ],
        "snapshots": [
            {
                "company": item.company.identity.name,
                "as_of": item.as_of.isoformat(),
                "financial_metrics": [
                    {
                        "name": value.name.value,
                        "value": str(value.value),
                        "currency": value.currency,
                        "unit": value.unit.value,
                        "period": value.period.label,
                        "estimate_status": value.period.estimate_status.value,
                        "basis": value.basis.value,
                        "evidence_ids": [e.evidence_id for e in value.evidence],
                    }
                    for value in item.financial_metrics
                ],
                "market_metrics": [
                    {
                        "kind": value.kind.value,
                        "value": str(value.value),
                        "currency": value.currency,
                        "unit": value.unit.value,
                        "as_of": value.as_of.isoformat(),
                        "evidence_ids": [e.evidence_id for e in value.evidence],
                    }
                    for value in item.market_metrics
                ],
                "quality_flags": [value.value for value in item.quality_flags],
                "warnings": list(item.warnings),
            }
            for item in peer_set.snapshots
        ],
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
