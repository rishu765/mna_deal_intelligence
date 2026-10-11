"""Rich offline fixture for Project 6 M3 reconciliation."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

from ma_deal_intelligence.evidence import EvidenceKind, EvidenceReference, ProjectId
from ma_deal_intelligence.finance import (
    DiligenceFindingReference,
    EstimateStatus,
    FinancialMetricReference,
    FinancialPeriodReference,
    FindingSeverity,
    FindingStatus,
    MetricBasis,
)
from ma_deal_intelligence.fixtures import representative_deal_state
from ma_deal_intelligence.outputs import DiligenceOutput, ProjectResultEnvelope
from ma_deal_intelligence.state import DealState
from ma_deal_intelligence.workflow import DealWarning, IssueSeverity, ResultStatus


def rich_reconciliation_state() -> DealState:
    """Return a five-project state with alignment, mismatches, risks, and stale inputs."""
    state = representative_deal_state()
    target_id = state.deal_context.target_entity_id
    assert target_id is not None
    period = FinancialPeriodReference("LTM 2025-12-31", date(2025, 1, 1), date(2025, 12, 31))
    fy_period = FinancialPeriodReference("FY2025", date(2025, 1, 1), date(2025, 12, 31))
    evidence = (
        *state.evidence,
        EvidenceReference(
            "ev:p1:revenue",
            ProjectId.PROJECT_1,
            EvidenceKind.DOCUMENT,
            document_id="doc:northstar-fy25",
            page_numbers=(40,),
            section="Revenue",
            excerpt="FY2025 revenue was GBP 500 million.",
            project_evidence_id="p1:revenue:500",
        ),
        EvidenceReference(
            "ev:p3:revenue",
            ProjectId.PROJECT_3,
            EvidenceKind.DOCUMENT,
            document_id="doc:northstar-fy25",
            page_numbers=(40,),
            section="Revenue",
            excerpt="FY2025 revenue was GBP 500 million.",
            project_evidence_id="p3:revenue:500",
        ),
        EvidenceReference(
            "ev:p5:customer-concentration",
            ProjectId.PROJECT_5,
            EvidenceKind.SPREADSHEET,
            document_id="vdr:customer-analysis",
            sheet_name="Customers",
            cell_range="B2:B11",
            excerpt="Top ten customers account for 42% of revenue.",
        ),
        EvidenceReference(
            "ev:p5:coc",
            ProjectId.PROJECT_5,
            EvidenceKind.DOCUMENT,
            document_id="vdr:top-customer-contract",
            page_numbers=(18,),
            section="Change of control",
            excerpt="Customer consent is required upon a change of control.",
        ),
        EvidenceReference(
            "ev:p5:net-debt",
            ProjectId.PROJECT_5,
            EvidenceKind.SPREADSHEET,
            document_id="vdr:net-debt-workbook",
            sheet_name="Net Debt",
            cell_range="F22",
            excerpt="Adjusted net debt is GBP 65 million.",
        ),
    )
    p1_revenue = FinancialMetricReference(
        "metric:p1:revenue-fy25",
        "Revenue",
        Decimal("500"),
        "GBP",
        "million",
        fy_period,
        MetricBasis.REPORTED,
        EstimateStatus.ACTUAL,
        ProjectId.PROJECT_1,
        "p1:fact:revenue-fy25",
        target_id,
        ("ev:p1:revenue",),
    )
    p3_revenue = replace(
        p1_revenue,
        metric_id="metric:p3:revenue-fy25",
        source_project=ProjectId.PROJECT_3,
        source_record_id="p3:profile:revenue-fy25",
        evidence_refs=("ev:p3:revenue",),
    )
    concentration = FinancialMetricReference(
        "metric:p5:customer-concentration",
        "Customer concentration",
        Decimal("42"),
        None,
        "percent",
        period,
        MetricBasis.ADJUSTED,
        EstimateStatus.ACTUAL,
        ProjectId.PROJECT_5,
        "p5:customers:top-ten",
        target_id,
        ("ev:p5:customer-concentration",),
    )
    net_debt = FinancialMetricReference(
        "metric:p5:adjusted-net-debt",
        "Net debt",
        Decimal("65"),
        "GBP",
        "million",
        period,
        MetricBasis.ADJUSTED,
        EstimateStatus.ACTUAL,
        ProjectId.PROJECT_5,
        "p5:net-debt:adjusted",
        target_id,
        ("ev:p5:net-debt",),
    )
    concentration_finding = DiligenceFindingReference(
        "finding:p5:customer-concentration",
        "commercial",
        "Customer concentration is 42%",
        FindingSeverity.HIGH,
        "42% of revenue from top ten customers",
        ("valuation", "customer_concentration"),
        FindingStatus.CONFIRMED,
        ProjectId.PROJECT_5,
        "p5:finding:customer-concentration",
        ("ev:p5:customer-concentration",),
    )
    contract_finding = DiligenceFindingReference(
        "finding:p5:change-of-control",
        "legal",
        "Change-of-control consent required",
        FindingSeverity.HIGH,
        "Potential closing condition",
        ("deal_execution", "contract_risk"),
        FindingStatus.UNDER_REVIEW,
        ProjectId.PROJECT_5,
        "p5:finding:coc",
        ("ev:p5:coc",),
    )
    net_debt_finding = DiligenceFindingReference(
        "finding:p5:net-debt",
        "financial",
        "Adjusted net debt is higher than management presentation",
        FindingSeverity.MEDIUM,
        "Equity value bridge impact",
        ("net_debt", "equity_value"),
        FindingStatus.CONFIRMED,
        ProjectId.PROJECT_5,
        "p5:finding:net-debt",
        ("ev:p5:net-debt",),
    )
    findings = (
        *state.diligence_findings,
        concentration_finding,
        contract_finding,
        net_debt_finding,
    )
    metrics = (*state.financial_metrics, p1_revenue, p3_revenue, concentration, net_debt)
    p3_valuation = replace(
        state.valuation_outputs[0],
        low=Decimal("850"),
        midpoint=Decimal("950"),
        high=Decimal("1050"),
    )
    p4_valuation = replace(
        state.valuation_outputs[1],
        low=Decimal("950"),
        midpoint=Decimal("1075"),
        high=Decimal("1200"),
        warning_ids=("warning:p4:low-sample",),
    )
    p3_result = replace(
        state.trading_comps_results[0],
        payload=replace(
            state.trading_comps_results[0].payload,
            financial_metrics=(state.financial_metrics[0], p3_revenue),
            valuations=(p3_valuation,),
        ),
    )
    p4_result = replace(
        state.precedent_transaction_results[0],
        payload=replace(
            state.precedent_transaction_results[0].payload,
            valuations=(p4_valuation,),
        ),
        warnings=(
            DealWarning(
                "warning:p4:low-sample",
                "LOW_SAMPLE_SIZE",
                IssueSeverity.MEDIUM,
                "Precedent range is based on two verified transactions.",
                ProjectId.PROJECT_4,
                affected_capability="p4.produce_valuation_range",
                evidence_refs=("ev:p4:precedent",),
            ),
        ),
    )
    diligence_output = DiligenceOutput(
        target_id,
        findings,
        (state.financial_metrics[1], concentration, net_debt),
        ("p5:missing:top-customer-consent",),
        ("conflict:ebitda-basis",),
        True,
        "p5:diligence-result:m3",
    )
    diligence_result = ProjectResultEnvelope(
        ProjectId.PROJECT_5,
        "p5.produce_diligence_findings",
        "run:p5:m3",
        ResultStatus.SUCCEEDED_WITH_WARNINGS,
        diligence_output,
        (
            "ev:p5:addback",
            "ev:p5:customer-concentration",
            "ev:p5:coc",
            "ev:p5:net-debt",
        ),
        (),
        (),
        (),
        datetime(2026, 1, 15, 12, tzinfo=UTC),
        datetime(2025, 12, 31, tzinfo=UTC),
        "1.0.0",
        tuple(item for item in evidence if item.source_project is ProjectId.PROJECT_5),
    )
    warnings = (
        DealWarning(
            "warning:p2:integration-risk",
            "STRATEGIC_INTEGRATION_RISK",
            IssueSeverity.MEDIUM,
            "Strong strategic fit depends on retaining specialist sales talent.",
            ProjectId.PROJECT_2,
        ),
        *p4_result.warnings,
    )
    return replace(
        state,
        trading_comps_results=(p3_result,),
        precedent_transaction_results=(p4_result,),
        diligence_results=(diligence_result,),
        financial_metrics=metrics,
        valuation_outputs=(p3_valuation, p4_valuation),
        diligence_findings=findings,
        evidence=evidence,
        warnings=warnings,
        revision=3,
    )
