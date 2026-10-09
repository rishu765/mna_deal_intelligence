"""Polished offline Project 4 V1 demo with one checkpointed analyst review."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

from ma_precedent_transactions.discovery import AcquisitionContext
from ma_precedent_transactions.precedent import precedent_fixture_inputs
from ma_precedent_transactions.presentation import workflow_state_to_dict
from ma_precedent_transactions.workflow import (
    HumanReviewDecision,
    ObservationResolution,
    ReviewAction,
    ReviewPolicy,
    WorkflowRequest,
    build_offline_application,
)


def run_demo() -> dict[str, object]:
    comparable, valuation, _ = precedent_fixture_inputs()
    request = WorkflowRequest(
        "project4-final-demo",
        AcquisitionContext(
            "project4-final-demo",
            "B2B fintech infrastructure",
            "Payments, ledger, banking API, and compliance infrastructure",
            ("United States", "United Kingdom"),
            date(2020, 1, 1),
            date(2025, 12, 31),
        ),
        comparable,
        valuation,
        ReviewPolicy.ALWAYS,
    )
    application = build_offline_application()
    paused = application.start(request, thread_id=request.request_id)
    conflict = next(
        item
        for record in paused["verified_transactions"]
        for item in record.conflicts
        if record.record.identity.transaction_id == "txn-conflict"
    )
    resumed = application.resume(
        thread_id=request.request_id,
        decision=HumanReviewDecision(
            ReviewAction.APPROVE,
            "demo-analyst",
            "Reviewed the conflicting headline values and approved the precedent policy.",
            (
                ObservationResolution(
                    "txn-conflict",
                    conflict.field,
                    conflict.observation_ids[0],
                    "Selected the official current observation for the demonstration.",
                ),
            ),
            recorded_at=datetime.now(UTC),
        ),
    )
    return {
        "portfolio_story": (
            "Discover -> deduplicate -> ingest/RAG -> extract/verify -> analyst review -> "
            "select precedents -> deterministic valuation -> grounded explanation"
        ),
        "paused": workflow_state_to_dict(paused),
        "resumed": workflow_state_to_dict(resumed),
        "scope": "Offline fixture V1; no live database, DCF, merger model, or frontend.",
    }


def main() -> None:
    print(json.dumps(run_demo(), indent=2))


if __name__ == "__main__":
    main()
