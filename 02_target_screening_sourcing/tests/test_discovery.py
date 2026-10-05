from __future__ import annotations

import json
from pathlib import Path

import pytest

from ma_target_screening.demo_discovery import main as demo_main
from ma_target_screening.discovery import (
    CandidateDiscoveryService,
    DeterministicQueryGenerator,
    DiscoveredCompanyRecord,
    DiscoveryLimits,
    DiscoveryQuery,
    DiscoveryRequest,
    DiscoverySettings,
    LocalDatasetDiscoveryProvider,
    ProviderDiscoveryResult,
    UserCandidateInput,
    UserSuppliedDiscoveryProvider,
)
from ma_target_screening.discovery.normalization import (
    candidate_from_record,
    deduplicate_candidates,
    normalize_domain,
)
from ma_target_screening.errors import DiscoveryError, DiscoveryUnavailableError
from ma_target_screening.thesis import AcquisitionThesis

ROOT = Path(__file__).parents[1]
DATASET = ROOT / "data" / "discovery_companies.json"
FINTECH_THESIS = ROOT / "examples" / "fintech-payments.json"


def load_fintech_thesis() -> AcquisitionThesis:
    return AcquisitionThesis.from_json(FINTECH_THESIS.read_text(encoding="utf-8"))


def test_query_generation_uses_industry_capability_and_geography() -> None:
    queries = DeterministicQueryGenerator().generate(load_fintech_thesis(), max_queries=6)

    texts = [query.text for query in queries]
    assert "Fintech companies India" in texts
    assert any("API infrastructure" in text and "India" in text for text in texts)
    assert len(queries) <= 6


def test_query_generation_obeys_limit() -> None:
    queries = DeterministicQueryGenerator().generate(load_fintech_thesis(), max_queries=2)
    assert len(queries) == 2


def test_local_provider_is_deterministic_and_preserves_query() -> None:
    provider = LocalDatasetDiscoveryProvider(DATASET)
    request = DiscoveryRequest(
        thesis_id="fintech",
        queries=(DiscoveryQuery("q1", "B2B fintech India", ("industry", "geography")),),
        max_candidates_per_query=3,
        overall_candidate_limit=3,
    )

    first = provider.discover(request)
    second = provider.discover(request)

    assert first == second
    assert first.candidates
    assert all(candidate.discovery_query == "B2B fintech India" for candidate in first.candidates)


def test_candidate_normalizes_url_without_verifying_snippet() -> None:
    candidate = candidate_from_record(
        DiscoveredCompanyRecord(
            observed_name="  Example   Labs Pvt. Ltd. ",
            provider_name="test",
            source_name="fixture",
            source_type="test_fixture",
            website="https://www.Example.com/path?utm_source=test",
            description="Unverified search snippet.",
            source_uri="https://search.example/result/1",
            discovery_query="example labs",
        )
    )

    assert candidate.canonical_name == "Example Labs Pvt. Ltd."
    assert candidate.website_domain == "example.com"
    assert candidate.description == "Unverified search snippet."
    assert candidate.discovery_evidence[0].excerpt == "Unverified search snippet."


def test_domain_normalization_rejects_non_domain() -> None:
    assert normalize_domain("www.Example.com/path") == "example.com"
    with pytest.raises(ValueError, match="invalid company website"):
        normalize_domain("localhost")


def test_deduplication_merges_domain_duplicates_and_provenance() -> None:
    records = (
        DiscoveredCompanyRecord(
            observed_name="Example Labs Private Limited",
            provider_name="provider_a",
            source_name="source-a",
            source_type="dataset",
            website="https://www.example.com",
            source_identifier="a-1",
        ),
        DiscoveredCompanyRecord(
            observed_name="Example Labs",
            provider_name="provider_b",
            source_name="source-b",
            source_type="user_list",
            website="example.com/about",
            source_identifier="b-1",
        ),
    )

    merged = deduplicate_candidates(tuple(candidate_from_record(item) for item in records))

    assert len(merged) == 1
    assert len(merged[0].discovery_evidence) == 2
    assert {item.provider_name for item in merged[0].discovery_evidence} == {
        "provider_a",
        "provider_b",
    }


def test_same_name_in_different_countries_is_not_merged() -> None:
    records = tuple(
        candidate_from_record(
            DiscoveredCompanyRecord(
                observed_name="Atlas Systems",
                provider_name=f"provider_{country}",
                source_name="fixture",
                source_type="dataset",
                country=country,
            )
        )
        for country in ("India", "Canada")
    )
    assert len(deduplicate_candidates(records)) == 2


