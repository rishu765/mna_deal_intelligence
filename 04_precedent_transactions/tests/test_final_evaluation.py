from ma_precedent_transactions.demo_final import run_demo
from ma_precedent_transactions.evaluation_final import run_final_evaluation


def test_final_evaluation_reports_separate_metrics_and_ten_scenarios() -> None:
    report = run_final_evaluation()

    assert len(report.metrics) >= 9
    assert len(report.scenarios) == 10
    assert all(item.passed for item in report.metrics)
    assert all(item.passed for item in report.scenarios)
    assert any("Fixture-heavy" in item for item in report.limitations)


def test_final_demo_pauses_resumes_and_returns_audit_trace() -> None:
    demo = run_demo()
    paused = demo["paused"]
    resumed = demo["resumed"]

    assert isinstance(paused, dict) and paused["status"] == "awaiting_human_review"
    assert isinstance(resumed, dict) and resumed["status"] == "completed"
    result = resumed["result"]
    assert isinstance(result, dict)
    assert result["valuation_ranges"]
    assert result["trace"][-1]["node"] == "finalize"
