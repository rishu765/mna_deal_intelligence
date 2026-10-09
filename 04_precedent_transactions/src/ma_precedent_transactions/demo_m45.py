"""Offline deterministic M4/5 comparable-deal and valuation demonstration."""

from __future__ import annotations

import json

from ma_precedent_transactions.precedent import (
    FixtureValuationExplanationProvider,
    PrecedentAnalysisService,
    precedent_fixture_inputs,
)


def run_demo() -> dict[str, object]:
    comparable, target, transactions = precedent_fixture_inputs()
    output = PrecedentAnalysisService().analyze(
        comparable,
        target,
        transactions,
        explanation_provider=FixtureValuationExplanationProvider(),
    )
    return {
        "selection": {
            "included": list(output.selection.selected_transaction_ids),
            "separate": list(output.selection.separate_transaction_ids),
            "decisions": {
                item.transaction_id: {
                    "decision": item.decision.value,
                    "rationale": item.rationale,
                    "warnings": list(item.warnings),
                }
                for item in output.selection.decisions
            },
        },
        "multiple_sets": [
            {
                "kind": item.key.kind.value,
                "currency": item.key.currency,
                "period_kind": item.key.period_kind,
                "basis": item.key.basis.value,
                "count": item.statistics.count,
                "p25": _decimal(item.statistics.percentile_25),
                "median": _decimal(item.statistics.median),
                "p75": _decimal(item.statistics.percentile_75),
                "outliers": list(item.statistics.outlier_multiple_ids),
                "warnings": list(item.statistics.warnings),
            }
            for item in output.multiple_sets
        ],
        "valuation_ranges": [
            {
                "kind": item.key.kind.value,
                "basis": item.key.basis.value,
                "low_ev": _decimal(item.low.implied_enterprise_value),
                "mid_ev": _decimal(item.mid.implied_enterprise_value),
                "high_ev": _decimal(item.high.implied_enterprise_value),
                "mid_equity": _decimal(item.mid.implied_equity_value),
                "mid_per_share": _decimal(item.mid.implied_per_share),
            }
            for item in output.ranges
        ],
        "explanation": None
        if output.explanation is None
        else {
            "assessment": output.explanation.precedent_set_assessment,
            "focus": list(output.explanation.recommended_multiple_focus),
            "caveats": list(output.explanation.valuation_caveats),
            "evidence_ids": list(output.explanation.evidence_ids),
        },
        "warnings": list(output.warnings),
        "scope_guard": "No LangGraph runtime, analyst UI, API, or final V1 evaluation.",
    }


def _decimal(value: object) -> str | None:
    return None if value is None else str(value)


def main() -> None:
    print(json.dumps(run_demo(), indent=2))


if __name__ == "__main__":
    main()
