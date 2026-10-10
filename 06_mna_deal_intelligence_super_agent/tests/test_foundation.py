from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ma_deal_intelligence.contracts import (
    CapabilityId,
    DocumentIntelligenceRequest,
    ExecutionNature,
    HealthStatus,
    ProjectAdapter,
    ProjectCapability,
    SchemaReference,
    ValidationResult,
)
from ma_deal_intelligence.evidence import EvidenceKind, EvidenceReference, ProjectId
from ma_deal_intelligence.finance import (
    DiligenceFindingReference,
    EstimateStatus,
    FinancialMetricReference,
    FinancialPeriodReference,
    FindingSeverity,
    FindingStatus,
    MetricBasis,
    ValuationBasis,
    ValuationMethod,
    ValuationReference,
)
from ma_deal_intelligence.fixtures import representative_deal_state
from ma_deal_intelligence.identity import CanonicalEntityReference, DealContext
from ma_deal_intelligence.outputs import CompanyIntelligenceOutput, ProjectResultEnvelope
from ma_deal_intelligence.serialization import (
    SerializationError,
    state_from_dict,
    state_from_json,
    state_to_dict,
    state_to_json,
)
from ma_deal_intelligence.state import DEAL_STATE_SCHEMA_VERSION, DealState
from ma_deal_intelligence.workflow import (
    AnalystDecision,
    ArtifactVersion,
    Assumption,
    DealError,
    DealWarning,
    DecisionAction,
    DependencyKind,
    DependencyRequirement,
    ExecutionStatus,
    IssueSeverity,
    ResultStatus,
    WorkflowStatus,
)


def test_context_entity_evidence_and_finance_references() -> None:
    entity = CanonicalEntityReference("entity:1", display_name="Target", aliases=("T",))
    context = DealContext("deal:1", target_entity_id=entity.canonical_entity_id)
    evidence = EvidenceReference(
        "evidence:1",
        ProjectId.PROJECT_1,
        EvidenceKind.DOCUMENT,
        document_id="doc:1",
        page_numbers=(2,),
        physical_page_indexes=(1,),
        section="Financials",
        chunk_id="chunk:1",
    )
    period = FinancialPeriodReference("FY2025", date(2025, 1, 1), date(2025, 12, 31))
    metric = FinancialMetricReference(
        "metric:1",
        "revenue",
        Decimal("125.50"),
        "usd",
        "million",
        period,
        MetricBasis.REPORTED,
        EstimateStatus.ACTUAL,
        ProjectId.PROJECT_3,
        "source:metric:1",
        entity.canonical_entity_id,
        (evidence.evidence_id,),
    )
    valuation = ValuationReference(
        "valuation:1",
        ValuationMethod.TRADING_COMPARABLES,
        Decimal("900"),
        Decimal("1000"),
        Decimal("1100"),
        ValuationBasis.ENTERPRISE_VALUE,
        "LTM EBITDA",
        "usd",
        "million",
        date(2025, 12, 31),
        ProjectId.PROJECT_3,
        "p3:output:1",
        (metric.metric_id,),
    )
    finding = DiligenceFindingReference(
        "finding:1",
        "financial",
        "EBITDA adjustment",
        FindingSeverity.HIGH,
        "material",
        ("valuation",),
        FindingStatus.UNDER_REVIEW,
        ProjectId.PROJECT_5,
        "p5:finding:1",
        (evidence.evidence_id,),
    )

    assert context.target_entity_id == entity.canonical_entity_id
    assert evidence.page_numbers == (2,)
    assert metric.currency == "USD"
    assert valuation.midpoint == Decimal("1000")
    assert finding.source_project is ProjectId.PROJECT_5


def test_assumptions_warnings_errors_decisions_and_staleness() -> None:
    assumption = Assumption("a:1", "Peer median applies", ProjectId.PROJECT_3, "valuation")
    warning = DealWarning(
        "w:1", "LOW_SAMPLE", IssueSeverity.MEDIUM, "Only three peers", ProjectId.PROJECT_3
    )
    error = DealError(
        "e:1", "SOURCE_UNAVAILABLE", ProjectId.PROJECT_1, "retrieve", True, True, "Unavailable"
    )
    decision = AnalystDecision(
        "d:1",
        "finding",
        "finding:1",
        "under_review",
        DecisionAction.APPROVE,
        "Evidence is sufficient",
        "analyst",
        datetime(2026, 1, 1, tzinfo=UTC),
    )
    version = ArtifactVersion("output:1", "1.0.0", "input:1", stale=True, stale_reason="Changed")

    assert assumption.analyst_approved is False
    assert warning.blocking is False
    assert error.retryable is True
    assert decision.action is DecisionAction.APPROVE
    assert version.stale is True


