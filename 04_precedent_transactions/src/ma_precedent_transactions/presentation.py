"""Stable, compact JSON presentation for workflow and API results."""

from __future__ import annotations

from ma_precedent_transactions.workflow import (
    PrecedentWorkflowResult,
    WorkflowState,
    WorkflowStatus,
)


def workflow_result_to_dict(result: PrecedentWorkflowResult) -> dict[str, object]:
    research = result.research
    valuation = result.valuation
    selection = result.selection
    return {
        "request_id": result.request.request_id,
        "target_id": result.request.valuation_target.target_id,
        "status": result.status.value,
        "failure_code": None if result.failure_code is None else result.failure_code.value,
        "discovery": {
            "raw_candidate_count": 0
            if research is None
            else research.discovery.raw_candidate_count,
            "deduplicated_count": 0 if research is None else len(research.discovery.transactions),
            "transaction_ids": []
            if research is None
            else [item.candidate_id for item in research.discovery.transactions],
            "document_count": 0 if research is None else len(research.parsed_documents),
            "chunk_count": 0 if research is None else len(research.chunks),
        },
        "verified_transactions": [
            {
                "transaction_id": item.record.identity.transaction_id,
                "acquirer": item.record.acquirer.legal_name,
                "target": item.record.target.legal_name,
                "status": item.record.lifecycle.status.value,
                "conflicts": [conflict.field for conflict in item.conflicts],
                "evidence_ids": [evidence.evidence_id for evidence in item.record.evidence],
            }
            for item in result.verified_transactions
        ],
        "selected_precedents": []
        if selection is None
        else list(selection.selected_transaction_ids),
        "excluded_precedents": []
        if selection is None
        else [
            {
                "transaction_id": item.transaction_id,
                "decision": item.decision.value,
                "rationale": item.rationale,
            }
            for item in selection.decisions
            if item.transaction_id not in selection.selected_transaction_ids
        ],
        "multiples": [
            {
                "multiple_id": item.contract.multiple_id,
                "transaction_id": item.contract.transaction_id,
                "kind": item.contract.definition.kind.value,
                "status": item.contract.status.value,
                "value": None if item.contract.value is None else str(item.contract.value),
                "numerator_currency": item.numerator_currency,
                "denominator_period": None
                if item.denominator_period is None
                else item.denominator_period.label,
                "basis": None if item.denominator_basis is None else item.denominator_basis.value,
                "evidence_ids": [evidence.evidence_id for evidence in item.evidence],
                "treatment_reason": item.contract.treatment_reason,
            }
            for item in result.multiples
        ],
        "peer_statistics": []
        if valuation is None
        else [
            {
                "kind": item.key.kind.value,
                "currency": item.key.currency,
                "period_kind": item.key.period_kind,
                "basis": item.key.basis.value,
                "count": item.statistics.count,
                "p25": _decimal(item.statistics.percentile_25),
                "median": _decimal(item.statistics.median),
                "p75": _decimal(item.statistics.percentile_75),
                "outlier_ids": list(item.statistics.outlier_multiple_ids),
                "warnings": list(item.statistics.warnings),
            }
            for item in valuation.multiple_sets
        ],
        "valuation_ranges": []
        if valuation is None
        else [
            {
                "kind": item.key.kind.value,
                "currency": item.mid.currency,
                "unit": item.mid.unit.value,
                "target_metric_id": item.target_metric_id,
                "low_equity": _decimal(item.low.implied_equity_value),
                "mid_equity": _decimal(item.mid.implied_equity_value),
                "high_equity": _decimal(item.high.implied_equity_value),
                "mid_per_share": _decimal(item.mid.implied_per_share),
                "trace_id": item.mid.trace.trace_id,
                "bridge_trace_id": None
                if item.mid.bridge_trace is None
                else item.mid.bridge_trace.trace_id,
                "warnings": list(item.warnings),
            }
            for item in valuation.ranges
        ],
        "explanation": None
        if valuation is None or valuation.explanation is None
        else {
            "status": valuation.explanation.status.value,
            "precedent_set_assessment": valuation.explanation.precedent_set_assessment,
            "key_valuation_drivers": list(valuation.explanation.key_valuation_drivers),
            "valuation_caveats": list(valuation.explanation.valuation_caveats),
            "evidence_ids": list(valuation.explanation.evidence_ids),
        },
        "human_review": None
        if result.human_review is None
        else {
            "action": result.human_review.action.value,
            "reviewer": result.human_review.reviewer,
            "rationale": result.human_review.rationale,
            "recorded_at": result.human_review.recorded_at.isoformat(),
            "resolution_count": len(result.human_review.resolutions),
            "override_count": len(result.human_review.overrides),
        },
        "evaluation": None
        if result.evaluation is None
        else {
            "discovered_count": result.evaluation.discovered_count,
            "deduplicated_count": result.evaluation.deduplicated_count,
            "document_count": result.evaluation.document_count,
            "evidence_count": result.evaluation.evidence_count,
            "verified_count": result.evaluation.verified_count,
            "conflict_count": result.evaluation.conflict_count,
            "selected_count": result.evaluation.selected_count,
            "valid_multiple_count": result.evaluation.valid_multiple_count,
            "valuation_range_count": result.evaluation.valuation_range_count,
            "explanation_available": result.evaluation.explanation_available,
        },
        "warnings": list(result.warnings),
        "errors": [
            {
                "code": item.code.value,
                "stage": item.stage,
                "message": item.message,
                "recoverable": item.recoverable,
                "attempt": item.attempt,
            }
            for item in result.errors
        ],
        "trace": [
            {
                "node": item.node,
                "status": item.status.value,
                "message": item.message,
                "duration_ms": item.duration_ms,
                "occurred_at": item.occurred_at.isoformat(),
                "retry_count": item.retry_count,
            }
            for item in result.trace
        ],
    }


def workflow_state_to_dict(state: WorkflowState) -> dict[str, object]:
    final = state.get("final_result")
    review = state.get("review_request")
    current_status = state.get("status", WorkflowStatus.FAILED)
    failure_code = state.get("failure_code")
    return {
        "request_id": state["request"].request_id,
        "status": current_status.value,
        "failure_code": None if failure_code is None else failure_code.value,
        "review_required": review is not None
        and current_status is WorkflowStatus.AWAITING_HUMAN_REVIEW,
        "review_request": None
        if review is None
        else {
            "reasons": list(review.reasons),
            "transaction_ids": list(review.transaction_ids),
            "conflict_fields": list(review.conflict_fields),
        },
        "result": None if final is None else workflow_result_to_dict(final),
        "warnings": list(state.get("warnings", ())),
        "errors": [
            {
                "code": item.code.value,
                "stage": item.stage,
                "message": item.message,
                "recoverable": item.recoverable,
                "attempt": item.attempt,
            }
            for item in state.get("errors", ())
        ],
        "trace": [
            {
                "node": item.node,
                "status": item.status.value,
                "message": item.message,
                "duration_ms": item.duration_ms,
                "occurred_at": item.occurred_at.isoformat(),
                "retry_count": item.retry_count,
            }
            for item in state.get("trace", ())
        ],
    }


def _decimal(value: object) -> str | None:
    return None if value is None else str(value)
