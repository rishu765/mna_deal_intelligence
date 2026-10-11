"""Run the deterministic M3 reconciliation demo."""

from __future__ import annotations

from ma_deal_intelligence.reconciliation import ReconciliationService
from ma_deal_intelligence.reconciliation_fixtures import rich_reconciliation_state


def main() -> None:
    state = rich_reconciliation_state()
    result = ReconciliationService().reconcile(state)
    snapshot = result.snapshot

    print("Deal:", snapshot.deal_context.deal_id)
    print("Specialist outputs: P1, P2, P3, P4, P5")
    print("\nUnified metrics")
    for view in snapshot.metrics:
        observations = ", ".join(
            f"{item.source_project.value}={item.value} {item.unit} ({item.basis.value})"
            for item in view.observations
        )
        print(f"- {view.metric_type}: {observations} [{view.status.value}]")

    print("\nReconciliation issues")
    for issue in snapshot.issues:
        print(f"- {issue.issue_type.value}: {issue.description}")

    print("\nStale outputs and recomputation requests")
    for item in snapshot.stale_outputs:
        print(f"- {item.output_id}: {item.status.value} - {item.reason}")
    for item in snapshot.recomputation_requests:
        print(f"- {item.request_id}: {item.target_capability}")

    comparison = snapshot.valuation_comparison
    print("\nValuation methods")
    for entry in comparison.entries:
        value = entry.valuation
        print(f"- {value.method.value}: {value.low} / {value.midpoint} / {value.high}")
    print("Midpoint divergence:", comparison.midpoint_gap_percent)

    print("\nDiligence impacts")
    for insight in snapshot.impact_insights:
        print(f"- {insight.title}: {insight.qualitative_impact}")

    print("\nAnalyst review queue")
    for item in snapshot.review_queue:
        print(f"- {item.priority.value}: {item.reason}")

    print("\nOpen questions")
    for question in snapshot.open_questions:
        print(f"- {question.question}")


if __name__ == "__main__":
    main()
