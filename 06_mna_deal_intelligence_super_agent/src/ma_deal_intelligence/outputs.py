"""Typed specialist payloads and their common result envelope."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Generic, TypeVar

from ma_deal_intelligence.evidence import ProjectId
from ma_deal_intelligence.finance import (
    DiligenceFindingReference,
    FinancialMetricReference,
    ValuationReference,
)
from ma_deal_intelligence.identity import CanonicalEntityReference
from ma_deal_intelligence.workflow import DealError, DealWarning, ResultStatus

PayloadT = TypeVar("PayloadT", covariant=True)


@dataclass(frozen=True, slots=True)
class ProjectResultEnvelope(Generic[PayloadT]):
    source_project: ProjectId
    capability: str
    run_id: str
    status: ResultStatus
    payload: PayloadT
    evidence_refs: tuple[str, ...]
    assumption_ids: tuple[str, ...]
    warnings: tuple[DealWarning, ...]
    errors: tuple[DealError, ...]
    generated_at: datetime
    data_as_of: datetime | None
    schema_version: str

    def __post_init__(self) -> None:
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        if self.data_as_of is not None and (
            self.data_as_of.tzinfo is None or self.data_as_of.utcoffset() is None
        ):
            raise ValueError("data_as_of must be timezone-aware")
        if self.status is ResultStatus.FAILED and not self.errors:
            raise ValueError("failed results require at least one error")


@dataclass(frozen=True, slots=True)
class CompanyIntelligenceOutput:
    entity_id: str
    source_document_ids: tuple[str, ...]
    research_profile_id: str | None = None
    cited_answer_ids: tuple[str, ...] = ()
    financial_metric_ids: tuple[str, ...] = ()
    summary: str | None = None


@dataclass(frozen=True, slots=True)
class TargetCandidateReference:
    entity: CanonicalEntityReference
    rank: int
    score: str
    eligibility: str
    rationale: str | None
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TargetScreeningOutput:
    thesis_id: str
    candidates: tuple[TargetCandidateReference, ...]
    shortlist_name: str | None = None


@dataclass(frozen=True, slots=True)
class TradingCompsOutput:
    target_entity_id: str
    peer_entity_ids: tuple[str, ...]
    financial_metrics: tuple[FinancialMetricReference, ...]
    valuations: tuple[ValuationReference, ...]
    source_output_id: str


@dataclass(frozen=True, slots=True)
class PrecedentTransactionReference:
    transaction_id: str
    acquirer_entity_id: str | None
    target_entity_id: str | None
    transaction_status: str
    valuation_basis: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PrecedentTransactionsOutput:
    selected_transactions: tuple[PrecedentTransactionReference, ...]
    financial_metrics: tuple[FinancialMetricReference, ...]
    valuations: tuple[ValuationReference, ...]
    source_output_id: str


@dataclass(frozen=True, slots=True)
class DiligenceOutput:
    target_entity_id: str
    findings: tuple[DiligenceFindingReference, ...]
    financial_metrics: tuple[FinancialMetricReference, ...]
    missing_information_ids: tuple[str, ...]
    conflict_ids: tuple[str, ...]
    analyst_review_required: bool
    source_output_id: str
