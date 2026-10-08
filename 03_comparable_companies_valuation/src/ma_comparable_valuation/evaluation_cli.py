"""Run and persist the Project 3 offline subsystem evaluation."""

from __future__ import annotations

import argparse
from pathlib import Path

from ma_comparable_valuation.evaluation import EvaluationRunner, load_evaluation_dataset
from ma_comparable_valuation.evaluation.reporting import write_report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    root = args.project_root.resolve()
    dataset = load_evaluation_dataset(root / "evaluation" / "datasets" / "m06_cases.json")
    report = EvaluationRunner(root).run(dataset)
    output = args.output_dir or root / "evaluation" / "baselines"
    json_path, markdown_path = write_report(report, output)
    print(f"Evaluation {'PASS' if report.passed else 'FAIL'}")
    print(json_path)
    print(markdown_path)
    if not report.passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
