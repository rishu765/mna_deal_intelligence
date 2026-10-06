"""Offline M1-to-M6 workflow demo with a real interrupt and programmatic approval."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from ma_target_screening.discovery import CandidateDiscoveryService, LocalDatasetDiscoveryProvider
from ma_target_screening.enrichment import (
    CandidateEnrichmentService,
    StructuredFixtureEnrichmentProvider,
)
from ma_target_screening.screening import (
    FixtureStrategicFitProvider,
    ScreeningRankingService,
    StrategicFitService,
)
from ma_target_screening.thesis import AcquisitionThesis
from ma_target_screening.workflow import (
    HumanReviewDecision,
    ReviewDecision,
    WorkflowApplication,
    build_workflow,
)


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
    parser.add_argument("--thread-id", default="m6-offline-demo")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    thesis = AcquisitionThesis.from_json(args.thesis.read_text(encoding="utf-8"))
    graph = build_workflow(
        discovery=CandidateDiscoveryService(
            providers=(LocalDatasetDiscoveryProvider(args.discovery_data),)
        ),
        enrichment=CandidateEnrichmentService(
            providers=(StructuredFixtureEnrichmentProvider(args.enrichment_data),)
        ),
        screening=ScreeningRankingService(
            strategic_fit_service=StrategicFitService(
                FixtureStrategicFitProvider(args.strategic_fit_data)
            )
        ),
    )
    application = WorkflowApplication(graph)

    paused = application.start(thesis, thread_id=args.thread_id)
    review = {
        "status": paused["status"].value,
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
            reviewer_notes="Approved by the offline M6 demo.",
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
