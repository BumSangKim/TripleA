from __future__ import annotations

from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.features.capex_cycle.dependencies import get_capex_cycle_service
from api.features.capex_cycle.schemas import CapexCycleScoreResponse, ReasonItem
from api.features.router_registry import include_feature_routers


def _build_client() -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_capex_cycle_service] = lambda: FakeCapexCycleService()
    include_feature_routers(app)
    return TestClient(app)


def test_router_registry_includes_capex_cycle_routes():
    client = _build_client()
    paths = {route.path for route in client.app.routes}

    assert "/api/capex-cycle/scores" in paths
    assert "/api/capex-cycle/scenarios" in paths
    assert "/api/capex-cycle/valuation/{asset_id}" in paths


def test_existing_feature_routes_remain_registered():
    client = _build_client()
    paths = {route.path for route in client.app.routes}

    assert "/api/data/status" in paths
    assert "/api/market-data/assets" in paths
    assert any(path.startswith("/api/intraday") for path in paths)


def test_capex_endpoint_can_be_reached_through_registered_app():
    client = _build_client()

    response = client.get("/api/capex-cycle/scores")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["score"] == 0.62
    assert payload[0]["reason_codes"][0]["code"] == "AI_CAPEX_CYCLE_COMPUTED"


def test_registered_capex_routes_are_readonly():
    client = _build_client()
    capex_routes = [route for route in client.app.routes if route.path.startswith("/api/capex-cycle")]

    assert capex_routes
    assert all(route.methods <= {"GET", "HEAD"} for route in capex_routes)
    assert not any("order" in route.path.lower() or "execution" in route.path.lower() for route in capex_routes)


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
