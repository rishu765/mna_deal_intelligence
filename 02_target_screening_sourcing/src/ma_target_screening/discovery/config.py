"""Environment-backed discovery limits with conservative defaults."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DiscoveryLimits:
    max_queries: int = 6
    max_candidates_per_query: int = 10
    overall_candidate_limit: int = 50

    def __post_init__(self) -> None:
        for field_name in (
            "max_queries",
            "max_candidates_per_query",
            "overall_candidate_limit",
        ):
            if getattr(self, field_name) < 1:
                raise ValueError(f"{field_name} must be positive")


@dataclass(frozen=True, slots=True)
class DiscoverySettings:
    limits: DiscoveryLimits = DiscoveryLimits()
    dataset_path: Path = Path("data/discovery_companies.json")

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> DiscoverySettings:
        try:
            limits = DiscoveryLimits(
                max_queries=int(env.get("MATS_DISCOVERY_MAX_QUERIES", "6")),
                max_candidates_per_query=int(
                    env.get("MATS_DISCOVERY_MAX_CANDIDATES_PER_QUERY", "10")
                ),
                overall_candidate_limit=int(
                    env.get("MATS_DISCOVERY_OVERALL_CANDIDATE_LIMIT", "50")
                ),
            )
        except ValueError as error:
            raise ValueError("MATS_DISCOVERY limit values must be integers") from error
        return cls(
            limits=limits,
            dataset_path=Path(
                env.get("MATS_DISCOVERY_DATASET_PATH", "data/discovery_companies.json")
            ),
        )
