"""Application-service errors that do not belong to a provider or transport."""


class ApplicationServiceError(Exception):
    """Base class for expected application orchestration failures."""


class DocumentAccessError(ApplicationServiceError):
    """A document reference is outside the configured safe input directory."""


class DocumentSizeLimitError(ApplicationServiceError):
    """A document exceeds the configured API ingestion limit."""


class NoIndexableTextError(ApplicationServiceError):
    """A parsed document contains no text chunks suitable for indexing."""


class IndexUnavailableError(ApplicationServiceError):
    """The persistent vector index has not been built or is unavailable."""
