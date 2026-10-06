"""Stable Project 2 exception families for future adapters and application layers."""


class TargetScreeningError(Exception):
    """Base class for expected Project 2 failures."""


class DiscoveryError(TargetScreeningError):
    """Raised when a discovery provider cannot complete a request."""


class DiscoveryUnavailableError(DiscoveryError):
    """Raised when every configured discovery provider fails."""


class MalformedDiscoverySourceError(DiscoveryError):
    """Raised when a discovery source cannot be parsed into valid records."""


class EnrichmentError(TargetScreeningError):
    """Raised when candidate research cannot complete reliably."""


class MalformedEnrichmentSourceError(EnrichmentError):
    """Raised when provider enrichment cannot be validated."""


class ScreeningError(TargetScreeningError):
    """Raised when deterministic screening cannot be evaluated safely."""


class StrategicFitError(TargetScreeningError):
    """Raised when a semantic assessment provider cannot return grounded output."""


class MalformedStrategicFitOutputError(StrategicFitError):
    """Raised when semantic provider output violates the structured contract."""
