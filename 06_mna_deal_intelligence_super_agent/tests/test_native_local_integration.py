from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ma_deal_intelligence.adapters import AdapterMode, AdapterValidationError, Project1Adapter
from ma_deal_intelligence.adapters.base import NativeProjectResult
from ma_deal_intelligence.adapters.project1 import Project1NativeRequest
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
from ma_deal_intelligence.outputs import CompanyIntelligenceOutput
from ma_deal_intelligence.portfolio_evaluation import evaluate_native_local

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROJECT_2_ROOT = REPOSITORY_ROOT / "02_target_screening_sourcing"
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


def test_native_local_registry_executes_all_five_specialists(tmp_path: Path) -> None:
    demo = pytest.importorskip("ma_company_intelligence.demo_document")
    document_path = demo.create_demo_pdf(tmp_path / "apex.pdf")
    registry = build_native_local_registry(
        NativeLocalSettings(PROJECT_2_ROOT, {"doc:apex": document_path})
    )

    p1_context = DealContext("deal:p1", target_entity_id="apex")
    p1 = registry.adapter(CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE).invoke(
        CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE,
        DocumentIntelligenceRequest(p1_context, "apex", ("doc:apex",)),
    )
    assert p1.run_id.startswith("native:")
    assert p1.payload.financial_metric_ids
    assert p1.evidence[0].document_id == "doc:apex"
    assert p1.evidence[0].page_numbers

    p2_context = DealContext("deal:p2", sectors=("Payments",), geographies=("India",))
    p2 = registry.adapter(CapabilityId.P2_SCREEN_TARGETS).invoke(
        CapabilityId.P2_SCREEN_TARGETS,
        TargetScreeningRequest(p2_context, "india-payments-screening-demo"),
    )
    assert len(p2.payload.candidates) == 4
    assert [item.rank for item in p2.payload.candidates] == [1, 2, 3, 4]
    assert all(item.entity.evidence_refs for item in p2.payload.candidates)

    p3_context = DealContext(
        "deal:p3",
        target_entity_id="targetco",
        reporting_currency="INR",
        as_of_date=date(2026, 10, 7),
    )
    p3 = registry.adapter(CapabilityId.P3_PRODUCE_VALUATION_RANGE).invoke(
        CapabilityId.P3_PRODUCE_VALUATION_RANGE,
        TradingCompsRequest(p3_context, "targetco", "profile:targetco"),
    )
    assert len(p3.payload.valuations) == 2
    assert {item.currency for item in p3.payload.valuations} == {"INR"}
    assert all(item.low <= item.midpoint <= item.high for item in p3.payload.valuations)
    assert {item.period.label for item in p3.payload.financial_metrics} >= {"LTM Jun-2026"}
    assert p3.data_as_of is not None and p3.data_as_of.date() == date(2026, 10, 7)

    p4_context = DealContext(
        "deal:p4",
        target_entity_id="target-fintech",
        sectors=("B2B fintech infrastructure",),
        as_of_date=date(2025, 12, 31),
    )
    p4 = registry.adapter(CapabilityId.P4_PRODUCE_VALUATION_RANGE).invoke(
        CapabilityId.P4_PRODUCE_VALUATION_RANGE,
        PrecedentTransactionsRequest(p4_context, "target-fintech", "search:fintech"),
    )
    assert len(p4.payload.selected_transactions) == 5
    assert len(p4.payload.valuations) == 5
    assert all(item.evidence_refs for item in p4.payload.selected_transactions)
    assert p4.data_as_of is not None and p4.data_as_of.date() == date(2025, 12, 31)

    p5_context = DealContext(
        "deal:p5",
        engagement_id="engagement:northstar",
        target_entity_id="target-northstar",
    )
    p5 = registry.adapter(CapabilityId.P5_PRODUCE_DILIGENCE_FINDINGS).invoke(
        CapabilityId.P5_PRODUCE_DILIGENCE_FINDINGS,
        DiligenceRequest(p5_context, "target-northstar", P5_DOCUMENTS),
    )
    by_type = {item.metric_type: item for item in p5.payload.financial_metrics}
    ebitda = [item for item in p5.payload.financial_metrics if item.metric_type == "ebitda"]
    assert [item.value for item in ebitda] == [14, 15]
    assert by_type["nwc_peg"].value == Decimal("9.309090909090909090909090909")
    assert by_type["net_debt"].value == 20
    assert p5.payload.analyst_review_required
    assert any(item.document_id == "doc-bridge" for item in p5.evidence)
    assert p5.data_as_of is not None and p5.data_as_of.date() == date(2025, 12, 31)

    for envelope in (p2, p3, p4, p5):
        codes = {item.code for item in envelope.warnings}
        assert "OFFLINE_SPECIALIST_FIXTURE" in codes
        assert "FIXTURE_DATA" not in codes


