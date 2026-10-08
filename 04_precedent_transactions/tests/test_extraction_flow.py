from __future__ import annotations

from decimal import Decimal

from conftest import ExtractionHarness
from ma_precedent_transactions.domain import (
    DealStatus,
    FactStatus,
    MetricBasis,
    ValuationBasis,
    ValuationMeasure,
)
from ma_precedent_transactions.extraction import VerificationStatus


def test_cash_deal_builds_auditable_record_and_derived_ev(
    extraction_harness: ExtractionHarness,
) -> None:
    result = extraction_harness.records["txn-cash"]
    record = result.record
    assert record.acquirer.legal_name == "Northstar Payments plc"
    assert record.target.legal_name == "Ledgerlane Technologies Ltd."
    assert record.lifecycle.announcement_date is not None
    assert record.lifecycle.completion_date is not None
    assert record.lifecycle.announcement_date.isoformat() == "2024-02-01"
    assert record.lifecycle.completion_date.isoformat() == "2024-06-03"
    assert record.lifecycle.status is DealStatus.COMPLETED
    ev = next(
        item
        for item in record.valuations
        if item.measure is ValuationMeasure.TRANSACTION_ENTERPRISE_VALUE
    )
    assert ev.amount is not None and ev.amount.value == Decimal("425")
    assert ev.basis is ValuationBasis.INDEPENDENTLY_CALCULATED
    assert ev.fact_status is FactStatus.DERIVED_FROM_DISCLOSED
    assert any(item.calculation and "EV =" in item.calculation for item in result.traces)


def test_equity_headline_and_offer_price_remain_distinct(
    extraction_harness: ExtractionHarness,
) -> None:
    measures = {item.measure for item in extraction_harness.records["txn-cash"].record.valuations}
    assert ValuationMeasure.HEADLINE_DEAL_VALUE in measures
    assert ValuationMeasure.EQUITY_PURCHASE_PRICE in measures
    assert ValuationMeasure.PER_SHARE_OFFER_PRICE in measures


def test_mixed_consideration_and_reported_adjusted_financials_are_preserved(
    extraction_harness: ExtractionHarness,
) -> None:
    record = extraction_harness.records["txn-stock"].record
    assert {item.kind.value for item in record.consideration} == {"cash", "shares"}
    ebitda = [item for item in record.target_financials if item.name.value == "ebitda"]
    assert {item.basis for item in ebitda} == {MetricBasis.REPORTED, MetricBasis.ADJUSTED}
    assert {item.value for item in ebitda} == {Decimal("9"), Decimal("12")}


def test_partial_stake_is_not_grossed_up(extraction_harness: ExtractionHarness) -> None:
    record = extraction_harness.records["txn-partial"].record
    ownership = record.ownership[0]
    assert ownership.pre_deal_percent == Decimal("55")
    assert ownership.acquired_percent == Decimal("20")
    assert ownership.post_deal_percent == Decimal("75")
    assert record.valuations[0].amount is not None
    assert record.valuations[0].amount.value == Decimal("75")


def test_withdrawn_status_does_not_become_completed(
    extraction_harness: ExtractionHarness,
) -> None:
    lifecycle = extraction_harness.records["txn-withdrawn"].record.lifecycle
    assert lifecycle.status is DealStatus.WITHDRAWN
    assert lifecycle.completion_date is None


def test_conflicting_values_are_retained_and_flagged(
    extraction_harness: ExtractionHarness,
) -> None:
    result = extraction_harness.records["txn-conflict"]
    assert [item.amount.value for item in result.record.valuations if item.amount] == [
        Decimal("600"),
        Decimal("640"),
    ]
    assert result.conflicts[0].field == "valuation.headline_deal_value"
    verification = next(
        item for item in result.verification if item.field == "valuation.headline_deal_value"
    )
    assert verification.status is VerificationStatus.CONFLICTING
    assert verification.selected_observation_id == "conflict-official-value"


def test_amendment_selects_latest_terms_without_false_conflict(
    extraction_harness: ExtractionHarness,
) -> None:
    result = extraction_harness.records["txn-amended"]
    assert not result.conflicts
    offer = next(
        item for item in result.verification if item.field == "valuation.per_share_offer_price"
    )
    assert offer.selected_observation_id == "amended-revised-offer"
    assert len(result.record.valuations) == 4


def test_undisclosed_value_and_missing_ebitda_are_explicit(
    extraction_harness: ExtractionHarness,
) -> None:
    result = extraction_harness.records["txn-undisclosed"]
    valuation = result.record.valuations[0]
    assert valuation.amount is None
    assert valuation.basis is ValuationBasis.UNAVAILABLE
    statuses = {item.field: item.status for item in result.verification}
    assert statuses["valuation.headline_deal_value"] is VerificationStatus.MISSING
    assert statuses["financial.ebitda"] is VerificationStatus.MISSING


def test_every_material_output_preserves_retrieval_evidence(
    extraction_harness: ExtractionHarness,
) -> None:
    result = extraction_harness.records["txn-cash"]
    evidence_ids = {item.evidence_id for item in result.record.evidence}
    assert evidence_ids
    assert all(
        evidence_id in evidence_ids for trace in result.traces for evidence_id in trace.evidence_ids
    )
