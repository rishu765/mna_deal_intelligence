from __future__ import annotations

from typing import NoReturn

from ma_deal_intelligence.adapters import AdapterMode, Project4Adapter
from ma_deal_intelligence.contracts import CapabilityId, TradingCompsRequest
from ma_deal_intelligence.ingestion import ingest_result
from ma_deal_intelligence.intent import IntentClassifier
from ma_deal_intelligence.planning import ExecutionPlanner
from ma_deal_intelligence.planning_fixtures import TARGET, fixture_requests, fixture_state
from ma_deal_intelligence.registry import default_registry
from ma_deal_intelligence.runner import SequentialPlanRunner, TraceEventType
from ma_deal_intelligence.serialization import state_from_json, state_to_json
from ma_deal_intelligence.workflow import WorkflowStatus


def test_result_ingestion_is_idempotent_and_preserves_rerun_history() -> None:
    state = fixture_state(financials=True)
    adapter = default_registry().adapter(CapabilityId.P3_PRODUCE_VALUATION_RANGE)
    first = adapter.invoke(
        CapabilityId.P3_PRODUCE_VALUATION_RANGE,
        TradingCompsRequest(
            state.deal_context, TARGET.canonical_entity_id, "profile:fixture", "run:first"
        ),
    )
    once = ingest_result(state, first)
    assert ingest_result(once, first) == once
    second = adapter.invoke(
        CapabilityId.P3_PRODUCE_VALUATION_RANGE,
        TradingCompsRequest(
            state.deal_context, TARGET.canonical_entity_id, "profile:fixture", "run:second"
        ),
    )
    twice = ingest_result(once, second)
    assert len(twice.trading_comps_results) == 2
    assert twice.artifact_versions[-2].superseded_by == twice.artifact_versions[-1].artifact_id
    assert twice.evidence
    assert twice.valuation_outputs


def test_sequential_runner_populates_state_and_trace() -> None:
    request = fixture_requests()["evaluation"]
    state = fixture_state(financials=False)
    registry = default_registry()
    plan = ExecutionPlanner(registry).build(request, IntentClassifier().classify(request), state)
    result = SequentialPlanRunner(registry).run(plan, state)
    assert result.state.company_intelligence
    assert result.state.trading_comps_results
    assert result.state.precedent_transaction_results
    assert result.state.diligence_results
    assert result.state.workflow_status in {
        WorkflowStatus.COMPLETED,
        WorkflowStatus.COMPLETED_WITH_WARNINGS,
    }
    assert TraceEventType.INGESTED in {item.event_type for item in result.trace}
    assert state_from_json(state_to_json(result.state)) == result.state


def test_runner_isolates_failure_and_preserves_independent_output() -> None:
    request = fixture_requests()["compare"]
    state = fixture_state(financials=True)
    registry = default_registry()

    def fail(request: object) -> NoReturn:
        del request
        raise RuntimeError("fixture native failure")

    registry._adapters[str(CapabilityId.P4_PRODUCE_VALUATION_RANGE)] = Project4Adapter(  # noqa: SLF001
        mode=AdapterMode.NATIVE, native_executor=fail
    )
    plan = ExecutionPlanner(registry).build(request, IntentClassifier().classify(request), state)
    result = SequentialPlanRunner(registry).run(plan, state)
    assert result.state.trading_comps_results
    assert result.state.errors[-1].code == "ADAPTER_INVOCATION_FAILED"
    assert result.state.workflow_status is WorkflowStatus.PARTIALLY_COMPLETED
    assert TraceEventType.FAILED in {item.event_type for item in result.trace}
