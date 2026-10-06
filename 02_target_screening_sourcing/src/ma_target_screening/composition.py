"""Credential-free composition root shared by demos, evaluation, and the API."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ma_target_screening.discovery import CandidateDiscoveryService, LocalDatasetDiscoveryProvider
from ma_target_screening.enrichment import (
    CandidateEnrichmentService,
    StructuredFixtureEnrichmentProvider,
)
from ma_target_screening.screening import (
    FixtureStrategicFitProvider,
    ScreeningRankingService,
    StrategicFitService,
)
from ma_target_screening.workflow import WorkflowApplication, build_workflow


@dataclass(frozen=True, slots=True)
class OfflinePaths:
    discovery_data: Path
    enrichment_data: Path
    strategic_fit_data: Path

    @classmethod
    def from_project_root(cls, root: Path) -> OfflinePaths:
        return cls(
            discovery_data=root / "data" / "discovery_companies.json",
            enrichment_data=root / "data" / "enrichment_profiles.json",
            strategic_fit_data=root / "data" / "strategic_fit_assessments.json",
        )


@dataclass(frozen=True, slots=True)
class OfflineServices:
    discovery: CandidateDiscoveryService
    enrichment: CandidateEnrichmentService
    screening: ScreeningRankingService
    workflow: WorkflowApplication


def build_offline_services(paths: OfflinePaths) -> OfflineServices:
    discovery = CandidateDiscoveryService(
        providers=(LocalDatasetDiscoveryProvider(paths.discovery_data),)
    )
    enrichment = CandidateEnrichmentService(
        providers=(StructuredFixtureEnrichmentProvider(paths.enrichment_data),)
    )
    screening = ScreeningRankingService(
        strategic_fit_service=StrategicFitService(
            FixtureStrategicFitProvider(paths.strategic_fit_data)
        )
    )
    workflow = WorkflowApplication(
        build_workflow(
            discovery=discovery,
            enrichment=enrichment,
            screening=screening,
        )
    )
    return OfflineServices(discovery, enrichment, screening, workflow)
