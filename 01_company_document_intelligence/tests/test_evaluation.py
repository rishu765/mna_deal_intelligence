"""Tests for deterministic evaluation metrics, reporting, and optional judging."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ma_company_intelligence.evaluation import EvaluationRunner, load_evaluation_dataset
from ma_company_intelligence.evaluation.errors import (
    EvaluationDatasetError,
    EvaluationJudgeError,
)
from ma_company_intelligence.evaluation.judge import OpenAIEvaluationJudge
from ma_company_intelligence.evaluation.metrics import (
    evaluate_answer,
    evaluate_citations,
    evaluate_retrieval,
)
from ma_company_intelligence.evaluation.reporting import write_report
from ma_company_intelligence.evaluation_cli import main as evaluation_cli_main

DATASET_PATH = Path(__file__).parents[1] / "evaluation" / "datasets" / "synthetic_company_v1.json"


@pytest.fixture
def dataset():  # type: ignore[no-untyped-def]
    return load_evaluation_dataset(DATASET_PATH)


def _case(dataset: Any, case_id: str) -> Any:
    return next(case for case in dataset.cases if case.case_id == case_id)


def test_dataset_is_versioned_diverse_and_copyright_safe(dataset: Any) -> None:
    assert dataset.dataset_id == "synthetic_apex_company_research"
    assert dataset.version == "1.0.0"
    assert len(dataset.cases) == 14
    assert len({case.category for case in dataset.cases}) >= 12
    assert any(case.should_be_insufficient for case in dataset.cases)
    assert all(record.source_filename.startswith("apex-") for record in dataset.evidence)


def test_malformed_dataset_fails_with_application_error(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text('{"dataset_id": "broken"}', encoding="utf-8")

    with pytest.raises(EvaluationDatasetError, match="invalid evaluation dataset"):
        load_evaluation_dataset(path)


def test_retrieval_metrics_capture_rank_recall_and_multiple_evidence(dataset: Any) -> None:
    evidence = dataset.evidence_by_chunk_id
    geography = evaluate_retrieval(_case(dataset, "geography-01"), evidence, (1, 3, 5))
    multi = evaluate_retrieval(_case(dataset, "multi-financial-01"), evidence, (1, 3, 5))

    assert geography.first_relevant_rank == 4
    assert geography.reciprocal_rank == 0.25
    assert geography.hit_at == {1: 0.0, 3: 0.0, 5: 1.0}
    assert multi.hit_at[1] == 1.0
    assert multi.recall_at[5] == 0.5


def test_unanswerable_retrieval_is_measured_separately(dataset: Any) -> None:
    result = evaluate_retrieval(
        _case(dataset, "unanswerable-01"),
        dataset.evidence_by_chunk_id,
        (1, 3, 5),
    )

    assert result.unanswerable_no_result == 0.0
    assert result.first_relevant_rank is None


def test_duplicate_retrievals_do_not_inflate_recall(dataset: Any) -> None:
    case = _case(dataset, "multi-financial-01")
    duplicated = replace(
        case,
        observation=replace(
            case.observation,
            retrieved_chunk_ids=("c05-revenue", "c05-revenue"),
        ),
    )

    result = evaluate_retrieval(
        duplicated,
        dataset.evidence_by_chunk_id,
        (1, 3),
    )

    assert result.hit_at[1] == 1.0
    assert result.recall_at[3] == 0.5


def test_correctness_and_faithfulness_are_independent(dataset: Any) -> None:
    case = _case(dataset, "growth-01")
    result = evaluate_answer(
        case,
        case.observation.retrieved_context_answer,
        case.observation.context_chunk_ids,
        dataset.evidence_by_chunk_id,
    )

    assert result.expected_fact_recall == 1.0
    assert result.claim_faithfulness == 0.0


def test_citation_metrics_detect_fabricated_pages_and_irrelevant_sources(dataset: Any) -> None:
    evidence = dataset.evidence_by_chunk_id
    products = _case(dataset, "products-01")
    strategy = _case(dataset, "strategy-01")

    fabricated = evaluate_citations(
        products.observation.retrieved_context_answer,
        products.observation.retrieved_chunk_ids,
        evidence,
    )
    irrelevant = evaluate_citations(
        strategy.observation.retrieved_context_answer,
        strategy.observation.retrieved_chunk_ids,
        evidence,
    )

    assert fabricated.validity == 0.0
    assert fabricated.support_precision == 0.0
    assert irrelevant.validity == 1.0
    assert irrelevant.support_precision == 0.5


def test_duplicate_citation_records_do_not_change_scores(dataset: Any) -> None:
    case = _case(dataset, "revenue-01")
    answer = case.observation.retrieved_context_answer
    duplicated = replace(answer, citations=answer.citations + answer.citations)

    result = evaluate_citations(
        duplicated,
        case.observation.retrieved_chunk_ids,
        dataset.evidence_by_chunk_id,
    )

    assert result.validity == 1.0
    assert result.support_precision == 1.0
    assert result.claim_coverage == 1.0


def test_runner_reports_gold_context_gap_and_no_composite_score(dataset: Any) -> None:
    report = EvaluationRunner().run(dataset)
    geography = next(case for case in report.cases if case.case_id == "geography-01")

    assert geography.correctness_gap == 1.0
    assert report.aggregate["retrieval"]["hit_at_5"] == pytest.approx(12 / 13)
    assert report.aggregate["generation"]["gold_context_correctness_gap"] > 0.0
    assert "overall_score" not in report.aggregate
    assert report.judge_status["enabled"] is False


def test_structured_metrics_surface_omissions_qualifiers_and_unsafe_population(
    dataset: Any,
) -> None:
    report = EvaluationRunner().run(dataset)
    complete, limited = report.structured_cases

    assert complete.supported_section_population < 1.0
    assert complete.financial_field_accuracy < 1.0
    assert complete.fact_analysis_separation < 1.0
    assert limited.unsupported_section_abstention == 0.5
    assert report.aggregate["structured_research"]["citation_retention"] < 1.0


def test_reporter_writes_machine_and_human_readable_results(dataset: Any, tmp_path: Path) -> None:
    report = EvaluationRunner().run(dataset)

    json_path, markdown_path = write_report(report, tmp_path, stem="baseline")

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert payload["dataset_id"] == dataset.dataset_id
    assert "## Retrieval" in markdown
    assert "## Failed cases" in markdown
    assert "composite score" in markdown


class _MalformedResponses:
    def parse(self, **_arguments: Any) -> SimpleNamespace:
        return SimpleNamespace(output_parsed=None)


class _ValidResponses:
    def parse(self, **arguments: Any) -> SimpleNamespace:
        output_type = arguments["text_format"]
        return SimpleNamespace(
            output_parsed=output_type(
                correctness=0.75,
                faithfulness=0.5,
                citation_support=0.25,
                reason="One fact is supported and one citation is weak.",
            )
        )


def test_optional_judge_is_skipped_without_credentials() -> None:
    assert OpenAIEvaluationJudge.from_environment({}) is None


def test_judge_malformed_response_fails_safely(dataset: Any) -> None:
    judge = OpenAIEvaluationJudge(
        api_key="test-key",
        client=SimpleNamespace(responses=_MalformedResponses()),
    )

    with pytest.raises(EvaluationJudgeError, match="no valid structured output"):
        judge.assess(dataset.cases[0], dataset.evidence_by_chunk_id)


def test_structured_judge_output_is_provider_neutral(dataset: Any) -> None:
    judge = OpenAIEvaluationJudge(
        api_key="test-key",
        model="judge-test-model",
        client=SimpleNamespace(responses=_ValidResponses()),
    )

    result = judge.assess(dataset.cases[0], dataset.evidence_by_chunk_id)

    assert result.correctness == 0.75
    assert result.faithfulness == 0.5
    assert result.citation_support == 0.25
    assert judge.model_name == "judge-test-model"


def test_cli_completes_deterministically_and_skips_requested_judge_without_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    exit_code = evaluation_cli_main(
        [
            "--dataset",
            str(DATASET_PATH),
            "--output-dir",
            str(tmp_path),
            "--report-stem",
            "test-baseline",
            "--llm-judge",
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["judge_status"]["enabled"] is False
    assert "judge_warning" in output
    assert (tmp_path / "test-baseline.json").is_file()
    assert (tmp_path / "test-baseline.md").is_file()
