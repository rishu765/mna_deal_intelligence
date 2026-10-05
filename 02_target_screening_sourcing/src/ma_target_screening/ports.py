"""Narrow ports for future discovery and Project 1-backed enrichment adapters."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from ma_target_screening.domain import CandidateCompany, CandidateProfile

if TYPE_CHECKING:
    from ma_target_screening.discovery.models import DiscoveryRequest, ProviderDiscoveryResult


class DiscoveryProvider(Protocol):
    """Discover provider-neutral candidate records for a bounded request."""

    @property
    def provider_name(self) -> str: ...

    def discover(self, request: DiscoveryRequest) -> ProviderDiscoveryResult: ...


class CompanyResearchProvider(Protocol):
    """Enrich one known candidate through an evidence-backed research capability."""

    def research(self, candidate: CandidateCompany) -> CandidateProfile: ...
