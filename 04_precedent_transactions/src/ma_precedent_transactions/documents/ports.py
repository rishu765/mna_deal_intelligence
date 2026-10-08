"""Document catalog and PDF parsing boundaries."""

from pathlib import Path
from typing import Protocol

from ma_precedent_transactions.documents.models import DealDocumentSource, ParsedDealDocument


class DealDocumentCatalog(Protocol):
    def find_for_transactions(
        self, transaction_ids: tuple[str, ...]
    ) -> tuple[DealDocumentSource, ...]: ...


class PdfDocumentParser(Protocol):
    def parse(self, source: DealDocumentSource, path: Path) -> ParsedDealDocument: ...
