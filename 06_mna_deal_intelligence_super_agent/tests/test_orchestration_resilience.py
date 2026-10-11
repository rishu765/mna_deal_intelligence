from __future__ import annotations

from typing import cast

from ma_deal_intelligence.contracts import CapabilityId
from ma_deal_intelligence.orchestration import (
    OrchestrationPolicy,
    OrchestrationStatus,
    RetryPolicy,
    SuperAgentApplication,
    TransientAdapterError,
    build_workflow,
)
from ma_deal_intelligence.orchestration.fixtures import scripted_services
from ma_deal_intelligence.orchestration.models import GraphState, TraceEventType
from ma_deal_intelligence.orchestration.nodes import GraphInvariantError, OrchestrationNodes
from ma_deal_intelligence.orchestration.services import default_services
from ma_deal_intelligence.planning_fixtures import fixture_requests, fixture_state


def test_retryable_project_3_failure_succeeds_once_without_duplicate_result() -> None:
    capability = str(CapabilityId.P3_PRODUCE_VALUATION_RANGE)
    services, invoker = scripted_services(
        {capability: (TransientAdapterError("temporary provider failure"),)}
    )
    state = SuperAgentApplication(build_workflow(services)).start(
        fixture_requests()["compare"],
        fixture_state(financials=True),
        thread_id="resilience:retry-success",
    )
    assert invoker.calls[capability] == 2
    assert state["retry_counts"][capability] == 1
    assert len(state["deal_state"].trading_comps_results) == 1
    assert len([item for item in state["errors"] if item.capability == capability]) == 1
    assert any(item.event_type is TraceEventType.RETRY_SCHEDULED for item in state["trace"])
    assert state["status"] is OrchestrationStatus.COMPLETED_WITH_WARNINGS


def test_retry_exhaustion_preserves_independent_project_4_output() -> None:
    capability = str(CapabilityId.P3_PRODUCE_VALUATION_RANGE)
    services, invoker = scripted_services(
        {
            capability: (
                TransientAdapterError("failure one"),
                TransientAdapterError("failure two"),
            )
        }
    )
    policy = OrchestrationPolicy(retry=RetryPolicy(max_attempts=2))
    app = SuperAgentApplication(build_workflow(services, policy=policy))
    state = app.start(
        fixture_requests()["compare"],
        fixture_state(financials=True),
        thread_id="resilience:retry-exhausted",
    )
    assert invoker.calls[capability] == 2
    assert not state["deal_state"].trading_comps_results
    assert state["deal_state"].precedent_transaction_results
    assert state["status"] is OrchestrationStatus.REVIEW_REQUIRED
    review = state["active_review"]
    assert review is not None
    from ma_deal_intelligence.orchestration import (
        AnalystReviewSubmission,
        ReviewDecisionAction,
    )

    state = app.resume(
        thread_id="resilience:retry-exhausted",
        submission=AnalystReviewSubmission(
            review.review_id,
            ReviewDecisionAction.CONTINUE_WITH_WARNINGS,
            "Reviewer",
            "Continue with the surviving precedent output.",
        ),
    )
    assert state["status"] is OrchestrationStatus.COMPLETED_WITH_WARNINGS
    assert len(state["errors"]) == 2


def test_orchestration_preserves_specialist_metric_and_valuation_numbers() -> None:
    state = SuperAgentApplication(build_workflow()).start(
        fixture_requests()["compare"],
        fixture_state(financials=True),
        thread_id="resilience:numeric-integrity",
    )
    p3 = state["deal_state"].trading_comps_results[0].payload
    metric = p3.financial_metrics[0]
    valuation = p3.valuations[0]
    canonical_metric = next(
        item for item in state["deal_state"].financial_metrics if item.metric_id == metric.metric_id
    )
    canonical_valuation = next(
        item
        for item in state["deal_state"].valuation_outputs
        if item.valuation_id == valuation.valuation_id
    )
    assert canonical_metric.value == metric.value
    assert (canonical_valuation.low, canonical_valuation.midpoint, canonical_valuation.high) == (
        valuation.low,
        valuation.midpoint,
        valuation.high,
    )


def test_invariant_rejects_completed_state_that_hides_errors() -> None:
    services = default_services()
    nodes = OrchestrationNodes(services, OrchestrationPolicy())
    state = SuperAgentApplication(build_workflow()).start(
        fixture_requests()["compare"],
        fixture_state(financials=True),
        thread_id="resilience:invariant-source",
    )
    bad_state = cast(GraphState, dict(state))
    bad_state["errors"] = state["errors"] + state["deal_state"].errors
    if not bad_state["errors"]:
        from ma_deal_intelligence.evidence import ProjectId
        from ma_deal_intelligence.workflow import DealError

        bad_state["errors"] = (
            DealError("error:forced", "FORCED", ProjectId.PROJECT_6, None, False, False, "forced"),
        )
    try:
        nodes.assert_invariants(bad_state, state["deal_state"], OrchestrationStatus.COMPLETED)
    except GraphInvariantError as exc:
        assert "cannot hide" in str(exc)
    else:
        raise AssertionError("completed state accepted hidden errors")


def test_checkpoint_reads_are_idempotent_and_threads_are_isolated() -> None:
    app = SuperAgentApplication(build_workflow())
    first = app.start(
        fixture_requests()["find_targets"],
        fixture_state(target=False, documents=False),
        thread_id="resilience:isolation-a",
    )
    second = app.start(
        fixture_requests()["compare"],
        fixture_state(financials=True),
        thread_id="resilience:isolation-b",
    )
    reread = app.state(thread_id="resilience:isolation-a")
    assert reread["run_id"] == first["run_id"]
    assert reread["trace"] == first["trace"]
    assert second["run_id"] != first["run_id"]
    assert second["invocation_log"] != first["invocation_log"]
