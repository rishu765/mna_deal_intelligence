from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest

from ma_target_screening.demo_enrichment import main as demo_main
from ma_target_screening.discovery import CandidateDiscoveryService, LocalDatasetDiscoveryProvider
from ma_target_screening.domain import CandidateCompany
from ma_target_screening.enrichment import (
    CandidateEnrichmentService,
    Project1DocumentResearchProvider,
    ProviderEnrichmentResult,
    StructuredFixtureEnrichmentProvider,
)
from ma_target_screening.enrichment.models import EnrichmentRequest
from ma_target_screening.enrichment.project1_adapter import (
    Project1ResearchClient,
    Project1ResearchProfile,
)
from ma_target_screening.errors import EnrichmentError
from ma_target_screening.profile import (
    CandidateProfile,
    EnrichmentEvidence,
    EnrichmentStatus,
    EvidenceQuality,
    ProfileField,
    ProfileFinancialMetric,
)
from ma_target_screening.thesis import AcquisitionThesis

ROOT = Path(__file__).parents[1]
THESIS_PATH = ROOT / "examples" / "fintech-payments.json"
DISCOVERY_DATA = ROOT / "data" / "discovery_companies.json"
ENRICHMENT_DATA = ROOT / "data" / "enrichment_profiles.json"


def thesis() -> AcquisitionThesis:
    return AcquisitionThesis.from_json(THESIS_PATH.read_text(encoding="utf-8"))


def candidate(domain: str = "payflow.example") -> CandidateCompany:
    result = CandidateDiscoveryService(
        providers=(LocalDatasetDiscoveryProvider(DISCOVERY_DATA),)
    ).discover(thesis())
    return next(item for item in result.candidates if item.website_domain == domain)


def evidence(provider: str = "test", evidence_id: str = "E1") -> EnrichmentEvidence:
    return EnrichmentEvidence(
        evidence_id=evidence_id,
        provider_name=provider,
        source_type="fixture",
        source_title="Synthetic source",
        source_reference="fixture/source.json",
        page_numbers=(1,),
        excerpt="Supporting source excerpt.",
        quality=EvidenceQuality.SUPPLIED,
    )


def test_fixture_enrichment_distinguishes_fact_inference_and_unknown() -> None:
    profile = CandidateEnrichmentService(
        providers=(StructuredFixtureEnrichmentProvider(ENRICHMENT_DATA),)
    ).enrich(candidate(), thesis())

    assert profile.status is EnrichmentStatus.COMPLETE_ENOUGH
    assert any(item.field is ProfileField.INDUSTRY for item in profile.facts)
    assert profile.inferences[0].field is ProfileField.MA_OBSERVATIONS
    assert any(item.field is ProfileField.EMPLOYEE_COUNT for item in profile.unknown_fields)
    assert all(item.evidence for item in profile.facts)
    assert all(item.evidence for item in profile.inferences)


def test_financial_metric_preserves_reported_metadata_and_evidence() -> None:
    profile = CandidateEnrichmentService(
        providers=(StructuredFixtureEnrichmentProvider(ENRICHMENT_DATA),)
    ).enrich(candidate(), thesis())

    metric = profile.financial_metrics[0]
    assert (
        metric.metric_name,
        metric.value,
        metric.currency,
        metric.unit,
        metric.fiscal_period,
        metric.basis,
    ) == ("Revenue", "320", "INR", "crore", "FY2025", "reported revenue")
    assert metric.evidence[0].evidence_id == "payflow-financials-1"


def test_thesis_prioritizes_fields_without_screening() -> None:
    fields = CandidateEnrichmentService.priority_fields(thesis())

    assert ProfileField.FINANCIALS in fields
    assert ProfileField.PROFITABILITY in fields
    assert ProfileField.TECHNOLOGY in fields
    assert ProfileField.GEOGRAPHIES in fields


