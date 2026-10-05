"""Conservative candidate normalization and deduplication."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from ma_target_screening.discovery.models import DiscoveredCompanyRecord
from ma_target_screening.domain import CandidateCompany, DiscoveryEvidence, ExternalIdentifier

_LEGAL_SUFFIX = re.compile(
    r"(?:,?\s+(?:private\s+limited|pvt\.?\s+ltd\.?|limited|ltd\.?|inc\.?|llc|plc))+$",
    re.IGNORECASE,
)


def normalize_domain(value: str | None) -> str | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or "").rstrip(".").casefold()
    if host.startswith("www."):
        host = host[4:]
    if not host or "." not in host:
        raise ValueError(f"invalid company website/domain: {value}")
    return host.encode("idna").decode("ascii")


def normalize_display_name(value: str) -> str:
    normalized = " ".join(value.split()).strip(" ,;")
    if not normalized:
        raise ValueError("company name must not be blank")
    return normalized


def company_name_key(value: str) -> str:
    normalized = normalize_display_name(value)
    without_suffix = _LEGAL_SUFFIX.sub("", normalized).strip(" ,;")
    return re.sub(r"[^a-z0-9]+", " ", without_suffix.casefold()).strip()


def candidate_from_record(record: DiscoveredCompanyRecord) -> CandidateCompany:
    domain = normalize_domain(record.website)
    identifier = (
        ()
        if record.source_identifier is None
        else (ExternalIdentifier(record.provider_name, record.source_identifier),)
    )
    evidence = DiscoveryEvidence(
        source_type=record.source_type,
        source_name=record.source_name,
        provider_name=record.provider_name,
        source_uri=record.source_uri,
        source_title=record.source_title,
        source_identifier=record.source_identifier,
        discovery_query=record.discovery_query,
        observed_at=record.observed_at,
        excerpt=record.description,
        raw_metadata=record.raw_metadata,
    )
    return CandidateCompany(
        canonical_name=normalize_display_name(record.observed_name),
        aliases=tuple(normalize_display_name(alias) for alias in record.aliases),
        website_domain=domain,
        country=record.country,
        industry_tags=record.industry_tags,
        description=record.description,
        identifiers=identifier,
        discovery_evidence=(evidence,),
    )


def deduplicate_candidates(
    candidates: tuple[CandidateCompany, ...],
) -> tuple[CandidateCompany, ...]:
    merged: list[CandidateCompany] = []
    for candidate in candidates:
        match_index = next(
            (index for index, existing in enumerate(merged) if _same_company(existing, candidate)),
            None,
        )
        if match_index is None:
            merged.append(candidate)
        else:
            merged[match_index] = _merge(merged[match_index], candidate)
    return tuple(merged)


def _same_company(left: CandidateCompany, right: CandidateCompany) -> bool:
    left_ids = {(item.scheme.casefold(), item.value.casefold()) for item in left.identifiers}
    right_ids = {(item.scheme.casefold(), item.value.casefold()) for item in right.identifiers}
    if left_ids & right_ids:
        return True
    if left.website_domain and left.website_domain == right.website_domain:
        return True
    if left.country and right.country and left.country.casefold() != right.country.casefold():
        return False
    left_names = {
        company_name_key(left.canonical_name),
        *(company_name_key(x) for x in left.aliases),
    }
    right_names = {
        company_name_key(right.canonical_name),
        *(company_name_key(x) for x in right.aliases),
    }
    return bool(left_names & right_names)


def _merge(left: CandidateCompany, right: CandidateCompany) -> CandidateCompany:
    aliases = list(left.aliases)
    left_key = company_name_key(left.canonical_name)
    if company_name_key(right.canonical_name) != left_key:
        aliases.append(right.canonical_name)
    aliases.extend(right.aliases)
    aliases = list(dict.fromkeys(alias for alias in aliases if company_name_key(alias) != left_key))
    identifiers = tuple(dict.fromkeys((*left.identifiers, *right.identifiers)))
    evidence = tuple(dict.fromkeys((*left.discovery_evidence, *right.discovery_evidence)))
    tags = tuple(dict.fromkeys((*left.industry_tags, *right.industry_tags)))
    return CandidateCompany(
        canonical_name=left.canonical_name,
        aliases=tuple(aliases),
        website_domain=left.website_domain or right.website_domain,
        country=left.country or right.country,
        industry_tags=tags,
        description=left.description or right.description,
        identifiers=identifiers,
        discovery_evidence=evidence,
    )
