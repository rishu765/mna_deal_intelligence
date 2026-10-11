from __future__ import annotations

from fastapi.testclient import TestClient

from ma_deal_intelligence.api import create_app


def _payload(query: str) -> dict[str, object]:
    return {
        "user_query": query,
        "deal_context": {
            "deal_id": "deal:api-test",
            "target_name": "TargetCo",
            "sector": ["B2B SaaS"],
            "geography": ["India"],
            "reporting_currency": "USD",
            "as_of_date": "2026-01-01",
        },
        "document_ids": ["doc:fixture-vdr"],
    }


def test_health_create_status_result_and_safe_trace() -> None:
    client = TestClient(create_app())
    assert client.get("/health").json() == {
        "status": "ok",
        "mode": "offline",
        "version": "1.0.0",
    }
    created = client.post(
        "/deal-intelligence/runs",
        json=_payload("Compare trading comps and precedents for TargetCo"),
    )
    assert created.status_code == 201
    run_id = created.json()["run_id"]
    assert created.json()["selected_capabilities"][-2:] == [
        "p3.produce_valuation_range",
        "p4.produce_valuation_range",
    ]
    result = client.get(f"/deal-intelligence/runs/{run_id}/result")
    assert result.status_code == 200
    assert len(result.json()["output"]["valuations"]) == 2
    trace = client.get(f"/deal-intelligence/runs/{run_id}/trace")
    assert trace.status_code == 200
    assert trace.json()["events"]
    assert "message" not in trace.json()["events"][0]


def test_review_and_resume_use_checkpointed_state() -> None:
    client = TestClient(create_app())
    created = client.post(
        "/deal-intelligence/runs",
        json=_payload("Evaluate the acquisition of TargetCo"),
    )
    body = created.json()
    assert body["status"] == "review_required"
    review = body["active_review"]
    response = client.post(
        f"/deal-intelligence/runs/{body['run_id']}/review",
        json={
            "review_id": review["review_id"],
            "decision": "run_both",
            "rationale": "Retain both approved EBITDA scenarios.",
            "reviewer": "API Reviewer",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] in {"completed", "completed_with_warnings"}
    assert client.get(f"/deal-intelligence/runs/{body['run_id']}/result").status_code == 200


def test_api_handles_unknown_not_ready_and_invalid_review_without_stack_trace() -> None:
    client = TestClient(create_app())
    assert client.get("/deal-intelligence/runs/unknown").status_code == 404
    created = client.post(
        "/deal-intelligence/runs",
        json=_payload("Evaluate the acquisition of TargetCo"),
    ).json()
    assert client.get(f"/deal-intelligence/runs/{created['run_id']}/result").status_code == 409
    invalid = client.post(
        f"/deal-intelligence/runs/{created['run_id']}/resume",
        json={
            "review_id": "wrong",
            "decision": "defer",
            "rationale": "Need more evidence.",
            "reviewer": "Reviewer",
        },
    )
    assert invalid.status_code == 400
    assert "traceback" not in invalid.text.casefold()
