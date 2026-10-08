"""Load the small public-safe Project 3 evaluation dataset."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    case_id: str
    name: str
    scenario: str
    expected_behaviors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvaluationDataset:
    schema_version: int
    dataset_id: str
    cases: tuple[EvaluationCase, ...]


def load_evaluation_dataset(path: Path) -> EvaluationDataset:
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"could not load evaluation dataset: {error}") from error
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("evaluation dataset schema_version must be 1")
    values = raw.get("cases")
    if not isinstance(values, list) or not values:
        raise ValueError("evaluation dataset requires cases")
    cases = tuple(_case(item) for item in values)
    if len({item.case_id for item in cases}) != len(cases):
        raise ValueError("evaluation case IDs must be unique")
    dataset_id = raw.get("dataset_id")
    if not isinstance(dataset_id, str) or not dataset_id.strip():
        raise ValueError("evaluation dataset_id must be a non-empty string")
    return EvaluationDataset(1, dataset_id, cases)


def _case(raw: object) -> EvaluationCase:
    if not isinstance(raw, dict):
        raise ValueError("evaluation case must be an object")
    expected = raw.get("expected_behaviors")
    if (
        not isinstance(expected, list)
        or not expected
        or not all(isinstance(item, str) and item.strip() for item in expected)
    ):
        raise ValueError("expected_behaviors must contain non-empty strings")
    values: dict[str, str] = {}
    for field in ("case_id", "name", "scenario"):
        value = raw.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"evaluation case {field} must be a non-empty string")
        values[field] = value
    return EvaluationCase(
        values["case_id"],
        values["name"],
        values["scenario"],
        tuple(expected),
    )
