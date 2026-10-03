"""Application errors for structured research orchestration."""


class ResearchError(Exception):
    """Base error for structured research requests."""


class InvalidResearchRequestError(ResearchError):
    """Raised when a structured research request is invalid."""
