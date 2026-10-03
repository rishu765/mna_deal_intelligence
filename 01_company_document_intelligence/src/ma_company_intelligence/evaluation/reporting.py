"""Machine-readable JSON and compact Markdown evaluation reports."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ma_company_intelligence.evaluation.models import EvaluationReport


def write_report(
    report: EvaluationReport,
    output_directory: Path,
    *,
    stem: str,
) -> tuple[Path, Path]:
    """Write reproducible JSON plus a human-reviewable Markdown summary."""

    if not stem.strip():
        raise ValueError("report stem must not be blank")
    output_directory.mkdir(parents=True, exist_ok=True)
    json_path = output_directory / f"{stem}.json"
    markdown_path = output_directory / f"{stem}.md"
    payload = asdict(report)
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def _markdown(report: EvaluationReport) -> str:
    aggregate = report.aggregate
    retrieval = _mapping(aggregate["retrieval"])
    generation = _mapping(aggregate["generation"])
    faithfulness = _mapping(aggregate["faithfulness"])
    citations = _mapping(aggregate["citations"])
    structured = _mapping(aggregate["structured_research"])
    lines = [
        f"# Evaluation baseline: {report.dataset_id} v{report.dataset_version}",
        "",
        "This report exposes component metrics separately; it intentionally has no "
        "composite score.",
        "",
        "## Retrieval",
        "",
    ]
    lines.extend(f"- `{key}`: {_format(value)}" for key, value in retrieval.items())
    lines.extend(("", "## Generation", ""))
    lines.extend(f"- `{key}`: {_format(value)}" for key, value in generation.items())
    lines.extend(("", "## Faithfulness", ""))
    lines.extend(f"- `{key}`: {_format(value)}" for key, value in faithfulness.items())
    lines.extend(("", "## Citations", ""))
    lines.extend(f"- `{key}`: {_format(value)}" for key, value in citations.items())
    lines.extend(("", "## Structured research", ""))
    lines.extend(f"- `{key}`: {_format(value)}" for key, value in structured.items())
    lines.extend(("", "## Failed cases", ""))
    failed = [case for case in report.cases if case.failures]
    if not failed:
        lines.append("No deterministic failures were classified.")
    for case in failed:
        labels = ", ".join(str(value) for value in case.failures)
        lines.append(f"- `{case.case_id}` ({case.category}): {labels}")
    lines.extend(("", "## Failure counts", ""))
    failure_counts = _mapping(aggregate["failure_counts"])
    lines.extend(f"- `{key}`: {value}" for key, value in failure_counts.items())
    lines.extend(
        (
            "",
            "## Judge status",
            "",
            f"```json\n{json.dumps(report.judge_status, indent=2)}\n```",
            "",
        )
    )
    return "\n".join(lines)


def _mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("expected report mapping")
    return value


def _format(value: Any) -> str:
    return f"{value:.4f}" if isinstance(value, float) else str(value)
