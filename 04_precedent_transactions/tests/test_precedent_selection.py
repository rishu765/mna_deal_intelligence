from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from ma_precedent_transactions.precedent import (
    ComparableTransactionSelector,
    ManualOverride,
    MinorityTreatment,
    OverrideAction,
    PrecedentSelectionPolicy,
    SelectionDecision,
    precedent_fixture_inputs,
)


def test_selector_excludes_withdrawn_and_partial_transactions() -> None:
    target, _, transactions = precedent_fixture_inputs()
    result = ComparableTransactionSelector().select(target, transactions)
    decisions = {item.transaction_id: item for item in result.decisions}

    assert decisions["txn-withdrawn"].decision is SelectionDecision.EXCLUDE
    assert "status" in decisions["txn-withdrawn"].rationale
    assert decisions["txn-partial"].decision is SelectionDecision.EXCLUDE
    assert "ownership_control" in decisions["txn-partial"].rationale
    assert "txn-cash" in result.selected_transaction_ids


def test_minority_transaction_can_be_retained_as_separate_analysis() -> None:
    target, _, transactions = precedent_fixture_inputs()
    policy = PrecedentSelectionPolicy(
        minority_treatment=MinorityTreatment.SEPARATE,
        require_usable_value=False,
        eligible_transaction_types=(
            *PrecedentSelectionPolicy().eligible_transaction_types,
            transactions[-2].record.structure.transaction_type,
        ),
    )
    result = ComparableTransactionSelector(policy).select(target, (transactions[-2],))

    assert result.decisions[0].decision is SelectionDecision.SEPARATE
    assert result.separate_transaction_ids == ("txn-partial",)


def test_minority_low_comparability_routes_to_review() -> None:
    target, _, transactions = precedent_fixture_inputs()
    partial = transactions[-2]
    policy = PrecedentSelectionPolicy(
        minority_treatment=MinorityTreatment.LOW_COMPARABILITY,
        require_usable_value=False,
        eligible_transaction_types=(
            *PrecedentSelectionPolicy().eligible_transaction_types,
            partial.record.structure.transaction_type,
        ),
    )
    decision = ComparableTransactionSelector(policy).select(target, (partial,)).decisions[0]

    assert decision.decision is SelectionDecision.REVIEW
    assert any("low-comparability" in warning for warning in decision.warnings)


def test_manual_override_requires_audit_rationale_and_applies_last() -> None:
    target, _, transactions = precedent_fixture_inputs()
    withdrawn = transactions[-1]
    with pytest.raises(ValueError, match="rationale"):
        ManualOverride(
            "txn-withdrawn",
            OverrideAction.FORCE_INCLUDE,
            "",
            "analyst@example.test",
            datetime.now(UTC),
        )
    override = ManualOverride(
        "txn-withdrawn",
        OverrideAction.FORCE_INCLUDE,
        "Include only for sensitivity review.",
        "analyst@example.test",
        datetime.now(UTC),
    )
    decision = (
        ComparableTransactionSelector().select(target, (withdrawn,), (override,)).decisions[0]
    )

    assert decision.decision is SelectionDecision.INCLUDE
    assert decision.override == override
    assert "sensitivity" in decision.rationale


def test_date_window_and_size_are_deterministic_hard_filters() -> None:
    target, _, transactions = precedent_fixture_inputs()
    cash = transactions[0]
    policy = replace(
        PrecedentSelectionPolicy(), announced_from=cash.record.lifecycle.announcement_date
    )
    assert policy.announced_from is not None
    future_policy = replace(policy, announced_from=policy.announced_from.replace(year=2025))
    decision = ComparableTransactionSelector(future_policy).select(target, (cash,)).decisions[0]

    assert decision.decision is SelectionDecision.EXCLUDE
    assert "announcement_window" in decision.rationale
