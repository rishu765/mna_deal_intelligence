from __future__ import annotations

import json
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path

import pytest

from ma_target_screening.demo_screening import main as demo_main
from ma_target_screening.discovery import CandidateDiscoveryService, LocalDatasetDiscoveryProvider
from ma_target_screening.domain import CandidateCompany
from ma_target_screening.enrichment import (
    CandidateEnrichmentService,
    StructuredFixtureEnrichmentProvider,
)
from ma_target_screening.errors import StrategicFitError
from ma_target_screening.profile import CandidateProfile
from ma_target_screening.screening import (
    CriterionOutcome,
    DeterministicScreeningEngine,
    EligibilityStatus,
    FixtureStrategicFitProvider,
    ScreeningRankingService,
    SemanticAssessmentOutput,
    StrategicFitRequest,
    StrategicFitService,
    StructuredLLMStrategicFitProvider,
)
from ma_target_screening.thesis import (
    AcquirerIdentity,
    AcquisitionThesis,
    CriterionCategory,
    CriterionOperator,
    CriterionPriority,
    CriterionRequirement,
    CriterionValueType,
    EvaluationMethod,
    ScreeningCriterion,
)

ROOT = Path(__file__).parents[1]
THESIS_PATH = ROOT / "examples" / "screening-ranking-demo.json"
DISCOVERY_DATA = ROOT / "data" / "discovery_companies.json"
ENRICHMENT_DATA = ROOT / "data" / "enrichment_profiles.json"
STRATEGIC_DATA = ROOT / "data" / "strategic_fit_assessments.json"


def thesis() -> AcquisitionThesis:
    return AcquisitionThesis.from_json(THESIS_PATH.read_text(encoding="utf-8"))


def profiles() -> dict[str, CandidateProfile]:
    active_thesis = thesis()
    discovery = CandidateDiscoveryService(
        providers=(LocalDatasetDiscoveryProvider(DISCOVERY_DATA),)
    ).discover(active_thesis)
    enrichment = CandidateEnrichmentService(
        providers=(StructuredFixtureEnrichmentProvider(ENRICHMENT_DATA),)
    )
    wanted = {
        "payflow.example",
        "ledgerbridge.example",
        "cashgrid.example",
        "consumercredit.example",
    }
    return {
        item.website_domain: enrichment.enrich(item, active_thesis)
        for item in discovery.candidates
        if item.website_domain in wanted
    }


def service() -> ScreeningRankingService:
    return ScreeningRankingService(
        strategic_fit_service=StrategicFitService(FixtureStrategicFitProvider(STRATEGIC_DATA))
    )


def test_hard_constraints_pass_and_fail_with_criterion_evidence() -> None:
    candidates = profiles()
    payflow = service().evaluate_candidate(thesis(), candidates["payflow.example"])
    consumer = service().evaluate_candidate(thesis(), candidates["consumercredit.example"])

    revenue = next(item for item in payflow.evaluations if item.criterion_id == "fy2025-revenue")
    industry = next(item for item in consumer.evaluations if item.criterion_id == "industry-fit")
    assert revenue.outcome is CriterionOutcome.PASS
    assert revenue.evidence[0].evidence_id == "payflow-financials-1"
    assert industry.outcome is CriterionOutcome.FAIL
    assert consumer.eligibility is EligibilityStatus.INELIGIBLE


def test_unknown_hard_criterion_requires_review_instead_of_failing() -> None:
    cashgrid = service().evaluate_candidate(thesis(), profiles()["cashgrid.example"])

    revenue = next(item for item in cashgrid.evaluations if item.criterion_id == "fy2025-revenue")
    assert revenue.outcome is CriterionOutcome.UNKNOWN
    assert revenue.score is None
    assert cashgrid.eligibility is EligibilityStatus.REVIEW_REQUIRED


def test_exclusion_is_auditable_and_disqualifies_when_triggered() -> None:
    consumer = service().evaluate_candidate(thesis(), profiles()["consumercredit.example"])
    excluded = next(
        item for item in consumer.evaluations if item.criterion_id == "exclude-consumer-lending"
    )

    assert excluded.requirement is CriterionRequirement.EXCLUSION
    assert excluded.outcome is CriterionOutcome.FAIL
    assert excluded.evidence[0].evidence_id == "consumercredit-profile-1"
    assert "triggered" in excluded.reason


