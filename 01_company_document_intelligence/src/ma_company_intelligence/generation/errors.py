"""Application-specific generation failures."""


class GenerationError(Exception):
    """Base class for text-generation failures."""


class GenerationConfigurationError(GenerationError):
    """Generation settings are missing or invalid."""


class GenerationProviderError(GenerationError):
    """The configured provider failed to complete a request."""


class GenerationResponseError(GenerationError):
    """The provider returned an unusable or malformed response."""
