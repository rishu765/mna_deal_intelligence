from ma_target_screening import (
    AcquirerIdentity,
    AcquisitionThesis,
    CandidateCompany,
    CandidateProfile,
)
from ma_target_screening.ports import CompanyResearchProvider, DiscoveryProvider


class StubDiscoveryProvider:
    @property
    def provider_name(self) -> str:
        return "stub"

    def discover(self, thesis: AcquisitionThesis) -> tuple[CandidateCompany, ...]:
        return (CandidateCompany(canonical_name=f"{thesis.acquirer.name} Target"),)


class StubResearchProvider:
    def research(self, candidate: CandidateCompany) -> CandidateProfile:
        return CandidateProfile(candidate=candidate, summary=None, evidence=())


def test_discovery_provider_contract_is_structural() -> None:
    provider: DiscoveryProvider = StubDiscoveryProvider()
    thesis = AcquisitionThesis(
        thesis_id="test-thesis",
        acquirer=AcquirerIdentity(name="Acquirer"),
        objective="Acquire capability",
    )

    assert provider.discover(thesis)[0].canonical_name == "Acquirer Target"


def test_company_research_provider_contract_is_structural() -> None:
    provider: CompanyResearchProvider = StubResearchProvider()
    candidate = CandidateCompany(canonical_name="Target")

    assert provider.research(candidate).candidate == candidate
