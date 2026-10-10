"""Canonical shared deal state owned by Project 6."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ma_deal_intelligence.evidence import EvidenceReference, LineageGraph, ProjectId
from ma_deal_intelligence.finance import (
    DiligenceFindingReference,
    FinancialMetricReference,
    MetricConflict,
    ValuationReference,
)
from ma_deal_intelligence.identity import CanonicalEntityReference, DealContext
from ma_deal_intelligence.outputs import (
    CompanyIntelligenceOutput,
    DiligenceOutput,
    PrecedentTransactionsOutput,
    ProjectResultEnvelope,
    TargetScreeningOutput,
    TradingCompsOutput,
)
from ma_deal_intelligence.workflow import (
    AnalystDecision,
    ArtifactVersion,
    Assumption,
    CapabilityExecution,
    DealError,
    DealWarning,
    DependencyRequirement,
    WorkflowStatus,
)

DEAL_STATE_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class SourceDocumentReference:
    document_id: str
    source_project: ProjectId
    title: str | None = None
    checksum_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class DealState:
    deal_context: DealContext
    entities: tuple[CanonicalEntityReference, ...] = ()
    source_documents: tuple[SourceDocumentReference, ...] = ()
    company_intelligence: tuple[ProjectResultEnvelope[CompanyIntelligenceOutput], ...] = ()
    target_screening_results: tuple[ProjectResultEnvelope[TargetScreeningOutput], ...] = ()
    trading_comps_results: tuple[ProjectResultEnvelope[TradingCompsOutput], ...] = ()
    precedent_transaction_results: tuple[
        ProjectResultEnvelope[PrecedentTransactionsOutput], ...
    ] = ()
    diligence_results: tuple[ProjectResultEnvelope[DiligenceOutput], ...] = ()
    financial_metrics: tuple[FinancialMetricReference, ...] = ()
    valuation_outputs: tuple[ValuationReference, ...] = ()
    diligence_findings: tuple[DiligenceFindingReference, ...] = ()
    metric_conflicts: tuple[MetricConflict, ...] = ()
    evidence: tuple[EvidenceReference, ...] = ()
    lineage: LineageGraph = LineageGraph()
    analyst_decisions: tuple[AnalystDecision, ...] = ()
    assumptions: tuple[Assumption, ...] = ()
    warnings: tuple[DealWarning, ...] = ()
    errors: tuple[DealError, ...] = ()
    workflow_status: WorkflowStatus = WorkflowStatus.CREATED
    capability_executions: tuple[CapabilityExecution, ...] = ()
    completed_capabilities: tuple[str, ...] = ()
    pending_capabilities: tuple[str, ...] = ()
    dependencies: tuple[DependencyRequirement, ...] = ()
    artifact_versions: tuple[ArtifactVersion, ...] = ()
    schema_version: str = DEAL_STATE_SCHEMA_VERSION
    revision: int = 1
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.revision < 1:
            raise ValueError("state revision must be positive")
        if self.schema_version != DEAL_STATE_SCHEMA_VERSION:
            raise ValueError(f"unsupported DealState schema version: {self.schema_version}")
        entity_ids = tuple(entity.canonical_entity_id for entity in self.entities)
        if len(entity_ids) != len(set(entity_ids)):
            raise ValueError("canonical entity IDs must be unique")
        evidence_ids = tuple(item.evidence_id for item in self.evidence)
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("evidence IDs must be unique")
        if self.updated_at is not None and (
            self.updated_at.tzinfo is None or self.updated_at.utcoffset() is None
        ):
            raise ValueError("updated_at must be timezone-aware")

    @property
    def requires_analyst_review(self) -> bool:
        return self.workflow_status is WorkflowStatus.REVIEW_REQUIRED or any(
            conflict.requires_analyst_review and conflict.resolved_by_decision_id is None
            for conflict in self.metric_conflicts
        )
