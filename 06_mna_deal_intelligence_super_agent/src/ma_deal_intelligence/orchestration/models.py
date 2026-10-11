"""Typed state and audit contracts for the Project 6 LangGraph runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from typing_extensions import TypedDict

from ma_deal_intelligence.intent import IntentClassification
from ma_deal_intelligence.outputs import ProjectResultEnvelope
from ma_deal_intelligence.planning import ClarificationRequirement, ExecutionPlan
from ma_deal_intelligence.reconciliation_models import ReconciliationResult
from ma_deal_intelligence.requests import UserDealRequest
from ma_deal_intelligence.state import DealState
from ma_deal_intelligence.workflow import DealError, ExecutionStatus


class OrchestrationStatus(StrEnum):
    CREATED = "created"
    VALIDATING = "validating"
    CLASSIFYING = "classifying"
    PLANNING = "planning"
    READY = "ready"
    RUNNING = "running"
    RECONCILING = "reconciling"
    REVIEW_REQUIRED = "review_required"
    WAITING_FOR_INPUT = "waiting_for_input"
    PARTIALLY_COMPLETED = "partially_completed"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FailureKind(StrEnum):
    RETRYABLE = "retryable"
    NONBLOCKING = "nonblocking"
    BLOCKING = "blocking"
    HUMAN_RESOLVABLE = "human_resolvable"


class TraceEventType(StrEnum):
    NODE_ENTERED = "node_entered"
    REQUEST_VALIDATED = "request_validated"
    INTENT_CLASSIFIED = "intent_classified"
    PLAN_BUILT = "plan_built"
    PLAN_VALIDATED = "plan_validated"
    CAPABILITY_SELECTED = "capability_selected"
    CAPABILITY_SKIPPED = "capability_skipped"
    ADAPTER_INVOKED = "adapter_invoked"
    ADAPTER_SUCCEEDED = "adapter_succeeded"
    ADAPTER_FAILED = "adapter_failed"
    RETRY_SCHEDULED = "retry_scheduled"
    RESULT_INGESTED = "result_ingested"
    RECONCILED = "reconciled"
    REVIEW_INTERRUPTED = "review_interrupted"
    REVIEW_RESUMED = "review_resumed"
    RERUN_SCHEDULED = "rerun_scheduled"
    TERMINATED = "terminated"


class ReviewDecisionAction(StrEnum):
    KEEP_REPORTED = "keep_reported"
    RUN_ADJUSTED = "run_adjusted"
    RUN_BOTH = "run_both"
    ACCEPT = "accept"
    REJECT = "reject"
    DEFER = "defer"
    CONTINUE_WITH_WARNINGS = "continue_with_warnings"
    SKIP_CAPABILITY = "skip_capability"
    CANCEL = "cancel"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 2

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least one")


@dataclass(frozen=True, slots=True)
class OrchestrationPolicy:
    retry: RetryPolicy = RetryPolicy()
    max_review_iterations: int = 4
    require_review_for_material_rerun: bool = True

    def __post_init__(self) -> None:
        if self.max_review_iterations < 1:
            raise ValueError("max_review_iterations must be at least one")


@dataclass(frozen=True, slots=True)
class CapabilityTransition:
    status: ExecutionStatus
    occurred_at: datetime
    reason: str
    attempt: int = 0


@dataclass(frozen=True, slots=True)
class CapabilityRuntimeState:
    capability_id: str
    status: ExecutionStatus
    transitions: tuple[CapabilityTransition, ...]
    attempts: int = 0
    result_run_ids: tuple[str, ...] = ()
    last_error_id: str | None = None


@dataclass(frozen=True, slots=True)
class SpecialistAttemptResult:
    attempt_id: str
    capability_id: str
    attempt: int
    rerun_iteration: int
    started_at: datetime
    finished_at: datetime
    envelope: ProjectResultEnvelope[Any] | None = None
    error: DealError | None = None
    failure_kind: FailureKind | None = None

    @property
    def succeeded(self) -> bool:
        return self.envelope is not None and self.error is None


@dataclass(frozen=True, slots=True)
class GraphTraceEvent:
    event_id: str
    run_id: str
    node: str
    event_type: TraceEventType
    status: OrchestrationStatus
    occurred_at: datetime
    message: str
    capability_id: str | None = None
    result_id: str | None = None
    retry_count: int = 0
    branch: str | None = None
    duration_ms: int | None = None


@dataclass(frozen=True, slots=True)
class ReviewOption:
    action: ReviewDecisionAction
    label: str
    resulting_action: str


@dataclass(frozen=True, slots=True)
class AnalystReviewRequest:
    review_id: str
    run_id: str
    issue_ids: tuple[str, ...]
    subject_id: str
    title: str
    summary: str
    conflicting_values: tuple[str, ...]
    affected_output_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    options: tuple[ReviewOption, ...]
    requested_at: datetime


@dataclass(frozen=True, slots=True)
class AnalystReviewSubmission:
    review_id: str
    action: ReviewDecisionAction
    reviewer: str
    rationale: str
    selected_metric_id: str | None = None


class HumanReviewInput(TypedDict):
    review_id: str
    action: str
    reviewer: str
    rationale: str
    selected_metric_id: str | None


@dataclass(frozen=True, slots=True)
class ReviewAuditEvent:
    audit_id: str
    review_id: str
    issue_ids: tuple[str, ...]
    run_id: str
    previous_status: OrchestrationStatus
    available_actions: tuple[ReviewDecisionAction, ...]
    selected_action: ReviewDecisionAction
    rationale: str
    reviewer: str
    decided_at: datetime
    resulting_action: str


@dataclass(frozen=True, slots=True)
class ClarificationState:
    requirements: tuple[ClarificationRequirement, ...]
    affected_capability_ids: tuple[str, ...]
    reason: str
    suggested_actions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OrchestrationTerminalResult:
    run_id: str
    status: OrchestrationStatus
    deal_state: DealState
    reconciliation: ReconciliationResult | None
    completed_capabilities: tuple[str, ...]
    failed_capabilities: tuple[str, ...]
    skipped_capabilities: tuple[str, ...]
    warning_count: int
    error_count: int
    ready_for_synthesis: bool
    message: str


def _merge_attempts(
    left: tuple[SpecialistAttemptResult, ...], right: tuple[SpecialistAttemptResult, ...]
) -> tuple[SpecialistAttemptResult, ...]:
    merged = {item.attempt_id: item for item in left}
    merged.update({item.attempt_id: item for item in right})
    return tuple(merged.values())


def _merge_trace(
    left: tuple[GraphTraceEvent, ...], right: tuple[GraphTraceEvent, ...]
) -> tuple[GraphTraceEvent, ...]:
    merged = {item.event_id: item for item in left}
    merged.update({item.event_id: item for item in right})
    return tuple(merged.values())


def _merge_capability_states(
    left: dict[str, CapabilityRuntimeState], right: dict[str, CapabilityRuntimeState]
) -> dict[str, CapabilityRuntimeState]:
    merged = dict(left)
    merged.update(right)
    return merged


def _merge_strings(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*left, *right)))


class GraphState(TypedDict, total=False):
    run_id: str
    thread_id: str
    request: UserDealRequest
    deal_state: DealState
    status: OrchestrationStatus
    classification: IntentClassification
    execution_plan: ExecutionPlan
    stage_index: int
    active_stage_capabilities: tuple[str, ...]
    execution_complete: bool
    capability_states: Annotated[dict[str, CapabilityRuntimeState], _merge_capability_states]
    specialist_attempts: Annotated[tuple[SpecialistAttemptResult, ...], _merge_attempts]
    processed_attempt_ids: Annotated[tuple[str, ...], _merge_strings]
    pending_retry_capabilities: tuple[str, ...]
    retry_counts: dict[str, int]
    rerun_iteration: int
    rerun_capabilities: tuple[str, ...]
    reconciliation: ReconciliationResult
    active_review: AnalystReviewRequest | None
    review_history: tuple[ReviewAuditEvent, ...]
    reviewed_subject_ids: tuple[str, ...]
    review_iteration: int
    clarification: ClarificationState | None
    errors: tuple[DealError, ...]
    warnings: tuple[str, ...]
    trace: Annotated[tuple[GraphTraceEvent, ...], _merge_trace]
    invocation_log: Annotated[tuple[str, ...], _merge_strings]
    terminal_result: OrchestrationTerminalResult
    worker_capability_id: str
    worker_attempt: int
    worker_rerun_iteration: int


@dataclass(frozen=True, slots=True)
class GraphEvaluationCase:
    case_id: str
    request: UserDealRequest
    initial_state: DealState
    expected_capabilities: tuple[str, ...]
    expected_terminal_statuses: tuple[OrchestrationStatus, ...]


@dataclass(frozen=True, slots=True)
class GraphEvaluationResult:
    case_id: str
    passed: bool
    invoked_capabilities: tuple[str, ...]
    unnecessary_capabilities: tuple[str, ...]
    missing_capabilities: tuple[str, ...]
    terminal_status: OrchestrationStatus
    routing_correct: bool
    dependency_order_correct: bool
    branch_correct: bool
    review_triggered: bool
    resume_completed: bool
    partial_failure_survived: bool
    unnecessary_call_rate: float
