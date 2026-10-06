from __future__ import annotations

import json
from pathlib import Path

import pytest

from ma_target_screening.evaluation import EvaluationRunner, load_evaluation_dataset
from ma_target_screening.evaluation_cli import main as evaluation_main

ROOT = Path(__file__).parents[1]
DATASET = ROOT / "data" / "evaluation_cases.json"


def test_curated_dataset_contains_five_distinct_valid_theses() -> None:
    dataset = load_evaluation_dataset(DATASET, project_root=ROOT)

    assert len(dataset.cases) == 5
    assert len({case.case_id for case in dataset.cases}) == 5
    assert {case.thesis.thesis_id for case in dataset.cases} == {
        "india-payments-screening-demo",
        "enterprise-ai-data-capability",
        "india-enterprise-fintech-expansion",
        "partial-industrial-tech-thesis",
        "india-fintech-exclusion-heavy",
    }


def test_offline_evaluation_reports_separate_subsystem_metrics() -> None:
    dataset = load_evaluation_dataset(DATASET, project_root=ROOT)
    report = EvaluationRunner.offline(ROOT).run(dataset)
    subsystems = {item.subsystem: dict(item.metrics) for item in report.subsystems}

    assert set(subsystems) == {
        "thesis",
        "discovery",
        "enrichment",
        "screening",
        "strategic_fit",
        "ranking",
        "workflow",
    }
    assert subsystems["thesis"]["schema_validity"] == 1.0
    assert subsystems["discovery"]["recall"] == 1.0
    assert 0.0 < subsystems["discovery"]["precision"] < 1.0
    assert subsystems["enrichment"]["claim_evidence_support"] == 1.0
    assert subsystems["screening"]["unknown_handling_agreement"] == 1.0
    assert subsystems["strategic_fit"]["unsupported_known_claim_rate"] == 0.0
    assert subsystems["ranking"]["deterministic_stability"] == 1.0
    assert subsystems["workflow"]["final_state_accuracy"] == 1.0
    assert subsystems["workflow"]["scenario_count"] == 9.0
    assert report.limitations


def test_evaluation_report_is_json_serializable() -> None:
    dataset = load_evaluation_dataset(DATASET, project_root=ROOT)
    report = EvaluationRunner.offline(ROOT).run(dataset)

    restored = json.loads(json.dumps(report.to_dict()))

    assert restored["schema_version"] == 1
    assert restored["case_count"] == 5


def test_evaluation_cli_writes_reproducible_report(tmp_path: Path) -> None:
    output = tmp_path / "evaluation.json"

    assert evaluation_main(["--project-root", str(ROOT), "--output", str(output)]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))

    assert report["case_count"] == 5
    assert len(report["subsystems"]) == 7


def test_dataset_rejects_path_escape(tmp_path: Path) -> None:
    dataset = tmp_path / "cases.json"
    dataset.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cases": [
                    {
                        "case_id": "escape",
                        "description": "invalid path",
                        "thesis_file": "../outside.json",
                        "expected_requirements": {},
                        "relevant_domains": [],
                        "profile_expectations": {},
                        "screening_expectations": {},
                        "strategic_fit_expectations": {},
                        "expected_top_domains": [],
                        "expected_pairs": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="within the project"):
        load_evaluation_dataset(dataset, project_root=tmp_path)
