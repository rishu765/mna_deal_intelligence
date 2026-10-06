"""Screening, score aggregation, deterministic ranking, and shortlist construction."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal

from ma_target_screening.profile import CandidateProfile
from ma_target_screening.screening.deterministic import DeterministicScreeningEngine
from ma_target_screening.screening.models import (
    CriterionEvaluation,
    CriterionOutcome,
    EligibilityStatus,
    RankedCandidate,
    ScoreSummary,
    ScreeningResult,
    Shortlist,
)
from ma_target_screening.screening.strategic import StrategicFitService
from ma_target_screening.thesis import (
    AcquisitionThesis,
    CriterionPriority,
    CriterionRequirement,
    EvaluationMethod,
    ScreeningCriterion,
)

_PRIORITY_WEIGHTS = {
    CriterionPriority.CRITICAL: Decimal("4"),
    CriterionPriority.HIGH: Decimal("3"),
    CriterionPriority.MEDIUM: Decimal("2"),
    CriterionPriority.LOW: Decimal("1"),
}

_ELIGIBILITY_ORDER = {
    EligibilityStatus.ELIGIBLE: 0,
    EligibilityStatus.REVIEW_REQUIRED: 1,
    EligibilityStatus.INELIGIBLE: 2,
}


@dataclass(frozen=True, slots=True)
class ScreeningRankingService:
    strategic_fit_service: StrategicFitService
    deterministic_engine: DeterministicScreeningEngine = DeterministicScreeningEngine()

    def evaluate_candidate(
        self, thesis: AcquisitionThesis, profile: CandidateProfile
    ) -> ScreeningResult:
        deterministic = self.deterministic_engine.evaluate(profile, thesis.criteria)
        strategic = self.strategic_fit_service.assess(thesis, profile)
        combined = (*deterministic, *strategic.evaluations)
        criteria = {item.criterion_id: item for item in thesis.criteria}
        weighted = tuple(
            replace(item, weight=_criterion_weight(criteria[item.criterion_id]))
            for item in combined
        )
        eligibility = _eligibility(weighted)
        scores = _scores(thesis.criteria, weighted)
        warnings = [*profile.warnings, *strategic.warnings]
        warnings.extend(
            f"Missing or uncertain data for criterion {item.criterion_id}."
            for item in weighted
            if item.outcome is CriterionOutcome.UNKNOWN
        )
        return ScreeningResult(
            profile=profile,
            eligibility=eligibility,
            evaluations=weighted,
            strategic_fit=replace(
                strategic,
                evaluations=tuple(
                    item for item in weighted if item.evaluation_method is EvaluationMethod.SEMANTIC
                ),
                score=scores.semantic_score,
            ),
            scores=scores,
            rationale=_rationale(profile, eligibility, weighted, scores),
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def build_shortlist(
        self,
        thesis: AcquisitionThesis,
        profiles: tuple[CandidateProfile, ...],
        *,
        top_n: int | None = None,
        include_review_required: bool = True,
    ) -> Shortlist:
        if top_n is not None and top_n < 1:
            raise ValueError("top_n must be positive")
        results = tuple(self.evaluate_candidate(thesis, profile) for profile in profiles)
        ordered = tuple(sorted(results, key=_ranking_key))
        allowed = {EligibilityStatus.ELIGIBLE}
        if include_review_required:
            allowed.add(EligibilityStatus.REVIEW_REQUIRED)
        candidates = tuple(result for result in ordered if result.eligibility in allowed)
        if top_n is not None:
            candidates = candidates[:top_n]
        ranked = tuple(
            RankedCandidate(
                rank=index,
                result=result,
                key_strengths=_strengths(result),
                key_weaknesses=_weaknesses(result),
            )
            for index, result in enumerate(candidates, start=1)
        )
        warnings: list[str] = []
        if not profiles:
            warnings.append("No candidate profiles were supplied.")
        elif not ranked:
            warnings.append("No candidate remained shortlist-eligible after hard constraints.")
        return Shortlist(
            thesis_id=thesis.thesis_id,
            ranked_candidates=ranked,
            screening_results=ordered,
            warnings=tuple(warnings),
        )


def _criterion_weight(criterion: ScreeningCriterion) -> Decimal:
    if criterion.weight is not None:
        return criterion.weight
    if criterion.priority is not None:
        return _PRIORITY_WEIGHTS[criterion.priority]
    return Decimal("1")


def _eligibility(evaluations: tuple[CriterionEvaluation, ...]) -> EligibilityStatus:
    gates = tuple(
        item
        for item in evaluations
        if item.requirement in {CriterionRequirement.HARD, CriterionRequirement.EXCLUSION}
    )
    if any(item.outcome is CriterionOutcome.FAIL for item in gates):
        return EligibilityStatus.INELIGIBLE
    if any(item.outcome in {CriterionOutcome.UNKNOWN, CriterionOutcome.PARTIAL} for item in gates):
        return EligibilityStatus.REVIEW_REQUIRED
    return EligibilityStatus.ELIGIBLE


def _scores(
    criteria: tuple[ScreeningCriterion, ...],
    evaluations: tuple[CriterionEvaluation, ...],
) -> ScoreSummary:
    soft = tuple(item for item in criteria if item.requirement is CriterionRequirement.SOFT)
    total_weight = sum((_criterion_weight(item) for item in soft), Decimal("0"))
    evaluation_by_id = {item.criterion_id: item for item in evaluations}
    known = tuple(
        (evaluation_by_id[item.criterion_id], _criterion_weight(item))
        for item in soft
        if item.criterion_id in evaluation_by_id
        and evaluation_by_id[item.criterion_id].score is not None
    )
    known_weight = sum((weight for _, weight in known), Decimal("0"))
    coverage = (
        Decimal("1")
        if total_weight == 0
        else (known_weight / total_weight).quantize(Decimal("0.001"))
    )
    raw = _weighted_score(known)
    deterministic = _weighted_score(
        tuple(
            (item, weight)
            for item, weight in known
            if item.evaluation_method is EvaluationMethod.DETERMINISTIC
        )
    )
    semantic = _weighted_score(
        tuple(
            (item, weight)
            for item, weight in known
            if item.evaluation_method is EvaluationMethod.SEMANTIC
        )
    )
    final = None
    if raw is not None:
        confidence_factor = Decimal("0.5") + Decimal("0.5") * coverage
        final = (raw * confidence_factor).quantize(Decimal("0.1"))
    return ScoreSummary(
        deterministic_soft_score=deterministic,
        semantic_score=semantic,
        raw_fit_score=raw,
        evidence_coverage=coverage,
        final_score=final,
    )


def _weighted_score(
    values: tuple[tuple[CriterionEvaluation, Decimal], ...],
) -> Decimal | None:
    if not values:
        return None
    denominator = sum((weight for _, weight in values), Decimal("0"))
    numerator = sum(
        (item.score * weight for item, weight in values if item.score is not None),
        Decimal("0"),
    )
    return (numerator / denominator * 100).quantize(Decimal("0.1"))


def _ranking_key(result: ScreeningResult) -> tuple[int, Decimal, Decimal, Decimal, Decimal, str]:
    missing = Decimal("-1")
    return (
        _ELIGIBILITY_ORDER[result.eligibility],
        -(result.scores.final_score if result.scores.final_score is not None else missing),
        -(result.scores.semantic_score if result.scores.semantic_score is not None else missing),
        -(
            result.scores.deterministic_soft_score
            if result.scores.deterministic_soft_score is not None
            else missing
        ),
        -result.scores.evidence_coverage,
        result.profile.candidate.canonical_name.casefold(),
    )


def _rationale(
    profile: CandidateProfile,
    eligibility: EligibilityStatus,
    evaluations: tuple[CriterionEvaluation, ...],
    scores: ScoreSummary,
) -> str:
    failures = [item.criterion_id for item in evaluations if item.outcome is CriterionOutcome.FAIL]
    unknowns = [
        item.criterion_id for item in evaluations if item.outcome is CriterionOutcome.UNKNOWN
    ]
    score_text = "unscored" if scores.final_score is None else f"score {scores.final_score}/100"
    if failures:
        detail = "failed " + ", ".join(failures[:3])
    elif unknowns:
        detail = "needs evidence for " + ", ".join(unknowns[:3])
    else:
        fit_criteria = [
            item.criterion_id
            for item in evaluations
            if item.requirement is CriterionRequirement.SOFT
            and item.outcome in {CriterionOutcome.PASS, CriterionOutcome.PARTIAL}
        ]
        detail = "passes all hard constraints and exclusions"
        if fit_criteria:
            detail += "; strongest fit signals are " + ", ".join(fit_criteria[:3])
    return (
        f"{profile.candidate.canonical_name} is {eligibility.value.replace('_', ' ')} with "
        f"{score_text}; it {detail}."
    )


def _strengths(result: ScreeningResult) -> tuple[str, ...]:
    return tuple(
        f"{item.criterion_id}: {item.reason}"
        for item in result.evaluations
        if item.outcome is CriterionOutcome.PASS
    )[:3]


def _weaknesses(result: ScreeningResult) -> tuple[str, ...]:
    return tuple(
        f"{item.criterion_id}: {item.reason}"
        for item in result.evaluations
        if item.outcome
        in {CriterionOutcome.FAIL, CriterionOutcome.UNKNOWN, CriterionOutcome.PARTIAL}
    )[:3]
