"""Structural adapter from Project 2 public candidate outputs into Project 3 identities."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ma_comparable_valuation.domain import (
    CompanyIdentity,
    ComparableCompany,
    EvidenceReference,
    TargetCompany,
)


class Project2Identifier(Protocol):
    scheme: str
    value: str


class Project2DiscoveryEvidence(Protocol):
    source_type: str
    source_name: str
    provider_name: str
    source_uri: str | None
    source_title: str | None
    observed_at: datetime | None
    excerpt: str | None


class Project2Candidate(Protocol):
    canonical_name: str
    website_domain: str | None
    country: str | None
    industry_tags: tuple[str, ...]
    description: str | None
    identifiers: tuple[Project2Identifier, ...]
    discovery_evidence: tuple[Project2DiscoveryEvidence, ...]


class Project2Field(Protocol):
    value: str


class Project2ProfileEvidence(Protocol):
    evidence_id: str
    source_type: str
    source_title: str
    source_reference: str | None
    document_id: str | None
    chunk_id: str | None
    page_numbers: tuple[int, ...]
    excerpt: str | None
    extraction_method: str


class Project2Fact(Protocol):
    field: Project2Field
    value: str
    evidence: tuple[Project2ProfileEvidence, ...]


class Project2CandidateProfile(Protocol):
    candidate: Project2Candidate
    facts: tuple[Project2Fact, ...]


@dataclass(frozen=True, slots=True)
class Project2CandidateAdapter:
    observed_at: datetime

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")

    def to_target(self, candidate: Project2Candidate) -> TargetCompany:
        identity = self._identity(candidate)
        industry, sub_industry = _industry_values(candidate.industry_tags)
        return TargetCompany(
            identity=identity,
            industry=industry,
            sub_industry=sub_industry,
            business_description=candidate.description,
            evidence=self._discovery_evidence(candidate),
        )

    def profile_to_target(self, profile: Project2CandidateProfile) -> TargetCompany:
        base = self.to_target(profile.candidate)
        facts = _fact_values(profile.facts)
        evidence = (*base.evidence, *self._profile_evidence(profile.facts))
        return TargetCompany(
            identity=base.identity,
            industry=facts.get("industry", base.industry),
            sub_industry=facts.get("sub_industry", base.sub_industry),
            business_description=facts.get("business_description", base.business_description),
            customer_type=facts.get("customer_segments"),
            business_model=facts.get("business_model"),
            evidence=tuple(dict.fromkeys(evidence)),
        )

    def to_comparable(self, candidate: Project2Candidate) -> ComparableCompany:
        identity = self._identity(candidate)
        industry, sub_industry = _industry_values(candidate.industry_tags)
        return ComparableCompany(
            identity=identity,
            industry=industry,
            sub_industry=sub_industry,
            business_description=candidate.description,
            website_domain=candidate.website_domain,
            evidence=self._discovery_evidence(candidate),
        )

    def profile_to_comparable(self, profile: Project2CandidateProfile) -> ComparableCompany:
        base = self.to_comparable(profile.candidate)
        facts = _fact_values(profile.facts)
        evidence = (*base.evidence, *self._profile_evidence(profile.facts))
        products = _split_values(facts.get("products_services"))
        geographies = _split_values(facts.get("geographies"))
        return ComparableCompany(
            identity=base.identity,
            industry=facts.get("industry", base.industry),
            sub_industry=facts.get("sub_industry", base.sub_industry),
            business_description=facts.get("business_description", base.business_description),
            products_services=products,
            customer_type=facts.get("customer_segments"),
            geographies=geographies,
            business_model=facts.get("business_model"),
            website_domain=base.website_domain,
            evidence=tuple(dict.fromkeys(evidence)),
        )

    def _identity(self, candidate: Project2Candidate) -> CompanyIdentity:
        identifiers = tuple((item.scheme, item.value) for item in candidate.identifiers)
        by_scheme = {scheme.casefold(): value for scheme, value in identifiers}
        ticker = by_scheme.get("ticker")
        exchange = by_scheme.get("exchange")
        stable = (
            candidate.website_domain
            or next((value for _, value in identifiers), None)
            or re.sub(r"[^a-z0-9]+", "-", candidate.canonical_name.casefold()).strip("-")
        )
        return CompanyIdentity(
            company_id=f"p2:{stable.casefold()}",
            name=candidate.canonical_name,
            ticker=ticker,
            exchange=exchange,
            country=candidate.country,
            identifiers=identifiers,
        )

    def _discovery_evidence(self, candidate: Project2Candidate) -> tuple[EvidenceReference, ...]:
        return tuple(
            EvidenceReference(
                evidence_id=f"p2:discovery:{index}",
                source_type=item.source_type,
                source_name=item.source_title or item.source_name,
                source_locator=item.source_uri,
                excerpt=item.excerpt,
                observed_at=item.observed_at or self.observed_at,
                extraction_method=f"project2:{item.provider_name}",
            )
            for index, item in enumerate(candidate.discovery_evidence, start=1)
        )

    def _profile_evidence(self, facts: tuple[Project2Fact, ...]) -> tuple[EvidenceReference, ...]:
        return tuple(
            EvidenceReference(
                evidence_id=f"p2:profile:{item.evidence_id}",
                source_type=item.source_type,
                source_name=item.source_title,
                source_locator=item.source_reference,
                document_id=item.document_id,
                chunk_id=item.chunk_id,
                page_numbers=item.page_numbers,
                excerpt=item.excerpt,
                observed_at=self.observed_at,
                extraction_method=item.extraction_method,
            )
            for fact in facts
            for item in fact.evidence
        )


def _industry_values(tags: tuple[str, ...]) -> tuple[str | None, str | None]:
    return (
        tags[0] if tags else None,
        tags[1] if len(tags) > 1 else None,
    )


def _fact_values(facts: tuple[Project2Fact, ...]) -> dict[str, str]:
    return {item.field.value: item.value for item in facts}


def _split_values(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())
