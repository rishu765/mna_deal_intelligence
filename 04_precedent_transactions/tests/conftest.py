from dataclasses import dataclass
from pathlib import Path

import pytest

from ma_precedent_transactions.demo import build_fixture_pipeline
from ma_precedent_transactions.discovery import AcquisitionContext
from ma_precedent_transactions.extraction import (
    FixtureStructuredExtractor,
    StructuredTransactionService,
    VerifiedTransactionRecord,
    retrieve_extraction_context,
)
from ma_precedent_transactions.pipeline import DealResearchCorpus, DealResearchPipeline
from ma_precedent_transactions.retrieval import HybridDealRetriever

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = PROJECT_ROOT / "data" / "fixtures"


@dataclass(frozen=True, slots=True)
class ResearchHarness:
    pipeline: DealResearchPipeline
    corpus: DealResearchCorpus
    retriever: HybridDealRetriever


@dataclass(frozen=True, slots=True)
class ExtractionHarness:
    research: ResearchHarness
    records: dict[str, VerifiedTransactionRecord]


@pytest.fixture
def research_harness() -> ResearchHarness:
    pipeline = build_fixture_pipeline()
    corpus = pipeline.build(
        AcquisitionContext(
            context_id="test-fintech",
            target_industry="B2B fintech infrastructure",
            business_description="Payments ledger banking API compliance infrastructure",
            geographies=("United States", "United Kingdom"),
        )
    )
    return ResearchHarness(pipeline, corpus, HybridDealRetriever(pipeline.index))


@pytest.fixture
def extraction_harness(research_harness: ResearchHarness) -> ExtractionHarness:
    service = StructuredTransactionService(
        FixtureStructuredExtractor(FIXTURE_ROOT / "extraction_responses.json")
    )
    records = {}
    for candidate in research_harness.corpus.discovery.transactions:
        context = retrieve_extraction_context(research_harness.retriever, candidate.candidate_id)
        records[candidate.candidate_id] = service.build(candidate, context)
    return ExtractionHarness(research_harness, records)
