"""Safe, structured observability derived from orchestration state."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from ma_deal_intelligence.orchestration.models import GraphState, TraceEventType
from ma_deal_intelligence.synthesis import DealAssessment
from ma_deal_intelligence.workflow import ExecutionStatus


@dataclass(frozen=True, slots=True)
class NodeTiming:
    node: str
    duration_ms: int


@dataclass(frozen=True, slots=True)
class RunMetrics:
    duration_ms: int
    node_timings: tuple[NodeTiming, ...]
    specialist_invocation_count: int
    specialist_skip_count: int
    retry_count: int
    failure_count: int
    reconciliation_issue_count: int
    review_count: int
    rerun_count: int
    evidence_count: int
    warning_count: int
    error_count: int


@dataclass(frozen=True, slots=True)
class SafeTraceEvent:
    event_id: str
    node: str
    event_type: str
    occurred_at: datetime
    status: str
    capability_id: str | None
    result_id: str | None
    retry_count: int
    branch: str | None
    duration_ms: int | None


@dataclass(frozen=True, slots=True)
class RunSummary:
    run_id: str
    query: str
    selected_capabilities: tuple[str, ...]
    completed_capabilities: tuple[str, ...]
    skipped_capabilities: tuple[str, ...]
    failed_capabilities: tuple[str, ...]
    review_event_ids: tuple[str, ...]
    final_status: str
    final_assessment: DealAssessment | None
    metrics: RunMetrics


def safe_trace(state: GraphState) -> tuple[SafeTraceEvent, ...]:
    """Exclude free-form messages and source content from the public trace."""
    return tuple(
        SafeTraceEvent(
            item.event_id,
            item.node,
            item.event_type.value,
            item.occurred_at,
            item.status.value,
            item.capability_id,
            item.result_id,
            item.retry_count,
            item.branch,
            item.duration_ms,
        )
        for item in state.get("trace", ())
    )


def build_run_summary(state: GraphState) -> RunSummary:
    trace = state.get("trace", ())
    timings: dict[str, int] = defaultdict(int)
    for item in trace:
        timings[item.node] += item.duration_ms or 0
    occurred = [item.occurred_at for item in trace]
    duration_ms = int((max(occurred) - min(occurred)).total_seconds() * 1000) if occurred else 0
    runtimes = state.get("capability_states", {})
    plan = state.get("execution_plan")
    selected = tuple(step.capability_id for step in plan.steps) if plan is not None else ()
    completed = tuple(
        key
        for key, value in runtimes.items()
        if value.status in {ExecutionStatus.COMPLETED, ExecutionStatus.COMPLETED_WITH_WARNINGS}
    )
    skipped = tuple(
        key
        for key, value in runtimes.items()
        if value.status in {ExecutionStatus.SKIPPED, ExecutionStatus.BLOCKED}
    )
    failed = tuple(key for key, value in runtimes.items() if value.status is ExecutionStatus.FAILED)
    reconciliation = state.get("reconciliation")
    final_output = state.get("final_output")
    metrics = RunMetrics(
        duration_ms,
        tuple(NodeTiming(node, value) for node, value in sorted(timings.items())),
        sum(item.event_type is TraceEventType.ADAPTER_INVOKED for item in trace),
        sum(item.event_type is TraceEventType.CAPABILITY_SKIPPED for item in trace),
        sum(item.event_type is TraceEventType.RETRY_SCHEDULED for item in trace),
        sum(item.event_type is TraceEventType.ADAPTER_FAILED for item in trace),
        len(reconciliation.snapshot.issues) if reconciliation else 0,
        len(state.get("review_history", ())),
        state.get("rerun_iteration", 0),
        len(state["deal_state"].evidence),
        len(state.get("warnings", ())) + len(state["deal_state"].warnings),
        len(state.get("errors", ())) + len(state["deal_state"].errors),
    )
    return RunSummary(
        state["run_id"],
        state["request"].user_query,
        selected,
        completed,
        skipped,
        failed,
        tuple(item.review_id for item in state.get("review_history", ())),
        state["status"].value,
        final_output.assessment.classification if final_output else None,
        metrics,
    )
