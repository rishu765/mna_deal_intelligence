"""Project 4 precedent-transactions adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ma_deal_intelligence.adapters.base import BaseAdapter, NativeProjectResult
from ma_deal_intelligence.contracts import (
    CapabilityId,
    ExecutionNature,
    PrecedentTransactionsRequest,
    ProjectCapability,
    SchemaReference,
)
from ma_deal_intelligence.evidence import ProjectId
from ma_deal_intelligence.fixtures import representative_deal_state
from ma_deal_intelligence.outputs import PrecedentTransactionsOutput


@dataclass(frozen=True, slots=True)
class Project4NativeRequest:
    target_entity_id: str
    search_criteria_id: str
    sectors: tuple[str, ...]
    as_of_date: date


class Project4Adapter(
    BaseAdapter[PrecedentTransactionsRequest, Project4NativeRequest, PrecedentTransactionsOutput]
):
    project_id = ProjectId.PROJECT_4
    supported_capabilities = (
        ProjectCapability(
            CapabilityId.P4_PRODUCE_VALUATION_RANGE,
            project_id,
            "Precedent-transactions valuation",
            "Use Project 4 discovery, verification, selection, multiples, and valuation services.",
            SchemaReference(
                "ma_deal_intelligence.contracts", "PrecedentTransactionsRequest", "1.0.0"
            ),
            SchemaReference("ma_deal_intelligence.outputs", "PrecedentTransactionsOutput", "1.0.0"),
            execution_nature=ExecutionNature.HYBRID,
            required_inputs=("target_entity", "sector_context"),
            produced_outputs=("precedent_transactions", "valuation"),
        ),
    )

    def _validation_errors(self, request: PrecedentTransactionsRequest) -> tuple[str, ...]:
        errors: list[str] = []
        if not request.target_entity_id.strip():
            errors.append("target entity identity is required")
        if not request.search_criteria_id.strip():
            errors.append("precedent search criteria are required")
        if not request.deal_context.sectors:
            errors.append("target sector context is required")
        if request.deal_context.as_of_date is None:
            errors.append("analysis as-of date is required")
        return tuple(errors)

    def translate_input(self, request: PrecedentTransactionsRequest) -> Project4NativeRequest:
        assert request.deal_context.as_of_date is not None
        return Project4NativeRequest(
            request.target_entity_id,
            request.search_criteria_id,
            request.deal_context.sectors,
            request.deal_context.as_of_date,
        )

    def fixture_result(
        self, request: Project4NativeRequest
    ) -> NativeProjectResult[PrecedentTransactionsOutput]:
        state = representative_deal_state()
        source = state.precedent_transaction_results[0]
        evidence_ids = {
            evidence_id
            for transaction in source.payload.selected_transactions
            for evidence_id in transaction.evidence_refs
        }
        evidence = tuple(item for item in state.evidence if item.evidence_id in evidence_ids)
        return NativeProjectResult(
            source.payload, evidence, source.warnings, data_as_of=source.data_as_of
        )
