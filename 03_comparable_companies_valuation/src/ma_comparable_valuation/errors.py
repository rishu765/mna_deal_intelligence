"""Stable Project 3 M1 error families."""


class TargetProfileError(Exception):
    """Base error for target-profile adapters and fixture loading."""


class Project1AdapterError(TargetProfileError):
    """Project 1 could not return a usable structured research result."""


class MalformedFixtureError(TargetProfileError):
    """A target-profile fixture could not be parsed or validated."""


class ValuationWorkflowError(Exception):
    """A complete valuation workflow could not produce a usable result."""


class NoMeaningfulValuationError(ValuationWorkflowError):
    """No requested method produced a meaningful target valuation range."""
