"""Credential-free discovery providers for local datasets and supplied longlists."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ma_target_screening.discovery.models import (
    DiscoveredCompanyRecord,
    DiscoveryRequest,
    ProviderDiscoveryResult,
    UserCandidateInput,
)
from ma_target_screening.errors import MalformedDiscoverySourceError

_STOPWORDS = {"and", "company", "companies", "enterprise", "in", "the", "with"}


@dataclass(frozen=True, slots=True)
class LocalDatasetDiscoveryProvider:
    dataset_path: Path

    @property
    def provider_name(self) -> str:
        return "local_dataset"

    def discover(self, request: DiscoveryRequest) -> ProviderDiscoveryResult:
        records = self._load()
        candidates: list[DiscoveredCompanyRecord] = []
        executed = []
        for query in request.queries:
            executed.append(query)
            matches = self._search(records, query.text)[: request.max_candidates_per_query]
            candidates.extend(self._to_record(item, discovery_query=query.text) for item in matches)
            if len(candidates) >= request.overall_candidate_limit:
                break
        return ProviderDiscoveryResult(
            provider_name=self.provider_name,
            candidates=tuple(candidates[: request.overall_candidate_limit]),
            queries_executed=tuple(executed),
            warnings=() if candidates else ("Local dataset returned no matching candidates.",),
        )

    def _load(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.dataset_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise MalformedDiscoverySourceError(
                f"Unable to load local discovery dataset: {self.dataset_path}"
            ) from error
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise MalformedDiscoverySourceError("Local discovery dataset must be a JSON list")
        return data

    @staticmethod
    def _search(records: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
        tokens = {
            token
            for token in re.findall(r"[a-z0-9]+", query.casefold())
            if len(token) > 1 and token not in _STOPWORDS
        }
        scored: list[tuple[int, str, dict[str, Any]]] = []
        for record in records:
            searchable = " ".join(
                str(value)
                for key, value in record.items()
                if key
                in {
                    "name",
                    "aliases",
                    "country",
                    "industry_tags",
                    "description",
                    "capabilities",
                    "customer_types",
                }
            ).casefold()
            score = sum(1 for token in tokens if token in searchable)
            if score:
                scored.append((score, str(record.get("name", "")), record))
        return [item for _, _, item in sorted(scored, key=lambda x: (-x[0], x[1].casefold()))]

    def _to_record(self, data: dict[str, Any], *, discovery_query: str) -> DiscoveredCompanyRecord:
        try:
            source_id = str(data["id"])
            return DiscoveredCompanyRecord(
                observed_name=str(data["name"]),
                provider_name=self.provider_name,
                source_name=self.dataset_path.name,
                source_type="curated_dataset",
                website=data.get("website"),
                aliases=tuple(str(item) for item in data.get("aliases", [])),
                country=data.get("country"),
                industry_tags=tuple(str(item) for item in data.get("industry_tags", [])),
                description=data.get("description"),
                source_uri=data.get("source_uri"),
                source_title=data.get("source_title") or str(data["name"]),
                source_identifier=source_id,
                discovery_query=discovery_query,
                raw_metadata=(("dataset_record_id", source_id),),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise MalformedDiscoverySourceError(
                f"Malformed local dataset record: {data.get('id', '<unknown>')}"
            ) from error


@dataclass(frozen=True, slots=True)
class UserSuppliedDiscoveryProvider:
    candidates: tuple[UserCandidateInput, ...]
    list_name: str = "user-supplied candidates"

    @property
    def provider_name(self) -> str:
        return "user_supplied"

    def discover(self, request: DiscoveryRequest) -> ProviderDiscoveryResult:
        now = datetime.now(UTC)
        records = tuple(
            DiscoveredCompanyRecord(
                observed_name=item.name,
                provider_name=self.provider_name,
                source_name=self.list_name,
                source_type="user_list",
                website=item.website,
                aliases=item.aliases,
                country=item.country,
                industry_tags=item.industry_tags,
                description=item.description,
                source_uri=item.source_reference,
                source_title=self.list_name,
                source_identifier=f"row-{index}",
                observed_at=now,
            )
            for index, item in enumerate(
                self.candidates[: request.overall_candidate_limit], start=1
            )
        )
        return ProviderDiscoveryResult(
            provider_name=self.provider_name,
            candidates=records,
            queries_executed=(),
            warnings=() if records else ("User-supplied candidate list was empty.",),
        )
