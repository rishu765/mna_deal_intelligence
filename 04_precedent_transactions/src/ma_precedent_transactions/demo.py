"""Reproducible offline M1/2 discovery and retrieval demo."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from ma_precedent_transactions.discovery import (
    AcquisitionContext,
    DealDiscoveryService,
    FixtureDealDiscoveryProvider,
)
from ma_precedent_transactions.documents import (
    DealDocumentIngestor,
    FixtureDocumentCatalog,
    TransactionAwareChunker,
)
from ma_precedent_transactions.evaluation import load_benchmark, run_benchmark
from ma_precedent_transactions.pipeline import DealResearchPipeline
from ma_precedent_transactions.retrieval import (
    HashingEmbeddingProvider,
    HybridDealRetriever,
    InMemoryDealIndex,
    RetrievalFilters,
    RetrievalResponse,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def build_fixture_pipeline() -> DealResearchPipeline:
    data_root = PROJECT_ROOT / "data" / "fixtures"
    embedder = HashingEmbeddingProvider()
    return DealResearchPipeline(
        discovery=DealDiscoveryService(
            (FixtureDealDiscoveryProvider(data_root / "discovered_deals.json"),)
        ),
        document_catalog=FixtureDocumentCatalog(data_root / "document_catalog.json"),
        ingestor=DealDocumentIngestor(data_root),
        chunker=TransactionAwareChunker(),
        index=InMemoryDealIndex(embedder),
    )


def run_demo() -> dict[str, object]:
    context = AcquisitionContext(
        context_id="demo-b2b-fintech-infrastructure",
        target_industry="B2B fintech infrastructure",
        business_description="Payments, ledger, banking API, and compliance infrastructure",
        geographies=("United States", "United Kingdom"),
        announced_from=date(2020, 1, 1),
        announced_to=date(2025, 12, 31),
    )
    pipeline = build_fixture_pipeline()
    corpus = pipeline.build(context)
    retriever = HybridDealRetriever(pipeline.index)
    consideration = retriever.retrieve(
        "What was the disclosed consideration for the acquisition?",
        top_k=3,
        filters=RetrievalFilters(transaction_id="txn-cash"),
    )
    ambiguous = retriever.retrieve(
        "What was the announced transaction value?",
        top_k=5,
        filters=RetrievalFilters(transaction_id="txn-conflict"),
    )
    missing = retriever.retrieve(
        "What was the exact purchase price?",
        top_k=3,
        filters=RetrievalFilters(transaction_id="txn-undisclosed"),
    )
    benchmark = run_benchmark(
        retriever,
        load_benchmark(PROJECT_ROOT / "evaluation" / "retrieval_cases.json"),
    )
    return {
        "context": asdict(context),
        "discovery": {
            "raw_candidates": corpus.discovery.raw_candidate_count,
            "resolved_transactions": len(corpus.discovery.transactions),
            "transaction_ids": [item.candidate_id for item in corpus.discovery.transactions],
        },
        "documents": len(corpus.parsed_documents),
        "chunks": len(corpus.chunks),
        "index": asdict(corpus.indexing_report),
        "relevant_retrieval": _response(consideration),
        "ambiguous_retrieval": _response(ambiguous),
        "undisclosed_price_retrieval": _response(missing),
        "benchmark": asdict(benchmark),
        "warnings": list(corpus.warnings),
    }


def _response(response: RetrievalResponse) -> dict[str, object]:
    return {
        "query": response.query,
        "results": [
            {
                "rank": item.rank,
                "transaction_id": item.transaction_id,
                "document_id": item.evidence.document_id,
                "page": item.evidence.page,
                "section": item.evidence.section,
                "fused_score": round(item.fused_score, 4),
                "text": item.text,
            }
            for item in response.results
        ],
        "warnings": [item.code.value for item in response.warnings],
    }


def main() -> None:
    print(json.dumps(run_demo(), indent=2, default=str))


if __name__ == "__main__":
    main()
