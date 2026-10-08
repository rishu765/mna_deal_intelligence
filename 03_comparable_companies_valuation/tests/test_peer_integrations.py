from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from ma_comparable_valuation.project2_adapter import Project2Candidate, Project2CandidateAdapter


@dataclass(frozen=True)
class Identifier:
    scheme: str
    value: str


@dataclass(frozen=True)
class DiscoveryEvidence:
    source_type: str = "company_website"
    source_name: str = "Example"
    provider_name: str = "fixture"
    source_uri: str | None = "https://example.test"
    source_title: str | None = "Example company"
    observed_at: datetime | None = datetime(2026, 10, 1, tzinfo=UTC)
    excerpt: str | None = "Enterprise workflow software."


@dataclass(frozen=True)
class Candidate:
    canonical_name: str = "Example Co"
    website_domain: str | None = "example.test"
    country: str | None = "India"
    industry_tags: tuple[str, ...] = ("Software", "Enterprise Software")
    description: str | None = "Enterprise workflow software."
    identifiers: tuple[Identifier, ...] = (
        Identifier("ticker", "EXM"),
        Identifier("exchange", "NSE"),
    )
    discovery_evidence: tuple[DiscoveryEvidence, ...] = (DiscoveryEvidence(),)


def test_project2_candidate_adapter_is_structural_and_independent() -> None:
    adapter = Project2CandidateAdapter(datetime(2026, 10, 7, tzinfo=UTC))

    candidate = cast(Project2Candidate, Candidate())
    target = adapter.to_target(candidate)
    peer = adapter.to_comparable(candidate)

    assert target.identity.ticker == "EXM"
    assert target.industry == "Software"
    assert peer.sub_industry == "Enterprise Software"
    assert peer.website_domain == "example.test"
    assert peer.evidence[0].source_locator == "https://example.test"
