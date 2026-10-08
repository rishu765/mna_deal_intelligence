from ma_precedent_transactions import (
    ComparableCriterion,
    ComparableCriterionKind,
    ComparableSelectionPolicy,
    CriterionMode,
    FinancialMetricName,
    MultipleKind,
    TransactionMultipleDefinition,
    ValuationMeasure,
)


def test_selection_policy_distinguishes_hard_and_qualitative_criteria() -> None:
    policy = ComparableSelectionPolicy(
        "precedent-policy-v1",
        (
            ComparableCriterion(
                "date-window",
                ComparableCriterionKind.ANNOUNCEMENT_PERIOD,
                CriterionMode.HARD_FILTER,
                "Announcement occurred in the approved historical window.",
            ),
            ComparableCriterion(
                "business-model",
                ComparableCriterionKind.BUSINESS_MODEL,
                CriterionMode.QUALITATIVE_JUDGMENT,
                "Target business models are economically comparable.",
            ),
        ),
    )

    assert policy.criteria[0].mode is CriterionMode.HARD_FILTER
    assert policy.criteria[1].mode is CriterionMode.QUALITATIVE_JUDGMENT


def test_multiple_definition_binds_ev_to_the_correct_denominator() -> None:
    definition = TransactionMultipleDefinition(
        MultipleKind.EV_EBITDA,
        ValuationMeasure.TRANSACTION_ENTERPRISE_VALUE,
        FinancialMetricName.EBITDA,
    )

    assert definition.numerator is ValuationMeasure.TRANSACTION_ENTERPRISE_VALUE
