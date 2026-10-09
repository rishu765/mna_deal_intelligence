"""Minimal FastAPI transport over the checkpointed precedent workflow."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from ma_precedent_transactions import __version__
from ma_precedent_transactions.api.schemas import (
    HealthResponse,
    HumanReviewRequest,
    PrecedentRunRequest,
    TargetInput,
    WorkflowResponse,
)
from ma_precedent_transactions.discovery import AcquisitionContext
from ma_precedent_transactions.domain import (
    BuyerType,
    CapitalComponentKind,
    CapitalStructureComponent,
    CapitalStructureSnapshot,
    EstimateStatus,
    EvidenceReference,
    ExtractionMethod,
    FactStatus,
    FinancialMetric,
    FinancialMetricName,
    FinancialPeriod,
    FinancialUnit,
    MetricBasis,
    MonetaryAmount,
    PeriodKind,
    SourceReliability,
    TransactionType,
)
from ma_precedent_transactions.errors import PrecedentTransactionsError
from ma_precedent_transactions.precedent import (
    OverrideAction,
    TargetCapitalProfile,
    TargetComparabilityProfile,
    TargetValuationProfile,
    precedent_fixture_inputs,
)
from ma_precedent_transactions.presentation import workflow_state_to_dict
from ma_precedent_transactions.workflow import (
    HumanReviewDecision,
    ObservationResolution,
    ReviewAction,
    ReviewOverride,
    ReviewPolicy,
    WorkflowApplication,
    WorkflowRequest,
    WorkflowState,
    WorkflowStatus,
    build_offline_application,
)

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class APIRuntime:
    workflow: WorkflowApplication
    run_ids: set[str] = field(default_factory=set)


def create_app(*, workflow: WorkflowApplication | None = None) -> FastAPI:
    runtime = APIRuntime(workflow or build_offline_application())
    application = FastAPI(
        title="Precedent Transactions Agent",
        version=__version__,
        description="Offline-first, evidence-grounded precedent transaction workflow.",
        debug=False,
    )
    application.state.runtime = runtime
    _install_errors(application)

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="ma-precedent-transactions",
            version=__version__,
            mode="offline_fixture",
        )

    @application.post("/precedents/run", response_model=WorkflowResponse, tags=["precedents"])
    def run_precedents(request: PrecedentRunRequest) -> WorkflowResponse:
        run_id = request.run_id or uuid4().hex
        if run_id in runtime.run_ids:
            raise HTTPException(status_code=409, detail="run_id already exists")
        state = runtime.workflow.start(_workflow_request(run_id, request), thread_id=run_id)
        runtime.run_ids.add(run_id)
        return _response(run_id, state)

    @application.get(
        "/precedents/runs/{run_id}", response_model=WorkflowResponse, tags=["precedents"]
    )
    def get_run(run_id: str) -> WorkflowResponse:
        _known_run(runtime, run_id)
        return _response(run_id, runtime.workflow.state(thread_id=run_id))

    @application.post(
        "/precedents/runs/{run_id}/review",
        response_model=WorkflowResponse,
        tags=["precedents"],
    )
    def review_run(run_id: str, request: HumanReviewRequest) -> WorkflowResponse:
        _known_run(runtime, run_id)
        current = runtime.workflow.state(thread_id=run_id)
        if current.get("status") is not WorkflowStatus.AWAITING_HUMAN_REVIEW:
            raise HTTPException(status_code=409, detail="run is not awaiting human review")
        decision = HumanReviewDecision(
            ReviewAction(request.action),
            request.reviewer,
            request.rationale,
            tuple(
                ObservationResolution(
                    item.transaction_id,
                    item.field,
                    item.selected_observation_id,
                    item.rationale,
                )
                for item in request.resolutions
            ),
            tuple(
                ReviewOverride(item.transaction_id, OverrideAction(item.action), item.rationale)
                for item in request.overrides
            ),
            datetime.now(UTC),
        )
        return _response(run_id, runtime.workflow.resume(thread_id=run_id, decision=decision))

    return application


def _workflow_request(run_id: str, request: PrecedentRunRequest) -> WorkflowRequest:
    target, valuation = _target_profiles(request.target)
    criteria = request.acquisition_criteria
    context = AcquisitionContext(
        run_id,
        request.target.industry,
        request.target.business_description,
        tuple(request.target.geographies),
        criteria.announced_from,
        criteria.announced_to,
        tuple(TransactionType(item) for item in criteria.transaction_types),
        tuple(BuyerType(item) for item in criteria.buyer_types),
        None if criteria.minimum_size is None else Decimal(criteria.minimum_size),
        None if criteria.maximum_size is None else Decimal(criteria.maximum_size),
        criteria.size_currency,
        tuple(criteria.keywords),
    )
    return WorkflowRequest(run_id, context, target, valuation, ReviewPolicy(request.review_policy))


def _target_profiles(
    request: TargetInput,
) -> tuple[TargetComparabilityProfile, TargetValuationProfile]:
    fixture_comparable, fixture_valuation, _ = precedent_fixture_inputs()
    metrics = tuple(_metric(item) for item in request.metrics)
    if not metrics:
        metrics = fixture_valuation.metrics
    revenue = next((item for item in metrics if item.name is FinancialMetricName.REVENUE), None)
    capital = _capital(request, fixture_valuation.capital)
    comparable = TargetComparabilityProfile(
        request.target_id,
        request.industry,
        request.business_description,
        tuple(request.products),
        tuple(request.customer_types),
        tuple(request.geographies),
        revenue,
    )
    return comparable, TargetValuationProfile(request.target_id, metrics, capital)


def _metric(item: object) -> FinancialMetric:
    from ma_precedent_transactions.api.schemas import TargetMetricInput

    assert isinstance(item, TargetMetricInput)
    evidence = (_input_evidence(item.evidence_id, item.measurement_date),)
    return FinancialMetric(
        item.metric_id,
        FinancialMetricName(item.name),
        Decimal(item.value),
        FinancialUnit(item.unit),
        FinancialPeriod(
            PeriodKind(item.period_kind),
            item.period_label,
            EstimateStatus(item.estimate_status),
            item.period_start,
            item.period_end,
        ),
        MetricBasis(item.basis),
        item.measurement_date,
        FactStatus.DIRECTLY_DISCLOSED,
        evidence,
        item.currency,
        item.adjustment_label,
    )


def _capital(request: TargetInput, default: TargetCapitalProfile) -> TargetCapitalProfile:
    if not request.capital_components:
        return replace(
            default,
            diluted_shares=default.diluted_shares
            if request.diluted_shares is None
            else Decimal(request.diluted_shares),
        )
    components = tuple(
        CapitalStructureComponent(
            item.component_id,
            CapitalComponentKind(item.kind),
            MonetaryAmount(
                Decimal(item.value), item.currency, FinancialUnit(item.unit), item.as_of
            ),
            item.as_of,
            FactStatus.DIRECTLY_DISCLOSED,
            (_input_evidence(item.evidence_id, item.as_of),),
        )
        for item in request.capital_components
    )
    as_of = max(item.as_of for item in request.capital_components)
    share_evidence = (
        ()
        if request.share_count_evidence_id is None
        else (_input_evidence(request.share_count_evidence_id, request.share_count_date or as_of),)
    )
    return TargetCapitalProfile(
        CapitalStructureSnapshot(f"{request.target_id}:capital", as_of, components),
        None if request.diluted_shares is None else Decimal(request.diluted_shares),
        None if request.share_unit is None else FinancialUnit(request.share_unit),
        request.share_count_date,
        request.share_count_basis,
        share_evidence,
    )


def _input_evidence(evidence_id: str, observed: object) -> EvidenceReference:
    from datetime import date

    assert isinstance(observed, date)
    return EvidenceReference(
        evidence_id,
        "user_input",
        "API target input",
        datetime.now(UTC),
        SourceReliability.OTHER,
        ExtractionMethod.MANUAL,
        publication_date=observed,
    )


def _known_run(runtime: APIRuntime, run_id: str) -> None:
    if run_id not in runtime.run_ids:
        raise HTTPException(status_code=404, detail="run not found")


def _response(run_id: str, state: WorkflowState) -> WorkflowResponse:
    payload = workflow_state_to_dict(state)
    return WorkflowResponse(
        run_id=run_id,
        provider_mode="offline_fixture",
        status=str(payload["status"]),
        review_required=bool(payload["review_required"]),
        state=payload,
    )


def _install_errors(app: FastAPI) -> None:
    @app.exception_handler(ValueError)
    async def invalid_value(_: Request, error: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"error": {"code": "invalid_request", "message": str(error)}},
        )

    @app.exception_handler(PrecedentTransactionsError)
    async def provider_error(_: Request, error: PrecedentTransactionsError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": {"code": "workflow_provider_error", "message": str(error)}},
        )

    @app.exception_handler(Exception)
    async def unexpected(_: Request, error: Exception) -> JSONResponse:
        LOGGER.exception("Unhandled precedent API error", exc_info=error)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "The precedent workflow request could not be completed.",
                }
            },
        )


app = create_app()
