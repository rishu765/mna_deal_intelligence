"""Write concise JSON and Markdown evaluation reports."""

from __future__ import annotations

import json
from pathlib import Path

from ma_comparable_valuation.evaluation.models import EvaluationReport


def write_report(report: EvaluationReport, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "m06_offline_report.json"
    markdown_path = output_dir / "m06_offline_report.md"
    json_path.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def _markdown(report: EvaluationReport) -> str:
    lines = [
        f"# Project 3 M6 evaluation: {report.dataset_id}",
        "",
        f"- Generated: {report.generated_at}",
        f"- Curated cases: {report.case_count}",
        f"- Overall check status: {'PASS' if report.passed else 'FAIL'}",
        "",
        "| Subsystem | Result | Passed | Failed | Representative failure | Limitation |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for subsystem in report.subsystems:
        failures = [
            item.representative_failure
            for item in subsystem.checks
            if item.representative_failure is not None
        ]
        lines.append(
            "| "
            + " | ".join(
                (
                    subsystem.subsystem,
                    "PASS" if subsystem.passed else "FAIL",
                    str(subsystem.pass_count),
                    str(subsystem.fail_count),
                    (failures[0] if failures else "None in fixture baseline").replace("|", "/"),
                    subsystem.limitation.replace("|", "/"),
                )
            )
            + " |"
        )
    lines.extend(("", "## Limitations", ""))
    lines.extend(f"- {item}" for item in report.limitations)
    lines.append("")
    return "\n".join(lines)