def test_soft_deterministic_criterion_contributes_without_gating() -> None:
    payflow = service().evaluate_candidate(thesis(), profiles()["payflow.example"])
    customer_fit = next(
        item for item in payflow.evaluations if item.criterion_id == "enterprise-customers"
    )

    assert customer_fit.outcome is CriterionOutcome.PASS
    assert customer_fit.score == Decimal("1")
    assert customer_fit.weight == Decimal("0.20")


def test_financial_range_comparison_passes_and_fails() -> None:
    active_thesis = thesis()
    profile = profiles()["payflow.example"]
    criterion = next(
        item for item in active_thesis.criteria if item.category is CriterionCategory.REVENUE
    )
    engine = DeterministicScreeningEngine()
    passed = engine.evaluate_criterion(profile, criterion)
    metric = replace(profile.financial_metrics[0], value="750")
    failed = engine.evaluate_criterion(replace(profile, financial_metrics=(metric,)), criterion)

    assert passed.outcome is CriterionOutcome.PASS
    assert failed.outcome is CriterionOutcome.FAIL


@pytest.mark.parametrize(
    ("field", "value"),
    [("currency", "USD"), ("unit", "million"), ("fiscal_period", "FY2024")],
)
def test_incompatible_financial_basis_is_unknown(field: str, value: str) -> None:
    active_thesis = thesis()
    profile = profiles()["payflow.example"]
    criterion = next(
        item for item in active_thesis.criteria if item.category is CriterionCategory.REVENUE
    )
    original = profile.financial_metrics[0]
    if field == "currency":
        metric = replace(original, currency=value)
    elif field == "unit":
        metric = replace(original, unit=value)
    else:
        metric = replace(original, fiscal_period=value)

    result = DeterministicScreeningEngine().evaluate_criterion(
        replace(profile, financial_metrics=(metric,)), criterion
    )

    assert result.outcome is CriterionOutcome.UNKNOWN
    assert "not comparable" in result.reason


def test_unsupported_deterministic_category_returns_unknown() -> None:
    original = AcquisitionThesis.from_json(
        (ROOT / "examples" / "fintech-payments.json").read_text(encoding="utf-8")
    )
    criterion = next(item for item in original.criteria if item.category is CriterionCategory.OTHER)

    result = DeterministicScreeningEngine().evaluate_criterion(
        profiles()["payflow.example"], criterion
    )

    assert result.outcome is CriterionOutcome.UNKNOWN
    assert "No deterministic" in result.reason


def test_strategic_fit_output_is_structured_and_grounded() -> None:
    result = service().evaluate_candidate(thesis(), profiles()["payflow.example"])
    semantic = next(
        item for item in result.evaluations if item.criterion_id == "api-complementarity"
    )

    assert semantic.outcome is CriterionOutcome.PASS
    assert semantic.score == Decimal("0.90")
    assert [item.evidence_id for item in semantic.evidence] == ["payflow-tech-1"]
    assert result.strategic_fit.score == Decimal("88.1")


class CapturingGenerationClient:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.system_prompt = ""
        self.user_prompt = ""

    def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, object]:
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return self.response


def test_structured_llm_boundary_supplies_only_groundable_profile_evidence() -> None:
    client = CapturingGenerationClient(
        {
            "criterion_id": "api-complementarity",
            "outcome": "pass",
            "score": "0.8",
            "reason": "The cited API evidence supports complementarity.",
            "evidence_ids": ["payflow-tech-1"],
            "uncertainty": None,
        }
    )
    provider = StructuredLLMStrategicFitProvider(client)
    active_thesis = thesis()
    criterion = next(
        item for item in active_thesis.criteria if item.criterion_id == "api-complementarity"
    )

    output = provider.assess(
        StrategicFitRequest(active_thesis, profiles()["payflow.example"], criterion)
    )

    assert output.score == Decimal("0.8")
    assert "Use only the supplied" in client.system_prompt
    prompt = json.loads(client.user_prompt)
    assert prompt["candidate"] == "PayFlow Labs Private Limited"
    assert any("payflow-tech-1" in item["evidence_ids"] for item in prompt["facts"])