def test_native_local_project3_rejects_cross_currency_request() -> None:
    registry = build_native_local_registry(NativeLocalSettings(PROJECT_2_ROOT, {}))
    context = DealContext(
        "deal:p3",
        target_entity_id="targetco",
        reporting_currency="USD",
        as_of_date=date(2026, 10, 7),
    )
    with pytest.raises(ValueError, match="currency"):
        registry.adapter(CapabilityId.P3_PRODUCE_VALUATION_RANGE).invoke(
            CapabilityId.P3_PRODUCE_VALUATION_RANGE,
            TradingCompsRequest(context, "targetco", "profile:targetco"),
        )


def test_native_local_project5_rejects_missing_evidence_document() -> None:
    registry = build_native_local_registry(NativeLocalSettings(PROJECT_2_ROOT, {}))
    context = DealContext(
        "deal:p5",
        engagement_id="engagement:northstar",
        target_entity_id="target-northstar",
    )
    with pytest.raises(ValueError, match="requires fixture documents"):
        registry.adapter(CapabilityId.P5_PRODUCE_DILIGENCE_FINDINGS).invoke(
            CapabilityId.P5_PRODUCE_DILIGENCE_FINDINGS,
            DiligenceRequest(context, "target-northstar", ("doc-audited",)),
        )


def test_adapter_rejects_incompatible_native_schema() -> None:
    context = DealContext("deal:schema", target_entity_id="entity:test")

    def execute(
        request: Project1NativeRequest,
    ) -> NativeProjectResult[CompanyIntelligenceOutput]:
        return NativeProjectResult(
            CompanyIntelligenceOutput(request.entity_id, request.document_ids),
            schema_version="2.0.0",
        )

    adapter = Project1Adapter(mode=AdapterMode.NATIVE, native_executor=execute)
    request = DocumentIntelligenceRequest(context, "entity:test", ("doc:test",))
    with pytest.raises(AdapterValidationError, match="incompatible specialist result schema"):
        adapter.invoke(CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE, request)


def test_native_local_project3_rejects_wrong_entity() -> None:
    registry = build_native_local_registry(NativeLocalSettings(PROJECT_2_ROOT, {}))
    context = DealContext(
        "deal:p3",
        target_entity_id="entity:other",
        reporting_currency="INR",
        as_of_date=date(2026, 10, 7),
    )
    request = TradingCompsRequest(context, "entity:other", "profile:other")
    with pytest.raises(ValueError, match="target"):
        registry.adapter(CapabilityId.P3_PRODUCE_VALUATION_RANGE).invoke(
            CapabilityId.P3_PRODUCE_VALUATION_RANGE,
            request,
        )


def test_native_local_project3_rejects_mismatched_as_of_date() -> None:
    registry = build_native_local_registry(NativeLocalSettings(PROJECT_2_ROOT, {}))
    context = DealContext(
        "deal:p3",
        target_entity_id="targetco",
        reporting_currency="INR",
        as_of_date=date(2026, 10, 8),
    )
    request = TradingCompsRequest(context, "targetco", "profile:targetco")
    with pytest.raises(ValueError, match="as-of date"):
        registry.adapter(CapabilityId.P3_PRODUCE_VALUATION_RANGE).invoke(
            CapabilityId.P3_PRODUCE_VALUATION_RANGE,
            request,
        )


def test_native_result_schema_default_remains_compatible() -> None:
    result = NativeProjectResult(CompanyIntelligenceOutput("entity:test", ("doc:test",)))
    assert result.schema_version == "1.0.0"
    assert replace(result, schema_version="1.0.0") == result


def test_native_local_evaluation_is_run_derived(tmp_path: Path) -> None:
    demo = pytest.importorskip("ma_company_intelligence.demo_document")
    document_path = demo.create_demo_pdf(tmp_path / "evaluation.pdf")
    report = evaluate_native_local(
        NativeLocalSettings(PROJECT_2_ROOT, {"doc:evaluation": document_path})
    )

    assert report.deterministic
    assert report.passed == report.total == 5
    assert all(item.mode == "native_local_offline_inputs" for item in report.observations)
    assert all("this execution" in item.notes for item in report.observations)
