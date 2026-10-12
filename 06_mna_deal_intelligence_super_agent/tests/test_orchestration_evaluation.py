from __future__ import annotations

from ma_deal_intelligence.contracts import CapabilityId
from ma_deal_intelligence.orchestration.evaluation import GraphEvaluationHarness
from ma_deal_intelligence.orchestration.models import (
    GraphEvaluationCase,
    OrchestrationStatus,
)
from ma_deal_intelligence.planning_fixtures import fixture_requests, fixture_state


def test_evaluation_harness_reports_zero_unnecessary_calls_for_fixture_routes() -> None:
    requests = fixture_requests()
    cases = (
        GraphEvaluationCase(
            "targets",
            requests["find_targets"],
            fixture_state(target=False, documents=False),
            (str(CapabilityId.P2_SOURCE_TARGETS),),
            (OrchestrationStatus.COMPLETED_WITH_WARNINGS,),
        ),
        GraphEvaluationCase(
            "valuation",
            requests["compare"],
            fixture_state(financials=True),
            (
                str(CapabilityId.P3_PRODUCE_VALUATION_RANGE),
                str(CapabilityId.P4_PRODUCE_VALUATION_RANGE),
            ),
            (OrchestrationStatus.COMPLETED_WITH_WARNINGS,),
        ),
    )
    results = tuple(GraphEvaluationHarness().evaluate(case) for case in cases)
    assert all(item.passed for item in results)
    assert all(item.routing_correct for item in results)
    assert all(item.dependency_order_correct for item in results)
    assert all(item.unnecessary_call_rate == 0.0 for item in results)
    assert all(not item.unnecessary_capabilities for item in results)
