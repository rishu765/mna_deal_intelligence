"""Provider-neutral contracts for historical transaction discovery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from ma_precedent_transactions.domain import BuyerType, DealStatus, TransactionType
from ma_precedent_transactions.errors import DomainValidationError


def _text(value: str, name: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise DomainValidationError(f"{name} must not be blank")
    return normalized


def _optional_text(value: str | None, name: str) -> str | None:
    return None if value is None else _text(value, name)


@dataclass(frozen=True, slots=True)
class AcquisitionContext:
    """Broad discovery criteria, not a final comparable-selection policy."""

    context_id: str
    target_industry: str | None = None
    business_description: str | None = None
    geographies: tuple[str, ...] = ()
    announced_from: date | None = None
    announced_to: date | None = None
    transaction_types: tuple[TransactionType, ...] = ()
    buyer_types: tuple[BuyerType, ...] = ()
    minimum_size: Decimal | None = None
    maximum_size: Decimal | None = None
    size_currency: str | None = None
    keywords: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "context_id", _text(self.context_id, "context_id"))
        for name in ("target_industry", "business_description"):
            object.__setattr__(self, name, _optional_text(getattr(self, name), name))
        object.__setattr__(
            self, "geographies", tuple(_text(x, "geography") for x in self.geographies)
        )
        object.__setattr__(self, "keywords", tuple(_text(x, "keyword") for x in self.keywords))
        if self.announced_from and self.announced_to and self.announced_from > self.announced_to:
            raise DomainValidationError("announced_from must not follow announced_to")
        for name in ("minimum_size", "maximum_size"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise DomainValidationError(f"{name} must not be negative")
        if (
            self.minimum_size is not None
            and self.maximum_size is not None
            and self.minimum_size > self.maximum_size
        ):
            raise DomainValidationError("minimum_size must not exceed maximum_size")
        if (
            self.minimum_size is not None or self.maximum_size is not None
        ) and not self.size_currency:
            raise DomainValidationError("size constraints require size_currency")
        if self.size_currency is not None:
            normalized = self.size_currency.strip().upper()
            if len(normalized) != 3 or not normalized.isalpha():
                raise DomainValidationError("size_currency must be a three-letter code")
            object.__setattr__(self, "size_currency", normalized)


@dataclass(frozen=True, slots=True)
class DiscoverySourceReference:
    reference_id: str
    provider_name: str
    source_name: str
    source_type: str
    observed_at: datetime
    source_uri: str | None = None
    source_title: str | None = None
    excerpt: str | None = None
    external_deal_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("reference_id", "provider_name", "source_name", "source_type"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        for name in ("source_uri", "source_title", "excerpt", "external_deal_id"):
            object.__setattr__(self, name, _optional_text(getattr(self, name), name))
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise DomainValidationError("observed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CandidateTransaction:
    """A provisional transaction returned by discovery, before M3 verification."""

    candidate_id: str
    acquirer_name: str
    target_name: str
    announcement_date: date | None
    status: DealStatus
    transaction_type: TransactionType
    buyer_type: BuyerType
    discovery_rationale: str
    discovery_sources: tuple[DiscoverySourceReference, ...]
    jurisdiction: str | None = None
    industry: str | None = None
    business_description: str | None = None
    headline_amount: Decimal | None = None
    headline_currency: str | None = None

    def __post_init__(self) -> None:
        for name in ("candidate_id", "acquirer_name", "target_name", "discovery_rationale"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        for name in ("jurisdiction", "industry", "business_description"):
            object.__setattr__(self, name, _optional_text(getattr(self, name), name))
        if not self.discovery_sources:
            raise DomainValidationError("candidate transactions require discovery sources")
        if self.headline_amount is not None and self.headline_amount < 0:
            raise DomainValidationError("headline_amount must not be negative")
        if self.headline_amount is not None and self.headline_currency is None:
            raise DomainValidationError("headline_amount requires headline_currency")
        if self.headline_currency is not None:
            currency = self.headline_currency.strip().upper()
            if len(currency) != 3 or not currency.isalpha():
                raise DomainValidationError("headline_currency must be a three-letter code")
            object.__setattr__(self, "headline_currency", currency)


@dataclass(frozen=True, slots=True)
class ProviderDiscoveryResult:
    provider_name: str
    candidates: tuple[CandidateTransaction, ...]
    warnings: tuple[str, ...] = ()


class ResolutionDisposition(StrEnum):
    UNIQUE = "unique"
    MERGED = "merged"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class IdentityResolutionDecision:
    input_candidate_ids: tuple[str, ...]
    output_transaction_ids: tuple[str, ...]
    disposition: ResolutionDisposition
    rationale: str


@dataclass(frozen=True, slots=True)
class IdentityResolutionResult:
    transactions: tuple[CandidateTransaction, ...]
    decisions: tuple[IdentityResolutionDecision, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DealDiscoveryResult:
    context_id: str
    raw_candidate_count: int
    transactions: tuple[CandidateTransaction, ...]
    provider_names: tuple[str, ...]
    resolution_decisions: tuple[IdentityResolutionDecision, ...]
    warnings: tuple[str, ...] = ()
