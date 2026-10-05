import json
from decimal import Decimal
from pathlib import Path

import pytest

from ma_target_screening import (
    AcquirerIdentity,
    AcquisitionThesis,
    CriterionCategory,
    CriterionOperator,
    CriterionPriority,
    CriterionRequirement,
    CriterionValueType,
    EvaluationMethod,
    FinancialUnit,
    MoneyAmount,
    MoneyRange,
    NumericRange,
    ScreeningCriterion,
)

EXAMPLES = Path(__file__).parents[1] / "examples"


def criterion(
    *,
    criterion_id: str = "criterion-1",
    category: CriterionCategory = CriterionCategory.INDUSTRY,
    requirement: CriterionRequirement = CriterionRequirement.HARD,
    value_type: CriterionValueType = CriterionValueType.CATEGORICAL,
    operator: CriterionOperator = CriterionOperator.IN,
    value: str | tuple[str, ...] | bool | Decimal | NumericRange | MoneyRange = ("Fintech",),
    evaluation_method: EvaluationMethod = EvaluationMethod.DETERMINISTIC,
    priority: CriterionPriority | None = CriterionPriority.HIGH,
    weight: Decimal | None = None,
) -> ScreeningCriterion:
    return ScreeningCriterion(
        criterion_id=criterion_id,
        category=category,
        requirement=requirement,
        value_type=value_type,
        operator=operator,
        value=value,
        evaluation_method=evaluation_method,
        priority=priority,
        weight=weight,
    )


def test_valid_thesis_normalizes_human_text() -> None:
    thesis = AcquisitionThesis(
        thesis_id="  india-payments  ",
        acquirer=AcquirerIdentity(
            name="  Example   Payments  ", country=" India ", industry=" Payments "
        ),
        objective="  Add   B2B fintech capabilities ",
        criteria=(criterion(),),
    )

    assert thesis.thesis_id == "india-payments"
    assert thesis.acquirer.name == "Example Payments"
    assert thesis.objective == "Add B2B fintech capabilities"


def test_incomplete_thesis_is_valid() -> None:
    thesis = AcquisitionThesis(
        thesis_id="early-stage-thesis",
        acquirer=AcquirerIdentity(name="Enterprise Software Co"),
    )

    assert thesis.objective is None
    assert thesis.criteria == ()


@pytest.mark.parametrize(
    "requirement",
    [CriterionRequirement.HARD, CriterionRequirement.SOFT, CriterionRequirement.EXCLUSION],
)
def test_requirement_types_are_explicit(requirement: CriterionRequirement) -> None:
    assert criterion(requirement=requirement).requirement is requirement


def test_semantic_criterion_requires_semantic_evaluation() -> None:
    semantic = criterion(
        category=CriterionCategory.TECHNOLOGY,
        requirement=CriterionRequirement.SOFT,
        value_type=CriterionValueType.SEMANTIC,
        operator=CriterionOperator.SEMANTIC_MATCH,
        value="Strong enterprise-grade API infrastructure",
        evaluation_method=EvaluationMethod.SEMANTIC,
    )

    assert semantic.evaluation_method is EvaluationMethod.SEMANTIC
    with pytest.raises(ValueError, match="semantic criteria require semantic evaluation"):
        criterion(
            value_type=CriterionValueType.SEMANTIC,
            operator=CriterionOperator.SEMANTIC_MATCH,
            value="API sophistication",
        )


def test_numeric_range_rejects_inverted_bounds() -> None:
    with pytest.raises(ValueError, match="minimum must not exceed maximum"):
        NumericRange(minimum=Decimal("500"), maximum=Decimal("100"), unit="employees")


def test_financial_range_preserves_currency_unit_and_period() -> None:
    revenue = MoneyRange(
        minimum=MoneyAmount(Decimal("100"), "inr", FinancialUnit.CRORE, "fy2025"),
        maximum=MoneyAmount(Decimal("500"), "INR", FinancialUnit.CRORE, "FY2025"),
    )
    revenue_criterion = criterion(
        category=CriterionCategory.REVENUE,
        value_type=CriterionValueType.FINANCIAL,
        operator=CriterionOperator.BETWEEN,
        value=revenue,
    )

    assert revenue.minimum is not None
    assert revenue.minimum.currency == "INR"
    assert revenue.minimum.unit is FinancialUnit.CRORE
    assert revenue.minimum.fiscal_period == "FY2025"
    assert revenue_criterion.value == revenue


