"""Narrow provider boundary for candidate transaction generation."""

from typing import Protocol

from ma_precedent_transactions.discovery.models import AcquisitionContext, ProviderDiscoveryResult


class DealDiscoveryProvider(Protocol):
    @property
    def provider_name(self) -> str: ...

    def discover(self, context: AcquisitionContext) -> ProviderDiscoveryResult: ...
