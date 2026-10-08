"""Typed request and response envelopes for the Project 3 V1 API."""

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


class TargetProfileRequest(StrictModel):
    profile: dict[str, Any]


class TargetProfileResponse(StrictModel):
    profile: dict[str, Any]


class ValuationRunRequest(StrictModel):
    provider_mode: Literal["offline_fixture"] = "offline_fixture"
    target_profile: dict[str, Any] | None = None
    methods: list[str] | None = Field(default=None, min_length=1)
    include_explanation: bool = True


class ValuationRunResponse(StrictModel):
    valuation_id: str
    provider_mode: Literal["offline_fixture"]
    result: dict[str, Any]


class ErrorBody(StrictModel):
    code: str
    message: str


class ErrorResponse(StrictModel):
    error: ErrorBody
