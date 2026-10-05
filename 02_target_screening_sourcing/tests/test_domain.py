from datetime import UTC, datetime

import pytest

from ma_target_screening import CandidateCompany, DiscoveryEvidence


def test_candidate_keeps_discovery_provenance() -> None:
    evidence = DiscoveryEvidence(
        source_type="user_list",
        source_name="Initial target list",
        source_uri="https://example.com/targets",
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        excerpt="Example Target",
    )

    candidate = CandidateCompany(
        canonical_name="Example Target",
        aliases=("ExampleTarget",),
        website_domain="example.com",
        country="India",
        discovery_evidence=(evidence,),
    )

    assert candidate.discovery_evidence == (evidence,)


def test_candidate_rejects_url_as_domain() -> None:
    with pytest.raises(ValueError, match="bare domain"):
        CandidateCompany(canonical_name="Example Target", website_domain="https://example.com")
