"""Bounded developer command for the complete PDF-to-grounded-answer pipeline."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from ma_company_intelligence.chunking import ChunkingConfig, chunk_document
from ma_company_intelligence.domain import DocumentMetadata, RetrievalFilters
from ma_company_intelligence.embeddings import (
    EmbeddingError,
    EmbeddingSettings,
    OpenAIEmbedder,
)
from ma_company_intelligence.generation import (
    GenerationError,
    GenerationSettings,
    OpenAIGenerator,
)
from ma_company_intelligence.indexing import (
    ChunkIndexingService,
    IndexingError,
    SQLiteVectorStore,
)
from ma_company_intelligence.ingestion import DocumentIngestionError, parse_pdf
from ma_company_intelligence.rag import ContextBuilder, GroundedRAGService, RAGError
from ma_company_intelligence.retrieval import RetrievalError, SemanticRetriever


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="madi-answer",
        description="Parse, chunk, index, retrieve, and generate one grounded answer.",
    )
    parser.add_argument("pdf_path", type=Path)
    parser.add_argument("question")
    parser.add_argument("--index-path", type=Path)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--preview-chars", type=int, default=300)
    parser.add_argument("--max-context-characters", type=int, default=12_000)
    parser.add_argument("--max-context-chunks", type=int, default=5)
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
    """Run the complete local RAG pipeline and print a bounded JSON summary."""

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
        )
        generator = OpenAIGenerator(
            api_key=generation_settings.api_key or "",
            model=generation_settings.model,
            reasoning_effort=generation_settings.reasoning_effort,
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
            rag_answer = GroundedRAGService(
                SemanticRetriever(embedder, store),
                ContextBuilder(
                    max_characters=arguments.max_context_characters,
                    max_chunks=arguments.max_context_chunks,
                ),
                generator,
                max_output_tokens=generation_settings.max_output_tokens,
            ).answer(
                arguments.question,
                top_k=arguments.top_k,
                filters=RetrievalFilters(document_id=parsed_document.document_id),
            )
    except (
        DocumentIngestionError,
        EmbeddingError,
        GenerationError,
        IndexingError,
        RAGError,
        RetrievalError,
        ValueError,
    ) as error:
        parser.exit(status=2, message=f"error: {error}\n")

    summary = {
        "question": rag_answer.question,
        "answer": rag_answer.answer,
        "insufficient_evidence": rag_answer.insufficient_evidence,
        "generator": {
            "provider": rag_answer.generator_provider,
            "model": rag_answer.generator_model,
        },
        "document_id": parsed_document.document_id,
        "chunks_indexed": indexing_report.records_upserted,
        "evidence_used": len(rag_answer.supporting_results),
        "warnings": rag_answer.warnings,
        "evidence": [
            {
                "rank": result.rank,
                "score": result.score,
                "chunk_id": result.chunk_id,
                "source_filename": result.chunk.source.filename,
                "page_numbers": result.chunk.page_numbers,
                "company": result.chunk.metadata.company,
                "document_type": result.chunk.metadata.document_type,
                "fiscal_year": result.chunk.metadata.fiscal_year,
                "text_preview": result.text[: arguments.preview_chars],
            }
            for result in rag_answer.supporting_results
        ],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
