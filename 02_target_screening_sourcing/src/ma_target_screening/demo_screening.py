"""Offline M1-to-M5 screening, strategic-fit, ranking, and shortlist demo."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from ma_target_screening.discovery import CandidateDiscoveryService, LocalDatasetDiscoveryProvider
from ma_target_screening.discovery.models import UserCandidateInput
from ma_target_screening.discovery.providers import UserSuppliedDiscoveryProvider
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

_DEMO_DOMAINS = (
    "payflow.example",
    "ledgerbridge.example",
    "cashgrid.example",
    "consumercredit.example",
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    thesis = AcquisitionThesis.from_json(args.thesis.read_text(encoding="utf-8"))
    discovery_provider = LocalDatasetDiscoveryProvider(args.discovery_data)
    discovered = CandidateDiscoveryService(providers=(discovery_provider,)).discover(thesis)
    by_domain = {item.website_domain: item for item in discovered.candidates}
    missing = tuple(domain for domain in _DEMO_DOMAINS if domain not in by_domain)
    if missing:
        supplied = tuple(
            UserCandidateInput(name=domain.split(".")[0], website=domain) for domain in missing
        )
        fallback = CandidateDiscoveryService(
            providers=(UserSuppliedDiscoveryProvider(supplied, "M4/5 demo longlist"),)
        ).discover(thesis)
        by_domain.update({item.website_domain: item for item in fallback.candidates})
    candidates = tuple(by_domain[domain] for domain in _DEMO_DOMAINS)
    enrichment = CandidateEnrichmentService(
        providers=(StructuredFixtureEnrichmentProvider(args.enrichment_data),)
    )
    profiles = tuple(enrichment.enrich(candidate, thesis) for candidate in candidates)
    service = ScreeningRankingService(
        strategic_fit_service=StrategicFitService(
            FixtureStrategicFitProvider(args.strategic_fit_data)
        )
    )
    shortlist = service.build_shortlist(thesis, profiles)
    print(json.dumps(shortlist.to_dict(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
