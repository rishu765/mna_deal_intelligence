"""Strict loader for the small, human-inspectable M7 benchmark."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ma_target_screening.thesis import AcquisitionThesis, CriterionRequirement


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    case_id: str
    description: str
    thesis: AcquisitionThesis
    expected_requirements: tuple[tuple[str, CriterionRequirement], ...]
    relevant_domains: tuple[str, ...]
    profile_expectations: dict[str, dict[str, Any]]
    screening_expectations: dict[str, dict[str, str]]
    strategic_fit_expectations: dict[str, dict[str, str]]
    expected_top_domains: tuple[str, ...]
    expected_pairs: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class EvaluationDataset:
    schema_version: int
    cases: tuple[EvaluationCase, ...]


def load_evaluation_dataset(path: Path, *, project_root: Path) -> EvaluationDataset:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"unable to load evaluation dataset: {path}") from error
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("evaluation dataset schema_version must be 1")
    raw_cases = raw.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("evaluation dataset requires a non-empty cases list")
    cases = tuple(_case(item, project_root) for item in raw_cases)
    identifiers = [item.case_id for item in cases]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("evaluation case IDs must be unique")
    return EvaluationDataset(schema_version=1, cases=cases)


def _case(raw: object, project_root: Path) -> EvaluationCase:
    if not isinstance(raw, dict):
        raise ValueError("evaluation cases must be objects")
    try:
        thesis_path = (project_root / str(raw["thesis_file"])).resolve()
        if project_root.resolve() not in thesis_path.parents:
            raise ValueError("evaluation thesis path must stay within the project")
        thesis = AcquisitionThesis.from_json(thesis_path.read_text(encoding="utf-8"))
        pairs = tuple((str(pair[0]), str(pair[1])) for pair in raw["expected_pairs"])
        return EvaluationCase(
            case_id=_text(raw["case_id"], "case_id"),
            description=_text(raw["description"], "description"),
            thesis=thesis,
            expected_requirements=tuple(
                (str(key), CriterionRequirement(value))
                for key, value in raw["expected_requirements"].items()
            ),
            relevant_domains=tuple(str(item) for item in raw["relevant_domains"]),
            profile_expectations=dict(raw["profile_expectations"]),
            screening_expectations=dict(raw["screening_expectations"]),
            strategic_fit_expectations=dict(raw["strategic_fit_expectations"]),
            expected_top_domains=tuple(str(item) for item in raw["expected_top_domains"]),
            expected_pairs=pairs,
        )
    except (KeyError, OSError, TypeError, ValueError, IndexError) as error:
        raise ValueError(f"invalid evaluation case: {error}") from error


def _text(value: object, name: str) -> str:
    normalized = " ".join(str(value).split())
    if not normalized:
        raise ValueError(f"{name} must not be blank")
    return normalized
