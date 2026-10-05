"""Provider-neutral value objects that establish the Project 2 boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")


def _require_unique_nonblank(values: tuple[str, ...], field_name: str) -> None:
    if any(not value.strip() for value in values):
        raise ValueError(f"{field_name} must not contain blank values")
    if len({value.casefold() for value in values}) != len(values):
        raise ValueError(f"{field_name} must not contain duplicates")


@dataclass(frozen=True, slots=True)
class AcquisitionThesis:
    """Human-authored M0 thesis envelope; parsing and full criteria belong to M1."""

    acquirer_name: str
    strategic_objective: str
    industries: tuple[str, ...] = ()
    capabilities_sought: tuple[str, ...] = ()
    geographies: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.acquirer_name, "acquirer_name")
        _require_text(self.strategic_objective, "strategic_objective")
        for name in ("industries", "capabilities_sought", "geographies", "exclusions"):
            _require_unique_nonblank(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class ExternalIdentifier:
    """Identifier assigned by a registry, database, or source system."""

    scheme: str
    value: str

    def __post_init__(self) -> None:
        _require_text(self.scheme, "identifier scheme")
        _require_text(self.value, "identifier value")


@dataclass(frozen=True, slots=True)
class DiscoveryEvidence:
    """Traceable source observation supporting a discovered candidate."""

    source_type: str
    source_name: str
    source_uri: str | None = None
    observed_at: datetime | None = None
    excerpt: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.source_type, "source_type")
        _require_text(self.source_name, "source_name")
        if self.source_uri is not None:
            _require_text(self.source_uri, "source_uri")
            parsed = urlparse(self.source_uri)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("source_uri must be an absolute HTTP(S) URL")
        if self.observed_at is not None:
            if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
                raise ValueError("observed_at must be timezone-aware")
            if self.observed_at > datetime.now(UTC):
                raise ValueError("observed_at must not be in the future")
        if self.excerpt is not None:
            _require_text(self.excerpt, "excerpt")


@dataclass(frozen=True, slots=True)
class CandidateCompany:
    """Normalized candidate identity with discovery provenance, not an enriched profile."""

    canonical_name: str
    aliases: tuple[str, ...] = ()
    website_domain: str | None = None
    country: str | None = None
    identifiers: tuple[ExternalIdentifier, ...] = ()
    discovery_evidence: tuple[DiscoveryEvidence, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.canonical_name, "canonical_name")
        _require_unique_nonblank(self.aliases, "aliases")
        if self.website_domain is not None:
            _require_text(self.website_domain, "website_domain")
            if "://" in self.website_domain or "/" in self.website_domain:
                raise ValueError("website_domain must be a bare domain")
        if self.country is not None:
            _require_text(self.country, "country")
        identifier_keys = {
            (item.scheme.casefold(), item.value.casefold()) for item in self.identifiers
        }
        if len(identifier_keys) != len(self.identifiers):
            raise ValueError("identifiers must not contain duplicates")


@dataclass(frozen=True, slots=True)
class CandidateProfile:
    """Boundary result for later evidence-backed enrichment; M3 will evolve its fields."""

    candidate: CandidateCompany
    summary: str | None
    evidence: tuple[DiscoveryEvidence, ...]
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.summary is not None:
            _require_text(self.summary, "summary")
        _require_unique_nonblank(self.warnings, "warnings")