def test_service_returns_unranked_universe_and_deduplication_counts() -> None:
    service = CandidateDiscoveryService(
        providers=(LocalDatasetDiscoveryProvider(DATASET),),
        limits=DiscoveryLimits(
            max_queries=6, max_candidates_per_query=5, overall_candidate_limit=20
        ),
    )

    result = service.discover(load_fintech_thesis())

    assert result.candidates
    assert result.raw_candidate_count > result.deduplicated_candidate_count
    assert result.provider_names == ("local_dataset",)
    assert all(candidate.discovery_evidence for candidate in result.candidates)


def test_user_supplied_candidates_merge_with_dataset() -> None:
    user_provider = UserSuppliedDiscoveryProvider(
        (
            UserCandidateInput(
                name="PayFlow Labs",
                website="https://payflow.example",
                country="India",
                source_reference="https://banker.example/longlist",
            ),
            UserCandidateInput(name="Management Suggested Co"),
        ),
        list_name="Banker longlist",
    )
    service = CandidateDiscoveryService(
        providers=(LocalDatasetDiscoveryProvider(DATASET), user_provider),
        limits=DiscoveryLimits(
            max_queries=2, max_candidates_per_query=5, overall_candidate_limit=20
        ),
    )

    result = service.discover(load_fintech_thesis())

    payflow = next(item for item in result.candidates if item.website_domain == "payflow.example")
    assert {e.provider_name for e in payflow.discovery_evidence} == {
        "local_dataset",
        "user_supplied",
    }
    assert any(item.canonical_name == "Management Suggested Co" for item in result.candidates)


def test_empty_results_are_explicit() -> None:
    service = CandidateDiscoveryService(
        providers=(UserSuppliedDiscoveryProvider(()),),
        limits=DiscoveryLimits(
            max_queries=1, max_candidates_per_query=1, overall_candidate_limit=1
        ),
    )

    result = service.discover(load_fintech_thesis())

    assert result.candidates == ()
    assert any("no candidates" in warning.casefold() for warning in result.warnings)


class FailingProvider:
    def __init__(self, name: str = "failing") -> None:
        self._name = name

    @property
    def provider_name(self) -> str:
        return self._name

    def discover(self, request: DiscoveryRequest) -> ProviderDiscoveryResult:
        raise DiscoveryError("simulated provider failure")


def test_partial_provider_failure_returns_candidates_and_warning() -> None:
    service = CandidateDiscoveryService(
        providers=(
            FailingProvider(),
            UserSuppliedDiscoveryProvider((UserCandidateInput("A Co"),)),
        ),
        limits=DiscoveryLimits(
            max_queries=1, max_candidates_per_query=2, overall_candidate_limit=2
        ),
    )

    result = service.discover(load_fintech_thesis())

    assert len(result.candidates) == 1
    assert "Discovery provider failed: failing" in result.warnings


def test_all_provider_failures_raise_unavailable() -> None:
    service = CandidateDiscoveryService(providers=(FailingProvider(),))
    with pytest.raises(DiscoveryUnavailableError, match="All configured"):
        service.discover(load_fintech_thesis())


def test_service_enforces_overall_limit() -> None:
    service = CandidateDiscoveryService(
        providers=(
            UserSuppliedDiscoveryProvider(
                tuple(UserCandidateInput(f"Candidate {index}") for index in range(5))
            ),
        ),
        limits=DiscoveryLimits(
            max_queries=1, max_candidates_per_query=2, overall_candidate_limit=2
        ),
    )
    assert len(service.discover(load_fintech_thesis()).candidates) == 2


def test_malformed_dataset_is_a_provider_failure(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("not-json", encoding="utf-8")
    service = CandidateDiscoveryService(providers=(LocalDatasetDiscoveryProvider(path),))
    with pytest.raises(DiscoveryUnavailableError):
        service.discover(load_fintech_thesis())


def test_discovery_settings_validate_environment_limits() -> None:
    settings = DiscoverySettings.from_env(
        {
            "MATS_DISCOVERY_MAX_QUERIES": "3",
            "MATS_DISCOVERY_MAX_CANDIDATES_PER_QUERY": "4",
            "MATS_DISCOVERY_OVERALL_CANDIDATE_LIMIT": "9",
            "MATS_DISCOVERY_DATASET_PATH": "fixtures/companies.json",
        }
    )

    assert settings.limits.max_queries == 3
    assert settings.dataset_path == Path("fixtures/companies.json")
    with pytest.raises(ValueError, match="must be integers"):
        DiscoverySettings.from_env({"MATS_DISCOVERY_MAX_QUERIES": "many"})


def test_offline_demo_prints_evidence_backed_candidate_set(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = demo_main(
        [
            "--thesis",
            str(FINTECH_THESIS),
            "--dataset",
            str(DATASET),
            "--max-queries",
            "2",
            "--max-candidates",
            "5",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["thesis_id"] == "india-b2b-fintech-2026"
    assert output["candidates"]
    assert output["candidates"][0]["discovery_evidence"]
