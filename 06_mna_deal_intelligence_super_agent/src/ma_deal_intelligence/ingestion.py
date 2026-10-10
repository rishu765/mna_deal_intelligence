"""Idempotent ingestion of specialist envelopes into canonical deal state."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from ma_deal_intelligence.outputs import (
    CompanyIntelligenceOutput,
    DiligenceOutput,
    PrecedentTransactionsOutput,
    ProjectResultEnvelope,
    TargetScreeningOutput,
    TradingCompsOutput,
)
from ma_deal_intelligence.state import DealState
from ma_deal_intelligence.workflow import (
    ArtifactVersion,
    CapabilityExecution,
    ExecutionStatus,
    ResultStatus,
)


def ingest_result(state: DealState, result: ProjectResultEnvelope[Any]) -> DealState:
    """Return a new state while retaining rerun history and ignoring exact duplicates."""
    existing = _all_results(state)
    identity = (result.source_project, result.capability, result.run_id)
    if any((item.source_project, item.capability, item.run_id) == identity for item in existing):
        return state

    field_name = _result_field(result.payload)
    values = getattr(state, field_name) + (result,)
    evidence = {item.evidence_id: item for item in state.evidence}
    evidence.update({item.evidence_id: item for item in result.evidence})

    metrics = state.financial_metrics
    valuations = state.valuation_outputs
    findings = state.diligence_findings
    if isinstance(result.payload, (TradingCompsOutput, PrecedentTransactionsOutput)):
        metrics = _merge_by_id(metrics, result.payload.financial_metrics, "metric_id")
        valuations = _merge_by_id(valuations, result.payload.valuations, "valuation_id")
    elif isinstance(result.payload, DiligenceOutput):
        metrics = _merge_by_id(metrics, result.payload.financial_metrics, "metric_id")
        findings = _merge_by_id(findings, result.payload.findings, "finding_id")

    artifact_id = f"result:{result.source_project.value}:{result.capability}:{result.run_id}"
    versions = list(state.artifact_versions)
    for index, version in enumerate(versions):
        if (
            version.artifact_id.startswith(
                f"result:{result.source_project.value}:{result.capability}:"
            )
            and version.superseded_by is None
        ):
            versions[index] = replace(version, superseded_by=artifact_id)
    versions.append(
        ArtifactVersion(
            artifact_id,
            result.schema_version,
            result.run_id,
            result.evidence_refs,
        )
    )
    execution_status = (
        ExecutionStatus.COMPLETED_WITH_WARNINGS
        if result.status in {ResultStatus.SUCCEEDED_WITH_WARNINGS, ResultStatus.PARTIAL}
        else ExecutionStatus.FAILED
        if result.status is ResultStatus.FAILED
        else ExecutionStatus.COMPLETED
    )
    execution = CapabilityExecution(
        result.capability,
        result.source_project,
        execution_status,
        result.run_id,
        output_artifact_ids=(artifact_id,),
    )
    completed = state.completed_capabilities
    if execution_status in {ExecutionStatus.COMPLETED, ExecutionStatus.COMPLETED_WITH_WARNINGS}:
        completed = tuple(dict.fromkeys((*completed, result.capability)))
    return replace(
        state,
        **{field_name: values},
        financial_metrics=metrics,
        valuation_outputs=valuations,
        diligence_findings=findings,
        evidence=tuple(evidence.values()),
        warnings=state.warnings
        + tuple(item for item in result.warnings if item not in state.warnings),
        errors=state.errors + tuple(item for item in result.errors if item not in state.errors),
        capability_executions=state.capability_executions + (execution,),
        completed_capabilities=completed,
        artifact_versions=tuple(versions),
        revision=state.revision + 1,
        updated_at=datetime.now(UTC),
    )


def _all_results(state: DealState) -> tuple[ProjectResultEnvelope[Any], ...]:
    return (
        *state.company_intelligence,
        *state.target_screening_results,
        *state.trading_comps_results,
        *state.precedent_transaction_results,
        *state.diligence_results,
    )


def _result_field(payload: object) -> str:
    if isinstance(payload, CompanyIntelligenceOutput):
        return "company_intelligence"
    if isinstance(payload, TargetScreeningOutput):
        return "target_screening_results"
    if isinstance(payload, TradingCompsOutput):
        return "trading_comps_results"
    if isinstance(payload, PrecedentTransactionsOutput):
        return "precedent_transaction_results"
    if isinstance(payload, DiligenceOutput):
        return "diligence_results"
    raise TypeError(f"unsupported specialist payload: {type(payload).__name__}")


def _merge_by_id(
    existing: tuple[Any, ...], additions: tuple[Any, ...], field: str
) -> tuple[Any, ...]:
    values = {getattr(item, field): item for item in existing}
    values.update({getattr(item, field): item for item in additions})
    return tuple(values.values())
