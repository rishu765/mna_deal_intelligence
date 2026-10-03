"""Provider-neutral structured research generation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ma_company_intelligence.domain import RESEARCH_SECTION_ORDER, ResearchSectionKey
from ma_company_intelligence.generation.base import GenerationRequest


def _validate_evidence_ids(evidence_ids: tuple[str, ...]) -> None:
    if any(not evidence_id.strip() for evidence_id in evidence_ids):
        raise ValueError("evidence IDs must not be blank")


@dataclass(frozen=True, slots=True)
class GeneratedResearchItem:
    """One generated fact or analytical observation before citation mapping."""

    text: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("generated research item text must not be blank")
        if not self.evidence_ids:
            raise ValueError("generated research item must reference evidence")
        _validate_evidence_ids(self.evidence_ids)


@dataclass(frozen=True, slots=True)
class GeneratedFinancialMetric:
    """One model-extracted financial metric before citation mapping."""

    metric_name: str
    value: str
    fiscal_period: str | None
    unit: str | None
    currency: str | None
    basis: str | None
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.metric_name.strip() or not self.value.strip():
            raise ValueError("generated financial metric name and value must not be blank")
        for field_name in ("fiscal_period", "unit", "currency", "basis"):
            value = getattr(self, field_name)
            if value is not None and not value.strip():
                raise ValueError(f"{field_name} must be non-blank when supplied")
        if not self.evidence_ids:
            raise ValueError("generated financial metric must reference evidence")
        _validate_evidence_ids(self.evidence_ids)


@dataclass(frozen=True, slots=True)
class GeneratedResearchSection:
    """One schema-validated research section before evidence resolution."""

    key: ResearchSectionKey
    summary: str | None
    summary_evidence_ids: tuple[str, ...]
    facts: tuple[GeneratedResearchItem, ...]
    observations: tuple[GeneratedResearchItem, ...]
    financial_metrics: tuple[GeneratedFinancialMetric, ...]
    insufficient_evidence: bool

    def __post_init__(self) -> None:
        if self.summary is not None and not self.summary.strip():
            raise ValueError("generated section summary must be non-blank when supplied")
        _validate_evidence_ids(self.summary_evidence_ids)
        content_present = bool(
            self.summary or self.facts or self.observations or self.financial_metrics
        )
        referenced = bool(
            self.summary_evidence_ids
            or any(item.evidence_ids for item in (*self.facts, *self.observations))
            or any(metric.evidence_ids for metric in self.financial_metrics)
        )
        if self.insufficient_evidence and (content_present or referenced):
            raise ValueError("an insufficient generated section must be empty")
        if not self.insufficient_evidence and (not content_present or not referenced):
            raise ValueError("a supported generated section needs content and evidence")
        if self.summary is None and self.summary_evidence_ids:
            raise ValueError("summary evidence cannot exist without a summary")
        if self.summary is not None and not self.summary_evidence_ids:
            raise ValueError("a generated summary must reference evidence")
        if self.financial_metrics and self.key is not ResearchSectionKey.FINANCIAL_HIGHLIGHTS:
            raise ValueError("generated financial metrics belong only in financial_highlights")

    @property
    def referenced_evidence_ids(self) -> tuple[str, ...]:
        ids: list[str] = list(self.summary_evidence_ids)
        for item in (*self.facts, *self.observations):
            ids.extend(item.evidence_ids)
        for metric in self.financial_metrics:
            ids.extend(metric.evidence_ids)
        return tuple(ids)


@dataclass(frozen=True, slots=True)
class ResearchGenerationOutput:
    """Application-owned structured response returned by a research generator."""

    company_name: str | None
    sections: tuple[GeneratedResearchSection, ...]

    def __post_init__(self) -> None:
        if self.company_name is not None and not self.company_name.strip():
            raise ValueError("generated company_name must be non-blank when supplied")
        if tuple(section.key for section in self.sections) != RESEARCH_SECTION_ORDER:
            raise ValueError("generated research sections must use the canonical order")

    @property
    def referenced_evidence_ids(self) -> tuple[str, ...]:
        return tuple(
            evidence_id
            for section in self.sections
            for evidence_id in section.referenced_evidence_ids
        )


class ResearchGenerator(Protocol):
    """Generate a schema-validated company research profile."""

    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    def generate_research(self, request: GenerationRequest) -> ResearchGenerationOutput: ...
