"""Stable Project 2 exception families for future adapters and application layers."""


class TargetScreeningError(Exception):
    """Base class for expected Project 2 failures."""


class DiscoveryError(TargetScreeningError):
    """Raised when a discovery provider cannot complete a request."""


class EnrichmentError(TargetScreeningError):
    """Raised when candidate research cannot complete reliably."""
