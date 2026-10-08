"""Deterministic company/listing identity normalization for peer universes."""

from __future__ import annotations

import re
from dataclasses import replace

from ma_comparable_valuation.domain import CompanyIdentity, ComparableCompany


def canonical_listing_key(identity: CompanyIdentity) -> tuple[str, ...]:
    """Prefer exchange+ticker, then explicit identifiers, then country+normalized name."""

    if identity.ticker is not None and identity.exchange is not None:
        return ("listing", identity.exchange.casefold(), identity.ticker.casefold())
    if identity.identifiers:
        scheme, value = sorted(
            identity.identifiers, key=lambda item: (item[0].casefold(), item[1].casefold())
        )[0]
        return ("identifier", scheme.casefold(), value.casefold())
    return (
        "name",
        (identity.country or "unknown").casefold(),
        re.sub(r"[^a-z0-9]+", "", identity.name.casefold()),
    )


def deduplicate_companies(
    companies: tuple[ComparableCompany, ...],
) -> tuple[tuple[ComparableCompany, ...], tuple[str, ...]]:
    """Merge exact identity aliases without silently discarding their evidence."""

    kept: list[ComparableCompany] = []
    positions: dict[tuple[str, ...], int] = {}
    warnings: list[str] = []
    for company in companies:
        key = canonical_listing_key(company.identity)
        prior = positions.get(key)
        if prior is None:
            positions[key] = len(kept)
            kept.append(company)
            continue
        existing = kept[prior]
        merged_evidence = tuple(dict.fromkeys((*existing.evidence, *company.evidence)))
        kept[prior] = replace(existing, evidence=merged_evidence)
        warnings.append(
            f"Deduplicated {company.identity.name} into {existing.identity.name} using {key[0]}."
        )
    return tuple(kept), tuple(warnings)
