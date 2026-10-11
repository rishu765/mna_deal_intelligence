from __future__ import annotations

from ma_deal_intelligence.contracts import CapabilityId
from ma_deal_intelligence.orchestration import (
    AnalystReviewSubmission,
    OrchestrationPolicy,
    OrchestrationStatus,
    ReviewDecisionAction,
    SuperAgentApplication,
    build_workflow,
)
from ma_deal_intelligence.orchestration.fixtures import rich_review_services
from ma_deal_intelligence.orchestration.models import GraphState, TraceEventType
from ma_deal_intelligence.planning_fixtures import fixture_requests, fixture_state


def _paused(thread_id: str, *, rich: bool = False) -> tuple[SuperAgentApplication, GraphState]:
    graph = build_workflow(rich_review_services()) if rich else build_workflow()
    app = SuperAgentApplication(graph)
    state = app.start(
        fixture_requests()["evaluation"],
        fixture_state(financials=False),
        thread_id=thread_id,
    )
    return app, state


def test_checkpointed_review_payload_contains_conflicting_values_and_evidence() -> None:
    app, state = _paused("hitl:payload")
    assert state["status"] is OrchestrationStatus.REVIEW_REQUIRED
    review = state["active_review"]
    assert review is not None
    assert review.title == "EBITDA basis mismatch"
    assert any("100" in item and "reported" in item for item in review.conflicting_values)
    assert any("85" in item and "adjusted" in item for item in review.conflicting_values)
    assert "valuation:p3:trading-comps" in review.affected_output_ids
    assert review.evidence_refs
    checkpointed = app.state(thread_id="hitl:payload")
    assert checkpointed["active_review"] == review
    assert checkpointed["deal_state"] == state["deal_state"]


def test_run_both_resumes_reruns_only_project_3_and_preserves_versions() -> None:
    app, state = _paused("hitl:run-both")
    review = state["active_review"]
    assert review is not None
    before = state["deal_state"].trading_comps_results[0]
    completed = app.resume(
        thread_id="hitl:run-both",
        submission=AnalystReviewSubmission(
            review.review_id,
            ReviewDecisionAction.RUN_BOTH,
            "Deal Team Reviewer",
            "Retain reported valuation and request the approved adjusted scenario.",
        ),
    )
    assert completed["status"] is OrchestrationStatus.COMPLETED_WITH_WARNINGS
    results = completed["deal_state"].trading_comps_results
    assert len(results) == 2
    assert results[0].run_id == before.run_id
    assert results[1].run_id != before.run_id
    assert completed["rerun_iteration"] == 1
    assert completed["review_history"][0].selected_action is ReviewDecisionAction.RUN_BOTH
    p3_versions = tuple(
        item
        for item in completed["deal_state"].artifact_versions
        if item.artifact_id.startswith("result:project_3:p3.produce_valuation_range")
    )
    assert len(p3_versions) == 2
    assert p3_versions[0].superseded_by == p3_versions[1].artifact_id
    assert (
        len([item for item in completed["trace"] if item.event_type is TraceEventType.RECONCILED])
        == 2
    )
    p3_attempts = [
        item
        for item in completed["specialist_attempts"]
        if item.capability_id == CapabilityId.P3_PRODUCE_VALUATION_RANGE
    ]
    assert len(p3_attempts) == 2
    assert all(
        item.capability_id != CapabilityId.P4_PRODUCE_VALUATION_RANGE
        for item in completed["specialist_attempts"]
        if item.rerun_iteration == 1
    )


def test_multiple_review_events_are_sequential_and_audited() -> None:
    app, state = _paused("hitl:multiple", rich=True)
    first = state["active_review"]
    assert first is not None
    state = app.resume(
        thread_id="hitl:multiple",
        submission=AnalystReviewSubmission(
            first.review_id,
            ReviewDecisionAction.RUN_BOTH,
            "Reviewer One",
            "Compare both EBITDA scenarios.",
        ),
    )
    second = state["active_review"]
    assert state["status"] is OrchestrationStatus.REVIEW_REQUIRED
    assert second is not None
    assert "Change-of-control" in second.title
    state = app.resume(
        thread_id="hitl:multiple",
        submission=AnalystReviewSubmission(
            second.review_id,
            ReviewDecisionAction.ACCEPT,
            "Reviewer Two",
            "Accept the execution risk for this analysis.",
        ),
    )
    assert len(state["review_history"]) >= 2
    assert state["review_history"][0].review_id == first.review_id
    assert state["review_history"][1].review_id == second.review_id


def test_invalid_review_action_is_structured_failure() -> None:
    app, state = _paused("hitl:invalid")
    review = state["active_review"]
    assert review is not None
    failed = app.resume(
        thread_id="hitl:invalid",
        submission=AnalystReviewSubmission(
            review.review_id,
            ReviewDecisionAction.ACCEPT,
            "Reviewer",
            "Invalid for this review.",
        ),
    )
    assert failed["status"] is OrchestrationStatus.FAILED
    assert failed["errors"][-1].code == "INVALID_REVIEW_DECISION"


def test_analyst_can_cancel_at_material_contract_review() -> None:
    app, state = _paused("hitl:cancel", rich=True)
    first = state["active_review"]
    assert first is not None
    state = app.resume(
        thread_id="hitl:cancel",
        submission=AnalystReviewSubmission(
            first.review_id,
            ReviewDecisionAction.KEEP_REPORTED,
            "Valuation Reviewer",
            "Retain the reported valuation case.",
        ),
    )
    contract_review = state["active_review"]
    assert contract_review is not None
    cancelled = app.resume(
        thread_id="hitl:cancel",
        submission=AnalystReviewSubmission(
            contract_review.review_id,
            ReviewDecisionAction.CANCEL,
            "Legal Reviewer",
            "Stop pending consent analysis.",
        ),
    )
    assert cancelled["status"] is OrchestrationStatus.CANCELLED
    assert cancelled["terminal_result"].status is OrchestrationStatus.CANCELLED
    assert len(cancelled["review_history"]) == 2


def test_review_iteration_bound_prevents_an_infinite_review_loop() -> None:
    app = SuperAgentApplication(
        build_workflow(rich_review_services(), policy=OrchestrationPolicy(max_review_iterations=1))
    )
    state = app.start(
        fixture_requests()["evaluation"],
        fixture_state(financials=False),
        thread_id="hitl:bounded",
    )
    review = state["active_review"]
    assert review is not None
    completed = app.resume(
        thread_id="hitl:bounded",
        submission=AnalystReviewSubmission(
            review.review_id,
            ReviewDecisionAction.KEEP_REPORTED,
            "Reviewer",
            "Use the reported case for this run.",
        ),
    )
    assert completed["status"] is OrchestrationStatus.COMPLETED_WITH_WARNINGS
    assert completed["active_review"] is None
    assert any("Maximum analyst review iterations" in item for item in completed["warnings"])
