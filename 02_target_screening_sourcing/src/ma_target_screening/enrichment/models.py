"""Provider-neutral enrichment request and partial-result contracts."""

from __future__ import annotations

from dataclasses import dataclass

from ma_target_screening.domain import CandidateCompany
from ma_target_screening.profile import (
    ProfileFact,
    ProfileField,
    ProfileFinancialMetric,
    ProfileInference,
    UnknownField,
)
from ma_target_screening.thesis import AcquisitionThesis


@dataclass(frozen=True, slots=True)
class EnrichmentRequest:
    candidate: CandidateCompany
    thesis: AcquisitionThesis
    priority_fields: tuple[ProfileField, ...]
    document_references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if len(set(self.priority_fields)) != len(self.priority_fields):
            raise ValueError("priority_fields must not contain duplicates")
        if any(not item.strip() for item in self.document_references):
            raise ValueError("document_references must not contain blank values")


@dataclass(frozen=True, slots=True)
class ProviderEnrichmentResult:
    provider_name: str
    facts: tuple[ProfileFact, ...] = ()
    inferences: tuple[ProfileInference, ...] = ()
    financial_metrics: tuple[ProfileFinancialMetric, ...] = ()
    unknown_fields: tuple[UnknownField, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.provider_name.strip():
            raise ValueError("provider_name must not be blank")
        if any(not warning.strip() for warning in self.warnings):
            raise ValueError("warnings must not contain blank values")
