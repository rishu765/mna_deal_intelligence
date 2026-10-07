"""Structural adapter from Project 1 research output into M1 observations."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol

from ma_comparable_valuation.domain import (
    EstimateStatus,
    EvidenceReference,
    FinancialObservation,
    FinancialPeriod,
    MetricBasis,
    PeriodKind,
    ProfileIssue,
    ProfileIssueKind,
    TargetCompany,
    TargetFinancialProfile,
)
from ma_comparable_valuation.errors import Project1AdapterError
from ma_comparable_valuation.profile_service import TargetFinancialProfileService


class Project1Citation(Protocol):
    reference_number: int
    chunk_id: str
    document_id: str
    source_filename: str
    source_title: str | None
    canonical_page_numbers: tuple[int, ...]
    excerpt: str


class Project1FinancialMetric(Protocol):
    metric_name: str
    value: str
    fiscal_period: str | None
    unit: str | None
    currency: str | None
    basis: str | None
    citations: tuple[Project1Citation, ...]


class Project1Section(Protocol):
    financial_metrics: tuple[Project1FinancialMetric, ...]


class Project1ResearchProfile(Protocol):
    sections: tuple[Project1Section, ...]
    warnings: tuple[str, ...]


class Project1ResearchClient(Protocol):
    def research(self, *, company_name: str | None) -> Project1ResearchProfile: ...


@dataclass(frozen=True, slots=True)
class Project1TargetProfileProvider:
    """Use Project 1's public research result without importing its implementation types."""

    client: Project1ResearchClient
    observed_at: datetime
    service: TargetFinancialProfileService = TargetFinancialProfileService()
    rolling_period_end_dates: tuple[tuple[str, date], ...] = ()

    @property
    def provider_name(self) -> str:
        return "project1_document_research"

    def get_target_profile(self, target: TargetCompany) -> TargetFinancialProfile:
        try:
            research = self.client.research(company_name=target.identity.name)
        except Exception as error:
            raise Project1AdapterError("Project 1 document research failed") from error

        observations: list[FinancialObservation] = []
        issues: list[ProfileIssue] = []
        ordinal = 0
        for section in research.sections:
            for item in section.financial_metrics:
                ordinal += 1
                observation_id = f"p1:{ordinal}"
                try:
                    observations.append(self._observation(observation_id, item))
                except (InvalidOperation, ValueError) as error:
                    issues.append(
                        ProfileIssue(
                            ProfileIssueKind.INVALID,
                            f"Project 1 metric could not be mapped: {error}",
                            (observation_id,),
                        )
                    )

        profile = self.service.build(target, tuple(observations))
        warnings = (*research.warnings, *(item.message for item in issues), *profile.warnings)
        return replace(
            profile,
            issues=(*issues, *profile.issues),
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def _observation(
        self, observation_id: str, item: Project1FinancialMetric
    ) -> FinancialObservation:
        if not item.citations:
            raise ValueError("metric has no citations")
        period = _parse_period(item.fiscal_period, dict(self.rolling_period_end_dates))
        basis = None if item.basis is None else _parse_basis(item.basis)
        return FinancialObservation(
            observation_id=observation_id,
            raw_metric_name=item.metric_name,
            value=Decimal(item.value.replace(",", "")),
            currency=item.currency,
            unit=item.unit,
            period=period,
            as_of=None if period is None else _period_as_of(period, self.observed_at),
            basis=basis,
            adjustment_label=(item.metric_name if basis is MetricBasis.ADJUSTED else None),
            evidence=tuple(self._evidence(citation) for citation in item.citations),
        )

    def _evidence(self, citation: Project1Citation) -> EvidenceReference:
        return EvidenceReference(
            evidence_id=f"p1:{citation.reference_number}:{citation.chunk_id}",
            source_type="project1_document_citation",
            source_name=citation.source_title or citation.source_filename,
            source_locator=citation.source_filename,
            document_id=citation.document_id,
            chunk_id=citation.chunk_id,
            page_numbers=citation.canonical_page_numbers,
            excerpt=citation.excerpt,
            observed_at=self.observed_at,
            extraction_method="project1_structured_research",
        )


def _parse_basis(value: str) -> MetricBasis:
    normalized = value.casefold().strip()
    if normalized == "reported":
        return MetricBasis.REPORTED
    if normalized == "adjusted":
        return MetricBasis.ADJUSTED
    raise ValueError(f"unsupported Project 1 metric basis: {value}")


def _parse_period(
    value: str | None, rolling_period_end_dates: dict[str, date]
) -> FinancialPeriod | None:
    if value is None:
        return None
    label = " ".join(value.upper().split())
    annual = re.fullmatch(r"(FY|CY)(\d{4})([AE])?", label.replace(" ", ""))
    if annual is not None:
        kind = PeriodKind.FISCAL_YEAR if annual.group(1) == "FY" else PeriodKind.CALENDAR_YEAR
        status = EstimateStatus.ESTIMATE if annual.group(3) == "E" else EstimateStatus.ACTUAL
        return FinancialPeriod(kind, label, status)
    if label.startswith("LTM") or label.startswith("NTM"):
        end_date = rolling_period_end_dates.get(label)
        if end_date is None:
            raise ValueError(f"rolling period requires configured end date: {label}")
        kind = PeriodKind.LTM if label.startswith("LTM") else PeriodKind.NTM
        status = EstimateStatus.ACTUAL if kind is PeriodKind.LTM else EstimateStatus.ESTIMATE
        return FinancialPeriod(kind, label, status, end_date=end_date)
    raise ValueError(f"unsupported Project 1 fiscal period: {value}")


def _period_as_of(period: FinancialPeriod, fallback: datetime) -> datetime:
    if period.end_date is None:
        return fallback
    return fallback.replace(
        year=period.end_date.year,
        month=period.end_date.month,
        day=period.end_date.day,
    )
