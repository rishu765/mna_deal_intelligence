"""Narrow ports for future discovery and Project 1-backed enrichment adapters."""

from __future__ import annotations

from typing import Protocol

from ma_target_screening.domain import CandidateCompany, CandidateProfile
from ma_target_screening.thesis import AcquisitionThesis


class DiscoveryProvider(Protocol):
    """Discover candidates without exposing a search or data vendor to the core."""

    @property
    def provider_name(self) -> str: ...

    def discover(self, thesis: AcquisitionThesis) -> tuple[CandidateCompany, ...]: ...


class CompanyResearchProvider(Protocol):
    """Enrich one known candidate through an evidence-backed research capability."""

    def research(self, candidate: CandidateCompany) -> CandidateProfile: ...
