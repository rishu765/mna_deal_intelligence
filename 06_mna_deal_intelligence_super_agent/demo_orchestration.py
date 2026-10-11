"""Deterministic M4/5 LangGraph orchestration, resilience, and HITL demo."""

from __future__ import annotations

from ma_deal_intelligence.contracts import CapabilityId
from ma_deal_intelligence.orchestration import (
    AnalystReviewSubmission,
    ReviewDecisionAction,
    SuperAgentApplication,
    build_workflow,
)
from ma_deal_intelligence.orchestration.fixtures import scripted_services
from ma_deal_intelligence.orchestration.models import GraphState
from ma_deal_intelligence.planning_fixtures import fixture_requests, fixture_state


def _summary(label: str, state: GraphState) -> None:
    print(f"\n{label}")
    print(f"Status: {state['status']}")
    print(f"Invoked: {', '.join(state.get('invocation_log', ()))}")
    deal_state = state["deal_state"]
    print(
        "Outputs: "
        f"P1={len(deal_state.company_intelligence)} "
        f"P2={len(deal_state.target_screening_results)} "
        f"P3={len(deal_state.trading_comps_results)} "
        f"P4={len(deal_state.precedent_transaction_results)} "
        f"P5={len(deal_state.diligence_results)}"
    )


def main() -> None:
    requests = fixture_requests()

    screening = SuperAgentApplication(build_workflow()).start(
        requests["find_targets"],
        fixture_state(target=False, documents=False),
        thread_id="demo:screening",
    )
    _summary("A. Target screening routes only to Project 2", screening)

    valuation = SuperAgentApplication(build_workflow()).start(
        requests["compare"],
        fixture_state(financials=True),
        thread_id="demo:valuation",
    )
    _summary("B. Trading comps and precedents fan out and fan in", valuation)

    full_app = SuperAgentApplication(build_workflow())
    full = full_app.start(
        requests["evaluation"],
        fixture_state(financials=False),
        thread_id="demo:full-deal",
    )
    _summary("C. Full acquisition evaluation reaches analyst review", full)
    review = full["active_review"]
    assert review is not None
    print(f"Review issue: {review.title}")
    print("Values: " + "; ".join(review.conflicting_values))
    full = full_app.resume(
        thread_id="demo:full-deal",
        submission=AnalystReviewSubmission(
            review.review_id,
            ReviewDecisionAction.RUN_BOTH,
            "demo-analyst",
            "Retain the reported case and request the adjusted scenario.",
        ),
    )
    _summary("C. Resumed after review and preserved both Project 3 runs", full)

    services, _ = scripted_services(
        {str(CapabilityId.P4_PRODUCE_VALUATION_RANGE): (RuntimeError("fixture outage"),)}
    )
    partial_app = SuperAgentApplication(build_workflow(services))
    partial = partial_app.start(
        requests["evaluation"],
        fixture_state(financials=False),
        thread_id="demo:partial-failure",
    )
    if partial.get("active_review") is not None:
        partial_review = partial["active_review"]
        assert partial_review is not None
        partial = partial_app.resume(
            thread_id="demo:partial-failure",
            submission=AnalystReviewSubmission(
                partial_review.review_id,
                ReviewDecisionAction.RUN_BOTH,
                "demo-analyst",
                "Continue with the surviving specialists and retain both EBITDA scenarios.",
            ),
        )
    _summary("D. Project 4 failure is isolated", partial)
    print("Errors: " + "; ".join(item.message for item in partial.get("errors", ())))


if __name__ == "__main__":
    main()
