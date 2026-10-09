from __future__ import annotations

from fastapi.testclient import TestClient

from ma_precedent_transactions.api import create_app


def _payload(run_id: str = "api-final") -> dict[str, object]:
    return {
        "run_id": run_id,
        "provider_mode": "offline_fixture",
        "review_policy": "always",
        "target": {
            "target_id": "target-fintech",
            "industry": "B2B fintech infrastructure",
            "business_description": "Enterprise payments ledger and banking API software",
            "products": ["payments", "ledger", "banking API"],
            "customer_types": ["enterprise", "financial institution"],
            "geographies": ["United States", "United Kingdom"],
        },
        "acquisition_criteria": {
            "announced_from": "2020-01-01",
            "announced_to": "2025-12-31",
        },
    }


def test_health_and_checkpointed_run_review_api() -> None:
    client = TestClient(create_app())
    assert client.get("/health").json()["version"] == "1.0.0"

    started = client.post("/precedents/run", json=_payload()).json()
    assert started["status"] == "awaiting_human_review"
    assert started["review_required"] is True

    fetched = client.get("/precedents/runs/api-final").json()
    assert fetched["state"]["review_request"]["reasons"]

    resumed = client.post(
        "/precedents/runs/api-final/review",
        json={
            "action": "approve",
            "reviewer": "api-analyst",
            "rationale": "Reviewed material ambiguity and approved the documented policy.",
        },
    ).json()
    assert resumed["status"] == "completed"
    assert resumed["state"]["result"]["valuation_ranges"]
    assert resumed["state"]["result"]["human_review"]["reviewer"] == "api-analyst"


def test_api_rejects_unknown_run_duplicate_id_and_invalid_review_state() -> None:
    client = TestClient(create_app())
    assert client.get("/precedents/runs/missing").status_code == 404
    assert client.post("/precedents/run", json=_payload("duplicate")).status_code == 200
    assert client.post("/precedents/run", json=_payload("duplicate")).status_code == 409
    client.post(
        "/precedents/runs/duplicate/review",
        json={
            "action": "reject",
            "reviewer": "api-analyst",
            "rationale": "Insufficient evidence.",
        },
    )
    assert (
        client.post(
            "/precedents/runs/duplicate/review",
            json={
                "action": "approve",
                "reviewer": "api-analyst",
                "rationale": "Second review is invalid.",
            },
        ).status_code
        == 409
    )


def test_api_validates_explicit_currency_unit_period_and_evidence_fields() -> None:
    client = TestClient(create_app())
    payload = _payload("explicit-target")
    target = payload["target"]
    assert isinstance(target, dict)
    target["metrics"] = [
        {
            "metric_id": "api-revenue",
            "name": "revenue",
            "value": "100",
            "currency": "USD",
            "unit": "million",
            "period_kind": "ltm",
            "period_label": "LTM Dec-2025",
            "estimate_status": "historical",
            "basis": "reported",
            "measurement_date": "2025-12-31",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "evidence_id": "api-input:revenue",
        }
    ]
    response = client.post("/precedents/run", json=payload)

    assert response.status_code == 200
    assert response.json()["status"] == "awaiting_human_review"
