from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ma_comparable_valuation import (
    CapitalStructure,
    CompanyIdentity,
    ComparableCompany,
    ComparableCompanySnapshot,
    ComparableSelectionResult,
    DataQualityFlag,
    EstimateStatus,
    EvidenceReference,
    FinancialMetric,
    FinancialMetricName,
    FinancialPeriod,
    FinancialUnit,
    MarketMetric,
    MarketMetricKind,
    MetricBasis,
    MultipleDefinition,
    MultipleKind,
    MultipleStatus,
    PeerSelectionDecision,
    PeerSet,
    PeriodKind,
    SelectionDecision,
    ShareCountBasis,
    TradingMultiple,
    ValueFamily,
)


def evidence(evidence_id: str = "ev-1") -> EvidenceReference:
    return EvidenceReference(
        evidence_id=evidence_id,
        source_type="annual_filing",
        source_name="Example FY2026 annual report",
        source_locator="filing.pdf",
        document_id="doc-1",
        chunk_id="chunk-7",
        page_numbers=(42,),
        excerpt="Revenue was INR 500 crore.",
        observed_at=datetime(2026, 7, 15, 10, 0, tzinfo=UTC),
    )


def actual_fy2026() -> FinancialPeriod:
    return FinancialPeriod(
        kind=PeriodKind.FISCAL_YEAR,
        label="FY2026A",
        estimate_status=EstimateStatus.ACTUAL,
        start_date=date(2025, 4, 1),
        end_date=date(2026, 3, 31),
    )


def revenue(metric_id: str = "metric-revenue") -> FinancialMetric:
    return FinancialMetric(
        metric_id=metric_id,
        name=FinancialMetricName.REVENUE,
        value=Decimal("500"),
        currency="inr",
        unit=FinancialUnit.CRORE,
        period=actual_fy2026(),
        basis=MetricBasis.REPORTED,
        evidence=(evidence(),),
        quality_flags=(DataQualityFlag.VERIFIED,),
    )


def company(company_id: str = "peer-a") -> ComparableCompany:
    return ComparableCompany(
        identity=CompanyIdentity(company_id=company_id, name=f"Company {company_id}"),
        industry="Software",
        evidence=(evidence(f"ev-{company_id}"),),
    )


def include_decision(company_id: str = "peer-a") -> PeerSelectionDecision:
    return PeerSelectionDecision(
        company_id=company_id,
        decision=SelectionDecision.INCLUDE,
        rationale="Comparable recurring-revenue business model and scale.",
        observations=(),
        evidence=(evidence(f"select-{company_id}"),),
        confidence=Decimal("0.85"),
        policy_id="selection-v1",
    )


def test_financial_metric_preserves_currency_unit_period_basis_and_evidence() -> None:
    metric = revenue()

    assert metric.currency == "INR"
    assert metric.unit is FinancialUnit.CRORE
    assert metric.period == actual_fy2026()
    assert metric.basis is MetricBasis.REPORTED
    assert metric.evidence[0].page_numbers == (42,)


def test_financial_metric_allows_negative_ebitda_as_an_observation() -> None:
    metric = FinancialMetric(
        metric_id="negative-ebitda",
        name=FinancialMetricName.EBITDA,
        value=Decimal("-12.5"),
        currency="USD",
        unit=FinancialUnit.MILLION,
        period=actual_fy2026(),
        basis=MetricBasis.ADJUSTED,
        adjustment_label="Management-adjusted EBITDA",
        evidence=(evidence(),),
    )

    assert metric.value == Decimal("-12.5")


