"""Offline M2 candidate to M3 evidence-backed profile demo."""

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
from ma_target_screening.thesis import AcquisitionThesis


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thesis", type=Path, default=Path("examples/fintech-payments.json"))
    parser.add_argument(
        "--discovery-data", type=Path, default=Path("data/discovery_companies.json")
    )
    parser.add_argument(
        "--enrichment-data", type=Path, default=Path("data/enrichment_profiles.json")
    )
    parser.add_argument("--domain", default="payflow.example")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    thesis = AcquisitionThesis.from_json(args.thesis.read_text(encoding="utf-8"))
    discovery = CandidateDiscoveryService(
        providers=(LocalDatasetDiscoveryProvider(args.discovery_data),)
    ).discover(thesis)
    candidate = next(
        (item for item in discovery.candidates if item.website_domain == args.domain), None
    )
    if candidate is None:
        raise ValueError(f"demo candidate domain was not discovered: {args.domain}")
    profile = CandidateEnrichmentService(
        providers=(StructuredFixtureEnrichmentProvider(args.enrichment_data),)
    ).enrich(candidate, thesis)
    print(json.dumps(profile.to_dict(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