def test_workflow_and_execution_status_vocabularies_are_complete() -> None:
    assert {status.value for status in WorkflowStatus} == {
        "created",
        "planning",
        "ready",
        "running",
        "partially_completed",
        "review_required",
        "waiting_for_input",
        "completed",
        "completed_with_warnings",
        "failed",
    }
    assert {status.value for status in ExecutionStatus} == {
        "not_started",
        "ready",
        "running",
        "completed",
        "completed_with_warnings",
        "blocked",
        "failed",
        "skipped",
    }


def test_capability_metadata_and_adapter_protocol() -> None:
    capability = ProjectCapability(
        "p1.company_intelligence",
        ProjectId.PROJECT_1,
        "Company intelligence",
        "Return cited company research without duplicating Project 1 logic.",
        SchemaReference("ma_deal_intelligence.contracts", "DocumentIntelligenceRequest", "1.0.0"),
        SchemaReference("ma_deal_intelligence.outputs", "CompanyIntelligenceOutput", "1.0.0"),
        execution_nature=ExecutionNature.AI_ASSISTED,
    )

    class StubAdapter:
        def capability_metadata(self) -> tuple[ProjectCapability, ...]:
            return (capability,)

        def validate_input(
            self, capability_id: str, request: DocumentIntelligenceRequest
        ) -> ValidationResult:
            return ValidationResult(capability_id == capability.capability_id)

        def invoke(
            self, capability_id: str, request: DocumentIntelligenceRequest
        ) -> ProjectResultEnvelope[CompanyIntelligenceOutput]:
            return ProjectResultEnvelope(
                ProjectId.PROJECT_1,
                capability_id,
                "run:1",
                ResultStatus.SUCCEEDED,
                CompanyIntelligenceOutput(request.entity_id, ()),
                (),
                (),
                (),
                (),
                datetime(2026, 1, 1, tzinfo=UTC),
                None,
                "1.0.0",
            )

        def health_check(self) -> HealthStatus:
            return HealthStatus(True)

    assert isinstance(StubAdapter(), ProjectAdapter)
    assert capability.supports_offline_mode is True
    assert CapabilityId.P5_ANALYZE_QOE.value == "p5.analyze_qoe"


def test_representative_cross_project_state() -> None:
    state = representative_deal_state()
    values = {metric.metric_id: metric.value for metric in state.financial_metrics}

    assert values["metric:p3:reported-ebitda"] == Decimal("100")
    assert values["metric:p5:diligence-adjusted-ebitda"] == Decimal("85")
    assert state.valuation_outputs[0].midpoint == Decimal("1000")
    assert state.metric_conflicts[0].requires_analyst_review is True
    assert state.requires_analyst_review is True
    assert state.artifact_versions[0].stale is True
    assert state.analyst_decisions[0].action is DecisionAction.REJECT
    assert state.dependencies[0].satisfied is True
    assert len(state.lineage.edges) == 2
    assert len(state.company_intelligence) == 1
    assert len(state.target_screening_results) == 1
    assert len(state.trading_comps_results) == 1
    assert len(state.precedent_transaction_results) == 1
    assert len(state.diligence_results) == 1


def test_deal_state_serialization_round_trip_preserves_typed_values() -> None:
    original = representative_deal_state()
    restored = state_from_json(state_to_json(original))

    assert restored == original
    assert restored.schema_version == DEAL_STATE_SCHEMA_VERSION
    assert isinstance(restored.financial_metrics[0].value, Decimal)
    assert isinstance(restored.deal_context.as_of_date, date)
    assert restored.workflow_status is WorkflowStatus.REVIEW_REQUIRED


def test_schema_version_rejection() -> None:
    payload = state_to_dict(representative_deal_state())
    payload["schema_version"] = "99.0.0"
    with pytest.raises(SerializationError, match="schema_version"):
        state_from_dict(payload)


def test_core_validation_rejects_ambiguous_or_invalid_state() -> None:
    with pytest.raises(ValueError, match="legal_name or display_name"):
        CanonicalEntityReference("entity:unknown")
    with pytest.raises(ValueError, match="stale artifacts require"):
        ArtifactVersion("a", "1.0.0", "i", stale=True)
    with pytest.raises(ValueError, match="state revision"):
        DealState(DealContext("deal:bad"), revision=0)


def test_dependency_contract_supports_required_and_any_of_inputs() -> None:
    required = DependencyRequirement(
        "dependency:financials",
        "p3.trading_comps",
        DependencyKind.REQUIRED,
        required_artifact_ids=("metric:ebitda",),
    )
    any_of = DependencyRequirement(
        "dependency:valuation",
        "p6.final_synthesis",
        DependencyKind.ANY_OF,
        required_capability_ids=("p3.trading_comps", "p4.precedent_transactions"),
    )
    assert required.required_artifact_ids == ("metric:ebitda",)
    assert any_of.kind is DependencyKind.ANY_OF
