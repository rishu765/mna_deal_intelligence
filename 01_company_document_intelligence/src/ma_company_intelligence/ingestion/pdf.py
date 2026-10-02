"""Page-aware PDF ingestion using PyMuPDF."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import cast

import pymupdf

from ma_company_intelligence.domain import (
    DocumentSource,
    ParsedDocument,
    ParsedPage,
    ParsingWarning,
    ParsingWarningCode,
    SourceProvenance,
)
from ma_company_intelligence.ingestion.errors import (
    DocumentIngestionError,
    EmptyPdfError,
    EncryptedPdfError,
    InvalidDocumentSourceError,
    InvalidPdfError,
    PdfParsingError,
    SourceNotFoundError,
    UnsupportedDocumentTypeError,
)
from ma_company_intelligence.ingestion.normalization import normalize_extracted_text

_HASH_BLOCK_SIZE = 1024 * 1024


class PdfParser:
    """Parse local, text-oriented PDFs into provider-neutral document models."""

    def parse(self, source_path: str | Path) -> ParsedDocument:
        """Validate and parse a PDF in deterministic physical page order."""

        path = self._validate_source(source_path)
        source = self._build_source(path)
        document_id = f"sha256:{source.sha256}"

        try:
            # PyMuPDF 1.x exposes this constructor without complete type annotations.
            with pymupdf.open(path) as pdf:  # type: ignore[no-untyped-call]
                if not pdf.is_pdf:
                    raise InvalidPdfError(path, "file contents are not recognized as PDF")
                if pdf.needs_pass:
                    raise EncryptedPdfError(path)
                if pdf.page_count == 0:
                    raise EmptyPdfError(path)

                pages: list[ParsedPage] = []
                warnings: list[ParsingWarning] = []
                for pdf_page_index in range(pdf.page_count):
                    page_number = pdf_page_index + 1
                    try:
                        page = pdf.load_page(pdf_page_index)
                        raw_text = cast(str, page.get_text("text"))
                    except Exception as error:
                        raise PdfParsingError(path, page_number, str(error)) from error

                    text = normalize_extracted_text(raw_text)
                    provenance = SourceProvenance(
                        document_id=document_id,
                        source_filename=source.filename,
                        source_path=source.path,
                        pdf_page_index=pdf_page_index,
                        page_number=page_number,
                        printed_page_label=None,
                    )
                    pages.append(ParsedPage(text=text, provenance=provenance))
                    if not text.strip():
                        warnings.append(
                            ParsingWarning(
                                code=ParsingWarningCode.EMPTY_PAGE_TEXT,
                                message="Page contains no extractable text; OCR was not attempted.",
                                page_number=page_number,
                            )
                        )

        except DocumentIngestionError:
            raise
        except (pymupdf.EmptyFileError, pymupdf.FileDataError, RuntimeError) as error:
            raise InvalidPdfError(path, str(error)) from error
        except OSError as error:
            raise InvalidDocumentSourceError(path, str(error)) from error

        return ParsedDocument(
            document_id=document_id,
            source=source,
            pages=tuple(pages),
            warnings=tuple(warnings),
        )

    @staticmethod
    def _validate_source(source_path: str | Path) -> Path:
        path = Path(source_path).expanduser()
        if not path.exists():
            raise SourceNotFoundError(path)
        if path.suffix.lower() != ".pdf":
            raise UnsupportedDocumentTypeError(path)
        if not path.is_file():
            raise InvalidDocumentSourceError(path, "path is not a regular file")
        try:
            return path.resolve(strict=True)
        except OSError as error:
            raise InvalidDocumentSourceError(path, str(error)) from error

    @staticmethod
    def _build_source(path: Path) -> DocumentSource:
        digest = hashlib.sha256()
        try:
            with path.open("rb") as source_file:
                while block := source_file.read(_HASH_BLOCK_SIZE):
                    digest.update(block)
            size_bytes = path.stat().st_size
        except OSError as error:
            raise InvalidDocumentSourceError(path, str(error)) from error

        return DocumentSource(
            filename=path.name,
            path=path,
            media_type="application/pdf",
            size_bytes=size_bytes,
            sha256=digest.hexdigest(),
        )


def parse_pdf(source_path: str | Path) -> ParsedDocument:
    """Parse one local PDF using the default M1 parser."""

    return PdfParser().parse(source_path)
