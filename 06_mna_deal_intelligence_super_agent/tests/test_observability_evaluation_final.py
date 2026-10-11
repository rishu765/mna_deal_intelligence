from __future__ import annotations

from ma_deal_intelligence.evaluation_final import FinalEvaluationHarness, benchmark_cases
from ma_deal_intelligence.observability import build_run_summary, safe_trace
from ma_deal_intelligence.orchestration import SuperAgentApplication, build_workflow
from ma_deal_intelligence.planning_fixtures import fixture_requests, fixture_state


def test_final_benchmark_has_required_18_scenarios_and_separate_metrics() -> None:
    cases = benchmark_cases()
    assert len(cases) >= 18
    assert {item.fixture_condition for item in cases} >= {
        "missing_target",
        "missing_vdr",
        "partial_availability",
        "retry_success",
        "review_required",
        "multiple_review",
        "entity_conflict",
        "currency_conflict",
        "stale_rerun",
    }
    report = FinalEvaluationHarness().evaluate()
    assert len(report.case_results) == len(cases)
    assert all(item.passed for item in report.case_results)
    assert {item.subsystem for item in report.metrics} >= {
        "intent",
        "routing",
        "planning",
        "adapters",
        "orchestration",
        "reconciliation",
        "hitl",
        "synthesis",
        "resilience",
        "end_to_end",
    }


def test_run_summary_and_trace_expose_safe_operational_metadata() -> None:
    state = SuperAgentApplication(build_workflow()).start(
        fixture_requests()["compare"],
        fixture_state(financials=True),
        thread_id="observability:summary",
    )
    summary = build_run_summary(state)
    trace = safe_trace(state)
    assert summary.metrics.specialist_invocation_count == 2
    assert summary.final_assessment is not None
    assert summary.completed_capabilities
    assert trace
    assert not hasattr(trace[0], "message")
