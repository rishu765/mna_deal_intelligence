"""Evaluation-specific failures."""


class EvaluationError(Exception):
    """Base error for evaluation loading and execution."""


class EvaluationDatasetError(EvaluationError):
    """Raised when a versioned evaluation dataset is malformed."""


class EvaluationJudgeError(EvaluationError):
    """Raised when an optional judge response cannot be used safely."""
