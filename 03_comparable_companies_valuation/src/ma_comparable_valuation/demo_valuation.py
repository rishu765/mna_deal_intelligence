"""Run the complete Project 3 V1 workflow offline and print auditable JSON."""

from __future__ import annotations

import json

from ma_comparable_valuation.presentation import workflow_to_dict
from ma_comparable_valuation.workflow import OfflineValuationService


def main() -> None:
    result = OfflineValuationService().run()
    payload = workflow_to_dict(result)
    payload["demo"] = {
        "mode": "offline_fixture",
        "stages": [
            "target_profile",
            "comparable_universe",
            "peer_selection",
            "market_financial_ingestion",
            "comparable_snapshots",
            "trading_multiples",
            "peer_statistics",
            "implied_valuation",
            "ev_equity_bridge",
            "valuation_range",
            "ai_assisted_explanation",
        ],
        "notice": (
            "Synthetic public-safe fixtures demonstrate behavior; values are not investment advice."
        ),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
