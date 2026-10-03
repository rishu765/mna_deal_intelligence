"""Application-specific semantic retrieval failures."""


class RetrievalError(Exception):
    """Base class for retrieval failures."""


class InvalidQueryError(RetrievalError):
    """A query or retrieval option is invalid."""


class QueryVectorError(RetrievalError):
    """The query embedding cannot be compared with the index."""


class StoredVectorError(RetrievalError):
    """A persisted vector cannot be scored safely."""
