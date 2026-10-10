"""Project 2 target sourcing and screening adapter."""

from __future__ import annotations

from dataclasses import dataclass

from ma_deal_intelligence.adapters.base import BaseAdapter, NativeProjectResult
from ma_deal_intelligence.contracts import (
    CapabilityId,
    ExecutionNature,
    ProjectCapability,
    SchemaReference,
    TargetScreeningRequest,
)
from ma_deal_intelligence.evidence import EvidenceKind, EvidenceReference, ProjectId
from ma_deal_intelligence.identity import CanonicalEntityReference
from ma_deal_intelligence.outputs import TargetCandidateReference, TargetScreeningOutput


@dataclass(frozen=True, slots=True)
class Project2NativeRequest:
    thesis_id: str
    buyer_entity_id: str | None
    sectors: tuple[str, ...]
    geographies: tuple[str, ...]


class Project2Adapter(
    BaseAdapter[TargetScreeningRequest, Project2NativeRequest, TargetScreeningOutput]
):
    project_id = ProjectId.PROJECT_2
    supported_capabilities = (
        ProjectCapability(
            CapabilityId.P2_SOURCE_TARGETS,
            project_id,
            "Target sourcing",
            "Use Project 2 discovery, enrichment, and sourcing services.",
            SchemaReference("ma_deal_intelligence.contracts", "TargetScreeningRequest", "1.0.0"),
            SchemaReference("ma_deal_intelligence.outputs", "TargetScreeningOutput", "1.0.0"),
            execution_nature=ExecutionNature.HYBRID,
            required_inputs=("acquisition_criteria",),
            produced_outputs=("target_candidates",),
        ),
        ProjectCapability(
            CapabilityId.P2_SCREEN_TARGETS,
            project_id,
            "Target screening and ranking",
            "Use Project 2 deterministic screening and strategic-fit ranking.",
            SchemaReference("ma_deal_intelligence.contracts", "TargetScreeningRequest", "1.0.0"),
            SchemaReference("ma_deal_intelligence.outputs", "TargetScreeningOutput", "1.0.0"),
            execution_nature=ExecutionNature.HYBRID,
            required_inputs=("acquisition_criteria",),
            produced_outputs=("screened_targets", "target_candidates"),
        ),
    )

    def _validation_errors(self, request: TargetScreeningRequest) -> tuple[str, ...]:
        errors: list[str] = []
        if not request.acquisition_criteria_id.strip():
            errors.append("acquisition criteria ID is required")
        if not request.deal_context.sectors and not request.deal_context.geographies:
            errors.append("acquisition criteria require a sector or geography")
        return tuple(errors)

    def translate_input(self, request: TargetScreeningRequest) -> Project2NativeRequest:
        return Project2NativeRequest(
            request.acquisition_criteria_id,
            request.deal_context.buyer_entity_id,
            request.deal_context.sectors,
            request.deal_context.geographies,
        )

    def fixture_result(
        self, request: Project2NativeRequest
    ) -> NativeProjectResult[TargetScreeningOutput]:
        sector = request.sectors[0] if request.sectors else "B2B software"
        geography = request.geographies[0] if request.geographies else "India"
        evidence = EvidenceReference(
            f"p2:evidence:{request.thesis_id}:1",
            ProjectId.PROJECT_2,
            EvidenceKind.DATASET,
            source_record_id="p2:fixture:candidate:1",
            excerpt=f"Candidate observed in the {sector} universe for {geography}.",
            project_evidence_id="discovery:fixture:1",
        )
        entity = CanonicalEntityReference(
            f"entity:fixture-{sector.casefold().replace(' ', '-')}",
            legal_name=f"Fixture {sector} Technologies Private Limited",
            display_name=f"Fixture {sector} Tech",
            country=geography,
            sector=sector,
            source_projects=(ProjectId.PROJECT_2,),
            evidence_refs=(evidence.evidence_id,),
        )
        candidate = TargetCandidateReference(
            entity,
            1,
            "91.5",
            "eligible",
            "Matches the requested sector and geography with strong strategic fit.",
            (evidence.evidence_id,),
        )
        return NativeProjectResult(
            TargetScreeningOutput(request.thesis_id, (candidate,), "Fixture target shortlist"),
            (evidence,),
        )
