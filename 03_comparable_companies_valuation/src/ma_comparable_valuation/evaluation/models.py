"""Inspectable, subsystem-separated evaluation results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class EvaluationCheck:
    check_id: str
    case_id: str
    passed: bool
    expected: str
    actual: str
    representative_failure: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "case_id": self.case_id,
            "passed": self.passed,
            "expected": self.expected,
            "actual": self.actual,
            "representative_failure": self.representative_failure,
        }


@dataclass(frozen=True, slots=True)
class SubsystemEvaluation:
    subsystem: str
    checks: tuple[EvaluationCheck, ...]
    limitation: str

    @property
    def pass_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def fail_count(self) -> int:
        return len(self.checks) - self.pass_count

    @property
    def passed(self) -> bool:
        return self.fail_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "subsystem": self.subsystem,
            "passed": self.passed,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "checks": [item.to_dict() for item in self.checks],
            "limitation": self.limitation,
        }


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    dataset_id: str
    generated_at: str
    case_count: int
    subsystems: tuple[SubsystemEvaluation, ...]
    limitations: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return all(item.passed for item in self.subsystems)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "dataset_id": self.dataset_id,
            "generated_at": self.generated_at,
            "case_count": self.case_count,
            "passed": self.passed,
            "subsystems": [item.to_dict() for item in self.subsystems],
            "limitations": list(self.limitations),
        }
