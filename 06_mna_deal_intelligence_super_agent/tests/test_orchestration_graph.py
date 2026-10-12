from __future__ import annotations

from ma_deal_intelligence.contracts import CapabilityId
from ma_deal_intelligence.orchestration import (
    AnalystReviewSubmission,
    OrchestrationStatus,
    ReviewDecisionAction,
    SuperAgentApplication,
    build_workflow,
)
from ma_deal_intelligence.orchestration.fixtures import scripted_services
from ma_deal_intelligence.orchestration.models import TraceEventType
from ma_deal_intelligence.planning_fixtures import fixture_requests, fixture_state
from ma_deal_intelligence.workflow import ExecutionStatus


def test_graph_compiles_and_target_sourcing_invokes_only_project_2() -> None:
    graph = build_workflow()
    assert graph.name == "mna_deal_intelligence_super_agent"
    state = SuperAgentApplication(graph).start(
        fixture_requests()["find_targets"],
        fixture_state(target=False, documents=False),
        thread_id="graph:targets",
    )
    assert state["status"] is OrchestrationStatus.COMPLETED_WITH_WARNINGS
    assert any(warning.code == "FIXTURE_DATA" for warning in state["deal_state"].warnings)
    assert state["invocation_log"] == (CapabilityId.P2_SOURCE_TARGETS,)
    assert state["deal_state"].target_screening_results
    assert not state["deal_state"].trading_comps_results
    assert not state["deal_state"].precedent_transaction_results
    assert not state["deal_state"].diligence_results
    assert (
        state["capability_states"][CapabilityId.P5_PRODUCE_DILIGENCE_FINDINGS].status
        is ExecutionStatus.SKIPPED
    )
    assert state["terminal_result"].skipped_capabilities


def test_valuation_plan_fans_out_and_fans_in_without_unnecessary_projects() -> None:
    state = SuperAgentApplication(build_workflow()).start(
        fixture_requests()["compare"],
        fixture_state(financials=True),
        thread_id="graph:valuation",
    )
    expected = {
        str(CapabilityId.P3_PRODUCE_VALUATION_RANGE),
        str(CapabilityId.P4_PRODUCE_VALUATION_RANGE),
    }
    assert set(state["invocation_log"]) == expected
    assert len(state["execution_plan"].stages) == 1
    assert state["execution_plan"].stages[0].parallelizable
    assert len(state["deal_state"].valuation_outputs) == 2
    assert state["reconciliation"].snapshot.valuation_comparison.entries


def test_dependency_stage_completes_project_1_before_project_3() -> None:
    state = SuperAgentApplication(build_workflow()).start(
        fixture_requests()["evaluation"],
        fixture_state(financials=False),
        thread_id="graph:dependency-order",
    )
    invoked = [
        item.capability_id
        for item in state["trace"]
        if item.event_type is TraceEventType.ADAPTER_INVOKED
    ]
    assert invoked.index(CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE) < invoked.index(
        CapabilityId.P3_PRODUCE_VALUATION_RANGE
    )
    assert CapabilityId.P2_SOURCE_TARGETS not in invoked


def test_missing_vdr_routes_to_structured_waiting_for_input() -> None:
    state = SuperAgentApplication(build_workflow()).start(
        fixture_requests()["diligence"],
        fixture_state(documents=False),
        thread_id="graph:missing-vdr",
    )
    assert state["status"] is OrchestrationStatus.WAITING_FOR_INPUT
    assert state["clarification"] is not None
    assert state["clarification"].requirements[0].missing_field == "documents"
    assert not state["invocation_log"]
    assert state["terminal_result"].status is OrchestrationStatus.WAITING_FOR_INPUT


def test_nonblocking_project_4_failure_keeps_project_3_result() -> None:
    services, _ = scripted_services(
        {str(CapabilityId.P4_PRODUCE_VALUATION_RANGE): (RuntimeError("fixture outage"),)}
    )
    state = SuperAgentApplication(build_workflow(services)).start(
        fixture_requests()["compare"],
        fixture_state(financials=True),
        thread_id="graph:partial-failure",
    )
    assert state["status"] is OrchestrationStatus.COMPLETED_WITH_WARNINGS
    assert state["deal_state"].trading_comps_results
    assert not state["deal_state"].precedent_transaction_results
    assert (
        state["capability_states"][CapabilityId.P4_PRODUCE_VALUATION_RANGE].status
        is ExecutionStatus.FAILED
    )
    assert state["errors"][0].message == "fixture outage"


def test_full_deal_project_4_failure_preserves_projects_1_3_and_5() -> None:
    services, _ = scripted_services(
        {str(CapabilityId.P4_PRODUCE_VALUATION_RANGE): (RuntimeError("fixture outage"),)}
    )
    app = SuperAgentApplication(build_workflow(services))
    state = app.start(
        fixture_requests()["evaluation"],
        fixture_state(financials=False),
        thread_id="graph:full-partial-failure",
    )
    review = state["active_review"]
    assert review is not None
    state = app.resume(
        thread_id="graph:full-partial-failure",
        submission=AnalystReviewSubmission(
            review.review_id,
            ReviewDecisionAction.RUN_BOTH,
            "Reviewer",
            "Continue with both EBITDA scenarios and surviving specialists.",
        ),
    )
    assert state["status"] is OrchestrationStatus.COMPLETED_WITH_WARNINGS
    assert state["deal_state"].company_intelligence
    assert len(state["deal_state"].trading_comps_results) == 2
    assert state["deal_state"].diligence_results
    assert not state["deal_state"].precedent_transaction_results
