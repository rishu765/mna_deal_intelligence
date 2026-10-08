from __future__ import annotations

from datetime import date

import pytest

from conftest import ResearchHarness
from ma_precedent_transactions.documents import DealSourceType, DocumentFormat
from ma_precedent_transactions.errors import IndexingError
from ma_precedent_transactions.retrieval import (
    HashingEmbeddingProvider,
    InMemoryDealIndex,
    RetrievalFilters,
    RetrievalWarningCode,
)


def test_index_contains_every_unique_fixture_chunk(research_harness: ResearchHarness) -> None:
    assert research_harness.pipeline.index.count == len(research_harness.corpus.chunks)
    assert research_harness.corpus.indexing_report.duplicate_chunks == 0


def test_duplicate_chunk_indexing_is_idempotent(research_harness: ResearchHarness) -> None:
    chunk = research_harness.corpus.chunks[0]

    report = research_harness.pipeline.index.index((chunk, chunk))

    assert report.chunks_indexed == 0
    assert report.duplicate_chunks == 2


def test_semantic_retrieval_finds_ownership_passage(research_harness: ResearchHarness) -> None:
    matches = research_harness.pipeline.index.semantic_search(
        "ownership stake purchased",
        filters=RetrievalFilters(transaction_id="txn-partial"),
    )

    assert matches[0].chunk.transaction_id == "txn-partial"
    assert "20 percent" in matches[0].chunk.text
    assert matches[0].score > 0


def test_lexical_retrieval_finds_exact_financial_term(research_harness: ResearchHarness) -> None:
    matches = research_harness.pipeline.index.lexical_search(
        "adjusted EBITDA",
        filters=RetrievalFilters(transaction_id="txn-cash"),
    )

    assert "adjusted EBITDA" in matches[0].chunk.text
    assert matches[0].score > 0


def test_hybrid_retrieval_ranks_cash_consideration_first(
    research_harness: ResearchHarness,
) -> None:
    response = research_harness.retriever.retrieve(
        "What cash consideration was paid?",
        filters=RetrievalFilters(transaction_id="txn-cash"),
    )

    assert response.results[0].transaction_id == "txn-cash"
    assert "USD 420 million in cash" in response.results[0].text
    assert response.results[0].semantic_score > 0
    assert response.results[0].lexical_score > 0


def test_semantic_channel_can_return_evidence_when_lexical_channel_has_no_term(
    research_harness: ResearchHarness,
) -> None:
    response = research_harness.retriever.retrieve(
        "bought",
        filters=RetrievalFilters(transaction_id="txn-cash"),
    )

    assert response.results
    assert response.results[0].semantic_score > 0
    assert RetrievalWarningCode.NO_LEXICAL_RESULTS in {item.code for item in response.warnings}


def test_metadata_filters_prevent_cross_transaction_retrieval(
    research_harness: ResearchHarness,
) -> None:
    response = research_harness.retriever.retrieve(
        "transaction value cash stock ownership",
        top_k=10,
        filters=RetrievalFilters(
            transaction_id="txn-stock",
            source_types=(DealSourceType.ACQUISITION_PRESS_RELEASE,),
            document_formats=(DocumentFormat.TEXT,),
            acquirer="Meridian",
            target="BridgeMint",
            jurisdiction="United Kingdom",
        ),
    )

    assert response.results
    assert {item.transaction_id for item in response.results} == {"txn-stock"}


def test_publication_date_filter_excludes_out_of_window_documents(
    research_harness: ResearchHarness,
) -> None:
    response = research_harness.retriever.retrieve(
        "transaction value",
        filters=RetrievalFilters(
            transaction_id="txn-stock",
            published_from=date(2024, 1, 1),
        ),
    )

    assert response.results == ()
    assert RetrievalWarningCode.NO_RESULTS in {item.code for item in response.warnings}


def test_provenance_is_preserved_in_retrieval_result(
    research_harness: ResearchHarness,
) -> None:
    result = research_harness.retriever.retrieve(
        "offer price per share",
        filters=RetrievalFilters(transaction_id="txn-cash"),
    ).results[0]

    assert result.evidence.document_id == "doc-cash-filing"
    assert result.evidence.chunk_id == result.chunk_id
    assert result.evidence.page == 1
    assert result.evidence.section == "Offer terms"
    assert result.evidence.publisher == "Synthetic Securities Commission"


def test_no_result_and_missing_channel_warnings_are_explicit(
    research_harness: ResearchHarness,
) -> None:
    response = research_harness.retriever.retrieve(
        "nonexistent quantum banana term",
        filters=RetrievalFilters(transaction_id="does-not-exist"),
    )
    codes = {item.code for item in response.warnings}

    assert response.results == ()
    assert RetrievalWarningCode.NO_RESULTS in codes
    assert RetrievalWarningCode.NO_SEMANTIC_RESULTS in codes
    assert RetrievalWarningCode.NO_LEXICAL_RESULTS in codes


def test_conflicting_source_values_surface_warning(research_harness: ResearchHarness) -> None:
    response = research_harness.retriever.retrieve(
        "What was the announced transaction value?",
        top_k=5,
        filters=RetrievalFilters(transaction_id="txn-conflict"),
    )

    assert all(
        any(phrase in result.text for result in response.results)
        for phrase in ("USD 600 million", "USD 640 million")
    )
    assert RetrievalWarningCode.CONFLICTING_PASSAGES in {item.code for item in response.warnings}


def test_normal_cash_retrieval_does_not_false_flag_conflict(
    research_harness: ResearchHarness,
) -> None:
    response = research_harness.retriever.retrieve(
        "What was the disclosed consideration?",
        filters=RetrievalFilters(transaction_id="txn-cash"),
    )

    assert RetrievalWarningCode.CONFLICTING_PASSAGES not in {
        item.code for item in response.warnings
    }


def test_retrieval_across_transactions_returns_multiple_deals(
    research_harness: ResearchHarness,
) -> None:
    response = research_harness.retriever.retrieve("cash acquisition transaction value", top_k=6)

    assert len({item.transaction_id for item in response.results}) >= 2


def test_embedding_failure_does_not_partially_mutate_index(
    research_harness: ResearchHarness,
) -> None:
    class BrokenEmbedder:
        provider_name = "broken"
        model_name = "broken-v1"
        dimension = 32

        def embed(self, text: str) -> tuple[float, ...]:
            del text
            return (1.0,)

    index = InMemoryDealIndex(BrokenEmbedder())

    with pytest.raises(IndexingError, match="wrong dimension"):
        index.index((research_harness.corpus.chunks[0],))
    assert index.count == 0


def test_default_embedder_is_reproducible() -> None:
    embedder = HashingEmbeddingProvider()
    assert embedder.embed("cash consideration") == embedder.embed("cash consideration")
