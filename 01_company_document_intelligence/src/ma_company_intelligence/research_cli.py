"""Developer command for PDF-to-structured-company-research validation."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from ma_company_intelligence.chunking import ChunkingConfig, chunk_document
from ma_company_intelligence.citations import CitationError
from ma_company_intelligence.domain import DocumentMetadata, RetrievalFilters
from ma_company_intelligence.embeddings import EmbeddingError, EmbeddingSettings, OpenAIEmbedder
from ma_company_intelligence.generation import GenerationError, GenerationSettings, OpenAIGenerator
from ma_company_intelligence.indexing import (
    ChunkIndexingService,
    IndexingError,
    SQLiteVectorStore,
)
from ma_company_intelligence.ingestion import DocumentIngestionError, parse_pdf
from ma_company_intelligence.research import (
    CompanyResearchService,
    ResearchError,
    ResearchEvidenceCollector,
)
from ma_company_intelligence.retrieval import RetrievalError, SemanticRetriever


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="madi-research",
        description="Parse a PDF and produce a cited structured company research profile.",
    )
    parser.add_argument("pdf_path", type=Path)
    parser.add_argument("--index-path", type=Path)
    parser.add_argument("--top-k-per-section", type=int, default=3)
    parser.add_argument("--max-context-characters", type=int, default=40_000)
    parser.add_argument("--max-output-tokens", type=int, default=4_000)
    parser.add_argument("--preview-chars", type=int, default=300)
    parser.add_argument("--chunk-size", type=int, default=1_800)
    parser.add_argument("--overlap", type=int, default=200)
    parser.add_argument("--min-chunk-size", type=int, default=300)
    parser.add_argument("--company")
    parser.add_argument("--document-title")
    parser.add_argument("--document-type")
    parser.add_argument("--fiscal-year", type=int)
    parser.add_argument("--reporting-period")
    parser.add_argument("--source-url")
    parser.add_argument("--filing-type")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the complete local research pipeline and print bounded JSON."""

    parser = _build_parser()
    arguments = parser.parse_args(argv)
    if arguments.preview_chars < 0:
        parser.error("--preview-chars must be non-negative")

    try:
        embedding_settings = EmbeddingSettings.from_environment()
        generation_settings = GenerationSettings.from_environment()
        index_path = arguments.index_path or embedding_settings.vector_db_path
        parsed_document = parse_pdf(arguments.pdf_path)
        chunked_document = chunk_document(
            parsed_document,
            metadata=DocumentMetadata(
                company=arguments.company,
                document_title=arguments.document_title,
                document_type=arguments.document_type,
                fiscal_year=arguments.fiscal_year,
                reporting_period=arguments.reporting_period,
                source_url=arguments.source_url,
                filing_type=arguments.filing_type,
            ),
            config=ChunkingConfig(
                max_characters=arguments.chunk_size,
                overlap_characters=arguments.overlap,
                min_chunk_characters=arguments.min_chunk_size,
            ),
        )
        embedder = OpenAIEmbedder(
            api_key=embedding_settings.api_key or "",
            model=embedding_settings.model,
            dimension=embedding_settings.dimension,
            timeout=embedding_settings.timeout_seconds,
            max_retries=embedding_settings.max_retries,
        )
        generator = OpenAIGenerator(
            api_key=generation_settings.api_key or "",
            model=generation_settings.model,
            reasoning_effort=generation_settings.reasoning_effort,
            timeout=generation_settings.timeout_seconds,
            max_retries=generation_settings.max_retries,
        )
        with SQLiteVectorStore(
            index_path,
            provider_name=embedder.provider_name,
            model_name=embedder.model_name,
            dimension=embedder.dimension,
        ) as store:
            indexing_report = ChunkIndexingService(
                embedder,
                store,
                batch_size=embedding_settings.batch_size,
            ).index(chunked_document.chunks)
            retriever = SemanticRetriever(embedder, store)
            profile = CompanyResearchService(
                ResearchEvidenceCollector(
                    retriever,
                    top_k_per_section=arguments.top_k_per_section,
                    max_characters=arguments.max_context_characters,
                ),
                generator,
                max_output_tokens=arguments.max_output_tokens,
            ).research(
                company_name=arguments.company,
                filters=RetrievalFilters(document_id=parsed_document.document_id),
            )
    except (
        CitationError,
        DocumentIngestionError,
        EmbeddingError,
        GenerationError,
        IndexingError,
        ResearchError,
        RetrievalError,
        ValueError,
    ) as error:
        parser.exit(status=2, message=f"error: {error}\n")

    summary = {
        "company_name": profile.company_name,
        "document_id": parsed_document.document_id,
        "chunks_indexed": indexing_report.records_upserted,
        "generator": {
            "provider": profile.generator_provider,
            "model": profile.generator_model,
        },
        "warnings": profile.warnings,
        "sections": [
            {
                "key": section.key,
                "summary": section.summary,
                "insufficient_evidence": section.insufficient_evidence,
                "facts": [
                    {
                        "statement": fact.statement,
                        "citations": [citation.marker for citation in fact.citations],
                    }
                    for fact in section.facts
                ],
                "analysis": [
                    {
                        "observation": observation.observation,
                        "citations": [citation.marker for citation in observation.citations],
                    }
                    for observation in section.observations
                ],
                "financial_metrics": [
                    {
                        "metric_name": metric.metric_name,
                        "value": metric.value,
                        "fiscal_period": metric.fiscal_period,
                        "unit": metric.unit,
                        "currency": metric.currency,
                        "basis": metric.basis,
                        "citations": [citation.marker for citation in metric.citations],
                    }
                    for metric in section.financial_metrics
                ],
                "citations": [citation.marker for citation in section.citations],
            }
            for section in profile.sections
        ],
        "citations": [
            {
                "id": citation.citation_id,
                "reference": citation.format_reference(),
                "chunk_id": citation.chunk_id,
                "document_id": citation.document_id,
                "canonical_page_numbers": citation.canonical_page_numbers,
                "physical_pdf_page_indexes": citation.physical_pdf_page_indexes,
                "printed_page_labels": citation.printed_page_labels,
                "excerpt": citation.excerpt[: arguments.preview_chars],
            }
            for citation in profile.citations
        ],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
