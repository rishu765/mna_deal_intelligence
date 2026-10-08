"""Run the complete M4/5 fixture valuation without network or API credentials."""

from __future__ import annotations

import json
from decimal import Decimal

from ma_comparable_valuation.valuation import (
    FixtureValuationExplanationProvider,
    ValuationEngine,
)
from ma_comparable_valuation.valuation_fixtures import (
    demo_multiple_requests,
    demo_peer_set,
    demo_target_profile,
)


def _primitive(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, tuple):
        return [_primitive(item) for item in value]
    if isinstance(value, list):
        return [_primitive(item) for item in value]
    if isinstance(value, dict):
        return {key: _primitive(item) for key, item in value.items()}
    return value


def main() -> None:
    target = demo_target_profile()
    peer_set = demo_peer_set()
    engine = ValuationEngine()
    output = engine.build_output(
        target,
        peer_set,
        demo_multiple_requests(),
        FixtureValuationExplanationProvider(),
    )
    peer_equity_and_ev = []
    for snapshot in peer_set.snapshots:
        equity = engine.equity_value(snapshot.company.identity.company_id, snapshot.market_metrics)
        enterprise = engine.enterprise_value(snapshot)
        peer_equity_and_ev.append(
            {
                "company_id": snapshot.company.identity.company_id,
                "equity_value": equity.value,
                "enterprise_value": enterprise.value,
                "status": enterprise.status.value,
                "warnings": enterprise.warnings,
                "trace": enterprise.trace.formula,
            }
        )
    payload = {
        "target": target.target.identity.name,
        "peer_equity_and_enterprise_values": peer_equity_and_ev,
        "multiple_sets": [
            {
                "label": item.request.label,
                "observations": [
                    {
                        "company_id": multiple.company_id,
                        "status": multiple.status.value,
                        "value": multiple.value,
                        "reason": multiple.treatment_reason,
                        "period": (
                            None
                            if multiple.denominator_period is None
                            else multiple.denominator_period.label
                        ),
                    }
                    for multiple in item.multiples
                ],
                "statistics": {
                    "count": item.statistics.count,
                    "excluded_count": item.statistics.excluded_count,
                    "minimum": item.statistics.minimum,
                    "percentile_25": item.statistics.percentile_25,
                    "median": item.statistics.median,
                    "percentile_75": item.statistics.percentile_75,
                    "maximum": item.statistics.maximum,
                    "outliers": item.statistics.outlier_multiple_ids,
                    "warnings": item.statistics.warnings,
                },
            }
            for item in output.multiple_sets
        ],
        "valuation_ranges": [
            {
                "method": item.request.label,
                "low": item.low.implied_value,
                "mid": item.mid.implied_value,
                "high": item.high.implied_value,
                "mid_equity_value": item.mid.implied_equity_value,
                "mid_per_share": item.mid.implied_per_share,
                "trace": item.mid.trace.formula,
            }
            for item in output.ranges
        ],
        "explanation": (
            None
            if output.explanation is None
            else {
                "peer_set_assessment": output.explanation.peer_set_assessment,
                "preferred_metrics": output.explanation.preferred_metrics,
                "key_drivers": output.explanation.key_drivers,
                "outlier_commentary": output.explanation.outlier_commentary,
                "range_interpretation": output.explanation.range_interpretation,
                "risks_and_caveats": output.explanation.risks_and_caveats,
                "evidence_ids": output.explanation.evidence_ids,
            }
        ),
    }
    print(json.dumps(_primitive(payload), indent=2))


if __name__ == "__main__":
    main()