def test_financial_metric_rejects_missing_evidence_and_invalid_currency() -> None:
    with pytest.raises(ValueError, match="require evidence"):
        FinancialMetric(
            metric_id="revenue",
            name=FinancialMetricName.REVENUE,
            value=Decimal("1"),
            currency="USD",
            unit=FinancialUnit.MILLION,
            period=actual_fy2026(),
            basis=MetricBasis.REPORTED,
            evidence=(),
        )

    with pytest.raises(ValueError, match="three-letter"):
        FinancialMetric(
            metric_id="revenue",
            name=FinancialMetricName.REVENUE,
            value=Decimal("1"),
            currency="US",
            unit=FinancialUnit.MILLION,
            period=actual_fy2026(),
            basis=MetricBasis.REPORTED,
            evidence=(evidence(),),
        )


def test_eps_requires_per_share_unit() -> None:
    with pytest.raises(ValueError, match="EPS must use"):
        FinancialMetric(
            metric_id="eps",
            name=FinancialMetricName.EPS,
            value=Decimal("12.4"),
            currency="INR",
            unit=FinancialUnit.UNITS,
            period=FinancialPeriod(
                PeriodKind.FISCAL_YEAR,
                "FY2027E",
                EstimateStatus.ESTIMATE,
            ),
            basis=MetricBasis.REPORTED,
            evidence=(evidence(),),
        )


def test_actual_and_estimate_periods_are_distinct() -> None:
    actual = FinancialPeriod(PeriodKind.FISCAL_YEAR, "FY2026A", EstimateStatus.ACTUAL)
    estimate = FinancialPeriod(PeriodKind.FISCAL_YEAR, "FY2026E", EstimateStatus.ESTIMATE)

    assert actual != estimate
    assert actual.estimate_status is EstimateStatus.ACTUAL
    assert estimate.estimate_status is EstimateStatus.ESTIMATE


def test_rolling_period_requires_end_date() -> None:
    with pytest.raises(ValueError, match="require an end_date"):
        FinancialPeriod(PeriodKind.LTM, "LTM Jun-2026", EstimateStatus.ACTUAL)

    ltm = FinancialPeriod(
        PeriodKind.LTM,
        "LTM Jun-2026",
        EstimateStatus.ACTUAL,
        end_date=date(2026, 6, 30),
    )
    assert ltm.end_date == date(2026, 6, 30)


def test_metric_json_round_trip_preserves_decimal_and_provenance() -> None:
    original = revenue()

    restored = FinancialMetric.from_json(original.to_json())

    assert restored == original
    assert restored.value == Decimal("500")
    assert restored.evidence[0].chunk_id == "chunk-7"


def test_market_metric_requires_timezone_and_appropriate_currency() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        MarketMetric(
            metric_id="price",
            kind=MarketMetricKind.SHARE_PRICE,
            value=Decimal("10"),
            currency="USD",
            unit=FinancialUnit.PER_SHARE,
            as_of=datetime(2026, 7, 15),
            evidence=(evidence(),),
        )

    shares = MarketMetric(
        metric_id="shares",
        kind=MarketMetricKind.DILUTED_SHARES,
        value=Decimal("25"),
        currency=None,
        unit=FinancialUnit.MILLION,
        as_of=datetime(2026, 7, 15, tzinfo=UTC),
        evidence=(evidence(),),
        share_basis=ShareCountBasis.DILUTED_END_OF_PERIOD,
    )
    assert shares.currency is None


def test_market_metric_rejects_negative_value() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        MarketMetric(
            metric_id="cash",
            kind=MarketMetricKind.CASH_AND_EQUIVALENTS,
            value=Decimal("-1"),
            currency="USD",
            unit=FinancialUnit.MILLION,
            as_of=datetime(2026, 7, 15, tzinfo=UTC),
            evidence=(evidence(),),
        )


def test_capital_structure_rejects_component_after_snapshot_time() -> None:
    component = MarketMetric(
        metric_id="debt",
        kind=MarketMetricKind.DEBT,
        value=Decimal("10"),
        currency="USD",
        unit=FinancialUnit.MILLION,
        as_of=datetime(2026, 7, 16, tzinfo=UTC),
        evidence=(evidence(),),
    )

    with pytest.raises(ValueError, match="must not post-date"):
        CapitalStructure(
            snapshot_id="capital-1",
            as_of=datetime(2026, 7, 15, tzinfo=UTC),
            policy_id="ev-policy-v1",
            components=(component,),
        )


