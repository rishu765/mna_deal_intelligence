"""Narrow ports for future discovery and Project 1-backed enrichment adapters."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from ma_target_screening.domain import CandidateCompany
from ma_target_screening.profile import CandidateProfile

if TYPE_CHECKING:
    from ma_target_screening.discovery.models import DiscoveryRequest, ProviderDiscoveryResult
    from ma_target_screening.enrichment.models import EnrichmentRequest, ProviderEnrichmentResult


class DiscoveryProvider(Protocol):
    """Discover provider-neutral candidate records for a bounded request."""

    @property
    def provider_name(self) -> str: ...

    def discover(self, request: DiscoveryRequest) -> ProviderDiscoveryResult: ...


class EnrichmentProvider(Protocol):
    """Return one evidence-backed partial profile from a bounded source."""

    @property
    def provider_name(self) -> str: ...

    def enrich(self, request: EnrichmentRequest) -> ProviderEnrichmentResult: ...


class CompanyResearchProvider(Protocol):
    """Legacy M0 boundary retained for compatible single-provider clients."""

    def research(self, candidate: CandidateCompany) -> CandidateProfile: ...
