"""FastAPI application factory around existing Project 2 services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from ma_target_screening import __version__
from ma_target_screening.api.schemas import (
    DiscoveryResponse,
    EnrichmentRequest,
    EnrichmentResponse,
    HealthResponse,
    HumanReviewRequest,
    ScreeningRequest,
    ScreeningResponse,
    ThesisRequest,
    ThesisValidationResponse,
    WorkflowIssueResponse,
    WorkflowStartRequest,
    WorkflowStateResponse,
)
from ma_target_screening.composition import OfflinePaths, OfflineServices, build_offline_services
from ma_target_screening.domain import CandidateCompany, DiscoveryEvidence, ExternalIdentifier
from ma_target_screening.errors import TargetScreeningError
from ma_target_screening.profile import CandidateProfile
from ma_target_screening.thesis import AcquisitionThesis
from ma_target_screening.workflow import (
    HumanReviewDecision,
    ReviewDecision,
    WorkflowState,
    WorkflowStatus,
)


@dataclass(slots=True)
class APIRuntime:
    services: OfflineServices
    workflow_ids: set[str] = field(default_factory=set)


def create_app(
    *,
    project_root: Path | None = None,
    services: OfflineServices | None = None,
) -> FastAPI:
    root = (project_root or Path.cwd()).resolve()
    runtime = APIRuntime(services or build_offline_services(OfflinePaths.from_project_root(root)))
    application = FastAPI(
        title="M&A Target Screening & Deal Sourcing Agent",
        version=__version__,
        description="Offline-first V1 API for evidence-backed target sourcing and review.",
    )
    application.state.runtime = runtime
    _install_errors(application)

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="ma-target-screening",
            version=__version__,
            mode="offline_fixture",
        )

    @application.post(
        "/theses/validate",
        response_model=ThesisValidationResponse,
        tags=["thesis"],
    )
    def validate_thesis(request: ThesisRequest) -> ThesisValidationResponse:
        thesis = AcquisitionThesis.from_dict(request.thesis)
        return ThesisValidationResponse(valid=True, thesis=thesis.to_dict())

    @application.post("/discovery", response_model=DiscoveryResponse, tags=["pipeline"])
    def discover(request: ThesisRequest) -> DiscoveryResponse:
        thesis = AcquisitionThesis.from_dict(request.thesis)
        result = runtime.services.discovery.discover(thesis)
        return DiscoveryResponse(result=result.to_dict())

    @application.post("/enrichment", response_model=EnrichmentResponse, tags=["pipeline"])
    def enrich(request: EnrichmentRequest) -> EnrichmentResponse:
        thesis = AcquisitionThesis.from_dict(request.thesis)
        profile = runtime.services.enrichment.enrich(
            _candidate(request.candidate.model_dump()), thesis
        )
        return EnrichmentResponse(profile=profile.to_dict())

    @application.post("/screen", response_model=ScreeningResponse, tags=["pipeline"])
    def screen(request: ScreeningRequest) -> ScreeningResponse:
        thesis = AcquisitionThesis.from_dict(request.thesis)
        profiles = tuple(CandidateProfile.from_dict(item) for item in request.profiles)
        shortlist = runtime.services.screening.build_shortlist(
            thesis,
            profiles,
            top_n=request.top_n,
            include_review_required=request.include_review_required,
        )
        return ScreeningResponse(shortlist=shortlist.to_dict())

    @application.post(
        "/workflow/start",
        response_model=WorkflowStateResponse,
        tags=["workflow"],
    )
    def start_workflow(request: WorkflowStartRequest) -> WorkflowStateResponse:
        thesis = AcquisitionThesis.from_dict(request.thesis)
        workflow_id = request.workflow_id or uuid4().hex
        if workflow_id in runtime.workflow_ids:
            raise HTTPException(status_code=409, detail="workflow_id already exists")
        state = runtime.services.workflow.start(thesis, thread_id=workflow_id)
        runtime.workflow_ids.add(workflow_id)
        return _state_response(workflow_id, state)

    @application.get(
        "/workflow/{workflow_id}",
        response_model=WorkflowStateResponse,
        tags=["workflow"],
    )
    def get_workflow(workflow_id: str) -> WorkflowStateResponse:
        _known_workflow(runtime, workflow_id)
        return _state_response(workflow_id, runtime.services.workflow.state(thread_id=workflow_id))

    @application.post(
        "/workflow/{workflow_id}/review",
        response_model=WorkflowStateResponse,
        tags=["workflow"],
    )
    def review_workflow(workflow_id: str, request: HumanReviewRequest) -> WorkflowStateResponse:
        _known_workflow(runtime, workflow_id)
        current = runtime.services.workflow.state(thread_id=workflow_id)
        if current.get("status") is not WorkflowStatus.AWAITING_HUMAN_REVIEW:
            raise HTTPException(status_code=409, detail="workflow is not awaiting human review")
        decision = HumanReviewDecision(
            decision=ReviewDecision(request.decision),
            reviewer_notes=request.reviewer_notes,
            approved_candidates=tuple(request.approved_candidates),
            rejected_candidates=tuple(request.rejected_candidates),
        )
        resumed = runtime.services.workflow.resume(thread_id=workflow_id, decision=decision)
        return _state_response(workflow_id, resumed)

    return application


def _install_errors(app: FastAPI) -> None:
    @app.exception_handler(ValueError)
    async def invalid_value(_: Request, error: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"error": {"code": "invalid_request", "message": str(error)}},
        )

    @app.exception_handler(TargetScreeningError)
    async def provider_failure(_: Request, error: TargetScreeningError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": {"code": "provider_failure", "message": str(error)}},
        )


def _known_workflow(runtime: APIRuntime, workflow_id: str) -> None:
    if workflow_id not in runtime.workflow_ids:
        raise HTTPException(status_code=404, detail="workflow not found")


def _candidate(data: dict[str, Any]) -> CandidateCompany:
    evidence = tuple(_discovery_evidence(item) for item in data["discovery_evidence"])
    identifiers = tuple(
        ExternalIdentifier(item["scheme"], item["value"]) for item in data["identifiers"]
    )
    return CandidateCompany(
        canonical_name=data["canonical_name"],
        aliases=tuple(data["aliases"]),
        website_domain=data["website_domain"],
        country=data["country"],
        industry_tags=tuple(data["industry_tags"]),
        description=data["description"],
        identifiers=identifiers,
        discovery_evidence=evidence,
    )


def _discovery_evidence(data: dict[str, Any]) -> DiscoveryEvidence:
    observed = data.get("observed_at")
    raw_metadata = data.get("raw_metadata", [])
    return DiscoveryEvidence(
        source_type=data["source_type"],
        source_name=data["source_name"],
        provider_name=data["provider_name"],
        source_uri=data.get("source_uri"),
        source_title=data.get("source_title"),
        source_identifier=data.get("source_identifier"),
        discovery_query=data.get("discovery_query"),
        observed_at=None if observed is None else datetime.fromisoformat(observed),
        excerpt=data.get("excerpt"),
        raw_metadata=tuple((str(pair[0]), str(pair[1])) for pair in raw_metadata),
    )


def _state_response(workflow_id: str, state: WorkflowState) -> WorkflowStateResponse:
    current_status = state.get("status", WorkflowStatus.FAILED)
    provisional = state.get("provisional_shortlist")
    final = state.get("final_result")
    return WorkflowStateResponse(
        workflow_id=workflow_id,
        status=current_status.value,
        review_required=current_status is WorkflowStatus.AWAITING_HUMAN_REVIEW,
        candidate_count=len(state.get("candidates", ())),
        profile_count=len(state.get("profiles", ())),
        provisional_shortlist=None if provisional is None else provisional.to_dict(),
        final_result=None if final is None else final.to_dict(),
        warnings=list(state.get("warnings", ())),
        errors=[WorkflowIssueResponse(**item.to_dict()) for item in state.get("errors", ())],
        trace=[item.to_dict() for item in state.get("trace", ())],
    )


app = create_app()
