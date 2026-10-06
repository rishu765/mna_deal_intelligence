"""Offline Project 2 V1 demo with a real interrupt and programmatic approval."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from ma_target_screening.composition import OfflinePaths, build_offline_services
from ma_target_screening.thesis import AcquisitionThesis
from ma_target_screening.workflow import HumanReviewDecision, ReviewDecision


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thesis", type=Path, default=Path("examples/screening-ranking-demo.json"))
    parser.add_argument(
        "--discovery-data", type=Path, default=Path("data/discovery_companies.json")
    )
    parser.add_argument(
        "--enrichment-data", type=Path, default=Path("data/enrichment_profiles.json")
    )
    parser.add_argument(
        "--strategic-fit-data",
        type=Path,
        default=Path("data/strategic_fit_assessments.json"),
    )
    parser.add_argument("--thread-id", default="project2-v1-offline-demo")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    thesis = AcquisitionThesis.from_json(args.thesis.read_text(encoding="utf-8"))
    services = build_offline_services(
        OfflinePaths(
            discovery_data=args.discovery_data,
            enrichment_data=args.enrichment_data,
            strategic_fit_data=args.strategic_fit_data,
        )
    )
    application = services.workflow

    paused = application.start(thesis, thread_id=args.thread_id)
    review = {
        "thesis": {
            "thesis_id": thesis.thesis_id,
            "acquirer": thesis.acquirer.name,
            "objective": thesis.objective,
            "criterion_count": len(thesis.criteria),
        },
        "status": paused["status"].value,
        "discovered_candidates": [item.canonical_name for item in paused.get("candidates", ())],
        "enrichment": [
            {
                "candidate": item.candidate.canonical_name,
                "status": item.status.value,
                "evidence_count": len(item.evidence),
                "unknown_count": len(item.unknown_fields),
            }
            for item in paused.get("profiles", ())
        ],
        "ranked_candidates": [
            {
                "rank": item.rank,
                "candidate": item.result.profile.candidate.canonical_name,
                "score": (
                    None
                    if item.result.scores.final_score is None
                    else str(item.result.scores.final_score)
                ),
                "eligibility": item.result.eligibility.value,
            }
            for item in paused["provisional_shortlist"].ranked_candidates
        ],
        "warnings": list(paused.get("warnings", ())),
    }
    print("HUMAN REVIEW CHECKPOINT")
    print(json.dumps(review, indent=2, ensure_ascii=False))

    completed = application.resume(
        thread_id=args.thread_id,
        decision=HumanReviewDecision(
            decision=ReviewDecision.APPROVE,
            reviewer_notes="Approved by the offline Project 2 V1 demo.",
            approved_candidates=("payflow.example", "ledgerbridge.example"),
        ),
    )
    result = completed["final_result"]
    output = {
        "status": result.status.value,
        "approved_candidates": [
            item.result.profile.candidate.canonical_name
            for item in result.final_shortlist.ranked_candidates
        ],
        "warnings": list(result.warnings),
        "trace": [
            {
                "node": event.node,
                "status": event.status.value,
                "retry_count": event.retry_count,
            }
            for event in result.trace
        ],
    }
    print("FINAL WORKFLOW RESULT")
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
