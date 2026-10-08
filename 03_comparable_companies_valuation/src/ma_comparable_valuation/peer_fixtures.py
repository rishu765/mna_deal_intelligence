"""Synthetic, public-safe fixture providers for peer selection and ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from ma_comparable_valuation.domain import (
    CompanyIdentity,
    ComparableCompany,
    ComparableUniverse,
    CriterionEvaluation,
    CriterionOutcome,
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
    PeriodKind,
    SelectionCriterion,
    SelectionCriterionKind,
    ShareCountBasis,
    TargetCompany,
    TargetFinancialProfile,
)

FIXTURE_VALUATION_TIME = datetime(2026, 10, 7, 10, 0, tzinfo=UTC)


def _evidence(company_id: str, subject: str) -> EvidenceReference:
    return EvidenceReference(
        evidence_id=f"fixture:{company_id}:{subject}",
        source_type="structured_fixture",
        source_name="Project 3 synthetic peer dataset",
        source_locator="data/comparable_peers.json",
        excerpt=f"Synthetic {subject} observation for {company_id}.",
        observed_at=FIXTURE_VALUATION_TIME,
        extraction_method="structured_fixture",
    )


def fixture_companies() -> tuple[ComparableCompany, ...]:
    return (
        ComparableCompany(
            CompanyIdentity("peer-a", "PeerA Systems", "PEERA", "NSE", "India"),
            industry="Business Services",
            sub_industry="Technology-enabled services",
            business_description="B2B workflow and payments infrastructure for enterprises.",
            products_services=("Workflow software", "Payments infrastructure"),
            customer_type="Enterprise",
            geographies=("India", "South Asia"),
            business_model="Recurring and project-based services",
            reporting_currency="INR",
            evidence=(_evidence("peer-a", "company profile"),),
        ),
        ComparableCompany(
            CompanyIdentity("peer-b", "PeerB Consumer Apps", "PEERB", "NASDAQ", "United States"),
            industry="Consumer Software",
            sub_industry="Mobile applications",
            business_description="Advertising-funded consumer mobile applications.",
            products_services=("Consumer apps",),
            customer_type="Consumer",
            geographies=("United States",),
            business_model="Advertising",
            reporting_currency="USD",
            evidence=(_evidence("peer-b", "company profile"),),
        ),
        ComparableCompany(
            CompanyIdentity("peer-c", "PeerC Digital Services", "PEERC", "NSE", "India"),
            industry="Business Services",
            sub_industry="Technology-enabled services",
            business_description="Large-scale enterprise digital operations provider.",
            products_services=("Digital operations", "Managed services"),
            customer_type="Enterprise",
            geographies=("India", "Global"),
            business_model="Recurring managed services",
            reporting_currency="INR",
            evidence=(_evidence("peer-c", "company profile"),),
        ),
        ComparableCompany(
            CompanyIdentity("peer-d", "PeerD Unclassified", "PEERD", "NSE", "India"),
            business_description="Newly listed technology company with sparse classification data.",
            reporting_currency="INR",
            evidence=(_evidence("peer-d", "company profile"),),
        ),
        ComparableCompany(
            CompanyIdentity("peer-e", "PeerE Fintech Platform", "PEERE", "NSE", "India"),
            industry="Business Services",
            sub_industry="Financial technology infrastructure",
            business_description="Enterprise financial workflow and API platform.",
            products_services=("Financial APIs", "Workflow software"),
            customer_type="Enterprise",
            geographies=("India",),
            business_model="Subscription platform",
            reporting_currency="INR",
            evidence=(_evidence("peer-e", "company profile"),),
        ),
    )


@dataclass(frozen=True, slots=True)
class FixtureComparableUniverseProvider:
    @property
    def provider_name(self) -> str:
        return "structured_peer_fixture"

    def get_universe(self, target: TargetCompany) -> ComparableUniverse:
        return ComparableUniverse(
            universe_id="fixture-universe-v1",
            target_id=target.identity.company_id,
            companies=fixture_companies(),
            provider_name=self.provider_name,
            observed_at=FIXTURE_VALUATION_TIME,
            evidence=(_evidence("universe", "candidate universe"),),
        )


def _actual_period() -> FinancialPeriod:
    return FinancialPeriod(
        kind=PeriodKind.LTM,
        label="LTM Jun-2026",
        estimate_status=EstimateStatus.ACTUAL,
        end_date=date(2026, 6, 30),
    )


def _estimate_period() -> FinancialPeriod:
    return FinancialPeriod(
        kind=PeriodKind.FISCAL_YEAR,
        label="FY2027E",
        estimate_status=EstimateStatus.ESTIMATE,
    )


def _financial(
    company_id: str,
    name: FinancialMetricName,
    value: str,
    *,
    estimate: bool = False,
) -> FinancialMetric:
    return FinancialMetric(
        metric_id=f"fixture:{company_id}:{'fy2027e' if estimate else 'ltm'}:{name.value}",
        name=name,
        value=Decimal(value),
        currency="INR",
        unit=(
            FinancialUnit.PER_SHARE if name is FinancialMetricName.EPS else FinancialUnit.MILLION
        ),
        period=_estimate_period() if estimate else _actual_period(),
        basis=MetricBasis.REPORTED,
        evidence=(_evidence(company_id, name.value),),
        quality_flags=(DataQualityFlag.SOURCE_BACKED,),
        as_of=datetime(2026, 6, 30, tzinfo=UTC),
    )


_FINANCIALS = {
    "peer-a": (
        _financial("peer-a", FinancialMetricName.REVENUE, "4200"),
        _financial("peer-a", FinancialMetricName.EBITDA, "680"),
        _financial("peer-a", FinancialMetricName.EBIT, "510"),
        _financial("peer-a", FinancialMetricName.NET_INCOME, "350"),
        _financial("peer-a", FinancialMetricName.EPS, "7.0"),
    ),
    "peer-b": (_financial("peer-b", FinancialMetricName.REVENUE, "4800"),),
    "peer-c": (
        _financial("peer-c", FinancialMetricName.REVENUE, "60000"),
        _financial("peer-c", FinancialMetricName.EBITDA, "9000"),
        _financial("peer-c", FinancialMetricName.EBIT, "7600"),
        _financial("peer-c", FinancialMetricName.NET_INCOME, "5200"),
    ),
    "peer-d": (),
    "peer-e": (
        _financial("peer-e", FinancialMetricName.REVENUE, "5600"),
        _financial("peer-e", FinancialMetricName.EBITDA, "-120"),
        _financial("peer-e", FinancialMetricName.EBIT, "-260"),
        _financial("peer-e", FinancialMetricName.NET_INCOME, "-310"),
    ),
}


@dataclass(frozen=True, slots=True)
class FixtureFinancialDataProvider:
    fail_company_ids: tuple[str, ...] = ()

    @property
    def provider_name(self) -> str:
        return "structured_peer_fixture"

    def get_financial_metrics(self, company_id: str) -> tuple[FinancialMetric, ...]:
        if company_id in self.fail_company_ids:
            raise RuntimeError("configured fixture financial failure")
        return _FINANCIALS.get(company_id, ())


@dataclass(frozen=True, slots=True)
class FixtureForecastDataProvider:
    @property
    def provider_name(self) -> str:
        return "structured_peer_fixture"

    def get_forecasts(self, company_id: str) -> tuple[FinancialMetric, ...]:
        if company_id not in {"peer-a", "peer-c"}:
            return ()
        revenue = "4700" if company_id == "peer-a" else "65000"
        ebitda = "780" if company_id == "peer-a" else "10100"
        return (
            _financial(company_id, FinancialMetricName.REVENUE, revenue, estimate=True),
            _financial(company_id, FinancialMetricName.EBITDA, ebitda, estimate=True),
        )


def _market(
    company_id: str,
    kind: MarketMetricKind,
    value: str,
    *,
    as_of: datetime,
    currency: str | None = "INR",
    share_basis: ShareCountBasis | None = None,
) -> MarketMetric:
    return MarketMetric(
        metric_id=f"fixture:{company_id}:{kind.value}",
        kind=kind,
        value=Decimal(value),
        currency=currency,
        unit=(
            FinancialUnit.PER_SHARE
            if kind is MarketMetricKind.SHARE_PRICE
            else FinancialUnit.MILLION
        ),
        as_of=as_of,
        evidence=(_evidence(company_id, kind.value),),
        quality_flags=(DataQualityFlag.SOURCE_BACKED,),
        share_basis=share_basis,
    )


def _complete_market(company_id: str, *, stale: bool = False) -> tuple[MarketMetric, ...]:
    price_time = datetime(2026, 9, 20, tzinfo=UTC) if stale else FIXTURE_VALUATION_TIME
    capital_time = datetime(2026, 6, 30, tzinfo=UTC)
    return (
        _market(company_id, MarketMetricKind.SHARE_PRICE, "125", as_of=price_time),
        _market(company_id, MarketMetricKind.MARKET_CAPITALIZATION, "25000", as_of=price_time),
        _market(
            company_id,
            MarketMetricKind.DILUTED_SHARES,
            "200",
            as_of=price_time,
            currency=None,
            share_basis=ShareCountBasis.DILUTED_END_OF_PERIOD,
        ),
        _market(company_id, MarketMetricKind.CASH_AND_EQUIVALENTS, "900", as_of=capital_time),
        _market(company_id, MarketMetricKind.DEBT, "1600", as_of=capital_time),
    )


_MARKET = {
    "peer-a": _complete_market("peer-a"),
    "peer-c": _complete_market("peer-c", stale=True),
    "peer-e": _complete_market("peer-e")[:-1],
}


@dataclass(frozen=True, slots=True)
class FixtureMarketDataProvider:
    fail_company_ids: tuple[str, ...] = ()

    @property
    def provider_name(self) -> str:
        return "structured_peer_fixture"

    def get_market_metrics(
        self, company_id: str, *, valuation_time: datetime
    ) -> tuple[MarketMetric, ...]:
        del valuation_time
        if company_id in self.fail_company_ids:
            raise RuntimeError("configured fixture market failure")
        return _MARKET.get(company_id, ())


@dataclass(frozen=True, slots=True)
class FixtureSemanticSimilarityEvaluator:
    """Deterministic semantic stand-in for offline tests; not an LLM."""

    def evaluate(
        self,
        target: TargetFinancialProfile,
        candidate: ComparableCompany,
        criterion: SelectionCriterion,
    ) -> CriterionEvaluation:
        del target
        scores = {
            "peer-a": {
                SelectionCriterionKind.BUSINESS_MODEL: Decimal("1"),
                SelectionCriterionKind.CUSTOMER_TYPE: Decimal("1"),
            },
            "peer-b": {
                SelectionCriterionKind.BUSINESS_MODEL: Decimal("0"),
                SelectionCriterionKind.CUSTOMER_TYPE: Decimal("0"),
            },
            "peer-c": {
                SelectionCriterionKind.BUSINESS_MODEL: Decimal("0.8"),
                SelectionCriterionKind.CUSTOMER_TYPE: Decimal("1"),
            },
            "peer-e": {
                SelectionCriterionKind.BUSINESS_MODEL: Decimal("0.2"),
                SelectionCriterionKind.CUSTOMER_TYPE: Decimal("0.2"),
            },
        }
        score = scores.get(candidate.identity.company_id, {}).get(criterion.kind)
        if score is None:
            return CriterionEvaluation(
                criterion.kind,
                criterion.method,
                CriterionOutcome.UNKNOWN,
                "Fixture has no semantic assessment for this dimension.",
                missing_information=(criterion.kind.value,),
            )
        return CriterionEvaluation(
            criterion.kind,
            criterion.method,
            CriterionOutcome.PASS if score >= Decimal("0.5") else CriterionOutcome.FAIL,
            f"Fixture semantic assessment scored {score} for {criterion.kind.value}.",
            score=score,
            evidence=candidate.evidence,
        )
