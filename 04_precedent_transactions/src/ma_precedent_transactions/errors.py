"""Project 4 exception hierarchy."""


class PrecedentTransactionsError(Exception):
    """Base error for the Project 4 package."""


class DomainValidationError(PrecedentTransactionsError, ValueError):
    """Raised when a domain invariant is violated."""


class SerializationError(PrecedentTransactionsError, ValueError):
    """Raised when a serialized transaction cannot be reconstructed."""


class UnsupportedSchemaVersionError(SerializationError):
    """Raised when input uses an unsupported schema version."""
