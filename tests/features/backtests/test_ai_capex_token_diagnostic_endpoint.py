from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.features.backtests.router import router


FORBIDDEN_OUTPUT_KEYS = {"account_id", "accountId", "order", "orders", "orderCandidate", "execution", "broker"}


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_ai_capex_token_diagnostic_endpoint_returns_gated_fixture_flow() -> None:
    response = client().post("/api/backtests/ai-capex-token/diagnostic/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "DIAGNOSTIC_ONLY"
    assert payload["diagnosticOnly"] is True
    assert payload["productionReady"] is False
    assert payload["productionGate"] == {
        "enabled": False,
        "productionEnabled": False,
        "approved": False,
        "requiresBacktestPass": True,
        "requiresWalkForwardPass": True,
    }
    assert {row["dominantScenario"] for row in payload["scenarioRows"] if row["dominantScenario"]} >= {"S1", "S3", "S7"}
    assert any(row["status"] == "REVIEW_REQUIRED" for row in payload["scenarioRows"])
    assert "AI_CAPEX_TOKEN_DIAGNOSTIC_ONLY" in payload["reasonCodes"]


def test_ai_capex_token_diagnostic_endpoint_has_no_order_or_execution_fields() -> None:
    payload = client().post("/api/backtests/ai-capex-token/diagnostic/run").json()

    assert _find_forbidden_keys(payload) == []


def _find_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    matches: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in FORBIDDEN_OUTPUT_KEYS:
                matches.append(child_path)
            matches.extend(_find_forbidden_keys(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            matches.extend(_find_forbidden_keys(child, f"{path}[{index}]"))
    return matches
