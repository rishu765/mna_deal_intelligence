"""Application errors raised by document ingestion."""

from pathlib import Path


class DocumentIngestionError(Exception):
    """Base class for expected document ingestion failures."""


class SourceNotFoundError(DocumentIngestionError):
    """Raised when the requested source path does not exist."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"Document source does not exist: {path}")


class InvalidDocumentSourceError(DocumentIngestionError):
    """Raised when a source exists but is not a readable regular file."""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"Invalid document source '{path}': {reason}")


class UnsupportedDocumentTypeError(DocumentIngestionError):
    """Raised when the source file type is not supported."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"Unsupported document type '{path.suffix or '<none>'}'; expected .pdf")


class InvalidPdfError(DocumentIngestionError):
    """Raised when a file cannot be opened as a structurally valid PDF."""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"Invalid or unreadable PDF '{path}': {reason}")


class EncryptedPdfError(DocumentIngestionError):
    """Raised when a PDF requires a password."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"Encrypted PDF requires a password and cannot be parsed: {path}")


class EmptyPdfError(DocumentIngestionError):
    """Raised when a PDF contains no physical pages."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"PDF contains no pages: {path}")


class PdfParsingError(DocumentIngestionError):
    """Raised when text extraction fails for an otherwise opened PDF."""

    def __init__(self, path: Path, page_number: int, reason: str) -> None:
        super().__init__(f"Failed to parse page {page_number} of '{path}': {reason}")
