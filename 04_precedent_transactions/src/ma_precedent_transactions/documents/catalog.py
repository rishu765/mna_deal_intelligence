"""Fixture-backed deal document discovery."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ma_precedent_transactions.documents.models import (
    DealDocumentSource,
    DealSourceType,
    DocumentFormat,
)
from ma_precedent_transactions.domain import SourceReliability
from ma_precedent_transactions.errors import MalformedFixtureError


@dataclass(frozen=True, slots=True)
class FixtureDocumentCatalog:
    catalog_path: Path

    def find_for_transactions(
        self, transaction_ids: tuple[str, ...]
    ) -> tuple[DealDocumentSource, ...]:
        requested = set(transaction_ids)
        sources = [self._source(item) for item in self._load()]
        unique: dict[str, DealDocumentSource] = {}
        checksum_ids: set[tuple[str, str]] = set()
        for source in sources:
            if source.transaction_id not in requested:
                continue
            existing = unique.get(source.source_id)
            if existing is not None and existing != source:
                raise MalformedFixtureError(
                    f"source_id {source.source_id!r} maps to conflicting documents"
                )
            checksum_key = (source.transaction_id, source.checksum_sha256 or "")
            if source.checksum_sha256 and checksum_key in checksum_ids:
                continue
            unique[source.source_id] = source
            if source.checksum_sha256:
                checksum_ids.add(checksum_key)
        return tuple(unique.values())

    def _load(self) -> list[dict[str, Any]]:
        try:
            payload = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise MalformedFixtureError(
                f"Unable to load document catalog: {self.catalog_path}"
            ) from error
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise MalformedFixtureError("document catalog must be a JSON list of objects")
        return payload

    @staticmethod
    def _source(item: dict[str, Any]) -> DealDocumentSource:
        try:
            return DealDocumentSource(
                source_id=str(item["source_id"]),
                transaction_id=str(item["transaction_id"]),
                source_type=DealSourceType(str(item["source_type"])),
                title=str(item["title"]),
                location=str(item["location"]),
                publisher=str(item["publisher"]),
                publication_date=(
                    None
                    if item.get("publication_date") is None
                    else date.fromisoformat(str(item["publication_date"]))
                ),
                jurisdiction=None
                if item.get("jurisdiction") is None
                else str(item["jurisdiction"]),
                document_format=DocumentFormat(str(item["document_format"])),
                retrieved_at=datetime.fromisoformat(str(item["retrieved_at"])),
                reliability=SourceReliability(str(item["reliability"])),
                official_source=bool(item["official_source"]),
                checksum_sha256=(
                    None if item.get("checksum_sha256") is None else str(item["checksum_sha256"])
                ),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise MalformedFixtureError(
                f"Malformed document catalog record: {item.get('source_id', '<unknown>')}"
            ) from error
