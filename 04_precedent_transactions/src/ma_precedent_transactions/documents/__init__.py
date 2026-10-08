"""Deal document discovery, ingestion, and chunking."""

from ma_precedent_transactions.documents.catalog import FixtureDocumentCatalog
from ma_precedent_transactions.documents.chunking import DealChunkingConfig, TransactionAwareChunker
from ma_precedent_transactions.documents.ingestion import (
    DealDocumentIngestor,
    Project1PdfParserAdapter,
)
from ma_precedent_transactions.documents.models import (
    ChunkedDealDocument,
    DealDocumentChunk,
    DealDocumentSource,
    DealSourceType,
    DocumentFormat,
    ParsedDealDocument,
    ParsedDealPage,
)
from ma_precedent_transactions.documents.ports import DealDocumentCatalog, PdfDocumentParser

__all__ = [
    "ChunkedDealDocument",
    "DealChunkingConfig",
    "DealDocumentCatalog",
    "DealDocumentChunk",
    "DealDocumentIngestor",
    "DealDocumentSource",
    "DealSourceType",
    "DocumentFormat",
    "FixtureDocumentCatalog",
    "ParsedDealDocument",
    "ParsedDealPage",
    "PdfDocumentParser",
    "Project1PdfParserAdapter",
    "TransactionAwareChunker",
]
