"""Application-specific vector indexing failures."""


class IndexingError(Exception):
    """Base class for indexing failures."""


class InvalidChunkError(IndexingError):
    """A value supplied to the indexing service is not a valid chunk."""


class DuplicateChunkError(IndexingError):
    """One indexing call contains conflicting data for a stable chunk ID."""


class VectorDimensionError(IndexingError):
    """An embedding does not match the configured index dimension."""


class VectorStoreError(IndexingError):
    """The vector-record store could not complete an operation."""


class IndexCompatibilityError(VectorStoreError):
    """An existing index was built with incompatible embedding settings."""
