"""Typed contracts for deterministic cross-project reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from ma_deal_intelligence.evidence import LineageGraph, ProjectId
from ma_deal_intelligence.finance import (
    DiligenceFindingReference,
    FinancialMetricReference,
    ValuationReference,
)
from ma_deal_intelligence.identity import DealContext
from ma_deal_intelligence.workflow import DealWarning, IssueSeverity


class ReconciliationIssueType(StrEnum):
    ENTITY_MISMATCH = "entity_mismatch"
    METRIC_CONFLICT = "metric_conflict"
    PERIOD_MISMATCH = "period_mismatch"
    BASIS_MISMATCH = "basis_mismatch"
    CURRENCY_MISMATCH = "currency_mismatch"
    STALE_RESULT = "stale_result"
    VALUATION_DIVERGENCE = "valuation_divergence"
    DILIGENCE_IMPACT = "diligence_impact"
    EVIDENCE_CONFLICT = "evidence_conflict"
    MISSING_DEPENDENCY = "missing_dependency"


class ReconciliationStatus(StrEnum):
    ALIGNED = "aligned"
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    REVIEW_REQUIRED = "review_required"
    STALE = "stale"
    SUPERSEDED = "superseded"
    NOT_COMPARABLE = "not_comparable"


class ImpactDirection(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    MIXED = "mixed"
    UNCERTAIN = "uncertain"


class ThesisPosition(StrEnum):
    SUPPORTS = "supports"
    CHALLENGES = "challenges"
    UNRESOLVED = "unresolved"


class ReviewPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReconciliationTraceType(StrEnum):
    INPUTS_COMPARED = "inputs_compared"
    COMPATIBILITY_CHECKED = "compatibility_checked"
    ISSUE_EMITTED = "issue_emitted"
    RESOLUTION_APPLIED = "resolution_applied"
    STALE_FLAG_SET = "stale_flag_set"
    RECOMPUTATION_REQUESTED = "recomputation_requested"
    INSIGHT_LINKED = "insight_linked"


@dataclass(frozen=True, slots=True)
class NumericTolerancePolicy:
    absolute: Decimal = Decimal("0.01")
    relative: Decimal = Decimal("0.001")
    valuation_divergence: Decimal = Decimal("0.10")

    def __post_init__(self) -> None:
        if min(self.absolute, self.relative, self.valuation_divergence) < 0:
            raise ValueError("numeric tolerances must be non-negative")


@dataclass(frozen=True, slots=True)
class CandidateResolution:
    action: str
    description: str
    requires_specialist_rerun: bool = False


@dataclass(frozen=True, slots=True)
class ReconciliationIssue:
    issue_id: str
    issue_type: ReconciliationIssueType
    subject_id: str
    affected_projects: tuple[ProjectId, ...]
    affected_output_ids: tuple[str, ...]
    severity: IssueSeverity
    blocking: bool
    description: str
    candidate_resolutions: tuple[CandidateResolution, ...]
    evidence_refs: tuple[str, ...]
    analyst_review_required: bool
    status: ReconciliationStatus


@dataclass(frozen=True, slots=True)
class EntityMatch:
    left_entity_id: str
    right_entity_id: str
    status: ReconciliationStatus
    normalized_names: tuple[str, str]
    matched_fields: tuple[str, ...] = ()
    ambiguity_reason: str | None = None


@dataclass(frozen=True, slots=True)
class UnifiedMetricView:
    metric_key: str
    metric_type: str
    entity_id: str | None
    observations: tuple[FinancialMetricReference, ...]
    status: ReconciliationStatus
    selected_metric_id: str | None = None
    issue_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StaleOutputReference:
    output_id: str
    status: ReconciliationStatus
    stale_for_scenarios: tuple[str, ...]
    reason: str
    changed_input_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RecomputeRequest:
    request_id: str
    source_output_id: str
    stale_because: str
    updated_input_ids: tuple[str, ...]
    target_capability: str
    priority: ReviewPriority
    analyst_approval_required: bool
    scenario_id: str


@dataclass(frozen=True, slots=True)
class UnifiedValuationEntry:
    valuation: ValuationReference
    stale_for_scenarios: tuple[str, ...] = ()
    source_warnings: tuple[DealWarning, ...] = ()


@dataclass(frozen=True, slots=True)
class ValuationComparison:
    entries: tuple[UnifiedValuationEntry, ...]
    midpoint_gap: Decimal | None
    midpoint_gap_percent: Decimal | None
    overlapping_ranges: bool | None
    issue_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DealImpactInsight:
    insight_id: str
    title: str
    category: str
    related_projects: tuple[ProjectId, ...]
    underlying_ids: tuple[str, ...]
    affected_output_ids: tuple[str, ...]
    qualitative_impact: str
    direction: ImpactDirection
    quantified_delta: Decimal | None = None
    quantified_delta_percent: Decimal | None = None
    evidence_refs: tuple[str, ...] = ()
    status: ReconciliationStatus = ReconciliationStatus.UNRESOLVED
    analyst_review_required: bool = False


@dataclass(frozen=True, slots=True)
class UnifiedRiskItem:
    risk_id: str
    title: str
    severity: IssueSeverity
    source_projects: tuple[ProjectId, ...]
    source_ids: tuple[str, ...]
    affected_areas: tuple[str, ...]
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RelatedInsightLink:
    source_id: str
    target_id: str
    relationship: str


@dataclass(frozen=True, slots=True)
class EvidenceLink:
    link_id: str
    evidence_ids: tuple[str, ...]
    shared_source_key: str
    relationship: str = "same_underlying_source"


@dataclass(frozen=True, slots=True)
class ThesisEvidence:
    item_id: str
    position: ThesisPosition
    description: str
    source_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OpenQuestion:
    question_id: str
    question: str
    source_projects: tuple[ProjectId, ...]
    related_ids: tuple[str, ...]
    blocking: bool = False


@dataclass(frozen=True, slots=True)
class AnalystReviewItem:
    review_id: str
    subject_id: str
    issue_ids: tuple[str, ...]
    priority: ReviewPriority
    reason: str
    affected_output_ids: tuple[str, ...]
    suggested_actions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MetricChoice:
    metric_type: str
    metric_id: str
    basis: str


@dataclass(frozen=True, slots=True)
class DealScenario:
    scenario_id: str
    name: str
    metric_choices: tuple[MetricChoice, ...]
    affected_output_ids: tuple[str, ...] = ()
    recomputation_request_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ScenarioComparison:
    scenarios: tuple[DealScenario, ...]
    differing_metric_ids: tuple[str, ...]
    stale_output_ids: tuple[str, ...]
    open_recomputation_request_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReconciliationTraceEvent:
    sequence: int
    event_type: ReconciliationTraceType
    subject_ids: tuple[str, ...]
    message: str


@dataclass(frozen=True, slots=True)
class UnifiedDealIntelligenceSnapshot:
    snapshot_id: str
    deal_context: DealContext
    company_fact_ids: tuple[str, ...]
    metrics: tuple[UnifiedMetricView, ...]
    valuation_comparison: ValuationComparison
    diligence_findings: tuple[DiligenceFindingReference, ...]
    risks: tuple[UnifiedRiskItem, ...]
    issues: tuple[ReconciliationIssue, ...]
    stale_outputs: tuple[StaleOutputReference, ...]
    recomputation_requests: tuple[RecomputeRequest, ...]
    impact_insights: tuple[DealImpactInsight, ...]
    related_insights: tuple[RelatedInsightLink, ...]
    evidence_links: tuple[EvidenceLink, ...]
    thesis_evidence: tuple[ThesisEvidence, ...]
    review_queue: tuple[AnalystReviewItem, ...]
    open_questions: tuple[OpenQuestion, ...]
    scenarios: ScenarioComparison
    evidence_refs: tuple[str, ...]
    lineage: LineageGraph
    warnings: tuple[DealWarning, ...]


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    snapshot: UnifiedDealIntelligenceSnapshot
    entity_matches: tuple[EntityMatch, ...]
    trace: tuple[ReconciliationTraceEvent, ...]
