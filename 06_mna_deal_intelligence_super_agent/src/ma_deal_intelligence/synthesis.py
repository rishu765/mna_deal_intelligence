"""Evidence-backed final deal synthesis built from canonical state only."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from ma_deal_intelligence.evidence import EvidenceReference, ProjectId
from ma_deal_intelligence.finance import (
    FinancialMetricReference,
    ValuationReference,
)
from ma_deal_intelligence.reconciliation_models import (
    ReconciliationResult,
    ReconciliationStatus,
    UnifiedDealIntelligenceSnapshot,
)
from ma_deal_intelligence.state import DealState
from ma_deal_intelligence.workflow import IssueSeverity


class DealAssessment(StrEnum):
    ATTRACTIVE = "attractive"
    ATTRACTIVE_WITH_CONDITIONS = "attractive_with_conditions"
    MIXED = "mixed"
    HIGH_RISK = "high_risk"
    INSUFFICIENT_INFORMATION = "insufficient_information"


class FinalOutputStatus(StrEnum):
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    PARTIALLY_COMPLETED = "partially_completed"
    INSUFFICIENT_INFORMATION = "insufficient_information"


@dataclass(frozen=True, slots=True)
class Citation:
    evidence_id: str
    label: str
    source_project: ProjectId


@dataclass(frozen=True, slots=True)
class SynthesisItem:
    item_id: str
    statement: str
    source_artifact_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...] = ()
    quantified: bool = False


@dataclass(frozen=True, slots=True)
class FinalSection:
    section_id: str
    title: str
    summary: str
    items: tuple[SynthesisItem, ...] = ()


@dataclass(frozen=True, slots=True)
class ValuationSynthesisEntry:
    valuation_id: str
    method: str
    low: Decimal
    midpoint: Decimal
    high: Decimal
    currency: str
    unit: str
    metric_basis: str
    source_project: ProjectId
    source_record_id: str
    evidence_refs: tuple[str, ...]
    stale_for_scenarios: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MetricSynthesisEntry:
    metric_id: str
    metric_type: str
    value: Decimal
    currency: str | None
    unit: str
    basis: str
    source_project: ProjectId
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AssessmentBasis:
    classification: DealAssessment
    policy_reasons: tuple[str, ...]
    unresolved_material_issue_count: int
    high_or_critical_risk_count: int
    missing_specialist_count: int


@dataclass(frozen=True, slots=True)
class FinalDealIntelligenceOutput:
    synthesis_id: str
    run_id: str
    deal_id: str
    as_of_date: date | None
    status: FinalOutputStatus
    assessment: AssessmentBasis
    executive_summary: str
    sections: tuple[FinalSection, ...]
    valuations: tuple[ValuationSynthesisEntry, ...]
    material_metrics: tuple[MetricSynthesisEntry, ...]
    citations: tuple[Citation, ...]
    evidence_refs: tuple[str, ...]
    assumption_ids: tuple[str, ...]
    warning_ids: tuple[str, ...]
    error_ids: tuple[str, ...]
    lineage_source_ids: tuple[str, ...]
    schema_version: str = "1.0.0"


class NarrativeProvider(Protocol):
    """Optional bounded narrative provider; structured output remains authoritative."""

    def draft(self, structured_summary: str) -> str: ...


class SynthesisValidationError(ValueError):
    """Raised when synthesis is inconsistent with canonical specialist values."""


class CitationRenderer:
    @staticmethod
    def render(item: EvidenceReference) -> Citation:
        source = item.source_project.value.replace("project_", "Project ")
        title = item.document_title or item.document_id or item.source_record_id or item.evidence_id
        locator: list[str] = []
        if item.page_numbers:
            locator.append("p." + ",".join(str(page) for page in item.page_numbers))
        if item.section:
            locator.append(f"Section {item.section}")
        if item.sheet_name:
            locator.append(f"Sheet: {item.sheet_name}")
        if item.cell_range:
            locator.append(item.cell_range)
        if item.row:
            locator.append(f"Row {item.row}")
        if item.chunk_id:
            locator.append(f"Chunk {item.chunk_id}")
        parts = [source, title, *locator]
        return Citation(item.evidence_id, "[" + " | ".join(parts) + "]", item.source_project)


class SynthesisGuard:
    _NUMBER = re.compile(r"(?<![A-Za-z:])[-+]?\d+(?:[,.]\d+)*(?:\.\d+)?%?")
    _WORD = re.compile(r"[A-Za-z][A-Za-z0-9_-]{3,}")
    _CONNECTIVES = {
        "analysis",
        "assessment",
        "available",
        "based",
        "deal",
        "evidence",
        "indicates",
        "overall",
        "remains",
        "shows",
        "summary",
        "with",
    }

    @classmethod
    def validate_numeric_mentions(cls, narrative: str, allowed_values: tuple[Decimal, ...]) -> None:
        allowed = {cls._normalize_number(str(value)) for value in allowed_values}
        unsupported = {
            cls._normalize_number(token.rstrip("%"))
            for token in cls._NUMBER.findall(narrative)
            if cls._normalize_number(token.rstrip("%")) not in allowed
        }
        if unsupported:
            raise SynthesisValidationError(
                "narrative introduced unsupported numeric values: " + ", ".join(sorted(unsupported))
            )

    @classmethod
    def validate_grounded_narrative(
        cls,
        narrative: str,
        source_text: str,
        allowed_values: tuple[Decimal, ...],
    ) -> None:
        cls.validate_numeric_mentions(narrative, allowed_values)
        source_words = {item.casefold() for item in cls._WORD.findall(source_text)}
        candidate_words = {item.casefold() for item in cls._WORD.findall(narrative)}
        unsupported = candidate_words - source_words - cls._CONNECTIVES
        if unsupported:
            raise SynthesisValidationError(
                "narrative introduced unsupported terms: " + ", ".join(sorted(unsupported))
            )

    @staticmethod
    def _normalize_number(value: str) -> str:
        cleaned = value.replace(",", "")
        try:
            return str(Decimal(cleaned).normalize())
        except Exception:
            return cleaned


class SynthesisService:
    """Build final decision support without recalculating specialist finance."""

    _MATERIAL_METRICS = ("ebitda", "working capital", "net debt", "customer concentration")

    def build(
        self,
        *,
        run_id: str,
        deal_state: DealState,
        reconciliation: ReconciliationResult,
        completed_capabilities: tuple[str, ...],
        failed_capabilities: tuple[str, ...] = (),
        orchestration_warnings: tuple[str, ...] = (),
        narrative_provider: NarrativeProvider | None = None,
    ) -> FinalDealIntelligenceOutput:
        snapshot = reconciliation.snapshot
        valuations = tuple(
            self._valuation_entry(item, snapshot) for item in deal_state.valuation_outputs
        )
        material_metrics = tuple(
            self._metric_entry(item)
            for item in deal_state.financial_metrics
            if any(key in item.metric_type.casefold() for key in self._MATERIAL_METRICS)
        )
        sections = self._sections(deal_state, reconciliation, valuations, material_metrics)
        assessment = self._assessment(
            deal_state, reconciliation, completed_capabilities, failed_capabilities
        )
        status = self._status(deal_state, assessment, failed_capabilities, orchestration_warnings)
        target = self._target_name(deal_state)
        summary = self._executive_summary(target, assessment, valuations, reconciliation)
        allowed_values = tuple(
            value for entry in valuations for value in (entry.low, entry.midpoint, entry.high)
        ) + tuple(item.value for item in material_metrics)
        if narrative_provider is not None:
            candidate = narrative_provider.draft(summary)
            SynthesisGuard.validate_grounded_narrative(candidate, summary, allowed_values)
            summary = candidate
        known_evidence_ids = {item.evidence_id for item in deal_state.evidence}
        evidence_ids = tuple(
            dict.fromkeys(
                evidence_id
                for section in sections
                for item in section.items
                for evidence_id in item.evidence_refs
                if evidence_id in known_evidence_ids
            )
        )
        evidence_by_id = {item.evidence_id: item for item in deal_state.evidence}
        citations = tuple(
            CitationRenderer.render(evidence_by_id[evidence_id])
            for evidence_id in evidence_ids
            if evidence_id in evidence_by_id
        )
        output = FinalDealIntelligenceOutput(
            f"synthesis:{run_id}",
            run_id,
            deal_state.deal_context.deal_id,
            deal_state.deal_context.as_of_date,
            status,
            assessment,
            summary,
            sections,
            valuations,
            material_metrics,
            citations,
            evidence_ids,
            tuple(item.assumption_id for item in deal_state.assumptions),
            tuple(item.warning_id for item in deal_state.warnings),
            tuple(item.error_id for item in deal_state.errors),
            tuple(
                dict.fromkeys(
                    source_id
                    for section in sections
                    for item in section.items
                    for source_id in item.source_artifact_ids
                )
            ),
        )
        self.validate(output, deal_state)
        return output

    @staticmethod
    def validate(output: FinalDealIntelligenceOutput, state: DealState) -> None:
        valuations = {item.valuation_id: item for item in state.valuation_outputs}
        for valuation_item in output.valuations:
            valuation_source = valuations.get(valuation_item.valuation_id)
            if valuation_source is None or (
                valuation_item.low,
                valuation_item.midpoint,
                valuation_item.high,
            ) != (
                valuation_source.low,
                valuation_source.midpoint,
                valuation_source.high,
            ):
                raise SynthesisValidationError(f"valuation mismatch: {valuation_item.valuation_id}")
        metrics = {item.metric_id: item for item in state.financial_metrics}
        for metric_item in output.material_metrics:
            metric_source = metrics.get(metric_item.metric_id)
            if metric_source is None or metric_item.value != metric_source.value:
                raise SynthesisValidationError(f"metric mismatch: {metric_item.metric_id}")
        known_evidence = {item.evidence_id for item in state.evidence}
        if set(output.evidence_refs) - known_evidence:
            raise SynthesisValidationError("synthesis references unknown evidence")

    def _sections(
        self,
        state: DealState,
        reconciliation: ReconciliationResult,
        valuations: tuple[ValuationSynthesisEntry, ...],
        metrics: tuple[MetricSynthesisEntry, ...],
    ) -> tuple[FinalSection, ...]:
        snapshot = reconciliation.snapshot
        context = state.deal_context
        rationale = context.strategic_rationale or (
            (context.transaction_thesis,) if context.transaction_thesis else ()
        )
        company_items = tuple(
            SynthesisItem(
                f"company:{index}",
                result.payload.summary
                or f"Company intelligence output {result.payload.source_document_ids}",
                (result.payload.research_profile_id or result.run_id,),
                result.evidence_refs,
            )
            for index, result in enumerate(state.company_intelligence, 1)
        )
        screening_items = tuple(
            SynthesisItem(
                f"screen:{candidate.entity.canonical_entity_id}",
                (
                    f"Rank {candidate.rank}; score {candidate.score}; "
                    f"{candidate.rationale or candidate.eligibility}."
                ),
                (result.run_id, candidate.entity.canonical_entity_id),
                candidate.evidence_refs,
            )
            for result in state.target_screening_results
            for candidate in result.payload.candidates
        )
        valuation_items = tuple(
            SynthesisItem(
                f"valuation:{item.valuation_id}",
                (
                    f"{item.method}: {item.low} to {item.high} {item.currency} {item.unit}; "
                    f"midpoint {item.midpoint}; basis {item.metric_basis}."
                ),
                (item.valuation_id, item.source_record_id),
                item.evidence_refs,
                True,
            )
            for item in valuations
        )
        finding_items = tuple(
            SynthesisItem(
                f"finding:{item.finding_id}",
                f"{item.title} ({item.severity.value}; {item.status.value}): {item.materiality}",
                (item.finding_id, item.source_record_id),
                item.evidence_refs,
            )
            for item in snapshot.diligence_findings
        )
        issue_items = tuple(
            SynthesisItem(
                f"issue:{item.issue_id}",
                item.description,
                (item.issue_id, *item.affected_output_ids),
                item.evidence_refs,
            )
            for item in snapshot.issues
        )
        risk_items = tuple(
            SynthesisItem(
                f"risk:{item.risk_id}",
                f"{item.title} ({item.severity.value}).",
                (item.risk_id, *item.source_ids),
                item.evidence_refs,
            )
            for item in snapshot.risks
        )
        impact_items = tuple(
            SynthesisItem(
                f"impact:{item.insight_id}",
                item.qualitative_impact,
                (item.insight_id, *item.underlying_ids, *item.affected_output_ids),
                item.evidence_refs,
                item.quantified_delta is not None,
            )
            for item in snapshot.impact_insights
        )
        decision_items = tuple(
            SynthesisItem(
                f"decision:{item.decision_id}",
                f"{item.action.value}: {item.rationale}",
                (item.decision_id, item.subject_id),
            )
            for item in state.analyst_decisions
        )
        question_items = tuple(
            SynthesisItem(
                f"question:{item.question_id}",
                item.question,
                (item.question_id, *item.related_ids),
            )
            for item in snapshot.open_questions
        )
        scenario_items = tuple(
            SynthesisItem(
                f"scenario:{item.scenario_id}",
                f"{item.name}: " + ", ".join(choice.basis for choice in item.metric_choices),
                (item.scenario_id, *item.affected_output_ids),
            )
            for item in snapshot.scenarios.scenarios
        )
        assumptions = tuple(
            SynthesisItem(
                f"assumption:{item.assumption_id}",
                item.description,
                (item.assumption_id,),
                item.evidence_refs,
            )
            for item in state.assumptions
        )
        sections = (
            FinalSection("deal_overview", "Deal Overview", self._target_name(state)),
            FinalSection(
                "strategic_rationale",
                "Strategic Rationale",
                "Stated thesis and evidence are retained separately.",
                tuple(
                    SynthesisItem(f"rationale:{i}", text, (context.deal_id,))
                    for i, text in enumerate(rationale, 1)
                ),
            ),
            FinalSection(
                "company_intelligence",
                "Company Intelligence",
                self._coverage(company_items),
                company_items,
            ),
            FinalSection(
                "target_screening",
                "Target Screening Context",
                self._coverage(
                    screening_items, "Target was specified; Project 2 was not required."
                ),
                screening_items,
            ),
            FinalSection(
                "trading_comps",
                "Trading Comps",
                "Project 3 values are preserved exactly.",
                tuple(item for item in valuation_items if "trading" in item.statement),
            ),
            FinalSection(
                "precedents",
                "Precedent Transactions",
                "Project 4 values are preserved exactly.",
                tuple(item for item in valuation_items if "precedent" in item.statement),
            ),
            FinalSection(
                "due_diligence", "Due Diligence", self._coverage(finding_items), finding_items
            ),
            FinalSection(
                "unified_valuation",
                "Unified Valuation View",
                "Methods are shown side by side and are not blended.",
                valuation_items,
            ),
            FinalSection("scenarios", "Scenarios", self._coverage(scenario_items), scenario_items),
            FinalSection(
                "reconciliation",
                "Cross-Project Reconciliation Issues",
                self._coverage(issue_items),
                issue_items,
            ),
            FinalSection(
                "diligence_implications",
                "Diligence-to-Valuation Implications",
                self._coverage(impact_items),
                impact_items,
            ),
            FinalSection("key_risks", "Key Risks", self._coverage(risk_items), risk_items),
            FinalSection(
                "analyst_decisions",
                "Analyst Decisions",
                self._coverage(decision_items),
                decision_items,
            ),
            FinalSection(
                "open_questions", "Open Questions", self._coverage(question_items), question_items
            ),
            FinalSection("assumptions", "Assumptions", self._coverage(assumptions), assumptions),
            FinalSection(
                "limitations",
                "Limitations",
                (
                    "Decision support from available specialist outputs; unresolved issues remain "
                    "explicit and this is not investment advice."
                ),
            ),
        )
        del metrics
        return sections

    @staticmethod
    def _valuation_entry(
        item: ValuationReference, reconciliation: UnifiedDealIntelligenceSnapshot
    ) -> ValuationSynthesisEntry:
        stale = next(
            (
                entry.stale_for_scenarios
                for entry in reconciliation.valuation_comparison.entries
                if entry.valuation.valuation_id == item.valuation_id
            ),
            (),
        )
        return ValuationSynthesisEntry(
            item.valuation_id,
            item.method.value,
            item.low,
            item.midpoint,
            item.high,
            item.currency,
            item.unit,
            item.metric_basis,
            item.source_project,
            item.source_record_id,
            item.evidence_refs,
            stale,
        )

    @staticmethod
    def _metric_entry(item: FinancialMetricReference) -> MetricSynthesisEntry:
        return MetricSynthesisEntry(
            item.metric_id,
            item.metric_type,
            item.value,
            item.currency,
            item.unit,
            item.basis.value,
            item.source_project,
            item.evidence_refs,
        )

    @staticmethod
    def _target_name(state: DealState) -> str:
        target_id = state.deal_context.target_entity_id
        entity = next(
            (item for item in state.entities if item.canonical_entity_id == target_id), None
        )
        if entity is not None:
            return entity.display_name or entity.legal_name or entity.canonical_entity_id
        return target_id or "Target not specified"

    @staticmethod
    def _coverage(
        items: tuple[SynthesisItem, ...],
        empty: str = "No specialist output was available for this section.",
    ) -> str:
        return f"{len(items)} structured item(s)." if items else empty

    @staticmethod
    def _status(
        state: DealState,
        assessment: AssessmentBasis,
        failed: tuple[str, ...],
        warnings: tuple[str, ...],
    ) -> FinalOutputStatus:
        if assessment.classification is DealAssessment.INSUFFICIENT_INFORMATION:
            return FinalOutputStatus.INSUFFICIENT_INFORMATION
        if failed:
            return FinalOutputStatus.PARTIALLY_COMPLETED
        if state.warnings or state.errors or warnings:
            return FinalOutputStatus.COMPLETED_WITH_WARNINGS
        return FinalOutputStatus.COMPLETED

    @staticmethod
    def _assessment(
        state: DealState,
        reconciliation: ReconciliationResult,
        completed: tuple[str, ...],
        failed: tuple[str, ...],
    ) -> AssessmentBasis:
        snapshot = reconciliation.snapshot
        unresolved = tuple(
            item
            for item in snapshot.issues
            if item.status
            in {
                ReconciliationStatus.UNRESOLVED,
                ReconciliationStatus.REVIEW_REQUIRED,
                ReconciliationStatus.STALE,
            }
        )
        high_risks = tuple(
            item
            for item in snapshot.risks
            if item.severity in {IssueSeverity.HIGH, IssueSeverity.CRITICAL}
        )
        required_domains = bool(completed)
        reasons: list[str] = []
        if not required_domains or not state.entities:
            classification = DealAssessment.INSUFFICIENT_INFORMATION
            reasons.append("No complete specialist basis or target identity is available.")
        elif any(item.severity is IssueSeverity.CRITICAL for item in snapshot.risks):
            classification = DealAssessment.HIGH_RISK
            reasons.append("At least one critical structured risk remains.")
        elif high_risks and unresolved:
            classification = DealAssessment.HIGH_RISK
            reasons.append("High-severity risk and unresolved reconciliation issues coexist.")
        elif unresolved or failed or high_risks:
            classification = DealAssessment.ATTRACTIVE_WITH_CONDITIONS
            reasons.append("The available analysis requires explicit conditions or further work.")
        elif snapshot.thesis_evidence and all(
            item.position.value == "supports" for item in snapshot.thesis_evidence
        ):
            classification = DealAssessment.ATTRACTIVE
            reasons.append(
                "Structured thesis evidence is supportive and no material unresolved risk remains."
            )
        else:
            classification = DealAssessment.MIXED
            reasons.append(
                "Available structured evidence is mixed or does not establish an attractive case."
            )
        if failed:
            reasons.append(f"{len(failed)} selected specialist capability failed.")
        return AssessmentBasis(
            classification, tuple(reasons), len(unresolved), len(high_risks), len(failed)
        )

    @staticmethod
    def _executive_summary(
        target: str,
        assessment: AssessmentBasis,
        valuations: tuple[ValuationSynthesisEntry, ...],
        reconciliation: ReconciliationResult,
    ) -> str:
        methods = (
            "; ".join(
                f"{item.method} {item.low} to {item.high} {item.currency} {item.unit}"
                for item in valuations
            )
            or "no valuation output"
        )
        return (
            f"{target}: {assessment.classification.value.replace('_', ' ')}. "
            f"Valuation methods: {methods}. "
            f"The analysis retains {len(reconciliation.snapshot.issues)} reconciliation issue(s), "
            f"{len(reconciliation.snapshot.risks)} risk item(s), and "
            f"{len(reconciliation.snapshot.open_questions)} open question(s)."
        )