def test_financial_range_rejects_incompatible_basis() -> None:
    with pytest.raises(ValueError, match="same currency, unit, and period"):
        MoneyRange(
            minimum=MoneyAmount(Decimal("25"), "USD", FinancialUnit.MILLION, "FY2025"),
            maximum=MoneyAmount(Decimal("50"), "EUR", FinancialUnit.MILLION, "FY2025"),
        )


def test_malformed_currency_and_period_are_rejected() -> None:
    with pytest.raises(ValueError, match="three-letter"):
        MoneyAmount(Decimal("100"), "rupees", FinancialUnit.CRORE)
    with pytest.raises(ValueError, match="FY####"):
        MoneyAmount(Decimal("100"), "INR", FinancialUnit.CRORE, "2025")


def test_range_shape_must_match_operator() -> None:
    with pytest.raises(ValueError, match="range shape requires operator between"):
        criterion(
            category=CriterionCategory.REVENUE,
            value_type=CriterionValueType.FINANCIAL,
            operator=CriterionOperator.GREATER_THAN_OR_EQUAL,
            value=MoneyRange(
                minimum=MoneyAmount(Decimal("100"), "INR", FinancialUnit.CRORE),
                maximum=MoneyAmount(Decimal("500"), "INR", FinancialUnit.CRORE),
            ),
        )


def test_duplicate_criterion_ids_are_rejected_case_insensitively() -> None:
    with pytest.raises(ValueError, match="criterion IDs must be unique"):
        AcquisitionThesis(
            thesis_id="duplicates",
            acquirer=AcquirerIdentity(name="Acquirer"),
            criteria=(criterion(criterion_id="Revenue"), criterion(criterion_id="revenue")),
        )


def test_clear_geographic_contradiction_is_rejected() -> None:
    required = criterion(
        criterion_id="required-geography",
        category=CriterionCategory.GEOGRAPHY,
        value_type=CriterionValueType.GEOGRAPHIC,
        operator=CriterionOperator.IN,
        value=("India",),
    )
    excluded = criterion(
        criterion_id="excluded-geography",
        category=CriterionCategory.GEOGRAPHY,
        requirement=CriterionRequirement.EXCLUSION,
        value_type=CriterionValueType.GEOGRAPHIC,
        operator=CriterionOperator.IN,
        value=("india",),
    )

    with pytest.raises(ValueError, match="both hard requirements and exclusions"):
        AcquisitionThesis(
            thesis_id="geography-conflict",
            acquirer=AcquirerIdentity(name="Acquirer"),
            criteria=(required, excluded),
        )


def test_weight_must_be_normalized_and_priority_must_be_enum() -> None:
    assert criterion(weight=Decimal("0.4")).weight == Decimal("0.4")
    with pytest.raises(ValueError, match="at most 1"):
        criterion(weight=Decimal("1.1"))
    with pytest.raises(ValueError, match="invalid criterion"):
        AcquisitionThesis.from_dict(
            {
                "schema_version": 1,
                "thesis_id": "bad-priority",
                "acquirer": {"name": "Acquirer"},
                "criteria": [
                    {
                        "criterion_id": "industry",
                        "category": "industry",
                        "requirement": "hard",
                        "value_type": "categorical",
                        "operator": "in",
                        "value": {"items": ["Software"]},
                        "evaluation_method": "deterministic",
                        "priority": "urgent",
                    }
                ],
            }
        )


def test_serialization_round_trip_is_lossless() -> None:
    thesis = AcquisitionThesis.from_json((EXAMPLES / "fintech-payments.json").read_text())

    restored = AcquisitionThesis.from_json(thesis.to_json())

    assert restored == thesis
    assert json.loads(thesis.to_json())["schema_version"] == 1


@pytest.mark.parametrize(
    "filename",
    ["fintech-payments.json", "technology-ai-data.json", "partial-thesis.json"],
)
def test_representative_example_theses_validate(filename: str) -> None:
    thesis = AcquisitionThesis.from_json((EXAMPLES / filename).read_text())

    assert thesis.thesis_id
    assert thesis.acquirer.name
