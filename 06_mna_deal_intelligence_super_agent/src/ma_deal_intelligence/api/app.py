"""Minimal local API over the checkpointed Project 6 workflow."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from fastapi import FastAPI, HTTPException, status

from ma_deal_intelligence.api.schemas import (
    CreateRunRequest,
    CreateRunResponse,
    FinalOutputSchema,
    HealthResponse,
    ResultResponse,
    ReviewItemResponse,
    ReviewSubmissionRequest,
    RunStatusResponse,
    TraceEventSchema,
    TraceResponse,
)
from ma_deal_intelligence.evidence import ProjectId
from ma_deal_intelligence.identity import CanonicalEntityReference, DealContext
from ma_deal_intelligence.observability import safe_trace
from ma_deal_intelligence.orchestration import (
    AnalystReviewSubmission,
    SuperAgentApplication,
    build_workflow,
)
from ma_deal_intelligence.orchestration.models import GraphState, OrchestrationStatus
from ma_deal_intelligence.requests import RequestMode, UserDealRequest
from ma_deal_intelligence.state import DealState, SourceDocumentReference


@dataclass(slots=True)
class LocalRunRegistry:
    """Process-local V1 run registry; checkpoint state stays in the graph application."""

    application: SuperAgentApplication
    states: dict[str, GraphState]

    def __init__(self, application: SuperAgentApplication | None = None) -> None:
        self.application = application or SuperAgentApplication(build_workflow())
        self.states = {}

    def start(self, payload: CreateRunRequest) -> tuple[str, GraphState]:
        run_id = f"run:{uuid4().hex}"
        request, state = _domain_request(payload, run_id)
        graph_state = self.application.start(request, state, thread_id=run_id, run_id=run_id)
        self.states[run_id] = graph_state
        return run_id, graph_state

    def resume(self, run_id: str, payload: ReviewSubmissionRequest) -> GraphState:
        state = self.get(run_id)
        if state.get("status") is not OrchestrationStatus.REVIEW_REQUIRED:
            raise RuntimeError("run is not awaiting analyst review")
        active = state.get("active_review")
        if active is None or active.review_id != payload.review_id:
            raise ValueError("review_id does not match the active review")
        submission = AnalystReviewSubmission(
            payload.review_id,
            payload.decision,
            payload.reviewer,
            payload.rationale,
            payload.selected_metric_id,
        )
        updated = self.application.resume(thread_id=run_id, submission=submission)
        self.states[run_id] = updated
        return updated

    def get(self, run_id: str) -> GraphState:
        try:
            return self.states[run_id]
        except KeyError as error:
            raise KeyError("run not found") from error


def create_app(registry: LocalRunRegistry | None = None) -> FastAPI:
    runs = registry or LocalRunRegistry()
    application = FastAPI(
        title="M&A Deal Intelligence Super-Agent",
        version="1.0.0",
        description="Local, offline-first decision-support orchestration across Projects 1–5.",
    )

    @application.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", mode="offline", version="1.0.0")

    @application.post(
        "/deal-intelligence/runs",
        response_model=CreateRunResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_run(payload: CreateRunRequest) -> CreateRunResponse:
        try:
            run_id, state = runs.start(payload)
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return CreateRunResponse(**_status_payload(run_id, state).model_dump(), created=True)

    @application.get("/deal-intelligence/runs/{run_id}", response_model=RunStatusResponse)
    def get_run(run_id: str) -> RunStatusResponse:
        state = _state_or_404(runs, run_id)
        return _status_payload(run_id, state)

    @application.post("/deal-intelligence/runs/{run_id}/review", response_model=RunStatusResponse)
    def review(run_id: str, payload: ReviewSubmissionRequest) -> RunStatusResponse:
        return _resume(runs, run_id, payload)

    @application.post("/deal-intelligence/runs/{run_id}/resume", response_model=RunStatusResponse)
    def resume(run_id: str, payload: ReviewSubmissionRequest) -> RunStatusResponse:
        return _resume(runs, run_id, payload)

    @application.get("/deal-intelligence/runs/{run_id}/result", response_model=ResultResponse)
    def result(run_id: str) -> ResultResponse:
        state = _state_or_404(runs, run_id)
        output = state.get("final_output")
        if output is None:
            raise HTTPException(status_code=409, detail="final result is not ready")
        return ResultResponse(
            run_id=run_id,
            status=state["status"].value,
            output=FinalOutputSchema.model_validate(output),
        )

    @application.get("/deal-intelligence/runs/{run_id}/trace", response_model=TraceResponse)
    def trace(run_id: str) -> TraceResponse:
        state = _state_or_404(runs, run_id)
        return TraceResponse(
            run_id=run_id,
            events=tuple(TraceEventSchema.model_validate(item) for item in safe_trace(state)),
        )

    return application


def _resume(
    runs: LocalRunRegistry, run_id: str, payload: ReviewSubmissionRequest
) -> RunStatusResponse:
    _state_or_404(runs, run_id)
    try:
        state = runs.resume(run_id, payload)
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return _status_payload(run_id, state)


def _state_or_404(runs: LocalRunRegistry, run_id: str) -> GraphState:
    try:
        return runs.get(run_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="run not found") from error


def _status_payload(run_id: str, state: GraphState) -> RunStatusResponse:
    plan = state.get("execution_plan")
    selected = tuple(step.capability_id for step in plan.steps) if plan else ()
    completed = tuple(
        capability
        for capability in selected
        if state.get("capability_states", {}).get(capability)
        and state["capability_states"][capability].status.value.startswith("completed")
    )
    failed = tuple(
        capability
        for capability in selected
        if state.get("capability_states", {}).get(capability)
        and state["capability_states"][capability].status.value == "failed"
    )
    pending = tuple(item for item in selected if item not in completed and item not in failed)
    active = state.get("active_review")
    review = None
    if active is not None:
        review = ReviewItemResponse(
            review_id=active.review_id,
            title=active.title,
            summary=active.summary,
            issue_ids=active.issue_ids,
            conflicting_values=active.conflicting_values,
            evidence_refs=active.evidence_refs,
            available_decisions=tuple(item.action for item in active.options),
        )
    clarification = state.get("clarification")
    return RunStatusResponse(
        run_id=run_id,
        status=state["status"].value,
        selected_capabilities=selected,
        completed_capabilities=completed,
        pending_capabilities=pending,
        failed_capabilities=failed,
        review_required=active is not None,
        active_review=review,
        clarification_needs=(
            tuple(item.reason for item in clarification.requirements) if clarification else ()
        ),
        warnings=tuple(state.get("warnings", ()))
        + tuple(item.message for item in state["deal_state"].warnings),
        errors=tuple(item.message for item in state.get("errors", ()))
        + tuple(item.message for item in state["deal_state"].errors),
    )


def _domain_request(payload: CreateRunRequest, run_id: str) -> tuple[UserDealRequest, DealState]:
    context = payload.deal_context
    target_id = context.target_id or (
        f"entity:{_slug(context.target_name)}" if context.target_name else None
    )
    buyer_id = context.buyer_id or (
        f"entity:{_slug(context.buyer_name)}" if context.buyer_name else None
    )
    entities = tuple(
        item
        for item in (
            CanonicalEntityReference(target_id, display_name=context.target_name or target_id)
            if target_id
            else None,
            CanonicalEntityReference(buyer_id, display_name=context.buyer_name or buyer_id)
            if buyer_id
            else None,
        )
        if item is not None
    )
    deal_context = DealContext(
        context.deal_id,
        engagement_id=context.deal_id,
        buyer_entity_id=buyer_id,
        target_entity_id=target_id,
        transaction_thesis=context.transaction_thesis,
        strategic_rationale=context.strategic_rationale,
        geographies=context.geography,
        sectors=context.sector,
        reporting_currency=context.reporting_currency,
        as_of_date=context.as_of_date,
        requested_capabilities=payload.requested_methods + payload.requested_workstreams,
    )
    documents = tuple(
        SourceDocumentReference(document_id, ProjectId.PROJECT_1, document_id)
        for document_id in payload.document_ids
    )
    request = UserDealRequest(
        f"request:{run_id}",
        payload.user_query,
        target=next((item for item in entities if item.canonical_entity_id == target_id), None),
        buyer=next((item for item in entities if item.canonical_entity_id == buyer_id), None),
        requested_capabilities=payload.requested_methods + payload.requested_workstreams,
        reporting_currency=context.reporting_currency,
        mode=RequestMode.OFFLINE,
    )
    return request, DealState(deal_context, entities, documents)


def _slug(value: str | None) -> str:
    return "-".join((value or "unknown").casefold().split())


app = create_app()
