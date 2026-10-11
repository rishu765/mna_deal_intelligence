"""Typed transport schemas for the local Project 6 API."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ma_deal_intelligence.orchestration.models import ReviewDecisionAction
from ma_deal_intelligence.synthesis import DealAssessment, FinalOutputStatus


class DealContextInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    deal_id: str = Field(min_length=1, max_length=120)
    target_name: str | None = None
    target_id: str | None = None
    buyer_name: str | None = None
    buyer_id: str | None = None
    transaction_thesis: str | None = None
    strategic_rationale: tuple[str, ...] = ()
    geography: tuple[str, ...] = ()
    sector: tuple[str, ...] = ()
    reporting_currency: str | None = Field(default=None, min_length=3, max_length=3)
    as_of_date: date | None = None


class CreateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_query: str = Field(min_length=1, max_length=4000)
    deal_context: DealContextInput
    document_ids: tuple[str, ...] = ()
    requested_methods: tuple[str, ...] = ()
    requested_workstreams: tuple[str, ...] = ()
    mode: Literal["offline"] = "offline"


class ReviewSubmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_id: str
    decision: ReviewDecisionAction
    rationale: str = Field(min_length=1, max_length=2000)
    reviewer: str = Field(min_length=1, max_length=200)
    selected_metric_id: str | None = None


class ReviewItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    review_id: str
    title: str
    summary: str
    issue_ids: tuple[str, ...]
    conflicting_values: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    available_decisions: tuple[ReviewDecisionAction, ...]


class RunStatusResponse(BaseModel):
    run_id: str
    status: str
    selected_capabilities: tuple[str, ...]
    completed_capabilities: tuple[str, ...]
    pending_capabilities: tuple[str, ...]
    failed_capabilities: tuple[str, ...]
    review_required: bool
    active_review: ReviewItemResponse | None
    clarification_needs: tuple[str, ...]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]


class CreateRunResponse(RunStatusResponse):
    created: bool = True


class SynthesisItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    item_id: str
    statement: str
    source_artifact_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    quantified: bool


class FinalSectionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    section_id: str
    title: str
    summary: str
    items: tuple[SynthesisItemSchema, ...]


class ValuationEntrySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    valuation_id: str
    method: str
    low: Decimal
    midpoint: Decimal
    high: Decimal
    currency: str
    unit: str
    metric_basis: str
    source_project: str
    source_record_id: str
    evidence_refs: tuple[str, ...]
    stale_for_scenarios: tuple[str, ...]


class MetricEntrySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    metric_id: str
    metric_type: str
    value: Decimal
    currency: str | None
    unit: str
    basis: str
    source_project: str
    evidence_refs: tuple[str, ...]


class CitationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    evidence_id: str
    label: str
    source_project: str


class AssessmentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    classification: DealAssessment
    policy_reasons: tuple[str, ...]
    unresolved_material_issue_count: int
    high_or_critical_risk_count: int
    missing_specialist_count: int


class FinalOutputSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    synthesis_id: str
    run_id: str
    deal_id: str
    as_of_date: date | None
    status: FinalOutputStatus
    assessment: AssessmentSchema
    executive_summary: str
    sections: tuple[FinalSectionSchema, ...]
    valuations: tuple[ValuationEntrySchema, ...]
    material_metrics: tuple[MetricEntrySchema, ...]
    citations: tuple[CitationSchema, ...]
    evidence_refs: tuple[str, ...]
    assumption_ids: tuple[str, ...]
    warning_ids: tuple[str, ...]
    error_ids: tuple[str, ...]
    lineage_source_ids: tuple[str, ...]
    schema_version: str


class ResultResponse(BaseModel):
    run_id: str
    status: str
    output: FinalOutputSchema


class TraceEventSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
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


class TraceResponse(BaseModel):
    run_id: str
    events: tuple[TraceEventSchema, ...]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    mode: Literal["offline"]
    version: str
