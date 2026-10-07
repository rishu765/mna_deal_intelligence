"""Narrow provider boundaries for future Project 3 data adapters."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from ma_comparable_valuation.domain import (
    ComparableCompanySnapshot,
    ComparableUniverse,
    FinancialMetric,
    MarketMetric,
    TargetCompany,
    TargetFinancialProfile,
)


class CompanyProfileProvider(Protocol):
    """Build an evidence-backed target profile without leaking provider-native types."""

    @property
    def provider_name(self) -> str: ...

    def get_target_profile(self, target: TargetCompany) -> TargetFinancialProfile: ...


class FinancialDataProvider(Protocol):
    """Return source-backed reported or adjusted financial observations."""

    @property
    def provider_name(self) -> str: ...

    def get_financial_metrics(self, company_id: str) -> tuple[FinancialMetric, ...]: ...


class MarketDataProvider(Protocol):
    """Return timestamped market and capital-structure observations."""

    @property
    def provider_name(self) -> str: ...

    def get_market_metrics(
        self, company_id: str, *, valuation_time: datetime
    ) -> tuple[MarketMetric, ...]: ...


class ComparableUniverseProvider(Protocol):
    """Return a traceable candidate universe for a target."""

    @property
    def provider_name(self) -> str: ...

    def get_universe(self, target: TargetCompany) -> ComparableUniverse: ...


class ForecastDataProvider(Protocol):
    """Return explicit estimate-period metrics, distinct from historical observations."""

    @property
    def provider_name(self) -> str: ...

    def get_forecasts(self, company_id: str) -> tuple[FinancialMetric, ...]: ...


class ComparableSnapshotProvider(Protocol):
    """Optional composed boundary for callers that already assemble peer snapshots."""

    @property
    def provider_name(self) -> str: ...

    def get_snapshot(
        self, company_id: str, *, valuation_time: datetime
    ) -> ComparableCompanySnapshot: ...
