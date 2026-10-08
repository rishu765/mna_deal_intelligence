from pathlib import Path

from conftest import ExtractionHarness
from ma_precedent_transactions.demo_m3 import run_demo
from ma_precedent_transactions.extraction import (
    load_extraction_benchmark,
    run_extraction_benchmark,
)


def test_m3_benchmark_reports_separate_perfect_fixture_metrics(
    extraction_harness: ExtractionHarness,
) -> None:
    cases = load_extraction_benchmark(
        Path(__file__).resolve().parents[1] / "evaluation" / "extraction_cases.json"
    )
    result = run_extraction_benchmark(extraction_harness.records, cases)
    assert result.case_count == 7
    assert result.field_accuracy == 1.0
    assert result.numeric_accuracy == 1.0
    assert result.missing_value_accuracy == 1.0
    assert result.evidence_link_accuracy == 1.0
    assert result.conflict_detection_accuracy == 1.0


def test_offline_demo_covers_required_cases_without_valuation_multiples() -> None:
    result = run_demo()
    transactions = result["transactions"]
    assert isinstance(transactions, dict)
    assert len(transactions) == 7
    assert transactions["txn-conflict"]["conflicts"] == ["valuation.headline_deal_value"]
    assert "valuation range" in str(result["scope_guard"])
