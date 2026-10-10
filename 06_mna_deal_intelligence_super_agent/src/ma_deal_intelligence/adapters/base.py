"""Shared mechanics for concrete specialist adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Generic, Protocol, TypeVar

from ma_deal_intelligence.contracts import HealthStatus, ProjectCapability, ValidationResult
from ma_deal_intelligence.evidence import EvidenceReference, ProjectId
from ma_deal_intelligence.identity import DealContext
from ma_deal_intelligence.outputs import ProjectResultEnvelope
from ma_deal_intelligence.workflow import DealError, DealWarning, ResultStatus


class AdapterRequest(Protocol):
    @property
    def deal_context(self) -> DealContext: ...

    @property
    def execution_id(self) -> str | None: ...


RequestT = TypeVar("RequestT", bound=AdapterRequest)
NativeRequestT = TypeVar("NativeRequestT")
NativeInputT = TypeVar("NativeInputT", contravariant=True)
PayloadT = TypeVar("PayloadT")


class AdapterMode(StrEnum):
    FIXTURE = "fixture"
    NATIVE = "native"


@dataclass(frozen=True, slots=True)
class NativeProjectResult(Generic[PayloadT]):
    payload: PayloadT
    evidence: tuple[EvidenceReference, ...] = ()
    warnings: tuple[DealWarning, ...] = ()
    errors: tuple[DealError, ...] = ()
    data_as_of: datetime | None = None


class NativeExecutor(Protocol[NativeInputT, PayloadT]):
    def __call__(self, request: NativeInputT) -> NativeProjectResult[PayloadT]: ...


class AdapterValidationError(ValueError):
    """Raised when a request cannot safely cross a specialist boundary."""


class BaseAdapter(Generic[RequestT, NativeRequestT, PayloadT]):
    project_id: ProjectId
    supported_capabilities: tuple[ProjectCapability, ...]

    def __init__(
        self,
        *,
        mode: AdapterMode = AdapterMode.FIXTURE,
        native_executor: NativeExecutor[NativeRequestT, PayloadT] | None = None,
    ) -> None:
        self.mode = mode
        self._native_executor = native_executor

    def capability_metadata(self) -> tuple[ProjectCapability, ...]:
        return self.supported_capabilities

    def health_check(self) -> HealthStatus:
        if self.mode is AdapterMode.FIXTURE:
            return HealthStatus(True, "deterministic fixture mode")
        if self._native_executor is None:
            return HealthStatus(False, "native service entry point was not supplied")
        return HealthStatus(True, "native service entry point supplied")

    def validate_input(self, capability_id: str, request: RequestT) -> ValidationResult:
        supported = {item.capability_id for item in self.supported_capabilities}
        errors: list[str] = []
        if capability_id not in supported:
            errors.append(f"unsupported capability: {capability_id}")
        errors.extend(self._validation_errors(request))
        if self.mode is AdapterMode.NATIVE and self._native_executor is None:
            errors.append("native service entry point is unavailable")
        return ValidationResult(not errors, tuple(errors))

    def invoke(self, capability_id: str, request: RequestT) -> ProjectResultEnvelope[PayloadT]:
        validation = self.validate_input(capability_id, request)
        if not validation.valid:
            raise AdapterValidationError("; ".join(validation.errors))
        native_request = self.translate_input(request)
        if self.mode is AdapterMode.FIXTURE:
            result = self.fixture_result(native_request)
        else:
            assert self._native_executor is not None
            result = self._native_executor(native_request)
        generated_at = datetime.now(UTC)
        status = (
            ResultStatus.PARTIAL
            if result.errors
            else ResultStatus.SUCCEEDED_WITH_WARNINGS
            if result.warnings
            else ResultStatus.SUCCEEDED
        )
        return ProjectResultEnvelope(
            self.project_id,
            capability_id,
            self.execution_id(request, capability_id),
            status,
            result.payload,
            tuple(item.evidence_id for item in result.evidence),
            (),
            result.warnings,
            result.errors,
            generated_at,
            result.data_as_of,
            "1.0.0",
            result.evidence,
        )

    def execution_id(self, request: RequestT, capability_id: str) -> str:
        explicit = getattr(request, "execution_id", None)
        if isinstance(explicit, str) and explicit.strip():
            return explicit
        context = request.deal_context
        return f"{self.mode.value}:{context.deal_id}:{capability_id}"

    def _validation_errors(self, request: RequestT) -> tuple[str, ...]:
        raise NotImplementedError

    def translate_input(self, request: RequestT) -> NativeRequestT:
        raise NotImplementedError

    def fixture_result(self, request: NativeRequestT) -> NativeProjectResult[PayloadT]:
        raise NotImplementedError
