"""Run the deterministic M1/2 routing demo without network or model calls."""

from __future__ import annotations

from ma_deal_intelligence.intent import IntentClassifier
from ma_deal_intelligence.planning import ExecutionPlanner
from ma_deal_intelligence.planning_fixtures import fixture_requests, fixture_state
from ma_deal_intelligence.registry import default_registry
from ma_deal_intelligence.runner import SequentialPlanRunner


def main() -> None:
    registry = default_registry()
    classifier = IntentClassifier()
    planner = ExecutionPlanner(registry)
    runner = SequentialPlanRunner(registry)
    for name, with_target, with_financials in (
        ("find_targets", False, False),
        ("compare", True, True),
        ("evaluation", True, False),
    ):
        request = fixture_requests()[name]
        state = fixture_state(target=with_target, financials=with_financials)
        classification = classifier.classify(request)
        plan = planner.build(request, classification, state)
        result = runner.run(plan, state)
        print(f"\n{name}: {request.user_query}")
        print("intents:", ", ".join(item.value for item in classification.intents))
        for stage in plan.stages:
            capabilities = [
                next(step.capability_id for step in plan.steps if step.step_id == step_id)
                for step_id in stage.step_ids
            ]
            print(f"stage {stage.stage_number}:", ", ".join(capabilities))
        print("completed:", ", ".join(result.state.completed_capabilities))
        print("trace events:", len(result.trace))


if __name__ == "__main__":
    main()
