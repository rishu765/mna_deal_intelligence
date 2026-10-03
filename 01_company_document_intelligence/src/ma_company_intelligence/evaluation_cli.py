"""Developer command for reproducible Project 1 quality evaluation."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from ma_company_intelligence.evaluation import (
    EvaluationRunner,
    OpenAIEvaluationJudge,
    load_evaluation_dataset,
)
from ma_company_intelligence.evaluation.errors import EvaluationError
from ma_company_intelligence.evaluation.reporting import write_report

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = PROJECT_ROOT / "evaluation" / "datasets" / "synthetic_company_v1.json"
DEFAULT_OUTPUT_DIRECTORY = PROJECT_ROOT / "artifacts" / "evaluation"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="madi-evaluate",
        description="Run deterministic component-level RAG and research evaluation.",
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--report-stem", default="m08-evaluation")
    parser.add_argument("--top-k", default="1,3,5", help="Comma-separated positive ranks")
    parser.add_argument(
        "--llm-judge",
        action="store_true",
        help="Optionally add OpenAI judge assessments when OPENAI_API_KEY is available",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    try:
        top_k = tuple(int(value.strip()) for value in arguments.top_k.split(","))
        judge = OpenAIEvaluationJudge.from_environment() if arguments.llm_judge else None
        dataset = load_evaluation_dataset(arguments.dataset)
        report = EvaluationRunner(top_k_values=top_k, judge=judge).run(dataset)
        json_path, markdown_path = write_report(
            report,
            arguments.output_dir,
            stem=arguments.report_stem,
        )
    except (EvaluationError, OSError, TypeError, ValueError) as error:
        parser.exit(status=2, message=f"error: {error}\n")

    summary = {
        "dataset_id": report.dataset_id,
        "dataset_version": report.dataset_version,
        "aggregate": report.aggregate,
        "judge_status": report.judge_status,
        "json_report": str(json_path.resolve()),
        "markdown_report": str(markdown_path.resolve()),
    }
    if arguments.llm_judge and judge is None:
        summary["judge_warning"] = (
            "LLM judge requested but OPENAI_API_KEY was absent; deterministic evaluation "
            "completed and judge evaluation was skipped."
        )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
