"""Adapter from Project 1's public structured research output to Project 2 profiles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ma_target_screening.enrichment.models import EnrichmentRequest, ProviderEnrichmentResult
from ma_target_screening.errors import EnrichmentError
from ma_target_screening.profile import (
    EnrichmentEvidence,
    EvidenceQuality,
    ProfileFact,
    ProfileField,
    ProfileFinancialMetric,
    ProfileInference,
    UnknownField,
)


class Project1Citation(Protocol):
    reference_number: int
    chunk_id: str
    document_id: str
    source_filename: str
    source_title: str | None
    canonical_page_numbers: tuple[int, ...]
    excerpt: str


class Project1Fact(Protocol):
    statement: str
    citations: tuple[Project1Citation, ...]


class Project1Observation(Protocol):
    observation: str
    citations: tuple[Project1Citation, ...]


class Project1FinancialMetric(Protocol):
    metric_name: str
    value: str
    fiscal_period: str | None
    unit: str | None
    currency: str | None
    basis: str | None
    citations: tuple[Project1Citation, ...]


class Project1SectionKey(Protocol):
    value: str


class Project1Section(Protocol):
    key: Project1SectionKey
    summary: str | None
    facts: tuple[Project1Fact, ...]
    observations: tuple[Project1Observation, ...]
    financial_metrics: tuple[Project1FinancialMetric, ...]
    citations: tuple[Project1Citation, ...]
    insufficient_evidence: bool


class Project1ResearchProfile(Protocol):
    sections: tuple[Project1Section, ...]
    warnings: tuple[str, ...]


class Project1ResearchClient(Protocol):
    def research(self, *, company_name: str | None) -> Project1ResearchProfile: ...


_SECTION_FIELDS = {
    "company_context": ProfileField.INDUSTRY,
    "business_overview": ProfileField.BUSINESS_DESCRIPTION,
    "products_services": ProfileField.PRODUCTS_SERVICES,
    "business_segments": ProfileField.INDUSTRY,
    "geographic_exposure": ProfileField.GEOGRAPHIES,
    "customers_end_markets": ProfileField.CUSTOMER_SEGMENTS,
    "financial_highlights": ProfileField.FINANCIALS,
    "major_risks": ProfileField.RISKS,
    "strategic_developments": ProfileField.STRATEGIC_DEVELOPMENTS,
    "management_outlook": ProfileField.GROWTH,
    "ma_relevant_observations": ProfileField.MA_OBSERVATIONS,
}


@dataclass(frozen=True, slots=True)
class Project1DocumentResearchProvider:
    """Map a pre-indexed Project 1 research facade into Project 2's profile vocabulary."""

    client: Project1ResearchClient

    @property
    def provider_name(self) -> str:
        return "project1_document_research"

    def enrich(self, request: EnrichmentRequest) -> ProviderEnrichmentResult:
        if not request.document_references:
            return ProviderEnrichmentResult(
                provider_name=self.provider_name,
                unknown_fields=tuple(
                    UnknownField(field, "No candidate documents were supplied or indexed.")
                    for field in request.priority_fields
                ),
                warnings=(
                    "Project 1 research skipped because candidate documents were unavailable.",
                ),
            )
        try:
            profile = self.client.research(company_name=request.candidate.canonical_name)
            return self._map(profile, request)
        except EnrichmentError:
            raise
        except Exception as error:
            raise EnrichmentError("Project 1 document research failed") from error

    def _map(
        self, profile: Project1ResearchProfile, request: EnrichmentRequest
    ) -> ProviderEnrichmentResult:
        facts: list[ProfileFact] = []
        inferences: list[ProfileInference] = []
        metrics: list[ProfileFinancialMetric] = []
        unknowns: list[UnknownField] = []
        for section in profile.sections:
            field = _SECTION_FIELDS.get(section.key.value)
            if field is None:
                continue
            if section.insufficient_evidence:
                if field in request.priority_fields:
                    unknowns.append(
                        UnknownField(field, "Project 1 reported insufficient document evidence.")
                    )
                continue
            if section.summary and section.citations:
                facts.append(
                    ProfileFact(
                        field=field,
                        value=section.summary,
                        evidence=self._evidence(section.citations),
                    )
                )
            facts.extend(
                ProfileFact(
                    field=field,
                    value=item.statement,
                    evidence=self._evidence(item.citations),
                )
                for item in section.facts
            )
            inferences.extend(
                ProfileInference(
                    field=field,
                    statement=item.observation,
                    evidence=self._evidence(item.citations),
                    rationale="Mapped from Project 1's explicitly analytical observation.",
                )
                for item in section.observations
            )
            metrics.extend(
                ProfileFinancialMetric(
                    metric_name=item.metric_name,
                    value=item.value,
                    fiscal_period=item.fiscal_period,
                    unit=item.unit,
                    currency=item.currency,
                    basis=item.basis,
                    evidence=self._evidence(item.citations),
                )
                for item in section.financial_metrics
            )
        covered = {fact.field for fact in facts}
        if metrics:
            covered.add(ProfileField.FINANCIALS)
        unknown_fields = {item.field for item in unknowns}
        unknowns.extend(
            UnknownField(field, "Project 1 output did not contain this prioritized field.")
            for field in request.priority_fields
            if field not in covered and field not in unknown_fields
        )
        return ProviderEnrichmentResult(
            provider_name=self.provider_name,
            facts=tuple(facts),
            inferences=tuple(inferences),
            financial_metrics=tuple(metrics),
            unknown_fields=tuple(unknowns),
            warnings=profile.warnings,
        )

    def _evidence(self, citations: tuple[Project1Citation, ...]) -> tuple[EnrichmentEvidence, ...]:
        return tuple(
            EnrichmentEvidence(
                evidence_id=f"p1:{citation.reference_number}:{citation.chunk_id}",
                provider_name=self.provider_name,
                source_type="project1_document_citation",
                source_title=citation.source_title or citation.source_filename,
                source_reference=citation.source_filename,
                document_id=citation.document_id,
                chunk_id=citation.chunk_id,
                page_numbers=citation.canonical_page_numbers,
                excerpt=citation.excerpt,
                extraction_method="project1_structured_research",
                quality=EvidenceQuality.PRIMARY,
            )
            for citation in citations
        )
