"""Inspectable result models for the Project 2 V1 evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class SubsystemEvaluation:
    subsystem: str
    metrics: tuple[tuple[str, float], ...]
    strengths: tuple[str, ...] = ()
    weaknesses: tuple[str, ...] = ()
    representative_failures: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.subsystem.strip():
            raise ValueError("evaluation subsystem must not be blank")
        names = [name for name, _ in self.metrics]
        if len(set(names)) != len(names):
            raise ValueError("metric names must be unique within a subsystem")
        if any(not name.strip() for name in names):
            raise ValueError("metric names must not be blank")

    def to_dict(self) -> dict[str, Any]:
        return {
            "subsystem": self.subsystem,
            "metrics": {name: value for name, value in self.metrics},
            "strengths": list(self.strengths),
            "weaknesses": list(self.weaknesses),
            "representative_failures": list(self.representative_failures),
        }


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    dataset_version: int
    case_count: int
    subsystems: tuple[SubsystemEvaluation, ...]
    generated_at: str
    limitations: tuple[str, ...]

    @classmethod
    def create(
        cls,
        *,
        dataset_version: int,
        case_count: int,
        subsystems: tuple[SubsystemEvaluation, ...],
        limitations: tuple[str, ...],
    ) -> EvaluationReport:
        return cls(
            dataset_version=dataset_version,
            case_count=case_count,
            subsystems=subsystems,
            generated_at=datetime.now(UTC).isoformat(),
            limitations=limitations,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "dataset_version": self.dataset_version,
            "case_count": self.case_count,
            "generated_at": self.generated_at,
            "subsystems": [item.to_dict() for item in self.subsystems],
            "limitations": list(self.limitations),
        }
