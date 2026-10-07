from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ma_comparable_valuation import (
    CriterionEvaluation,
    CriterionOutcome,
    ManualOverrideAction,
    ManualPeerOverride,
    SelectionDecision,
    TargetFinancialProfile,
)
from ma_comparable_valuation.fixtures import FixtureTargetProfileProvider
from ma_comparable_valuation.identity import canonical_listing_key, deduplicate_companies
from ma_comparable_valuation.peer_fixtures import (
    FIXTURE_VALUATION_TIME,
    FixtureComparableUniverseProvider,
    FixtureFinancialDataProvider,
    FixtureSemanticSimilarityEvaluator,
)
from ma_comparable_valuation.selection import ComparableSelectionService


def target_profile() -> TargetFinancialProfile:
    from pathlib import Path

    path = Path(__file__).parents[1] / "data" / "targetco_profile.json"
    provider = FixtureTargetProfileProvider(path)
    target, _ = provider.load()
    return provider.get_target_profile(target)


def test_selection_is_auditable_across_all_dispositions() -> None:
    target = target_profile()
    universe = FixtureComparableUniverseProvider().get_universe(target.target)
    financials = FixtureFinancialDataProvider()

    result = ComparableSelectionService(
        semantic_evaluator=FixtureSemanticSimilarityEvaluator()
    ).select(
        target,
        universe,
        candidate_financials={
            item.identity.company_id: financials.get_financial_metrics(item.identity.company_id)
            for item in universe.companies
        },
    )

    by_id = {item.company_id: item for item in result.decisions}
    assert by_id["peer-a"].decision is SelectionDecision.INCLUDE
    assert by_id["peer-b"].decision is SelectionDecision.EXCLUDE
    assert by_id["peer-d"].decision is SelectionDecision.INSUFFICIENT_DATA
    assert by_id["peer-e"].decision is SelectionDecision.REVIEW
    assert by_id["peer-a"].evaluations
    assert by_id["peer-b"].rationale
    assert by_id["peer-d"].missing_information


def test_manual_override_preserves_analyst_rationale() -> None:
    target = target_profile()
    universe = FixtureComparableUniverseProvider().get_universe(target.target)
    financials = FixtureFinancialDataProvider()
    override = ManualPeerOverride(
        "peer-e",
        ManualOverrideAction.FORCE_INCLUDE,
        "Relevant adjacent infrastructure platform.",
        "analyst@example.test",
        FIXTURE_VALUATION_TIME,
        universe.companies[-1].evidence,
    )

    result = ComparableSelectionService(
        semantic_evaluator=FixtureSemanticSimilarityEvaluator()
    ).select(
        target,
        universe,
        candidate_financials={
            item.identity.company_id: financials.get_financial_metrics(item.identity.company_id)
            for item in universe.companies
        },
        overrides=(override,),
    )

    decision = next(item for item in result.decisions if item.company_id == "peer-e")
    assert decision.decision is SelectionDecision.INCLUDE
    assert decision.manual_override == override
    assert "Manual analyst override" in decision.rationale


def test_manual_force_exclude_can_override_an_automatic_include() -> None:
    target = target_profile()
    universe = FixtureComparableUniverseProvider().get_universe(target.target)
    financials = FixtureFinancialDataProvider()
    override = ManualPeerOverride(
        "peer-a",
        ManualOverrideAction.FORCE_EXCLUDE,
        "Customer concentration is outside the analyst mandate.",
        "analyst@example.test",
        FIXTURE_VALUATION_TIME,
        universe.companies[0].evidence,
    )

    result = ComparableSelectionService(
        semantic_evaluator=FixtureSemanticSimilarityEvaluator()
    ).select(
        target,
        universe,
        candidate_financials={
            item.identity.company_id: financials.get_financial_metrics(item.identity.company_id)
            for item in universe.companies
        },
        overrides=(override,),
    )

    decision = next(item for item in result.decisions if item.company_id == "peer-a")
    assert decision.decision is SelectionDecision.EXCLUDE
    assert decision.manual_override is not None


class FailingSemanticEvaluator:
    def evaluate(self, target, candidate, criterion):  # type: ignore[no-untyped-def]
        del target, candidate, criterion
        raise RuntimeError("offline evaluator unavailable")


def test_semantic_failure_becomes_unknown_not_pipeline_failure() -> None:
    target = target_profile()
    universe = FixtureComparableUniverseProvider().get_universe(target.target)
    financials = FixtureFinancialDataProvider()

    result = ComparableSelectionService(semantic_evaluator=FailingSemanticEvaluator()).select(
        target,
        universe,
        candidate_financials={
            item.identity.company_id: financials.get_financial_metrics(item.identity.company_id)
            for item in universe.companies
        },
    )

    semantic = [
        evaluation
        for evaluation in result.decisions[0].evaluations
        if evaluation.method.value == "semantic"
    ]
    assert semantic
    assert all(item.outcome is CriterionOutcome.UNKNOWN for item in semantic)
    assert all("failed safely" in item.rationale for item in semantic)


def test_semantic_result_must_match_requested_criterion() -> None:
    class WrongEvaluator:
        def evaluate(self, target, candidate, criterion):  # type: ignore[no-untyped-def]
            del target, candidate
            return CriterionEvaluation(
                criterion=next(item for item in type(criterion.kind) if item is not criterion.kind),
                method=criterion.method,
                outcome=CriterionOutcome.PASS,
                rationale="Wrong dimension.",
                score=Decimal("1"),
            )

    target = target_profile()
    universe = FixtureComparableUniverseProvider().get_universe(target.target)
    with pytest.raises(ValueError, match="mismatched criterion"):
        ComparableSelectionService(semantic_evaluator=WrongEvaluator()).select(
            target,
            universe,
            candidate_financials={
                "peer-a": FixtureFinancialDataProvider().get_financial_metrics("peer-a")
            },
        )


def test_identity_deduplication_uses_listing_and_preserves_evidence() -> None:
    companies = FixtureComparableUniverseProvider().get_universe(target_profile().target).companies
    duplicate = replace(
        companies[0],
        identity=replace(companies[0].identity, company_id="peer-a-alias", name="Peer A Ltd."),
        evidence=companies[1].evidence,
    )

    deduplicated, warnings = deduplicate_companies((companies[0], duplicate, companies[1]))

    assert len(deduplicated) == 2
    assert len(deduplicated[0].evidence) == 2
    assert warnings and "listing" in warnings[0]
    assert canonical_listing_key(companies[0].identity) == (
        "listing",
        "nse",
        "peera",
    )


def test_manual_override_outside_universe_is_rejected() -> None:
    target = target_profile()
    universe = FixtureComparableUniverseProvider().get_universe(target.target)
    override = ManualPeerOverride(
        "unknown",
        ManualOverrideAction.FORCE_EXCLUDE,
        "Not in universe.",
        "analyst",
        datetime(2026, 10, 7, tzinfo=UTC),
    )
    with pytest.raises(ValueError, match="outside the universe"):
        ComparableSelectionService().select(target, universe, overrides=(override,))
