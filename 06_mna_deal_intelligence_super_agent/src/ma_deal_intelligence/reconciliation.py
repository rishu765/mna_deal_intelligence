"""Deterministic reconciliation across specialist-owned deal outputs."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import replace
from decimal import Decimal
from hashlib import sha256
from itertools import combinations

from ma_deal_intelligence.contracts import CapabilityId
from ma_deal_intelligence.evidence import EvidenceReference, ProjectId
from ma_deal_intelligence.finance import (
    FinancialMetricReference,
    FindingSeverity,
    MetricBasis,
    ValuationReference,
)
from ma_deal_intelligence.identity import CanonicalEntityReference
from ma_deal_intelligence.reconciliation_models import (
    AnalystReviewItem,
    CandidateResolution,
    DealImpactInsight,
    DealScenario,
    EntityMatch,
    EvidenceLink,
    ImpactDirection,
    MetricChoice,
    NumericTolerancePolicy,
    OpenQuestion,
    RecomputeRequest,
    ReconciliationIssue,
    ReconciliationIssueType,
    ReconciliationResult,
    ReconciliationStatus,
    ReconciliationTraceEvent,
    ReconciliationTraceType,
    RelatedInsightLink,
    ReviewPriority,
    ScenarioComparison,
    StaleOutputReference,
    ThesisEvidence,
    ThesisPosition,
    UnifiedDealIntelligenceSnapshot,
    UnifiedMetricView,
    UnifiedRiskItem,
    UnifiedValuationEntry,
    ValuationComparison,
)
from ma_deal_intelligence.state import DealState
from ma_deal_intelligence.workflow import (
    AnalystDecision,
    ArtifactVersion,
    DealWarning,
    DecisionAction,
    IssueSeverity,
)

_UNIT_SCALE = {
    "unit": Decimal("1"),
    "units": Decimal("1"),
    "ones": Decimal("1"),
    "thousand": Decimal("1000"),
    "thousands": Decimal("1000"),
    "million": Decimal("1000000"),
    "millions": Decimal("1000000"),
    "billion": Decimal("1000000000"),
    "billions": Decimal("1000000000"),
    "%": Decimal("1"),
    "percent": Decimal("1"),
}
_LEGAL_SUFFIXES = {
    "limited",
    "ltd",
    "plc",
    "inc",
    "incorporated",
    "corp",
    "corporation",
    "llc",
    "private",
}


class ReconciliationService:
    """Build a read-only unified view while preserving every specialist observation."""

    def __init__(self, tolerance: NumericTolerancePolicy | None = None) -> None:
        self.tolerance = tolerance or NumericTolerancePolicy()

    def reconcile(self, state: DealState) -> ReconciliationResult:
        trace: list[ReconciliationTraceEvent] = []
        issues: list[ReconciliationIssue] = []
        self._validate_envelopes(state, issues, trace)
        entity_matches = self._reconcile_entities(state.entities, issues, trace)
        metric_views = self._reconcile_metrics(state.financial_metrics, issues, trace)
        stale, recomputations = self._detect_staleness(state, issues, trace)
        valuation_comparison = self._compare_valuations(
            state.valuation_outputs, state.warnings, stale, issues, trace
        )
        insights, links = self._link_diligence(state, stale, issues, trace)
        issues, metric_views = self._apply_analyst_decisions(
            issues, metric_views, state.analyst_decisions, trace
        )
        risks = self._build_risks(state, issues)
        thesis = self._build_thesis_view(state, insights)
        questions = self._build_open_questions(state, issues)
        review_queue = self._build_review_queue(issues)
        scenarios = self._build_scenarios(state, stale, recomputations)
        evidence_links = reconcile_evidence(state.evidence)
        warnings = _cross_project_warnings(state, issues, stale)
        for view in metric_views:
            if view.status is ReconciliationStatus.ALIGNED and len(view.observations) > 1:
                _trace(
                    trace,
                    ReconciliationTraceType.RESOLUTION_APPLIED,
                    tuple(item.metric_id for item in view.observations),
                    "Equivalent observations aligned without changing source records.",
                )
        for issue in issues:
            _trace(
                trace,
                ReconciliationTraceType.ISSUE_EMITTED,
                (issue.issue_id, *issue.affected_output_ids),
                issue.description,
            )
        snapshot = UnifiedDealIntelligenceSnapshot(
            f"snapshot:{state.deal_context.deal_id}:r{state.revision}",
            state.deal_context,
            tuple(
                metric_id
                for result in state.company_intelligence
                for metric_id in result.payload.financial_metric_ids
            ),
            metric_views,
            valuation_comparison,
            state.diligence_findings,
            risks,
            tuple(issues),
            stale,
            recomputations,
            insights,
            links,
            evidence_links,
            thesis,
            review_queue,
            questions,
            scenarios,
            tuple(item.evidence_id for item in state.evidence),
            state.lineage,
            tuple(dict.fromkeys((*state.warnings, *warnings))),
        )
        return ReconciliationResult(snapshot, entity_matches, tuple(trace))

    def _apply_analyst_decisions(
        self,
        issues: list[ReconciliationIssue],
        metric_views: tuple[UnifiedMetricView, ...],
        decisions: tuple[AnalystDecision, ...],
        trace: list[ReconciliationTraceEvent],
    ) -> tuple[list[ReconciliationIssue], tuple[UnifiedMetricView, ...]]:
        resolving_actions = {
            DecisionAction.APPROVE,
            DecisionAction.RESOLVE,
            DecisionAction.SELECT,
        }
        resolved_issue_ids: set[str] = set()
        selected_metrics: dict[str, str] = {}
        updated_issues: list[ReconciliationIssue] = []
        for issue in issues:
            decision = next(
                (
                    item
                    for item in decisions
                    if item.action in resolving_actions
                    and item.subject_id in {issue.issue_id, issue.subject_id}
                ),
                None,
            )
            if decision is None:
                updated_issues.append(issue)
                continue
            updated_issues.append(
                replace(
                    issue,
                    status=ReconciliationStatus.RESOLVED,
                    analyst_review_required=False,
                )
            )
            resolved_issue_ids.add(issue.issue_id)
            if decision.selected_value:
                selected_metrics[issue.issue_id] = decision.selected_value
            _trace(
                trace,
                ReconciliationTraceType.RESOLUTION_APPLIED,
                (issue.issue_id, decision.decision_id),
                "An explicit analyst decision resolved the issue.",
            )
        updated_views: list[UnifiedMetricView] = []
        for view in metric_views:
            if view.issue_ids and set(view.issue_ids) <= resolved_issue_ids:
                selected = next(
                    (
                        selected_metrics[issue_id]
                        for issue_id in view.issue_ids
                        if selected_metrics.get(issue_id)
                        in {item.metric_id for item in view.observations}
                    ),
                    None,
                )
                updated_views.append(
                    replace(
                        view,
                        status=ReconciliationStatus.RESOLVED,
                        selected_metric_id=selected,
                    )
                )
            else:
                updated_views.append(view)
        return updated_issues, tuple(updated_views)

    def apply_staleness(self, state: DealState, result: ReconciliationResult) -> DealState:
        """Return state with stale metadata only; specialist values remain unchanged."""
        stale_by_id = {
            item.output_id: item
            for item in result.snapshot.stale_outputs
            if item.status is ReconciliationStatus.STALE
        }
        versions: list[ArtifactVersion] = []
        known_version_ids = {item.artifact_id for item in state.artifact_versions}
        for version in state.artifact_versions:
            stale = stale_by_id.get(version.artifact_id)
            versions.append(
                replace(version, stale=True, stale_reason=stale.reason) if stale else version
            )
        for output_id, stale in stale_by_id.items():
            if output_id not in known_version_ids:
                versions.append(
                    ArtifactVersion(
                        output_id,
                        "1.0.0",
                        "reconciliation-observed",
                        stale.changed_input_ids,
                        stale=True,
                        stale_reason=stale.reason,
                    )
                )
        return replace(
            state,
            artifact_versions=tuple(versions),
            warnings=result.snapshot.warnings,
            revision=state.revision + 1,
        )

    def _validate_envelopes(
        self,
        state: DealState,
        issues: list[ReconciliationIssue],
        trace: list[ReconciliationTraceEvent],
    ) -> None:
        collections = (
            state.company_intelligence,
            state.target_screening_results,
            state.trading_comps_results,
            state.precedent_transaction_results,
            state.diligence_results,
        )
        results = tuple(result for collection in collections for result in collection)
        present = {result.source_project for result in results}
        for project in tuple(ProjectId)[:5]:
            if project not in present:
                issues.append(
                    _issue(
                        ReconciliationIssueType.MISSING_DEPENDENCY,
                        f"output:{project.value}",
                        (project,),
                        (),
                        IssueSeverity.LOW,
                        False,
                        f"No current result from {project.value} is available.",
                        (),
                        False,
                        ReconciliationStatus.UNRESOLVED,
                    )
                )
        for result in results:
            if result.schema_version != "1.0.0":
                issues.append(
                    _issue(
                        ReconciliationIssueType.MISSING_DEPENDENCY,
                        result.run_id,
                        (result.source_project,),
                        (result.run_id,),
                        IssueSeverity.HIGH,
                        True,
                        f"Unsupported specialist schema {result.schema_version}.",
                        result.evidence_refs,
                        True,
                        ReconciliationStatus.REVIEW_REQUIRED,
                    )
                )
        known_evidence = {item.evidence_id for item in state.evidence}
        referenced_evidence = {
            evidence_id
            for references in (
                *(result.evidence_refs for result in results),
                *(metric.evidence_refs for metric in state.financial_metrics),
                *(valuation.evidence_refs for valuation in state.valuation_outputs),
                *(finding.evidence_refs for finding in state.diligence_findings),
            )
            for evidence_id in references
        }
        for evidence_id in sorted(referenced_evidence - known_evidence):
            issues.append(
                _issue(
                    ReconciliationIssueType.MISSING_DEPENDENCY,
                    evidence_id,
                    (ProjectId.PROJECT_6,),
                    (evidence_id,),
                    IssueSeverity.HIGH,
                    False,
                    f"Referenced evidence {evidence_id} is absent from canonical state.",
                    (evidence_id,),
                    True,
                    ReconciliationStatus.REVIEW_REQUIRED,
                )
            )
        _trace(
            trace,
            ReconciliationTraceType.INPUTS_COMPARED,
            tuple(r.run_id for r in results),
            "Specialist envelopes inspected.",
        )

    def _reconcile_entities(
        self,
        entities: tuple[CanonicalEntityReference, ...],
        issues: list[ReconciliationIssue],
        trace: list[ReconciliationTraceEvent],
    ) -> tuple[EntityMatch, ...]:
        matches: list[EntityMatch] = []
        for left, right in combinations(entities, 2):
            match = compare_entities(left, right)
            matches.append(match)
            if match.status is ReconciliationStatus.REVIEW_REQUIRED:
                issues.append(
                    _issue(
                        ReconciliationIssueType.ENTITY_MISMATCH,
                        f"{left.canonical_entity_id}|{right.canonical_entity_id}",
                        tuple(dict.fromkeys((*left.source_projects, *right.source_projects))),
                        (left.canonical_entity_id, right.canonical_entity_id),
                        IssueSeverity.HIGH,
                        True,
                        match.ambiguity_reason or "Entity identity is ambiguous.",
                        tuple(dict.fromkeys((*left.evidence_refs, *right.evidence_refs))),
                        True,
                        ReconciliationStatus.REVIEW_REQUIRED,
                    )
                )
        _trace(
            trace,
            ReconciliationTraceType.COMPATIBILITY_CHECKED,
            tuple(item.canonical_entity_id for item in entities),
            "Entity identifiers and normalized names compared.",
        )
        return tuple(matches)

    def _reconcile_metrics(
        self,
        metrics: tuple[FinancialMetricReference, ...],
        issues: list[ReconciliationIssue],
        trace: list[ReconciliationTraceEvent],
    ) -> tuple[UnifiedMetricView, ...]:
        grouped: dict[str, list[FinancialMetricReference]] = defaultdict(list)
        for metric in metrics:
            grouped[_metric_key(metric)].append(metric)
        views: list[UnifiedMetricView] = []
        for key, observations in grouped.items():
            related_issues: list[str] = []
            status = ReconciliationStatus.ALIGNED
            for left, right in combinations(observations, 2):
                issue = self._compare_metric_pair(left, right)
                if issue is not None:
                    issues.append(issue)
                    related_issues.append(issue.issue_id)
                    if issue.issue_type is ReconciliationIssueType.METRIC_CONFLICT and set(
                        left.evidence_refs
                    ).isdisjoint(right.evidence_refs):
                        evidence_issue = _issue(
                            ReconciliationIssueType.EVIDENCE_CONFLICT,
                            f"{left.metric_id}|{right.metric_id}",
                            _projects(left, right),
                            (left.metric_id, right.metric_id),
                            IssueSeverity.HIGH,
                            False,
                            "Conflicting metric observations rely on different evidence.",
                            _evidence(left, right),
                            True,
                            ReconciliationStatus.REVIEW_REQUIRED,
                        )
                        issues.append(evidence_issue)
                        related_issues.append(evidence_issue.issue_id)
                    if issue.status is ReconciliationStatus.REVIEW_REQUIRED:
                        status = ReconciliationStatus.REVIEW_REQUIRED
                    elif status is ReconciliationStatus.ALIGNED:
                        status = issue.status
            selected = observations[0].metric_id if status is ReconciliationStatus.ALIGNED else None
            views.append(
                UnifiedMetricView(
                    key,
                    observations[0].metric_type,
                    observations[0].entity_id,
                    tuple(observations),
                    status,
                    selected,
                    tuple(related_issues),
                )
            )
        # Record different-period observations as non-conflicting compatibility issues.
        for left, right in combinations(metrics, 2):
            if _same_metric_subject(left, right) and not _same_period(left, right):
                issues.append(
                    _issue(
                        ReconciliationIssueType.PERIOD_MISMATCH,
                        f"{left.metric_id}|{right.metric_id}",
                        _projects(left, right),
                        (left.metric_id, right.metric_id),
                        IssueSeverity.INFO,
                        False,
                        "Observations use different periods and are not direct contradictions.",
                        _evidence(left, right),
                        False,
                        ReconciliationStatus.NOT_COMPARABLE,
                    )
                )
        _trace(
            trace,
            ReconciliationTraceType.COMPATIBILITY_CHECKED,
            tuple(metric.metric_id for metric in metrics),
            "Metric type, period, basis, currency, unit, and estimate status compared.",
        )
        return tuple(views)

    def _compare_metric_pair(
        self, left: FinancialMetricReference, right: FinancialMetricReference
    ) -> ReconciliationIssue | None:
        if left.currency != right.currency:
            return _metric_issue(
                ReconciliationIssueType.CURRENCY_MISMATCH,
                left,
                right,
                "Currencies differ; no implicit FX conversion was performed.",
                ReconciliationStatus.NOT_COMPARABLE,
                IssueSeverity.MEDIUM,
                False,
            )
        if left.estimate_status is not right.estimate_status:
            return _metric_issue(
                ReconciliationIssueType.BASIS_MISMATCH,
                left,
                right,
                "Actual and forecast observations are not directly comparable.",
                ReconciliationStatus.NOT_COMPARABLE,
                IssueSeverity.MEDIUM,
                False,
            )
        if left.basis is not right.basis:
            message = (
                f"{left.basis.value} and {right.basis.value} {left.metric_type} are valid "
                "observations on different bases and require scenario selection."
            )
            return _metric_issue(
                ReconciliationIssueType.BASIS_MISMATCH,
                left,
                right,
                message,
                ReconciliationStatus.REVIEW_REQUIRED,
                IssueSeverity.HIGH,
                True,
            )
        left_value = _normalized_value(left)
        right_value = _normalized_value(right)
        if left_value is None or right_value is None:
            return _metric_issue(
                ReconciliationIssueType.BASIS_MISMATCH,
                left,
                right,
                "Metric units cannot be normalized safely.",
                ReconciliationStatus.NOT_COMPARABLE,
                IssueSeverity.MEDIUM,
                False,
            )
        if _within_tolerance(left_value, right_value, self.tolerance):
            return None
        return _metric_issue(
            ReconciliationIssueType.METRIC_CONFLICT,
            left,
            right,
            "Same-period, same-basis observations differ beyond configured tolerance.",
            ReconciliationStatus.REVIEW_REQUIRED,
            IssueSeverity.HIGH,
            True,
        )

    def _detect_staleness(
        self,
        state: DealState,
        issues: list[ReconciliationIssue],
        trace: list[ReconciliationTraceEvent],
    ) -> tuple[tuple[StaleOutputReference, ...], tuple[RecomputeRequest, ...]]:
        metrics = {item.metric_id: item for item in state.financial_metrics}
        stale: dict[str, StaleOutputReference] = {}
        requests: dict[str, RecomputeRequest] = {}
        adjusted = [
            item
            for item in state.financial_metrics
            if item.basis in {MetricBasis.ADJUSTED, MetricBasis.NORMALIZED}
        ]
        for valuation in state.valuation_outputs:
            for input_id in valuation.input_metric_ids:
                source_metric = metrics.get(input_id)
                if source_metric is None:
                    continue
                alternatives = [
                    item
                    for item in adjusted
                    if _same_metric_subject(source_metric, item)
                    and _same_period(source_metric, item)
                    and _compatible_numeric_pair(source_metric, item)
                    and item.metric_id != source_metric.metric_id
                ]
                if not alternatives:
                    continue
                changed = tuple(item.metric_id for item in alternatives)
                scenario = "scenario:diligence-adjusted"
                reason = (
                    f"{valuation.valuation_id} uses {source_metric.metric_id}; adjusted "
                    f"alternative(s) {', '.join(changed)} are available."
                )
                stale[valuation.valuation_id] = StaleOutputReference(
                    valuation.valuation_id,
                    ReconciliationStatus.STALE,
                    (scenario,),
                    reason,
                    changed,
                )
                request = RecomputeRequest(
                    f"recompute:{valuation.valuation_id}:adjusted",
                    valuation.valuation_id,
                    reason,
                    changed,
                    _valuation_capability(valuation),
                    ReviewPriority.HIGH,
                    True,
                    scenario,
                )
                requests[request.request_id] = request
                issue = _issue(
                    ReconciliationIssueType.STALE_RESULT,
                    valuation.valuation_id,
                    tuple(
                        dict.fromkeys(
                            (valuation.source_project, *(x.source_project for x in alternatives))
                        )
                    ),
                    (valuation.valuation_id, input_id, *changed),
                    IssueSeverity.HIGH,
                    False,
                    reason,
                    tuple(
                        dict.fromkeys((*valuation.evidence_refs, *(_evidence_many(alternatives))))
                    ),
                    True,
                    ReconciliationStatus.STALE,
                )
                issues.append(issue)
                _trace(
                    trace, ReconciliationTraceType.STALE_FLAG_SET, (valuation.valuation_id,), reason
                )
                _trace(
                    trace,
                    ReconciliationTraceType.RECOMPUTATION_REQUESTED,
                    (request.request_id,),
                    "Specialist rerun requested; no valuation was recomputed.",
                )

        superseded_versions = [item for item in state.artifact_versions if item.superseded_by]
        superseded = {item.artifact_id for item in superseded_versions}
        for version in superseded_versions:
            stale.setdefault(
                version.artifact_id,
                StaleOutputReference(
                    version.artifact_id,
                    ReconciliationStatus.SUPERSEDED,
                    (),
                    f"Artifact was superseded by {version.superseded_by}.",
                    (),
                ),
            )
        for version in state.artifact_versions:
            changed = tuple(item for item in version.produced_from if item in superseded)
            if not changed or version.artifact_id in stale:
                continue
            reason = f"A producing input was superseded: {', '.join(changed)}."
            stale[version.artifact_id] = StaleOutputReference(
                version.artifact_id,
                ReconciliationStatus.STALE,
                ("scenario:current",),
                reason,
                changed,
            )
            dependent_valuation = next(
                (
                    item
                    for item in state.valuation_outputs
                    if item.valuation_id == version.artifact_id
                ),
                None,
            )
            if dependent_valuation is not None:
                request = RecomputeRequest(
                    f"recompute:{dependent_valuation.valuation_id}:current",
                    dependent_valuation.valuation_id,
                    reason,
                    changed,
                    _valuation_capability(dependent_valuation),
                    ReviewPriority.HIGH,
                    True,
                    "scenario:current",
                )
                requests[request.request_id] = request
                issues.append(
                    _issue(
                        ReconciliationIssueType.STALE_RESULT,
                        dependent_valuation.valuation_id,
                        (dependent_valuation.source_project,),
                        (dependent_valuation.valuation_id, *changed),
                        IssueSeverity.HIGH,
                        False,
                        reason,
                        dependent_valuation.evidence_refs,
                        True,
                        ReconciliationStatus.STALE,
                    )
                )
        return tuple(stale.values()), tuple(requests.values())

    def _compare_valuations(
        self,
        valuations: tuple[ValuationReference, ...],
        warnings: tuple[DealWarning, ...],
        stale: tuple[StaleOutputReference, ...],
        issues: list[ReconciliationIssue],
        trace: list[ReconciliationTraceEvent],
    ) -> ValuationComparison:
        stale_map = {item.output_id: item.stale_for_scenarios for item in stale}
        entries = tuple(
            UnifiedValuationEntry(
                valuation,
                stale_map.get(valuation.valuation_id, ()),
                tuple(item for item in warnings if item.warning_id in valuation.warning_ids),
            )
            for valuation in valuations
        )
        if len(valuations) < 2:
            return ValuationComparison(entries, None, None, None)
        left, right = valuations[:2]
        issue_ids: list[str] = []
        left_scale = _UNIT_SCALE.get(left.unit.casefold().strip())
        right_scale = _UNIT_SCALE.get(right.unit.casefold().strip())
        if left.currency != right.currency or left_scale is None or right_scale is None:
            issue = _issue(
                ReconciliationIssueType.CURRENCY_MISMATCH,
                "valuation-comparison",
                (left.source_project, right.source_project),
                (left.valuation_id, right.valuation_id),
                IssueSeverity.MEDIUM,
                False,
                "Valuation ranges use incompatible currency or units.",
                tuple(dict.fromkeys((*left.evidence_refs, *right.evidence_refs))),
                True,
                ReconciliationStatus.NOT_COMPARABLE,
            )
            issues.append(issue)
            return ValuationComparison(entries, None, None, None, (issue.issue_id,))
        if left.valuation_basis is not right.valuation_basis:
            issue = _issue(
                ReconciliationIssueType.BASIS_MISMATCH,
                "valuation-comparison",
                (left.source_project, right.source_project),
                (left.valuation_id, right.valuation_id),
                IssueSeverity.HIGH,
                False,
                "Enterprise-value and equity-value ranges are not directly comparable.",
                tuple(dict.fromkeys((*left.evidence_refs, *right.evidence_refs))),
                True,
                ReconciliationStatus.NOT_COMPARABLE,
            )
            issues.append(issue)
            return ValuationComparison(entries, None, None, None, (issue.issue_id,))
        right_factor = right_scale / left_scale
        right_low = right.low * right_factor
        right_midpoint = right.midpoint * right_factor
        right_high = right.high * right_factor
        gap = right_midpoint - left.midpoint
        denominator = min(abs(left.midpoint), abs(right_midpoint))
        gap_percent = abs(gap) / denominator if denominator else None
        overlap = max(left.low, right_low) <= min(left.high, right_high)
        if gap_percent is not None and gap_percent > self.tolerance.valuation_divergence:
            issue = _issue(
                ReconciliationIssueType.VALUATION_DIVERGENCE,
                "valuation-comparison",
                (left.source_project, right.source_project),
                (left.valuation_id, right.valuation_id),
                IssueSeverity.MEDIUM,
                False,
                "Valuation midpoints diverge beyond the configured materiality threshold.",
                tuple(dict.fromkeys((*left.evidence_refs, *right.evidence_refs))),
                True,
                ReconciliationStatus.REVIEW_REQUIRED,
            )
            issues.append(issue)
            issue_ids.append(issue.issue_id)
        _trace(
            trace,
            ReconciliationTraceType.COMPATIBILITY_CHECKED,
            (left.valuation_id, right.valuation_id),
            "Valuation methods retained separately and compared without averaging.",
        )
        return ValuationComparison(entries, gap, gap_percent, overlap, tuple(issue_ids))

    def _link_diligence(
        self,
        state: DealState,
        stale: tuple[StaleOutputReference, ...],
        issues: list[ReconciliationIssue],
        trace: list[ReconciliationTraceEvent],
    ) -> tuple[tuple[DealImpactInsight, ...], tuple[RelatedInsightLink, ...]]:
        valuations = tuple(item.valuation_id for item in state.valuation_outputs)
        insights: list[DealImpactInsight] = []
        links: list[RelatedInsightLink] = []
        reported = next(
            (
                m
                for m in state.financial_metrics
                if m.metric_type.casefold() == "ebitda" and m.basis is MetricBasis.REPORTED
            ),
            None,
        )
        adjusted = next(
            (
                m
                for m in state.financial_metrics
                if m.metric_type.casefold() == "ebitda"
                and m.basis in {MetricBasis.ADJUSTED, MetricBasis.NORMALIZED}
            ),
            None,
        )
        if (
            reported
            and adjusted
            and _same_period(reported, adjusted)
            and _compatible_numeric_pair(reported, adjusted)
        ):
            reported_scale = _UNIT_SCALE[reported.unit.casefold().strip()]
            adjusted_value = _normalized_value(adjusted)
            assert adjusted_value is not None
            adjusted_in_reported_unit = adjusted_value / reported_scale
            delta = adjusted_in_reported_unit - reported.value
            percent = delta / abs(reported.value) if reported.value else None
            insight = DealImpactInsight(
                "insight:ebitda-basis",
                "Diligence EBITDA differs from valuation input",
                "valuation_input",
                (reported.source_project, adjusted.source_project),
                (reported.metric_id, adjusted.metric_id),
                tuple(item.output_id for item in stale),
                (
                    "The diligence-adjusted EBITDA should be evaluated as a separate "
                    "valuation scenario."
                ),
                ImpactDirection.NEGATIVE if delta < 0 else ImpactDirection.POSITIVE,
                delta,
                percent,
                tuple(dict.fromkeys((*reported.evidence_refs, *adjusted.evidence_refs))),
                ReconciliationStatus.REVIEW_REQUIRED,
                True,
            )
            insights.append(insight)
            issues.append(
                _issue(
                    ReconciliationIssueType.DILIGENCE_IMPACT,
                    "ebitda-basis",
                    (reported.source_project, adjusted.source_project),
                    (reported.metric_id, adjusted.metric_id, *insight.affected_output_ids),
                    IssueSeverity.HIGH,
                    False,
                    insight.qualitative_impact,
                    insight.evidence_refs,
                    True,
                    ReconciliationStatus.REVIEW_REQUIRED,
                )
            )
        for finding in state.diligence_findings:
            text = f"{finding.title} {' '.join(finding.deal_impacts)}".casefold()
            if "customer" in text or "concentration" in text:
                category = "valuation_confidence"
                impact = (
                    "Customer concentration may weaken confidence in an upper-quartile multiple."
                )
                affected = valuations
            elif "net debt" in text or "net_debt" in text:
                category = "equity_value_context"
                impact = (
                    "Adjusted net debt affects the bridge from enterprise value to equity value."
                )
                affected = (
                    tuple(
                        v.valuation_id
                        for v in state.valuation_outputs
                        if v.valuation_basis.value == "equity_value"
                    )
                    or valuations
                )
            elif "contract" in text or "change-of-control" in text or "change of control" in text:
                category = "deal_execution"
                impact = "Change-of-control requirements may affect deal execution and timing."
                affected = ()
            else:
                continue
            insight = DealImpactInsight(
                f"insight:{finding.finding_id}",
                finding.title,
                category,
                (ProjectId.PROJECT_5,),
                (finding.finding_id,),
                affected,
                impact,
                ImpactDirection.NEGATIVE,
                evidence_refs=finding.evidence_refs,
                status=ReconciliationStatus.REVIEW_REQUIRED,
                analyst_review_required=True,
            )
            insights.append(insight)
            for output_id in affected:
                links.append(RelatedInsightLink(insight.insight_id, output_id, "affects"))
            _trace(
                trace,
                ReconciliationTraceType.INSIGHT_LINKED,
                (insight.insight_id, *affected),
                impact,
            )
        return tuple(insights), tuple(links)

    def _build_risks(
        self, state: DealState, issues: list[ReconciliationIssue]
    ) -> tuple[UnifiedRiskItem, ...]:
        risks = [
            UnifiedRiskItem(
                f"risk:{finding.finding_id}",
                finding.title,
                _issue_severity(finding.severity),
                (finding.source_project,),
                (finding.finding_id,),
                finding.deal_impacts,
                finding.evidence_refs,
            )
            for finding in state.diligence_findings
        ]
        risks.extend(
            UnifiedRiskItem(
                f"risk:{warning.warning_id}",
                warning.message,
                warning.severity,
                (warning.source_project,),
                (warning.warning_id,),
                tuple(
                    item for item in (warning.affected_field, warning.affected_capability) if item
                ),
                warning.evidence_refs,
            )
            for warning in state.warnings
        )
        risks.extend(
            UnifiedRiskItem(
                f"risk:{issue.issue_id}",
                issue.description,
                issue.severity,
                issue.affected_projects,
                (issue.issue_id,),
                issue.affected_output_ids,
                issue.evidence_refs,
            )
            for issue in issues
            if issue.severity in {IssueSeverity.MEDIUM, IssueSeverity.HIGH, IssueSeverity.CRITICAL}
        )
        return tuple({item.risk_id: item for item in risks}.values())

    def _build_thesis_view(
        self, state: DealState, insights: tuple[DealImpactInsight, ...]
    ) -> tuple[ThesisEvidence, ...]:
        items: list[ThesisEvidence] = []
        for result in state.target_screening_results:
            for candidate in result.payload.candidates:
                if candidate.rationale:
                    items.append(
                        ThesisEvidence(
                            f"thesis:{candidate.entity.canonical_entity_id}",
                            ThesisPosition.SUPPORTS,
                            candidate.rationale,
                            (candidate.entity.canonical_entity_id,),
                            candidate.evidence_refs,
                        )
                    )
        items.extend(
            ThesisEvidence(
                f"thesis:{insight.insight_id}",
                ThesisPosition.CHALLENGES
                if insight.direction is ImpactDirection.NEGATIVE
                else ThesisPosition.UNRESOLVED,
                insight.qualitative_impact,
                insight.underlying_ids,
                insight.evidence_refs,
            )
            for insight in insights
        )
        return tuple(items)

    def _build_open_questions(
        self, state: DealState, issues: list[ReconciliationIssue]
    ) -> tuple[OpenQuestion, ...]:
        questions: list[OpenQuestion] = []
        for result in state.diligence_results:
            questions.extend(
                OpenQuestion(
                    f"question:{missing_id}",
                    _question_text(missing_id),
                    (ProjectId.PROJECT_5,),
                    (missing_id,),
                    False,
                )
                for missing_id in result.payload.missing_information_ids
            )
        for issue in issues:
            if issue.analyst_review_required:
                questions.append(
                    OpenQuestion(
                        f"question:{issue.issue_id}",
                        _issue_question(issue),
                        issue.affected_projects,
                        (issue.issue_id,),
                        issue.blocking,
                    )
                )
        return tuple({item.question.casefold(): item for item in questions}.values())

    def _build_review_queue(
        self, issues: list[ReconciliationIssue]
    ) -> tuple[AnalystReviewItem, ...]:
        grouped: dict[str, list[ReconciliationIssue]] = defaultdict(list)
        for issue in issues:
            if issue.analyst_review_required and issue.status is not ReconciliationStatus.RESOLVED:
                grouped[issue.subject_id].append(issue)
        items = []
        for subject, subject_issues in grouped.items():
            output_ids = tuple(
                dict.fromkeys(
                    output for issue in subject_issues for output in issue.affected_output_ids
                )
            )
            items.append(
                AnalystReviewItem(
                    f"review:{_stable_id(subject)}",
                    subject,
                    tuple(issue.issue_id for issue in subject_issues),
                    _review_priority(subject_issues, len(output_ids)),
                    "; ".join(dict.fromkeys(issue.description for issue in subject_issues)),
                    output_ids,
                    tuple(
                        dict.fromkeys(
                            resolution.action
                            for issue in subject_issues
                            for resolution in issue.candidate_resolutions
                        )
                    ),
                )
            )
        order = {
            ReviewPriority.CRITICAL: 0,
            ReviewPriority.HIGH: 1,
            ReviewPriority.MEDIUM: 2,
            ReviewPriority.LOW: 3,
        }
        return tuple(sorted(items, key=lambda item: (order[item.priority], item.review_id)))

    def _build_scenarios(
        self,
        state: DealState,
        stale: tuple[StaleOutputReference, ...],
        requests: tuple[RecomputeRequest, ...],
    ) -> ScenarioComparison:
        ebitda = [
            item for item in state.financial_metrics if item.metric_type.casefold() == "ebitda"
        ]
        scenario_values: list[DealScenario] = []
        for metric in ebitda:
            scenario_id = (
                "scenario:diligence-adjusted"
                if metric.basis is MetricBasis.ADJUSTED
                and metric.source_project is ProjectId.PROJECT_5
                else f"scenario:{metric.basis.value}"
            )
            name = (
                "Diligence-adjusted EBITDA"
                if scenario_id == "scenario:diligence-adjusted"
                else f"{metric.basis.value.replace('_', ' ').title()} EBITDA"
            )
            scenario_values.append(
                DealScenario(
                    scenario_id,
                    name,
                    (MetricChoice(metric.metric_type, metric.metric_id, metric.basis.value),),
                    tuple(
                        item.output_id for item in stale if scenario_id in item.stale_for_scenarios
                    ),
                    tuple(item.request_id for item in requests if item.scenario_id == scenario_id),
                )
            )
        scenarios = tuple(scenario_values)
        return ScenarioComparison(
            scenarios,
            tuple(metric.metric_id for metric in ebitda),
            tuple(item.output_id for item in stale),
            tuple(item.request_id for item in requests),
        )


def compare_entities(
    left: CanonicalEntityReference, right: CanonicalEntityReference
) -> EntityMatch:
    left_name = _entity_name(left)
    right_name = _entity_name(right)
    if left.canonical_entity_id == right.canonical_entity_id:
        return EntityMatch(
            left.canonical_entity_id,
            right.canonical_entity_id,
            ReconciliationStatus.ALIGNED,
            (left_name, right_name),
            ("canonical_entity_id",),
        )
    matched: list[str] = []
    if left.ticker and right.ticker and left.ticker.casefold() == right.ticker.casefold():
        matched.append("ticker")
    if left.exchange and right.exchange and left.exchange.casefold() == right.exchange.casefold():
        matched.append("exchange")
    left_names = {_normalize_entity_name(item) for item in _entity_names(left)}
    right_names = {_normalize_entity_name(item) for item in _entity_names(right)}
    if left_names & right_names:
        matched.append("name_or_alias")
    incompatible = bool(
        left.country and right.country and left.country.casefold() != right.country.casefold()
    )
    if "ticker" in matched and not incompatible:
        return EntityMatch(
            left.canonical_entity_id,
            right.canonical_entity_id,
            ReconciliationStatus.ALIGNED,
            (left_name, right_name),
            tuple(matched),
        )
    if "name_or_alias" in matched and not incompatible:
        return EntityMatch(
            left.canonical_entity_id,
            right.canonical_entity_id,
            ReconciliationStatus.ALIGNED,
            (left_name, right_name),
            tuple(matched),
        )
    if matched or left_name == right_name:
        return EntityMatch(
            left.canonical_entity_id,
            right.canonical_entity_id,
            ReconciliationStatus.REVIEW_REQUIRED,
            (left_name, right_name),
            tuple(matched),
            "Entity attributes conflict despite a partial identity match.",
        )
    return EntityMatch(
        left.canonical_entity_id,
        right.canonical_entity_id,
        ReconciliationStatus.NOT_COMPARABLE,
        (left_name, right_name),
        (),
        "No deterministic identity match was found.",
    )


def reconcile_evidence(evidence: tuple[EvidenceReference, ...]) -> tuple[EvidenceLink, ...]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for item in evidence:
        key = _evidence_source_key(item)
        if key:
            grouped[key].append(item.evidence_id)
    return tuple(
        EvidenceLink(f"evidence-link:{_stable_id(key)}", tuple(ids), key)
        for key, ids in grouped.items()
        if len(ids) > 1
    )


def _metric_key(metric: FinancialMetricReference) -> str:
    period = (
        f"{metric.period.start_date}:{metric.period.end_date}"
        if metric.period.start_date
        else metric.period.label.casefold().strip()
    )
    entity_id = (metric.entity_id or "unknown").casefold()
    metric_type = metric.metric_type.casefold().strip()
    return f"{entity_id}|{metric_type}|{period}"


def _same_metric_subject(left: FinancialMetricReference, right: FinancialMetricReference) -> bool:
    return left.metric_type.casefold().strip() == right.metric_type.casefold().strip() and (
        left.entity_id == right.entity_id or left.entity_id is None or right.entity_id is None
    )


def _same_period(left: FinancialMetricReference, right: FinancialMetricReference) -> bool:
    if left.period.start_date and right.period.start_date:
        return (
            left.period.start_date == right.period.start_date
            and left.period.end_date == right.period.end_date
        )
    return left.period.label.casefold().strip() == right.period.label.casefold().strip()


def _normalized_value(metric: FinancialMetricReference) -> Decimal | None:
    scale = _UNIT_SCALE.get(metric.unit.casefold().strip())
    return metric.value * scale if scale is not None else None


def _compatible_numeric_pair(
    left: FinancialMetricReference, right: FinancialMetricReference
) -> bool:
    return (
        left.currency == right.currency
        and left.estimate_status is right.estimate_status
        and _normalized_value(left) is not None
        and _normalized_value(right) is not None
    )


def _within_tolerance(left: Decimal, right: Decimal, policy: NumericTolerancePolicy) -> bool:
    difference = abs(left - right)
    relative_base = max(abs(left), abs(right))
    return difference <= policy.absolute or (
        relative_base > 0 and difference / relative_base <= policy.relative
    )


def _metric_issue(
    kind: ReconciliationIssueType,
    left: FinancialMetricReference,
    right: FinancialMetricReference,
    description: str,
    status: ReconciliationStatus,
    severity: IssueSeverity,
    review: bool,
) -> ReconciliationIssue:
    resolutions = (
        (
            CandidateResolution(
                "select_metric_basis", "Choose the metric basis for the intended scenario."
            ),
            CandidateResolution(
                "request_specialist_rerun",
                "Request a specialist rerun using the selected input.",
                True,
            ),
        )
        if review
        else ()
    )
    return _issue(
        kind,
        f"{left.metric_id}|{right.metric_id}",
        _projects(left, right),
        (left.metric_id, right.metric_id),
        severity,
        False,
        description,
        _evidence(left, right),
        review,
        status,
        resolutions,
    )


def _issue(
    kind: ReconciliationIssueType,
    subject_id: str,
    projects: tuple[ProjectId, ...],
    outputs: tuple[str, ...],
    severity: IssueSeverity,
    blocking: bool,
    description: str,
    evidence_refs: tuple[str, ...],
    review: bool,
    status: ReconciliationStatus,
    resolutions: tuple[CandidateResolution, ...] = (),
) -> ReconciliationIssue:
    return ReconciliationIssue(
        f"issue:{kind.value}:{_stable_id(subject_id)}",
        kind,
        subject_id,
        tuple(dict.fromkeys(projects)),
        tuple(dict.fromkeys(outputs)),
        severity,
        blocking,
        description,
        resolutions,
        tuple(dict.fromkeys(evidence_refs)),
        review,
        status,
    )


def _projects(
    left: FinancialMetricReference, right: FinancialMetricReference
) -> tuple[ProjectId, ...]:
    return tuple(dict.fromkeys((left.source_project, right.source_project)))


def _evidence(left: FinancialMetricReference, right: FinancialMetricReference) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*left.evidence_refs, *right.evidence_refs)))


def _evidence_many(metrics: list[FinancialMetricReference]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item for metric in metrics for item in metric.evidence_refs))


def _valuation_capability(valuation: ValuationReference) -> str:
    return (
        str(CapabilityId.P3_PRODUCE_VALUATION_RANGE)
        if valuation.source_project is ProjectId.PROJECT_3
        else str(CapabilityId.P4_PRODUCE_VALUATION_RANGE)
    )


def _cross_project_warnings(
    state: DealState,
    issues: list[ReconciliationIssue],
    stale: tuple[StaleOutputReference, ...],
) -> tuple[DealWarning, ...]:
    warnings = [
        DealWarning(
            f"warning:{issue.issue_id}",
            issue.issue_type.value.upper(),
            issue.severity,
            issue.description,
            ProjectId.PROJECT_6,
            affected_field=issue.subject_id,
            evidence_refs=issue.evidence_refs,
            blocking=issue.blocking,
        )
        for issue in issues
        if issue.issue_type
        in {
            ReconciliationIssueType.BASIS_MISMATCH,
            ReconciliationIssueType.METRIC_CONFLICT,
            ReconciliationIssueType.CURRENCY_MISMATCH,
            ReconciliationIssueType.VALUATION_DIVERGENCE,
            ReconciliationIssueType.EVIDENCE_CONFLICT,
        }
    ]
    warnings.extend(
        DealWarning(
            f"warning:stale:{_stable_id(item.output_id)}",
            "STALE_FOR_SCENARIO",
            IssueSeverity.HIGH,
            item.reason,
            ProjectId.PROJECT_6,
            affected_field=item.output_id,
        )
        for item in stale
    )
    return tuple(warnings)


def _review_priority(
    issues: list[ReconciliationIssue], affected_output_count: int
) -> ReviewPriority:
    if any(item.blocking and item.severity is IssueSeverity.CRITICAL for item in issues):
        return ReviewPriority.CRITICAL
    if any(
        item.blocking or item.severity in {IssueSeverity.HIGH, IssueSeverity.CRITICAL}
        for item in issues
    ):
        return ReviewPriority.HIGH
    if affected_output_count > 1 or any(item.severity is IssueSeverity.MEDIUM for item in issues):
        return ReviewPriority.MEDIUM
    return ReviewPriority.LOW


def _issue_severity(severity: FindingSeverity) -> IssueSeverity:
    try:
        return IssueSeverity(severity.value)
    except ValueError:
        return IssueSeverity.MEDIUM


def _question_text(missing_id: str) -> str:
    text = missing_id.split(":")[-1].replace("-", " ").replace("_", " ")
    return f"What information resolves {text}?"


def _issue_question(issue: ReconciliationIssue) -> str:
    if issue.issue_type is ReconciliationIssueType.BASIS_MISMATCH:
        return "Which metric basis should be used for the relevant valuation scenario?"
    if issue.issue_type is ReconciliationIssueType.STALE_RESULT:
        return "Should the affected specialist valuation be rerun with updated inputs?"
    if issue.issue_type is ReconciliationIssueType.VALUATION_DIVERGENCE:
        return "How should the method-specific valuation divergence be interpreted?"
    return f"How should the analyst resolve {issue.issue_type.value.replace('_', ' ')}?"


def _entity_names(entity: CanonicalEntityReference) -> tuple[str, ...]:
    return tuple(item for item in (entity.legal_name, entity.display_name, *entity.aliases) if item)


def _entity_name(entity: CanonicalEntityReference) -> str:
    return _normalize_entity_name(
        entity.display_name or entity.legal_name or entity.canonical_entity_id
    )


def _normalize_entity_name(name: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", name.casefold().replace("&", " and "))
    while tokens and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def _evidence_source_key(item: EvidenceReference) -> str | None:
    if item.document_id:
        locator = item.cell_range or item.chunk_id or ",".join(map(str, item.page_numbers))
        return f"document:{item.document_id}:{locator}"
    if item.url:
        return f"url:{item.url.casefold().rstrip('/')}"
    if item.source_record_id:
        return f"record:{item.source_record_id}"
    return None


def _stable_id(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()[:12]


def _trace(
    trace: list[ReconciliationTraceEvent],
    event_type: ReconciliationTraceType,
    subjects: tuple[str, ...],
    message: str,
) -> None:
    trace.append(ReconciliationTraceEvent(len(trace) + 1, event_type, subjects, message))
