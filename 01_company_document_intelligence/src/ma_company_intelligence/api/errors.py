"""Safe HTTP error classification and response handling."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ma_company_intelligence.api.schemas import ErrorBody, ErrorResponse
from ma_company_intelligence.application import (
    DocumentAccessError,
    DocumentSizeLimitError,
    IndexUnavailableError,
    NoIndexableTextError,
)
from ma_company_intelligence.citations import CitationError
from ma_company_intelligence.embeddings import (
    EmbeddingConfigurationError,
    EmbeddingError,
    EmbeddingProviderError,
)
from ma_company_intelligence.generation import (
    GenerationConfigurationError,
    GenerationError,
    GenerationProviderError,
)
from ma_company_intelligence.indexing import IndexingError
from ma_company_intelligence.ingestion import (
    DocumentIngestionError,
    SourceNotFoundError,
    UnsupportedDocumentTypeError,
)
from ma_company_intelligence.rag import InvalidQuestionError, RAGError
from ma_company_intelligence.research import InvalidResearchRequestError, ResearchError
from ma_company_intelligence.retrieval import InvalidQueryError, RetrievalError

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ErrorClassification:
    status_code: int
    code: str
    safe_message: str


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        LOGGER.info(
            "request_validation_failed request_id=%s errors=%d",
            _request_id(request),
            len(error.errors()),
        )
        return _response(
            request,
            ErrorClassification(422, "invalid_request", "Request validation failed."),
        )

    async def application_error(request: Request, error: Exception) -> JSONResponse:
        classification = classify_error(error)
        LOGGER.warning(
            "operation_failed request_id=%s code=%s error_type=%s",
            _request_id(request),
            classification.code,
            type(error).__name__,
        )
        return _response(request, classification)

    expected_errors = (
        DocumentAccessError,
        DocumentSizeLimitError,
        IndexUnavailableError,
        NoIndexableTextError,
        CitationError,
        EmbeddingError,
        GenerationError,
        IndexingError,
        DocumentIngestionError,
        RAGError,
        ResearchError,
        RetrievalError,
        ValueError,
    )
    for error_type in expected_errors:
        app.add_exception_handler(error_type, application_error)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception) -> JSONResponse:
        LOGGER.exception("unexpected_failure request_id=%s", _request_id(request))
        return _response(request, classify_error(error))


def classify_error(error: Exception) -> ErrorClassification:
    if isinstance(error, DocumentAccessError):
        return ErrorClassification(
            403, "document_access_denied", "Document reference is not allowed."
        )
    if isinstance(error, DocumentSizeLimitError):
        return ErrorClassification(413, "document_too_large", "Document exceeds the size limit.")
    if isinstance(error, SourceNotFoundError):
        return ErrorClassification(404, "document_not_found", "Document was not found.")
    if isinstance(error, UnsupportedDocumentTypeError):
        return ErrorClassification(415, "unsupported_document", "Only PDF documents are supported.")
    if isinstance(error, NoIndexableTextError):
        return ErrorClassification(422, "no_indexable_text", "Document has no indexable text.")
    if isinstance(error, DocumentIngestionError):
        return ErrorClassification(422, "document_parsing_failed", "Document could not be parsed.")
    if isinstance(error, (EmbeddingConfigurationError, GenerationConfigurationError)):
        return ErrorClassification(
            503, "configuration_error", "Required provider configuration is unavailable."
        )
    if isinstance(error, (EmbeddingProviderError, GenerationProviderError)):
        return ErrorClassification(
            502, "provider_failure", "An external AI provider request failed."
        )
    if isinstance(error, (EmbeddingError, GenerationError, CitationError)):
        return ErrorClassification(
            502, "provider_response_invalid", "An AI provider returned an invalid response."
        )
    if isinstance(error, IndexUnavailableError):
        return ErrorClassification(
            409, "index_unavailable", "No vector index is available. Index a document first."
        )
    if isinstance(error, IndexingError):
        return ErrorClassification(503, "indexing_failure", "The document index operation failed.")
    if isinstance(error, (InvalidQueryError, InvalidQuestionError, InvalidResearchRequestError)):
        return ErrorClassification(422, "invalid_request", "The operation parameters are invalid.")
    if isinstance(error, RetrievalError):
        return ErrorClassification(503, "retrieval_failure", "Evidence retrieval failed.")
    if isinstance(error, (RAGError, ResearchError)):
        return ErrorClassification(502, "generation_failure", "Grounded synthesis failed.")
    if isinstance(error, ValueError):
        return ErrorClassification(422, "invalid_request", "The operation parameters are invalid.")
    return ErrorClassification(500, "internal_error", "An unexpected internal error occurred.")


def _response(request: Request, classification: ErrorClassification) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorBody(
            code=classification.code,
            message=classification.safe_message,
            request_id=_request_id(request),
        )
    )
    return JSONResponse(status_code=classification.status_code, content=payload.model_dump())


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "unavailable"))
