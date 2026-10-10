"""Capability metadata and adapter interfaces for Projects 1-5."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, Protocol, TypeVar, runtime_checkable

from ma_deal_intelligence.evidence import ProjectId
from ma_deal_intelligence.identity import DealContext
from ma_deal_intelligence.outputs import (
    CompanyIntelligenceOutput,
    DiligenceOutput,
    PrecedentTransactionsOutput,
    ProjectResultEnvelope,
    TargetScreeningOutput,
    TradingCompsOutput,
)

InputT = TypeVar("InputT", contravariant=True)
OutputT = TypeVar("OutputT", covariant=True)


class ExecutionNature(StrEnum):
    DETERMINISTIC = "deterministic"
    AI_ASSISTED = "ai_assisted"
    HYBRID = "hybrid"


class CapabilityId(StrEnum):
    P1_INGEST_DOCUMENTS = "p1.ingest_documents"
    P1_RETRIEVE_COMPANY_EVIDENCE = "p1.retrieve_company_evidence"
    P1_EXTRACT_COMPANY_INTELLIGENCE = "p1.extract_company_intelligence"
    P1_RETRIEVE_FINANCIAL_FACTS = "p1.retrieve_financial_facts"
    P1_PROVIDE_CITED_ANSWERS = "p1.provide_cited_answers"
    P2_SOURCE_TARGETS = "p2.source_targets"
    P2_SCREEN_TARGETS = "p2.screen_targets"
    P2_SCORE_CANDIDATES = "p2.score_candidates"
    P2_ASSESS_STRATEGIC_FIT = "p2.assess_strategic_fit"
    P2_BUILD_CANDIDATE_PROFILES = "p2.build_candidate_profiles"
    P3_SELECT_TRADING_COMPARABLES = "p3.select_trading_comparables"
    P3_ANALYZE_TRADING_MULTIPLES = "p3.analyze_trading_multiples"
    P3_PRODUCE_VALUATION_RANGE = "p3.produce_valuation_range"
    P3_PRODUCE_PEER_STATISTICS = "p3.produce_peer_statistics"
    P4_DISCOVER_TRANSACTIONS = "p4.discover_transactions"
    P4_SELECT_PRECEDENTS = "p4.select_precedents"
    P4_ANALYZE_TRANSACTION_MULTIPLES = "p4.analyze_transaction_multiples"
    P4_PRODUCE_VALUATION_RANGE = "p4.produce_valuation_range"
    P5_PRODUCE_DILIGENCE_FINDINGS = "p5.produce_diligence_findings"
    P5_ANALYZE_QOE = "p5.analyze_qoe"
    P5_CALCULATE_ADJUSTED_EBITDA = "p5.calculate_adjusted_ebitda"
    P5_ANALYZE_WORKING_CAPITAL = "p5.analyze_working_capital"
    P5_ANALYZE_NET_DEBT = "p5.analyze_net_debt"
    P5_ANALYZE_CUSTOMER_CONCENTRATION = "p5.analyze_customer_concentration"
    P5_ANALYZE_CONTRACT_RISKS = "p5.analyze_contract_risks"
    P5_IDENTIFY_COMPOUND_RISKS = "p5.identify_compound_risks"
    P5_IDENTIFY_MISSING_INFORMATION = "p5.identify_missing_information"
    P5_GET_ANALYST_REVIEW_STATE = "p5.get_analyst_review_state"


@dataclass(frozen=True, slots=True)
class SchemaReference:
    module: str
    model: str
    schema_version: str


@dataclass(frozen=True, slots=True)
class ProjectCapability:
    capability_id: str
    project_id: ProjectId
    name: str
    description: str
    input_schema: SchemaReference
    output_schema: SchemaReference
    required_dependencies: tuple[str, ...] = ()
    optional_dependencies: tuple[str, ...] = ()
    can_run_standalone: bool = True
    execution_nature: ExecutionNature = ExecutionNature.DETERMINISTIC
    requires_human_review: bool = False
    supports_offline_mode: bool = True
    version: str = "1.0.0"


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.valid and self.errors:
            raise ValueError("valid input cannot have validation errors")


@dataclass(frozen=True, slots=True)
class HealthStatus:
    healthy: bool
    message: str | None = None


@runtime_checkable
class ProjectAdapter(Protocol, Generic[InputT, OutputT]):
    def capability_metadata(self) -> tuple[ProjectCapability, ...]: ...

    def validate_input(self, capability_id: str, request: InputT) -> ValidationResult: ...

    def invoke(self, capability_id: str, request: InputT) -> ProjectResultEnvelope[OutputT]: ...

    def health_check(self) -> HealthStatus: ...


@dataclass(frozen=True, slots=True)
class DocumentIntelligenceRequest:
    deal_context: DealContext
    entity_id: str
    document_ids: tuple[str, ...] = ()
    question: str | None = None


@dataclass(frozen=True, slots=True)
class TargetScreeningRequest:
    deal_context: DealContext
    acquisition_criteria_id: str


@dataclass(frozen=True, slots=True)
class TradingCompsRequest:
    deal_context: DealContext
    target_entity_id: str
    target_financial_profile_id: str


@dataclass(frozen=True, slots=True)
class PrecedentTransactionsRequest:
    deal_context: DealContext
    target_entity_id: str
    search_criteria_id: str


@dataclass(frozen=True, slots=True)
class DiligenceRequest:
    deal_context: DealContext
    target_entity_id: str
    vdr_document_ids: tuple[str, ...]
    requested_workstreams: tuple[str, ...] = ()


class Project1Adapter(
    ProjectAdapter[DocumentIntelligenceRequest, CompanyIntelligenceOutput], Protocol
):
    """Future boundary for ingest, retrieval, extraction, financial facts, and cited answers."""


class Project2Adapter(ProjectAdapter[TargetScreeningRequest, TargetScreeningOutput], Protocol):
    """Future boundary for sourcing, screening, scoring, fit, and candidate profiles."""


class Project3Adapter(ProjectAdapter[TradingCompsRequest, TradingCompsOutput], Protocol):
    """Future boundary for peer selection and deterministic trading-comps valuation."""


class Project4Adapter(
    ProjectAdapter[PrecedentTransactionsRequest, PrecedentTransactionsOutput], Protocol
):
    """Future boundary for transaction discovery, selection, multiples, and valuation."""


class Project5Adapter(ProjectAdapter[DiligenceRequest, DiligenceOutput], Protocol):
    """Future boundary for diligence findings, QoE, bridges, risks, and review states."""
