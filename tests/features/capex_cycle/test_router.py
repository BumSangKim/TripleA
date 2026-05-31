from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.features.capex_cycle.dependencies import get_capex_cycle_service
from api.features.capex_cycle.router import router
from api.features.capex_cycle.schemas import CapexCycleScoreResponse, CapexScenarioResponse, CapexValuationResponse, ReasonItem, WarningItem


def _build_client(service=None) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    if service is not None:
        app.dependency_overrides[get_capex_cycle_service] = lambda: service
    return TestClient(app)


def test_scores_endpoint_returns_readonly_schema_with_fake_service():
    client = _build_client(FakeCapexCycleService())

    response = client.get("/api/capex-cycle/scores", params={"as_of_date": "2026-05-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["score"] == 0.62
    assert payload[0]["confidence"] == 0.81
    assert payload[0]["data_quality"] == 0.74
    assert payload[0]["reason_codes"][0]["code"] == "AI_CAPEX_CYCLE_COMPUTED"
    assert payload[0]["warnings"] == []


def test_scenario_endpoint_returns_explainable_schema():
    client = _build_client(FakeCapexCycleService())

    response = client.get("/api/capex-cycle/scenarios")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dominant_scenario"] == "ai_buildout_continues"
    assert "scenario_distribution" in payload
    assert "reason_codes" in payload
    assert "warnings" in payload


def test_unknown_valuation_asset_returns_conservative_unavailable_response():
    client = _build_client(FakeCapexCycleService())

    response = client.get("/api/capex-cycle/valuation/unknown")

    assert response.status_code == 200
    payload = response.json()
    assert payload["asset_id"] == "unknown"
    assert payload["fair_value"] is None
    assert payload["fair_value_ratio"] is None
    assert payload["warnings"][0]["code"] == "VALUATION_UNAVAILABLE"


def test_router_exposes_no_mutation_routes():
    client = _build_client(FakeCapexCycleService())
    paths = {route.path: route.methods for route in client.app.routes if route.path.startswith("/api/capex-cycle")}

    assert set(paths) == {
        "/api/capex-cycle/scores",
        "/api/capex-cycle/scenarios",
        "/api/capex-cycle/valuation/{asset_id}",
    }
    for methods in paths.values():
        assert methods <= {"GET", "HEAD"}


def test_router_has_no_forbidden_layer_imports():
    source = Path("api/features/capex_cycle/router.py").read_text(encoding="utf-8").lower()

    forbidden = ["api.brokers", "api.strategy", "api.features.orders", "kis", "submit_order", "execute_draft"]
    assert not [item for item in forbidden if item in source]


class FakeCapexCycleService:
    def get_scores(self, *, as_of_date=None, asset_id=None):
        return [
            CapexCycleScoreResponse(
                feature_id="feature:ai_capex_cycle",
                entity_id="ai_infrastructure",
                score=0.62,
                confidence=0.81,
                data_quality=0.74,
                as_of_date=date(2026, 5, 31),
                parameter_version="params_v1",
                model_version="model_v1",
                reason_codes=[ReasonItem(code="AI_CAPEX_CYCLE_COMPUTED", category="feature")],
                warnings=[],
            )
        ]

    def get_scenario(self, *, as_of_date=None):
        return CapexScenarioResponse(
            scenario_id="capex_scenario_distribution",
            score=0.51,
            confidence=0.8,
            data_quality=0.75,
            scenario_distribution={"ai_buildout_continues": 0.51, "credit_stress": 0.09},
            dominant_scenario="ai_buildout_continues",
            as_of_date=date(2026, 5, 31),
            parameter_version="scenario_params_v1",
            model_version="scenario_model_v1",
            reason_codes=[ReasonItem(code="CAPEX_SCENARIO_DISTRIBUTION_COMPUTED", category="scenario")],
            warnings=[],
        )

    def get_valuation(self, *, asset_id, as_of_date=None):
        return CapexValuationResponse(
            asset_id=asset_id,
            score=0.5,
            confidence=0.0,
            data_quality=0.0,
            fair_value=None,
            current_price=None,
            fair_value_ratio=None,
            target_per=None,
            as_of_date=date(2026, 5, 31),
            parameter_version="unavailable",
            model_version="valuation_model_v1",
            reason_codes=[ReasonItem(code="VALUATION_UNAVAILABLE", category="valuation")],
            warnings=[
                WarningItem(
                    code="VALUATION_UNAVAILABLE",
                    severity="WARNING",
                    source="valuation",
                    message="missing valuation inputs",
                )
            ],
        )
