"""Offline fixture and optional LangChain-compatible structured extraction providers."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from ma_precedent_transactions.errors import (
    ExtractionProviderError,
    ExtractionValidationError,
)
from ma_precedent_transactions.extraction.models import ExtractionBatch
from ma_precedent_transactions.extraction.ports import ExtractionRequest
from ma_precedent_transactions.extraction.prompts import (
    EXTRACTION_INSTRUCTIONS,
    build_extraction_input,
)
from ma_precedent_transactions.extraction.schema import (
    EXTRACTION_JSON_SCHEMA,
    load_extraction_fixture,
    parse_extraction_payload,
)


class _StructuredRunnable(Protocol):
    def invoke(self, input: object) -> object: ...


class _LangChainChatModel(Protocol):
    def with_structured_output(self, schema: object) -> _StructuredRunnable: ...


class FixtureStructuredExtractor:
    """Deterministic fixture extractor that still enforces evidence-link integrity."""

    def __init__(self, fixture_path: Path) -> None:
        self._batches = load_extraction_fixture(fixture_path)

    @property
    def provider_name(self) -> str:
        return "fixture"

    def extract(self, request: ExtractionRequest) -> ExtractionBatch:
        try:
            batch = self._batches[request.transaction_id]
        except KeyError as error:
            raise ExtractionProviderError(
                f"no fixture extraction for transaction {request.transaction_id}"
            ) from error
        available = {item.evidence.evidence_id for item in request.evidence}
        missing = {
            evidence_id
            for observation in batch.observations
            for evidence_id in observation.evidence_ids
            if evidence_id not in available
        }
        if missing:
            raise ExtractionValidationError(
                "fixture cited evidence outside the bounded context: " + ", ".join(sorted(missing))
            )
        return batch


class LangChainStructuredExtractor:
    """Use a LangChain chat model's native structured-output runnable when installed.

    The adapter owns no model or vendor dependency. Callers inject a LangChain chat model that
    implements ``with_structured_output``. The returned mapping is validated again into the
    application-owned frozen dataclasses before it crosses the provider boundary.
    """

    def __init__(self, model: _LangChainChatModel) -> None:
        self._runnable = model.with_structured_output(EXTRACTION_JSON_SCHEMA)

    @property
    def provider_name(self) -> str:
        return "langchain_structured_output"

    def extract(self, request: ExtractionRequest) -> ExtractionBatch:
        messages = (
            ("system", EXTRACTION_INSTRUCTIONS),
            ("human", build_extraction_input(request.transaction_id, request.evidence)),
        )
        try:
            raw = self._runnable.invoke(messages)
        except Exception as error:
            raise ExtractionProviderError("LangChain structured extraction failed") from error
        if hasattr(raw, "model_dump"):
            raw = raw.model_dump()
        if not isinstance(raw, Mapping):
            raise ExtractionValidationError("structured model output must be an object")
        batch = parse_extraction_payload(raw)
        if batch.transaction_id != request.transaction_id:
            raise ExtractionValidationError("model changed the transaction ID")
        available = {item.evidence.evidence_id for item in request.evidence}
        cited = {value for item in batch.observations for value in item.evidence_ids}
        unsupported = cited - available
        if unsupported:
            raise ExtractionValidationError(
                "model cited unknown evidence IDs: " + ", ".join(sorted(unsupported))
            )
        return batch
