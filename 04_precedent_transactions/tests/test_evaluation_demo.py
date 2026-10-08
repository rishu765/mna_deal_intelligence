from conftest import PROJECT_ROOT, ResearchHarness
from ma_precedent_transactions.demo import run_demo
from ma_precedent_transactions.evaluation import load_benchmark, run_benchmark


def test_retrieval_benchmark_reports_interpretable_metrics(
    research_harness: ResearchHarness,
) -> None:
    result = run_benchmark(
        research_harness.retriever,
        load_benchmark(PROJECT_ROOT / "evaluation" / "retrieval_cases.json"),
    )

    assert result.case_count == 6
    assert result.hit_at_k == 1.0
    assert result.recall_at_k == 1.0
    assert result.mean_reciprocal_rank >= 0.8


def test_demo_covers_discovery_retrieval_and_ambiguous_case() -> None:
    result = run_demo()

    discovery = result["discovery"]
    assert isinstance(discovery, dict)
    assert discovery["raw_candidates"] == 8
    assert discovery["resolved_transactions"] == 7
    relevant = result["relevant_retrieval"]
    assert isinstance(relevant, dict)
    assert relevant["results"]
    ambiguous = result["ambiguous_retrieval"]
    assert isinstance(ambiguous, dict)
    assert "conflicting_passages" in ambiguous["warnings"]
    undisclosed = result["undisclosed_price_retrieval"]
    assert isinstance(undisclosed, dict)
    assert "not disclosed" in str(undisclosed["results"])
