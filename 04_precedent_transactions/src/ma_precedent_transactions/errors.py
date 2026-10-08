"""Project 4 exception hierarchy."""


class PrecedentTransactionsError(Exception):
    """Base error for the Project 4 package."""


class DomainValidationError(PrecedentTransactionsError, ValueError):
    """Raised when a domain invariant is violated."""


class SerializationError(PrecedentTransactionsError, ValueError):
    """Raised when a serialized transaction cannot be reconstructed."""


class UnsupportedSchemaVersionError(SerializationError):
    """Raised when input uses an unsupported schema version."""


class DiscoveryError(PrecedentTransactionsError):
    """Base error for deal discovery failures."""


class DiscoveryUnavailableError(DiscoveryError):
    """Raised when every configured discovery provider fails."""


class MalformedFixtureError(DiscoveryError):
    """Raised when deterministic fixture data is invalid."""


class DocumentError(PrecedentTransactionsError):
    """Base error for document catalog and ingestion failures."""


class DocumentUnavailableError(DocumentError):
    """Raised when a referenced local document is unavailable."""


class UnsupportedDocumentFormatError(DocumentError):
    """Raised when no parser supports a document format."""


class MalformedDocumentError(DocumentError):
    """Raised when document contents cannot be decoded or parsed."""


class IndexingError(PrecedentTransactionsError):
    """Raised when chunks cannot be indexed safely."""


class EmbeddingError(IndexingError):
    """Raised when an embedding provider fails or returns invalid vectors."""


class RetrievalError(PrecedentTransactionsError):
    """Raised for invalid or failed retrieval requests."""


class ExtractionError(PrecedentTransactionsError):
    """Structured extraction could not produce a usable observation batch."""


class ExtractionProviderError(ExtractionError):
    """An optional model provider failed or timed out."""


class ExtractionValidationError(ExtractionError):
    """A structured extraction response violated the application schema."""


class NormalizationError(PrecedentTransactionsError):
    """A source observation could not be normalized without guessing."""


class VerificationError(PrecedentTransactionsError):
    """Transaction observations could not be verified consistently."""
