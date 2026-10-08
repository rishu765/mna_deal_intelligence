from ma_comparable_valuation.presentation import workflow_to_dict
from ma_comparable_valuation.workflow import OfflineValuationService


def test_offline_workflow_composes_all_existing_stages() -> None:
    result = OfflineValuationService().run()

    assert result.target_profile.target.identity.company_id == "targetco"
    assert len(result.universe.companies) == 5
    assert len(result.selection.selected_company_ids) == 5
    assert len(result.peer_set.snapshots) == 5
    assert len(result.valuation.multiple_sets) == 7
    assert len(result.valuation.ranges) == 2
    assert result.valuation.explanation is not None


def test_workflow_presentation_preserves_audit_metadata() -> None:
    payload = workflow_to_dict(OfflineValuationService().run())

    assert payload["schema_version"] == 1
    assert payload["target_profile"]["metrics"][0]["value"]
    assert payload["universe"]["companies"][0]["evidence_ids"]
    assert payload["selection"]["decisions"][0]["rationale"]
    snapshot = payload["peer_set"]["snapshots"][0]
    assert snapshot["financial_metrics"][0]["period"] == "LTM Jun-2026"
    assert snapshot["financial_metrics"][0]["currency"] == "INR"
    multiple_set = payload["valuation"]["multiple_sets"][0]
    assert multiple_set["statistics"]["percentile_method"] == "linear_interpolation_r7"
    assert multiple_set["observations"][0]["evidence_ids"]
    assert payload["valuation"]["ranges"][0]["mid"]["trace"]["input_ids"]


def test_explanation_can_be_disabled_without_changing_calculations() -> None:
    with_explanation = OfflineValuationService().run()
    without_explanation = OfflineValuationService().run(include_explanation=False)

    assert without_explanation.valuation.explanation is None
    assert without_explanation.valuation.ranges == with_explanation.valuation.ranges