@pytest.mark.parametrize(
    ("kind", "numerator", "denominator"),
    [
        (MultipleKind.EV_REVENUE, ValueFamily.ENTERPRISE_VALUE, FinancialMetricName.REVENUE),
        (MultipleKind.EV_EBITDA, ValueFamily.ENTERPRISE_VALUE, FinancialMetricName.EBITDA),
        (MultipleKind.EV_EBIT, ValueFamily.ENTERPRISE_VALUE, FinancialMetricName.EBIT),
        (
            MultipleKind.PRICE_EARNINGS,
            ValueFamily.EQUITY_VALUE,
            FinancialMetricName.NET_INCOME,
        ),
        (MultipleKind.PRICE_EARNINGS, ValueFamily.SHARE_PRICE, FinancialMetricName.EPS),
    ],
)
def test_supported_multiple_definitions_are_explicit(
    kind: MultipleKind,
    numerator: ValueFamily,
    denominator: FinancialMetricName,
) -> None:
    definition = MultipleDefinition(kind, numerator, denominator)
    assert definition.denominator_metric is denominator


def test_multiple_definition_rejects_market_cap_style_mismatch() -> None:
    with pytest.raises(ValueError, match="invalid numerator/denominator"):
        MultipleDefinition(
            MultipleKind.EV_EBITDA,
            ValueFamily.EQUITY_VALUE,
            FinancialMetricName.EBITDA,
        )


def test_excluded_multiple_retains_raw_value_and_treatment_reason() -> None:
    multiple = TradingMultiple(
        multiple_id="multiple-1",
        company_id="peer-a",
        definition=MultipleDefinition(
            MultipleKind.EV_EBITDA,
            ValueFamily.ENTERPRISE_VALUE,
            FinancialMetricName.EBITDA,
        ),
        numerator_id="ev-1",
        denominator_id="negative-ebitda",
        status=MultipleStatus.NOT_MEANINGFUL,
        value=Decimal("12.3"),
        treatment_reason="Negative EBITDA makes the conventional multiple not meaningful.",
        policy_id="multiple-policy-v1",
    )

    assert multiple.value == Decimal("12.3")
    assert multiple.treatment_reason is not None


def test_selection_result_keeps_included_and_rejected_audit_trail() -> None:
    included = include_decision("peer-a")
    rejected = PeerSelectionDecision(
        company_id="peer-b",
        decision=SelectionDecision.EXCLUDE,
        rationale="Materially different end market.",
        observations=(),
        evidence=(evidence("select-peer-b"),),
        confidence=Decimal("0.9"),
        policy_id="selection-v1",
    )
    result = ComparableSelectionResult(
        universe_id="universe-1",
        decisions=(included, rejected),
        policy_id="selection-v1",
    )

    assert result.selected_company_ids == ("peer-a",)
    assert result.rejected_company_ids == ("peer-b",)


def test_peer_set_requires_snapshots_for_exactly_included_peers() -> None:
    snapshot = ComparableCompanySnapshot(
        company=company("peer-a"),
        as_of=datetime(2026, 7, 15, tzinfo=UTC),
        financial_metrics=(revenue(),),
        market_metrics=(),
    )
    peer_set = PeerSet(
        peer_set_id="peers-1",
        universe_id="universe-1",
        snapshots=(snapshot,),
        decisions=(include_decision("peer-a"),),
    )
    assert peer_set.snapshots == (snapshot,)

    with pytest.raises(ValueError, match="exactly match"):
        PeerSet(
            peer_set_id="peers-2",
            universe_id="universe-1",
            snapshots=(),
            decisions=(include_decision("peer-a"),),
        )
