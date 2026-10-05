from pathlib import Path

from ma_target_screening.discovery import DiscoveryQuery, DiscoveryRequest
from ma_target_screening.discovery.providers import LocalDatasetDiscoveryProvider
from ma_target_screening.ports import DiscoveryProvider


def test_discovery_provider_contract_is_structural() -> None:
    provider: DiscoveryProvider = LocalDatasetDiscoveryProvider(
        Path("data/discovery_companies.json")
    )
    request = DiscoveryRequest(
        thesis_id="test-thesis",
        queries=(DiscoveryQuery("q1", "fintech companies India", ("industry", "geography")),),
        max_candidates_per_query=2,
        overall_candidate_limit=2,
    )

    result = provider.discover(request)

    assert result.provider_name == "local_dataset"
    assert len(result.candidates) == 2
