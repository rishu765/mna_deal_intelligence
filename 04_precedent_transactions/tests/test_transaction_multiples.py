from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from ma_precedent_transactions.domain import (
    EstimateStatus,
    FinancialUnit,
    MultipleKind,
    MultipleStatus,
    ValuationMeasure,
)
from ma_precedent_transactions.extraction import FactConflict, VerifiedTransactionRecord
from ma_precedent_transactions.precedent import (
    ComparableTransactionSelector,
    TransactionMultipleEngine,
    TransactionMultiplePolicy,
    TransactionMultipleResult,
    precedent_fixture_inputs,
)


def _calculated(
    transaction_id: str = "txn-cash",
) -> tuple[VerifiedTransactionRecord, tuple[TransactionMultipleResult, ...]]:
    target, _, transactions = precedent_fixture_inputs()
    transaction = next(
        item for item in transactions if item.record.identity.transaction_id == transaction_id
    )
    decision = ComparableTransactionSelector().select(target, (transaction,)).decisions[0]
    return transaction, TransactionMultipleEngine().calculate(transaction, decision)


def test_engine_uses_derived_ev_and_preserves_calculation_trace() -> None:
    _, results = _calculated()
    revenue = next(
        item for item in results if item.contract.definition.kind is MultipleKind.EV_REVENUE
    )

    assert revenue.contract.status is MultipleStatus.INCLUDED
    assert revenue.contract.value == Decimal("425") / Decimal("96")
    assert revenue.numerator_basis is not None
    assert revenue.numerator_basis.value == "independently_calculated"
    assert any("Numerator is derived" in warning for warning in revenue.warnings)


def test_engine_calculates_supported_ev_and_equity_multiples_separately() -> None:
    _, results = _calculated("txn-financial")
    by_kind = {item.contract.definition.kind: item for item in results}

    assert by_kind[MultipleKind.EV_REVENUE].numerator_value == Decimal("360")
    assert by_kind[MultipleKind.EV_EBITDA].contract.value == Decimal("22.5")
    assert by_kind[MultipleKind.EV_EBIT].contract.value == Decimal("360") / Decimal("11")
    assert by_kind[MultipleKind.EQUITY_VALUE_NET_INCOME].numerator_value == Decimal("340")
    assert by_kind[MultipleKind.EQUITY_VALUE_NET_INCOME].contract.value == Decimal("340") / Decimal(
        "7"
    )


def test_ambiguous_headline_value_is_not_used_as_enterprise_value() -> None:
    target, _, transactions = precedent_fixture_inputs()
    stock = next(
        item for item in transactions if item.record.identity.transaction_id == "txn-stock"
    )
    ambiguous_only = replace(
        stock,
        record=replace(
            stock.record,
            valuations=tuple(
                item
                for item in stock.record.valuations
                if item.measure is ValuationMeasure.HEADLINE_DEAL_VALUE
            ),
        ),
    )
    decision = ComparableTransactionSelector().select(target, (ambiguous_only,)).decisions[0]
    results = TransactionMultipleEngine().calculate(ambiguous_only, decision)

    assert all(item.contract.status is not MultipleStatus.INCLUDED for item in results)
    assert all(item.numerator_value is None for item in results)


def test_negative_denominators_are_not_meaningful() -> None:
    _, results = _calculated("txn-negative")
    by_kind = {item.contract.definition.kind: item for item in results}

    assert by_kind[MultipleKind.EV_REVENUE].contract.status is MultipleStatus.INCLUDED
    assert by_kind[MultipleKind.EV_EBITDA].contract.status is MultipleStatus.NOT_MEANINGFUL
    assert by_kind[MultipleKind.EV_EBIT].contract.status is MultipleStatus.NOT_MEANINGFUL
    assert (
        by_kind[MultipleKind.EQUITY_VALUE_NET_INCOME].contract.status
        is MultipleStatus.NOT_MEANINGFUL
    )


def test_future_and_stale_financial_periods_are_excluded() -> None:
    transaction, _ = _calculated("txn-financial")
    target, _, _ = precedent_fixture_inputs()
    metric = transaction.record.target_financials[0]
    assert metric.period.end_date is not None
    future = replace(
        metric,
        measurement_date=date(2028, 12, 31),
        period=replace(metric.period, end_date=date(2028, 12, 31)),
    )
    changed = replace(transaction, record=replace(transaction.record, target_financials=(future,)))
    decision = ComparableTransactionSelector().select(target, (changed,)).decisions[0]
    result = TransactionMultipleEngine().calculate(changed, decision)[0]

    assert result.contract.status is MultipleStatus.EXCLUDED
    assert "post-dates transaction announcement" in (result.contract.treatment_reason or "")


def test_currency_mismatch_is_excluded_and_units_are_normalized() -> None:
    transaction, _ = _calculated("txn-financial")
    target, _, _ = precedent_fixture_inputs()
    revenue = transaction.record.target_financials[0]
    mismatch = replace(revenue, currency="GBP", value=Decimal("8"), unit=FinancialUnit.CRORE)
    changed = replace(
        transaction, record=replace(transaction.record, target_financials=(mismatch,))
    )
    decision = ComparableTransactionSelector().select(target, (changed,)).decisions[0]
    result = TransactionMultipleEngine().calculate(changed, decision)[0]

    assert result.contract.status is MultipleStatus.EXCLUDED
    assert "currencies differ" in (result.contract.treatment_reason or "")

    converted = replace(mismatch, currency="USD")
    changed = replace(
        transaction, record=replace(transaction.record, target_financials=(converted,))
    )
    decision = ComparableTransactionSelector().select(target, (changed,)).decisions[0]
    result = TransactionMultipleEngine().calculate(changed, decision)[0]
    assert result.contract.value == Decimal("4.5")


def test_policy_can_exclude_forecast_denominators() -> None:
    transaction, _ = _calculated("txn-financial")
    target, _, _ = precedent_fixture_inputs()
    metric = transaction.record.target_financials[0]
    forecast = replace(
        metric,
        period=replace(metric.period, estimate_status=EstimateStatus.FORECAST),
    )
    changed = replace(
        transaction, record=replace(transaction.record, target_financials=(forecast,))
    )
    decision = ComparableTransactionSelector().select(target, (changed,)).decisions[0]
    result = TransactionMultipleEngine(
        TransactionMultiplePolicy(allow_forecast_periods=False)
    ).calculate(changed, decision)[0]

    assert result.contract.status is MultipleStatus.EXCLUDED
    assert "Forecast denominators" in (result.contract.treatment_reason or "")


def test_reported_and_adjusted_ebitda_remain_separate_observations() -> None:
    _, results = _calculated("txn-stock")
    ebitda = [item for item in results if item.contract.definition.kind is MultipleKind.EV_EBITDA]

    assert {item.denominator_basis.value for item in ebitda if item.denominator_basis} == {
        "reported",
        "adjusted",
    }


def test_unresolved_financial_conflict_excludes_denominator() -> None:
    transaction, _ = _calculated("txn-financial")
    target, _, _ = precedent_fixture_inputs()
    revenue = transaction.record.target_financials[0]
    conflict = FactConflict(
        f"financial.revenue.{revenue.period.label}.reported",
        ("obs-a", "obs-b"),
        ("80", "82"),
        "Sources disagree on target revenue.",
    )
    changed = replace(transaction, conflicts=(conflict,))
    decision = ComparableTransactionSelector().select(target, (changed,)).decisions[0]
    result = TransactionMultipleEngine().calculate(changed, decision)[0]

    assert result.contract.status is MultipleStatus.EXCLUDED
    assert "unresolved source conflicts" in (result.contract.treatment_reason or "")
