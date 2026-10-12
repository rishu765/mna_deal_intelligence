"""Project 5 due-diligence adapter."""

from __future__ import annotations

from dataclasses import dataclass

from ma_deal_intelligence.adapters.base import BaseAdapter, NativeProjectResult
from ma_deal_intelligence.contracts import (
    CapabilityId,
    DiligenceRequest,
    ExecutionNature,
    ProjectCapability,
    SchemaReference,
)
from ma_deal_intelligence.evidence import ProjectId
from ma_deal_intelligence.fixtures import representative_deal_state
from ma_deal_intelligence.outputs import DiligenceOutput


@dataclass(frozen=True, slots=True)
class Project5NativeRequest:
    target_entity_id: str
    engagement_id: str
    vdr_document_ids: tuple[str, ...]
    workstreams: tuple[str, ...]


class Project5Adapter(BaseAdapter[DiligenceRequest, Project5NativeRequest, DiligenceOutput]):
    fixture_document_ids = ("doc:fixture-vdr",)
    project_id = ProjectId.PROJECT_5
    supported_capabilities = (
        ProjectCapability(
            CapabilityId.P5_PRODUCE_DILIGENCE_FINDINGS,
            project_id,
            "Due-diligence analysis",
            "Use Project 5 VDR, QoE, financial, and specialist diligence services.",
            SchemaReference("ma_deal_intelligence.contracts", "DiligenceRequest", "1.0.0"),
            SchemaReference("ma_deal_intelligence.outputs", "DiligenceOutput", "1.0.0"),
            execution_nature=ExecutionNature.HYBRID,
            requires_human_review=True,
            required_inputs=("target_entity", "documents"),
            produced_outputs=(
                "diligence_findings",
                "adjusted_ebitda",
                "working_capital",
                "net_debt",
                "missing_information",
            ),
        ),
    )

    def _validation_errors(self, request: DiligenceRequest) -> tuple[str, ...]:
        errors: list[str] = []
        if not request.target_entity_id.strip():
            errors.append("target entity identity is required")
        if not request.vdr_document_ids:
            errors.append("VDR documents are required")
        if request.deal_context.engagement_id is None:
            errors.append("engagement ID is required")
        return tuple(errors)

    def translate_input(self, request: DiligenceRequest) -> Project5NativeRequest:
        assert request.deal_context.engagement_id is not None
        return Project5NativeRequest(
            request.target_entity_id,
            request.deal_context.engagement_id,
            request.vdr_document_ids,
            request.requested_workstreams,
        )

    def fixture_result(
        self, request: Project5NativeRequest
    ) -> NativeProjectResult[DiligenceOutput]:
        state = representative_deal_state()
        source = state.diligence_results[0]
        evidence_ids = {
            evidence_id
            for finding in source.payload.findings
            for evidence_id in finding.evidence_refs
        }
        evidence = tuple(item for item in state.evidence if item.evidence_id in evidence_ids)
        return NativeProjectResult(
            source.payload, evidence, source.warnings, data_as_of=source.data_as_of
        )

    def _fixture_validation_errors(self, request: Project5NativeRequest) -> tuple[str, ...]:
        state = representative_deal_state()
        source = state.diligence_results[0].payload
        errors: list[str] = []
        if request.target_entity_id != source.target_entity_id:
            errors.append("fixture target entity does not match the requested target")
        if request.engagement_id != state.deal_context.engagement_id:
            errors.append("fixture engagement does not match the requested engagement")
        if request.vdr_document_ids != self.fixture_document_ids:
            errors.append("fixture VDR documents do not match the requested documents")
        return tuple(errors)
