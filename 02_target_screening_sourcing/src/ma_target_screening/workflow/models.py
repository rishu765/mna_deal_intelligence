"""Typed state, review, trace, and final-result models for the M6 workflow."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal, NotRequired

from typing_extensions import TypedDict

from ma_target_screening.discovery.models import CandidateDiscoveryResult
from ma_target_screening.domain import CandidateCompany
from ma_target_screening.profile import CandidateProfile
from ma_target_screening.screening.models import Shortlist
from ma_target_screening.thesis import AcquisitionThesis


class WorkflowStatus(StrEnum):
    INITIALIZED = "initialized"
    VALIDATED = "validated"
    DISCOVERY_COMPLETE = "discovery_complete"
    ENRICHMENT_COMPLETE = "enrichment_complete"
    SCREENING_COMPLETE = "screening_complete"
    AWAITING_HUMAN_REVIEW = "awaiting_human_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


class ReviewDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    RERUN = "rerun"


class HumanReviewInput(TypedDict):
    """JSON-serializable schema validated by LangGraph on resume."""

    decision: Literal["approve", "reject", "rerun"]
    reviewer_notes: NotRequired[str]
    approved_candidates: NotRequired[list[str]]
    rejected_candidates: NotRequired[list[str]]


@dataclass(frozen=True, slots=True)
class HumanReviewDecision:
    decision: ReviewDecision
    reviewer_notes: str | None = None
    approved_candidates: tuple[str, ...] = ()
    rejected_candidates: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        notes = None if self.reviewer_notes is None else " ".join(self.reviewer_notes.split())
        if self.reviewer_notes is not None and not notes:
            raise ValueError("reviewer_notes must not be blank")
        object.__setattr__(self, "reviewer_notes", notes)
        for name in ("approved_candidates", "rejected_candidates"):
            values = tuple(" ".join(item.split()) for item in getattr(self, name))
            if any(not item for item in values):
                raise ValueError(f"{name} must not contain blank identifiers")
            if len({item.casefold() for item in values}) != len(values):
                raise ValueError(f"{name} must not contain duplicates")
            object.__setattr__(self, name, values)
        overlap = {item.casefold() for item in self.approved_candidates} & {
            item.casefold() for item in self.rejected_candidates
        }
        if overlap:
            raise ValueError("approved and rejected candidates must not overlap")

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "reviewer_notes": self.reviewer_notes,
            "approved_candidates": list(self.approved_candidates),
            "rejected_candidates": list(self.rejected_candidates),
        }


@dataclass(frozen=True, slots=True)
class WorkflowIssue:
    stage: str
    message: str
    recoverable: bool
    attempt: int

    def __post_init__(self) -> None:
        if not self.stage.strip() or not self.message.strip():
            raise ValueError("workflow issue stage and message must not be blank")
        if self.attempt < 1:
            raise ValueError("workflow issue attempt must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "message": self.message,
            "recoverable": self.recoverable,
            "attempt": self.attempt,
        }


@dataclass(frozen=True, slots=True)
class WorkflowTraceEvent:
    node: str
    status: WorkflowStatus
    duration_ms: int
    message: str
    occurred_at: str
    retry_count: int = 0

    def __post_init__(self) -> None:
        if not self.node.strip() or not self.message.strip() or not self.occurred_at.strip():
            raise ValueError("workflow trace text must not be blank")
        if self.duration_ms < 0 or self.retry_count < 0:
            raise ValueError("workflow trace durations and retry counts must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "node": self.node,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "message": self.message,
            "occurred_at": self.occurred_at,
            "retry_count": self.retry_count,
        }


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    discovery: int = 1
    enrichment: int = 1
    screening: int = 1
    human_reruns: int = 1

    def __post_init__(self) -> None:
        if any(
            value < 0
            for value in (
                self.discovery,
                self.enrichment,
                self.screening,
                self.human_reruns,
            )
        ):
            raise ValueError("retry limits must be non-negative")


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    thesis: AcquisitionThesis
    final_shortlist: Shortlist
    human_review: HumanReviewDecision | None
    status: WorkflowStatus
    warnings: tuple[str, ...]
    errors: tuple[WorkflowIssue, ...]
    trace: tuple[WorkflowTraceEvent, ...]

    def __post_init__(self) -> None:
        if self.status not in {
            WorkflowStatus.APPROVED,
            WorkflowStatus.REJECTED,
            WorkflowStatus.FAILED,
        }:
            raise ValueError("final workflow result requires a terminal status")

    def to_dict(self) -> dict[str, Any]:
        return {
            "thesis": self.thesis.to_dict(),
            "final_shortlist": self.final_shortlist.to_dict(),
            "human_review": (None if self.human_review is None else self.human_review.to_dict()),
            "status": self.status.value,
            "warnings": list(self.warnings),
            "errors": [item.to_dict() for item in self.errors],
            "trace": [item.to_dict() for item in self.trace],
        }


class WorkflowState(TypedDict, total=False):
    thesis: AcquisitionThesis
    discovery_result: CandidateDiscoveryResult
    candidates: tuple[CandidateCompany, ...]
    profiles: tuple[CandidateProfile, ...]
    provisional_shortlist: Shortlist
    human_review: HumanReviewDecision
    final_result: WorkflowResult
    status: WorkflowStatus
    warnings: tuple[str, ...]
    errors: tuple[WorkflowIssue, ...]
    retry_counts: dict[str, int]
    retry_stage: str | None
    trace: tuple[WorkflowTraceEvent, ...]
