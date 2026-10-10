"""Small sequential runner for validating M1/2 plans without LangGraph."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from ma_deal_intelligence.contracts import (
    CapabilityId,
    DiligenceRequest,
    DocumentIntelligenceRequest,
    PrecedentTransactionsRequest,
    TargetScreeningRequest,
    TradingCompsRequest,
)
from ma_deal_intelligence.evidence import ProjectId
from ma_deal_intelligence.ingestion import ingest_result
from ma_deal_intelligence.planning import ExecutionPlan, PlanStepStatus
from ma_deal_intelligence.registry import CapabilityRegistry
from ma_deal_intelligence.state import DealState
from ma_deal_intelligence.workflow import DealError, WorkflowStatus


class TraceEventType(StrEnum):
    SELECTED = "selected"
    INVOKED = "invoked"
    SUCCEEDED = "succeeded"
    WARNING = "warning"
    FAILED = "failed"
    SKIPPED = "skipped"
    INGESTED = "ingested"


@dataclass(frozen=True, slots=True)
class ExecutionTraceEvent:
    event_type: TraceEventType
    capability_id: str
    timestamp: datetime
    message: str
    run_id: str | None = None


@dataclass(frozen=True, slots=True)
class RunnerResult:
    state: DealState
    trace: tuple[ExecutionTraceEvent, ...]


class SequentialPlanRunner:
    def __init__(self, registry: CapabilityRegistry) -> None:
        self.registry = registry

    def run(self, plan: ExecutionPlan, state: DealState) -> RunnerResult:
        current = replace(state, workflow_status=WorkflowStatus.RUNNING)
        trace: list[ExecutionTraceEvent] = []
        failures: set[str] = set()
        steps_by_id = {step.step_id: step for step in plan.steps}
        for stage in plan.stages:
            for step_id in stage.step_ids:
                step = steps_by_id[step_id]
                trace.append(_event(TraceEventType.SELECTED, step.capability_id, step.rationale))
                if step.status is PlanStepStatus.BLOCKED:
                    trace.append(
                        _event(
                            TraceEventType.SKIPPED,
                            step.capability_id,
                            f"Missing inputs: {', '.join(step.missing_inputs)}",
                        )
                    )
                    continue
                if any(dependency in failures for dependency in step.depends_on):
                    trace.append(
                        _event(
                            TraceEventType.SKIPPED,
                            step.capability_id,
                            "A required capability failed.",
                        )
                    )
                    continue
                try:
                    specialist_request = _request_for(step.capability_id, plan, current)
                    trace.append(
                        _event(TraceEventType.INVOKED, step.capability_id, "Adapter invoked.")
                    )
                    result = self.registry.adapter(step.capability_id).invoke(
                        step.capability_id, specialist_request
                    )
                    current = ingest_result(current, result)
                    trace.append(
                        _event(
                            TraceEventType.SUCCEEDED,
                            step.capability_id,
                            "Specialist completed.",
                            result.run_id,
                        )
                    )
                    for warning in result.warnings:
                        trace.append(
                            _event(
                                TraceEventType.WARNING,
                                step.capability_id,
                                warning.message,
                                result.run_id,
                            )
                        )
                    trace.append(
                        _event(
                            TraceEventType.INGESTED,
                            step.capability_id,
                            "Result ingested into canonical DealState.",
                            result.run_id,
                        )
                    )
                except Exception as exc:  # isolate each external boundary
                    failures.add(step.capability_id)
                    error = DealError(
                        f"error:{plan.plan_id}:{step.capability_id}",
                        "ADAPTER_INVOCATION_FAILED",
                        ProjectId(step.project_id),
                        step.capability_id,
                        True,
                        False,
                        str(exc),
                        "capability_executions",
                        (("exception_type", type(exc).__name__),),
                    )
                    current = replace(
                        current,
                        errors=current.errors + (error,),
                        revision=current.revision + 1,
                        updated_at=datetime.now(UTC),
                    )
                    trace.append(_event(TraceEventType.FAILED, step.capability_id, str(exc)))
        status = WorkflowStatus.PARTIALLY_COMPLETED if failures else WorkflowStatus.COMPLETED
        if current.warnings and not failures:
            status = WorkflowStatus.COMPLETED_WITH_WARNINGS
        return RunnerResult(replace(current, workflow_status=status), tuple(trace))


def _request_for(capability_id: str, plan: ExecutionPlan, state: DealState) -> Any:
    normalized = plan.request
    context = replace(
        state.deal_context,
        target_entity_id=normalized.target_entity_id or state.deal_context.target_entity_id,
        buyer_entity_id=normalized.buyer_entity_id or state.deal_context.buyer_entity_id,
        sectors=normalized.sectors or state.deal_context.sectors,
        geographies=normalized.geographies or state.deal_context.geographies,
    )
    target_id = context.target_entity_id or ""
    if not target_id and state.target_screening_results:
        candidates = state.target_screening_results[-1].payload.candidates
        if candidates:
            target_id = candidates[0].entity.canonical_entity_id
            context = replace(context, target_entity_id=target_id)
    execution_id = f"{plan.plan_id}:{capability_id}:v1"
    documents = tuple(item.document_id for item in state.source_documents)
    if capability_id == CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE:
        return DocumentIntelligenceRequest(
            context, target_id, documents, normalized.query, execution_id
        )
    if capability_id in {CapabilityId.P2_SOURCE_TARGETS, CapabilityId.P2_SCREEN_TARGETS}:
        return TargetScreeningRequest(context, f"criteria:{normalized.request_id}", execution_id)
    if capability_id == CapabilityId.P3_PRODUCE_VALUATION_RANGE:
        profile_id = (
            state.company_intelligence[-1].payload.research_profile_id
            if state.company_intelligence
            else "canonical:financial-profile"
        )
        return TradingCompsRequest(context, target_id, profile_id or "", execution_id)
    if capability_id == CapabilityId.P4_PRODUCE_VALUATION_RANGE:
        return PrecedentTransactionsRequest(
            context, target_id, f"precedent-criteria:{normalized.request_id}", execution_id
        )
    if capability_id == CapabilityId.P5_PRODUCE_DILIGENCE_FINDINGS:
        return DiligenceRequest(
            context,
            target_id,
            documents,
            normalized.requested_workstreams,
            execution_id,
        )
    raise ValueError(f"unsupported runner capability: {capability_id}")


def _event(
    event_type: TraceEventType,
    capability_id: str,
    message: str,
    run_id: str | None = None,
) -> ExecutionTraceEvent:
    return ExecutionTraceEvent(event_type, capability_id, datetime.now(UTC), message, run_id)
