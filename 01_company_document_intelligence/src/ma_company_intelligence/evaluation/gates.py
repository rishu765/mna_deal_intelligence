"""Small deterministic quality gates for evidence-critical benchmark regressions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ma_company_intelligence.evaluation.models import EvaluationReport, FailureCategory


@dataclass(frozen=True, slots=True)
class QualityGateThresholds:
    generation_abstention_accuracy: float = 0.85
    citation_validity: float = 0.90
    citation_support_precision: float = 0.75
    citation_claim_coverage: float = 0.75
    structured_unsupported_abstention: float = 0.75


@dataclass(frozen=True, slots=True)
class QualityGateViolation:
    check: str
    observed: float | tuple[str, ...]
    requirement: str


@dataclass(frozen=True, slots=True)
class QualityGateResult:
    passed: bool
    violations: tuple[QualityGateViolation, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "violations": [
                {
                    "check": item.check,
                    "observed": item.observed,
                    "requirement": item.requirement,
                }
                for item in self.violations
            ],
        }


DEFAULT_QUALITY_THRESHOLDS = QualityGateThresholds()

_KNOWN_CRITICAL_FAILURE_CASES: dict[FailureCategory, frozenset[str]] = {
    FailureCategory.GENERATION_UNEXPECTED_ANSWER: frozenset({"unanswerable-01"}),
    FailureCategory.GENERATION_UNSUPPORTED: frozenset({"growth-01", "unanswerable-01"}),
    FailureCategory.CITATION_INVALID: frozenset({"products-01", "structured/profile-complete-01"}),
    FailureCategory.CITATION_IRRELEVANT: frozenset(
        {"products-01", "growth-01", "strategy-01", "unanswerable-01"}
    ),
    FailureCategory.CITATION_MISSING: frozenset({"products-01", "growth-01", "unanswerable-01"}),
}


def evaluate_quality_gate(
    report: EvaluationReport,
    thresholds: QualityGateThresholds = DEFAULT_QUALITY_THRESHOLDS,
) -> QualityGateResult:
    """Fail on evidence-metric regression or new critical failure cases."""

    metrics = (
        (
            "generation.abstention_accuracy",
            _metric(report, "generation", "abstention_accuracy"),
            thresholds.generation_abstention_accuracy,
        ),
        (
            "citations.validity",
            _metric(report, "citations", "validity"),
            thresholds.citation_validity,
        ),
        (
            "citations.support_precision",
            _metric(report, "citations", "support_precision"),
            thresholds.citation_support_precision,
        ),
        (
            "citations.claim_coverage",
            _metric(report, "citations", "claim_coverage"),
            thresholds.citation_claim_coverage,
        ),
        (
            "structured_research.unsupported_section_abstention",
            _metric(report, "structured_research", "unsupported_section_abstention"),
            thresholds.structured_unsupported_abstention,
        ),
    )
    violations = [
        QualityGateViolation(check, observed, f">= {minimum:.2f}")
        for check, observed, minimum in metrics
        if observed < minimum
    ]

    observed_failures: dict[FailureCategory, set[str]] = {
        category: set() for category in _KNOWN_CRITICAL_FAILURE_CASES
    }
    for case in report.cases:
        for failure in case.failures:
            if failure in observed_failures:
                observed_failures[failure].add(case.case_id)
    for structured_case in report.structured_cases:
        for failure in structured_case.failures:
            if failure in observed_failures:
                observed_failures[failure].add(f"structured/{structured_case.case_id}")

    for category, allowed_cases in _KNOWN_CRITICAL_FAILURE_CASES.items():
        unexpected = tuple(sorted(observed_failures[category] - allowed_cases))
        if unexpected:
            violations.append(
                QualityGateViolation(
                    f"new_failure_cases.{category.value}",
                    unexpected,
                    f"subset of {tuple(sorted(allowed_cases))}",
                )
            )
    return QualityGateResult(not violations, tuple(violations))


def _metric(report: EvaluationReport, section: str, metric: str) -> float:
    values = report.aggregate.get(section)
    if not isinstance(values, dict):
        raise ValueError(f"evaluation report is missing the {section} section")
    value = values.get(metric)
    if not isinstance(value, int | float):
        raise ValueError(f"evaluation report is missing {section}.{metric}")
    return float(value)
