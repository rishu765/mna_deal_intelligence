"""Canonical deal and entity identity contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from ma_deal_intelligence.evidence import ProjectId


class DealType(StrEnum):
    ACQUISITION = "acquisition"
    MERGER = "merger"
    DIVESTITURE = "divestiture"
    MINORITY_INVESTMENT = "minority_investment"
    OTHER = "other"
    UNKNOWN = "unknown"


class TransactionStage(StrEnum):
    EXPLORATORY = "exploratory"
    SCREENING = "screening"
    INDICATIVE_OFFER = "indicative_offer"
    DILIGENCE = "diligence"
    NEGOTIATION = "negotiation"
    SIGNED = "signed"
    CLOSED = "closed"
    ABANDONED = "abandoned"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ExternalIdentifier:
    scheme: str
    value: str

    def __post_init__(self) -> None:
        if not self.scheme.strip() or not self.value.strip():
            raise ValueError("external identifier scheme and value must not be blank")


@dataclass(frozen=True, slots=True)
class CanonicalEntityReference:
    canonical_entity_id: str
    legal_name: str | None = None
    display_name: str | None = None
    aliases: tuple[str, ...] = ()
    ticker: str | None = None
    exchange: str | None = None
    country: str | None = None
    sector: str | None = None
    external_ids: tuple[ExternalIdentifier, ...] = ()
    source_projects: tuple[ProjectId, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.canonical_entity_id.strip():
            raise ValueError("canonical_entity_id must not be blank")
        if self.legal_name is None and self.display_name is None:
            raise ValueError("an entity requires a legal_name or display_name")
        if len(self.aliases) != len(set(self.aliases)):
            raise ValueError("entity aliases must be unique")


@dataclass(frozen=True, slots=True)
class AnalystContext:
    user_id: str | None = None
    team: str | None = None
    role: str | None = None


@dataclass(frozen=True, slots=True)
class DealContext:
    deal_id: str
    engagement_id: str | None = None
    buyer_entity_id: str | None = None
    target_entity_id: str | None = None
    deal_type: DealType = DealType.UNKNOWN
    transaction_stage: TransactionStage = TransactionStage.UNKNOWN
    transaction_thesis: str | None = None
    strategic_rationale: tuple[str, ...] = ()
    geographies: tuple[str, ...] = ()
    sectors: tuple[str, ...] = ()
    reporting_currency: str | None = None
    as_of_date: date | None = None
    analyst_context: AnalystContext | None = None
    requested_capabilities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.deal_id.strip():
            raise ValueError("deal_id must not be blank")
        if self.reporting_currency is not None:
            currency = self.reporting_currency.upper()
            if len(currency) != 3 or not currency.isalpha():
                raise ValueError("reporting_currency must be a three-letter code")
            object.__setattr__(self, "reporting_currency", currency)
