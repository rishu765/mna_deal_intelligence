"""Narrow service contracts consumed by graph nodes."""

from __future__ import annotations

from typing import Protocol

from ma_target_screening.discovery.models import CandidateDiscoveryResult
from ma_target_screening.domain import CandidateCompany
from ma_target_screening.profile import CandidateProfile
from ma_target_screening.screening.models import Shortlist
from ma_target_screening.thesis import AcquisitionThesis


class DiscoveryWorkflowService(Protocol):
    def discover(self, thesis: AcquisitionThesis) -> CandidateDiscoveryResult: ...


class EnrichmentWorkflowService(Protocol):
    def enrich(
        self, candidate: CandidateCompany, thesis: AcquisitionThesis
    ) -> CandidateProfile: ...


class ScreeningWorkflowService(Protocol):
    def build_shortlist(
        self,
        thesis: AcquisitionThesis,
        profiles: tuple[CandidateProfile, ...],
        *,
        top_n: int | None = None,
        include_review_required: bool = True,
    ) -> Shortlist: ...