def test_partial_fixture_profile_retains_missing_fields() -> None:
    profile = CandidateEnrichmentService(
        providers=(StructuredFixtureEnrichmentProvider(ENRICHMENT_DATA),)
    ).enrich(candidate("cashgrid.example"), thesis())

    assert profile.status is EnrichmentStatus.PARTIAL
    assert profile.facts
    assert ProfileField.FINANCIALS in {item.field for item in profile.unknown_fields}


def test_unmatched_fixture_returns_insufficient_profile() -> None:
    profile = CandidateEnrichmentService(
        providers=(StructuredFixtureEnrichmentProvider(ENRICHMENT_DATA),)
    ).enrich(CandidateCompany(canonical_name="Unknown Co"), thesis())

    assert profile.status is EnrichmentStatus.INSUFFICIENT_EVIDENCE
    assert profile.facts == ()
    assert set(profile.requested_fields) == {item.field for item in profile.unknown_fields}


@dataclass(frozen=True)
class StaticProvider:
    provider_name: str
    result: ProviderEnrichmentResult

    def enrich(self, request: EnrichmentRequest) -> ProviderEnrichmentResult:
        return self.result


def test_multi_source_financial_conflict_preserves_both_values() -> None:
    first_evidence = evidence("source_a", "A1")
    second_evidence = evidence("source_b", "B1")
    first = ProviderEnrichmentResult(
        provider_name="source_a",
        financial_metrics=(
            ProfileFinancialMetric(
                "Revenue", "320", "FY2025", "crore", "INR", "reported", (first_evidence,)
            ),
        ),
    )
    second = ProviderEnrichmentResult(
        provider_name="source_b",
        financial_metrics=(
            ProfileFinancialMetric(
                "Revenue", "350", "FY2025", "crore", "INR", "reported", (second_evidence,)
            ),
        ),
    )

    profile = CandidateEnrichmentService(
        providers=(StaticProvider("source_a", first), StaticProvider("source_b", second))
    ).enrich(candidate(), thesis())

    assert len(profile.financial_metrics) == 2
    assert profile.status is EnrichmentStatus.PARTIAL
    assert {item.value for item in profile.conflicts[0].alternatives} == {"320", "350"}


class FailingProvider:
    provider_name = "failing"

    def enrich(self, request: EnrichmentRequest) -> ProviderEnrichmentResult:
        raise EnrichmentError("simulated failure")


def test_partial_provider_failure_preserves_successful_data() -> None:
    profile = CandidateEnrichmentService(
        providers=(
            FailingProvider(),
            StructuredFixtureEnrichmentProvider(ENRICHMENT_DATA),
        )
    ).enrich(candidate(), thesis())

    assert profile.facts
    assert "structured_fixture" in profile.provider_names
    assert any("partial results" in warning for warning in profile.warnings)


def test_all_provider_failure_returns_profile_instead_of_discarding_candidate() -> None:
    profile = CandidateEnrichmentService(providers=(FailingProvider(),)).enrich(
        candidate(), thesis()
    )

    assert profile.candidate.website_domain == "payflow.example"
    assert profile.status is EnrichmentStatus.PROVIDER_FAILURE
    assert profile.provider_names == ()


def test_profile_serialization_round_trip_preserves_discovery_and_enrichment_evidence() -> None:
    profile = CandidateEnrichmentService(
        providers=(StructuredFixtureEnrichmentProvider(ENRICHMENT_DATA),)
    ).enrich(candidate(), thesis())

    restored = CandidateProfile.from_json(profile.to_json())

    assert restored == profile
    assert json.loads(profile.to_json())["schema_version"] == 1


@dataclass(frozen=True)
class FakeSectionKey:
    value: str


@dataclass(frozen=True)
class FakeCitation:
    reference_number: int = 1
    chunk_id: str = "chunk-1"
    document_id: str = "document-1"
    source_filename: str = "annual-report.pdf"
    source_title: str | None = "Annual Report FY2025"
    canonical_page_numbers: tuple[int, ...] = (7,)
    excerpt: str = "The company provides payment APIs in India."


