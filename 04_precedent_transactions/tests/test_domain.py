from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ma_precedent_transactions import (
    BuyerType,
    ConsiderationComponent,
    ConsiderationKind,
    ControlType,
    DealLifecycle,
    DealStatus,
    DomainValidationError,
    EstimateStatus,
    EvidenceReference,
    ExtractionMethod,
    FactStatus,
    FinancialMetric,
    FinancialMetricName,
    FinancialPeriod,
    FinancialUnit,
    MetricBasis,
    MonetaryAmount,
    OwnershipObservation,
    PeriodKind,
    PublicStatus,
    SourceReliability,
    TransactionIdentity,
    TransactionParty,
    TransactionRecord,
    TransactionStructure,
    TransactionType,
    ValuationBasis,
    ValuationMeasure,
    ValuationObservation,
)


def evidence(evidence_id: str = "ev-1") -> EvidenceReference:
    return EvidenceReference(
        evidence_id=evidence_id,
        source_type="regulatory_filing",
        document_title="Synthetic merger filing",
        retrieved_at=datetime(2026, 10, 9, 12, 0, tzinfo=UTC),
        reliability=SourceReliability.REGULATORY,
        extraction_method=ExtractionMethod.MANUAL,
        source_url="https://fixtures.invalid/filing",
        publisher="Synthetic regulator",
        publication_date=date(2024, 1, 10),
        document_id="doc-1",
        page=12,
        section="Consideration",
        table="Offer terms",
        chunk_id="chunk-5",
        text_location="paragraph 3",
        excerpt_id="excerpt-9",
        excerpt="The offer is USD 10.00 per share.",
    )


def party(party_id: str, name: str | None) -> TransactionParty:
    return TransactionParty(
        party_id=party_id,
        legal_name=name,
        public_status=PublicStatus.UNKNOWN,
        evidence=(evidence(f"ev-{party_id}"),),
    )


def identity() -> TransactionIdentity:
    return TransactionIdentity(
        transaction_id="txn-1",
        acquirer_party_id="buyer-1",
        target_party_id="target-1",
        transaction_type=TransactionType.STOCK_ACQUISITION,
        announcement_date=date(2024, 1, 10),
        identity_qualifier="First announced bid",
    )


def amount(value: str = "100") -> MonetaryAmount:
    return MonetaryAmount(
        Decimal(value), "usd", FinancialUnit.MILLION, measurement_date=date(2024, 1, 10)
    )


def test_transaction_identity_does_not_depend_on_target_name_or_article_count() -> None:
    first = identity()
    same_deal_from_another_article = TransactionIdentity(
        transaction_id="txn-1",
        acquirer_party_id="buyer-1",
        target_party_id="target-1",
        transaction_type=TransactionType.STOCK_ACQUISITION,
        announcement_date=date(2024, 1, 10),
        identity_qualifier="First announced bid",
    )

    assert first == same_deal_from_another_article
    assert not hasattr(first, "target_name")


def test_acquirer_and_target_must_be_distinct_and_match_record_roles() -> None:
    with pytest.raises(DomainValidationError, match="distinct"):
        TransactionIdentity(
            "txn-bad",
            "same-party",
            "same-party",
            TransactionType.MERGER,
        )

    with pytest.raises(DomainValidationError, match="must match acquirer"):
        TransactionRecord(
            identity=identity(),
            acquirer=party("wrong-buyer", "Wrong Buyer"),
            target=party("target-1", "Target One"),
            lifecycle=DealLifecycle(DealStatus.PENDING, date(2024, 1, 10), date(2024, 1, 10)),
            structure=TransactionStructure(TransactionType.STOCK_ACQUISITION),
        )


def test_party_supports_incomplete_information_explicitly() -> None:
    unknown_party = party("unknown-buyer", None)

    assert unknown_party.legal_name is None
    assert unknown_party.ticker is None
    assert unknown_party.public_status is PublicStatus.UNKNOWN


def test_announcement_and_completion_dates_are_not_interchangeable() -> None:
    lifecycle = DealLifecycle(
        status=DealStatus.COMPLETED,
        announcement_date=date(2024, 1, 10),
        completion_date=date(2024, 5, 1),
        status_as_of=date(2024, 5, 1),
        evidence=(evidence(),),
    )

    assert lifecycle.announcement_date != lifecycle.completion_date
    with pytest.raises(DomainValidationError, match="must not precede"):
        DealLifecycle(
            DealStatus.COMPLETED,
            date(2024, 1, 10),
            announcement_date=date(2024, 1, 10),
            completion_date=date(2024, 1, 9),
        )


def test_completed_and_withdrawn_status_rules_are_explicit() -> None:
    with pytest.raises(DomainValidationError, match="require completion_date"):
        DealLifecycle(DealStatus.COMPLETED, date(2024, 2, 1))

    withdrawn = DealLifecycle(
        DealStatus.WITHDRAWN,
        date(2024, 3, 1),
        announcement_date=date(2024, 1, 10),
        evidence=(evidence(),),
    )
    assert withdrawn.completion_date is None


@pytest.mark.parametrize("value", [Decimal("-0.1"), Decimal("100.1")])
def test_ownership_percentages_must_be_bounded(value: Decimal) -> None:
    with pytest.raises(DomainValidationError, match="between 0 and 100"):
        OwnershipObservation(
            "own-1",
            FactStatus.DIRECTLY_DISCLOSED,
            (evidence(),),
            acquired_percent=value,
        )


