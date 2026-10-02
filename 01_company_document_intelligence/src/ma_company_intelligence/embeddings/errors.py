"""Application-specific embedding failures."""


class EmbeddingError(Exception):
    """Base class for embedding failures."""


class EmbeddingConfigurationError(EmbeddingError):
    """Required embedding configuration is missing or invalid."""


class InvalidEmbeddingInputError(EmbeddingError):
    """Text supplied for embedding is empty or otherwise invalid."""


class EmbeddingProviderError(EmbeddingError):
    """The configured provider could not generate embeddings."""


class EmbeddingResponseError(EmbeddingError):
    """A provider response violates the embedding interface contract."""
