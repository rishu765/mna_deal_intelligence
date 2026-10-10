from __future__ import annotations

import pytest

from ma_deal_intelligence.adapters import AdapterMode, Project1Adapter, Project4Adapter
from ma_deal_intelligence.contracts import CapabilityId
from ma_deal_intelligence.intent import DealIntent, IntentClassification, IntentClassifier
from ma_deal_intelligence.planning import (
    ExecutionPlan,
    ExecutionPlanner,
    PlanValidationError,
    validate_dependency_graph,
)
from ma_deal_intelligence.planning_fixtures import fixture_requests, fixture_state
from ma_deal_intelligence.registry import default_registry
from ma_deal_intelligence.requests import UserDealRequest


@pytest.mark.parametrize(
    ("fixture_name", "intent"),
    (
        ("company_research", DealIntent.COMPANY_RESEARCH),
        ("find_targets", DealIntent.FIND_TARGETS),
        ("trading_comps", DealIntent.RUN_TRADING_COMPS),
        ("precedents", DealIntent.RUN_PRECEDENTS),
        ("diligence", DealIntent.RUN_DUE_DILIGENCE),
        ("compare", DealIntent.COMPARE_VALUATION_METHODS),
        ("evaluation", DealIntent.EVALUATE_ACQUISITION),
    ),
)
def test_rule_classifier_examples(fixture_name: str, intent: DealIntent) -> None:
    result = IntentClassifier().classify(fixture_requests()[fixture_name])
    assert result.primary_intent is intent


def test_multi_intent_ambiguous_and_mock_model_fallback() -> None:
    requests = fixture_requests()
    result = IntentClassifier().classify(requests["multi_intent"])
    assert result.intents == (DealIntent.FIND_TARGETS, DealIntent.VALUE_TARGET)

    ambiguous = UserDealRequest("ambiguous", "Help me understand this situation")
    assert IntentClassifier().classify(ambiguous).ambiguous

    class MockModel:
        def classify(self, request: UserDealRequest) -> IntentClassification:
            return IntentClassification(DealIntent.COMPANY_RESEARCH, classifier="mock_llm")

    assert IntentClassifier(MockModel()).classify(ambiguous).classifier == "mock_llm"


def _plan(name: str, *, documents: bool = True, financials: bool = True) -> ExecutionPlan:
    request = fixture_requests()[name]
    state = fixture_state(
        target=request.target is not None, documents=documents, financials=financials
    )
    classification = IntentClassifier().classify(request)
    return ExecutionPlanner(default_registry()).build(request, classification, state)


def test_planner_avoids_unnecessary_specialists() -> None:
    find = _plan("find_targets", financials=False)
    assert [step.capability_id for step in find.steps] == [CapabilityId.P2_SOURCE_TARGETS]
    diligence = _plan("diligence")
    assert [step.capability_id for step in diligence.steps] == [
        CapabilityId.P5_PRODUCE_DILIGENCE_FINDINGS
    ]
    compare = _plan("compare")
    assert {step.capability_id for step in compare.steps} == {
        CapabilityId.P3_PRODUCE_VALUATION_RANGE,
        CapabilityId.P4_PRODUCE_VALUATION_RANGE,
    }


def test_full_evaluation_parallel_stages_and_p2_skip() -> None:
    plan = _plan("evaluation", financials=False)
    selected = {step.capability_id for step in plan.steps}
    assert selected == {
        CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE,
        CapabilityId.P3_PRODUCE_VALUATION_RANGE,
        CapabilityId.P4_PRODUCE_VALUATION_RANGE,
        CapabilityId.P5_PRODUCE_DILIGENCE_FINDINGS,
    }
    assert any(stage.parallelizable for stage in plan.stages)
    assert any("already specified" in item.reason for item in plan.skipped_capabilities)


def test_missing_inputs_and_cycle_detection() -> None:
    missing_target = _plan("missing_target", documents=False, financials=False)
    missing = {item.missing_field for item in missing_target.required_user_inputs}
    assert "target_entity" in missing
    assert "documents" in missing
    missing_vdr = _plan("missing_vdr", documents=False)
    assert {item.missing_field for item in missing_vdr.required_user_inputs} == {"documents"}
    with pytest.raises(PlanValidationError, match="cycle"):
        validate_dependency_graph({"a": {"b"}, "b": {"a"}})


def test_partial_availability_produces_partial_plan_warning() -> None:
    registry = default_registry()
    # Replace only P4 with an unhealthy native adapter.
    registry._adapters[str(CapabilityId.P4_PRODUCE_VALUATION_RANGE)] = Project4Adapter(  # noqa: SLF001
        mode=AdapterMode.NATIVE
    )
    request = fixture_requests()["compare"]
    state = fixture_state(financials=True)
    plan = ExecutionPlanner(registry).build(request, IntentClassifier().classify(request), state)
    assert [step.capability_id for step in plan.steps] == [CapabilityId.P3_PRODUCE_VALUATION_RANGE]
    assert plan.warnings[0].code == "CAPABILITY_UNAVAILABLE"

    registry = default_registry()
    registry._adapters[str(CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE)] = (  # noqa: SLF001
        Project1Adapter(mode=AdapterMode.NATIVE)
    )
    request = fixture_requests()["evaluation"]
    state = fixture_state(financials=False)
    plan = ExecutionPlanner(registry).build(request, IntentClassifier().classify(request), state)
    p3 = next(
        step for step in plan.steps if step.capability_id == CapabilityId.P3_PRODUCE_VALUATION_RANGE
    )
    assert p3.missing_inputs == ("target_financials",)
