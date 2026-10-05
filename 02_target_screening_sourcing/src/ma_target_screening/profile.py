"""Evidence-backed candidate profile domain models."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Self

from ma_target_screening.domain import CandidateCompany, DiscoveryEvidence, ExternalIdentifier


class ProfileField(StrEnum):
    BUSINESS_DESCRIPTION = "business_description"
    INDUSTRY = "industry"
    SUB_INDUSTRY = "sub_industry"
    PRODUCTS_SERVICES = "products_services"
    CAPABILITIES = "capabilities"
    GEOGRAPHIES = "geographies"
    CUSTOMER_SEGMENTS = "customer_segments"
    PROFITABILITY = "profitability"
    GROWTH = "growth"
    EMPLOYEE_COUNT = "employee_count"
    COMPANY_SIZE = "company_size"
    OWNERSHIP = "ownership"
    TECHNOLOGY = "technology"
    STRATEGIC_DEVELOPMENTS = "strategic_developments"
    RISKS = "risks"
    MA_OBSERVATIONS = "ma_observations"
    FINANCIALS = "financials"


class EvidenceQuality(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    SUPPLIED = "supplied"
    UNKNOWN = "unknown"


class EnrichmentStatus(StrEnum):
    COMPLETE_ENOUGH = "complete_enough"
    PARTIAL = "partial"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    PROVIDER_FAILURE = "provider_failure"


def _text(value: str, name: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"{name} must not be blank")
    return normalized


def _optional_text(value: str | None, name: str) -> str | None:
    return None if value is None else _text(value, name)


@dataclass(frozen=True, slots=True)
class EnrichmentEvidence:
    evidence_id: str
    provider_name: str
    source_type: str
    source_title: str
    source_reference: str | None = None
    document_id: str | None = None
    chunk_id: str | None = None
    page_numbers: tuple[int, ...] = ()
    excerpt: str | None = None
    extraction_method: str = "structured_fixture"
    quality: EvidenceQuality = EvidenceQuality.UNKNOWN

    def __post_init__(self) -> None:
        for field_name in (
            "evidence_id",
            "provider_name",
            "source_type",
            "source_title",
            "extraction_method",
        ):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), field_name))
        for field_name in ("source_reference", "document_id", "chunk_id", "excerpt"):
            object.__setattr__(
                self, field_name, _optional_text(getattr(self, field_name), field_name)
            )
        if any(page < 1 for page in self.page_numbers):
            raise ValueError("page_numbers must be positive")
        if len(set(self.page_numbers)) != len(self.page_numbers):
            raise ValueError("page_numbers must be unique")


@dataclass(frozen=True, slots=True)
class ProfileFact:
    field: ProfileField
    value: str
    evidence: tuple[EnrichmentEvidence, ...]
    raw_value: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _text(self.value, "fact value"))
        object.__setattr__(self, "raw_value", _optional_text(self.raw_value, "raw_value"))
        if not self.evidence:
            raise ValueError("facts require evidence")


@dataclass(frozen=True, slots=True)
class ProfileInference:
    field: ProfileField
    statement: str
    evidence: tuple[EnrichmentEvidence, ...]
    rationale: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "statement", _text(self.statement, "inference statement"))
        object.__setattr__(self, "rationale", _optional_text(self.rationale, "rationale"))
        if not self.evidence:
            raise ValueError("inferences require supporting evidence")


@dataclass(frozen=True, slots=True)
class UnknownField:
    field: ProfileField
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason", _text(self.reason, "unknown reason"))


@dataclass(frozen=True, slots=True)
class ProfileFinancialMetric:
    metric_name: str
    value: str
    fiscal_period: str | None
    unit: str | None
    currency: str | None
    basis: str | None
    evidence: tuple[EnrichmentEvidence, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "metric_name", _text(self.metric_name, "metric_name"))
        object.__setattr__(self, "value", _text(self.value, "financial value"))
        for field_name in ("fiscal_period", "unit", "basis"):
            object.__setattr__(
                self, field_name, _optional_text(getattr(self, field_name), field_name)
            )
        if self.currency is not None:
            currency = self.currency.strip().upper()
            if not re.fullmatch(r"[A-Z]{3}", currency):
                raise ValueError("financial currency must be a three-letter code")
            object.__setattr__(self, "currency", currency)
        if not self.evidence:
            raise ValueError("financial metrics require evidence")


@dataclass(frozen=True, slots=True)
class ConflictAlternative:
    value: str
    evidence: tuple[EnrichmentEvidence, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _text(self.value, "conflict value"))
        if not self.evidence:
            raise ValueError("conflict alternatives require evidence")


@dataclass(frozen=True, slots=True)
class ProfileConflict:
    field: ProfileField
    alternatives: tuple[ConflictAlternative, ...]
    reason: str

    def __post_init__(self) -> None:
        if len(self.alternatives) < 2:
            raise ValueError("a conflict requires at least two alternatives")
        object.__setattr__(self, "reason", _text(self.reason, "conflict reason"))


@dataclass(frozen=True, slots=True)
class CandidateProfile:
    candidate: CandidateCompany
    facts: tuple[ProfileFact, ...]
    inferences: tuple[ProfileInference, ...]
    financial_metrics: tuple[ProfileFinancialMetric, ...]
    unknown_fields: tuple[UnknownField, ...]
    conflicts: tuple[ProfileConflict, ...]
    status: EnrichmentStatus
    provider_names: tuple[str, ...]
    requested_fields: tuple[ProfileField, ...]
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, values in (
            ("provider_names", self.provider_names),
            ("warnings", self.warnings),
        ):
            if any(not value.strip() for value in values):
                raise ValueError(f"{name} must not contain blank values")
            if len(set(values)) != len(values):
                raise ValueError(f"{name} must not contain duplicates")
        if len(set(self.requested_fields)) != len(self.requested_fields):
            raise ValueError("requested_fields must not contain duplicates")

    @property
    def evidence(self) -> tuple[EnrichmentEvidence, ...]:
        values = (
            *(e for fact in self.facts for e in fact.evidence),
            *(e for inference in self.inferences for e in inference.evidence),
            *(e for metric in self.financial_metrics for e in metric.evidence),
        )
        return tuple(dict.fromkeys(values))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "candidate": {
                "canonical_name": self.candidate.canonical_name,
                "aliases": list(self.candidate.aliases),
                "website_domain": self.candidate.website_domain,
                "country": self.candidate.country,
                "industry_tags": list(self.candidate.industry_tags),
                "description": self.candidate.description,
                "identifiers": [
                    {"scheme": item.scheme, "value": item.value}
                    for item in self.candidate.identifiers
                ],
                "discovery_evidence": [
                    {
                        "source_type": item.source_type,
                        "source_name": item.source_name,
                        "provider_name": item.provider_name,
                        "source_uri": item.source_uri,
                        "source_title": item.source_title,
                        "source_identifier": item.source_identifier,
                        "discovery_query": item.discovery_query,
                        "observed_at": (
                            None if item.observed_at is None else item.observed_at.isoformat()
                        ),
                        "excerpt": item.excerpt,
                        "raw_metadata": [list(pair) for pair in item.raw_metadata],
                    }
                    for item in self.candidate.discovery_evidence
                ],
            },
            "facts": [_fact_to_dict(item) for item in self.facts],
            "inferences": [_inference_to_dict(item) for item in self.inferences],
            "financial_metrics": [_metric_to_dict(item) for item in self.financial_metrics],
            "unknown_fields": [
                {"field": item.field.value, "reason": item.reason} for item in self.unknown_fields
            ],
            "conflicts": [
                {
                    "field": item.field.value,
                    "reason": item.reason,
                    "alternatives": [
                        {
                            "value": alternative.value,
                            "evidence": [_evidence_to_dict(e) for e in alternative.evidence],
                        }
                        for alternative in item.alternatives
                    ],
                }
                for item in self.conflicts
            ],
            "status": self.status.value,
            "provider_names": list(self.provider_names),
            "requested_fields": [item.value for item in self.requested_fields],
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        if data.get("schema_version") != 1:
            raise ValueError("candidate profile schema_version must be 1")
        try:
            candidate_data = data["candidate"]
            candidate = CandidateCompany(
                canonical_name=candidate_data["canonical_name"],
                aliases=tuple(candidate_data.get("aliases", [])),
                website_domain=candidate_data.get("website_domain"),
                country=candidate_data.get("country"),
                industry_tags=tuple(candidate_data.get("industry_tags", [])),
                description=candidate_data.get("description"),
                identifiers=tuple(
                    ExternalIdentifier(item["scheme"], item["value"])
                    for item in candidate_data.get("identifiers", [])
                ),
                discovery_evidence=tuple(
                    DiscoveryEvidence(
                        source_type=item["source_type"],
                        source_name=item["source_name"],
                        provider_name=item["provider_name"],
                        source_uri=item.get("source_uri"),
                        source_title=item.get("source_title"),
                        source_identifier=item.get("source_identifier"),
                        discovery_query=item.get("discovery_query"),
                        observed_at=(
                            None
                            if item.get("observed_at") is None
                            else datetime.fromisoformat(item["observed_at"])
                        ),
                        excerpt=item.get("excerpt"),
                        raw_metadata=tuple(
                            (str(pair[0]), str(pair[1])) for pair in item.get("raw_metadata", [])
                        ),
                    )
                    for item in candidate_data.get("discovery_evidence", [])
                ),
            )
            return cls(
                candidate=candidate,
                facts=tuple(_fact_from_dict(item) for item in data.get("facts", [])),
                inferences=tuple(_inference_from_dict(item) for item in data.get("inferences", [])),
                financial_metrics=tuple(
                    _metric_from_dict(item) for item in data.get("financial_metrics", [])
                ),
                unknown_fields=tuple(
                    UnknownField(ProfileField(item["field"]), item["reason"])
                    for item in data.get("unknown_fields", [])
                ),
                conflicts=tuple(_conflict_from_dict(item) for item in data.get("conflicts", [])),
                status=EnrichmentStatus(data["status"]),
                provider_names=tuple(data.get("provider_names", [])),
                requested_fields=tuple(
                    ProfileField(item) for item in data.get("requested_fields", [])
                ),
                warnings=tuple(data.get("warnings", [])),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"invalid candidate profile: {error}") from error

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, value: str) -> Self:
        try:
            data = json.loads(value)
        except json.JSONDecodeError as error:
            raise ValueError("invalid candidate profile JSON") from error
        if not isinstance(data, dict):
            raise ValueError("candidate profile JSON must contain an object")
        return cls.from_dict(data)


def _evidence_to_dict(value: EnrichmentEvidence) -> dict[str, Any]:
    return {
        "evidence_id": value.evidence_id,
        "provider_name": value.provider_name,
        "source_type": value.source_type,
        "source_title": value.source_title,
        "source_reference": value.source_reference,
        "document_id": value.document_id,
        "chunk_id": value.chunk_id,
        "page_numbers": list(value.page_numbers),
        "excerpt": value.excerpt,
        "extraction_method": value.extraction_method,
        "quality": value.quality.value,
    }


def _evidence_from_dict(data: dict[str, Any]) -> EnrichmentEvidence:
    return EnrichmentEvidence(
        evidence_id=data["evidence_id"],
        provider_name=data["provider_name"],
        source_type=data["source_type"],
        source_title=data["source_title"],
        source_reference=data.get("source_reference"),
        document_id=data.get("document_id"),
        chunk_id=data.get("chunk_id"),
        page_numbers=tuple(data.get("page_numbers", [])),
        excerpt=data.get("excerpt"),
        extraction_method=data.get("extraction_method", "structured_fixture"),
        quality=EvidenceQuality(data.get("quality", "unknown")),
    )


def _fact_to_dict(value: ProfileFact) -> dict[str, Any]:
    return {
        "field": value.field.value,
        "value": value.value,
        "raw_value": value.raw_value,
        "evidence": [_evidence_to_dict(item) for item in value.evidence],
    }


def _fact_from_dict(data: dict[str, Any]) -> ProfileFact:
    return ProfileFact(
        field=ProfileField(data["field"]),
        value=data["value"],
        raw_value=data.get("raw_value"),
        evidence=tuple(_evidence_from_dict(item) for item in data["evidence"]),
    )


def _inference_to_dict(value: ProfileInference) -> dict[str, Any]:
    return {
        "field": value.field.value,
        "statement": value.statement,
        "rationale": value.rationale,
        "evidence": [_evidence_to_dict(item) for item in value.evidence],
    }


def _inference_from_dict(data: dict[str, Any]) -> ProfileInference:
    return ProfileInference(
        field=ProfileField(data["field"]),
        statement=data["statement"],
        rationale=data.get("rationale"),
        evidence=tuple(_evidence_from_dict(item) for item in data["evidence"]),
    )


def _metric_to_dict(value: ProfileFinancialMetric) -> dict[str, Any]:
    return {
        "metric_name": value.metric_name,
        "value": value.value,
        "fiscal_period": value.fiscal_period,
        "unit": value.unit,
        "currency": value.currency,
        "basis": value.basis,
        "evidence": [_evidence_to_dict(item) for item in value.evidence],
    }


def _metric_from_dict(data: dict[str, Any]) -> ProfileFinancialMetric:
    return ProfileFinancialMetric(
        metric_name=data["metric_name"],
        value=data["value"],
        fiscal_period=data.get("fiscal_period"),
        unit=data.get("unit"),
        currency=data.get("currency"),
        basis=data.get("basis"),
        evidence=tuple(_evidence_from_dict(item) for item in data["evidence"]),
    )


def _conflict_from_dict(data: dict[str, Any]) -> ProfileConflict:
    return ProfileConflict(
        field=ProfileField(data["field"]),
        reason=data["reason"],
        alternatives=tuple(
            ConflictAlternative(
                value=item["value"],
                evidence=tuple(_evidence_from_dict(e) for e in item["evidence"]),
            )
            for item in data["alternatives"]
        ),
    )
