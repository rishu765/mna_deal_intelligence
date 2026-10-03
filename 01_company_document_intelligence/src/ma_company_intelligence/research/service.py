"""Orchestration for targeted retrieval and structured company research synthesis."""

from __future__ import annotations

from ma_company_intelligence.citations import CitationBuilder, CitationMapping
from ma_company_intelligence.domain import (
    RESEARCH_SECTION_ORDER,
    CompanyResearchProfile,
    FinancialMetric,
    ResearchFact,
    ResearchObservation,
    ResearchSection,
    RetrievalFilters,
)
from ma_company_intelligence.generation import GenerationRequest, ResearchGenerator
from ma_company_intelligence.generation.research import GeneratedResearchSection
from ma_company_intelligence.research.context import ResearchEvidenceCollector
from ma_company_intelligence.research.errors import InvalidResearchRequestError
from ma_company_intelligence.research.prompts import (
    RESEARCH_INSTRUCTIONS,
    build_research_input,
)


class CompanyResearchService:
    """Collect category evidence and produce a typed, cited company profile."""

    def __init__(
        self,
        evidence_collector: ResearchEvidenceCollector,
        generator: ResearchGenerator,
        *,
        citation_builder: CitationBuilder | None = None,
        max_output_tokens: int = 4_000,
    ) -> None:
        if max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")
        self._evidence_collector = evidence_collector
        self._generator = generator
        self._citation_builder = citation_builder or CitationBuilder()
        self._max_output_tokens = max_output_tokens

    def research(
        self,
        *,
        company_name: str | None = None,
        filters: RetrievalFilters | None = None,
    ) -> CompanyResearchProfile:
        """Return a canonical profile, abstaining section-by-section when evidence is absent."""

        if company_name is not None and not company_name.strip():
            raise InvalidResearchRequestError("company_name must be non-blank when supplied")
        context = self._evidence_collector.collect(company_name=company_name, filters=filters)
        if not context.evidence_by_id:
            return self._empty_profile(
                company_name,
                warning="Targeted retrieval returned no evidence, so generation was skipped.",
            )

        generated = self._generator.generate_research(
            GenerationRequest(
                instructions=RESEARCH_INSTRUCTIONS,
                input_text=build_research_input(company_name=company_name, context=context.text),
                max_output_tokens=self._max_output_tokens,
            )
        )
        citation_mapping = self._citation_builder.build(
            generated.referenced_evidence_ids,
            context.evidence_by_id,
        )
        sections = tuple(
            self._build_section(section, citation_mapping) for section in generated.sections
        )
        warnings: list[str] = []
        if context.omitted_result_count:
            warnings.append(
                f"{context.omitted_result_count} targeted retrieval result(s) were omitted "
                "by the research context limit."
            )
        source_document_ids = tuple(
            dict.fromkeys(citation.document_id for citation in citation_mapping.citations)
        )
        return CompanyResearchProfile(
            company_name=company_name or generated.company_name,
            sections=sections,
            citations=citation_mapping.citations,
            source_document_ids=source_document_ids,
            generator_provider=self._generator.provider_name,
            generator_model=self._generator.model_name,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _build_section(
        section: GeneratedResearchSection,
        citation_mapping: CitationMapping,
    ) -> ResearchSection:
        if section.insufficient_evidence:
            return ResearchSection(
                key=section.key,
                summary=None,
                facts=(),
                observations=(),
                financial_metrics=(),
                citations=(),
                insufficient_evidence=True,
            )
        facts = tuple(
            ResearchFact(
                statement=item.text,
                citations=citation_mapping.citations_for(item.evidence_ids),
            )
            for item in section.facts
        )
        observations = tuple(
            ResearchObservation(
                observation=item.text,
                citations=citation_mapping.citations_for(item.evidence_ids),
            )
            for item in section.observations
        )
        metrics = tuple(
            FinancialMetric(
                metric_name=metric.metric_name,
                value=metric.value,
                fiscal_period=metric.fiscal_period,
                unit=metric.unit,
                currency=metric.currency,
                basis=metric.basis,
                citations=citation_mapping.citations_for(metric.evidence_ids),
            )
            for metric in section.financial_metrics
        )
        section_citations = citation_mapping.citations_for(section.referenced_evidence_ids)
        return ResearchSection(
            key=section.key,
            summary=section.summary,
            facts=facts,
            observations=observations,
            financial_metrics=metrics,
            citations=section_citations,
            insufficient_evidence=False,
        )

    def _empty_profile(self, company_name: str | None, *, warning: str) -> CompanyResearchProfile:
        return CompanyResearchProfile(
            company_name=company_name,
            sections=tuple(
                ResearchSection(
                    key=key,
                    summary=None,
                    facts=(),
                    observations=(),
                    financial_metrics=(),
                    citations=(),
                    insufficient_evidence=True,
                )
                for key in RESEARCH_SECTION_ORDER
            ),
            citations=(),
            source_document_ids=(),
            generator_provider=self._generator.provider_name,
            generator_model=self._generator.model_name,
            warnings=(warning,),
        )
