"""Polished deterministic Project 6 V1 demo with no network or model dependency."""

from __future__ import annotations

from ma_deal_intelligence.evaluation_final import FinalEvaluationHarness
from ma_deal_intelligence.observability import build_run_summary
from ma_deal_intelligence.orchestration import (
    AnalystReviewSubmission,
    ReviewDecisionAction,
    SuperAgentApplication,
    build_workflow,
)
from ma_deal_intelligence.orchestration.fixtures import rich_review_services
from ma_deal_intelligence.orchestration.models import GraphState
from ma_deal_intelligence.planning_fixtures import fixture_requests, fixture_state


def _route(label: str, state: GraphState) -> None:
    plan = state.get("execution_plan")
    print(f"\n{label}")
    print("REQUEST:", state["request"].user_query)
    print("INTENT:", state["classification"].primary_intent)
    print("PLAN:", ", ".join(step.capability_id for step in plan.steps) if plan else "none")
    print("STATUS:", state["status"].value)


def _final(state: GraphState) -> None:
    output = state.get("final_output")
    assert output is not None
    section_by_id = {item.section_id: item for item in output.sections}
    for section_id in (
        "deal_overview",
        "strategic_rationale",
        "unified_valuation",
        "due_diligence",
        "reconciliation",
        "analyst_decisions",
        "key_risks",
        "open_questions",
    ):
        section = section_by_id[section_id]
        print(f"\n{section.title.upper()}")
        print(section.summary)
        for item in section.items[:5]:
            print("-", item.statement)
    print("\nFINAL DEAL ASSESSMENT")
    print(output.assessment.classification.value)
    for reason in output.assessment.policy_reasons:
        print("-", reason)
    print("\nEVIDENCE")
    for citation in output.citations[:8]:
        print("-", citation.label)


def main() -> None:
    requests = fixture_requests()
    screening = SuperAgentApplication(build_workflow()).start(
        requests["find_targets"],
        fixture_state(target=False, documents=False),
        thread_id="final-demo:screening",
    )
    _route("A. TARGET SCREENING", screening)

    valuation = SuperAgentApplication(build_workflow()).start(
        requests["compare"],
        fixture_state(financials=True),
        thread_id="final-demo:valuation",
    )
    _route("B. VALUATION FAN-OUT / FAN-IN", valuation)
    for item in valuation["final_output"].valuations if valuation.get("final_output") else ():
        print(f"- {item.method}: {item.low} to {item.high} {item.currency} {item.unit}")

    application = SuperAgentApplication(build_workflow(rich_review_services()))
    full = application.start(
        requests["evaluation"],
        fixture_state(financials=False),
        thread_id="final-demo:full",
    )
    _route("C. FULL DEAL EVALUATION", full)
    first_review = True
    while full.get("active_review") is not None:
        review = full["active_review"]
        assert review is not None
        actions = {item.action for item in review.options}
        if first_review and ReviewDecisionAction.RUN_BOTH in actions:
            action = ReviewDecisionAction.RUN_BOTH
            rationale = "Retain reported EBITDA and rerun the approved adjusted scenario."
            first_review = False
        elif ReviewDecisionAction.ACCEPT in actions:
            action = ReviewDecisionAction.ACCEPT
            rationale = "Accept the disclosed risk for current decision support."
        else:
            action = ReviewDecisionAction.CONTINUE_WITH_WARNINGS
            rationale = "Continue while preserving the unresolved warning."
        print(f"REVIEW: {review.title} -> {action.value}")
        full = application.resume(
            thread_id="final-demo:full",
            submission=AnalystReviewSubmission(
                review.review_id,
                action,
                "Demo Analyst",
                rationale,
            ),
        )
    _final(full)
    summary = build_run_summary(full)
    print("\nRUN SUMMARY")
    print(
        f"status={summary.final_status}; calls={summary.metrics.specialist_invocation_count}; "
        f"reviews={summary.metrics.review_count}; reruns={summary.metrics.rerun_count}; "
        f"evidence={summary.metrics.evidence_count}"
    )
    evaluation = FinalEvaluationHarness().evaluate()
    print("\nEVALUATION SUMMARY")
    for metric in evaluation.metrics:
        print(f"- {metric.subsystem}/{metric.metric}: {metric.result:.1%}")


if __name__ == "__main__":
    main()
