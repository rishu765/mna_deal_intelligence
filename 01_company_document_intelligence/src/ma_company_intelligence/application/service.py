"""Reusable application facade over ingestion, indexing, RAG, and research services."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from ma_company_intelligence.application.config import APISettings
from ma_company_intelligence.application.errors import (
    DocumentAccessError,
    DocumentSizeLimitError,
    IndexUnavailableError,
    NoIndexableTextError,
)
from ma_company_intelligence.chunking import ChunkingConfig, chunk_document
from ma_company_intelligence.domain import (
    CompanyResearchProfile,
    DocumentMetadata,
    RAGAnswer,
    RetrievalFilters,
)
from ma_company_intelligence.embeddings import Embedder
from ma_company_intelligence.generation import Generator, ResearchGenerator
from ma_company_intelligence.indexing import ChunkIndexingService, SQLiteVectorStore
from ma_company_intelligence.ingestion import parse_pdf
from ma_company_intelligence.rag import ContextBuilder, GroundedRAGService
from ma_company_intelligence.research import CompanyResearchService, ResearchEvidenceCollector
from ma_company_intelligence.retrieval import SemanticRetriever

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class IndexDocumentCommand:
    source_reference: str
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)


@dataclass(frozen=True, slots=True)
class IndexDocumentResult:
    document_id: str
    source_filename: str
    page_count: int
    chunk_count: int
    records_upserted: int
    total_index_records: int
    warnings: tuple[str, ...]


class CompanyIntelligenceService(Protocol):
    def index_document(self, command: IndexDocumentCommand) -> IndexDocumentResult: ...

    def answer(
        self,
        question: str,
        *,
        top_k: int,
        filters: RetrievalFilters | None = None,
    ) -> RAGAnswer: ...

    def research(
        self,
        *,
        company_name: str | None,
        filters: RetrievalFilters | None = None,
    ) -> CompanyResearchProfile: ...


class CombinedGenerator(Generator, ResearchGenerator, Protocol):
    """Generation capabilities required by both API workflows."""


class ProjectApplicationService:
    """Compose existing domain services without leaking transport concerns into them."""

    def __init__(
        self,
        *,
        embedder: Embedder,
        generator: CombinedGenerator,
        index_path: Path,
        embedding_batch_size: int,
        api_settings: APISettings,
        answer_max_output_tokens: int = 800,
        research_max_output_tokens: int = 4_000,
    ) -> None:
        if embedding_batch_size <= 0:
            raise ValueError("embedding_batch_size must be positive")
        self._embedder = embedder
        self._generator = generator
        self._index_path = index_path
        self._embedding_batch_size = embedding_batch_size
        self._api_settings = api_settings
        self._answer_max_output_tokens = answer_max_output_tokens
        self._research_max_output_tokens = research_max_output_tokens

    def index_document(self, command: IndexDocumentCommand) -> IndexDocumentResult:
        started = time.perf_counter()
        source = self._resolve_document(command.source_reference)
        parsed = parse_pdf(source)
        chunked = chunk_document(parsed, metadata=command.metadata, config=command.chunking)
        if not chunked.chunks:
            raise NoIndexableTextError("document contains no indexable extracted text")
        with self._open_store() as store:
            report = ChunkIndexingService(
                self._embedder,
                store,
                batch_size=self._embedding_batch_size,
            ).index(chunked.chunks)
        LOGGER.info(
            "document_indexed document_id=%s pages=%d chunks=%d duration_ms=%.2f",
            parsed.document_id,
            parsed.page_count,
            len(chunked.chunks),
            (time.perf_counter() - started) * 1000,
        )
        return IndexDocumentResult(
            document_id=parsed.document_id,
            source_filename=parsed.source.filename,
            page_count=parsed.page_count,
            chunk_count=len(chunked.chunks),
            records_upserted=report.records_upserted,
            total_index_records=report.total_records,
            warnings=tuple(warning.message for warning in parsed.warnings),
        )

    def answer(
        self,
        question: str,
        *,
        top_k: int,
        filters: RetrievalFilters | None = None,
    ) -> RAGAnswer:
        self._require_index()
        started = time.perf_counter()
        with self._open_store() as store:
            answer = GroundedRAGService(
                SemanticRetriever(self._embedder, store),
                ContextBuilder(),
                self._generator,
                max_output_tokens=self._answer_max_output_tokens,
            ).answer(question, top_k=top_k, filters=filters)
        LOGGER.info(
            "answer_completed evidence_count=%d insufficient=%s duration_ms=%.2f",
            len(answer.supporting_results),
            answer.insufficient_evidence,
            (time.perf_counter() - started) * 1000,
        )
        return answer

    def research(
        self,
        *,
        company_name: str | None,
        filters: RetrievalFilters | None = None,
    ) -> CompanyResearchProfile:
        self._require_index()
        started = time.perf_counter()
        with self._open_store() as store:
            profile = CompanyResearchService(
                ResearchEvidenceCollector(SemanticRetriever(self._embedder, store)),
                self._generator,
                max_output_tokens=self._research_max_output_tokens,
            ).research(company_name=company_name, filters=filters)
        LOGGER.info(
            "research_completed cited_sources=%d duration_ms=%.2f",
            len(profile.citations),
            (time.perf_counter() - started) * 1000,
        )
        return profile

    def _resolve_document(self, reference: str) -> Path:
        if not reference.strip():
            raise DocumentAccessError("document reference must not be blank")
        root = self._api_settings.document_root.resolve()
        requested = Path(reference)
        candidate = requested if requested.is_absolute() else root / requested
        resolved = candidate.resolve()
        if not resolved.is_relative_to(root):
            raise DocumentAccessError("document reference is outside the configured root")
        if resolved.is_file() and resolved.stat().st_size > self._api_settings.max_document_bytes:
            raise DocumentSizeLimitError("document exceeds the configured size limit")
        return resolved

    def _require_index(self) -> None:
        if not self._index_path.is_file():
            raise IndexUnavailableError("vector index has not been created")

    def _open_store(self) -> SQLiteVectorStore:
        return SQLiteVectorStore(
            self._index_path,
            provider_name=self._embedder.provider_name,
            model_name=self._embedder.model_name,
            dimension=self._embedder.dimension,
        )
