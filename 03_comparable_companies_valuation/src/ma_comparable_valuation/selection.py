"""Transparent deterministic and advisory semantic peer selection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from ma_comparable_valuation.domain import (
    ComparableCompany,
    ComparableSelectionResult,
    ComparableUniverse,
    CriterionEvaluation,
    CriterionOutcome,
    EstimateStatus,
    FinancialMetric,
    FinancialMetricName,
    FinancialUnit,
    ManualOverrideAction,
    ManualPeerOverride,
    PeerSelectionDecision,
    SelectionCriterion,
    SelectionCriterionKind,
    SelectionDecision,
    SimilarityMethod,
    TargetFinancialProfile,
)
from ma_comparable_valuation.normalization import convert_unit


class SemanticSimilarityEvaluator(Protocol):
    """Advisory semantic evaluator; it never applies numeric filters or final decisions."""

    def evaluate(
        self,
        target: TargetFinancialProfile,
        candidate: ComparableCompany,
        criterion: SelectionCriterion,
    ) -> CriterionEvaluation: ...


@dataclass(frozen=True, slots=True)
class PeerSelectionPolicy:
    policy_id: str
    criteria: tuple[SelectionCriterion, ...]
    include_threshold: Decimal = Decimal("0.65")
    review_threshold: Decimal = Decimal("0.45")

    def __post_init__(self) -> None:
        if not self.policy_id.strip():
            raise ValueError("policy_id must not be blank")
        if not self.criteria:
            raise ValueError("selection policy requires criteria")
        if len({item.kind for item in self.criteria}) != len(self.criteria):
            raise ValueError("selection criteria kinds must be unique")
        if not 0 <= self.review_threshold <= self.include_threshold <= 1:
            raise ValueError("selection thresholds must satisfy 0 <= review <= include <= 1")


DEFAULT_SELECTION_POLICY = PeerSelectionPolicy(
    policy_id="peer-selection-v1",
    criteria=(
        SelectionCriterion(
            SelectionCriterionKind.INDUSTRY,
            SimilarityMethod.DETERMINISTIC,
            Decimal("0.25"),
            required=True,
        ),
        SelectionCriterion(
            SelectionCriterionKind.SUB_INDUSTRY,
            SimilarityMethod.DETERMINISTIC,
            Decimal("0.15"),
        ),
        SelectionCriterion(
            SelectionCriterionKind.COUNTRY,
            SimilarityMethod.DETERMINISTIC,
            Decimal("0.10"),
        ),
        SelectionCriterion(
            SelectionCriterionKind.REVENUE_SCALE,
            SimilarityMethod.DETERMINISTIC,
            Decimal("0.20"),
            minimum_ratio=Decimal("0.25"),
            maximum_ratio=Decimal("4"),
        ),
        SelectionCriterion(
            SelectionCriterionKind.BUSINESS_MODEL,
            SimilarityMethod.SEMANTIC,
            Decimal("0.20"),
        ),
        SelectionCriterion(
            SelectionCriterionKind.CUSTOMER_TYPE,
            SimilarityMethod.SEMANTIC,
            Decimal("0.10"),
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class ComparableSelectionService:
    policy: PeerSelectionPolicy = DEFAULT_SELECTION_POLICY
    semantic_evaluator: SemanticSimilarityEvaluator | None = None

    def select(
        self,
        target: TargetFinancialProfile,
        universe: ComparableUniverse,
        *,
        candidate_financials: Mapping[str, tuple[FinancialMetric, ...]] | None = None,
        overrides: tuple[ManualPeerOverride, ...] = (),
    ) -> ComparableSelectionResult:
        if universe.target_id != target.target.identity.company_id:
            raise ValueError("comparable universe target does not match target profile")
        override_by_id = {item.company_id: item for item in overrides}
        if len(override_by_id) != len(overrides):
            raise ValueError("manual overrides must contain one entry per company")
        universe_ids = {item.identity.company_id for item in universe.companies}
        unknown_overrides = set(override_by_id) - universe_ids
        if unknown_overrides:
            raise ValueError("manual override references a company outside the universe")

        financials = candidate_financials or {}
        decisions = tuple(
            self._assess(
                target,
                company,
                financials.get(company.identity.company_id, ()),
                override_by_id.get(company.identity.company_id),
            )
            for company in universe.companies
        )
        warnings = tuple(
            f"{item.company_id}: selection evidence is missing"
            for item in decisions
            if not item.evidence
        )
        return ComparableSelectionResult(
            universe_id=universe.universe_id,
            decisions=decisions,
            policy_id=self.policy.policy_id,
            selected_at=universe.observed_at,
            warnings=warnings,
        )

    def _assess(
        self,
        target: TargetFinancialProfile,
        company: ComparableCompany,
        candidate_metrics: tuple[FinancialMetric, ...],
        override: ManualPeerOverride | None,
    ) -> PeerSelectionDecision:
        evaluations = tuple(
            self._evaluate(target, company, candidate_metrics, criterion)
            for criterion in self.policy.criteria
        )
        weighted = [
            (criterion.weight, evaluation.score)
            for criterion, evaluation in zip(self.policy.criteria, evaluations, strict=True)
            if evaluation.score is not None
        ]
        assessed_weight = sum((weight for weight, _ in weighted), Decimal("0"))
        total_weight = sum((item.weight for item in self.policy.criteria), Decimal("0"))
        score = None
        if assessed_weight:
            score = (
                sum(
                    (weight * value for weight, value in weighted if value is not None),
                    Decimal("0"),
                )
                / assessed_weight
            )
        coverage = assessed_weight / total_weight
        required_unknown = any(
            criterion.required and evaluation.outcome is CriterionOutcome.UNKNOWN
            for criterion, evaluation in zip(self.policy.criteria, evaluations, strict=True)
        )
        required_failed = any(
            criterion.required and evaluation.outcome is CriterionOutcome.FAIL
            for criterion, evaluation in zip(self.policy.criteria, evaluations, strict=True)
        )
        if required_unknown:
            decision = SelectionDecision.INSUFFICIENT_DATA
        elif required_failed:
            decision = SelectionDecision.EXCLUDE
        elif score is None:
            decision = SelectionDecision.INSUFFICIENT_DATA
        elif score >= self.policy.include_threshold:
            decision = SelectionDecision.INCLUDE
        elif score >= self.policy.review_threshold:
            decision = SelectionDecision.REVIEW
        else:
            decision = SelectionDecision.EXCLUDE

        warnings: list[str] = []
        if override is not None:
            decision = (
                SelectionDecision.INCLUDE
                if override.action is ManualOverrideAction.FORCE_INCLUDE
                else SelectionDecision.EXCLUDE
            )
            warnings.append(f"Analyst {override.action.value} override applied.")
        missing = tuple(
            dict.fromkeys(
                value for evaluation in evaluations for value in evaluation.missing_information
            )
        )
        rationale = _decision_rationale(decision, score, evaluations, override)
        evidence = tuple(
            dict.fromkeys(
                (
                    *company.evidence,
                    *(item for evaluation in evaluations for item in evaluation.evidence),
                )
            )
        )
        return PeerSelectionDecision(
            company_id=company.identity.company_id,
            decision=decision,
            rationale=rationale,
            observations=(),
            evidence=evidence,
            confidence=coverage,
            policy_id=self.policy.policy_id,
            evaluations=evaluations,
            score=score,
            missing_information=missing,
            warnings=tuple(warnings),
            manual_override=override,
        )

    def _evaluate(
        self,
        target: TargetFinancialProfile,
        company: ComparableCompany,
        candidate_metrics: tuple[FinancialMetric, ...],
        criterion: SelectionCriterion,
    ) -> CriterionEvaluation:
        if criterion.method is SimilarityMethod.SEMANTIC:
            if self.semantic_evaluator is None:
                return CriterionEvaluation(
                    criterion.kind,
                    criterion.method,
                    CriterionOutcome.UNKNOWN,
                    "No semantic evaluator was configured; analyst review remains available.",
                    missing_information=(criterion.kind.value,),
                )
            try:
                result = self.semantic_evaluator.evaluate(target, company, criterion)
            except Exception as error:
                return CriterionEvaluation(
                    criterion.kind,
                    criterion.method,
                    CriterionOutcome.UNKNOWN,
                    f"Semantic evaluator failed safely: {type(error).__name__}.",
                    missing_information=(criterion.kind.value,),
                )
            if result.criterion is not criterion.kind or result.method is not criterion.method:
                raise ValueError("semantic evaluator returned a mismatched criterion")
            return result
        return _deterministic_evaluation(target, company, candidate_metrics, criterion)


def _deterministic_evaluation(
    target: TargetFinancialProfile,
    company: ComparableCompany,
    candidate_metrics: tuple[FinancialMetric, ...],
    criterion: SelectionCriterion,
) -> CriterionEvaluation:
    kind = criterion.kind
    if kind is SelectionCriterionKind.REVENUE_SCALE:
        return _revenue_scale(target.metrics, candidate_metrics, criterion)
    values: tuple[str | None, str | None]
    if kind is SelectionCriterionKind.INDUSTRY:
        values = (target.target.industry, company.industry)
    elif kind is SelectionCriterionKind.SUB_INDUSTRY:
        values = (target.target.sub_industry, company.sub_industry)
    elif kind is SelectionCriterionKind.COUNTRY:
        values = (target.target.identity.country, company.identity.country)
    else:
        return CriterionEvaluation(
            kind,
            criterion.method,
            CriterionOutcome.UNKNOWN,
            "This dimension requires an explicit semantic evaluator.",
            missing_information=(kind.value,),
        )
    target_value, peer_value = values
    if target_value is None or peer_value is None:
        return CriterionEvaluation(
            kind,
            criterion.method,
            CriterionOutcome.UNKNOWN,
            f"Cannot compare {kind.value}: target or peer value is missing.",
            evidence=company.evidence,
            missing_information=(kind.value,),
        )
    matches = target_value.casefold() == peer_value.casefold()
    return CriterionEvaluation(
        kind,
        criterion.method,
        CriterionOutcome.PASS if matches else CriterionOutcome.FAIL,
        (
            f"Target '{target_value}' and peer '{peer_value}' "
            f"{'match' if matches else 'do not match'}."
        ),
        score=Decimal("1") if matches else Decimal("0"),
        evidence=company.evidence,
    )


def _revenue_scale(
    target_metrics: tuple[FinancialMetric, ...],
    candidate_metrics: tuple[FinancialMetric, ...],
    criterion: SelectionCriterion,
) -> CriterionEvaluation:
    target = _latest_actual_revenue(target_metrics)
    peer = _latest_actual_revenue(candidate_metrics)
    evidence = () if peer is None else peer.evidence
    if target is None or peer is None:
        return CriterionEvaluation(
            criterion.kind,
            criterion.method,
            CriterionOutcome.UNKNOWN,
            "Comparable actual revenue observations are unavailable.",
            evidence=evidence,
            missing_information=("actual_revenue",),
        )
    if target.currency != peer.currency:
        return CriterionEvaluation(
            criterion.kind,
            criterion.method,
            CriterionOutcome.UNKNOWN,
            "Revenue currencies differ and M2/3 performs no FX conversion.",
            evidence=peer.evidence,
            missing_information=("same_currency_revenue",),
        )
    if target.value <= 0 or peer.value < 0:
        return CriterionEvaluation(
            criterion.kind,
            criterion.method,
            CriterionOutcome.UNKNOWN,
            "Revenue scale requires a positive target and non-negative peer revenue.",
            evidence=peer.evidence,
            missing_information=("positive_revenue",),
        )
    peer_value, _ = convert_unit(peer.value, peer.unit, target.unit)
    ratio = peer_value / target.value
    assert criterion.minimum_ratio is not None and criterion.maximum_ratio is not None
    passes = criterion.minimum_ratio <= ratio <= criterion.maximum_ratio
    return CriterionEvaluation(
        criterion.kind,
        criterion.method,
        CriterionOutcome.PASS if passes else CriterionOutcome.FAIL,
        (
            f"Peer/target revenue ratio {ratio.normalize()} is "
            f"{'inside' if passes else 'outside'} the "
            f"{criterion.minimum_ratio.normalize()}–{criterion.maximum_ratio.normalize()} band."
        ),
        score=Decimal("1") if passes else Decimal("0"),
        evidence=peer.evidence,
    )


def _latest_actual_revenue(metrics: tuple[FinancialMetric, ...]) -> FinancialMetric | None:
    values = [
        item
        for item in metrics
        if item.name is FinancialMetricName.REVENUE
        and item.period.estimate_status is EstimateStatus.ACTUAL
        and item.unit is not FinancialUnit.PER_SHARE
    ]
    if not values:
        return None
    return max(
        values,
        key=lambda item: (
            item.period.end_date or (item.as_of.date() if item.as_of is not None else date.min)
        ),
    )


def _decision_rationale(
    decision: SelectionDecision,
    score: Decimal | None,
    evaluations: tuple[CriterionEvaluation, ...],
    override: ManualPeerOverride | None,
) -> str:
    if override is not None:
        return f"Manual analyst override: {override.rationale}"
    failed = [item.criterion.value for item in evaluations if item.outcome is CriterionOutcome.FAIL]
    unknown = [
        item.criterion.value for item in evaluations if item.outcome is CriterionOutcome.UNKNOWN
    ]
    score_text = "unavailable" if score is None else str(score.quantize(Decimal("0.001")))
    details = []
    if failed:
        details.append("failed=" + ", ".join(failed))
    if unknown:
        details.append("unknown=" + ", ".join(unknown))
    suffix = "; ".join(details) or "all assessed criteria passed"
    return f"Decision {decision.value} under weighted score {score_text}: {suffix}."
