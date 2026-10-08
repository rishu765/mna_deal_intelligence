import json
from pathlib import Path

from ma_comparable_valuation.evaluation import EvaluationRunner, load_evaluation_dataset
from ma_comparable_valuation.evaluation.reporting import write_report

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evaluation" / "datasets" / "m06_cases.json"


def test_curated_dataset_covers_eight_required_scenarios() -> None:
    dataset = load_evaluation_dataset(DATASET)

    assert len(dataset.cases) == 8
    assert {item.case_id for item in dataset.cases} == {
        "profitable-software",
        "negative-ebitda",
        "industrial-debt",
        "mixed-basis",
        "stale-market",
        "incomplete-capital",
        "forward-estimates",
        "negative-earnings",
    }
    assert all(item.expected_behaviors for item in dataset.cases)


def test_evaluation_reports_each_subsystem_separately() -> None:
    report = EvaluationRunner(ROOT).run(load_evaluation_dataset(DATASET))

    assert report.passed is True
    assert {item.subsystem for item in report.subsystems} == {
        "target_financial_profile",
        "comparable_selection",
        "market_financial_ingestion",
        "trading_multiples",
        "peer_statistics",
        "implied_valuation",
        "ai_explanation",
    }
    assert all(item.pass_count > 0 and item.fail_count == 0 for item in report.subsystems)
    assert report.limitations


def test_evaluation_report_writes_machine_and_human_readable_outputs(
    tmp_path: Path,
) -> None:
    report = EvaluationRunner(ROOT).run(load_evaluation_dataset(DATASET))

    json_path, markdown_path = write_report(report, tmp_path)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert payload["passed"] is True
    assert payload["case_count"] == 8
    assert "production-grade validation" in " ".join(payload["limitations"])
    assert "| Subsystem | Result |" in markdown
    assert "Overall check status: PASS" in markdown


def test_invalid_dataset_fails_readably(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"schema_version": 1, "cases": []}', encoding="utf-8")

    try:
        load_evaluation_dataset(invalid)
    except ValueError as error:
        assert "requires cases" in str(error)
    else:
        raise AssertionError("invalid evaluation dataset should fail")
