from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from fastapi.testclient import TestClient

from ma_target_screening.api import create_app
from ma_target_screening.thesis import AcquisitionThesis

ROOT = Path(__file__).parents[1]
THESIS = AcquisitionThesis.from_json(
    (ROOT / "examples" / "screening-ranking-demo.json").read_text(encoding="utf-8")
).to_dict()


def client() -> TestClient:
    return TestClient(create_app(project_root=ROOT))


def discovered_candidate(api: TestClient) -> dict[str, Any]:
    response = api.post("/discovery", json={"thesis": THESIS})
    assert response.status_code == 200
    return next(
        item
        for item in response.json()["result"]["candidates"]
        if item["website_domain"] == "payflow.example"
    )


def enriched_profile(api: TestClient) -> dict[str, Any]:
    response = api.post(
        "/enrichment",
        json={"thesis": THESIS, "candidate": discovered_candidate(api)},
    )
    assert response.status_code == 200
    return cast(dict[str, Any], response.json()["profile"])


def test_health_and_openapi_describe_v1_endpoints() -> None:
    api = client()

    health = api.get("/health")
    schema = api.get("/openapi.json").json()

    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "service": "ma-target-screening",
        "version": "1.0.0",
        "mode": "offline_fixture",
    }
    assert {
        "/health",
        "/theses/validate",
        "/discovery",
        "/enrichment",
        "/screen",
        "/workflow/start",
        "/workflow/{workflow_id}",
        "/workflow/{workflow_id}/review",
    } <= set(schema["paths"])


def test_thesis_validation_returns_normalized_domain_schema() -> None:
    response = client().post("/theses/validate", json={"thesis": THESIS})

    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert response.json()["thesis"]["thesis_id"] == THESIS["thesis_id"]


def test_invalid_thesis_maps_to_safe_422_error() -> None:
    response = client().post("/theses/validate", json={"thesis": {"schema_version": 1}})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert "acquirer" in response.json()["error"]["message"]


def test_discovery_enrichment_and_screening_endpoints_compose() -> None:
    api = client()
    profile = enriched_profile(api)

    response = api.post(
        "/screen",
        json={
            "thesis": THESIS,
            "profiles": [profile],
            "top_n": 1,
            "include_review_required": True,
        },
    )

    assert response.status_code == 200
    shortlist = response.json()["shortlist"]
    assert shortlist["ranked_candidates"][0]["domain"] == "payflow.example"
    assert shortlist["ranked_candidates"][0]["eligibility"] == "eligible"


def test_workflow_start_get_and_human_approval() -> None:
    api = client()
    started = api.post(
        "/workflow/start",
        json={"workflow_id": "api-approval", "thesis": THESIS},
    )

    assert started.status_code == 200
    assert started.json()["status"] == "awaiting_human_review"
    assert started.json()["review_required"] is True
    assert started.json()["provisional_shortlist"]["ranked_candidates"]

    inspected = api.get("/workflow/api-approval")
    assert inspected.status_code == 200
    assert inspected.json()["status"] == "awaiting_human_review"

    approved = api.post(
        "/workflow/api-approval/review",
        json={"decision": "approve", "reviewer_notes": "Reviewed in API test."},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["review_required"] is False
    assert approved.json()["final_result"]["final_shortlist"]["ranked_candidates"]


def test_workflow_rejection_and_invalid_second_review() -> None:
    api = client()
    api.post(
        "/workflow/start",
        json={"workflow_id": "api-rejection", "thesis": THESIS},
    )
    rejected = api.post(
        "/workflow/api-rejection/review",
        json={"decision": "reject", "reviewer_notes": "Do not proceed."},
    )

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert not rejected.json()["final_result"]["final_shortlist"]["ranked_candidates"]

    repeated = api.post("/workflow/api-rejection/review", json={"decision": "approve"})
    assert repeated.status_code == 409
    assert repeated.json()["detail"] == "workflow is not awaiting human review"


def test_workflow_identity_conflict_and_unknown_workflow() -> None:
    api = client()
    first = api.post("/workflow/start", json={"workflow_id": "duplicate-id", "thesis": THESIS})
    duplicate = api.post("/workflow/start", json={"workflow_id": "duplicate-id", "thesis": THESIS})
    missing = api.get("/workflow/not-found")

    assert first.status_code == 200
    assert duplicate.status_code == 409
    assert missing.status_code == 404


def test_extra_request_fields_are_rejected() -> None:
    response = client().post(
        "/workflow/start",
        json={"workflow_id": "extra", "thesis": THESIS, "secret": "must-not-pass"},
    )

    assert response.status_code == 422
