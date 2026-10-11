from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from ma_deal_intelligence.reconciliation import ReconciliationService
from ma_deal_intelligence.reconciliation_fixtures import rich_reconciliation_state
from ma_deal_intelligence.reconciliation_models import (
    ReconciliationIssueType,
    ReconciliationStatus,
)
from ma_deal_intelligence.workflow import ArtifactVersion


def test_adjusted_ebitda_marks_dependent_valuation_stale_without_recomputing() -> None:
    state = rich_reconciliation_state()
    result = ReconciliationService().reconcile(state)
    stale = next(
        item
        for item in result.snapshot.stale_outputs
        if item.output_id == "valuation:p3:trading-comps"
    )
    assert stale.status is ReconciliationStatus.STALE
    assert stale.changed_input_ids == ("metric:p5:diligence-adjusted-ebitda",)
    request = result.snapshot.recomputation_requests[0]
    assert request.analyst_approval_required
    assert request.updated_input_ids == stale.changed_input_ids
    assert state.valuation_outputs[0].midpoint == Decimal("950")

    updated = ReconciliationService().apply_staleness(state, result)
    version = next(
        item for item in updated.artifact_versions if item.artifact_id == stale.output_id
    )
    assert version.stale
    assert updated.valuation_outputs == state.valuation_outputs


def test_dependency_version_change_marks_only_dependent_output_stale() -> None:
    state = rich_reconciliation_state()
    versions = (
        ArtifactVersion("input:old", "1.0.0", "v1", superseded_by="input:new"),
        ArtifactVersion("output:dependent", "1.0.0", "v1", ("input:old",)),
        ArtifactVersion("output:unrelated", "1.0.0", "v1", ("input:other",)),
    )
    result = ReconciliationService().reconcile(replace(state, artifact_versions=versions))
    statuses = {item.output_id: item.status for item in result.snapshot.stale_outputs}
    assert statuses["input:old"] is ReconciliationStatus.SUPERSEDED
    assert statuses["output:dependent"] is ReconciliationStatus.STALE
    assert "output:unrelated" not in statuses


def test_superseded_input_creates_valuation_recompute_request() -> None:
    state = rich_reconciliation_state()
    metrics = tuple(
        item
        for item in state.financial_metrics
        if item.metric_id != "metric:p5:diligence-adjusted-ebitda"
    )
    versions = (
        ArtifactVersion("input:old", "1.0.0", "v1", superseded_by="input:new"),
        ArtifactVersion("valuation:p3:trading-comps", "1.0.0", "v1", ("input:old",)),
    )
    snapshot = (
        ReconciliationService()
        .reconcile(replace(state, financial_metrics=metrics, artifact_versions=versions))
        .snapshot
    )
    request = next(
        item
        for item in snapshot.recomputation_requests
        if item.source_output_id == "valuation:p3:trading-comps"
    )
    assert request.updated_input_ids == ("input:old",)


def test_valuation_methods_remain_separate_and_divergence_is_explicit() -> None:
    result = ReconciliationService().reconcile(rich_reconciliation_state())
    comparison = result.snapshot.valuation_comparison
    assert len(comparison.entries) == 2
    assert comparison.entries[0].valuation.midpoint == Decimal("950")
    assert comparison.entries[1].valuation.midpoint == Decimal("1075")
    assert comparison.midpoint_gap == Decimal("125")
    assert comparison.midpoint_gap_percent is not None
    assert comparison.overlapping_ranges is True
    assert any(
        issue.issue_type is ReconciliationIssueType.VALUATION_DIVERGENCE
        for issue in result.snapshot.issues
    )
    assert comparison.entries[1].source_warnings[0].code == "LOW_SAMPLE_SIZE"
