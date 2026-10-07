from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ma_comparable_valuation import (
    CompanyIdentity,
    DataQualityFlag,
    EstimateStatus,
    EvidenceReference,
    FinancialMetricName,
    FinancialObservation,
    FinancialPeriod,
    FinancialUnit,
    MarketMetric,
    MarketMetricKind,
    MetricBasis,
    PeriodKind,
    ProfileCompletenessStatus,
    ProfileIssueKind,
    ShareCountBasis,
    TargetCompany,
    TargetFinancialProfile,
    TargetFinancialProfileService,
)
from ma_comparable_valuation.normalization import convert_unit, normalize_observation

AS_OF = datetime(2026, 6, 30, tzinfo=UTC)


def evidence(evidence_id: str) -> EvidenceReference:
    return EvidenceReference(
        evidence_id=evidence_id,
        source_type="annual_report",
        source_name="TargetCo annual report",
        observed_at=datetime(2026, 7, 15, tzinfo=UTC),
        source_locator="targetco.pdf",
        document_id="doc-1",
        chunk_id=f"chunk-{evidence_id}",
        page_numbers=(42,),
        excerpt="Source-backed financial fact.",
        section="Financial highlights",
        extraction_method="manual_fixture",
    )


def target() -> TargetCompany:
    return TargetCompany(
        identity=CompanyIdentity(
            company_id="targetco",
            name="TargetCo",
            country="India",
            identifiers=(("fixture_id", "targetco"),),
        ),
        industry="Business Services",
        sub_industry="Technology-enabled services",
        fiscal_year_end="03-31",
        reporting_currency="inr",
        business_model="Recurring services",
        evidence=(evidence("identity"),),
    )


def fy2025_actual() -> FinancialPeriod:
    return FinancialPeriod(
        PeriodKind.FISCAL_YEAR,
        "FY2025A",
        EstimateStatus.ACTUAL,
        start_date=date(2024, 4, 1),
        end_date=date(2025, 3, 31),
    )


def observation(
    observation_id: str,
    name: str,
    value: str,
    *,
    unit: str = "crore",
    currency: str | None = "INR",
    period: FinancialPeriod | None = None,
    as_of: datetime | None = None,
    basis: MetricBasis | None = MetricBasis.REPORTED,
    adjustment_label: str | None = None,
) -> FinancialObservation:
    return FinancialObservation(
        observation_id=observation_id,
        raw_metric_name=name,
        value=Decimal(value),
        unit=unit,
        currency=currency,
        period=period,
        as_of=as_of,
        basis=basis,
        adjustment_label=adjustment_label,
        evidence=(evidence(observation_id),),
    )


def complete_observations() -> tuple[FinancialObservation, ...]:
    return (
        observation("revenue", "Revenue", "500", period=fy2025_actual()),
        observation("ebitda", "EBITDA", "75", period=fy2025_actual()),
        observation("cash", "Cash", "40", as_of=AS_OF),
        observation("debt", "Debt", "100", as_of=AS_OF),
        observation(
            "shares",
            "Diluted Shares Outstanding",
            "50",
            unit="million",
            currency=None,
            as_of=AS_OF,
        ),
    )


def test_target_company_keeps_valuation_relevant_business_and_reporting_fields() -> None:
    company = target()

    assert company.reporting_currency == "INR"
    assert company.fiscal_year_end == "03-31"
    assert company.business_model == "Recurring services"
    assert company.evidence[0].section == "Financial highlights"


def test_target_company_rejects_invalid_reporting_metadata() -> None:
    with pytest.raises(ValueError, match="MM-DD"):
        TargetCompany(
            identity=CompanyIdentity("bad", "Bad Co"),
            fiscal_year_end="31-03",
        )


def test_exact_unit_conversion_is_centralized() -> None:
    crore_value, crore_factor = convert_unit(
        Decimal("5"), FinancialUnit.CRORE, FinancialUnit.MILLION
    )
    billion_value, billion_factor = convert_unit(
        Decimal("1"), FinancialUnit.BILLION, FinancialUnit.MILLION
    )

    assert crore_value == Decimal("50")
    assert crore_factor == Decimal("10")
    assert billion_value == Decimal("1000")
    assert billion_factor == Decimal("1000")


