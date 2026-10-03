"""Application errors for citation mapping."""


class CitationError(Exception):
    """Base error for citation construction."""


class CitationReferenceError(CitationError):
    """Raised when generated evidence references cannot be validated."""
