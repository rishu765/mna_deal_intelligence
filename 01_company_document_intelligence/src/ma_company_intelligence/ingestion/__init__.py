"""Document ingestion entry points and errors."""

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
from ma_company_intelligence.ingestion.pdf import PdfParser, parse_pdf

__all__ = [
    "DocumentIngestionError",
    "EmptyPdfError",
    "EncryptedPdfError",
    "InvalidDocumentSourceError",
    "InvalidPdfError",
    "PdfParser",
    "PdfParsingError",
    "SourceNotFoundError",
    "UnsupportedDocumentTypeError",
    "parse_pdf",
]
