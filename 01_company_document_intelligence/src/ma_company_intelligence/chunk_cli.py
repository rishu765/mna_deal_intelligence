"""Bounded developer inspection for the parse-to-chunk pipeline."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from ma_company_intelligence.chunking import ChunkingConfig, chunk_document
from ma_company_intelligence.domain import DocumentMetadata
from ma_company_intelligence.ingestion import DocumentIngestionError, parse_pdf


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="madi-inspect-chunks",
        description="Parse and chunk a PDF, then print a bounded provenance-aware summary.",
    )
    parser.add_argument("pdf_path", type=Path, help="Path to a local text-oriented PDF")
    parser.add_argument("--chunk-size", type=int, default=1_800)
    parser.add_argument("--overlap", type=int, default=200)
    parser.add_argument("--min-chunk-size", type=int, default=300)
    parser.add_argument("--max-chunks", type=int, default=5)
    parser.add_argument("--preview-chars", type=int, default=300)
    parser.add_argument("--company")
    parser.add_argument("--document-title")
    parser.add_argument("--document-type")
    parser.add_argument("--fiscal-year", type=int)
    parser.add_argument("--reporting-period")
    parser.add_argument("--source-url")
    parser.add_argument("--filing-type")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run bounded parsing and chunk inspection."""

    parser = _build_parser()
    arguments = parser.parse_args(argv)
    if arguments.max_chunks < 0 or arguments.preview_chars < 0:
        parser.error("--max-chunks and --preview-chars must be non-negative")

    try:
        config = ChunkingConfig(
            max_characters=arguments.chunk_size,
            overlap_characters=arguments.overlap,
            min_chunk_characters=arguments.min_chunk_size,
        )
        metadata = DocumentMetadata(
            company=arguments.company,
            document_title=arguments.document_title,
            document_type=arguments.document_type,
            fiscal_year=arguments.fiscal_year,
            reporting_period=arguments.reporting_period,
            source_url=arguments.source_url,
            filing_type=arguments.filing_type,
        )
        parsed_document = parse_pdf(arguments.pdf_path)
        chunked_document = chunk_document(parsed_document, metadata, config)
    except (DocumentIngestionError, ValueError) as error:
        parser.exit(status=2, message=f"error: {error}\n")

    displayed_chunks = chunked_document.chunks[: arguments.max_chunks]
    summary = {
        "document_id": chunked_document.document_id,
        "source_filename": chunked_document.source.filename,
        "page_count": parsed_document.page_count,
        "chunk_count": len(chunked_document.chunks),
        "chunks_displayed": len(displayed_chunks),
        "chunks_truncated": len(displayed_chunks) < len(chunked_document.chunks),
        "parser_warning_count": len(chunked_document.parser_warnings),
        "chunking_config": asdict(config),
        "metadata": asdict(metadata),
        "chunks": [
            {
                "chunk_id": chunk.chunk_id,
                "chunk_index": chunk.chunk_index,
                "chunk_number": chunk.chunk_number,
                "character_count": chunk.character_count,
                "page_numbers": chunk.page_numbers,
                "page_references": [asdict(reference) for reference in chunk.page_references],
                "text_preview": chunk.text[: arguments.preview_chars],
            }
            for chunk in displayed_chunks
        ],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
