"""Run the credential-free Project 2 benchmark and print or save JSON."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from ma_target_screening.evaluation import EvaluationRunner, load_evaluation_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.project_root.resolve()
    dataset_path = args.dataset or root / "data" / "evaluation_cases.json"
    dataset = load_evaluation_dataset(dataset_path, project_root=root)
    report = EvaluationRunner.offline(root).run(dataset)
    rendered = json.dumps(report.to_dict(), indent=2, ensure_ascii=False)
    if args.output is None:
        print(rendered)
    else:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
