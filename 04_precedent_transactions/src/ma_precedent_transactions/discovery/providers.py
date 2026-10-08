"""Deterministic, credential-free historical deal discovery providers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from ma_precedent_transactions.discovery.models import (
    AcquisitionContext,
    CandidateTransaction,
    DiscoverySourceReference,
    ProviderDiscoveryResult,
)
from ma_precedent_transactions.domain import BuyerType, DealStatus, TransactionType
from ma_precedent_transactions.errors import MalformedFixtureError

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_STOPWORDS = {"a", "and", "business", "company", "for", "in", "of", "the", "with"}


@dataclass(frozen=True, slots=True)
class FixtureDealDiscoveryProvider:
    dataset_path: Path

    @property
    def provider_name(self) -> str:
        return "fixture_deal_dataset"

    def discover(self, context: AcquisitionContext) -> ProviderDiscoveryResult:
        records = self._load()
        ranked: list[tuple[int, str, CandidateTransaction]] = []
        for record in records:
            candidate = self._candidate(record)
            score = self._match_score(context, candidate)
            if score is not None:
                ranked.append((score, candidate.candidate_id, candidate))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        candidates = tuple(item[2] for item in ranked)
        warnings = () if candidates else ("Fixture discovery found no candidate transactions.",)
        return ProviderDiscoveryResult(self.provider_name, candidates, warnings)

    def _load(self) -> list[dict[str, Any]]:
        try:
            payload = json.loads(self.dataset_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise MalformedFixtureError(
                f"Unable to load discovery fixture: {self.dataset_path}"
            ) from error
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise MalformedFixtureError("discovery fixture must be a JSON list of objects")
        return payload

    def _candidate(self, record: dict[str, Any]) -> CandidateTransaction:
        try:
            source = DiscoverySourceReference(
                reference_id=str(record["reference_id"]),
                provider_name=self.provider_name,
                source_name=str(record["source_name"]),
                source_type=str(record["source_type"]),
                observed_at=datetime.fromisoformat(str(record["observed_at"])),
                source_uri=_optional_string(record.get("source_uri")),
                source_title=_optional_string(record.get("source_title")),
                excerpt=_optional_string(record.get("excerpt")),
                external_deal_id=_optional_string(record.get("external_deal_id")),
            )
            amount = record.get("headline_amount")
            return CandidateTransaction(
                candidate_id=str(record["candidate_id"]),
                acquirer_name=str(record["acquirer_name"]),
                target_name=str(record["target_name"]),
                announcement_date=(
                    None
                    if record.get("announcement_date") is None
                    else datetime.fromisoformat(str(record["announcement_date"])).date()
                ),
                status=DealStatus(str(record["status"])),
                transaction_type=TransactionType(str(record["transaction_type"])),
                buyer_type=BuyerType(str(record["buyer_type"])),
                jurisdiction=_optional_string(record.get("jurisdiction")),
                industry=_optional_string(record.get("industry")),
                business_description=_optional_string(record.get("business_description")),
                headline_amount=None if amount is None else Decimal(str(amount)),
                headline_currency=_optional_string(record.get("headline_currency")),
                discovery_rationale=str(record["discovery_rationale"]),
                discovery_sources=(source,),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise MalformedFixtureError(
                f"Malformed discovery record: {record.get('candidate_id', '<unknown>')}"
            ) from error

    @staticmethod
    def _match_score(context: AcquisitionContext, candidate: CandidateTransaction) -> int | None:
        if context.announced_from and (
            candidate.announcement_date is None
            or candidate.announcement_date < context.announced_from
        ):
            return None
        if context.announced_to and (
            candidate.announcement_date is None
            or candidate.announcement_date > context.announced_to
        ):
            return None
        if (
            context.transaction_types
            and candidate.transaction_type not in context.transaction_types
        ):
            return None
        if context.buyer_types and candidate.buyer_type not in context.buyer_types:
            return None
        if context.geographies and not _contains_any(candidate.jurisdiction, context.geographies):
            return None
        if context.minimum_size is not None:
            if (
                candidate.headline_amount is None
                or candidate.headline_currency != context.size_currency
            ):
                return None
            if candidate.headline_amount < context.minimum_size:
                return None
        if context.maximum_size is not None:
            if (
                candidate.headline_amount is None
                or candidate.headline_currency != context.size_currency
            ):
                return None
            if candidate.headline_amount > context.maximum_size:
                return None

        query_text = " ".join(
            value
            for value in (
                context.target_industry,
                context.business_description,
                " ".join(context.keywords),
            )
            if value
        )
        query_tokens = _tokens(query_text)
        candidate_tokens = _tokens(
            " ".join(
                value
                for value in (
                    candidate.industry,
                    candidate.business_description,
                    candidate.acquirer_name,
                    candidate.target_name,
                )
                if value
            )
        )
        if query_tokens and not query_tokens & candidate_tokens:
            return None
        return len(query_tokens & candidate_tokens)


def _tokens(value: str) -> set[str]:
    return {token for token in _TOKEN_PATTERN.findall(value.casefold()) if token not in _STOPWORDS}


def _contains_any(value: str | None, expected: tuple[str, ...]) -> bool:
    if value is None:
        return False
    normalized = value.casefold()
    return any(item.casefold() in normalized for item in expected)


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)
