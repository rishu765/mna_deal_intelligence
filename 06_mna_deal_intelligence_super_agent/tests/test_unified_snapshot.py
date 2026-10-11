from __future__ import annotations

from dataclasses import replace

from ma_deal_intelligence.evidence import ProjectId
from ma_deal_intelligence.reconciliation import ReconciliationService
from ma_deal_intelligence.reconciliation_fixtures import rich_reconciliation_state
from ma_deal_intelligence.reconciliation_models import (
    ReconciliationIssueType,
    ReconciliationTraceType,
    ReviewPriority,
    ThesisPosition,
)


def test_rich_snapshot_links_diligence_to_valuation_and_execution() -> None:
    result = ReconciliationService().reconcile(rich_reconciliation_state())
    snapshot = result.snapshot
    categories = {item.category for item in snapshot.impact_insights}
    assert {
        "valuation_input",
        "valuation_confidence",
        "equity_value_context",
        "deal_execution",
    } <= categories
    ebitda = next(item for item in snapshot.impact_insights if item.category == "valuation_input")
    assert str(ebitda.quantified_delta) == "-15"
    assert str(ebitda.quantified_delta_percent) == "-0.15"
    assert snapshot.related_insights


def test_review_queue_prioritizes_material_unresolved_items_and_deduplicates() -> None:
    result = ReconciliationService().reconcile(rich_reconciliation_state())
    queue = result.snapshot.review_queue
    assert queue
    assert queue[0].priority in {ReviewPriority.CRITICAL, ReviewPriority.HIGH}
    assert len({item.subject_id for item in queue}) == len(queue)
    aligned_metric_issue_ids = {
        issue.issue_id for issue in result.snapshot.issues if issue.status.value == "aligned"
    }
    assert all(not aligned_metric_issue_ids.intersection(item.issue_ids) for item in queue)


def test_unified_snapshot_preserves_all_projects_lineage_questions_and_scenarios() -> None:
    state = rich_reconciliation_state()
    result = ReconciliationService().reconcile(state)
    snapshot = result.snapshot
    assert state.company_intelligence
    assert state.target_screening_results
    assert len(snapshot.valuation_comparison.entries) == 2
    assert snapshot.diligence_findings == state.diligence_findings
    assert snapshot.evidence_refs == tuple(item.evidence_id for item in state.evidence)
    assert snapshot.lineage == state.lineage
    assert snapshot.warnings
    assert snapshot.stale_outputs
    assert any("consent" in item.question.casefold() for item in snapshot.open_questions)
    assert {item.name for item in snapshot.scenarios.scenarios} >= {
        "Reported EBITDA",
        "Diligence-adjusted EBITDA",
    }
    adjusted_scenario = next(
        item
        for item in snapshot.scenarios.scenarios
        if item.scenario_id == "scenario:diligence-adjusted"
    )
    assert adjusted_scenario.affected_output_ids == ("valuation:p3:trading-comps",)
    assert adjusted_scenario.recomputation_request_ids
    assert any(item.position is ThesisPosition.SUPPORTS for item in snapshot.thesis_evidence)
    assert any(item.position is ThesisPosition.CHALLENGES for item in snapshot.thesis_evidence)
    assert result.trace
    trace_types = {item.event_type for item in result.trace}
    assert ReconciliationTraceType.ISSUE_EMITTED in trace_types
    assert ReconciliationTraceType.RESOLUTION_APPLIED in trace_types


def test_missing_project_output_produces_partial_view() -> None:
    state = replace(
        rich_reconciliation_state(),
        precedent_transaction_results=(),
        valuation_outputs=(rich_reconciliation_state().valuation_outputs[0],),
    )
    snapshot = ReconciliationService().reconcile(state).snapshot
    assert len(snapshot.valuation_comparison.entries) == 1
    assert any(
        issue.issue_type is ReconciliationIssueType.MISSING_DEPENDENCY
        and issue.affected_projects == (ProjectId.PROJECT_4,)
        for issue in snapshot.issues
    )


def test_incompatible_schema_and_missing_evidence_are_structured_issues() -> None:
    state = rich_reconciliation_state()
    bad_p1 = replace(state.company_intelligence[0], schema_version="9.0.0")
    bad_metric = replace(state.financial_metrics[0], evidence_refs=("evidence:missing",))
    state = replace(
        state,
        company_intelligence=(bad_p1,),
        financial_metrics=(bad_metric, *state.financial_metrics[1:]),
    )
    issues = ReconciliationService().reconcile(state).snapshot.issues
    assert any("Unsupported specialist schema" in issue.description for issue in issues)
    assert any(issue.subject_id == "evidence:missing" for issue in issues)