def test_partial_ownership_preserves_pre_acquired_and_post_percentages() -> None:
    ownership = OwnershipObservation(
        "own-1",
        FactStatus.DIRECTLY_DISCLOSED,
        (evidence(),),
        pre_deal_percent=Decimal("30"),
        acquired_percent=Decimal("20"),
        post_deal_percent=Decimal("50"),
    )

    assert ownership.acquired_percent == Decimal("20")
    assert ownership.post_deal_percent == Decimal("50")


def test_cash_and_stock_consideration_remain_separate_components() -> None:
    cash = ConsiderationComponent(
        "cash-1",
        ConsiderationKind.CASH,
        FactStatus.DIRECTLY_DISCLOSED,
        (evidence(),),
        amount=amount("50"),
    )
    stock = ConsiderationComponent(
        "stock-1",
        ConsiderationKind.SHARES,
        FactStatus.DIRECTLY_DISCLOSED,
        (evidence(),),
        quantity=Decimal("4.2"),
        quantity_unit="million buyer shares",
    )

    assert cash.amount is not None
    assert stock.amount is None
    assert stock.quantity == Decimal("4.2")


def test_headline_equity_ev_and_per_share_are_distinct_measures() -> None:
    measures = {
        ValuationMeasure.HEADLINE_DEAL_VALUE,
        ValuationMeasure.EQUITY_PURCHASE_PRICE,
        ValuationMeasure.TRANSACTION_ENTERPRISE_VALUE,
        ValuationMeasure.PER_SHARE_OFFER_PRICE,
    }
    observations = tuple(
        ValuationObservation(
            f"val-{measure.value}",
            measure,
            ValuationBasis.EXPLICITLY_DISCLOSED,
            FactStatus.DIRECTLY_DISCLOSED,
            (evidence(f"ev-{measure.value}"),),
            amount("10"),
        )
        for measure in measures
    )

    assert {item.measure for item in observations} == measures


def test_unavailable_value_is_none_not_zero() -> None:
    observation = ValuationObservation(
        "val-undisclosed",
        ValuationMeasure.HEADLINE_DEAL_VALUE,
        ValuationBasis.UNAVAILABLE,
        FactStatus.UNKNOWN,
        (evidence(),),
        amount=None,
    )

    assert observation.amount is None
    with pytest.raises(DomainValidationError, match="cannot have an amount"):
        ValuationObservation(
            "val-invalid",
            ValuationMeasure.HEADLINE_DEAL_VALUE,
            ValuationBasis.UNAVAILABLE,
            FactStatus.UNKNOWN,
            (),
            amount("0"),
        )


def test_transaction_money_rejects_negative_values() -> None:
    with pytest.raises(DomainValidationError, match="must not be negative"):
        amount("-1")


def test_negative_earnings_remain_valid_financial_observations() -> None:
    metric = FinancialMetric(
        metric_id="metric-ebitda",
        name=FinancialMetricName.EBITDA,
        value=Decimal("-8.5"),
        currency="USD",
        unit=FinancialUnit.MILLION,
        period=FinancialPeriod(
            PeriodKind.FISCAL_YEAR,
            "FY2023A",
            EstimateStatus.HISTORICAL,
            date(2023, 1, 1),
            date(2023, 12, 31),
        ),
        basis=MetricBasis.ADJUSTED,
        adjustment_label="Management-adjusted EBITDA",
        measurement_date=date(2024, 1, 10),
        fact_status=FactStatus.DIRECTLY_DISCLOSED,
        evidence=(evidence(),),
    )

    assert metric.value == Decimal("-8.5")
    assert metric.period.end_date == date(2023, 12, 31)


def test_currency_unit_period_and_evidence_are_preserved() -> None:
    metric = FinancialMetric(
        metric_id="metric-revenue",
        name=FinancialMetricName.REVENUE,
        value=Decimal("250"),
        currency="inr",
        unit=FinancialUnit.CRORE,
        period=FinancialPeriod(
            PeriodKind.LTM,
            "LTM Sep-2023",
            EstimateStatus.HISTORICAL,
            date(2022, 10, 1),
            date(2023, 9, 30),
        ),
        basis=MetricBasis.REPORTED,
        measurement_date=date(2024, 1, 10),
        fact_status=FactStatus.DIRECTLY_DISCLOSED,
        evidence=(evidence(),),
    )

    assert metric.currency == "INR"
    assert metric.unit is FinancialUnit.CRORE
    assert metric.period.label == "LTM Sep-2023"
    assert metric.evidence[0].chunk_id == "chunk-5"


def test_record_distinguishes_transaction_structure_from_consideration() -> None:
    record = TransactionRecord(
        identity=identity(),
        acquirer=party("buyer-1", "Buyer One"),
        target=party("target-1", "Target One"),
        lifecycle=DealLifecycle(
            DealStatus.PENDING,
            date(2024, 1, 10),
            announcement_date=date(2024, 1, 10),
        ),
        structure=TransactionStructure(
            TransactionType.STOCK_ACQUISITION,
            BuyerType.STRATEGIC,
            ControlType.CONTROL,
        ),
        consideration=(
            ConsiderationComponent(
                "cash-1",
                ConsiderationKind.CASH,
                FactStatus.DIRECTLY_DISCLOSED,
                (evidence(),),
                amount=amount(),
            ),
        ),
    )

    assert record.structure.transaction_type is TransactionType.STOCK_ACQUISITION
    assert record.consideration[0].kind is ConsiderationKind.CASH
