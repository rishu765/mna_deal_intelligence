"""Application-specific grounded RAG failures."""


class RAGError(Exception):
    """Base class for grounded-answer orchestration failures."""


class InvalidQuestionError(RAGError):
    """The user question or RAG option is invalid."""
