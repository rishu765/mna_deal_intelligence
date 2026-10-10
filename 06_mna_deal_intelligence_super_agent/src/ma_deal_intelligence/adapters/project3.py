"""Project 3 comparable-company valuation adapter."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

from ma_deal_intelligence.adapters.base import BaseAdapter, NativeProjectResult
from ma_deal_intelligence.contracts import (
    CapabilityId,
    ExecutionNature,
    ProjectCapability,
    SchemaReference,
    TradingCompsRequest,
)
from ma_deal_intelligence.evidence import ProjectId
from ma_deal_intelligence.fixtures import representative_deal_state
from ma_deal_intelligence.outputs import TradingCompsOutput


@dataclass(frozen=True, slots=True)
class Project3NativeRequest:
    target_entity_id: str
    target_financial_profile_id: str
    reporting_currency: str
    as_of_date: date


class Project3Adapter(BaseAdapter[TradingCompsRequest, Project3NativeRequest, TradingCompsOutput]):
    project_id = ProjectId.PROJECT_3
    supported_capabilities = (
        ProjectCapability(
            CapabilityId.P3_PRODUCE_VALUATION_RANGE,
            project_id,
            "Trading-comps valuation",
            "Use Project 3 peer selection, multiples, statistics, and valuation engine.",
            SchemaReference("ma_deal_intelligence.contracts", "TradingCompsRequest", "1.0.0"),
            SchemaReference("ma_deal_intelligence.outputs", "TradingCompsOutput", "1.0.0"),
            execution_nature=ExecutionNature.HYBRID,
            required_inputs=("target_entity", "target_financials", "reporting_currency"),
            produced_outputs=("trading_comps", "valuation", "peer_statistics"),
        ),
    )

    def _validation_errors(self, request: TradingCompsRequest) -> tuple[str, ...]:
        errors: list[str] = []
        if not request.target_entity_id.strip():
            errors.append("target entity identity is required")
        if not request.target_financial_profile_id.strip():
            errors.append("target financial profile is required")
        if request.deal_context.reporting_currency is None:
            errors.append("reporting currency is required")
        if request.deal_context.as_of_date is None:
            errors.append("valuation as-of date is required")
        return tuple(errors)

    def translate_input(self, request: TradingCompsRequest) -> Project3NativeRequest:
        assert request.deal_context.reporting_currency is not None
        assert request.deal_context.as_of_date is not None
        return Project3NativeRequest(
            request.target_entity_id,
            request.target_financial_profile_id,
            request.deal_context.reporting_currency,
            request.deal_context.as_of_date,
        )

    def fixture_result(
        self, request: Project3NativeRequest
    ) -> NativeProjectResult[TradingCompsOutput]:
        state = representative_deal_state()
        source = state.trading_comps_results[0]
        payload = replace(source.payload, target_entity_id=request.target_entity_id)
        evidence_ids = {
            evidence_id
            for valuation in source.payload.valuations
            for evidence_id in valuation.evidence_refs
        }
        evidence = tuple(item for item in state.evidence if item.evidence_id in evidence_ids)
        return NativeProjectResult(payload, evidence, source.warnings, data_as_of=source.data_as_of)
