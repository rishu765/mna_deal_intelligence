from __future__ import annotations

import json
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = PROJECT_ROOT / "data" / "public_validation" / "ibm_hashicorp_2024.json"


def test_ibm_hashicorp_public_snapshot_has_explicit_basis_period_and_sources() -> None:
    case = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert date.fromisoformat(case["announcement_date"]) == date(2024, 4, 24)
    assert case["transaction_value"]["basis"] == "enterprise_value_net_of_cash"
    assert case["target_revenue"]["period"] == "FY2024"
    assert case["target_revenue"]["basis"] == "reported"
    assert {item["publisher"] for item in case["sources"]} == {
        "IBM",
        "U.S. Securities and Exchange Commission",
    }
    assert all(item["url"].startswith("https://") for item in case["sources"])


def test_ibm_hashicorp_ev_revenue_multiple_is_independently_reproducible() -> None:
    case = json.loads(FIXTURE.read_text(encoding="utf-8"))
    enterprise_value = Decimal(case["transaction_value"]["value"])
    revenue = Decimal(case["target_revenue"]["value"])

    observed = (enterprise_value / revenue).quantize(Decimal("0.001"), ROUND_HALF_UP)

    assert observed == Decimal(case["expected_ev_revenue_multiple"])
