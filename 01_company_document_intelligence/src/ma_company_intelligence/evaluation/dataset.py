"""Load and validate versioned JSON evaluation datasets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ma_company_intelligence.evaluation.errors import EvaluationDatasetError
from ma_company_intelligence.evaluation.models import (
    AnswerObservation,
    CaseObservation,
    CitationObservation,
    ClaimObservation,
    EvaluationCase,
    EvaluationDataset,
    EvidenceRecord,
    EvidenceTarget,
    ExpectedFinancialMetric,
    ObservedFinancialMetric,
    StructuredEvaluationCase,
    StructuredSectionExpectation,
    StructuredSectionObservation,
)


def load_evaluation_dataset(path: Path) -> EvaluationDataset:
    """Load a dataset without permitting unknown execution behavior from the file."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("dataset root must be an object")
        return _dataset(payload)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise EvaluationDatasetError(f"invalid evaluation dataset {path}") from error


def _dataset(data: dict[str, Any]) -> EvaluationDataset:
    return EvaluationDataset(
        dataset_id=str(data["dataset_id"]),
        version=str(data["version"]),
        description=str(data["description"]),
        evidence=tuple(_evidence(item) for item in _list(data["evidence"])),
        cases=tuple(_case(item) for item in _list(data["cases"])),
        structured_cases=tuple(
            _structured_case(item) for item in _list(data.get("structured_cases", []))
        ),
    )


def _evidence(data: Any) -> EvidenceRecord:
    item = _dict(data)
    return EvidenceRecord(
        chunk_id=str(item["chunk_id"]),
        document_id=str(item["document_id"]),
        source_filename=str(item["source_filename"]),
        page_numbers=_integers(item["page_numbers"]),
        text=str(item["text"]),
    )


def _target(data: Any) -> EvidenceTarget:
    item = _dict(data)
    chunk_id = item.get("chunk_id")
    return EvidenceTarget(
        chunk_id=str(chunk_id) if chunk_id is not None else None,
        document_id=str(item["document_id"]),
        page_numbers=_integers(item["page_numbers"]),
    )


def _claim(data: Any) -> ClaimObservation:
    item = _dict(data)
    return ClaimObservation(
        text=str(item["text"]),
        citation_chunk_ids=_strings(item.get("citation_chunk_ids", [])),
    )


def _citation(data: Any) -> CitationObservation:
    item = _dict(data)
    return CitationObservation(
        chunk_id=str(item["chunk_id"]),
        document_id=str(item["document_id"]),
        page_numbers=_integers(item.get("page_numbers", [])),
    )


def _answer(data: Any) -> AnswerObservation:
    item = _dict(data)
    return AnswerObservation(
        answer=str(item["answer"]),
        insufficient_evidence=bool(item["insufficient_evidence"]),
        claims=tuple(_claim(value) for value in _list(item.get("claims", []))),
        citations=tuple(_citation(value) for value in _list(item.get("citations", []))),
    )


def _case(data: Any) -> EvaluationCase:
    item = _dict(data)
    observation = _dict(item["observation"])
    return EvaluationCase(
        case_id=str(item["case_id"]),
        question=str(item["question"]),
        category=str(item["category"]),
        expected_facts=_strings(item.get("expected_facts", [])),
        expected_evidence=tuple(
            _target(value) for value in _list(item.get("expected_evidence", []))
        ),
        should_be_insufficient=bool(item["should_be_insufficient"]),
        acceptable_variants=_strings(item.get("acceptable_variants", [])),
        notes=str(item.get("notes", "")),
        observation=CaseObservation(
            retrieved_chunk_ids=_strings(observation.get("retrieved_chunk_ids", [])),
            context_chunk_ids=_strings(observation.get("context_chunk_ids", [])),
            retrieved_context_answer=_answer(observation["retrieved_context_answer"]),
            gold_context_answer=_answer(observation["gold_context_answer"]),
        ),
    )


def _expected_metric(data: Any) -> ExpectedFinancialMetric:
    item = _dict(data)
    return ExpectedFinancialMetric(
        metric_name=str(item["metric_name"]),
        value=str(item["value"]),
        fiscal_period=_optional_string(item.get("fiscal_period")),
        unit=_optional_string(item.get("unit")),
        currency=_optional_string(item.get("currency")),
        basis=_optional_string(item.get("basis")),
    )


def _observed_metric(data: Any) -> ObservedFinancialMetric:
    item = _dict(data)
    return ObservedFinancialMetric(
        metric_name=str(item["metric_name"]),
        value=str(item["value"]),
        fiscal_period=_optional_string(item.get("fiscal_period")),
        unit=_optional_string(item.get("unit")),
        currency=_optional_string(item.get("currency")),
        basis=_optional_string(item.get("basis")),
        citation_chunk_ids=_strings(item.get("citation_chunk_ids", [])),
    )


def _structured_case(data: Any) -> StructuredEvaluationCase:
    item = _dict(data)
    expected = tuple(
        StructuredSectionExpectation(
            key=str(section["key"]),
            should_be_insufficient=bool(section["should_be_insufficient"]),
            expected_facts=_strings(section.get("expected_facts", [])),
            expected_observations=_strings(section.get("expected_observations", [])),
            expected_metrics=tuple(
                _expected_metric(metric) for metric in _list(section.get("expected_metrics", []))
            ),
            expected_evidence_chunk_ids=_strings(section.get("expected_evidence_chunk_ids", [])),
        )
        for section in (_dict(value) for value in _list(item["expected_sections"]))
    )
    observed = tuple(
        StructuredSectionObservation(
            key=str(section["key"]),
            insufficient_evidence=bool(section["insufficient_evidence"]),
            facts=_strings(section.get("facts", [])),
            observations=_strings(section.get("observations", [])),
            metrics=tuple(_observed_metric(metric) for metric in _list(section.get("metrics", []))),
            citation_chunk_ids=_strings(section.get("citation_chunk_ids", [])),
        )
        for section in (_dict(value) for value in _list(item["observed_sections"]))
    )
    return StructuredEvaluationCase(
        case_id=str(item["case_id"]),
        company_name=str(item["company_name"]),
        expected_sections=expected,
        observed_sections=observed,
    )


def _dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("expected object")
    return value


def _list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError("expected array")
    return value


def _strings(value: Any) -> tuple[str, ...]:
    return tuple(str(item) for item in _list(value))


def _integers(value: Any) -> tuple[int, ...]:
    return tuple(int(item) for item in _list(value))


def _optional_string(value: Any) -> str | None:
    return str(value) if value is not None else None
