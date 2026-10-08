from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ma_precedent_transactions.domain import (
    CapitalComponentKind,
    CapitalStructureComponent,
    EvidenceReference,
    ExtractionMethod,
    FactStatus,
    FinancialUnit,
    MonetaryAmount,
    SourceReliability,
    ValuationBasis,
    ValuationMeasure,
    ValuationObservation,
)
from ma_precedent_transactions.errors import NormalizationError
from ma_precedent_transactions.extraction import (
    convert_unit,
    derive_enterprise_value,
    normalize_period,
    parse_decimal,
    parse_unit,
)


def _evidence() -> EvidenceReference:
    return EvidenceReference(
        "e1",
        "filing",
        "Filing",
        datetime(2025, 1, 1, tzinfo=UTC),
        SourceReliability.REGULATORY,
        ExtractionMethod.RULE_BASED,
    )


def test_unit_normalization_supports_billion_and_crore() -> None:
    assert convert_unit(Decimal("2"), parse_unit("billion"), FinancialUnit.MILLION) == (
        Decimal("2000"),
        Decimal("1000"),
    )
    assert convert_unit(Decimal("4"), parse_unit("crore"), FinancialUnit.MILLION) == (
        Decimal("40"),
        Decimal("10"),
    )


def test_period_normalization_preserves_kind_and_estimate_status() -> None:
    assert normalize_period("FY2025").label == "FY2025A"
    assert normalize_period("FY2027E").label == "FY2027E"
    ltm = normalize_period("LTM Sep-2026")
    assert ltm.label == "LTM Sep-2026"
    assert ltm.start_date == date(2025, 10, 1)
    assert ltm.end_date == date(2026, 9, 30)


def test_negative_earnings_are_parseable_but_negative_money_is_not() -> None:
    assert parse_decimal("(12.5)", allow_negative=True) == Decimal("-12.5")
    with pytest.raises(NormalizationError, match="negative"):
        parse_decimal("-1", allow_negative=False)


def test_cross_currency_ev_bridge_is_rejected() -> None:
    evidence = (_evidence(),)
    equity = ValuationObservation(
        "eq",
        ValuationMeasure.EQUITY_PURCHASE_PRICE,
        ValuationBasis.EXPLICITLY_DISCLOSED,
        FactStatus.DIRECTLY_DISCLOSED,
        evidence,
        MonetaryAmount(Decimal("100"), "USD", FinancialUnit.MILLION),
    )
    debt = CapitalStructureComponent(
        "debt",
        CapitalComponentKind.DEBT,
        MonetaryAmount(Decimal("10"), "GBP", FinancialUnit.MILLION),
        date(2024, 12, 31),
        FactStatus.DIRECTLY_DISCLOSED,
        evidence,
    )
    cash = CapitalStructureComponent(
        "cash",
        CapitalComponentKind.CASH,
        MonetaryAmount(Decimal("5"), "USD", FinancialUnit.MILLION),
        date(2024, 12, 31),
        FactStatus.DIRECTLY_DISCLOSED,
        evidence,
    )
    with pytest.raises(NormalizationError, match="same currency"):
        derive_enterprise_value(equity=equity, debt=debt, cash=cash, observation_id="ev")
