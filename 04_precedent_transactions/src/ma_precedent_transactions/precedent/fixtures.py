"""Synthetic M4/5 inputs expressed as verified M3 transaction records."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

from ma_precedent_transactions.demo_m3 import build_fixture_records
from ma_precedent_transactions.domain import (
    BuyerType,
    CapitalComponentKind,
    CapitalStructureComponent,
    CapitalStructureSnapshot,
    ControlType,
    DealLifecycle,
    DealStatus,
    EstimateStatus,
    EvidenceReference,
    FactStatus,
    FinancialMetric,
    FinancialMetricName,
    FinancialPeriod,
    FinancialUnit,
    MetricBasis,
    MonetaryAmount,
    PeriodKind,
    TransactionIdentity,
    TransactionParty,
    TransactionStructure,
    TransactionType,
    ValuationBasis,
    ValuationMeasure,
    ValuationObservation,
)
from ma_precedent_transactions.extraction import VerifiedTransactionRecord
from ma_precedent_transactions.precedent.models import (
    TargetCapitalProfile,
    TargetComparabilityProfile,
    TargetValuationProfile,
)


def precedent_fixture_inputs() -> tuple[
    TargetComparabilityProfile,
    TargetValuationProfile,
    tuple[VerifiedTransactionRecord, ...],
]:
    m3 = build_fixture_records()
    cash = m3["txn-cash"]
    stock = _with_stock_values(m3["txn-stock"])
    generated = (
        _synthetic(
            cash,
            "txn-financial",
            BuyerType.FINANCIAL,
            "360",
            "80",
            "16",
            "11",
            "7",
            date(2023, 8, 1),
        ),
        _synthetic(
            cash, "txn-outlier", BuyerType.STRATEGIC, "1200", "70", "14", "9", "5", date(2024, 4, 1)
        ),
        _synthetic(
            cash,
            "txn-negative",
            BuyerType.STRATEGIC,
            "250",
            "60",
            "-5",
            "-8",
            "-9",
            date(2022, 6, 1),
        ),
    )
    transactions = (cash, stock, *generated, m3["txn-partial"], m3["txn-withdrawn"])
    evidence = cash.record.evidence
    period = FinancialPeriod(
        PeriodKind.LTM,
        "LTM Dec-2025",
        EstimateStatus.HISTORICAL,
        date(2025, 1, 1),
        date(2025, 12, 31),
    )
    metrics = (
        _metric(
            "target-revenue",
            FinancialMetricName.REVENUE,
            "100",
            period,
            MetricBasis.REPORTED,
            evidence,
        ),
        _metric(
            "target-ebitda-reported",
            FinancialMetricName.EBITDA,
            "20",
            period,
            MetricBasis.REPORTED,
            evidence,
        ),
        _metric(
            "target-ebitda-adjusted",
            FinancialMetricName.EBITDA,
            "22",
            period,
            MetricBasis.ADJUSTED,
            evidence,
            "Adjusted EBITDA",
        ),
        _metric(
            "target-ebit", FinancialMetricName.EBIT, "14", period, MetricBasis.REPORTED, evidence
        ),
        _metric(
            "target-net-income",
            FinancialMetricName.NET_INCOME,
            "8",
            period,
            MetricBasis.REPORTED,
            evidence,
        ),
    )
    components = tuple(
        CapitalStructureComponent(
            f"target-{kind.value}",
            kind,
            MonetaryAmount(value, "USD", FinancialUnit.MILLION, date(2025, 12, 31)),
            date(2025, 12, 31),
            FactStatus.DIRECTLY_DISCLOSED,
            evidence,
        )
        for kind, value in (
            (CapitalComponentKind.DEBT, Decimal("30")),
            (CapitalComponentKind.CASH, Decimal("10")),
            (CapitalComponentKind.PREFERRED_STOCK, Decimal("5")),
            (CapitalComponentKind.NONCONTROLLING_INTEREST, Decimal("3")),
        )
    )
    capital = TargetCapitalProfile(
        CapitalStructureSnapshot("target-capital", date(2025, 12, 31), components),
        Decimal("50"),
        FinancialUnit.MILLION,
        date(2025, 12, 31),
        "diluted_end_of_period",
        evidence,
    )
    comparable = TargetComparabilityProfile(
        "target-fintech",
        "B2B fintech infrastructure",
        "Enterprise payments, ledger, and banking API software",
        ("payments", "ledger", "banking API"),
        ("enterprise", "financial institution"),
        ("United States", "United Kingdom"),
        metrics[0],
    )
    return comparable, TargetValuationProfile("target-fintech", metrics, capital), transactions


def _with_stock_values(transaction: VerifiedTransactionRecord) -> VerifiedTransactionRecord:
    evidence = transaction.record.evidence
    additions = (
        _value(
            "stock-ev",
            ValuationMeasure.TRANSACTION_ENTERPRISE_VALUE,
            "540",
            date(2023, 5, 12),
            evidence,
        ),
        _value(
            "stock-equity",
            ValuationMeasure.EQUITY_PURCHASE_PRICE,
            "510",
            date(2023, 5, 12),
            evidence,
        ),
    )
    return replace(
        transaction,
        record=replace(transaction.record, valuations=(*transaction.record.valuations, *additions)),
    )


def _synthetic(
    base: VerifiedTransactionRecord,
    transaction_id: str,
    buyer_type: BuyerType,
    ev: str,
    revenue: str,
    ebitda: str,
    ebit: str,
    net_income: str,
    announced: date,
) -> VerifiedTransactionRecord:
    evidence = base.record.evidence
    acquirer = TransactionParty(f"party:{transaction_id}:acquirer", f"{transaction_id} Buyer")
    target = replace(
        base.record.target,
        party_id=f"party:{transaction_id}:target",
        legal_name=f"{transaction_id} Target",
    )
    year = announced.year - 1
    period = FinancialPeriod(
        PeriodKind.LTM,
        f"LTM Dec-{year}",
        EstimateStatus.HISTORICAL,
        date(year, 1, 1),
        date(year, 12, 31),
    )
    metrics = tuple(
        _metric(
            f"{transaction_id}-{name.value}", name, value, period, MetricBasis.REPORTED, evidence
        )
        for name, value in (
            (FinancialMetricName.REVENUE, revenue),
            (FinancialMetricName.EBITDA, ebitda),
            (FinancialMetricName.EBIT, ebit),
            (FinancialMetricName.NET_INCOME, net_income),
        )
    )
    valuations = (
        _value(
            transaction_id + "-ev",
            ValuationMeasure.TRANSACTION_ENTERPRISE_VALUE,
            ev,
            announced,
            evidence,
        ),
        _value(
            transaction_id + "-equity",
            ValuationMeasure.EQUITY_PURCHASE_PRICE,
            str(Decimal(ev) - 20),
            announced,
            evidence,
        ),
    )
    record = replace(
        base.record,
        identity=TransactionIdentity(
            transaction_id,
            acquirer.party_id,
            target.party_id,
            TransactionType.STOCK_ACQUISITION,
            announced,
        ),
        acquirer=acquirer,
        target=target,
        lifecycle=DealLifecycle(
            DealStatus.COMPLETED,
            announced + timedelta(days=90),
            announced,
            announced + timedelta(days=90),
            evidence,
        ),
        structure=TransactionStructure(
            TransactionType.STOCK_ACQUISITION,
            buyer_type,
            ControlType.CONTROL,
            "United States",
            "Control acquisition of B2B fintech infrastructure.",
            evidence,
        ),
        valuations=valuations,
        ownership=(),
        target_financials=metrics,
        capital_structure=(),
    )
    return replace(base, record=record, verification=(), conflicts=(), traces=(), warnings=())


def _value(
    suffix: str,
    measure: ValuationMeasure,
    value: str,
    measured: date,
    evidence: tuple[EvidenceReference, ...],
) -> ValuationObservation:
    return ValuationObservation(
        f"valuation:{suffix}",
        measure,
        ValuationBasis.EXPLICITLY_DISCLOSED,
        FactStatus.DIRECTLY_DISCLOSED,
        evidence,
        MonetaryAmount(Decimal(value), "USD", FinancialUnit.MILLION, measured),
    )


def _metric(
    metric_id: str,
    name: FinancialMetricName,
    value: str,
    period: FinancialPeriod,
    basis: MetricBasis,
    evidence: tuple[EvidenceReference, ...],
    adjustment_label: str | None = None,
) -> FinancialMetric:
    assert period.end_date is not None
    return FinancialMetric(
        metric_id,
        name,
        Decimal(value),
        FinancialUnit.MILLION,
        period,
        basis,
        period.end_date,
        FactStatus.DIRECTLY_DISCLOSED,
        evidence,
        "USD",
        adjustment_label,
    )