def test_malformed_structured_semantic_output_becomes_unknown() -> None:
    client = CapturingGenerationClient(
        {
            "criterion_id": "api-complementarity",
            "outcome": "definitely",
            "score": "2",
            "reason": "Malformed.",
            "evidence_ids": ["payflow-tech-1"],
        }
    )
    assessment = StrategicFitService(StructuredLLMStrategicFitProvider(client)).assess(
        thesis(), profiles()["payflow.example"]
    )

    assert all(item.outcome is CriterionOutcome.UNKNOWN for item in assessment.evaluations)
    assert assessment.warnings


def test_semantic_outcome_and_score_band_must_agree() -> None:
    with pytest.raises(ValueError, match="pass semantic output"):
        SemanticAssessmentOutput(
            criterion_id="api-complementarity",
            outcome=CriterionOutcome.PASS,
            reason="Inconsistent score.",
            score=Decimal("0.20"),
            evidence_ids=("payflow-tech-1",),
        )


@dataclass(frozen=True)
class BadEvidenceProvider:
    provider_name: str = "bad_evidence"

    def assess(self, request: StrategicFitRequest) -> SemanticAssessmentOutput:
        return SemanticAssessmentOutput(
            criterion_id=request.criterion.criterion_id,
            outcome=CriterionOutcome.PASS,
            reason="Unsupported claim.",
            score=Decimal("1"),
            evidence_ids=("invented-evidence",),
        )


def test_unsupported_semantic_evidence_becomes_unknown() -> None:
    assessment = StrategicFitService(BadEvidenceProvider()).assess(
        thesis(), profiles()["payflow.example"]
    )

    assert all(item.outcome is CriterionOutcome.UNKNOWN for item in assessment.evaluations)
    assert assessment.score is None
    assert assessment.warnings


@dataclass(frozen=True)
class FailingSemanticProvider:
    provider_name: str = "failing"

    def assess(self, request: StrategicFitRequest) -> SemanticAssessmentOutput:
        raise StrategicFitError("simulated provider failure")


def test_semantic_provider_failure_preserves_deterministic_results() -> None:
    screening = ScreeningRankingService(
        strategic_fit_service=StrategicFitService(FailingSemanticProvider())
    ).evaluate_candidate(thesis(), profiles()["payflow.example"])

    assert any(item.outcome is CriterionOutcome.PASS for item in screening.evaluations)
    assert all(
        item.outcome is CriterionOutcome.UNKNOWN for item in screening.strategic_fit.evaluations
    )
    assert screening.eligibility is EligibilityStatus.ELIGIBLE


def test_scoring_formula_and_missing_data_discount_are_interpretable() -> None:
    candidates = profiles()
    payflow = service().evaluate_candidate(thesis(), candidates["payflow.example"])
    cashgrid = service().evaluate_candidate(thesis(), candidates["cashgrid.example"])

    assert payflow.scores.raw_fit_score == Decimal("90.5")
    assert payflow.scores.evidence_coverage == Decimal("1.000")
    assert payflow.scores.final_score == Decimal("90.5")
    assert cashgrid.scores.raw_fit_score == Decimal("45.0")
    assert cashgrid.scores.evidence_coverage == Decimal("0.300")
    assert cashgrid.scores.final_score == Decimal("29.2")


def test_priority_weights_apply_when_explicit_weight_is_absent() -> None:
    custom = AcquisitionThesis(
        thesis_id="priority-test",
        acquirer=AcquirerIdentity("Acquirer"),
        criteria=(
            ScreeningCriterion(
                "industry",
                CriterionCategory.INDUSTRY,
                CriterionRequirement.SOFT,
                CriterionValueType.CATEGORICAL,
                CriterionOperator.CONTAINS,
                "Fintech",
                EvaluationMethod.DETERMINISTIC,
                priority=CriterionPriority.HIGH,
            ),
            ScreeningCriterion(
                "geography",
                CriterionCategory.GEOGRAPHY,
                CriterionRequirement.SOFT,
                CriterionValueType.GEOGRAPHIC,
                CriterionOperator.IN,
                ("Germany",),
                EvaluationMethod.DETERMINISTIC,
                priority=CriterionPriority.LOW,
            ),
        ),
    )

    result = service().evaluate_candidate(custom, profiles()["payflow.example"])

    assert result.scores.deterministic_soft_score == Decimal("75.0")
    assert result.scores.final_score == Decimal("75.0")


