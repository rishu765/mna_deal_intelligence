"""Minimal FastAPI application over the complete offline valuation workflow."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from ma_comparable_valuation import __version__
from ma_comparable_valuation.api.schemas import (
    HealthResponse,
    TargetProfileRequest,
    TargetProfileResponse,
    ValuationRunRequest,
    ValuationRunResponse,
)
from ma_comparable_valuation.domain import TargetFinancialProfile
from ma_comparable_valuation.errors import NoMeaningfulValuationError
from ma_comparable_valuation.presentation import workflow_to_dict
from ma_comparable_valuation.valuation import MultipleRequest
from ma_comparable_valuation.valuation_fixtures import demo_multiple_requests
from ma_comparable_valuation.workflow import OfflineValuationService

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class APIRuntime:
    service: OfflineValuationService
    results: dict[str, dict[str, Any]] = field(default_factory=dict)


def create_app(*, service: OfflineValuationService | None = None) -> FastAPI:
    runtime = APIRuntime(service or OfflineValuationService())
    application = FastAPI(
        title="Comparable Companies & Valuation Copilot",
        version=__version__,
        description=(
            "Offline-first V1 API for evidence-backed public-company trading comps valuation."
        ),
        debug=False,
    )
    application.state.runtime = runtime
    _install_errors(application)

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="ma-comparable-valuation",
            version=__version__,
            mode="offline_fixture",
        )

    @application.post(
        "/target/profile",
        response_model=TargetProfileResponse,
        tags=["valuation"],
    )
    def validate_profile(request: TargetProfileRequest) -> TargetProfileResponse:
        profile = TargetFinancialProfile.from_dict(request.profile)
        return TargetProfileResponse(profile=profile.to_dict())

    @application.post(
        "/valuation/run",
        response_model=ValuationRunResponse,
        tags=["valuation"],
    )
    def run_valuation(request: ValuationRunRequest) -> ValuationRunResponse:
        profile = (
            None
            if request.target_profile is None
            else TargetFinancialProfile.from_dict(request.target_profile)
        )
        result = runtime.service.run(
            target_profile=profile,
            requests=_requests(request.methods),
            include_explanation=request.include_explanation,
        )
        valuation_id = uuid4().hex
        payload = workflow_to_dict(result)
        runtime.results[valuation_id] = payload
        return ValuationRunResponse(
            valuation_id=valuation_id,
            provider_mode=request.provider_mode,
            result=payload,
        )

    @application.get(
        "/valuation/{valuation_id}",
        response_model=ValuationRunResponse,
        tags=["valuation"],
    )
    def get_valuation(valuation_id: str) -> ValuationRunResponse:
        payload = runtime.results.get(valuation_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="valuation not found")
        return ValuationRunResponse(
            valuation_id=valuation_id,
            provider_mode="offline_fixture",
            result=payload,
        )

    return application


def _requests(labels: list[str] | None) -> tuple[MultipleRequest, ...] | None:
    if labels is None:
        return None
    available = {item.label: item for item in demo_multiple_requests()}
    unknown = sorted(set(labels) - set(available))
    if unknown:
        raise ValueError("unsupported valuation method labels: " + ", ".join(unknown))
    if len(set(labels)) != len(labels):
        raise ValueError("valuation method labels must not contain duplicates")
    return tuple(available[label] for label in labels)


def _install_errors(app: FastAPI) -> None:
    @app.exception_handler(NoMeaningfulValuationError)
    async def no_valuation(_: Request, error: NoMeaningfulValuationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"error": {"code": "no_meaningful_valuation", "message": str(error)}},
        )

    @app.exception_handler(ValueError)
    async def invalid_value(_: Request, error: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"error": {"code": "invalid_request", "message": str(error)}},
        )

    @app.exception_handler(Exception)
    async def unexpected(_: Request, error: Exception) -> JSONResponse:
        LOGGER.exception("Unhandled valuation API error", exc_info=error)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "The valuation request could not be completed.",
                }
            },
        )


app = create_app()
