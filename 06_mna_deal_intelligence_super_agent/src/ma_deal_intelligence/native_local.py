"""Optional native-local composition over the five installed specialist packages.

The imports are intentionally lazy: Project 6 remains installable on its own, while a portfolio
environment can opt into real specialist execution. External providers remain replaced by each
specialist's deterministic offline inputs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from typing import Any

from ma_deal_intelligence.adapters import (
    AdapterMode,
    Project1Adapter,
    Project2Adapter,
    Project3Adapter,
    Project4Adapter,
    Project5Adapter,
)
from ma_deal_intelligence.adapters.base import NativeProjectResult
from ma_deal_intelligence.adapters.project1 import Project1NativeRequest
from ma_deal_intelligence.adapters.project2 import Project2NativeRequest
from ma_deal_intelligence.adapters.project3 import Project3NativeRequest
from ma_deal_intelligence.adapters.project4 import Project4NativeRequest
from ma_deal_intelligence.adapters.project5 import Project5NativeRequest
from ma_deal_intelligence.evidence import EvidenceKind, EvidenceReference, ProjectId
from ma_deal_intelligence.finance import (
    DiligenceFindingReference,
    EstimateStatus,
    FinancialMetricReference,
    FinancialPeriodReference,
    FindingSeverity,
    FindingStatus,
    MetricBasis,
    ValuationBasis,
    ValuationMethod,
    ValuationReference,
    VerificationStatus,
)
from ma_deal_intelligence.identity import CanonicalEntityReference
from ma_deal_intelligence.outputs import (
    CompanyIntelligenceOutput,
    DiligenceOutput,
    PrecedentTransactionReference,
    PrecedentTransactionsOutput,
    TargetCandidateReference,
    TargetScreeningOutput,
    TradingCompsOutput,
)
from ma_deal_intelligence.registry import CapabilityRegistry
from ma_deal_intelligence.workflow import DealWarning, IssueSeverity


@dataclass(frozen=True, slots=True)
class NativeLocalSettings:
    """Filesystem inputs required by deterministic native-local specialist execution."""

    project_2_root: Path
    project_1_documents: Mapping[str, Path]


def build_native_local_registry(settings: NativeLocalSettings) -> CapabilityRegistry:
    """Register all five adapters with executors that call specialist-owned code."""

    registry = CapabilityRegistry()
    adapters = (
        Project1Adapter(
            mode=AdapterMode.NATIVE,
            native_executor=Project1NativeLocalExecutor(settings.project_1_documents),
        ),
        Project2Adapter(
            mode=AdapterMode.NATIVE,
            native_executor=Project2NativeLocalExecutor(settings.project_2_root),
        ),
        Project3Adapter(mode=AdapterMode.NATIVE, native_executor=Project3NativeLocalExecutor()),
        Project4Adapter(mode=AdapterMode.NATIVE, native_executor=Project4NativeLocalExecutor()),
        Project5Adapter(mode=AdapterMode.NATIVE, native_executor=Project5NativeLocalExecutor()),
    )
    for adapter in adapters:
        registry.register(adapter)
    return registry


@dataclass(frozen=True, slots=True)
class Project1NativeLocalExecutor:
    document_paths: Mapping[str, Path]

    def __call__(
        self, request: Project1NativeRequest
    ) -> NativeProjectResult[CompanyIntelligenceOutput]:
        ingestion = import_module("ma_company_intelligence.ingestion")
        chunking = import_module("ma_company_intelligence.chunking")
        all_evidence: list[EvidenceReference] = []
        metric_ids: list[str] = []
        summaries: list[str] = []
        for requested_id in request.document_ids:
            path = self.document_paths.get(requested_id)
            if path is None:
                raise ValueError(
                    f"native-local Project 1 document is not configured: {requested_id}"
                )
            parsed = ingestion.parse_pdf(path)
            chunked = chunking.chunk_document(parsed)
            if not chunked.chunks:
                raise ValueError(f"native-local Project 1 document has no text: {requested_id}")
            for chunk in chunked.chunks:
                pages = tuple(int(item.page_number) for item in chunk.page_references)
                all_evidence.append(
                    EvidenceReference(
                        f"p1:{requested_id}:{chunk.chunk_id}",
                        ProjectId.PROJECT_1,
                        EvidenceKind.DOCUMENT,
                        source_record_id=chunk.chunk_id,
                        document_id=requested_id,
                        document_title=parsed.source.filename,
                        page_numbers=pages,
                        section=chunk.section,
                        chunk_id=chunk.chunk_id,
                        excerpt=chunk.text[:500],
                        project_evidence_id=chunk.chunk_id,
                    )
                )
            summaries.append(f"{parsed.source.filename}: {len(chunked.chunks)} indexed chunks")
            metric_ids.extend(_p1_metric_ids(chunked.chunks, request.entity_id))
        payload = CompanyIntelligenceOutput(
            request.entity_id,
            request.document_ids,
            f"p1:native-local:profile:{request.entity_id}",
            (f"p1:native-local:answer:{request.entity_id}",) if request.question else (),
            tuple(dict.fromkeys(metric_ids)),
            "; ".join(summaries),
        )
        return NativeProjectResult(payload, tuple(all_evidence))


@dataclass(frozen=True, slots=True)
class Project2NativeLocalExecutor:
    project_root: Path

    def __call__(
        self, request: Project2NativeRequest
    ) -> NativeProjectResult[TargetScreeningOutput]:
        composition = import_module("ma_target_screening.composition")
        thesis_module = import_module("ma_target_screening.thesis")
        thesis_path = self.project_root / "examples" / "screening-ranking-demo.json"
        thesis = thesis_module.AcquisitionThesis.from_json(thesis_path.read_text(encoding="utf-8"))
        if request.thesis_id != thesis.thesis_id:
            raise ValueError(
                "native-local Project 2 supports thesis "
                f"{thesis.thesis_id}, got {request.thesis_id}"
            )
        paths = composition.OfflinePaths.from_project_root(self.project_root)
        app = composition.build_offline_services(paths).workflow
        state = app.start(thesis, thread_id=f"p6:{request.thesis_id}")
        shortlist = state["provisional_shortlist"]
        evidence: dict[str, EvidenceReference] = {}
        candidates: list[TargetCandidateReference] = []
        for ranked in shortlist.ranked_candidates:
            candidate = ranked.result.profile.candidate
            refs: list[str] = []
            for item in candidate.discovery_evidence:
                evidence_id = f"p2:{candidate.website_domain}:{item.source_identifier}"
                refs.append(evidence_id)
                evidence[evidence_id] = EvidenceReference(
                    evidence_id,
                    ProjectId.PROJECT_2,
                    EvidenceKind.URL if item.source_uri else EvidenceKind.DATASET,
                    source_record_id=item.source_identifier,
                    url=item.source_uri,
                    excerpt=item.excerpt,
                    project_evidence_id=item.source_identifier,
                )
            identity = CanonicalEntityReference(
                "entity:"
                + (
                    candidate.website_domain
                    or candidate.canonical_name.casefold().replace(" ", "-")
                ),
                legal_name=candidate.canonical_name,
                aliases=candidate.aliases,
                country=candidate.country,
                sector=candidate.industry_tags[0] if candidate.industry_tags else None,
                source_projects=(ProjectId.PROJECT_2,),
                evidence_refs=tuple(refs),
            )
            score = ranked.result.scores.final_score
            candidates.append(
                TargetCandidateReference(
                    identity,
                    ranked.rank,
                    "unknown" if score is None else str(score),
                    ranked.result.eligibility.value,
                    ranked.result.rationale,
                    tuple(refs),
                )
            )
        return NativeProjectResult(
            TargetScreeningOutput(
                request.thesis_id,
                tuple(candidates),
                f"native-local:{request.thesis_id}",
            ),
            tuple(evidence.values()),
            (_offline_source_warning(ProjectId.PROJECT_2),),
        )


@dataclass(frozen=True, slots=True)
class Project3NativeLocalExecutor:
    def __call__(self, request: Project3NativeRequest) -> NativeProjectResult[TradingCompsOutput]:
        workflow = import_module("ma_comparable_valuation.workflow")
        result = workflow.OfflineValuationService().run()
        target = result.target_profile
        if request.target_entity_id != target.target.identity.company_id:
            raise ValueError("native-local Project 3 target does not match its target profile")
        if request.reporting_currency != target.target.reporting_currency:
            raise ValueError("native-local Project 3 currency does not match its target profile")
        native_as_of = result.peer_set.created_at
        if request.as_of_date != native_as_of.date():
            raise ValueError("native-local Project 3 as-of date does not match its peer snapshot")
        metrics = tuple(_p3_metric(item, request.target_entity_id) for item in target.metrics)
        evidence = _unique_evidence(
            _p3_evidence(item) for metric in target.metrics for item in metric.evidence
        )
        valuations = tuple(
            _p3_valuation(item, request.as_of_date) for item in result.valuation.ranges
        )
        payload = TradingCompsOutput(
            request.target_entity_id,
            tuple(item.company.identity.company_id for item in result.peer_set.snapshots),
            metrics,
            valuations,
            result.valuation.output_id,
        )
        return NativeProjectResult(
            payload,
            evidence,
            (_offline_source_warning(ProjectId.PROJECT_3),),
            data_as_of=native_as_of,
        )


@dataclass(frozen=True, slots=True)
class Project4NativeLocalExecutor:
    def __call__(
        self, request: Project4NativeRequest
    ) -> NativeProjectResult[PrecedentTransactionsOutput]:
        precedent = import_module("ma_precedent_transactions.precedent")
        comparable, target, transactions = precedent.precedent_fixture_inputs()
        if request.target_entity_id != target.target_id:
            raise ValueError("native-local Project 4 target does not match its valuation profile")
        output = precedent.PrecedentAnalysisService().analyze(comparable, target, transactions)
        data_as_of_date = max(item.measurement_date for item in target.metrics)
        by_id = {item.record.identity.transaction_id: item.record for item in transactions}
        selected = tuple(
            _p4_transaction(by_id[transaction_id])
            for transaction_id in output.selection.selected_transaction_ids
        )
        metrics = tuple(_p4_metric(item, request.target_entity_id) for item in target.metrics)
        valuations = tuple(_p4_valuation(item, request.as_of_date) for item in output.ranges)
        evidence = _unique_evidence(
            _p4_evidence(item)
            for transaction in selected
            for evidence_id in transaction.evidence_refs
            for item in _p4_native_evidence(evidence_id, transactions)
        )
        return NativeProjectResult(
            PrecedentTransactionsOutput(selected, metrics, valuations, output.output_id),
            evidence,
            (_offline_source_warning(ProjectId.PROJECT_4),),
            data_as_of=datetime.combine(data_as_of_date, datetime.min.time(), UTC),
        )


@dataclass(frozen=True, slots=True)
class Project5NativeLocalExecutor:
    def __call__(self, request: Project5NativeRequest) -> NativeProjectResult[DiligenceOutput]:
        financial = import_module("ma_due_diligence.workflow_final.financial")
        snapshot = financial.run_fixture_financial_diligence(request.engagement_id)
        native_evidence = _p5_snapshot_evidence(snapshot)
        expected_documents = {item.document_id for item in native_evidence if item.document_id}
        if not expected_documents.issubset(set(request.vdr_document_ids)):
            missing = sorted(expected_documents - set(request.vdr_document_ids))
            raise ValueError(f"native-local Project 5 requires fixture documents: {missing}")
        bridge = snapshot.ebitda_bridge
        metrics = (
            _p5_metric(
                "p5:reported-ebitda",
                "ebitda",
                bridge.reported_ebitda.value,
                bridge.currency,
                bridge.unit.value,
                bridge.reported_ebitda.period,
                MetricBasis.REPORTED,
                bridge.reported_ebitda.evidence,
                request.target_entity_id,
            ),
            _p5_metric(
                "p5:adjusted-ebitda",
                "ebitda",
                bridge.final_adjusted_ebitda,
                bridge.currency,
                bridge.unit.value,
                bridge.reported_ebitda.period,
                MetricBasis.ADJUSTED,
                tuple(item for line in bridge.lines for item in line.evidence),
                request.target_entity_id,
            ),
            _p5_metric(
                "p5:nwc-peg",
                "nwc_peg",
                snapshot.nwc_peg.normalized_nwc,
                snapshot.nwc_peg.currency,
                snapshot.nwc_peg.unit.value,
                snapshot.working_capital.results[-1].period,
                MetricBasis.NORMALIZED,
                tuple(
                    item
                    for result in snapshot.working_capital.results
                    for line in result.lines
                    for item in line.evidence
                ),
                request.target_entity_id,
            ),
            _p5_metric(
                "p5:adjusted-net-debt",
                "net_debt",
                snapshot.net_debt.adjusted_net_debt,
                snapshot.net_debt.currency,
                snapshot.net_debt.unit.value,
                None,
                MetricBasis.ADJUSTED,
                tuple(item for line in snapshot.net_debt.lines for item in line.evidence),
                request.target_entity_id,
            ),
        )
        findings = tuple(_p5_finding(item.finding) for item in snapshot.findings)
        payload = DiligenceOutput(
            request.target_entity_id,
            findings,
            metrics,
            (),
            ("p5:revenue-source-conflict",)
            if snapshot.revenue_reconciliation.unresolved_conflict
            else (),
            True,
            f"p5:native-local:{request.engagement_id}",
        )
        return NativeProjectResult(
            payload,
            tuple(_p5_evidence(item) for item in native_evidence),
            (_offline_source_warning(ProjectId.PROJECT_5),),
            data_as_of=datetime.combine(
                max(item.as_of_date for item in snapshot.net_debt.items),
                datetime.min.time(),
                UTC,
            ),
        )


def _p1_metric_ids(chunks: tuple[Any, ...], entity_id: str) -> tuple[str, ...]:
    financial_terms = ("revenue", "ebitda", "net income", "cash", "debt")
    return tuple(
        f"p1:native-local:metric:{entity_id}:{chunk.chunk_id}"
        for chunk in chunks
        if any(term in chunk.text.casefold() for term in financial_terms)
    )


def _offline_source_warning(project: ProjectId) -> DealWarning:
    return DealWarning(
        f"warning:{project.value}:offline-specialist-fixture",
        "OFFLINE_SPECIALIST_FIXTURE",
        IssueSeverity.LOW,
        "Native specialist code executed against deterministic offline fixture inputs.",
        project,
    )


def _period(period: Any) -> FinancialPeriodReference:
    return FinancialPeriodReference(period.label, period.start_date, period.end_date)


def _basis(value: Any) -> MetricBasis:
    return (
        MetricBasis(value.value)
        if value.value in {item.value for item in MetricBasis}
        else MetricBasis.OTHER
    )


def _estimate(value: Any) -> EstimateStatus:
    return (
        EstimateStatus.FORECAST
        if value.value in {"estimate", "forecast"}
        else EstimateStatus.ACTUAL
    )


def _p3_metric(item: Any, entity_id: str) -> FinancialMetricReference:
    return FinancialMetricReference(
        item.metric_id,
        item.name.value,
        item.value,
        item.currency,
        item.unit.value,
        _period(item.period),
        _basis(item.basis),
        _estimate(item.period.estimate_status),
        ProjectId.PROJECT_3,
        item.metric_id,
        entity_id,
        tuple(evidence.evidence_id for evidence in item.evidence),
        VerificationStatus.SOURCE_BACKED,
    )


def _p3_valuation(item: Any, as_of: date) -> ValuationReference:
    return ValuationReference(
        item.range_id,
        ValuationMethod.TRADING_COMPARABLES,
        item.low.implied_value,
        item.mid.implied_value,
        item.high.implied_value,
        ValuationBasis.ENTERPRISE_VALUE,
        f"{item.request.definition.kind.value}:{item.request.period_label}:{item.request.basis.value}",
        item.mid.currency,
        item.mid.unit.value,
        as_of,
        ProjectId.PROJECT_3,
        item.range_id,
        (item.mid.target_metric_id,),
        tuple(item.warnings),
        tuple(input_.evidence_ids[0] for input_ in item.mid.trace.inputs if input_.evidence_ids),
    )


def _p3_evidence(item: Any) -> EvidenceReference:
    return EvidenceReference(
        item.evidence_id,
        ProjectId.PROJECT_3,
        EvidenceKind.DATASET,
        source_record_id=item.source_locator,
        document_id=item.document_id,
        page_numbers=item.page_numbers,
        section=item.section,
        chunk_id=item.chunk_id,
        excerpt=item.excerpt,
        project_evidence_id=item.evidence_id,
    )


def _p4_metric(item: Any, entity_id: str) -> FinancialMetricReference:
    return FinancialMetricReference(
        item.metric_id,
        item.name.value,
        item.value,
        item.currency,
        item.unit.value,
        _period(item.period),
        _basis(item.basis),
        _estimate(item.period.estimate_status),
        ProjectId.PROJECT_4,
        item.metric_id,
        entity_id,
        tuple(evidence.evidence_id for evidence in item.evidence),
        VerificationStatus.VERIFIED,
    )


def _p4_transaction(record: Any) -> PrecedentTransactionReference:
    evidence = tuple(item.evidence_id for item in record.evidence)
    basis = record.valuations[0].basis.value if record.valuations else "unknown"
    return PrecedentTransactionReference(
        record.identity.transaction_id,
        record.acquirer.party_id,
        record.target.party_id,
        record.lifecycle.status.value,
        basis,
        evidence,
    )


def _p4_valuation(item: Any, as_of: date) -> ValuationReference:
    use_ev = all(
        value is not None
        for value in (
            item.low.implied_enterprise_value,
            item.mid.implied_enterprise_value,
            item.high.implied_enterprise_value,
        )
    )
    values = (
        (
            item.low.implied_enterprise_value,
            item.mid.implied_enterprise_value,
            item.high.implied_enterprise_value,
        )
        if use_ev
        else (
            item.low.implied_equity_value,
            item.mid.implied_equity_value,
            item.high.implied_equity_value,
        )
    )
    if any(value is None for value in values):
        raise ValueError(f"Project 4 valuation range is incomplete: {item.range_id}")
    low, mid, high = values
    assert low is not None and mid is not None and high is not None
    return ValuationReference(
        item.range_id,
        ValuationMethod.PRECEDENT_TRANSACTIONS,
        low,
        mid,
        high,
        ValuationBasis.ENTERPRISE_VALUE if use_ev else ValuationBasis.EQUITY_VALUE,
        f"{item.key.kind.value}:{item.key.period_kind}:{item.key.basis.value}",
        item.mid.currency,
        item.mid.unit.value,
        as_of,
        ProjectId.PROJECT_4,
        item.range_id,
        (item.target_metric_id,),
        tuple(item.warnings),
        tuple(item.mid.trace.inputs[0].evidence_ids),
    )


def _p4_native_evidence(evidence_id: str, transactions: tuple[Any, ...]) -> tuple[Any, ...]:
    return tuple(
        evidence
        for transaction in transactions
        for evidence in transaction.record.evidence
        if evidence.evidence_id == evidence_id
    )


def _p4_evidence(item: Any) -> EvidenceReference:
    return EvidenceReference(
        item.evidence_id,
        ProjectId.PROJECT_4,
        EvidenceKind.URL if item.source_url else EvidenceKind.DOCUMENT,
        source_record_id=item.excerpt_id,
        document_id=item.document_id,
        document_title=item.document_title,
        page_numbers=() if item.page is None else (item.page,),
        section=item.section,
        table=item.table,
        chunk_id=item.chunk_id,
        url=item.source_url,
        excerpt=item.excerpt,
        project_evidence_id=item.evidence_id,
    )


def _p5_metric(
    metric_id: str,
    metric_type: str,
    value: Decimal | None,
    currency: str,
    unit: str,
    period: Any | None,
    basis: MetricBasis,
    evidence: tuple[Any, ...],
    entity_id: str,
) -> FinancialMetricReference:
    if value is None:
        raise ValueError(f"Project 5 metric is unavailable: {metric_id}")
    return FinancialMetricReference(
        metric_id,
        metric_type,
        value,
        currency,
        unit,
        FinancialPeriodReference("as_of") if period is None else _period(period),
        basis,
        EstimateStatus.ACTUAL,
        ProjectId.PROJECT_5,
        metric_id,
        entity_id,
        tuple(dict.fromkeys(item.evidence_id for item in evidence)),
        VerificationStatus.DERIVED,
    )


def _p5_finding(item: Any) -> DiligenceFindingReference:
    severity = (
        FindingSeverity(item.severity.value)
        if item.severity.value in {value.value for value in FindingSeverity}
        else FindingSeverity.UNASSESSED
    )
    status = (
        FindingStatus(item.status.value)
        if item.status.value in {value.value for value in FindingStatus}
        else FindingStatus.UNDER_REVIEW
    )
    return DiligenceFindingReference(
        item.finding_id,
        item.workstream.value,
        item.title,
        severity,
        item.materiality.qualitative.value,
        tuple(value.value for value in item.impact_areas),
        status,
        ProjectId.PROJECT_5,
        item.finding_id,
        tuple(evidence.evidence_id for evidence in item.evidence),
    )


def _p5_snapshot_evidence(snapshot: Any) -> tuple[Any, ...]:
    return tuple(
        {
            item.evidence_id: item
            for item in (
                *(evidence for output in snapshot.findings for evidence in output.finding.evidence),
                *(evidence for line in snapshot.ebitda_bridge.lines for evidence in line.evidence),
                *(evidence for line in snapshot.net_debt.lines for evidence in line.evidence),
                *(
                    evidence
                    for result in snapshot.working_capital.results
                    for line in result.lines
                    for evidence in line.evidence
                ),
            )
        }.values()
    )


def _p5_evidence(item: Any) -> EvidenceReference:
    is_sheet = item.sheet_name is not None or item.cell_range is not None
    return EvidenceReference(
        item.evidence_id,
        ProjectId.PROJECT_5,
        EvidenceKind.SPREADSHEET if is_sheet else EvidenceKind.DOCUMENT,
        document_id=item.document_id,
        page_numbers=item.page_numbers,
        section=item.section,
        table=item.table,
        sheet_name=item.sheet_name,
        cell_range=item.cell_range,
        row=item.row,
        column=item.column,
        chunk_id=item.chunk_id,
        excerpt=item.source_text,
        project_evidence_id=item.evidence_id,
    )


def _unique_evidence(items: Any) -> tuple[EvidenceReference, ...]:
    return tuple({item.evidence_id: item for item in items}.values())
