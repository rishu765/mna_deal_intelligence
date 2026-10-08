"""Small field-level M3 extraction benchmark with separate interpretable metrics."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from ma_precedent_transactions.errors import ExtractionValidationError
from ma_precedent_transactions.extraction.models import VerifiedTransactionRecord


@dataclass(frozen=True, slots=True)
class ExtractionGoldCase:
    transaction_id: str
    status: str
    acquirer: str
    target: str
    acquired_percent: str | None
    headline_value: str | None
    expected_missing_fields: tuple[str, ...]
    expected_conflict_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExtractionBenchmarkResult:
    case_count: int
    field_accuracy: float
    numeric_accuracy: float
    missing_value_accuracy: float
    evidence_link_accuracy: float
    conflict_detection_accuracy: float


def load_extraction_benchmark(path: Path) -> tuple[ExtractionGoldCase, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ExtractionValidationError(f"unable to load extraction benchmark: {path}") from error
    if not isinstance(payload, list):
        raise ExtractionValidationError("extraction benchmark must be a list")
    cases = []
    for raw in payload:
        if not isinstance(raw, dict):
            raise ExtractionValidationError("extraction benchmark cases must be objects")
        data: dict[str, Any] = raw
        cases.append(
            ExtractionGoldCase(
                str(data["transaction_id"]),
                str(data["status"]),
                str(data["acquirer"]),
                str(data["target"]),
                None if data.get("acquired_percent") is None else str(data["acquired_percent"]),
                None if data.get("headline_value") is None else str(data["headline_value"]),
                tuple(str(item) for item in data.get("expected_missing_fields", [])),
                tuple(str(item) for item in data.get("expected_conflict_fields", [])),
            )
        )
    return tuple(cases)


def run_extraction_benchmark(
    records: dict[str, VerifiedTransactionRecord],
    cases: tuple[ExtractionGoldCase, ...],
) -> ExtractionBenchmarkResult:
    if not cases:
        raise ValueError("extraction benchmark requires at least one case")
    field_hits = field_total = 0
    numeric_hits = numeric_total = 0
    missing_hits = missing_total = 0
    conflict_hits = conflict_total = 0
    evidence_hits = evidence_total = 0
    for case in cases:
        result = records[case.transaction_id]
        actual_fields = (
            result.record.lifecycle.status.value,
            result.record.acquirer.legal_name or "",
            result.record.target.legal_name or "",
        )
        expected_fields = (case.status, case.acquirer, case.target)
        field_hits += sum(
            actual == expected
            for actual, expected in zip(actual_fields, expected_fields, strict=True)
        )
        field_total += len(expected_fields)
        actual_owned = next(
            (
                item.acquired_percent
                for item in result.record.ownership
                if item.acquired_percent is not None
            ),
            None,
        )
        actual_headline = next(
            (
                item.amount.value
                for item in result.record.valuations
                if item.measure.value == "headline_deal_value" and item.amount is not None
            ),
            None,
        )
        for actual, expected in (
            (actual_owned, case.acquired_percent),
            (actual_headline, case.headline_value),
        ):
            if expected is not None:
                numeric_total += 1
                numeric_hits += actual == Decimal(expected)
        statuses = {item.field: item.status.value for item in result.verification}
        for field in case.expected_missing_fields:
            missing_total += 1
            missing_hits += statuses.get(field) == "missing"
        actual_conflicts = {item.field for item in result.conflicts}
        conflict_total += 1
        conflict_hits += actual_conflicts == set(case.expected_conflict_fields)
        for trace in result.traces:
            evidence_total += 1
            evidence_hits += bool(trace.evidence_ids) and all(
                value.startswith("retrieval:") for value in trace.evidence_ids
            )
    return ExtractionBenchmarkResult(
        len(cases),
        field_hits / field_total if field_total else 1.0,
        numeric_hits / numeric_total if numeric_total else 1.0,
        missing_hits / missing_total if missing_total else 1.0,
        evidence_hits / evidence_total if evidence_total else 1.0,
        conflict_hits / conflict_total if conflict_total else 1.0,
    )
