"""Provider-neutral candidate discovery request and result models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ma_target_screening.domain import CandidateCompany


def _require_text(value: str, field_name: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    return normalized


def _optional_text(value: str | None, field_name: str) -> str | None:
    return None if value is None else _require_text(value, field_name)


@dataclass(frozen=True, slots=True)
class DiscoveryQuery:
    query_id: str
    text: str
    dimensions: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "query_id", _require_text(self.query_id, "query_id"))
        object.__setattr__(self, "text", _require_text(self.text, "query text"))
        if not self.dimensions:
            raise ValueError("discovery query must identify at least one thesis dimension")
        normalized = tuple(_require_text(item, "query dimension") for item in self.dimensions)
        if len(set(normalized)) != len(normalized):
            raise ValueError("query dimensions must be unique")
        object.__setattr__(self, "dimensions", normalized)


@dataclass(frozen=True, slots=True)
class DiscoveryRequest:
    thesis_id: str
    queries: tuple[DiscoveryQuery, ...]
    max_candidates_per_query: int
    overall_candidate_limit: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "thesis_id", _require_text(self.thesis_id, "thesis_id"))
        if self.max_candidates_per_query < 1:
            raise ValueError("max_candidates_per_query must be positive")
        if self.overall_candidate_limit < 1:
            raise ValueError("overall_candidate_limit must be positive")


@dataclass(frozen=True, slots=True)
class DiscoveredCompanyRecord:
    """One unverified provider observation before identity normalization."""

    observed_name: str
    provider_name: str
    source_name: str
    source_type: str
    website: str | None = None
    aliases: tuple[str, ...] = ()
    country: str | None = None
    industry_tags: tuple[str, ...] = ()
    description: str | None = None
    source_uri: str | None = None
    source_title: str | None = None
    source_identifier: str | None = None
    discovery_query: str | None = None
    observed_at: datetime | None = None
    raw_metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("observed_name", "provider_name", "source_name", "source_type"):
            object.__setattr__(
                self, field_name, _require_text(getattr(self, field_name), field_name)
            )
        for field_name in (
            "website",
            "country",
            "description",
            "source_uri",
            "source_title",
            "source_identifier",
            "discovery_query",
        ):
            object.__setattr__(
                self, field_name, _optional_text(getattr(self, field_name), field_name)
            )
        for field_name in ("aliases", "industry_tags"):
            values = tuple(_require_text(value, field_name) for value in getattr(self, field_name))
            if len({value.casefold() for value in values}) != len(values):
                raise ValueError(f"{field_name} must not contain duplicates")
            object.__setattr__(self, field_name, values)


@dataclass(frozen=True, slots=True)
class ProviderDiscoveryResult:
    provider_name: str
    candidates: tuple[DiscoveredCompanyRecord, ...]
    queries_executed: tuple[DiscoveryQuery, ...]
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "provider_name", _require_text(self.provider_name, "provider_name")
        )
        if any(item.provider_name != self.provider_name for item in self.candidates):
            raise ValueError("provider result candidates must use the result provider_name")


@dataclass(frozen=True, slots=True)
class CandidateDiscoveryResult:
    thesis_id: str
    queries: tuple[DiscoveryQuery, ...]
    candidates: tuple[CandidateCompany, ...]
    provider_names: tuple[str, ...]
    warnings: tuple[str, ...]
    raw_candidate_count: int
    deduplicated_candidate_count: int

    def __post_init__(self) -> None:
        if self.raw_candidate_count < self.deduplicated_candidate_count:
            raise ValueError("raw candidate count cannot be below deduplicated count")
        if self.deduplicated_candidate_count != len(self.candidates):
            raise ValueError("deduplicated count must equal candidate count")

    def to_dict(self) -> dict[str, Any]:
        return {
            "thesis_id": self.thesis_id,
            "queries": [query.text for query in self.queries],
            "provider_names": list(self.provider_names),
            "raw_candidate_count": self.raw_candidate_count,
            "deduplicated_candidate_count": self.deduplicated_candidate_count,
            "warnings": list(self.warnings),
            "candidates": [
                {
                    "canonical_name": candidate.canonical_name,
                    "aliases": list(candidate.aliases),
                    "website_domain": candidate.website_domain,
                    "country": candidate.country,
                    "industry_tags": list(candidate.industry_tags),
                    "description": candidate.description,
                    "discovery_evidence": [
                        {
                            "provider_name": evidence.provider_name,
                            "source_type": evidence.source_type,
                            "source_name": evidence.source_name,
                            "source_uri": evidence.source_uri,
                            "source_title": evidence.source_title,
                            "source_identifier": evidence.source_identifier,
                            "discovery_query": evidence.discovery_query,
                            "excerpt": evidence.excerpt,
                        }
                        for evidence in candidate.discovery_evidence
                    ],
                }
                for candidate in self.candidates
            ],
        }


@dataclass(frozen=True, slots=True)
class UserCandidateInput:
    name: str
    website: str | None = None
    aliases: tuple[str, ...] = ()
    country: str | None = None
    industry_tags: tuple[str, ...] = ()
    description: str | None = None
    source_reference: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _require_text(self.name, "candidate name"))
        for field_name in ("website", "country", "description", "source_reference"):
            object.__setattr__(
                self, field_name, _optional_text(getattr(self, field_name), field_name)
            )
