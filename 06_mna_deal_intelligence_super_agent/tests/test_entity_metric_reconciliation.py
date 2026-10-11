from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

from ma_deal_intelligence.evidence import ProjectId
from ma_deal_intelligence.finance import (
    EstimateStatus,
    FinancialMetricReference,
    FinancialPeriodReference,
    MetricBasis,
)
from ma_deal_intelligence.identity import CanonicalEntityReference, DealContext
from ma_deal_intelligence.reconciliation import ReconciliationService, compare_entities
from ma_deal_intelligence.reconciliation_models import (
    NumericTolerancePolicy,
    ReconciliationIssueType,
    ReconciliationStatus,
    UnifiedDealIntelligenceSnapshot,
)
from ma_deal_intelligence.state import DealState
from ma_deal_intelligence.workflow import AnalystDecision, DecisionAction

PERIOD = FinancialPeriodReference("FY2025", date(2025, 1, 1), date(2025, 12, 31))


def _metric(
    metric_id: str,
    value: str,
    *,
    project: ProjectId = ProjectId.PROJECT_1,
    period: FinancialPeriodReference = PERIOD,
    basis: MetricBasis = MetricBasis.REPORTED,
    currency: str | None = "USD",
    unit: str = "million",
    evidence: str = "evidence:1",
) -> FinancialMetricReference:
    return FinancialMetricReference(
        metric_id,
        "Revenue",
        Decimal(value),
        currency,
        unit,
        period,
        basis,
        EstimateStatus.ACTUAL,
        project,
        f"source:{metric_id}",
        "entity:target",
        (evidence,),
    )


def _reconcile(*metrics: FinancialMetricReference) -> UnifiedDealIntelligenceSnapshot:
    state = DealState(DealContext("deal:metric"), financial_metrics=metrics)
    return ReconciliationService().reconcile(state).snapshot


def test_entity_alias_normalization_exact_id_and_false_positive_avoidance() -> None:
    exact = CanonicalEntityReference("entity:abc", legal_name="ABC Limited")
    alias = CanonicalEntityReference(
        "entity:abc-alias", display_name="ABC", aliases=("ABC Ltd.",), country="GB"
    )
    same_country = replace(exact, canonical_entity_id="entity:abc-legal", country="GB")
    assert compare_entities(exact, exact).status is ReconciliationStatus.ALIGNED
    assert compare_entities(alias, same_country).status is ReconciliationStatus.ALIGNED

    ambiguous = replace(same_country, canonical_entity_id="entity:abc-us", country="US")
    assert compare_entities(alias, ambiguous).status is ReconciliationStatus.REVIEW_REQUIRED
    unrelated = CanonicalEntityReference("entity:xyz", display_name="XYZ Holdings", country="GB")
    assert compare_entities(alias, unrelated).status is ReconciliationStatus.NOT_COMPARABLE


def test_aligned_conflicting_and_tolerance_metric_comparisons() -> None:
    aligned = _reconcile(
        _metric("m1", "500"),
        _metric("m2", "500", project=ProjectId.PROJECT_3, evidence="evidence:2"),
    )
    assert aligned.metrics[0].status is ReconciliationStatus.ALIGNED
    assert not any(
        issue.issue_type is ReconciliationIssueType.METRIC_CONFLICT for issue in aligned.issues
    )

    near = _reconcile(_metric("m1", "100.00"), _metric("m2", "100.01"))
    assert near.metrics[0].status is ReconciliationStatus.ALIGNED

    conflict = _reconcile(
        _metric("m1", "500", evidence="evidence:a"),
        _metric("m2", "560", project=ProjectId.PROJECT_3, evidence="evidence:b"),
    )
    kinds = {issue.issue_type for issue in conflict.issues}
    assert ReconciliationIssueType.METRIC_CONFLICT in kinds
    assert ReconciliationIssueType.EVIDENCE_CONFLICT in kinds


def test_period_basis_currency_and_unit_reconciliation() -> None:
    other_period = FinancialPeriodReference("LTM Sep-2026", date(2025, 10, 1), date(2026, 9, 30))
    period_result = _reconcile(_metric("m1", "500"), _metric("m2", "550", period=other_period))
    assert any(
        issue.issue_type is ReconciliationIssueType.PERIOD_MISMATCH
        and issue.status is ReconciliationStatus.NOT_COMPARABLE
        for issue in period_result.issues
    )
    assert not any(
        issue.issue_type is ReconciliationIssueType.METRIC_CONFLICT
        for issue in period_result.issues
    )

    basis_result = _reconcile(
        _metric("reported", "100"),
        _metric("adjusted", "85", basis=MetricBasis.ADJUSTED, project=ProjectId.PROJECT_5),
    )
    assert any(
        issue.issue_type is ReconciliationIssueType.BASIS_MISMATCH for issue in basis_result.issues
    )

    currency_result = _reconcile(_metric("usd", "100"), _metric("gbp", "100", currency="GBP"))
    assert any(
        issue.issue_type is ReconciliationIssueType.CURRENCY_MISMATCH
        for issue in currency_result.issues
    )

    units = _reconcile(_metric("million", "1"), _metric("thousand", "1000", unit="thousand"))
    assert units.metrics[0].status is ReconciliationStatus.ALIGNED


def test_tolerance_policy_is_configurable() -> None:
    state = DealState(
        DealContext("deal:tolerance"),
        financial_metrics=(_metric("m1", "100"), _metric("m2", "100.5")),
    )
    strict = ReconciliationService(NumericTolerancePolicy(relative=Decimal("0.001")))
    relaxed = ReconciliationService(NumericTolerancePolicy(relative=Decimal("0.01")))
    assert (
        strict.reconcile(state).snapshot.metrics[0].status is ReconciliationStatus.REVIEW_REQUIRED
    )
    assert relaxed.reconcile(state).snapshot.metrics[0].status is ReconciliationStatus.ALIGNED


def test_explicit_analyst_decision_resolves_without_changing_observations() -> None:
    metrics = (_metric("m1", "500"), _metric("m2", "560"))
    initial = ReconciliationService().reconcile(
        DealState(DealContext("deal:decision"), financial_metrics=metrics)
    )
    conflict = next(
        issue
        for issue in initial.snapshot.issues
        if issue.issue_type is ReconciliationIssueType.METRIC_CONFLICT
    )
    decision = AnalystDecision(
        "decision:metric",
        "reconciliation_issue",
        conflict.subject_id,
        "unresolved",
        DecisionAction.SELECT,
        "Select the audited observation.",
        "analyst@example.com",
        datetime(2026, 1, 1, tzinfo=UTC),
        selected_value="m1",
    )
    state = DealState(
        DealContext("deal:decision"),
        financial_metrics=metrics,
        analyst_decisions=(decision,),
    )
    snapshot = ReconciliationService().reconcile(state).snapshot
    assert snapshot.metrics[0].status is ReconciliationStatus.RESOLVED
    assert snapshot.metrics[0].selected_metric_id == "m1"
    assert snapshot.metrics[0].observations == metrics
