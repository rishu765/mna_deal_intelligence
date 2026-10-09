"""Typed state, review, trace, failure, and final-result contracts for M6/7."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, NotRequired

from typing_extensions import TypedDict

from ma_precedent_transactions.discovery import AcquisitionContext
from ma_precedent_transactions.extraction import VerifiedTransactionRecord
from ma_precedent_transactions.pipeline import DealResearchCorpus
from ma_precedent_transactions.precedent import (
    ComparableTransactionSet,
    OverrideAction,
    PrecedentValuationOutput,
    TargetComparabilityProfile,
    TargetValuationProfile,
    TransactionMultipleResult,
)
from ma_precedent_transactions.retrieval import DealRetrievalResult


class WorkflowStatus(StrEnum):
    INITIALIZED = "initialized"
    VALIDATED = "validated"
    RESEARCH_COMPLETE = "research_complete"
    EXTRACTION_COMPLETE = "extraction_complete"
    AWAITING_HUMAN_REVIEW = "awaiting_human_review"
    REVIEW_APPLIED = "review_applied"
    SELECTION_COMPLETE = "selection_complete"
    VALUATION_COMPLETE = "valuation_complete"
    EXPLANATION_COMPLETE = "explanation_complete"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


class FailureCode(StrEnum):
    INVALID_INPUT = "invalid_input"
    NO_DEALS_FOUND = "no_deals_found"
    RETRIEVAL_INSUFFICIENT = "retrieval_insufficient"
    EXTRACTION_FAILED = "extraction_failed"
    VERIFICATION_BLOCKED = "verification_blocked"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    NO_ELIGIBLE_PRECEDENTS = "no_eligible_precedents"
    VALUATION_UNAVAILABLE = "valuation_unavailable"
    EXPLANATION_FAILED = "explanation_failed"
    USER_REJECTED = "user_rejected"


class ReviewPolicy(StrEnum):
    WHEN_NEEDED = "when_needed"
    ALWAYS = "always"
    NEVER = "never"


class ReviewAction(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class HumanReviewInput(TypedDict):
    action: Literal["approve", "reject"]
    reviewer: str
    rationale: str
    resolutions: NotRequired[list[dict[str, str]]]
    overrides: NotRequired[list[dict[str, str]]]


@dataclass(frozen=True, slots=True)
class ObservationResolution:
    transaction_id: str
    field: str
    selected_observation_id: str
    rationale: str

    def __post_init__(self) -> None:
        if any(
            not value.strip()
            for value in (
                self.transaction_id,
                self.field,
                self.selected_observation_id,
                self.rationale,
            )
        ):
            raise ValueError("observation resolution fields must not be blank")


@dataclass(frozen=True, slots=True)
class ReviewOverride:
    transaction_id: str
    action: OverrideAction
    rationale: str

    def __post_init__(self) -> None:
        if not self.transaction_id.strip() or not self.rationale.strip():
            raise ValueError("review override requires transaction ID and rationale")


@dataclass(frozen=True, slots=True)
class HumanReviewDecision:
    action: ReviewAction
    reviewer: str
    rationale: str
    resolutions: tuple[ObservationResolution, ...] = ()
    overrides: tuple[ReviewOverride, ...] = ()
    recorded_at: datetime = datetime.min.replace(tzinfo=UTC)

    def __post_init__(self) -> None:
        if not self.reviewer.strip() or not self.rationale.strip():
            raise ValueError("human review requires reviewer and rationale")
        if self.recorded_at.tzinfo is None:
            raise ValueError("human review timestamp must be timezone-aware")
        ids = [item.transaction_id for item in self.overrides]
        if len(ids) != len(set(ids)):
            raise ValueError("only one override is allowed per transaction")


@dataclass(frozen=True, slots=True)
class ReviewRequest:
    reasons: tuple[str, ...]
    transaction_ids: tuple[str, ...]
    conflict_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorkflowRequest:
    request_id: str
    acquisition_context: AcquisitionContext
    comparable_target: TargetComparabilityProfile
    valuation_target: TargetValuationProfile
    review_policy: ReviewPolicy = ReviewPolicy.WHEN_NEEDED

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id must not be blank")
        if self.acquisition_context.context_id != self.request_id:
            raise ValueError("request and acquisition context IDs must match")
        if self.comparable_target.target_id != self.valuation_target.target_id:
            raise ValueError("comparable and valuation target IDs must match")


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    research: int = 1
    extraction: int = 1

    def __post_init__(self) -> None:
        if self.research < 0 or self.extraction < 0:
            raise ValueError("retry limits must be non-negative")


@dataclass(frozen=True, slots=True)
class WorkflowIssue:
    code: FailureCode
    stage: str
    message: str
    recoverable: bool
    attempt: int


@dataclass(frozen=True, slots=True)
class WorkflowTraceEvent:
    node: str
    status: WorkflowStatus
    message: str
    duration_ms: int
    occurred_at: datetime
    retry_count: int = 0


@dataclass(frozen=True, slots=True)
class TransactionEvidenceBundle:
    transaction_id: str
    results: tuple[DealRetrievalResult, ...]


@dataclass(frozen=True, slots=True)
class RunEvaluationMetadata:
    discovered_count: int
    deduplicated_count: int
    document_count: int
    evidence_count: int
    verified_count: int
    conflict_count: int
    selected_count: int
    valid_multiple_count: int
    valuation_range_count: int
    explanation_available: bool


@dataclass(frozen=True, slots=True)
class PrecedentWorkflowResult:
    request: WorkflowRequest
    status: WorkflowStatus
    failure_code: FailureCode | None
    research: DealResearchCorpus | None
    verified_transactions: tuple[VerifiedTransactionRecord, ...]
    selection: ComparableTransactionSet | None
    multiples: tuple[TransactionMultipleResult, ...]
    valuation: PrecedentValuationOutput | None
    human_review: HumanReviewDecision | None
    evaluation: RunEvaluationMetadata | None
    warnings: tuple[str, ...]
    errors: tuple[WorkflowIssue, ...]
    trace: tuple[WorkflowTraceEvent, ...]


class WorkflowState(TypedDict, total=False):
    request: WorkflowRequest
    research: DealResearchCorpus
    evidence_bundles: tuple[TransactionEvidenceBundle, ...]
    verified_transactions: tuple[VerifiedTransactionRecord, ...]
    valuation_transactions: tuple[VerifiedTransactionRecord, ...]
    review_request: ReviewRequest
    human_review: HumanReviewDecision
    selection: ComparableTransactionSet
    multiples: tuple[TransactionMultipleResult, ...]
    valuation: PrecedentValuationOutput
    evaluation: RunEvaluationMetadata
    final_result: PrecedentWorkflowResult
    status: WorkflowStatus
    failure_code: FailureCode | None
    warnings: tuple[str, ...]
    errors: tuple[WorkflowIssue, ...]
    retry_counts: dict[str, int]
    retry_stage: str | None
    trace: tuple[WorkflowTraceEvent, ...]
