from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from ma_deal_intelligence.orchestration import SuperAgentApplication, build_workflow
from ma_deal_intelligence.planning_fixtures import fixture_requests, fixture_state
from ma_deal_intelligence.reconciliation import ReconciliationService
from ma_deal_intelligence.reconciliation_fixtures import rich_reconciliation_state
from ma_deal_intelligence.reconciliation_models import ReconciliationResult
from ma_deal_intelligence.state import DealState
from ma_deal_intelligence.synthesis import (
    CitationRenderer,
    DealAssessment,
    FinalDealIntelligenceOutput,
    SynthesisGuard,
    SynthesisService,
    SynthesisValidationError,
)


def _output() -> tuple[DealState, ReconciliationResult, FinalDealIntelligenceOutput]:
    state = rich_reconciliation_state()
    reconciliation = ReconciliationService().reconcile(state)
    output = SynthesisService().build(
        run_id="run:synthesis:test",
        deal_state=state,
        reconciliation=reconciliation,
        completed_capabilities=("p1", "p2", "p3", "p4", "p5"),
    )
    return state, reconciliation, output


def test_synthesis_preserves_specialist_values_sections_and_citations() -> None:
    state, _, output = _output()
    assert {item.section_id for item in output.sections} >= {
        "trading_comps",
        "precedents",
        "due_diligence",
        "unified_valuation",
        "reconciliation",
        "open_questions",
    }
    assert [(item.low, item.midpoint, item.high) for item in output.valuations] == [
        (item.low, item.midpoint, item.high) for item in state.valuation_outputs
    ]
    assert {item.value for item in output.material_metrics} >= {Decimal("100"), Decimal("85")}
    assert output.assessment.classification in {
        DealAssessment.ATTRACTIVE_WITH_CONDITIONS,
        DealAssessment.HIGH_RISK,
    }
    assert output.citations
    assert set(output.evidence_refs) <= {item.evidence_id for item in state.evidence}


def test_synthesis_validation_rejects_changed_specialist_number() -> None:
    state, _, output = _output()
    changed = replace(
        output,
        valuations=(replace(output.valuations[0], midpoint=Decimal("999")), *output.valuations[1:]),
    )
    with pytest.raises(SynthesisValidationError, match="valuation mismatch"):
        SynthesisService.validate(changed, state)


def test_narrative_guard_rejects_unsupported_numeric_claim() -> None:
    with pytest.raises(SynthesisValidationError, match="unsupported numeric"):
        SynthesisGuard.validate_numeric_mentions("Enterprise value is 777.", (Decimal("1000"),))


def test_narrative_guard_rejects_unsupported_entity_or_risk_terms() -> None:
    with pytest.raises(SynthesisValidationError, match="unsupported terms"):
        SynthesisGuard.validate_grounded_narrative(
            "TargetCo has a CyberNova breach.",
            "TargetCo has a high risk assessment.",
            (),
        )


def test_citation_renderer_retains_precise_spreadsheet_locator() -> None:
    state = rich_reconciliation_state()
    evidence = next(item for item in state.evidence if item.cell_range)
    citation = CitationRenderer.render(evidence)
    assert evidence.cell_range is not None
    assert evidence.cell_range in citation.label
    assert evidence.sheet_name is not None
    assert evidence.sheet_name in citation.label


def test_terminal_graph_run_contains_validated_final_output() -> None:
    state = SuperAgentApplication(build_workflow()).start(
        fixture_requests()["compare"],
        fixture_state(financials=True),
        thread_id="synthesis:terminal",
    )
    assert state["final_output"] is not None
    assert state["terminal_result"].final_output == state["final_output"]
    assert len(state["final_output"].valuations) == 2