def test_normalization_preserves_currency_and_does_not_apply_fx() -> None:
    inr = normalize_observation(
        observation("inr-revenue", "Revenue", "5", period=fy2025_actual())
    ).metric
    usd = normalize_observation(
        observation(
            "usd-revenue",
            "Revenue",
            "5",
            currency="USD",
            period=fy2025_actual(),
        )
    ).metric

    assert inr.currency == "INR"
    assert usd.currency == "USD"
    assert inr.value == usd.value == Decimal("50")


def test_fy_ltm_actual_and_forecast_remain_distinct() -> None:
    ltm = FinancialPeriod(
        PeriodKind.LTM,
        "LTM Jun-2026",
        EstimateStatus.ACTUAL,
        end_date=date(2026, 6, 30),
    )
    forecast = FinancialPeriod(
        PeriodKind.FISCAL_YEAR,
        "FY2027E",
        EstimateStatus.ESTIMATE,
    )
    profile = TargetFinancialProfileService(required_fields=("revenue",)).build(
        target(),
        (
            observation("fy", "Revenue", "500", period=fy2025_actual()),
            observation("ltm", "Revenue", "540", period=ltm),
            observation("forecast", "Revenue", "600", period=forecast),
        ),
    )

    assert {item.period.kind for item in profile.metrics} == {
        PeriodKind.FISCAL_YEAR,
        PeriodKind.LTM,
    }
    forecast_metric = next(item for item in profile.metrics if item.period.label == "FY2027E")
    assert forecast_metric.period.estimate_status is EstimateStatus.ESTIMATE
    assert DataQualityFlag.ESTIMATED in forecast_metric.quality_flags


def test_period_suffix_cannot_masquerade_as_wrong_estimate_status() -> None:
    with pytest.raises(ValueError, match="E-suffixed"):
        FinancialPeriod(PeriodKind.FISCAL_YEAR, "FY2027E", EstimateStatus.ACTUAL)


def test_reported_and_adjusted_ebitda_are_preserved_without_conflict() -> None:
    profile = TargetFinancialProfileService(required_fields=("ebitda",)).build(
        target(),
        (
            observation("reported", "EBITDA", "75", period=fy2025_actual()),
            observation(
                "adjusted",
                "Adjusted EBITDA",
                "82",
                period=fy2025_actual(),
                basis=MetricBasis.ADJUSTED,
                adjustment_label="Management-adjusted EBITDA",
            ),
        ),
    )

    assert {item.basis for item in profile.metrics} == {
        MetricBasis.REPORTED,
        MetricBasis.ADJUSTED,
    }
    assert profile.conflicts == ()
    assert (
        next(
            item for item in profile.metrics if item.basis is MetricBasis.ADJUSTED
        ).adjustment_label
        == "Management-adjusted EBITDA"
    )


def test_negative_ebitda_is_economically_valid() -> None:
    profile = TargetFinancialProfileService(required_fields=("ebitda",)).build(
        target(),
        (observation("negative", "EBITDA", "-5", period=fy2025_actual()),),
    )
    assert profile.metrics[0].value == Decimal("-50")


def test_missing_data_stays_missing_and_profile_is_partial() -> None:
    profile = TargetFinancialProfileService().build(
        target(),
        (observation("revenue", "Revenue", "500", period=fy2025_actual()),),
    )

    assert profile.completeness is not None
    assert profile.completeness.status is ProfileCompletenessStatus.PARTIAL
    assert "debt" in profile.completeness.missing
    assert profile.capital_structure is None
    assert any(issue.kind is ProfileIssueKind.MISSING for issue in profile.issues)


def test_conflicting_same_basis_observations_are_preserved_and_flagged() -> None:
    profile = TargetFinancialProfileService(required_fields=("ebitda",)).build(
        target(),
        (
            observation("source-a", "EBITDA", "75", period=fy2025_actual()),
            observation("source-b", "EBITDA", "80", period=fy2025_actual()),
        ),
    )

    assert len(profile.metrics) == 2
    assert len(profile.conflicts) == 1
    assert all(DataQualityFlag.CONFLICTING in item.quality_flags for item in profile.metrics)
    assert profile.completeness is not None
    assert profile.completeness.status is ProfileCompletenessStatus.PARTIAL


