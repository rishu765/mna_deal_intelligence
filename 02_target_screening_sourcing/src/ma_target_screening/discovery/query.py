"""Transparent acquisition-thesis to discovery-query generation."""

from __future__ import annotations

from dataclasses import dataclass

from ma_target_screening.discovery.models import DiscoveryQuery
from ma_target_screening.thesis import (
    AcquisitionThesis,
    CriterionCategory,
    CriterionRequirement,
)

_INDUSTRY_CATEGORIES = {CriterionCategory.INDUSTRY, CriterionCategory.SUB_INDUSTRY}
_CAPABILITY_CATEGORIES = {
    CriterionCategory.PRODUCT_CAPABILITY,
    CriterionCategory.TECHNOLOGY,
}


@dataclass(frozen=True, slots=True)
class DeterministicQueryGenerator:
    """Generate bounded, inspectable queries from discovery-relevant thesis fields."""

    def generate(
        self, thesis: AcquisitionThesis, *, max_queries: int
    ) -> tuple[DiscoveryQuery, ...]:
        if max_queries < 1:
            raise ValueError("max_queries must be positive")
        industries = self._values(thesis, _INDUSTRY_CATEGORIES)
        capabilities = self._values(thesis, _CAPABILITY_CATEGORIES)
        geographies = self._values(thesis, {CriterionCategory.GEOGRAPHY})
        customers = self._values(thesis, {CriterionCategory.CUSTOMER_TYPE})

        proposals: list[tuple[str, tuple[str, ...]]] = []
        locations: tuple[str | None, ...] = geographies or (None,)
        for industry in industries:
            for geography in locations:
                parts = (industry, "companies", geography)
                proposals.append(
                    (self._join(parts), ("industry", "geography") if geography else ("industry",))
                )
        for capability in capabilities:
            for geography in locations:
                parts = (capability, "companies", geography)
                dimensions = ("capability", "geography") if geography else ("capability",)
                proposals.append((self._join(parts), dimensions))
        for capability in capabilities:
            for industry in industries[:2]:
                proposals.append(
                    (self._join((capability, industry, "companies")), ("capability", "industry"))
                )
        for customer in customers:
            anchor = industries[0] if industries else "companies"
            geography = geographies[0] if geographies else None
            customer_dimensions: tuple[str, ...]
            if geography and industries:
                customer_dimensions = ("customer_type", "industry", "geography")
            else:
                customer_dimensions = ("customer_type",)
            proposals.append(
                (
                    self._join((customer, anchor, geography)),
                    customer_dimensions,
                )
            )
        if not proposals and thesis.objective:
            proposals.append((self._join((thesis.objective, "companies")), ("objective",)))

        unique: list[DiscoveryQuery] = []
        seen: set[str] = set()
        for text, proposal_dimensions in proposals:
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            unique.append(
                DiscoveryQuery(
                    query_id=f"query-{len(unique) + 1}",
                    text=text,
                    dimensions=proposal_dimensions,
                )
            )
            if len(unique) == max_queries:
                break
        return tuple(unique)

    @staticmethod
    def _values(thesis: AcquisitionThesis, categories: set[CriterionCategory]) -> tuple[str, ...]:
        values: list[str] = []
        for criterion in thesis.criteria:
            if criterion.category not in categories:
                continue
            if criterion.requirement is CriterionRequirement.EXCLUSION:
                continue
            if isinstance(criterion.value, str):
                values.append(criterion.value)
            elif isinstance(criterion.value, tuple):
                values.extend(criterion.value)
        return tuple(dict.fromkeys(values))

    @staticmethod
    def _join(parts: tuple[str | None, ...]) -> str:
        return " ".join(part for part in parts if part)
