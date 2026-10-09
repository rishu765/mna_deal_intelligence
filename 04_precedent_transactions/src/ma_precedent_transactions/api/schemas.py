"""Typed HTTP request and response envelopes for Project 4 V1."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(StrictModel):
    status: Literal["ok"]
    service: str
    version: str
    mode: Literal["offline_fixture"]


class AcquisitionCriteriaInput(StrictModel):
    announced_from: date | None = None
    announced_to: date | None = None
    transaction_types: list[str] = Field(default_factory=list)
    buyer_types: list[str] = Field(default_factory=list)
    minimum_size: str | None = None
    maximum_size: str | None = None
    size_currency: str | None = Field(default=None, min_length=3, max_length=3)
    keywords: list[str] = Field(default_factory=list)


class TargetMetricInput(StrictModel):
    metric_id: str = Field(min_length=1)
    name: Literal["revenue", "ebitda", "ebit", "net_income"]
    value: str
    currency: str = Field(min_length=3, max_length=3)
    unit: Literal["units", "thousand", "million", "billion", "lakh", "crore"]
    period_kind: Literal["fiscal_year", "calendar_year", "ltm", "point_in_time"]
    period_label: str = Field(min_length=1)
    estimate_status: Literal["historical", "forecast"]
    basis: Literal["reported", "adjusted"]
    measurement_date: date
    period_start: date | None = None
    period_end: date | None = None
    adjustment_label: str | None = None
    evidence_id: str = Field(min_length=1)


class CapitalComponentInput(StrictModel):
    component_id: str = Field(min_length=1)
    kind: Literal["cash", "debt", "preferred_stock", "noncontrolling_interest"]
    value: str
    currency: str = Field(min_length=3, max_length=3)
    unit: Literal["units", "thousand", "million", "billion", "lakh", "crore"]
    as_of: date
    evidence_id: str = Field(min_length=1)


class TargetInput(StrictModel):
    target_id: str = Field(min_length=1)
    industry: str = Field(min_length=1)
    business_description: str = Field(min_length=1)
    products: list[str] = Field(min_length=1)
    customer_types: list[str] = Field(min_length=1)
    geographies: list[str] = Field(min_length=1)
    metrics: list[TargetMetricInput] = Field(default_factory=list)
    capital_components: list[CapitalComponentInput] = Field(default_factory=list)
    diluted_shares: str | None = None
    share_unit: Literal["units", "thousand", "million", "billion", "lakh", "crore"] | None = None
    share_count_date: date | None = None
    share_count_basis: Literal["diluted_end_of_period", "weighted_average"] | None = None
    share_count_evidence_id: str | None = None


class PrecedentRunRequest(StrictModel):
    run_id: str | None = Field(default=None, min_length=1, max_length=100)
    provider_mode: Literal["offline_fixture"] = "offline_fixture"
    review_policy: Literal["when_needed", "always", "never"] = "when_needed"
    target: TargetInput
    acquisition_criteria: AcquisitionCriteriaInput = AcquisitionCriteriaInput()


class ObservationResolutionInput(StrictModel):
    transaction_id: str = Field(min_length=1)
    field: str = Field(min_length=1)
    selected_observation_id: str = Field(min_length=1)
    rationale: str = Field(min_length=1, max_length=2000)


class PrecedentOverrideInput(StrictModel):
    transaction_id: str = Field(min_length=1)
    action: Literal["force_include", "force_exclude"]
    rationale: str = Field(min_length=1, max_length=2000)


class HumanReviewRequest(StrictModel):
    action: Literal["approve", "reject"]
    reviewer: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=1, max_length=2000)
    resolutions: list[ObservationResolutionInput] = Field(default_factory=list)
    overrides: list[PrecedentOverrideInput] = Field(default_factory=list)


class WorkflowResponse(StrictModel):
    run_id: str
    provider_mode: Literal["offline_fixture"]
    status: str
    review_required: bool
    state: dict[str, Any]


class ErrorBody(StrictModel):
    code: str
    message: str


class ErrorResponse(StrictModel):
    error: ErrorBody
