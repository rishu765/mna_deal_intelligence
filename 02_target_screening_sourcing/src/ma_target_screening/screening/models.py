"""Transparent screening, scoring, ranking, and shortlist domain models."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any

from ma_target_screening.profile import CandidateProfile, EnrichmentEvidence
from ma_target_screening.thesis import (
    CriterionCategory,
    CriterionRequirement,
    EvaluationMethod,
)


class CriterionOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class EligibilityStatus(StrEnum):
    ELIGIBLE = "eligible"
    REVIEW_REQUIRED = "review_required"
    INELIGIBLE = "ineligible"


def _normalized_decimal(value: Decimal, name: str, *, maximum: Decimal) -> Decimal:
    if not value.is_finite() or value < 0 or value > maximum:
        raise ValueError(f"{name} must be between 0 and {maximum}")
    return value


@dataclass(frozen=True, slots=True)
class CriterionEvaluation:
    criterion_id: str
    category: CriterionCategory
    requirement: CriterionRequirement
    evaluation_method: EvaluationMethod
    outcome: CriterionOutcome
    reason: str
    candidate_values: tuple[str, ...] = ()
    evidence: tuple[EnrichmentEvidence, ...] = ()
    score: Decimal | None = None
    weight: Decimal | None = None
    uncertainty: str | None = None

    def __post_init__(self) -> None:
        if not self.criterion_id.strip() or not self.reason.strip():
            raise ValueError("criterion evaluation ID and reason must not be blank")
        if self.score is not None:
            _normalized_decimal(self.score, "criterion score", maximum=Decimal("1"))
        if self.weight is not None and self.weight <= 0:
            raise ValueError("criterion weight must be positive")
        if (
            self.outcome in {CriterionOutcome.UNKNOWN, CriterionOutcome.NOT_APPLICABLE}
            and self.score is not None
        ):
            raise ValueError("unknown and not-applicable evaluations cannot have a score")


@dataclass(frozen=True, slots=True)
class StrategicFitAssessment:
    evaluations: tuple[CriterionEvaluation, ...]
    score: Decimal | None
    summary: str
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.summary.strip():
            raise ValueError("strategic-fit summary must not be blank")
        if any(
            item.evaluation_method is not EvaluationMethod.SEMANTIC for item in self.evaluations
        ):
            raise ValueError("strategic-fit assessments may contain only semantic evaluations")
        if self.score is not None:
            _normalized_decimal(self.score, "strategic-fit score", maximum=Decimal("100"))


@dataclass(frozen=True, slots=True)
class ScoreSummary:
    deterministic_soft_score: Decimal | None
    semantic_score: Decimal | None
    raw_fit_score: Decimal | None
    evidence_coverage: Decimal
    final_score: Decimal | None

    def __post_init__(self) -> None:
        for name in (
            "deterministic_soft_score",
            "semantic_score",
            "raw_fit_score",
            "final_score",
        ):
            value = getattr(self, name)
            if value is not None:
                _normalized_decimal(value, name, maximum=Decimal("100"))
        _normalized_decimal(self.evidence_coverage, "evidence_coverage", maximum=Decimal("1"))


@dataclass(frozen=True, slots=True)
class ScreeningResult:
    profile: CandidateProfile
    eligibility: EligibilityStatus
    evaluations: tuple[CriterionEvaluation, ...]
    strategic_fit: StrategicFitAssessment
    scores: ScoreSummary
    rationale: str
    warnings: tuple[str, ...] = ()

    @property
    def failed_criteria(self) -> tuple[CriterionEvaluation, ...]:
        return tuple(item for item in self.evaluations if item.outcome is CriterionOutcome.FAIL)

    @property
    def unknown_criteria(self) -> tuple[CriterionEvaluation, ...]:
        return tuple(item for item in self.evaluations if item.outcome is CriterionOutcome.UNKNOWN)


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    rank: int
    result: ScreeningResult
    key_strengths: tuple[str, ...]
    key_weaknesses: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.rank < 1:
            raise ValueError("rank must be positive")


@dataclass(frozen=True, slots=True)
class Shortlist:
    thesis_id: str
    ranked_candidates: tuple[RankedCandidate, ...]
    screening_results: tuple[ScreeningResult, ...]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "thesis_id": self.thesis_id,
            "ranked_candidates": [
                {
                    "rank": item.rank,
                    "candidate": item.result.profile.candidate.canonical_name,
                    "domain": item.result.profile.candidate.website_domain,
                    "eligibility": item.result.eligibility.value,
                    "final_score": _decimal_text(item.result.scores.final_score),
                    "raw_fit_score": _decimal_text(item.result.scores.raw_fit_score),
                    "evidence_coverage": str(item.result.scores.evidence_coverage),
                    "key_strengths": list(item.key_strengths),
                    "key_weaknesses": list(item.key_weaknesses),
                    "rationale": item.result.rationale,
                    "criteria": [_evaluation_to_dict(e) for e in item.result.evaluations],
                }
                for item in self.ranked_candidates
            ],
            "excluded_candidates": [
                {
                    "candidate": result.profile.candidate.canonical_name,
                    "eligibility": result.eligibility.value,
                    "failed_criteria": [item.criterion_id for item in result.failed_criteria],
                    "rationale": result.rationale,
                }
                for result in self.screening_results
                if result.eligibility is EligibilityStatus.INELIGIBLE
            ],
            "warnings": list(self.warnings),
        }


def _decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _evaluation_to_dict(value: CriterionEvaluation) -> dict[str, Any]:
    return {
        "criterion_id": value.criterion_id,
        "category": value.category.value,
        "requirement": value.requirement.value,
        "evaluation_method": value.evaluation_method.value,
        "outcome": value.outcome.value,
        "reason": value.reason,
        "candidate_values": list(value.candidate_values),
        "evidence_ids": [item.evidence_id for item in value.evidence],
        "score": _decimal_text(value.score),
        "weight": _decimal_text(value.weight),
        "uncertainty": value.uncertainty,
    }
