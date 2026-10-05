"""Plain-Python multi-provider candidate enrichment orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ma_target_screening.domain import CandidateCompany
from ma_target_screening.enrichment.models import EnrichmentRequest
from ma_target_screening.errors import EnrichmentError
from ma_target_screening.ports import EnrichmentProvider
from ma_target_screening.profile import (
    CandidateProfile,
    ConflictAlternative,
    EnrichmentStatus,
    ProfileConflict,
    ProfileFact,
    ProfileField,
    ProfileFinancialMetric,
    ProfileInference,
    UnknownField,
)
from ma_target_screening.thesis import AcquisitionThesis, CriterionCategory

LOGGER = logging.getLogger(__name__)

_CORE_FIELDS = (
    ProfileField.BUSINESS_DESCRIPTION,
    ProfileField.INDUSTRY,
    ProfileField.PRODUCTS_SERVICES,
    ProfileField.GEOGRAPHIES,
)

_CRITERION_FIELDS = {
    CriterionCategory.INDUSTRY: ProfileField.INDUSTRY,
    CriterionCategory.SUB_INDUSTRY: ProfileField.SUB_INDUSTRY,
    CriterionCategory.PRODUCT_CAPABILITY: ProfileField.CAPABILITIES,
    CriterionCategory.GEOGRAPHY: ProfileField.GEOGRAPHIES,
    CriterionCategory.REVENUE: ProfileField.FINANCIALS,
    CriterionCategory.PROFITABILITY: ProfileField.PROFITABILITY,
    CriterionCategory.COMPANY_SIZE: ProfileField.COMPANY_SIZE,
    CriterionCategory.EMPLOYEE_COUNT: ProfileField.EMPLOYEE_COUNT,
    CriterionCategory.GROWTH: ProfileField.GROWTH,
    CriterionCategory.OWNERSHIP: ProfileField.OWNERSHIP,
    CriterionCategory.CUSTOMER_TYPE: ProfileField.CUSTOMER_SEGMENTS,
    CriterionCategory.TECHNOLOGY: ProfileField.TECHNOLOGY,
    CriterionCategory.STRATEGIC_FIT: ProfileField.MA_OBSERVATIONS,
}

_SINGLE_VALUE_FIELDS = {
    ProfileField.PROFITABILITY,
    ProfileField.EMPLOYEE_COUNT,
    ProfileField.COMPANY_SIZE,
    ProfileField.OWNERSHIP,
}


@dataclass(frozen=True, slots=True)
class CandidateEnrichmentService:
    providers: tuple[EnrichmentProvider, ...]

    def __post_init__(self) -> None:
        if not self.providers:
            raise ValueError("at least one enrichment provider is required")
        names = [provider.provider_name for provider in self.providers]
        if len(set(names)) != len(names):
            raise ValueError("enrichment provider names must be unique")

    def enrich(
        self,
        candidate: CandidateCompany,
        thesis: AcquisitionThesis,
        *,
        document_references: tuple[str, ...] = (),
    ) -> CandidateProfile:
        requested = self.priority_fields(thesis)
        request = EnrichmentRequest(
            candidate=candidate,
            thesis=thesis,
            priority_fields=requested,
            document_references=document_references,
        )
        facts: list[ProfileFact] = []
        inferences: list[ProfileInference] = []
        metrics: list[ProfileFinancialMetric] = []
        unknowns: list[UnknownField] = []
        warnings: list[str] = []
        successful: list[str] = []
        failures: list[str] = []
        LOGGER.info(
            "candidate enrichment started candidate=%s providers=%d fields=%d",
            candidate.canonical_name,
            len(self.providers),
            len(requested),
        )
        for provider in self.providers:
            try:
                result = provider.enrich(request)
            except (EnrichmentError, TypeError, ValueError):
                failures.append(provider.provider_name)
                warnings.append(f"Enrichment provider failed: {provider.provider_name}")
                LOGGER.warning("enrichment provider failed provider=%s", provider.provider_name)
                continue
            if result.provider_name != provider.provider_name:
                failures.append(provider.provider_name)
                warnings.append(
                    f"Enrichment provider returned mismatched name: {provider.provider_name}"
                )
                continue
            successful.append(provider.provider_name)
            facts.extend(result.facts)
            inferences.extend(result.inferences)
            metrics.extend(result.financial_metrics)
            unknowns.extend(result.unknown_fields)
            warnings.extend(result.warnings)

        facts_tuple = tuple(dict.fromkeys(facts))
        inference_tuple = tuple(dict.fromkeys(inferences))
        metrics_tuple = tuple(dict.fromkeys(metrics))
        conflicts = self._conflicts(facts_tuple, metrics_tuple)
        covered = {fact.field for fact in facts_tuple}
        if metrics_tuple:
            covered.add(ProfileField.FINANCIALS)
        unknown_tuple = tuple(item for item in dict.fromkeys(unknowns) if item.field not in covered)
        status = self._status(
            requested=requested,
            covered=covered,
            has_content=bool(facts_tuple or inference_tuple or metrics_tuple),
            conflicts=conflicts,
            all_failed=bool(failures and not successful),
        )
        if failures and successful:
            warnings.append("Candidate profile contains partial results after provider failure.")
        if status is EnrichmentStatus.INSUFFICIENT_EVIDENCE:
            warnings.append("Enrichment completed without enough evidence for prioritized fields.")
        LOGGER.info(
            "candidate enrichment completed candidate=%s facts=%d metrics=%d "
            "conflicts=%d status=%s",
            candidate.canonical_name,
            len(facts_tuple),
            len(metrics_tuple),
            len(conflicts),
            status.value,
        )
        return CandidateProfile(
            candidate=candidate,
            facts=facts_tuple,
            inferences=inference_tuple,
            financial_metrics=metrics_tuple,
            unknown_fields=unknown_tuple,
            conflicts=conflicts,
            status=status,
            provider_names=tuple(successful),
            requested_fields=requested,
            warnings=tuple(dict.fromkeys(warnings)),
        )

    @staticmethod
    def priority_fields(thesis: AcquisitionThesis) -> tuple[ProfileField, ...]:
        fields = list(_CORE_FIELDS)
        fields.extend(
            _CRITERION_FIELDS[criterion.category]
            for criterion in thesis.criteria
            if criterion.category in _CRITERION_FIELDS
        )
        return tuple(dict.fromkeys(fields))

    @staticmethod
    def _conflicts(
        facts: tuple[ProfileFact, ...], metrics: tuple[ProfileFinancialMetric, ...]
    ) -> tuple[ProfileConflict, ...]:
        conflicts: list[ProfileConflict] = []
        fact_fields = {fact.field for fact in facts if fact.field in _SINGLE_VALUE_FIELDS}
        for field in fact_fields:
            values: dict[str, list[ProfileFact]] = {}
            for fact in facts:
                if fact.field is field:
                    values.setdefault(fact.value.casefold(), []).append(fact)
            if len(values) > 1:
                conflicts.append(
                    ProfileConflict(
                        field=field,
                        alternatives=tuple(
                            ConflictAlternative(
                                value=group[0].value,
                                evidence=tuple(
                                    dict.fromkeys(e for fact in group for e in fact.evidence)
                                ),
                            )
                            for group in values.values()
                        ),
                        reason="Providers reported different evidence-backed values.",
                    )
                )
        metric_groups: dict[tuple[str, str | None], list[ProfileFinancialMetric]] = {}
        for metric in metrics:
            metric_groups.setdefault(
                (metric.metric_name.casefold(), metric.fiscal_period), []
            ).append(metric)
        for group in metric_groups.values():
            by_value: dict[str, list[ProfileFinancialMetric]] = {}
            for metric in group:
                by_value.setdefault(metric.value.casefold(), []).append(metric)
            if len(by_value) > 1:
                conflicts.append(
                    ProfileConflict(
                        field=ProfileField.FINANCIALS,
                        alternatives=tuple(
                            ConflictAlternative(
                                value=items[0].value,
                                evidence=tuple(
                                    dict.fromkeys(e for item in items for e in item.evidence)
                                ),
                            )
                            for items in by_value.values()
                        ),
                        reason=(
                            "Sources reported different values for the same metric and period."
                        ),
                    )
                )
        return tuple(conflicts)

    @staticmethod
    def _status(
        *,
        requested: tuple[ProfileField, ...],
        covered: set[ProfileField],
        has_content: bool,
        conflicts: tuple[ProfileConflict, ...],
        all_failed: bool,
    ) -> EnrichmentStatus:
        if all_failed:
            return EnrichmentStatus.PROVIDER_FAILURE
        if not has_content:
            return EnrichmentStatus.INSUFFICIENT_EVIDENCE
        coverage = len(covered & set(requested)) / len(requested) if requested else 1.0
        if coverage >= 0.6 and not conflicts:
            return EnrichmentStatus.COMPLETE_ENOUGH
        return EnrichmentStatus.PARTIAL
