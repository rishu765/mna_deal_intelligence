"""Credential-free candidate discovery demo using the bundled synthetic dataset."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from ma_target_screening.discovery import (
    CandidateDiscoveryService,
    DiscoveryLimits,
    LocalDatasetDiscoveryProvider,
)
from ma_target_screening.thesis import AcquisitionThesis


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thesis", type=Path, default=Path("examples/fintech-payments.json"))
    parser.add_argument("--dataset", type=Path, default=Path("data/discovery_companies.json"))
    parser.add_argument("--max-queries", type=int, default=6)
    parser.add_argument("--max-candidates", type=int, default=20)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    thesis = AcquisitionThesis.from_json(args.thesis.read_text(encoding="utf-8"))
    service = CandidateDiscoveryService(
        providers=(LocalDatasetDiscoveryProvider(args.dataset),),
        limits=DiscoveryLimits(
            max_queries=args.max_queries,
            max_candidates_per_query=args.max_candidates,
            overall_candidate_limit=args.max_candidates,
        ),
    )
    result = service.discover(thesis)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
