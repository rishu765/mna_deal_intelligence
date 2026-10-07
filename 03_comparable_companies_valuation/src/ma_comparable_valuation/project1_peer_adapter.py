"""Project 1 document-research adapter for peer financial observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from ma_comparable_valuation.domain import ComparableCompany, FinancialMetric, TargetCompany
from ma_comparable_valuation.errors import Project1AdapterError
from ma_comparable_valuation.project1_adapter import (
    Project1ResearchClient,
    Project1TargetProfileProvider,
)


@dataclass(frozen=True, slots=True)
class Project1PeerFinancialDataProvider:
    """Map public Project 1 research output without importing Project 1 internals."""

    client: Project1ResearchClient
    companies: tuple[ComparableCompany, ...]
    observed_at: datetime
    rolling_period_end_dates: tuple[tuple[str, date], ...] = ()

    @property
    def provider_name(self) -> str:
        return "project1_document_research"

    def get_financial_metrics(self, company_id: str) -> tuple[FinancialMetric, ...]:
        company = next(
            (item for item in self.companies if item.identity.company_id == company_id), None
        )
        if company is None:
            raise Project1AdapterError(f"Unknown peer company_id: {company_id}")
        target = TargetCompany(
            identity=company.identity,
            industry=company.industry,
            sub_industry=company.sub_industry,
            fiscal_year_end=company.fiscal_year_end,
            reporting_currency=company.reporting_currency,
            business_description=company.business_description,
            customer_type=company.customer_type,
            business_model=company.business_model,
            evidence=company.evidence,
        )
        provider = Project1TargetProfileProvider(
            client=self.client,
            observed_at=self.observed_at,
            rolling_period_end_dates=self.rolling_period_end_dates,
        )
        return provider.get_target_profile(target).metrics
