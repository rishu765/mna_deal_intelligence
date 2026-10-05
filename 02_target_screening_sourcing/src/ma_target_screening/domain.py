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
class ExternalIdentifier:
    """Identifier assigned by a registry, database, or source system."""

    scheme: str
    value: str

    def __post_init__(self) -> None:
        _require_text(self.scheme, "identifier scheme")
        _require_text(self.value, "identifier value")


@dataclass(frozen=True, slots=True)
class DiscoveryEvidence:
    """Traceable, discovery-grade source observation supporting a candidate."""

    source_type: str
    source_name: str
    provider_name: str
    source_uri: str | None = None
    source_title: str | None = None
    source_identifier: str | None = None
    discovery_query: str | None = None
    observed_at: datetime | None = None
    excerpt: str | None = None
    raw_metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.source_type, "source_type")
        _require_text(self.source_name, "source_name")
        _require_text(self.provider_name, "provider_name")
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
        for field_name in ("source_title", "source_identifier", "discovery_query"):
            value = getattr(self, field_name)
            if value is not None:
                _require_text(value, field_name)
        metadata_keys = [key.casefold() for key, _ in self.raw_metadata]
        if any(not key.strip() or not value.strip() for key, value in self.raw_metadata):
            raise ValueError("raw_metadata keys and values must not be blank")
        if len(set(metadata_keys)) != len(metadata_keys):
            raise ValueError("raw_metadata keys must be unique")


@dataclass(frozen=True, slots=True)
class CandidateCompany:
    """Normalized discovery identity; fields are observed, not verified facts."""

    canonical_name: str
    aliases: tuple[str, ...] = ()
    website_domain: str | None = None
    country: str | None = None
    industry_tags: tuple[str, ...] = ()
    description: str | None = None
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
        _require_unique_nonblank(self.industry_tags, "industry_tags")
        if self.description is not None:
            _require_text(self.description, "description")
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
