"""Candidate discovery contracts, providers, and orchestration."""

from ma_target_screening.discovery.config import DiscoveryLimits, DiscoverySettings
from ma_target_screening.discovery.models import (
    CandidateDiscoveryResult,
    DiscoveredCompanyRecord,
    DiscoveryQuery,
    DiscoveryRequest,
    ProviderDiscoveryResult,
    UserCandidateInput,
)
from ma_target_screening.discovery.providers import (
    LocalDatasetDiscoveryProvider,
    UserSuppliedDiscoveryProvider,
)
from ma_target_screening.discovery.query import DeterministicQueryGenerator
from ma_target_screening.discovery.service import CandidateDiscoveryService

__all__ = [
    "CandidateDiscoveryResult",
    "CandidateDiscoveryService",
    "DeterministicQueryGenerator",
    "DiscoveredCompanyRecord",
    "DiscoveryLimits",
    "DiscoveryQuery",
    "DiscoveryRequest",
    "DiscoverySettings",
    "LocalDatasetDiscoveryProvider",
    "ProviderDiscoveryResult",
    "UserCandidateInput",
    "UserSuppliedDiscoveryProvider",
]
