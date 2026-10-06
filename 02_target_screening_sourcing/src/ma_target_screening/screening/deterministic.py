"""Deterministic criterion evaluation with explicit comparability safeguards."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from ma_target_screening.profile import (
    CandidateProfile,
    EnrichmentEvidence,
    ProfileFact,
    ProfileField,
    ProfileFinancialMetric,
)
from ma_target_screening.screening.models import CriterionEvaluation, CriterionOutcome
from ma_target_screening.thesis import (
    CriterionCategory,
    CriterionOperator,
    CriterionRequirement,
    CriterionValueType,
    EvaluationMethod,
    MoneyRange,
    NumericRange,
    ScreeningCriterion,
)

_CATEGORY_FIELDS: dict[CriterionCategory, tuple[ProfileField, ...]] = {
    CriterionCategory.INDUSTRY: (ProfileField.INDUSTRY,),
    CriterionCategory.SUB_INDUSTRY: (ProfileField.SUB_INDUSTRY,),
    CriterionCategory.PRODUCT_CAPABILITY: (
        ProfileField.CAPABILITIES,
        ProfileField.PRODUCTS_SERVICES,
    ),
    CriterionCategory.GEOGRAPHY: (ProfileField.GEOGRAPHIES,),
    CriterionCategory.PROFITABILITY: (ProfileField.PROFITABILITY,),
    CriterionCategory.COMPANY_SIZE: (ProfileField.COMPANY_SIZE,),
    CriterionCategory.EMPLOYEE_COUNT: (ProfileField.EMPLOYEE_COUNT,),
    CriterionCategory.FOUNDED_YEAR: (ProfileField.FOUNDED_YEAR,),
    CriterionCategory.GROWTH: (ProfileField.GROWTH,),
    CriterionCategory.OWNERSHIP: (ProfileField.OWNERSHIP,),
    CriterionCategory.CUSTOMER_TYPE: (ProfileField.CUSTOMER_SEGMENTS,),
    CriterionCategory.TECHNOLOGY: (ProfileField.TECHNOLOGY,),
}

_TRUE_SIGNALS = ("true", "yes", "profitable", "positive ebitda", "positive net income")
_FALSE_SIGNALS = ("false", "no", "not profitable", "unprofitable", "negative ebitda", "loss-making")


@dataclass(frozen=True, slots=True)
class DeterministicScreeningEngine:
    """Evaluate only criteria that M1 explicitly classifies as deterministic."""

    def evaluate(
        self, profile: CandidateProfile, criteria: tuple[ScreeningCriterion, ...]
    ) -> tuple[CriterionEvaluation, ...]:
        return tuple(
            self.evaluate_criterion(profile, criterion)
            for criterion in criteria
            if criterion.evaluation_method is EvaluationMethod.DETERMINISTIC
        )

    def evaluate_criterion(
        self, profile: CandidateProfile, criterion: ScreeningCriterion
    ) -> CriterionEvaluation:
        if criterion.value_type is CriterionValueType.FINANCIAL:
            return self._financial(profile, criterion)
        fields = _CATEGORY_FIELDS.get(criterion.category)
        if fields is None:
            return self._unknown(
                criterion,
                "No deterministic candidate-profile field is mapped to this criterion category.",
            )
        if any(conflict.field in fields for conflict in profile.conflicts):
            return self._unknown(
                criterion,
                "Candidate sources conflict on the field required by this criterion.",
            )
        facts = tuple(fact for fact in profile.facts if fact.field in fields)
        if not facts:
            return self._unknown(criterion, "The candidate profile does not contain this field.")
        if criterion.value_type in {
            CriterionValueType.CATEGORICAL,
            CriterionValueType.GEOGRAPHIC,
        }:
            return self._textual(criterion, facts)
        if criterion.value_type is CriterionValueType.BOOLEAN:
            return self._boolean(criterion, facts)
        if criterion.value_type in {CriterionValueType.NUMERIC, CriterionValueType.DERIVED}:
            return self._numeric(criterion, facts)
        return self._unknown(criterion, "This deterministic criterion type is unsupported.")

    def _financial(
        self, profile: CandidateProfile, criterion: ScreeningCriterion
    ) -> CriterionEvaluation:
        if criterion.category is not CriterionCategory.REVENUE:
            return self._unknown(
                criterion, "Only revenue financial criteria have a defined metric mapping."
            )
        if any(conflict.field is ProfileField.FINANCIALS for conflict in profile.conflicts):
            return self._unknown(
                criterion, "Candidate sources report conflicting financial values."
            )
        assert isinstance(criterion.value, MoneyRange)
        metrics = tuple(
            item for item in profile.financial_metrics if "revenue" in item.metric_name.casefold()
        )
        if not metrics:
            return self._unknown(criterion, "No evidence-backed revenue metric is available.")
        expected = criterion.value.minimum or criterion.value.maximum
        assert expected is not None
        comparable = tuple(
            item
            for item in metrics
            if item.currency == expected.currency
            and item.unit is not None
            and item.unit.casefold() == expected.unit.value
            and (expected.fiscal_period is None or item.fiscal_period == expected.fiscal_period)
        )
        if not comparable:
            bases = ", ".join(
                f"{item.currency or '?'} {item.unit or '?'} {item.fiscal_period or '?'}"
                for item in metrics
            )
            return self._unknown(
                criterion,
                "Available revenue metrics are not comparable with the required currency, "
                f"unit, or period (available: {bases}).",
                values=tuple(item.value for item in metrics),
                evidence=_metric_evidence(metrics),
            )
        if len(comparable) > 1:
            distinct = {item.value for item in comparable}
            if len(distinct) > 1:
                return self._unknown(
                    criterion,
                    "Multiple comparable revenue values remain unresolved.",
                    values=tuple(sorted(distinct)),
                    evidence=_metric_evidence(comparable),
                )
        metric = comparable[0]
        try:
            actual = Decimal(metric.value.replace(",", ""))
        except InvalidOperation:
            return self._unknown(
                criterion,
                "The reported revenue value is not a parseable decimal.",
                values=(metric.value,),
                evidence=metric.evidence,
            )
        matched = _in_money_range(actual, criterion.value)
        return self._result(
            criterion,
            matched,
            f"Revenue {actual} {expected.currency} {expected.unit.value} "
            f"{expected.fiscal_period or '(period not constrained)'} "
            f"{'meets' if matched else 'does not meet'} the required range.",
            values=(metric.value,),
            evidence=metric.evidence,
        )

    def _textual(
        self, criterion: ScreeningCriterion, facts: tuple[ProfileFact, ...]
    ) -> CriterionEvaluation:
        expected = (criterion.value,) if isinstance(criterion.value, str) else criterion.value
        assert isinstance(expected, tuple)
        actual = tuple(fact.value for fact in facts)
        matched = _text_predicate(actual, expected, criterion.operator)
        return self._result(
            criterion,
            matched,
            f"Observed value {'matches' if matched else 'does not match'} the criterion.",
            values=actual,
            evidence=_fact_evidence(facts),
        )

    def _boolean(
        self, criterion: ScreeningCriterion, facts: tuple[ProfileFact, ...]
    ) -> CriterionEvaluation:
        parsed = tuple(_parse_boolean(item.value) for item in facts)
        known = tuple(value for value in parsed if value is not None)
        if not known or len(set(known)) > 1:
            return self._unknown(
                criterion,
                "The available text does not establish an unambiguous boolean value.",
                values=tuple(item.value for item in facts),
                evidence=_fact_evidence(facts),
            )
        expected = bool(criterion.value)
        matched = known[0] is expected
        return self._result(
            criterion,
            matched,
            f"Observed boolean value is {str(known[0]).lower()}, expected {str(expected).lower()}.",
            values=tuple(item.value for item in facts),
            evidence=_fact_evidence(facts),
        )

    def _numeric(
        self, criterion: ScreeningCriterion, facts: tuple[ProfileFact, ...]
    ) -> CriterionEvaluation:
        if isinstance(criterion.value, NumericRange):
            expected_unit = criterion.value.unit
            expected_period = criterion.value.period
            comparable = tuple(
                fact
                for fact in facts
                if (expected_unit is None or expected_unit.casefold() in fact.value.casefold())
                and (expected_period is None or expected_period.casefold() in fact.value.casefold())
            )
            if not comparable:
                return self._unknown(
                    criterion,
                    "Available numeric values do not establish the required unit or period.",
                    values=tuple(item.value for item in facts),
                    evidence=_fact_evidence(facts),
                )
            facts = comparable
        parsed = tuple(_parse_number(item.value) for item in facts)
        known = tuple(value for value in parsed if value is not None)
        if not known or len(set(known)) > 1:
            return self._unknown(
                criterion,
                "The candidate value is missing, non-numeric, or conflicting.",
                values=tuple(item.value for item in facts),
                evidence=_fact_evidence(facts),
            )
        matched = _numeric_predicate(known[0], criterion.value, criterion.operator)
        return self._result(
            criterion,
            matched,
            f"Observed numeric value {known[0]} {'meets' if matched else 'does not meet'} "
            "the criterion.",
            values=tuple(item.value for item in facts),
            evidence=_fact_evidence(facts),
        )

    def _result(
        self,
        criterion: ScreeningCriterion,
        predicate_matched: bool,
        reason: str,
        *,
        values: tuple[str, ...],
        evidence: tuple[EnrichmentEvidence, ...],
    ) -> CriterionEvaluation:
        exclusion = criterion.requirement is CriterionRequirement.EXCLUSION
        passed = not predicate_matched if exclusion else predicate_matched
        outcome = CriterionOutcome.PASS if passed else CriterionOutcome.FAIL
        if exclusion:
            reason = (
                "Exclusion was not triggered. " if passed else "Exclusion was triggered. "
            ) + reason
        score = None
        if criterion.requirement is CriterionRequirement.SOFT:
            score = Decimal("1") if passed else Decimal("0")
        return CriterionEvaluation(
            criterion_id=criterion.criterion_id,
            category=criterion.category,
            requirement=criterion.requirement,
            evaluation_method=criterion.evaluation_method,
            outcome=outcome,
            reason=reason,
            candidate_values=values,
            evidence=evidence,
            score=score,
        )

    @staticmethod
    def _unknown(
        criterion: ScreeningCriterion,
        reason: str,
        *,
        values: tuple[str, ...] = (),
        evidence: tuple[EnrichmentEvidence, ...] = (),
    ) -> CriterionEvaluation:
        return CriterionEvaluation(
            criterion_id=criterion.criterion_id,
            category=criterion.category,
            requirement=criterion.requirement,
            evaluation_method=criterion.evaluation_method,
            outcome=CriterionOutcome.UNKNOWN,
            reason=reason,
            candidate_values=values,
            evidence=evidence,
            uncertainty=reason,
        )


def _text_predicate(
    actual: tuple[str, ...], expected: tuple[str, ...], operator: CriterionOperator
) -> bool:
    actual_values = tuple(value.casefold() for value in actual)
    expected_values = tuple(value.casefold() for value in expected)

    def matches(left: str, right: str) -> bool:
        return left == right or right in left or left in right

    any_match = any(
        matches(observed, target) for observed in actual_values for target in expected_values
    )
    if operator is CriterionOperator.NOT_EQUALS:
        return not any_match
    if operator in {
        CriterionOperator.EQUALS,
        CriterionOperator.IN,
        CriterionOperator.CONTAINS,
    }:
        return any_match
    return False


def _parse_boolean(value: str) -> bool | None:
    normalized = value.casefold()
    if any(signal in normalized for signal in _FALSE_SIGNALS):
        return False
    if any(signal in normalized for signal in _TRUE_SIGNALS):
        return True
    return None


def _parse_number(value: str) -> Decimal | None:
    match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", value)
    if match is None:
        return None
    try:
        return Decimal(match.group(0).replace(",", ""))
    except InvalidOperation:
        return None


def _numeric_predicate(
    actual: Decimal,
    expected: str | tuple[str, ...] | bool | Decimal | NumericRange | MoneyRange,
    operator: CriterionOperator,
) -> bool:
    if isinstance(expected, NumericRange):
        if expected.minimum is not None and actual < expected.minimum:
            return False
        return expected.maximum is None or actual <= expected.maximum
    if not isinstance(expected, Decimal):
        return False
    comparisons = {
        CriterionOperator.EQUALS: actual == expected,
        CriterionOperator.NOT_EQUALS: actual != expected,
        CriterionOperator.GREATER_THAN: actual > expected,
        CriterionOperator.GREATER_THAN_OR_EQUAL: actual >= expected,
        CriterionOperator.LESS_THAN: actual < expected,
        CriterionOperator.LESS_THAN_OR_EQUAL: actual <= expected,
    }
    return comparisons.get(operator, False)


def _in_money_range(actual: Decimal, expected: MoneyRange) -> bool:
    if expected.minimum is not None and actual < expected.minimum.amount:
        return False
    return expected.maximum is None or actual <= expected.maximum.amount


def _fact_evidence(facts: tuple[ProfileFact, ...]) -> tuple[EnrichmentEvidence, ...]:
    return tuple(dict.fromkeys(evidence for fact in facts for evidence in fact.evidence))


def _metric_evidence(
    metrics: tuple[ProfileFinancialMetric, ...],
) -> tuple[EnrichmentEvidence, ...]:
    evidence: list[EnrichmentEvidence] = []
    for metric in metrics:
        evidence.extend(metric.evidence)
    return tuple(dict.fromkeys(evidence))
