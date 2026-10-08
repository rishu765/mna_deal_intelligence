"""Bounded multi-provider discovery and preliminary identity resolution."""

from dataclasses import dataclass

from ma_precedent_transactions.discovery.identity import TransactionIdentityResolver
from ma_precedent_transactions.discovery.models import (
    AcquisitionContext,
    CandidateTransaction,
    DealDiscoveryResult,
)
from ma_precedent_transactions.discovery.ports import DealDiscoveryProvider
from ma_precedent_transactions.errors import DiscoveryError, DiscoveryUnavailableError


@dataclass(frozen=True, slots=True)
class DealDiscoveryService:
    providers: tuple[DealDiscoveryProvider, ...]
    resolver: TransactionIdentityResolver = TransactionIdentityResolver()

    def __post_init__(self) -> None:
        if not self.providers:
            raise ValueError("at least one discovery provider is required")
        names = [provider.provider_name for provider in self.providers]
        if len(set(names)) != len(names):
            raise ValueError("discovery provider names must be unique")

    def discover(self, context: AcquisitionContext) -> DealDiscoveryResult:
        candidates: list[CandidateTransaction] = []
        warnings: list[str] = []
        successful: list[str] = []
        for provider in self.providers:
            try:
                result = provider.discover(context)
            except (DiscoveryError, OSError, TypeError, ValueError):
                warnings.append(f"Discovery provider failed: {provider.provider_name}")
                continue
            successful.append(provider.provider_name)
            candidates.extend(result.candidates)
            warnings.extend(result.warnings)
        if not successful:
            raise DiscoveryUnavailableError("all configured discovery providers failed")
        resolution = self.resolver.resolve(tuple(candidates))
        warnings.extend(resolution.warnings)
        if not resolution.transactions:
            warnings.append("Discovery completed successfully but found no transactions.")
        return DealDiscoveryResult(
            context_id=context.context_id,
            raw_candidate_count=len(candidates),
            transactions=resolution.transactions,
            provider_names=tuple(successful),
            resolution_decisions=resolution.decisions,
            warnings=tuple(dict.fromkeys(warnings)),
        )
