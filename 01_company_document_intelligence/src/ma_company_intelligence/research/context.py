"""Targeted retrieval and deterministic context construction for research profiles."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from ma_company_intelligence.domain import (
    RESEARCH_SECTION_ORDER,
    ResearchSectionKey,
    RetrievalFilters,
    RetrievalResult,
)
from ma_company_intelligence.rag import format_evidence_result
from ma_company_intelligence.retrieval import Retriever


@dataclass(frozen=True, slots=True)
class ResearchCategory:
    """One stable research section and its focused semantic query."""

    key: ResearchSectionKey
    query: str


RESEARCH_CATEGORIES = (
    ResearchCategory(
        ResearchSectionKey.COMPANY_CONTEXT,
        "company identity reporting scope document title and covered fiscal period",
    ),
    ResearchCategory(
        ResearchSectionKey.BUSINESS_OVERVIEW,
        "business overview operations business model and how the company makes money",
    ),
    ResearchCategory(
        ResearchSectionKey.PRODUCTS_SERVICES,
        "key products services solutions brands and offerings",
    ),
    ResearchCategory(
        ResearchSectionKey.BUSINESS_SEGMENTS,
        "reportable business segments divisions and segment activities",
    ),
    ResearchCategory(
        ResearchSectionKey.GEOGRAPHIC_EXPOSURE,
        "geographic markets regions countries revenue exposure and operations",
    ),
    ResearchCategory(
        ResearchSectionKey.CUSTOMERS_END_MARKETS,
        "important customers customer concentration end markets industries and channels",
    ),
    ResearchCategory(
        ResearchSectionKey.FINANCIAL_HIGHLIGHTS,
        "revenue EBITDA adjusted EBITDA margins growth net income segment revenue "
        "financial results",
    ),
    ResearchCategory(
        ResearchSectionKey.MAJOR_RISKS,
        "material risk factors operational financial regulatory market and concentration risks",
    ),
    ResearchCategory(
        ResearchSectionKey.STRATEGIC_DEVELOPMENTS,
        "strategic developments acquisitions divestitures investments partnerships and initiatives",
    ),
    ResearchCategory(
        ResearchSectionKey.MANAGEMENT_OUTLOOK,
        "management outlook guidance priorities expectations and forward-looking statements",
    ),
    ResearchCategory(
        ResearchSectionKey.MA_RELEVANT_OBSERVATIONS,
        "M&A relevant scale concentration capabilities growth risks assets and strategic "
        "positioning",
    ),
)


@dataclass(frozen=True, slots=True)
class ResearchEvidenceContext:
    """Bounded evidence catalog and section-to-evidence mapping."""

    text: str
    evidence_by_id: Mapping[str, RetrievalResult]
    evidence_ids_by_section: Mapping[ResearchSectionKey, tuple[str, ...]]
    omitted_result_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_by_id", MappingProxyType(dict(self.evidence_by_id)))
        object.__setattr__(
            self,
            "evidence_ids_by_section",
            MappingProxyType(dict(self.evidence_ids_by_section)),
        )

    @property
    def included_results(self) -> tuple[RetrievalResult, ...]:
        return tuple(self.evidence_by_id.values())

    @property
    def character_count(self) -> int:
        return len(self.text)


class ResearchEvidenceCollector:
    """Run focused queries and pack unique chunks into one bounded evidence catalog."""

    def __init__(
        self,
        retriever: Retriever,
        *,
        top_k_per_section: int = 3,
        max_characters: int = 40_000,
    ) -> None:
        if top_k_per_section <= 0:
            raise ValueError("top_k_per_section must be positive")
        if max_characters <= 0:
            raise ValueError("max_characters must be positive")
        self._retriever = retriever
        self._top_k_per_section = top_k_per_section
        self._max_characters = max_characters

    def collect(
        self,
        *,
        company_name: str | None = None,
        filters: RetrievalFilters | None = None,
    ) -> ResearchEvidenceContext:
        """Retrieve every category and retain a deterministic bounded evidence set."""

        evidence_by_id: dict[str, RetrievalResult] = {}
        evidence_id_by_chunk: dict[str, str] = {}
        ids_by_section: dict[ResearchSectionKey, list[str]] = {
            key: [] for key in RESEARCH_SECTION_ORDER
        }
        omitted_count = 0

        for category in RESEARCH_CATEGORIES:
            query = f"{company_name}: {category.query}" if company_name else category.query
            results = self._retriever.retrieve(
                query,
                top_k=self._top_k_per_section,
                filters=filters,
            )
            for result in results:
                existing_id = evidence_id_by_chunk.get(result.chunk_id)
                candidate_id = existing_id or f"E{len(evidence_by_id) + 1}"
                candidate_ids = {key: list(value) for key, value in ids_by_section.items()}
                if candidate_id not in candidate_ids[category.key]:
                    candidate_ids[category.key].append(candidate_id)
                candidate_evidence = dict(evidence_by_id)
                if existing_id is None:
                    candidate_evidence[candidate_id] = result
                candidate_text = _render_context(candidate_ids, candidate_evidence)
                if len(candidate_text) > self._max_characters:
                    omitted_count += 1
                    continue
                ids_by_section = candidate_ids
                if existing_id is None:
                    evidence_by_id[candidate_id] = result
                    evidence_id_by_chunk[result.chunk_id] = candidate_id

        return ResearchEvidenceContext(
            text=_render_context(ids_by_section, evidence_by_id),
            evidence_by_id=evidence_by_id,
            evidence_ids_by_section={
                key: tuple(ids_by_section[key]) for key in RESEARCH_SECTION_ORDER
            },
            omitted_result_count=omitted_count,
        )


def _render_context(
    ids_by_section: Mapping[ResearchSectionKey, list[str]],
    evidence_by_id: Mapping[str, RetrievalResult],
) -> str:
    if not evidence_by_id:
        return ""
    section_lines = ["CATEGORY EVIDENCE MAP"]
    section_lines.extend(
        f"{key.value}: {', '.join(ids_by_section[key]) or 'none'}" for key in RESEARCH_SECTION_ORDER
    )
    blocks = [
        format_evidence_result(result, evidence_id=evidence_id)
        for evidence_id, result in evidence_by_id.items()
    ]
    return "\n".join(section_lines) + "\n\nEVIDENCE CATALOG\n\n" + "\n\n".join(blocks)