@dataclass(frozen=True)
class FakeFact:
    statement: str
    citations: tuple[FakeCitation, ...]


@dataclass(frozen=True)
class FakeObservation:
    observation: str
    citations: tuple[FakeCitation, ...]


@dataclass(frozen=True)
class FakeMetric:
    metric_name: str
    value: str
    fiscal_period: str | None
    unit: str | None
    currency: str | None
    basis: str | None
    citations: tuple[FakeCitation, ...]


@dataclass(frozen=True)
class FakeSection:
    key: FakeSectionKey
    summary: str | None
    facts: tuple[FakeFact, ...]
    observations: tuple[FakeObservation, ...]
    financial_metrics: tuple[FakeMetric, ...]
    citations: tuple[FakeCitation, ...]
    insufficient_evidence: bool


@dataclass(frozen=True)
class FakeProfile:
    sections: tuple[FakeSection, ...]
    warnings: tuple[str, ...] = ()


class FakeProject1Client:
    def __init__(self, profile: FakeProfile) -> None:
        self.profile = profile
        self.calls: list[str | None] = []

    def research(self, *, company_name: str | None) -> Project1ResearchProfile:
        self.calls.append(company_name)
        return cast(Project1ResearchProfile, self.profile)


def test_project1_adapter_maps_public_research_profile_without_deep_imports() -> None:
    citation = FakeCitation()
    fake_profile = FakeProfile(
        sections=(
            FakeSection(
                key=FakeSectionKey("business_overview"),
                summary="Payment API provider.",
                facts=(FakeFact("The company provides payment APIs.", (citation,)),),
                observations=(),
                financial_metrics=(),
                citations=(citation,),
                insufficient_evidence=False,
            ),
            FakeSection(
                key=FakeSectionKey("financial_highlights"),
                summary=None,
                facts=(),
                observations=(),
                financial_metrics=(
                    FakeMetric("Revenue", "320", "FY2025", "crore", "INR", "reported", (citation,)),
                ),
                citations=(citation,),
                insufficient_evidence=False,
            ),
            FakeSection(
                key=FakeSectionKey("ma_relevant_observations"),
                summary=None,
                facts=(),
                observations=(FakeObservation("APIs may complement the acquirer.", (citation,)),),
                financial_metrics=(),
                citations=(citation,),
                insufficient_evidence=False,
            ),
        )
    )
    client = FakeProject1Client(fake_profile)
    provider = Project1DocumentResearchProvider(cast(Project1ResearchClient, client))
    profile = CandidateEnrichmentService(providers=(provider,)).enrich(
        candidate(), thesis(), document_references=("annual-report.pdf",)
    )

    assert client.calls == ["PayFlow Labs Private Limited"]
    assert profile.facts[0].evidence[0].document_id == "document-1"
    assert profile.financial_metrics[0].currency == "INR"
    assert profile.inferences[0].field is ProfileField.MA_OBSERVATIONS


def test_project1_adapter_skips_cleanly_without_documents() -> None:
    client = FakeProject1Client(FakeProfile(()))
    provider = Project1DocumentResearchProvider(cast(Project1ResearchClient, client))

    profile = CandidateEnrichmentService(providers=(provider,)).enrich(candidate(), thesis())

    assert client.calls == []
    assert profile.status is EnrichmentStatus.INSUFFICIENT_EVIDENCE
    assert any("documents were unavailable" in warning for warning in profile.warnings)


def test_offline_enrichment_demo(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = demo_main(
        [
            "--thesis",
            str(THESIS_PATH),
            "--discovery-data",
            str(DISCOVERY_DATA),
            "--enrichment-data",
            str(ENRICHMENT_DATA),
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["candidate"]["website_domain"] == "payflow.example"
    assert output["facts"]
    assert output["financial_metrics"]
