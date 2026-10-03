"""Stable HTTP request and response schemas."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from ma_company_intelligence.application import IndexDocumentResult
from ma_company_intelligence.chunking import ChunkingConfig
from ma_company_intelligence.domain import (
    Citation,
    CompanyResearchProfile,
    DocumentMetadata,
    RAGAnswer,
    ResearchSection,
    RetrievalFilters,
)

NonBlank = Annotated[str, Field(min_length=1)]
OptionalShortText = Annotated[str | None, Field(default=None, min_length=1, max_length=500)]


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class HealthResponse(APIModel):
    status: Literal["ok"] = "ok"
    service: Literal["ma-company-intelligence"] = "ma-company-intelligence"
    version: str = "0.1.0"


class MetadataRequest(APIModel):
    company: OptionalShortText = None
    document_title: OptionalShortText = None
    document_type: OptionalShortText = None
    fiscal_year: int | None = Field(default=None, ge=1800, le=2200)
    reporting_period: OptionalShortText = None
    source_url: OptionalShortText = None
    filing_type: OptionalShortText = None

    def to_domain(self) -> DocumentMetadata:
        return DocumentMetadata(**self.model_dump())


class ChunkingRequest(APIModel):
    max_characters: int = Field(default=1_800, ge=100, le=20_000)
    overlap_characters: int = Field(default=200, ge=0, le=5_000)
    min_chunk_characters: int = Field(default=300, ge=1, le=20_000)

    def to_domain(self) -> ChunkingConfig:
        return ChunkingConfig(**self.model_dump())


class IndexDocumentRequest(APIModel):
    source_reference: NonBlank = Field(max_length=500)
    metadata: MetadataRequest = Field(default_factory=MetadataRequest)
    chunking: ChunkingRequest = Field(default_factory=ChunkingRequest)


class IndexDocumentResponse(APIModel):
    document_id: str
    source_filename: str
    page_count: int
    chunk_count: int
    records_upserted: int
    total_index_records: int
    warnings: list[str]

    @classmethod
    def from_domain(cls, result: IndexDocumentResult) -> IndexDocumentResponse:
        return cls(
            document_id=result.document_id,
            source_filename=result.source_filename,
            page_count=result.page_count,
            chunk_count=result.chunk_count,
            records_upserted=result.records_upserted,
            total_index_records=result.total_index_records,
            warnings=list(result.warnings),
        )


class RetrievalFiltersRequest(APIModel):
    document_id: OptionalShortText = None
    source_filename: OptionalShortText = None
    company: OptionalShortText = None
    document_type: OptionalShortText = None
    fiscal_year: int | None = Field(default=None, ge=1800, le=2200)

    def to_domain(self) -> RetrievalFilters:
        return RetrievalFilters(**self.model_dump())


class QuestionRequest(APIModel):
    question: NonBlank = Field(max_length=10_000)
    top_k: int = Field(default=5, ge=1, le=100)
    filters: RetrievalFiltersRequest | None = None


class ResearchRequest(APIModel):
    company_name: OptionalShortText = None
    filters: RetrievalFiltersRequest | None = None


class MetadataResponse(APIModel):
    company: str | None
    document_title: str | None
    document_type: str | None
    fiscal_year: int | None
    reporting_period: str | None
    source_url: str | None
    filing_type: str | None


class CitationResponse(APIModel):
    id: str
    marker: str
    reference: str
    chunk_id: str
    document_id: str
    source_filename: str
    source_title: str | None
    canonical_page_numbers: list[int]
    physical_pdf_page_indexes: list[int]
    printed_page_labels: list[str | None]
    excerpt: str
    metadata: MetadataResponse

    @classmethod
    def from_domain(cls, citation: Citation) -> CitationResponse:
        return cls(
            id=citation.citation_id,
            marker=citation.marker,
            reference=citation.format_reference(),
            chunk_id=citation.chunk_id,
            document_id=citation.document_id,
            source_filename=citation.source_filename,
            source_title=citation.source_title,
            canonical_page_numbers=list(citation.canonical_page_numbers),
            physical_pdf_page_indexes=list(citation.physical_pdf_page_indexes),
            printed_page_labels=list(citation.printed_page_labels),
            excerpt=citation.excerpt,
            metadata=MetadataResponse(**asdict(citation.metadata)),
        )


class EvidenceResponse(APIModel):
    rank: int
    score: float
    chunk_id: str
    document_id: str
    source_filename: str
    canonical_page_numbers: list[int]
    text: str
    metadata: MetadataResponse


class AnswerResponse(APIModel):
    question: str
    answer: str
    insufficient_evidence: bool
    generator_provider: str
    generator_model: str
    citations: list[CitationResponse]
    evidence: list[EvidenceResponse]
    warnings: list[str]

    @classmethod
    def from_domain(cls, answer: RAGAnswer) -> AnswerResponse:
        return cls(
            question=answer.question,
            answer=answer.answer,
            insufficient_evidence=answer.insufficient_evidence,
            generator_provider=answer.generator_provider,
            generator_model=answer.generator_model,
            citations=[CitationResponse.from_domain(value) for value in answer.citations],
            evidence=[
                EvidenceResponse(
                    rank=result.rank,
                    score=result.score,
                    chunk_id=result.chunk_id,
                    document_id=result.document_id,
                    source_filename=result.chunk.source.filename,
                    canonical_page_numbers=list(result.chunk.page_numbers),
                    text=result.text,
                    metadata=MetadataResponse(**asdict(result.chunk.metadata)),
                )
                for result in answer.supporting_results
            ],
            warnings=list(answer.warnings),
        )


class ResearchFactResponse(APIModel):
    statement: str
    citations: list[CitationResponse]


class ResearchObservationResponse(APIModel):
    observation: str
    citations: list[CitationResponse]


class FinancialMetricResponse(APIModel):
    metric_name: str
    value: str
    fiscal_period: str | None
    unit: str | None
    currency: str | None
    basis: str | None
    citations: list[CitationResponse]


class ResearchSectionResponse(APIModel):
    key: str
    summary: str | None
    insufficient_evidence: bool
    facts: list[ResearchFactResponse]
    observations: list[ResearchObservationResponse]
    financial_metrics: list[FinancialMetricResponse]
    citations: list[CitationResponse]

    @classmethod
    def from_domain(cls, section: ResearchSection) -> ResearchSectionResponse:
        return cls(
            key=section.key,
            summary=section.summary,
            insufficient_evidence=section.insufficient_evidence,
            facts=[
                ResearchFactResponse(
                    statement=fact.statement,
                    citations=[CitationResponse.from_domain(value) for value in fact.citations],
                )
                for fact in section.facts
            ],
            observations=[
                ResearchObservationResponse(
                    observation=item.observation,
                    citations=[CitationResponse.from_domain(value) for value in item.citations],
                )
                for item in section.observations
            ],
            financial_metrics=[
                FinancialMetricResponse(
                    metric_name=metric.metric_name,
                    value=metric.value,
                    fiscal_period=metric.fiscal_period,
                    unit=metric.unit,
                    currency=metric.currency,
                    basis=metric.basis,
                    citations=[CitationResponse.from_domain(value) for value in metric.citations],
                )
                for metric in section.financial_metrics
            ],
            citations=[CitationResponse.from_domain(value) for value in section.citations],
        )


class ResearchResponse(APIModel):
    company_name: str | None
    sections: list[ResearchSectionResponse]
    citations: list[CitationResponse]
    source_document_ids: list[str]
    generator_provider: str
    generator_model: str
    warnings: list[str]

    @classmethod
    def from_domain(cls, profile: CompanyResearchProfile) -> ResearchResponse:
        return cls(
            company_name=profile.company_name,
            sections=[ResearchSectionResponse.from_domain(value) for value in profile.sections],
            citations=[CitationResponse.from_domain(value) for value in profile.citations],
            source_document_ids=list(profile.source_document_ids),
            generator_provider=profile.generator_provider,
            generator_model=profile.generator_model,
            warnings=list(profile.warnings),
        )


class ErrorBody(APIModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(APIModel):
    error: ErrorBody
