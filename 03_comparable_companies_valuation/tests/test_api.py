from typing import Any, cast

from fastapi.testclient import TestClient

from ma_comparable_valuation.api import create_app
from ma_comparable_valuation.valuation_fixtures import demo_target_profile


def client() -> TestClient:
    return TestClient(create_app())


def test_health_and_openapi_expose_minimal_v1_surface() -> None:
    api = client()

    health = api.get("/health")
    paths = api.get("/openapi.json").json()["paths"]

    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "service": "ma-comparable-valuation",
        "version": "1.0.0",
        "mode": "offline_fixture",
    }
    assert set(paths) == {
        "/health",
        "/target/profile",
        "/valuation/run",
        "/valuation/{valuation_id}",
    }


def test_target_profile_endpoint_validates_and_preserves_decimal_strings() -> None:
    profile = cast(dict[str, Any], demo_target_profile().to_dict())

    response = client().post("/target/profile", json={"profile": profile})

    assert response.status_code == 200
    assert response.json()["profile"]["metrics"][0]["value"] == profile["metrics"][0]["value"]
    assert response.json()["profile"]["metrics"][0]["period"]["label"]


def test_end_to_end_valuation_and_retrieval() -> None:
    api = client()

    response = api.post(
        "/valuation/run",
        json={"provider_mode": "offline_fixture", "include_explanation": True},
    )

    assert response.status_code == 200
    body = response.json()
    result = body["result"]
    assert len(result["universe"]["companies"]) == 5
    assert len(result["selection"]["decisions"]) == 5
    assert len(result["peer_set"]["snapshots"]) == 5
    assert result["valuation"]["multiple_sets"]
    assert result["valuation"]["ranges"]
    assert result["valuation"]["explanation"]["evidence_ids"]
    stored = api.get(f"/valuation/{body['valuation_id']}")
    assert stored.status_code == 200
    assert stored.json() == body


def test_method_filter_is_exact_and_period_aware() -> None:
    method = "LTM Jun-2026 EV/EBITDA (reported)"

    response = client().post("/valuation/run", json={"methods": [method]})

    assert response.status_code == 200
    valuation = response.json()["result"]["valuation"]
    assert len(valuation["multiple_sets"]) == 1
    assert valuation["multiple_sets"][0]["label"] == method
    assert len(valuation["ranges"]) == 1


def test_unsupported_method_maps_to_safe_422() -> None:
    response = client().post("/valuation/run", json={"methods": ["DCF"]})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert "unsupported valuation method" in response.json()["error"]["message"]


def test_no_meaningful_target_range_maps_to_safe_422() -> None:
    profile = cast(dict[str, Any], demo_target_profile().to_dict())
    profile["metrics"] = []
    profile["capital_structure"] = None
    profile["normalization_decisions"] = []
    profile["completeness"] = None

    response = client().post("/valuation/run", json={"target_profile": profile})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "no_meaningful_valuation"
    assert "compatible positive target metric" in response.json()["error"]["message"]


def test_invalid_profile_and_extra_fields_are_rejected_without_stack_trace() -> None:
    invalid = client().post(
        "/target/profile",
        json={"profile": {"schema_version": 1}},
    )
    extra = client().post(
        "/valuation/run",
        json={"provider_mode": "offline_fixture", "api_key": "must-not-pass"},
    )

    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_request"
    assert "Traceback" not in invalid.text
    assert extra.status_code == 422
    assert "Traceback" not in extra.text


def test_unknown_valuation_returns_404() -> None:
    response = client().get("/valuation/not-found")

    assert response.status_code == 404
    assert response.json()["detail"] == "valuation not found"
