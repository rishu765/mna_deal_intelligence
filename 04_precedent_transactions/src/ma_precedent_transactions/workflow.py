"""State contracts for the planned M6/7 LangGraph workflow; no graph executes in M0."""

from __future__ import annotations

from enum import StrEnum
from typing import TypedDict

from ma_precedent_transactions.domain import (
    ComparableSelectionPolicy,
    EvidenceReference,
    TransactionRecord,
)


class WorkflowStatus(StrEnum):
    INITIALIZED = "initialized"
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalystDecision(TypedDict):
    checkpoint: str
    decision: str
    rationale: str


class PrecedentWorkflowState(TypedDict, total=False):
    """Serializable state passed between future orchestration stages."""

    target_context: dict[str, object]
    acquisition_criteria: ComparableSelectionPolicy
    discovered_deal_ids: tuple[str, ...]
    retrieved_document_ids: tuple[str, ...]
    extracted_observation_ids: tuple[str, ...]
    verified_transactions: tuple[TransactionRecord, ...]
    selected_precedent_ids: tuple[str, ...]
    valuation_result_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    analyst_decisions: tuple[AnalystDecision, ...]
    evidence_references: tuple[EvidenceReference, ...]
    retry_counts: dict[str, int]
    status: WorkflowStatus
