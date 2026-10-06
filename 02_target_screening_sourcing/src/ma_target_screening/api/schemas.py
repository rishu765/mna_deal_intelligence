"""Typed HTTP request and response schemas for the Project 2 V1 API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(StrictModel):
    status: Literal["ok"]
    service: str
    version: str
    mode: Literal["offline_fixture"]


class ThesisRequest(StrictModel):
    thesis: dict[str, Any]


class ThesisValidationResponse(StrictModel):
    valid: Literal[True]
    thesis: dict[str, Any]


class DiscoveryResponse(StrictModel):
    result: dict[str, Any]


class CandidateInput(StrictModel):
    canonical_name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    website_domain: str | None = None
    country: str | None = None
    industry_tags: list[str] = Field(default_factory=list)
    description: str | None = None
    identifiers: list[dict[str, str]] = Field(default_factory=list)
    discovery_evidence: list[dict[str, Any]] = Field(default_factory=list)


class EnrichmentRequest(ThesisRequest):
    candidate: CandidateInput


class EnrichmentResponse(StrictModel):
    profile: dict[str, Any]


class ScreeningRequest(ThesisRequest):
    profiles: list[dict[str, Any]]
    top_n: int | None = Field(default=None, ge=1)
    include_review_required: bool = True


class ScreeningResponse(StrictModel):
    shortlist: dict[str, Any]


class WorkflowStartRequest(ThesisRequest):
    workflow_id: str | None = Field(default=None, min_length=1, max_length=100)


class HumanReviewRequest(StrictModel):
    decision: Literal["approve", "reject", "rerun"]
    reviewer_notes: str | None = Field(default=None, min_length=1, max_length=2000)
    approved_candidates: list[str] = Field(default_factory=list)
    rejected_candidates: list[str] = Field(default_factory=list)


class WorkflowIssueResponse(StrictModel):
    stage: str
    message: str
    recoverable: bool
    attempt: int


class WorkflowStateResponse(StrictModel):
    workflow_id: str
    status: str
    review_required: bool
    candidate_count: int
    profile_count: int
    provisional_shortlist: dict[str, Any] | None
    final_result: dict[str, Any] | None
    warnings: list[str]
    errors: list[WorkflowIssueResponse]
    trace: list[dict[str, Any]]


class ErrorBody(StrictModel):
    code: str
    message: str


class ErrorResponse(StrictModel):
    error: ErrorBody