def test_invalid_unit_becomes_issue_without_losing_valid_observation() -> None:
    profile = TargetFinancialProfileService(required_fields=("revenue",)).build(
        target(),
        (
            observation("valid", "Revenue", "500", period=fy2025_actual()),
            observation(
                "invalid",
                "EBITDA",
                "75",
                unit="bushels",
                period=fy2025_actual(),
            ),
        ),
    )

    assert len(profile.metrics) == 1
    assert profile.metrics[0].name is FinancialMetricName.REVENUE
    assert any(issue.kind is ProfileIssueKind.UNSUPPORTED for issue in profile.issues)


def test_normalized_metric_preserves_evidence_and_decision_lineage() -> None:
    profile = TargetFinancialProfileService(required_fields=("revenue",)).build(
        target(),
        (observation("sales", "Net Sales", "500", period=fy2025_actual()),),
    )

    metric = profile.metrics[0]
    assert metric.evidence[0].evidence_id == "sales"
    assert metric.source_observation_ids == ("sales",)
    assert profile.normalization_decisions[0].conversion_factor == Decimal("10")
    assert profile.normalization_decisions[0].normalized_name == "revenue"


def test_profile_json_round_trip_preserves_all_m1_metadata() -> None:
    profile = TargetFinancialProfileService().build(target(), complete_observations())

    restored = TargetFinancialProfile.from_json(profile.to_json())

    assert restored == profile
    assert restored.capital_structure is not None
    assert (
        restored.capital_structure.components[-1].share_basis
        is ShareCountBasis.DILUTED_END_OF_PERIOD
    )


def test_complete_profile_and_compatible_net_debt() -> None:
    profile = TargetFinancialProfileService().build(target(), complete_observations())

    assert profile.completeness is not None
    assert profile.completeness.status is ProfileCompletenessStatus.COMPLETE
    net_debt = profile.net_debt()
    assert net_debt is not None
    assert net_debt.value == Decimal("600")
    assert net_debt.currency == "INR"


def test_net_debt_is_unknown_when_as_of_dates_are_incompatible() -> None:
    profile = TargetFinancialProfileService(required_fields=("cash_and_equivalents", "debt")).build(
        target(),
        (
            observation("cash", "Cash", "40", as_of=AS_OF),
            observation(
                "debt",
                "Debt",
                "100",
                as_of=datetime(2026, 3, 31, tzinfo=UTC),
            ),
        ),
    )
    assert profile.net_debt() is None


def test_weighted_average_diluted_shares_do_not_satisfy_end_of_period_requirement() -> None:
    profile = TargetFinancialProfileService(
        required_fields=("diluted_shares_end_of_period",)
    ).build(
        target(),
        (
            observation(
                "weighted",
                "Diluted Weighted Average Shares",
                "50",
                unit="million",
                currency=None,
                as_of=AS_OF,
            ),
        ),
    )

    assert profile.capital_structure is not None
    share_metric = profile.capital_structure.components[0]
    assert share_metric.kind is MarketMetricKind.DILUTED_SHARES
    assert share_metric.share_basis is ShareCountBasis.DILUTED_WEIGHTED_AVERAGE
    assert profile.completeness is not None
    assert profile.completeness.status is ProfileCompletenessStatus.INSUFFICIENT


def test_share_kind_rejects_incompatible_share_basis() -> None:
    with pytest.raises(ValueError, match="diluted share_basis"):
        MarketMetric(
            metric_id="bad-shares",
            kind=MarketMetricKind.DILUTED_SHARES,
            value=Decimal("50"),
            unit=FinancialUnit.MILLION,
            as_of=AS_OF,
            evidence=(evidence("bad-shares"),),
            share_basis=ShareCountBasis.BASIC_END_OF_PERIOD,
        )
