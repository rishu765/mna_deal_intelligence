"""Workflow, dependency, decision, warning, and error contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from ma_deal_intelligence.evidence import ProjectId


class WorkflowStatus(StrEnum):
    CREATED = "created"
    PLANNING = "planning"
    READY = "ready"
    RUNNING = "running"
    PARTIALLY_COMPLETED = "partially_completed"
    REVIEW_REQUIRED = "review_required"
    WAITING_FOR_INPUT = "waiting_for_input"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"


class ExecutionStatus(StrEnum):
    NOT_STARTED = "not_started"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    BLOCKED = "blocked"
    FAILED = "failed"
    SKIPPED = "skipped"


class ResultStatus(StrEnum):
    SUCCEEDED = "succeeded"
    SUCCEEDED_WITH_WARNINGS = "succeeded_with_warnings"
    PARTIAL = "partial"
    FAILED = "failed"


class IssueSeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class Assumption:
    assumption_id: str
    description: str
    source_project: ProjectId
    category: str
    value: str | None = None
    rationale: str | None = None
    evidence_refs: tuple[str, ...] = ()
    analyst_approved: bool = False
    materiality: str | None = None


@dataclass(frozen=True, slots=True)
class DealWarning:
    warning_id: str
    code: str
    severity: IssueSeverity
    message: str
    source_project: ProjectId
    affected_field: str | None = None
    affected_capability: str | None = None
    evidence_refs: tuple[str, ...] = ()
    blocking: bool = False


@dataclass(frozen=True, slots=True)
class DealError:
    error_id: str
    code: str
    source_project: ProjectId
    capability: str | None
    recoverable: bool
    retryable: bool
    message: str
    affected_state: str | None = None
    safe_details: tuple[tuple[str, str], ...] = ()


class DependencyKind(StrEnum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    ANY_OF = "any_of"


@dataclass(frozen=True, slots=True)
class DependencyRequirement:
    dependency_id: str
    capability_id: str
    kind: DependencyKind
    required_capability_ids: tuple[str, ...] = ()
    required_artifact_ids: tuple[str, ...] = ()
    satisfied: bool = False
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ArtifactVersion:
    artifact_id: str
    schema_version: str
    input_version: str
    produced_from: tuple[str, ...] = ()
    dependency_fingerprint: str | None = None
    stale: bool = False
    stale_reason: str | None = None
    superseded_by: str | None = None

    def __post_init__(self) -> None:
        if self.stale and self.stale_reason is None:
            raise ValueError("stale artifacts require stale_reason")


class DecisionAction(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"
    SELECT = "select"
    INCLUDE = "include"
    EXCLUDE = "exclude"
    OVERRIDE = "override"
    RESOLVE = "resolve"


@dataclass(frozen=True, slots=True)
class AnalystDecision:
    decision_id: str
    subject_type: str
    subject_id: str
    previous_state: str | None
    action: DecisionAction
    rationale: str
    reviewer: str
    decided_at: datetime
    selected_value: str | None = None

    def __post_init__(self) -> None:
        if self.decided_at.tzinfo is None or self.decided_at.utcoffset() is None:
            raise ValueError("decision timestamp must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CapabilityExecution:
    capability_id: str
    source_project: ProjectId
    status: ExecutionStatus = ExecutionStatus.NOT_STARTED
    run_id: str | None = None
    dependency_ids: tuple[str, ...] = ()
    output_artifact_ids: tuple[str, ...] = ()
