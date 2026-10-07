"""Stable Project 3 M1 error families."""


class TargetProfileError(Exception):
    """Base error for target-profile adapters and fixture loading."""


class Project1AdapterError(TargetProfileError):
    """Project 1 could not return a usable structured research result."""


class MalformedFixtureError(TargetProfileError):
    """A target-profile fixture could not be parsed or validated."""