def test_hard_failed_candidate_is_retained_but_excluded_from_shortlist() -> None:
    candidates = profiles()
    shortlist = service().build_shortlist(thesis(), tuple(candidates.values()))

    ranked_domains = {
        item.result.profile.candidate.website_domain for item in shortlist.ranked_candidates
    }
    assert "consumercredit.example" not in ranked_domains
    assert any(
        result.profile.candidate.website_domain == "consumercredit.example"
        for result in shortlist.screening_results
    )


def test_full_fixture_flow_ranks_eligible_then_review_candidate() -> None:
    candidates = profiles()
    shortlist = service().build_shortlist(thesis(), tuple(candidates.values()))

    assert [
        item.result.profile.candidate.website_domain for item in shortlist.ranked_candidates
    ] == ["payflow.example", "ledgerbridge.example", "cashgrid.example"]
    assert [item.rank for item in shortlist.ranked_candidates] == [1, 2, 3]
    assert shortlist.ranked_candidates[0].key_strengths
    assert shortlist.ranked_candidates[2].key_weaknesses


def test_ties_are_broken_by_normalized_candidate_name() -> None:
    custom = AcquisitionThesis(
        thesis_id="tie-test",
        acquirer=AcquirerIdentity("Acquirer"),
        criteria=(
            ScreeningCriterion(
                "industry",
                CriterionCategory.INDUSTRY,
                CriterionRequirement.SOFT,
                CriterionValueType.CATEGORICAL,
                CriterionOperator.CONTAINS,
                "Fintech",
                EvaluationMethod.DETERMINISTIC,
            ),
        ),
    )
    source = profiles()["payflow.example"]
    alpha = replace(source, candidate=replace(source.candidate, canonical_name="Alpha Co"))
    zeta = replace(source, candidate=replace(source.candidate, canonical_name="Zeta Co"))

    shortlist = service().build_shortlist(custom, (zeta, alpha))

    assert [
        item.result.profile.candidate.canonical_name for item in shortlist.ranked_candidates
    ] == [
        "Alpha Co",
        "Zeta Co",
    ]


def test_empty_candidate_list_returns_empty_shortlist_with_warning() -> None:
    shortlist = service().build_shortlist(thesis(), ())

    assert shortlist.ranked_candidates == ()
    assert shortlist.screening_results == ()
    assert shortlist.warnings == ("No candidate profiles were supplied.",)


def test_all_hard_failures_return_auditable_results_without_shortlist_entries() -> None:
    consumer = profiles()["consumercredit.example"]
    second = replace(
        consumer,
        candidate=CandidateCompany(
            canonical_name="Another Consumer Lender",
            website_domain="another-consumer.example",
        ),
    )
    shortlist = service().build_shortlist(thesis(), (consumer, second))

    assert shortlist.ranked_candidates == ()
    assert len(shortlist.screening_results) == 2
    assert "No candidate remained" in shortlist.warnings[0]


def test_shortlist_serialization_exposes_scores_reasons_and_evidence_ids() -> None:
    shortlist = service().build_shortlist(thesis(), tuple(profiles().values()))

    payload = shortlist.to_dict()

    assert payload["ranked_candidates"][0]["final_score"] == "90.5"
    assert payload["ranked_candidates"][0]["criteria"][0]["evidence_ids"]
    assert payload["excluded_candidates"][0]["failed_criteria"]


def test_offline_screening_demo(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = demo_main(
        [
            "--thesis",
            str(THESIS_PATH),
            "--discovery-data",
            str(DISCOVERY_DATA),
            "--enrichment-data",
            str(ENRICHMENT_DATA),
            "--strategic-fit-data",
            str(STRATEGIC_DATA),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert [item["domain"] for item in payload["ranked_candidates"]] == [
        "payflow.example",
        "ledgerbridge.example",
        "cashgrid.example",
    ]
    assert payload["excluded_candidates"][0]["candidate"] == "ConsumerCredit Hub"
