"""Synthetic M0 integration-contract fixtures; no specialist is invoked."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from ma_deal_intelligence.evidence import (
    EvidenceKind,
    EvidenceReference,
    LineageEdge,
    LineageGraph,
    LineageNode,
    LineageNodeKind,
    ProjectId,
)
from ma_deal_intelligence.finance import (
    DiligenceFindingReference,
    EstimateStatus,
    FinancialMetricReference,
    FinancialPeriodReference,
    FindingSeverity,
    FindingStatus,
    MetricBasis,
    MetricConflict,
    ValuationBasis,
    ValuationMethod,
    ValuationReference,
    VerificationStatus,
)
from ma_deal_intelligence.identity import (
    CanonicalEntityReference,
    DealContext,
    DealType,
    TransactionStage,
)
from ma_deal_intelligence.outputs import (
    CompanyIntelligenceOutput,
    DiligenceOutput,
    PrecedentTransactionReference,
    PrecedentTransactionsOutput,
    ProjectResultEnvelope,
    TargetCandidateReference,
    TargetScreeningOutput,
    TradingCompsOutput,
)
from ma_deal_intelligence.state import DealState, SourceDocumentReference
from ma_deal_intelligence.workflow import (
    AnalystDecision,
    ArtifactVersion,
    Assumption,
    CapabilityExecution,
    DealWarning,
    DecisionAction,
    DependencyKind,
    DependencyRequirement,
    ExecutionStatus,
    IssueSeverity,
    ResultStatus,
    WorkflowStatus,
)


def representative_deal_state() -> DealState:
    """Return a fictitious five-specialist state with an unresolved EBITDA conflict."""

    generated_at = datetime(2026, 1, 15, 12, tzinfo=UTC)
    target = CanonicalEntityReference(
        "entity:northstar-data",
        legal_name="Northstar Data Systems Ltd.",
        display_name="Northstar Data",
        aliases=("Northstar",),
        country="GB",
        sector="Data infrastructure",
        source_projects=tuple(ProjectId),
        evidence_refs=("ev:p1:annual-report",),
    )
    buyer = CanonicalEntityReference(
        "entity:atlas-software",
        legal_name="Atlas Software plc",
        display_name="Atlas Software",
        country="GB",
        sector="Enterprise software",
        source_projects=(ProjectId.PROJECT_2, ProjectId.PROJECT_6),
    )
    context = DealContext(
        "deal:atlas-northstar",
        engagement_id="engagement:atlas-northstar",
        buyer_entity_id=buyer.canonical_entity_id,
        target_entity_id=target.canonical_entity_id,
        deal_type=DealType.ACQUISITION,
        transaction_stage=TransactionStage.DILIGENCE,
        transaction_thesis="Acquire a recurring-revenue data infrastructure platform.",
        strategic_rationale=("Expand data platform", "Cross-sell to Atlas customers"),
        geographies=("United Kingdom",),
        sectors=("Enterprise software", "Data infrastructure"),
        reporting_currency="GBP",
        as_of_date=date(2025, 12, 31),
        requested_capabilities=(
            "p1.company_intelligence",
            "p2.target_screening",
            "p3.trading_comps",
            "p4.precedent_transactions",
            "p5.due_diligence",
        ),
    )
    evidence = (
        EvidenceReference(
            "ev:p1:annual-report",
            ProjectId.PROJECT_1,
            EvidenceKind.DOCUMENT,
            document_id="doc:northstar-fy25",
            document_title="Northstar FY2025 Annual Report",
            page_numbers=(42,),
            physical_page_indexes=(41,),
            section="Adjusted performance measures",
            chunk_id="chunk:northstar-fy25:42:1",
            excerpt="Reported LTM EBITDA was GBP 100 million.",
            project_evidence_id="1",
        ),
        EvidenceReference(
            "ev:p5:addback",
            ProjectId.PROJECT_5,
            EvidenceKind.SPREADSHEET,
            document_id="vdr:qoe-workbook",
            sheet_name="QoE Bridge",
            cell_range="B18:F18",
            excerpt="Recurring contractor costs were proposed as an add-back.",
            project_evidence_id="evidence:qoe:addback-18",
        ),
        EvidenceReference(
            "ev:p4:precedent",
            ProjectId.PROJECT_4,
            EvidenceKind.DOCUMENT,
            document_id="deal-doc:orion-announcement",
            page_numbers=(3,),
            section="Transaction value",
            project_evidence_id="evidence:orion:ev",
        ),
    )
    period = FinancialPeriodReference("LTM 2025-12-31", date(2025, 1, 1), date(2025, 12, 31))
    reported_ebitda = FinancialMetricReference(
        "metric:p3:reported-ebitda",
        "EBITDA",
        Decimal("100"),
        "GBP",
        "million",
        period,
        MetricBasis.REPORTED,
        EstimateStatus.ACTUAL,
        ProjectId.PROJECT_3,
        "p3:target-profile:ebitda",
        target.canonical_entity_id,
        ("ev:p1:annual-report",),
        VerificationStatus.SOURCE_BACKED,
    )
    adjusted_ebitda = FinancialMetricReference(
        "metric:p5:diligence-adjusted-ebitda",
        "EBITDA",
        Decimal("85"),
        "GBP",
        "million",
        period,
        MetricBasis.ADJUSTED,
        EstimateStatus.ACTUAL,
        ProjectId.PROJECT_5,
        "p5:ebitda-bridge:adjusted",
        target.canonical_entity_id,
        ("ev:p5:addback",),
        VerificationStatus.VERIFIED,
    )
    comps_valuation = ValuationReference(
        "valuation:p3:trading-comps",
        ValuationMethod.TRADING_COMPARABLES,
        Decimal("900"),
        Decimal("1000"),
        Decimal("1100"),
        ValuationBasis.ENTERPRISE_VALUE,
        "Reported LTM EBITDA",
        "GBP",
        "million",
        date(2025, 12, 31),
        ProjectId.PROJECT_3,
        "p3:valuation-output:base",
        (reported_ebitda.metric_id,),
        ("Selected peer median multiple",),
        ("ev:p1:annual-report",),
        ("warning:stale-comps",),
    )
    precedent_valuation = ValuationReference(
        "valuation:p4:precedents",
        ValuationMethod.PRECEDENT_TRANSACTIONS,
        Decimal("850"),
        Decimal("950"),
        Decimal("1050"),
        ValuationBasis.ENTERPRISE_VALUE,
        "Transaction EV / LTM EBITDA",
        "GBP",
        "million",
        date(2025, 12, 31),
        ProjectId.PROJECT_4,
        "p4:precedent-output:base",
        evidence_refs=("ev:p4:precedent",),
    )
    finding = DiligenceFindingReference(
        "finding:p5:recurring-addback-rejected",
        "financial",
        "Recurring add-back rejected",
        FindingSeverity.HIGH,
        "GBP 15 million EBITDA impact",
        ("quality_of_earnings", "valuation"),
        FindingStatus.CONFIRMED,
        ProjectId.PROJECT_5,
        "p5:finding:qoe-18",
        ("ev:p5:addback",),
        "decision:reject-recurring-addback",
    )
    warning = DealWarning(
        "warning:stale-comps",
        "STALE_INPUT_METRIC",
        IssueSeverity.HIGH,
        "Project 3 valuation uses reported EBITDA 100 while diligence-adjusted EBITDA is 85.",
        ProjectId.PROJECT_6,
        affected_field="valuation_outputs[valuation:p3:trading-comps]",
        affected_capability="p3.trading_comps",
        evidence_refs=("ev:p1:annual-report", "ev:p5:addback"),
    )
    decision = AnalystDecision(
        "decision:reject-recurring-addback",
        "financial_adjustment",
        "p5:addback:contractor-costs",
        "proposed",
        DecisionAction.REJECT,
        "Costs recur in the normal operating model and are not a valid add-back.",
        "analyst@example.com",
        generated_at,
        selected_value="rejected",
    )
    conflict = MetricConflict(
        "conflict:ebitda-basis",
        (reported_ebitda.metric_id, adjusted_ebitda.metric_id),
        "Reported and diligence-adjusted EBITDA use different adjustment bases.",
        True,
    )

    def envelope(
        project: ProjectId, capability: str, payload: object
    ) -> ProjectResultEnvelope[object]:
        return ProjectResultEnvelope(
            project,
            capability,
            f"run:{project.value}:{capability}",
            ResultStatus.SUCCEEDED,
            payload,
            (),
            (),
            (),
            (),
            generated_at,
            generated_at,
            "1.0.0",
        )

    p1 = envelope(
        ProjectId.PROJECT_1,
        "p1.company_intelligence",
        CompanyIntelligenceOutput(
            target.canonical_entity_id,
            ("doc:northstar-fy25",),
            "p1:research-profile:northstar",
            financial_metric_ids=(reported_ebitda.metric_id,),
            summary="Evidence-backed company profile fixture.",
        ),
    )
    p2 = envelope(
        ProjectId.PROJECT_2,
        "p2.target_screening",
        TargetScreeningOutput(
            "p2:thesis:atlas",
            (TargetCandidateReference(target, 1, "92.0", "eligible", "Strong strategic fit"),),
            "Atlas acquisition shortlist",
        ),
    )
    p3 = envelope(
        ProjectId.PROJECT_3,
        "p3.trading_comps",
        TradingCompsOutput(
            target.canonical_entity_id,
            ("entity:peer-one", "entity:peer-two"),
            (reported_ebitda,),
            (comps_valuation,),
            "p3:valuation-output:base",
        ),
    )
    p4 = envelope(
        ProjectId.PROJECT_4,
        "p4.precedent_transactions",
        PrecedentTransactionsOutput(
            (
                PrecedentTransactionReference(
                    "transaction:orion",
                    "entity:buyer-orion",
                    "entity:target-orion",
                    "completed",
                    "transaction_enterprise_value",
                    ("ev:p4:precedent",),
                ),
            ),
            (),
            (precedent_valuation,),
            "p4:precedent-output:base",
        ),
    )
    p5 = envelope(
        ProjectId.PROJECT_5,
        "p5.due_diligence",
        DiligenceOutput(
            target.canonical_entity_id,
            (finding,),
            (adjusted_ebitda,),
            ("p5:missing:customer-cohorts",),
            (conflict.conflict_id,),
            True,
            "p5:diligence-result:base",
        ),
    )
    return DealState(
        context,
        (buyer, target),
        (
            SourceDocumentReference(
                "doc:northstar-fy25", ProjectId.PROJECT_1, "FY2025 Annual Report"
            ),
        ),
        (p1,),  # type: ignore[arg-type]
        (p2,),  # type: ignore[arg-type]
        (p3,),  # type: ignore[arg-type]
        (p4,),  # type: ignore[arg-type]
        (p5,),  # type: ignore[arg-type]
        (reported_ebitda, adjusted_ebitda),
        (comps_valuation, precedent_valuation),
        (finding,),
        (conflict,),
        evidence,
        lineage=LineageGraph(
            (
                LineageNode(
                    "lineage:evidence:addback",
                    LineageNodeKind.EVIDENCE,
                    ProjectId.PROJECT_5,
                    "ev:p5:addback",
                    ("ev:p5:addback",),
                ),
                LineageNode(
                    "lineage:finding:addback",
                    LineageNodeKind.SPECIALIST_OUTPUT,
                    ProjectId.PROJECT_5,
                    finding.finding_id,
                    ("ev:p5:addback",),
                ),
                LineageNode(
                    "lineage:conflict:ebitda",
                    LineageNodeKind.RECONCILIATION,
                    ProjectId.PROJECT_6,
                    conflict.conflict_id,
                    ("ev:p1:annual-report", "ev:p5:addback"),
                ),
            ),
            (
                LineageEdge("lineage:finding:addback", "lineage:evidence:addback", "supported_by"),
                LineageEdge("lineage:conflict:ebitda", "lineage:finding:addback", "derived_from"),
            ),
        ),
        analyst_decisions=(decision,),
        assumptions=(
            Assumption(
                "assumption:p3:peer-median",
                "Selected peer median is appropriate for the base case.",
                ProjectId.PROJECT_3,
                "valuation",
                analyst_approved=False,
            ),
        ),
        warnings=(warning,),
        workflow_status=WorkflowStatus.REVIEW_REQUIRED,
        capability_executions=tuple(
            CapabilityExecution(capability, project, ExecutionStatus.COMPLETED)
            for project, capability in (
                (ProjectId.PROJECT_1, "p1.company_intelligence"),
                (ProjectId.PROJECT_2, "p2.target_screening"),
                (ProjectId.PROJECT_3, "p3.trading_comps"),
                (ProjectId.PROJECT_4, "p4.precedent_transactions"),
                (ProjectId.PROJECT_5, "p5.due_diligence"),
            )
        ),
        completed_capabilities=context.requested_capabilities,
        dependencies=(
            DependencyRequirement(
                "dependency:p3:target-financials",
                "p3.trading_comps",
                DependencyKind.REQUIRED,
                required_artifact_ids=(reported_ebitda.metric_id,),
                satisfied=True,
            ),
            DependencyRequirement(
                "dependency:p5:vdr",
                "p5.due_diligence",
                DependencyKind.REQUIRED,
                required_artifact_ids=("doc:northstar-fy25",),
                satisfied=True,
            ),
        ),
        artifact_versions=(
            ArtifactVersion(
                comps_valuation.valuation_id,
                "1.0.0",
                "p3-input-v1",
                (reported_ebitda.metric_id,),
                "sha256:reported-ebitda-100",
                True,
                (
                    "Project 5 produced diligence-adjusted EBITDA 85 and rejected the "
                    "recurring add-back."
                ),
            ),
            ArtifactVersion(
                adjusted_ebitda.metric_id,
                "1.0.0",
                "p5-input-v1",
                ("ev:p5:addback",),
                "sha256:adjusted-ebitda-85",
            ),
        ),
        revision=2,
        updated_at=generated_at,
    )
