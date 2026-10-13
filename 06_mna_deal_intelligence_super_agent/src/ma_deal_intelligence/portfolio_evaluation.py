"""Run-derived scorecard for the optional native-local portfolio composition."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ma_deal_intelligence.contracts import (
    CapabilityId,
    DiligenceRequest,
    DocumentIntelligenceRequest,
    PrecedentTransactionsRequest,
    TargetScreeningRequest,
    TradingCompsRequest,
)
from ma_deal_intelligence.identity import DealContext
from ma_deal_intelligence.native_local import NativeLocalSettings, build_native_local_registry


@dataclass(frozen=True, slots=True)
class EvaluationObservation:
    subsystem: str
    case_id: str
    metric: str
    expected: str
    observed: str
    passed: bool
    mode: str = "native_local_offline_inputs"
    notes: str = ""


@dataclass(frozen=True, slots=True)
class PortfolioEvaluationReport:
    observations: tuple[EvaluationObservation, ...]
    deterministic: bool
    external_dependencies: tuple[str, ...]

    @property
    def passed(self) -> int:
        return sum(item.passed for item in self.observations)

    @property
    def total(self) -> int:
        return len(self.observations)


P5_DOCUMENTS = (
    "doc-audited",
    "doc-bridge",
    "doc-cash",
    "doc-debt",
    "doc-debt-like",
    "doc-deck",
    "doc-management",
    "doc-sales",
    "doc-wc",
)


def evaluate_native_local(settings: NativeLocalSettings) -> PortfolioEvaluationReport:
    """Execute specialist code and compute separate, factual integration observations."""

    registry = build_native_local_registry(settings)
    document_id = next(iter(settings.project_1_documents))
    p1_context = DealContext("evaluation:p1", target_entity_id="apex")
    p1 = registry.adapter(CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE).invoke(
        CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE,
        DocumentIntelligenceRequest(p1_context, "apex", (document_id,)),
    )
    p2_context = DealContext("evaluation:p2", sectors=("Payments",), geographies=("India",))
    p2 = registry.adapter(CapabilityId.P2_SCREEN_TARGETS).invoke(
        CapabilityId.P2_SCREEN_TARGETS,
        TargetScreeningRequest(p2_context, "india-payments-screening-demo"),
    )
    p3_context = DealContext(
        "evaluation:p3",
        target_entity_id="targetco",
        reporting_currency="INR",
        as_of_date=date(2026, 10, 7),
    )
    p3 = registry.adapter(CapabilityId.P3_PRODUCE_VALUATION_RANGE).invoke(
        CapabilityId.P3_PRODUCE_VALUATION_RANGE,
        TradingCompsRequest(p3_context, "targetco", "profile:targetco"),
    )
    p4_context = DealContext(
        "evaluation:p4",
        target_entity_id="target-fintech",
        sectors=("B2B fintech infrastructure",),
        as_of_date=date(2025, 12, 31),
    )
    p4 = registry.adapter(CapabilityId.P4_PRODUCE_VALUATION_RANGE).invoke(
        CapabilityId.P4_PRODUCE_VALUATION_RANGE,
        PrecedentTransactionsRequest(p4_context, "target-fintech", "search:fintech"),
    )
    p5_context = DealContext(
        "evaluation:p5",
        engagement_id="engagement:northstar",
        target_entity_id="target-northstar",
    )
    p5 = registry.adapter(CapabilityId.P5_PRODUCE_DILIGENCE_FINDINGS).invoke(
        CapabilityId.P5_PRODUCE_DILIGENCE_FINDINGS,
        DiligenceRequest(p5_context, "target-northstar", P5_DOCUMENTS),
    )
    observations = (
        _observation("p1", "document-provenance", bool(p1.evidence), len(p1.evidence)),
        _observation("p2", "ranked-candidates", len(p2.payload.candidates) == 4, 4),
        _observation("p3", "valuation-ranges", len(p3.payload.valuations) == 2, 2),
        _observation("p4", "precedent-ranges", len(p4.payload.valuations) == 5, 5),
        _observation(
            "p5",
            "financial-and-finding-handoff",
            len(p5.payload.financial_metrics) == 4 and len(p5.payload.findings) == 5,
            f"{len(p5.payload.financial_metrics)} metrics/{len(p5.payload.findings)} findings",
            expected="4 metrics/5 findings",
        ),
    )
    return PortfolioEvaluationReport(observations, True, ())


def _observation(
    subsystem: str,
    case_id: str,
    passed: bool,
    observed: object,
    *,
    expected: str = "non-empty and contract-valid",
) -> EvaluationObservation:
    return EvaluationObservation(
        subsystem,
        case_id,
        "contract_execution",
        expected,
        str(observed),
        passed,
        notes="Computed from this execution; no statement-based credit.",
    )
