"""Credential-free M4/5 fixtures with varied multiple-quality outcomes."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from ma_comparable_valuation.domain import (
    CapitalStructure,
    CompanyIdentity,
    ComparableCompany,
    ComparableCompanySnapshot,
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
    PeerSelectionDecision,
    PeerSet,
    PeriodKind,
    SelectionDecision,
    ShareCountBasis,
    TargetFinancialProfile,
    ValueFamily,
)
from ma_comparable_valuation.fixtures import FixtureTargetProfileProvider
from ma_comparable_valuation.valuation import MultipleRequest

VALUATION_TIME = datetime(2026, 10, 7, 10, 0, tzinfo=UTC)


def demo_target_profile() -> TargetFinancialProfile:
    path = Path(__file__).resolve().parents[2] / "data" / "targetco_profile.json"
    provider = FixtureTargetProfileProvider(path)
    target, _ = provider.load()
    return provider.get_target_profile(target)


def _evidence(peer_id: str, field: str) -> EvidenceReference:
    return EvidenceReference(
        f"valuation-fixture:{peer_id}:{field}",
        "structured_fixture",
        "M4/5 valuation fixture",
        VALUATION_TIME,
        source_locator="valuation_fixtures.py",
        excerpt=f"{peer_id} {field} fixture observation.",
        extraction_method="structured_fixture",
    )


def _period(*, forecast: bool = False) -> FinancialPeriod:
    if forecast:
        return FinancialPeriod(
            PeriodKind.FISCAL_YEAR,
            "FY2027E",
            EstimateStatus.ESTIMATE,
        )
    return FinancialPeriod(
        PeriodKind.LTM,
        "LTM Jun-2026",
        EstimateStatus.ACTUAL,
        date(2025, 7, 1),
        date(2026, 6, 30),
    )


def _financial(
    peer_id: str,
    name: FinancialMetricName,
    value: str,
    *,
    forecast: bool = False,
    basis: MetricBasis = MetricBasis.REPORTED,
) -> FinancialMetric:
    return FinancialMetric(
        f"valuation-fixture:{peer_id}:{'fy2027e' if forecast else 'ltm'}:{name.value}",
        name,
        Decimal(value),
        "INR",
        FinancialUnit.PER_SHARE if name is FinancialMetricName.EPS else FinancialUnit.MILLION,
        _period(forecast=forecast),
        basis,
        (_evidence(peer_id, name.value),),
        (DataQualityFlag.SOURCE_BACKED,),
        datetime(2026, 6, 30, tzinfo=UTC),
        "fixture adjusted basis" if basis is MetricBasis.ADJUSTED else None,
    )


def _market(
    peer_id: str,
    kind: MarketMetricKind,
    value: str,
    *,
    currency: str | None = "INR",
    as_of: datetime = VALUATION_TIME,
) -> MarketMetric:
    return MarketMetric(
        f"valuation-fixture:{peer_id}:{kind.value}",
        kind,
        Decimal(value),
        FinancialUnit.PER_SHARE if kind is MarketMetricKind.SHARE_PRICE else FinancialUnit.MILLION,
        as_of,
        (_evidence(peer_id, kind.value),),
        currency,
        (DataQualityFlag.SOURCE_BACKED,),
        (
            ShareCountBasis.DILUTED_END_OF_PERIOD
            if kind is MarketMetricKind.DILUTED_SHARES
            else None
        ),
    )


def _snapshot(
    peer_id: str,
    name: str,
    *,
    price: str,
    shares: str,
    debt: str | None,
    cash: str,
    revenue: str,
    ebitda: str | None,
    ebit: str | None,
    net_income: str | None,
    eps: str | None,
    forward_revenue: str | None = None,
    forward_ebitda: str | None = None,
    forward_eps: str | None = None,
) -> ComparableCompanySnapshot:
    company = ComparableCompany(
        CompanyIdentity(peer_id, name, ticker=peer_id.upper(), exchange="NSE", country="India"),
        industry="Business Services",
        sub_industry="Technology-enabled services",
        business_description=f"{name} is a fictional comparable company.",
        reporting_currency="INR",
        evidence=(_evidence(peer_id, "company"),),
    )
    financial: list[FinancialMetric] = [
        _financial(peer_id, FinancialMetricName.REVENUE, revenue),
    ]
    for metric_name, value in (
        (FinancialMetricName.EBITDA, ebitda),
        (FinancialMetricName.EBIT, ebit),
        (FinancialMetricName.NET_INCOME, net_income),
        (FinancialMetricName.EPS, eps),
    ):
        if value is not None:
            financial.append(_financial(peer_id, metric_name, value))
    for metric_name, value in (
        (FinancialMetricName.REVENUE, forward_revenue),
        (FinancialMetricName.EBITDA, forward_ebitda),
        (FinancialMetricName.EPS, forward_eps),
    ):
        if value is not None:
            financial.append(_financial(peer_id, metric_name, value, forecast=True))
    market = [
        _market(peer_id, MarketMetricKind.SHARE_PRICE, price),
        _market(peer_id, MarketMetricKind.DILUTED_SHARES, shares, currency=None),
        _market(
            peer_id,
            MarketMetricKind.CASH_AND_EQUIVALENTS,
            cash,
            as_of=datetime(2026, 6, 30, tzinfo=UTC),
        ),
    ]
    if debt is not None:
        market.append(
            _market(
                peer_id,
                MarketMetricKind.DEBT,
                debt,
                as_of=datetime(2026, 6, 30, tzinfo=UTC),
            )
        )
    capital = tuple(
        item
        for item in market
        if item.kind
        in {
            MarketMetricKind.DILUTED_SHARES,
            MarketMetricKind.CASH_AND_EQUIVALENTS,
            MarketMetricKind.DEBT,
        }
    )
    return ComparableCompanySnapshot(
        company,
        VALUATION_TIME,
        tuple(financial),
        tuple(market),
        capital_structure=CapitalStructure(
            f"valuation-fixture:{peer_id}:capital",
            VALUATION_TIME,
            "fixture-capital-v1",
            capital,
        ),
        quality_flags=(DataQualityFlag.SOURCE_BACKED,),
    )


def demo_peer_set() -> PeerSet:
    """Return five peers: normal, high, negative, and missing-input cases."""

    snapshots = (
        _snapshot(
            "peer-a",
            "Peer A",
            price="125",
            shares="200",
            debt="1600",
            cash="900",
            revenue="4200",
            ebitda="680",
            ebit="510",
            net_income="350",
            eps="7",
            forward_revenue="4700",
            forward_ebitda="780",
            forward_eps="8",
        ),
        _snapshot(
            "peer-b",
            "Peer B",
            price="100",
            shares="250",
            debt="1000",
            cash="500",
            revenue="4800",
            ebitda="600",
            ebit="420",
            net_income="300",
            eps="5",
            forward_revenue="5200",
            forward_ebitda="690",
            forward_eps="6",
        ),
        _snapshot(
            "peer-c",
            "Peer C High Multiple",
            price="300",
            shares="150",
            debt="3000",
            cash="500",
            revenue="3500",
            ebitda="400",
            ebit="250",
            net_income="180",
            eps="4",
            forward_revenue="3900",
            forward_ebitda="460",
            forward_eps="5",
        ),
        _snapshot(
            "peer-d",
            "Peer D Negative Profit",
            price="80",
            shares="180",
            debt="800",
            cash="300",
            revenue="4000",
            ebitda="-100",
            ebit="-180",
            net_income="-200",
            eps="-2",
        ),
        _snapshot(
            "peer-e",
            "Peer E Missing Data",
            price="90",
            shares="100",
            debt=None,
            cash="200",
            revenue="3000",
            ebitda=None,
            ebit=None,
            net_income=None,
            eps=None,
        ),
    )
    decisions = tuple(
        PeerSelectionDecision(
            item.company.identity.company_id,
            SelectionDecision.INCLUDE,
            "Included by the explicit M4/5 demo fixture policy.",
            (),
            item.company.evidence,
            Decimal("1"),
            "valuation-fixture-selection-v1",
        )
        for item in snapshots
    )
    return PeerSet(
        "valuation-demo-peer-set",
        "valuation-demo-universe",
        snapshots,
        decisions,
        "targetco",
        VALUATION_TIME,
        "valuation-fixture-selection-v1",
    )


def demo_multiple_requests() -> tuple[MultipleRequest, ...]:
    return (
        MultipleRequest(
            MultipleDefinition(
                MultipleKind.EV_REVENUE,
                ValueFamily.ENTERPRISE_VALUE,
                FinancialMetricName.REVENUE,
            ),
            "LTM Jun-2026",
            MetricBasis.REPORTED,
        ),
        MultipleRequest(
            MultipleDefinition(
                MultipleKind.EV_EBITDA,
                ValueFamily.ENTERPRISE_VALUE,
                FinancialMetricName.EBITDA,
            ),
            "LTM Jun-2026",
            MetricBasis.REPORTED,
        ),
        MultipleRequest(
            MultipleDefinition(
                MultipleKind.EV_EBIT,
                ValueFamily.ENTERPRISE_VALUE,
                FinancialMetricName.EBIT,
            ),
            "LTM Jun-2026",
            MetricBasis.REPORTED,
        ),
        MultipleRequest(
            MultipleDefinition(
                MultipleKind.PRICE_EARNINGS,
                ValueFamily.SHARE_PRICE,
                FinancialMetricName.EPS,
            ),
            "LTM Jun-2026",
            MetricBasis.REPORTED,
        ),
        MultipleRequest(
            MultipleDefinition(
                MultipleKind.EV_REVENUE,
                ValueFamily.ENTERPRISE_VALUE,
                FinancialMetricName.REVENUE,
            ),
            "FY2027E",
            MetricBasis.REPORTED,
        ),
        MultipleRequest(
            MultipleDefinition(
                MultipleKind.EV_EBITDA,
                ValueFamily.ENTERPRISE_VALUE,
                FinancialMetricName.EBITDA,
            ),
            "FY2027E",
            MetricBasis.REPORTED,
        ),
        MultipleRequest(
            MultipleDefinition(
                MultipleKind.PRICE_EARNINGS,
                ValueFamily.SHARE_PRICE,
                FinancialMetricName.EPS,
            ),
            "FY2027E",
            MetricBasis.REPORTED,
        ),
    )
