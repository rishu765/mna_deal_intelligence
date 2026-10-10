from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from ma_deal_intelligence.adapters import (
    AdapterMode,
    AdapterValidationError,
    Project1Adapter,
    Project2Adapter,
    Project3Adapter,
    Project4Adapter,
    Project5Adapter,
)
from ma_deal_intelligence.adapters.base import NativeProjectResult
from ma_deal_intelligence.adapters.project1 import Project1NativeRequest
from ma_deal_intelligence.contracts import (
    CapabilityId,
    DiligenceRequest,
    DocumentIntelligenceRequest,
    PrecedentTransactionsRequest,
    TargetScreeningRequest,
    TradingCompsRequest,
)
from ma_deal_intelligence.evidence import ProjectId
from ma_deal_intelligence.outputs import CompanyIntelligenceOutput
from ma_deal_intelligence.planning_fixtures import TARGET, fixture_state
from ma_deal_intelligence.registry import (
    CapabilityAvailability,
    DuplicateCapabilityError,
    default_registry,
)
from ma_deal_intelligence.workflow import DealError, DealWarning, IssueSeverity, ResultStatus


def test_all_project_adapters_translate_and_preserve_fixture_provenance() -> None:
    state = fixture_state(financials=True)
    context = state.deal_context
    cases: tuple[tuple[Any, str, Any], ...] = (
        (
            Project1Adapter(),
            CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE,
            DocumentIntelligenceRequest(context, TARGET.canonical_entity_id, ("doc:fixture",)),
        ),
        (
            Project2Adapter(),
            CapabilityId.P2_SOURCE_TARGETS,
            TargetScreeningRequest(context, "criteria:fixture"),
        ),
        (
            Project3Adapter(),
            CapabilityId.P3_PRODUCE_VALUATION_RANGE,
            TradingCompsRequest(context, TARGET.canonical_entity_id, "profile:fixture"),
        ),
        (
            Project4Adapter(),
            CapabilityId.P4_PRODUCE_VALUATION_RANGE,
            PrecedentTransactionsRequest(context, TARGET.canonical_entity_id, "search:fixture"),
        ),
        (
            Project5Adapter(),
            CapabilityId.P5_PRODUCE_DILIGENCE_FINDINGS,
            DiligenceRequest(context, TARGET.canonical_entity_id, ("doc:fixture",)),
        ),
    )
    for adapter, capability, request in cases:
        validation = adapter.validate_input(capability, request)
        assert validation.valid
        envelope = adapter.invoke(capability, request)
        assert envelope.source_project is adapter.project_id
        assert envelope.payload is not None
        assert envelope.evidence
        assert envelope.evidence_refs == tuple(item.evidence_id for item in envelope.evidence)
        assert adapter.health_check().healthy


def test_adapter_rejects_bad_input_and_native_mode_without_service() -> None:
    state = fixture_state(documents=False)
    request = DocumentIntelligenceRequest(state.deal_context, TARGET.canonical_entity_id)
    with pytest.raises(AdapterValidationError, match="indexed document"):
        Project1Adapter().invoke(CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE, request)
    assert not Project1Adapter(mode=AdapterMode.NATIVE).health_check().healthy


def test_registry_discovery_availability_and_duplicate_rejection() -> None:
    registry = default_registry()
    assert registry.for_project(ProjectId.PROJECT_3)[0].capability_id == (
        CapabilityId.P3_PRODUCE_VALUATION_RANGE
    )
    assert registry.requiring("target_financials")
    assert all("documents" not in item.required_inputs for item in registry.without_documents())
    status = registry.status(
        CapabilityId.P3_PRODUCE_VALUATION_RANGE,
        frozenset({"target_entity", "reporting_currency"}),
    )
    assert status.availability is CapabilityAvailability.REQUIRES_INPUT
    assert status.missing_inputs == ("target_financials",)
    assert registry.status("missing.capability").availability is CapabilityAvailability.UNSUPPORTED
    with pytest.raises(DuplicateCapabilityError):
        registry.register(Project1Adapter())


def test_project5_requires_engagement_id() -> None:
    state = fixture_state()
    context = replace(state.deal_context, engagement_id=None)
    request = DiligenceRequest(context, TARGET.canonical_entity_id, ("doc:fixture",))
    assert (
        "engagement ID is required"
        in Project5Adapter()
        .validate_input(CapabilityId.P5_PRODUCE_DILIGENCE_FINDINGS, request)
        .errors
    )


def test_native_warning_and_error_mapping_is_structured() -> None:
    state = fixture_state()
    warning = DealWarning(
        "warning:native",
        "PARTIAL_NATIVE_RESULT",
        IssueSeverity.MEDIUM,
        "One native source was unavailable.",
        ProjectId.PROJECT_1,
    )
    error = DealError(
        "error:native",
        "SOURCE_UNAVAILABLE",
        ProjectId.PROJECT_1,
        CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE,
        True,
        True,
        "A source was unavailable.",
    )

    def execute(request: Project1NativeRequest) -> NativeProjectResult[CompanyIntelligenceOutput]:
        payload = CompanyIntelligenceOutput(request.entity_id, request.document_ids)
        return NativeProjectResult(payload, warnings=(warning,), errors=(error,))

    adapter = Project1Adapter(mode=AdapterMode.NATIVE, native_executor=execute)
    result = adapter.invoke(
        CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE,
        DocumentIntelligenceRequest(
            state.deal_context, TARGET.canonical_entity_id, ("doc:fixture",)
        ),
    )
    assert result.status is ResultStatus.PARTIAL
    assert result.warnings == (warning,)
    assert result.errors == (error,)
