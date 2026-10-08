"""Historical transaction discovery."""

from ma_precedent_transactions.discovery.identity import TransactionIdentityResolver
from ma_precedent_transactions.discovery.models import (
    AcquisitionContext,
    CandidateTransaction,
    DealDiscoveryResult,
    DiscoverySourceReference,
    IdentityResolutionDecision,
    IdentityResolutionResult,
    ProviderDiscoveryResult,
    ResolutionDisposition,
)
from ma_precedent_transactions.discovery.ports import DealDiscoveryProvider
from ma_precedent_transactions.discovery.providers import FixtureDealDiscoveryProvider
from ma_precedent_transactions.discovery.service import DealDiscoveryService

__all__ = [
    "AcquisitionContext",
    "CandidateTransaction",
    "DealDiscoveryProvider",
    "DealDiscoveryResult",
    "DealDiscoveryService",
    "DiscoverySourceReference",
    "FixtureDealDiscoveryProvider",
    "IdentityResolutionDecision",
    "IdentityResolutionResult",
    "ProviderDiscoveryResult",
    "ResolutionDisposition",
    "TransactionIdentityResolver",
]
