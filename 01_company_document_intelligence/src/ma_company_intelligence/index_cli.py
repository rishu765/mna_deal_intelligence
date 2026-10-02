"""Developer command for the complete PDF-to-local-index pipeline."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from ma_company_intelligence.chunking import ChunkingConfig, chunk_document
from ma_company_intelligence.domain import DocumentMetadata
from ma_company_intelligence.embeddings import (
    EmbeddingError,
    EmbeddingSettings,
    OpenAIEmbedder,
)
from ma_company_intelligence.indexing import (
    ChunkIndexingService,
    IndexingError,
    SQLiteVectorStore,
)
from ma_company_intelligence.ingestion import DocumentIngestionError, parse_pdf


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="madi-build-index",
        description="Parse, chunk, embed, and persist a PDF without running retrieval.",
    )
    parser.add_argument("pdf_path", type=Path, help="Path to a local text-oriented PDF")
    parser.add_argument("--index-path", type=Path)
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
    """Run PDF ingestion through persisted vector records and print a small summary."""

    parser = _build_parser()
    arguments = parser.parse_args(argv)
    try:
        settings = EmbeddingSettings.from_environment()
        index_path = arguments.index_path or settings.vector_db_path
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
            api_key=settings.api_key or "",
            model=settings.model,
            dimension=settings.dimension,
        )
        with SQLiteVectorStore(
            index_path,
            provider_name=embedder.provider_name,
            model_name=embedder.model_name,
            dimension=embedder.dimension,
        ) as store:
            report = ChunkIndexingService(
                embedder,
                store,
                batch_size=settings.batch_size,
            ).index(chunked_document.chunks)
            sample = (
                store.get(chunked_document.chunks[0].chunk_id)
                if chunked_document.chunks
                else None
            )
    except (DocumentIngestionError, EmbeddingError, IndexingError, ValueError) as error:
        parser.exit(status=2, message=f"error: {error}\n")

    summary = {
        "document_id": parsed_document.document_id,
        "page_count": parsed_document.page_count,
        "chunk_count": len(chunked_document.chunks),
        "embedding_batches": report.embedding_batches,
        "embedding_provider": report.embedding_provider,
        "embedding_model": report.embedding_model,
        "embedding_dimension": report.embedding_dimension,
        "records_upserted": report.records_upserted,
        "total_index_records": report.total_records,
        "index_path": str(index_path.resolve()),
        "sample_record": (
            {
                "record_id": sample.record_id,
                "document_id": sample.chunk.document_id,
                "chunk_index": sample.chunk.chunk_index,
                "page_numbers": sample.chunk.page_numbers,
                "source_filename": sample.chunk.source.filename,
                "company": sample.chunk.metadata.company,
            }
            if sample is not None
            else None
        ),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
