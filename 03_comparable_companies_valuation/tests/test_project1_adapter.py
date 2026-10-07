from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

import pytest

from ma_comparable_valuation import CompanyIdentity, FinancialMetricName, TargetCompany
from ma_comparable_valuation.errors import Project1AdapterError
from ma_comparable_valuation.project1_adapter import (
    Project1ResearchClient,
    Project1TargetProfileProvider,
)


@dataclass(frozen=True)
class FakeCitation:
    reference_number: int = 1
    chunk_id: str = "chunk-1"
    document_id: str = "doc-1"
    source_filename: str = "annual-report.pdf"
    source_title: str | None = "Annual Report"
    canonical_page_numbers: tuple[int, ...] = (42,)
    excerpt: str = "Net sales were INR 500 crore."


@dataclass(frozen=True)
class FakeMetric:
    metric_name: str
    value: str
    fiscal_period: str | None
    unit: str | None
    currency: str | None
    basis: str | None
    citations: tuple[FakeCitation, ...]


@dataclass(frozen=True)
class FakeSection:
    financial_metrics: tuple[FakeMetric, ...]


@dataclass(frozen=True)
class FakeProfile:
    sections: tuple[FakeSection, ...]
    warnings: tuple[str, ...] = ()


class FakeClient:
    def research(self, *, company_name: str | None) -> FakeProfile:
        assert company_name == "TargetCo"
        return FakeProfile(
            sections=(
                FakeSection(
                    financial_metrics=(
                        FakeMetric(
                            metric_name="Net Sales",
                            value="500",
                            fiscal_period="FY2025A",
                            unit="crore",
                            currency="INR",
                            basis="reported",
                            citations=(FakeCitation(),),
                        ),
                    )
                ),
            )
        )


class FailingClient:
    def research(self, *, company_name: str | None) -> FakeProfile:
        raise RuntimeError("provider detail must be translated")


def target() -> TargetCompany:
    return TargetCompany(CompanyIdentity("targetco", "TargetCo"))


def test_project1_adapter_maps_public_shape_and_citations_without_deep_imports() -> None:
    provider = Project1TargetProfileProvider(
        cast(Project1ResearchClient, FakeClient()),
        observed_at=datetime(2026, 7, 15, tzinfo=UTC),
    )

    profile = provider.get_target_profile(target())

    assert profile.metrics[0].name is FinancialMetricName.REVENUE
    assert profile.metrics[0].value == Decimal("5000")
    assert profile.metrics[0].evidence[0].document_id == "doc-1"
    assert profile.metrics[0].evidence[0].extraction_method == "project1_structured_research"


def test_project1_adapter_translates_provider_failure() -> None:
    provider = Project1TargetProfileProvider(
        cast(Project1ResearchClient, FailingClient()),
        observed_at=datetime(2026, 7, 15, tzinfo=UTC),
    )

    with pytest.raises(Project1AdapterError, match="document research failed"):
        provider.get_target_profile(target())


def test_project1_partial_metric_becomes_profile_issue() -> None:
    class PartialClient:
        def research(self, *, company_name: str | None) -> FakeProfile:
            return FakeProfile(
                sections=(
                    FakeSection(
                        (
                            FakeMetric(
                                "Revenue",
                                "500",
                                "FY2025A",
                                None,
                                "INR",
                                "reported",
                                (FakeCitation(),),
                            ),
                        )
                    ),
                )
            )

    profile = Project1TargetProfileProvider(
        cast(Project1ResearchClient, PartialClient()),
        observed_at=datetime(2026, 7, 15, tzinfo=UTC),
    ).get_target_profile(target())

    assert profile.metrics == ()
    assert any("missing unit" in issue.message for issue in profile.issues)
