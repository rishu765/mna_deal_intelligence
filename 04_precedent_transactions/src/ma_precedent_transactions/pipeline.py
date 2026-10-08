"""Deal-centric discovery-to-index pipeline for M1/2."""

from __future__ import annotations

from dataclasses import dataclass

from ma_precedent_transactions.discovery import (
    AcquisitionContext,
    DealDiscoveryResult,
    DealDiscoveryService,
)
from ma_precedent_transactions.documents import (
    DealDocumentCatalog,
    DealDocumentChunk,
    DealDocumentIngestor,
    DealDocumentSource,
    ParsedDealDocument,
    TransactionAwareChunker,
)
from ma_precedent_transactions.errors import DocumentError
from ma_precedent_transactions.retrieval import IndexingReport, InMemoryDealIndex


@dataclass(frozen=True, slots=True)
class DealResearchCorpus:
    discovery: DealDiscoveryResult
    document_sources: tuple[DealDocumentSource, ...]
    parsed_documents: tuple[ParsedDealDocument, ...]
    chunks: tuple[DealDocumentChunk, ...]
    indexing_report: IndexingReport
    warnings: tuple[str, ...] = ()


class DealResearchPipeline:
    def __init__(
        self,
        discovery: DealDiscoveryService,
        document_catalog: DealDocumentCatalog,
        ingestor: DealDocumentIngestor,
        chunker: TransactionAwareChunker,
        index: InMemoryDealIndex,
    ) -> None:
        self._discovery = discovery
        self._document_catalog = document_catalog
        self._ingestor = ingestor
        self._chunker = chunker
        self._index = index

    @property
    def index(self) -> InMemoryDealIndex:
        return self._index

    def build(self, context: AcquisitionContext) -> DealResearchCorpus:
        discovery = self._discovery.discover(context)
        transaction_ids = tuple(item.candidate_id for item in discovery.transactions)
        sources = self._document_catalog.find_for_transactions(transaction_ids)
        transaction_by_id = {item.candidate_id: item for item in discovery.transactions}
        parsed_documents: list[ParsedDealDocument] = []
        chunks: list[DealDocumentChunk] = []
        warnings = list(discovery.warnings)
        if discovery.transactions and not sources:
            warnings.append("No source documents were found for discovered transactions.")
        for source in sources:
            transaction = transaction_by_id.get(source.transaction_id)
            if transaction is None:
                warnings.append(
                    f"Document {source.source_id} was ignored because its transaction "
                    "was not discovered."
                )
                continue
            try:
                parsed = self._ingestor.ingest(source)
                chunked = self._chunker.chunk(parsed, transaction)
            except DocumentError as error:
                warnings.append(f"Document {source.source_id} failed ingestion: {error}")
                continue
            parsed_documents.append(parsed)
            chunks.extend(chunked.chunks)
            warnings.extend(chunked.parser_warnings)
        report = self._index.index(tuple(chunks))
        return DealResearchCorpus(
            discovery=discovery,
            document_sources=sources,
            parsed_documents=tuple(parsed_documents),
            chunks=tuple(chunks),
            indexing_report=report,
            warnings=tuple(dict.fromkeys(warnings)),
        )
