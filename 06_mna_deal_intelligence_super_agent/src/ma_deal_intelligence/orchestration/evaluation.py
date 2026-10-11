"""Small deterministic M4/5 graph behavior evaluation harness."""

from __future__ import annotations

from ma_deal_intelligence.orchestration.graph import SuperAgentApplication, build_workflow
from ma_deal_intelligence.orchestration.models import (
    AnalystReviewSubmission,
    GraphEvaluationCase,
    GraphEvaluationResult,
    OrchestrationStatus,
    ReviewDecisionAction,
    TraceEventType,
)


class GraphEvaluationHarness:
    def evaluate(self, case: GraphEvaluationCase) -> GraphEvaluationResult:
        application = SuperAgentApplication(build_workflow())
        thread_id = f"evaluation:{case.case_id}"
        state = application.start(
            case.request,
            case.initial_state,
            thread_id=thread_id,
            run_id=f"run:evaluation:{case.case_id}",
        )
        review_triggered = state.get("active_review") is not None
        resumed = False
        while state.get("active_review") is not None:
            review = state["active_review"]
            assert review is not None
            actions = {item.action for item in review.options}
            action = (
                ReviewDecisionAction.CONTINUE_WITH_WARNINGS
                if ReviewDecisionAction.CONTINUE_WITH_WARNINGS in actions
                else ReviewDecisionAction.ACCEPT
                if ReviewDecisionAction.ACCEPT in actions
                else ReviewDecisionAction.DEFER
            )
            state = application.resume(
                thread_id=thread_id,
                submission=AnalystReviewSubmission(
                    review.review_id,
                    action,
                    "evaluation-harness",
                    "Deterministic evaluation disposition.",
                ),
            )
            resumed = True
        trace = state.get("trace", ())
        invocations = tuple(
            item.capability_id
            for item in trace
            if item.event_type is TraceEventType.ADAPTER_INVOKED and item.capability_id is not None
        )
        expected = set(case.expected_capabilities)
        invoked = set(invocations)
        unnecessary = tuple(sorted(invoked - expected))
        missing = tuple(sorted(expected - invoked))
        rate = len(unnecessary) / len(invocations) if invocations else 0.0
        order = {capability: index for index, capability in enumerate(invocations)}
        plan = state.get("execution_plan")
        dependency_order_correct = True
        if plan is not None:
            for step in plan.steps:
                for dependency in step.depends_on:
                    if dependency in order and step.capability_id in order:
                        dependency_order_correct &= order[dependency] < order[step.capability_id]
        terminal = state["status"]
        routing_correct = not unnecessary and not missing
        branch_correct = terminal in case.expected_terminal_statuses
        partial_survived = not state.get("errors") or terminal in {
            OrchestrationStatus.COMPLETED_WITH_WARNINGS,
            OrchestrationStatus.PARTIALLY_COMPLETED,
        }
        return GraphEvaluationResult(
            case.case_id,
            routing_correct and dependency_order_correct and branch_correct,
            tuple(dict.fromkeys(invocations)),
            unnecessary,
            missing,
            terminal,
            routing_correct,
            dependency_order_correct,
            branch_correct,
            review_triggered,
            resumed and state.get("active_review") is None,
            partial_survived,
            rate,
        )
