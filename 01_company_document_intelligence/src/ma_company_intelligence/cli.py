"""Developer-facing command-line helpers."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from ma_company_intelligence.ingestion import DocumentIngestionError, parse_pdf


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="madi-inspect-pdf",
        description="Parse a PDF and print a bounded provenance-aware summary.",
    )
    parser.add_argument("pdf_path", type=Path, help="Path to a local text-oriented PDF")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=3,
        help="Maximum number of page previews to print (default: 3)",
    )
    parser.add_argument(
        "--preview-chars",
        type=int,
        default=300,
        help="Maximum characters per page preview (default: 300)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the bounded PDF inspection command."""

    parser = _build_parser()
    arguments = parser.parse_args(argv)
    if arguments.max_pages < 0 or arguments.preview_chars < 0:
        parser.error("--max-pages and --preview-chars must be non-negative")

    try:
        document = parse_pdf(arguments.pdf_path)
    except DocumentIngestionError as error:
        parser.exit(status=2, message=f"error: {error}\n")

    previews = [
        {
            "page_number": page.page_number,
            "pdf_page_index": page.provenance.pdf_page_index,
            "printed_page_label": page.provenance.printed_page_label,
            "text_preview": page.text[: arguments.preview_chars],
        }
        for page in document.pages[: arguments.max_pages]
    ]
    summary = {
        "document_id": document.document_id,
        "source_filename": document.source.filename,
        "source_path": str(document.source.path),
        "page_count": document.page_count,
        "warnings": [
            {
                "code": warning.code.value,
                "page_number": warning.page_number,
                "message": warning.message,
            }
            for warning in document.warnings
        ],
        "page_previews": previews,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
