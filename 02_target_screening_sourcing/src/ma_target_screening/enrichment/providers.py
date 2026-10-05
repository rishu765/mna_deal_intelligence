"""Deterministic structured-fixture candidate enrichment provider."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ma_target_screening.enrichment.models import EnrichmentRequest, ProviderEnrichmentResult
from ma_target_screening.errors import MalformedEnrichmentSourceError
from ma_target_screening.profile import (
    EnrichmentEvidence,
    EvidenceQuality,
    ProfileFact,
    ProfileField,
    ProfileFinancialMetric,
    ProfileInference,
    UnknownField,
)


@dataclass(frozen=True, slots=True)
class StructuredFixtureEnrichmentProvider:
    fixture_path: Path

    @property
    def provider_name(self) -> str:
        return "structured_fixture"

    def enrich(self, request: EnrichmentRequest) -> ProviderEnrichmentResult:
        data = self._load()
        record = self._find(data, request)
        if record is None:
            return ProviderEnrichmentResult(
                provider_name=self.provider_name,
                unknown_fields=tuple(
                    UnknownField(field, "No fixture enrichment record was available.")
                    for field in request.priority_fields
                ),
                warnings=("No fixture enrichment record matched the candidate.",),
            )
        try:
            evidence = {
                item["evidence_id"]: self._evidence(item) for item in record.get("evidence", [])
            }
            facts = tuple(
                ProfileFact(
                    field=ProfileField(item["field"]),
                    value=item["value"],
                    raw_value=item.get("raw_value"),
                    evidence=self._resolve(evidence, item["evidence_ids"]),
                )
                for item in record.get("facts", [])
            )
            inferences = tuple(
                ProfileInference(
                    field=ProfileField(item["field"]),
                    statement=item["statement"],
                    rationale=item.get("rationale"),
                    evidence=self._resolve(evidence, item["evidence_ids"]),
                )
                for item in record.get("inferences", [])
            )
            metrics = tuple(
                ProfileFinancialMetric(
                    metric_name=item["metric_name"],
                    value=item["value"],
                    fiscal_period=item.get("fiscal_period"),
                    unit=item.get("unit"),
                    currency=item.get("currency"),
                    basis=item.get("basis"),
                    evidence=self._resolve(evidence, item["evidence_ids"]),
                )
                for item in record.get("financial_metrics", [])
            )
            unknowns = tuple(
                UnknownField(ProfileField(item["field"]), item["reason"])
                for item in record.get("unknown_fields", [])
            )
            covered = {fact.field for fact in facts}
            if metrics:
                covered.add(ProfileField.FINANCIALS)
            known_unknowns = {item.field for item in unknowns}
            requested_unknowns = tuple(
                UnknownField(field, "Fixture did not contain this thesis-prioritized field.")
                for field in request.priority_fields
                if field not in covered and field not in known_unknowns
            )
            return ProviderEnrichmentResult(
                provider_name=self.provider_name,
                facts=facts,
                inferences=inferences,
                financial_metrics=metrics,
                unknown_fields=(*unknowns, *requested_unknowns),
                warnings=tuple(record.get("warnings", [])),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise MalformedEnrichmentSourceError(
                "Malformed structured enrichment fixture"
            ) from error

    def _load(self) -> list[dict[str, Any]]:
        try:
            value = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise MalformedEnrichmentSourceError(
                f"Unable to load enrichment fixture: {self.fixture_path}"
            ) from error
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise MalformedEnrichmentSourceError("Enrichment fixture must be a JSON list")
        return value

    @staticmethod
    def _find(records: list[dict[str, Any]], request: EnrichmentRequest) -> dict[str, Any] | None:
        domain = request.candidate.website_domain
        name = request.candidate.canonical_name.casefold()
        return next(
            (
                item
                for item in records
                if (domain and item.get("website_domain", "").casefold() == domain.casefold())
                or item.get("canonical_name", "").casefold() == name
            ),
            None,
        )

    def _evidence(self, data: dict[str, Any]) -> EnrichmentEvidence:
        return EnrichmentEvidence(
            evidence_id=data["evidence_id"],
            provider_name=self.provider_name,
            source_type=data["source_type"],
            source_title=data["source_title"],
            source_reference=data.get("source_reference"),
            document_id=data.get("document_id"),
            chunk_id=data.get("chunk_id"),
            page_numbers=tuple(data.get("page_numbers", [])),
            excerpt=data.get("excerpt"),
            extraction_method=data.get("extraction_method", "structured_fixture"),
            quality=EvidenceQuality(data.get("quality", "unknown")),
        )

    @staticmethod
    def _resolve(
        catalog: dict[str, EnrichmentEvidence], evidence_ids: list[str]
    ) -> tuple[EnrichmentEvidence, ...]:
        try:
            resolved = tuple(catalog[evidence_id] for evidence_id in evidence_ids)
        except KeyError as error:
            raise ValueError(f"unknown fixture evidence ID: {error.args[0]}") from error
        if not resolved:
            raise ValueError("fixture claims must cite evidence")
        return resolved
