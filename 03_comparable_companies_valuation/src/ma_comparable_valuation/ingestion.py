"""Provider-neutral assembly of valuation-ready peer snapshots without valuation math."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal

from ma_comparable_valuation.domain import (
    CapitalStructure,
    ComparableCompany,
    ComparableCompanySnapshot,
    ComparableSelectionResult,
    ComparableUniverse,
    DataQualityFlag,
    EstimateStatus,
    FinancialMetric,
    FinancialMetricName,
    FinancialUnit,
    MarketMetric,
    MarketMetricKind,
    PeerSet,
    ProfileConflict,
    ProfileIssue,
    ProfileIssueKind,
    SelectionDecision,
    ShareCountBasis,
)
from ma_comparable_valuation.normalization import convert_unit
from ma_comparable_valuation.ports import (
    FinancialDataProvider,
    ForecastDataProvider,
    MarketDataProvider,
)

_CAPITAL_KINDS = {
    MarketMetricKind.DILUTED_SHARES,
    MarketMetricKind.BASIC_SHARES,
    MarketMetricKind.DEBT,
    MarketMetricKind.CASH_AND_EQUIVALENTS,
    MarketMetricKind.PREFERRED_STOCK,
    MarketMetricKind.MINORITY_INTEREST,
    MarketMetricKind.LEASE_LIABILITIES,
    MarketMetricKind.PENSION_DEFICIT,
}


@dataclass(frozen=True, slots=True)
class ComparableSnapshotService:
    financial_provider: FinancialDataProvider
    market_provider: MarketDataProvider
    forecast_provider: ForecastDataProvider | None = None
    stale_market_days: int = 7
    capital_structure_lag_days: int = 550
    policy_id: str = "peer-snapshot-v1"

    def __post_init__(self) -> None:
        if self.stale_market_days < 0 or self.capital_structure_lag_days < 0:
            raise ValueError("date tolerances must not be negative")
        if not self.policy_id.strip():
            raise ValueError("policy_id must not be blank")

    def build_peer_set(
        self,
        universe: ComparableUniverse,
        selection: ComparableSelectionResult,
        *,
        valuation_time: datetime,
    ) -> PeerSet:
        if valuation_time.tzinfo is None or valuation_time.utcoffset() is None:
            raise ValueError("valuation_time must be timezone-aware")
        if selection.universe_id != universe.universe_id:
            raise ValueError("selection result does not belong to the universe")
        companies = {item.identity.company_id: item for item in universe.companies}
        issues: list[ProfileIssue] = []
        snapshots: list[ComparableCompanySnapshot] = []
        for decision in selection.decisions:
            if decision.decision is not SelectionDecision.INCLUDE:
                continue
            company = companies.get(decision.company_id)
            if company is None:
                issues.append(
                    ProfileIssue(
                        ProfileIssueKind.MISSING,
                        f"Included company {decision.company_id} is absent from the universe.",
                    )
                )
                continue
            snapshots.append(self._build_snapshot(company, valuation_time, issues))

        included = set(selection.selected_company_ids)
        built = {item.company.identity.company_id for item in snapshots}
        for missing_id in sorted(included - built):
            company = companies.get(missing_id)
            if company is not None:
                snapshots.append(
                    ComparableCompanySnapshot(
                        company=company,
                        as_of=valuation_time,
                        financial_metrics=(),
                        market_metrics=(),
                        quality_flags=(
                            DataQualityFlag.MISSING_FINANCIALS,
                            DataQualityFlag.MISSING_MARKET_DATA,
                        ),
                        issues=(
                            ProfileIssue(
                                ProfileIssueKind.PROVIDER_FAILURE,
                                "Snapshot construction failed before usable data was produced.",
                            ),
                        ),
                        warnings=("No usable peer data was produced.",),
                    )
                )
        warnings = tuple(
            dict.fromkeys((*universe.warnings, *selection.warnings, *(i.message for i in issues)))
        )
        return PeerSet(
            peer_set_id=f"peer-set:{universe.universe_id}:{valuation_time.date().isoformat()}",
            universe_id=universe.universe_id,
            snapshots=tuple(snapshots),
            decisions=selection.decisions,
            target_id=universe.target_id,
            created_at=valuation_time,
            policy_id=self.policy_id,
            issues=tuple(issues),
            warnings=warnings,
        )

    def _build_snapshot(
        self,
        company: ComparableCompany,
        valuation_time: datetime,
        peer_set_issues: list[ProfileIssue],
    ) -> ComparableCompanySnapshot:
        issues: list[ProfileIssue] = []
        financial = self._financial(company, issues)
        market = self._market(company, valuation_time, issues)
        financial, financial_conflicts = _financial_conflicts(financial)
        market, market_conflicts = _market_conflicts(market)
        conflicts = (*financial_conflicts, *market_conflicts)
        issues.extend(
            ProfileIssue(ProfileIssueKind.CONFLICT, item.reason, item.observation_ids)
            for item in conflicts
        )

        flags: list[DataQualityFlag] = []
        financial_names = {item.name for item in financial}
        missing_financial = {
            FinancialMetricName.REVENUE,
            FinancialMetricName.EBITDA,
        } - financial_names
        if missing_financial:
            flags.append(DataQualityFlag.MISSING_FINANCIALS)
            issues.append(
                ProfileIssue(
                    ProfileIssueKind.MISSING,
                    "Missing peer financial fields: "
                    + ", ".join(sorted(item.value for item in missing_financial)),
                )
            )
        market_kinds = {item.kind for item in market}
        missing_market = {
            MarketMetricKind.SHARE_PRICE,
            MarketMetricKind.CASH_AND_EQUIVALENTS,
            MarketMetricKind.DEBT,
            MarketMetricKind.DILUTED_SHARES,
        } - market_kinds
        if missing_market:
            flags.append(DataQualityFlag.MISSING_MARKET_DATA)
            issues.append(
                ProfileIssue(
                    ProfileIssueKind.MISSING,
                    "Missing peer market/capital fields: "
                    + ", ".join(sorted(item.value for item in missing_market)),
                )
            )
        if conflicts:
            flags.append(DataQualityFlag.CONFLICTING)
        stale = tuple(
            item
            for item in market
            if item.kind in {MarketMetricKind.SHARE_PRICE, MarketMetricKind.MARKET_CAPITALIZATION}
            and (valuation_time.date() - item.as_of.date()).days > self.stale_market_days
        )
        if stale:
            flags.append(DataQualityFlag.STALE_MARKET_DATA)
            market = tuple(
                _with_market_flag(item, DataQualityFlag.STALE) if item in stale else item
                for item in market
            )
            issues.append(
                ProfileIssue(
                    ProfileIssueKind.INVALID,
                    "Market price or capitalization is stale under the configured tolerance.",
                    tuple(item.metric_id for item in stale),
                )
            )
        capital_items = tuple(item for item in market if item.kind in _CAPITAL_KINDS)
        capital_structure = None
        if capital_items:
            capital_structure = CapitalStructure(
                snapshot_id=f"peer-capital:{company.identity.company_id}:{valuation_time.date().isoformat()}",
                as_of=max(item.as_of for item in capital_items),
                policy_id="peer-capital-structure-v1",
                components=capital_items,
            )
        price_dates = [
            item.as_of
            for item in market
            if item.kind in {MarketMetricKind.SHARE_PRICE, MarketMetricKind.MARKET_CAPITALIZATION}
        ]
        if price_dates and capital_items:
            price_time = max(price_dates)
            oldest_capital = min(item.as_of for item in capital_items)
            if (
                abs((price_time.date() - oldest_capital.date()).days)
                > self.capital_structure_lag_days
            ):
                flags.append(DataQualityFlag.PERIOD_MISMATCH)
                issues.append(
                    ProfileIssue(
                        ProfileIssueKind.INVALID,
                        (
                            "Market and capital-structure dates exceed the configured alignment "
                            "tolerance."
                        ),
                        tuple(item.metric_id for item in capital_items),
                    )
                )
        currencies = {item.currency for item in financial}
        currencies.update(item.currency for item in market if item.currency is not None)
        if len(currencies) > 1:
            flags.append(DataQualityFlag.UNSUPPORTED_CURRENCY)
            issues.append(
                ProfileIssue(
                    ProfileIssueKind.UNSUPPORTED,
                    "Snapshot contains multiple currencies; M2/3 performs no FX conversion.",
                )
            )
        flags.extend(_outlier_flags(financial, issues))
        if _complete_enough(financial, market) and not any(
            item
            in {
                DataQualityFlag.CONFLICTING,
                DataQualityFlag.STALE_MARKET_DATA,
                DataQualityFlag.PERIOD_MISMATCH,
            }
            for item in flags
        ):
            flags.append(DataQualityFlag.COMPLETE_ENOUGH_FOR_VALUATION)
        peer_set_issues.extend(issues)
        warnings = tuple(dict.fromkeys(item.message for item in issues))
        return ComparableCompanySnapshot(
            company=company,
            as_of=valuation_time,
            financial_metrics=financial,
            market_metrics=market,
            capital_structure=capital_structure,
            conflicts=conflicts,
            issues=tuple(issues),
            quality_flags=tuple(dict.fromkeys(flags)),
            warnings=warnings,
        )

    def _financial(
        self, company: ComparableCompany, issues: list[ProfileIssue]
    ) -> tuple[FinancialMetric, ...]:
        values: list[FinancialMetric] = []
        try:
            values.extend(
                self.financial_provider.get_financial_metrics(company.identity.company_id)
            )
        except Exception as error:
            issues.append(
                ProfileIssue(
                    ProfileIssueKind.PROVIDER_FAILURE,
                    f"Financial provider failed safely: {type(error).__name__}.",
                )
            )
        if self.forecast_provider is not None:
            try:
                forecasts = self.forecast_provider.get_forecasts(company.identity.company_id)
                if any(
                    item.period.estimate_status is not EstimateStatus.ESTIMATE for item in forecasts
                ):
                    raise ValueError("forecast provider returned a historical metric")
                values.extend(forecasts)
            except Exception as error:
                issues.append(
                    ProfileIssue(
                        ProfileIssueKind.PROVIDER_FAILURE,
                        f"Forecast provider failed safely: {type(error).__name__}.",
                    )
                )
        normalized: list[FinancialMetric] = []
        for item in values:
            try:
                normalized.append(_normalize_financial_metric(item))
            except ValueError as error:
                issues.append(
                    ProfileIssue(ProfileIssueKind.UNSUPPORTED, str(error), (item.metric_id,))
                )
        return tuple(normalized)

    def _market(
        self,
        company: ComparableCompany,
        valuation_time: datetime,
        issues: list[ProfileIssue],
    ) -> tuple[MarketMetric, ...]:
        try:
            values = self.market_provider.get_market_metrics(
                company.identity.company_id, valuation_time=valuation_time
            )
        except Exception as error:
            issues.append(
                ProfileIssue(
                    ProfileIssueKind.PROVIDER_FAILURE,
                    f"Market provider failed safely: {type(error).__name__}.",
                )
            )
            return ()
        normalized: list[MarketMetric] = []
        for item in values:
            if item.as_of > valuation_time:
                issues.append(
                    ProfileIssue(
                        ProfileIssueKind.INVALID,
                        "Market observation post-dates the valuation time and was excluded.",
                        (item.metric_id,),
                    )
                )
                continue
            try:
                normalized.append(_normalize_market_metric(item))
            except ValueError as error:
                issues.append(
                    ProfileIssue(ProfileIssueKind.UNSUPPORTED, str(error), (item.metric_id,))
                )
        return tuple(normalized)


def _normalize_financial_metric(metric: FinancialMetric) -> FinancialMetric:
    if metric.unit is FinancialUnit.PER_SHARE:
        return metric
    value, _ = convert_unit(metric.value, metric.unit, FinancialUnit.MILLION)
    return replace(metric, value=value, unit=FinancialUnit.MILLION)


def _normalize_market_metric(metric: MarketMetric) -> MarketMetric:
    if metric.unit is FinancialUnit.PER_SHARE:
        return metric
    value, _ = convert_unit(metric.value, metric.unit, FinancialUnit.MILLION)
    return replace(metric, value=value, unit=FinancialUnit.MILLION)


def _financial_conflicts(
    values: tuple[FinancialMetric, ...],
) -> tuple[tuple[FinancialMetric, ...], tuple[ProfileConflict, ...]]:
    grouped: dict[tuple[object, ...], list[int]] = defaultdict(list)
    mutable = list(values)
    for index, item in enumerate(values):
        grouped[(item.name, item.period, item.basis, item.currency)].append(index)
    conflicts: list[ProfileConflict] = []
    for indexes in grouped.values():
        if len({mutable[index].value for index in indexes}) <= 1:
            continue
        first = mutable[indexes[0]]
        ids = tuple(mutable[index].metric_id for index in indexes)
        conflicts.append(
            ProfileConflict(
                f"peer-conflict:{first.name.value}:{len(conflicts) + 1}",
                first.name.value,
                ids,
                "Providers supplied different values for the same financial metric semantics.",
            )
        )
        for index in indexes:
            mutable[index] = _with_financial_flag(mutable[index], DataQualityFlag.CONFLICTING)
    return tuple(mutable), tuple(conflicts)


def _market_conflicts(
    values: tuple[MarketMetric, ...],
) -> tuple[tuple[MarketMetric, ...], tuple[ProfileConflict, ...]]:
    grouped: dict[tuple[object, ...], list[int]] = defaultdict(list)
    mutable = list(values)
    for index, item in enumerate(values):
        grouped[(item.kind, item.share_basis, item.as_of, item.currency)].append(index)
    conflicts: list[ProfileConflict] = []
    for indexes in grouped.values():
        if len({mutable[index].value for index in indexes}) <= 1:
            continue
        first = mutable[indexes[0]]
        ids = tuple(mutable[index].metric_id for index in indexes)
        conflicts.append(
            ProfileConflict(
                f"peer-conflict:{first.kind.value}:{len(conflicts) + 1}",
                first.kind.value,
                ids,
                "Providers supplied different values for the same point-in-time market field.",
            )
        )
        for index in indexes:
            mutable[index] = _with_market_flag(mutable[index], DataQualityFlag.CONFLICTING)
    return tuple(mutable), tuple(conflicts)


def _with_financial_flag(metric: FinancialMetric, flag: DataQualityFlag) -> FinancialMetric:
    return replace(metric, quality_flags=tuple(dict.fromkeys((*metric.quality_flags, flag))))


def _with_market_flag(metric: MarketMetric, flag: DataQualityFlag) -> MarketMetric:
    return replace(metric, quality_flags=tuple(dict.fromkeys((*metric.quality_flags, flag))))


def _complete_enough(
    financial: tuple[FinancialMetric, ...], market: tuple[MarketMetric, ...]
) -> bool:
    financial_names = {item.name for item in financial}
    market_kinds = {item.kind for item in market}
    has_diluted_eop = any(
        item.kind is MarketMetricKind.DILUTED_SHARES
        and item.share_basis is ShareCountBasis.DILUTED_END_OF_PERIOD
        for item in market
    )
    return (
        {FinancialMetricName.REVENUE, FinancialMetricName.EBITDA} <= financial_names
        and {
            MarketMetricKind.SHARE_PRICE,
            MarketMetricKind.CASH_AND_EQUIVALENTS,
            MarketMetricKind.DEBT,
        }
        <= market_kinds
        and has_diluted_eop
    )


def _outlier_flags(
    financial: tuple[FinancialMetric, ...], issues: list[ProfileIssue]
) -> tuple[DataQualityFlag, ...]:
    negative = tuple(
        item
        for item in financial
        if item.value < Decimal("0")
        and item.name
        in {FinancialMetricName.EBITDA, FinancialMetricName.EBIT, FinancialMetricName.EPS}
    )
    if negative:
        issues.append(
            ProfileIssue(
                ProfileIssueKind.INVALID,
                "Negative profitability observations are preserved for later multiple treatment.",
                tuple(item.metric_id for item in negative),
            )
        )
    mapping = {
        FinancialMetricName.EBITDA: DataQualityFlag.NEGATIVE_EBITDA,
        FinancialMetricName.EBIT: DataQualityFlag.NEGATIVE_EBIT,
        FinancialMetricName.EPS: DataQualityFlag.NEGATIVE_EPS,
    }
    return tuple(dict.fromkeys(mapping[item.name] for item in negative))
