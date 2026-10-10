"""Project 1 company and document intelligence adapter."""

from __future__ import annotations

from dataclasses import dataclass

from ma_deal_intelligence.adapters.base import BaseAdapter, NativeProjectResult
from ma_deal_intelligence.contracts import (
    CapabilityId,
    DocumentIntelligenceRequest,
    ExecutionNature,
    ProjectCapability,
    SchemaReference,
)
from ma_deal_intelligence.evidence import EvidenceKind, EvidenceReference, ProjectId
from ma_deal_intelligence.outputs import CompanyIntelligenceOutput


@dataclass(frozen=True, slots=True)
class Project1NativeRequest:
    entity_id: str
    company_name: str | None
    document_ids: tuple[str, ...]
    question: str | None


class Project1Adapter(
    BaseAdapter[DocumentIntelligenceRequest, Project1NativeRequest, CompanyIntelligenceOutput]
):
    project_id = ProjectId.PROJECT_1
    supported_capabilities = (
        ProjectCapability(
            CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE,
            project_id,
            "Company intelligence",
            "Use Project 1 research over indexed company documents.",
            SchemaReference(
                "ma_deal_intelligence.contracts", "DocumentIntelligenceRequest", "1.0.0"
            ),
            SchemaReference("ma_deal_intelligence.outputs", "CompanyIntelligenceOutput", "1.0.0"),
            execution_nature=ExecutionNature.AI_ASSISTED,
            required_inputs=("target_entity", "documents"),
            produced_outputs=("company_intelligence", "target_financials", "sector_context"),
        ),
        ProjectCapability(
            CapabilityId.P1_PROVIDE_CITED_ANSWERS,
            project_id,
            "Cited company question answering",
            "Use Project 1 grounded RAG answer service.",
            SchemaReference(
                "ma_deal_intelligence.contracts", "DocumentIntelligenceRequest", "1.0.0"
            ),
            SchemaReference("ma_deal_intelligence.outputs", "CompanyIntelligenceOutput", "1.0.0"),
            execution_nature=ExecutionNature.AI_ASSISTED,
            required_inputs=("target_entity", "documents", "question"),
            produced_outputs=("cited_answer",),
        ),
    )

    def _validation_errors(self, request: DocumentIntelligenceRequest) -> tuple[str, ...]:
        errors: list[str] = []
        if not request.entity_id.strip():
            errors.append("entity identity is required")
        if not request.document_ids:
            errors.append("at least one indexed document is required")
        return tuple(errors)

    def translate_input(self, request: DocumentIntelligenceRequest) -> Project1NativeRequest:
        company_name = request.entity_id
        return Project1NativeRequest(
            request.entity_id, company_name, request.document_ids, request.question
        )

    def fixture_result(
        self, request: Project1NativeRequest
    ) -> NativeProjectResult[CompanyIntelligenceOutput]:
        evidence = tuple(
            EvidenceReference(
                f"p1:{document_id}:fixture",
                ProjectId.PROJECT_1,
                EvidenceKind.DOCUMENT,
                document_id=document_id,
                section="Company overview",
                chunk_id=f"{document_id}:chunk:1",
                excerpt=f"Fixture company intelligence for {request.company_name}.",
                project_evidence_id="1",
            )
            for document_id in request.document_ids
        )
        payload = CompanyIntelligenceOutput(
            request.entity_id,
            request.document_ids,
            f"p1:profile:{request.entity_id}",
            (f"p1:answer:{request.entity_id}",) if request.question else (),
            (f"p1:metric:{request.entity_id}:ebitda",),
            f"Fixture Project 1 profile for {request.company_name}.",
        )
        return NativeProjectResult(payload, evidence)
