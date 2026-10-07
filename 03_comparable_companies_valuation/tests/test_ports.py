from datetime import datetime

from ma_comparable_valuation import TargetCompany
from ma_comparable_valuation.ports import (
    CompanyProfileProvider,
    ComparableUniverseProvider,
    FinancialDataProvider,
    ForecastDataProvider,
    MarketDataProvider,
)


def accepts_profile_provider(provider: CompanyProfileProvider, target: TargetCompany) -> None:
    provider.get_target_profile(target)


def accepts_financial_provider(provider: FinancialDataProvider) -> None:
    provider.get_financial_metrics("company-1")


def accepts_market_provider(provider: MarketDataProvider, valuation_time: datetime) -> None:
    provider.get_market_metrics("company-1", valuation_time=valuation_time)


def accepts_universe_provider(provider: ComparableUniverseProvider, target: TargetCompany) -> None:
    provider.get_universe(target)


def accepts_forecast_provider(provider: ForecastDataProvider) -> None:
    provider.get_forecasts("company-1")


def test_provider_protocols_are_importable_without_runtime_dependencies() -> None:
    assert CompanyProfileProvider is not None
    assert FinancialDataProvider is not None
    assert MarketDataProvider is not None
    assert ComparableUniverseProvider is not None
    assert ForecastDataProvider is not None
