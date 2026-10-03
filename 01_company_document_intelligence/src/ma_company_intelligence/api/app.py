"""FastAPI application factory and thin transport routes."""

from __future__ import annotations

import logging
import re
import time
from typing import Annotated, Any
from uuid import uuid4

from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse

from ma_company_intelligence import __version__
from ma_company_intelligence.api.errors import install_exception_handlers
from ma_company_intelligence.api.schemas import (
    AnswerResponse,
    ErrorBody,
    ErrorResponse,
    HealthResponse,
    IndexDocumentRequest,
    IndexDocumentResponse,
    QuestionRequest,
    ResearchRequest,
    ResearchResponse,
)
from ma_company_intelligence.application import (
    APISettings,
    CompanyIntelligenceService,
    IndexDocumentCommand,
    ServiceContainer,
)

LOGGER = logging.getLogger(__name__)
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    413: {"model": ErrorResponse},
    415: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
    502: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


def create_app(
    *,
    service: CompanyIntelligenceService | None = None,
    settings: APISettings | None = None,
) -> FastAPI:
    """Create an API with explicit injectable dependencies for offline tests."""

    resolved_settings = settings or APISettings.from_environment()
    logging.basicConfig(
        level=getattr(logging, resolved_settings.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    application = FastAPI(
        title="M&A Company Research & Document Intelligence API",
        version=__version__,
        description=(
            "Evidence-backed local document indexing, grounded Q&A, and structured company "
            "research. Provider credentials are required only for provider-dependent operations."
        ),
    )
    application.state.container = ServiceContainer(
        api_settings=resolved_settings,
        service=service,
    )
    application.state.api_settings = resolved_settings
    install_exception_handlers(application)

    @application.middleware("http")
    async def request_observability(request: Request, call_next):  # type: ignore[no-untyped-def]
        supplied_id = request.headers.get("X-Request-ID", "")
        request_id = supplied_id if _REQUEST_ID_PATTERN.fullmatch(supplied_id) else uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        LOGGER.info(
            "request_received request_id=%s method=%s path=%s",
            request_id,
            request.method,
            request.url.path,
        )
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                body_size = int(content_length)
            except ValueError:
                body_size = resolved_settings.max_request_body_bytes + 1
            if body_size > resolved_settings.max_request_body_bytes:
                response = JSONResponse(
                    status_code=413,
                    content=ErrorResponse(
                        error=ErrorBody(
                            code="request_too_large",
                            message="Request body exceeds the size limit.",
                            request_id=request_id,
                        )
                    ).model_dump(),
                )
                response.headers["X-Request-ID"] = request_id
                LOGGER.warning(
                    "request_rejected request_id=%s code=request_too_large",
                    request_id,
                )
                return response
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        LOGGER.info(
            "request_completed request_id=%s status=%d duration_ms=%.2f",
            request_id,
            response.status_code,
            (time.perf_counter() - started) * 1000,
        )
        return response

    @application.get("/health", response_model=HealthResponse, tags=["status"])
    def health() -> HealthResponse:
        return HealthResponse()

    @application.post(
        "/v1/documents/index",
        response_model=IndexDocumentResponse,
        status_code=status.HTTP_201_CREATED,
        responses=_ERROR_RESPONSES,
        tags=["documents"],
    )
    def index_document(
        payload: IndexDocumentRequest,
        dependency: Annotated[CompanyIntelligenceService, Depends(_service)],
    ) -> IndexDocumentResponse:
        result = dependency.index_document(
            IndexDocumentCommand(
                source_reference=payload.source_reference,
                metadata=payload.metadata.to_domain(),
                chunking=payload.chunking.to_domain(),
            )
        )
        return IndexDocumentResponse.from_domain(result)

    @application.post(
        "/v1/answers",
        response_model=AnswerResponse,
        responses=_ERROR_RESPONSES,
        tags=["research"],
    )
    def answer_question(
        payload: QuestionRequest,
        request: Request,
        dependency: Annotated[CompanyIntelligenceService, Depends(_service)],
    ) -> AnswerResponse:
        api_settings: APISettings = request.app.state.api_settings
        if len(payload.question) > api_settings.max_question_characters:
            raise ValueError("question exceeds configured character limit")
        if payload.top_k > api_settings.max_top_k:
            raise ValueError("top_k exceeds configured limit")
        result = dependency.answer(
            payload.question,
            top_k=payload.top_k,
            filters=payload.filters.to_domain() if payload.filters else None,
        )
        return AnswerResponse.from_domain(result)

    @application.post(
        "/v1/research",
        response_model=ResearchResponse,
        responses=_ERROR_RESPONSES,
        tags=["research"],
    )
    def structured_research(
        payload: ResearchRequest,
        dependency: Annotated[CompanyIntelligenceService, Depends(_service)],
    ) -> ResearchResponse:
        result = dependency.research(
            company_name=payload.company_name,
            filters=payload.filters.to_domain() if payload.filters else None,
        )
        return ResearchResponse.from_domain(result)

    return application


def _service(request: Request) -> CompanyIntelligenceService:
    container: ServiceContainer = request.app.state.container
    return container.get_service()


app = create_app()
