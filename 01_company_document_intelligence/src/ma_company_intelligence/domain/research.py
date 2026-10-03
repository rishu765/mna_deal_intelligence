"""Typed outputs for evidence-backed company and M&A research."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ma_company_intelligence.domain.citations import Citation


class ResearchSectionKey(StrEnum):
    COMPANY_CONTEXT = "company_context"
    BUSINESS_OVERVIEW = "business_overview"
    PRODUCTS_SERVICES = "products_services"
    BUSINESS_SEGMENTS = "business_segments"
    GEOGRAPHIC_EXPOSURE = "geographic_exposure"
    CUSTOMERS_END_MARKETS = "customers_end_markets"
    FINANCIAL_HIGHLIGHTS = "financial_highlights"
    MAJOR_RISKS = "major_risks"
    STRATEGIC_DEVELOPMENTS = "strategic_developments"
    MANAGEMENT_OUTLOOK = "management_outlook"
    MA_RELEVANT_OBSERVATIONS = "ma_relevant_observations"


RESEARCH_SECTION_ORDER = tuple(ResearchSectionKey)


@dataclass(frozen=True, slots=True)
class ResearchFact:
    """A directly supported factual statement."""

    statement: str
    citations: tuple[Citation, ...]

    def __post_init__(self) -> None:
        if not self.statement.strip():
            raise ValueError("research fact must not be blank")
        if not self.citations:
            raise ValueError("research fact must have supporting citations")


@dataclass(frozen=True, slots=True)
class ResearchObservation:
    """An explicitly analytical M&A observation grounded in cited facts."""

    observation: str
    citations: tuple[Citation, ...]

    def __post_init__(self) -> None:
        if not self.observation.strip():
            raise ValueError("research observation must not be blank")
        if not self.citations:
            raise ValueError("research observation must have supporting citations")


@dataclass(frozen=True, slots=True)
class FinancialMetric:
    """A disclosed financial metric with its original semantic qualifiers."""

    metric_name: str
    value: str
    fiscal_period: str | None
    unit: str | None
    currency: str | None
    basis: str | None
    citations: tuple[Citation, ...]

    def __post_init__(self) -> None:
        for field_name in ("metric_name", "value"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"financial metric {field_name} must not be blank")
        for field_name in ("fiscal_period", "unit", "currency", "basis"):
            value = getattr(self, field_name)
            if value is not None and not value.strip():
                raise ValueError(f"financial metric {field_name} must be non-blank when supplied")
        if not self.citations:
            raise ValueError("financial metric must have supporting citations")


@dataclass(frozen=True, slots=True)
class ResearchSection:
    """One structured research category and its section-local evidence."""

    key: ResearchSectionKey
    summary: str | None
    facts: tuple[ResearchFact, ...]
    observations: tuple[ResearchObservation, ...]
    financial_metrics: tuple[FinancialMetric, ...]
    citations: tuple[Citation, ...]
    insufficient_evidence: bool

    def __post_init__(self) -> None:
        if self.summary is not None and not self.summary.strip():
            raise ValueError("research section summary must be non-blank when supplied")
        content_present = bool(
            self.summary or self.facts or self.observations or self.financial_metrics
        )
        if self.insufficient_evidence and (content_present or self.citations):
            raise ValueError("an insufficient section cannot contain claims or citations")
        if not self.insufficient_evidence and (not content_present or not self.citations):
            raise ValueError("a supported section must contain content and citations")
        if self.financial_metrics and self.key is not ResearchSectionKey.FINANCIAL_HIGHLIGHTS:
            raise ValueError("financial metrics belong only in financial_highlights")


@dataclass(frozen=True, slots=True)
class CompanyResearchProfile:
    """Complete evidence-backed structured company research output."""

    company_name: str | None
    sections: tuple[ResearchSection, ...]
    citations: tuple[Citation, ...]
    source_document_ids: tuple[str, ...]
    generator_provider: str
    generator_model: str
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.company_name is not None and not self.company_name.strip():
            raise ValueError("company_name must be non-blank when supplied")
        if tuple(section.key for section in self.sections) != RESEARCH_SECTION_ORDER:
            raise ValueError("research sections must appear once in the canonical order")
        if not self.generator_provider.strip() or not self.generator_model.strip():
            raise ValueError("generator provider and model must not be blank")
        expected_numbers = tuple(range(1, len(self.citations) + 1))
        if tuple(c.reference_number for c in self.citations) != expected_numbers:
            raise ValueError("profile citations must have contiguous one-based numbering")
        if len(set(self.source_document_ids)) != len(self.source_document_ids):
            raise ValueError("source_document_ids must be unique")
        if any(not document_id.strip() for document_id in self.source_document_ids):
            raise ValueError("source_document_ids must not contain blank values")
        catalog = {(citation.reference_number, citation.chunk_id) for citation in self.citations}
        section_citations = (
            citation
            for section in self.sections
            for citation in (
                *section.citations,
                *(citation for fact in section.facts for citation in fact.citations),
                *(
                    citation
                    for observation in section.observations
                    for citation in observation.citations
                ),
                *(
                    citation
                    for metric in section.financial_metrics
                    for citation in metric.citations
                ),
            )
        )
        if any(
            (citation.reference_number, citation.chunk_id) not in catalog
            for citation in section_citations
        ):
            raise ValueError("every section citation must belong to the profile citation catalog")

    def section(self, key: ResearchSectionKey) -> ResearchSection:
        """Return one named section from the canonical profile."""

        return self.sections[RESEARCH_SECTION_ORDER.index(key)]
