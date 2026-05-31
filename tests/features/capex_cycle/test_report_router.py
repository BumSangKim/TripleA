from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.features.capex_cycle.dependencies import get_capex_cycle_service
from api.features.capex_cycle.router import router
from api.features.capex_cycle.schemas import (
    BioCapexBottleneckScoreResponse,
    CapexCycleScoreResponse,
    CapexScenarioResponse,
    CapexValuationResponse,
    ReasonItem,
    WarningItem,
)


AS_OF = date(2026, 5, 31)


def build_client(service=None) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    if service is not None:
        app.dependency_overrides[get_capex_cycle_service] = lambda: service
    return TestClient(app)


def reason(code: str) -> ReasonItem:
    return ReasonItem(code=code, category="fixture")


def warning(code: str) -> WarningItem:
    return WarningItem(code=code, severity="WARNING", source="fixture", message="fixture warning")


def test_report_endpoint_returns_200_with_fake_service() -> None:
    client = build_client(FakeCapexCycleService())

    response = client.get(
        "/api/capex-cycle/report",
        params={"as_of_date": "2026-05-31", "asset_ids": "sample_ai"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["as_of_date"] == "2026-05-31"
    assert "source_health" in payload
    assert payload["ai_capex_score"]["score"] == 0.62
    assert payload["scenario_distribution"]["dominant_scenario"] == "ai_buildout_continues"
    assert payload["valuation_views"][0]["asset_id"] == "sample_ai"
    assert payload["warnings"]
    assert payload["reason_codes"]
    assert payload["versions"]["report_schema_version"] == "capex_report_v1"


def test_report_endpoint_exposes_no_mutation_routes() -> None:
    client = build_client(FakeCapexCycleService())
    paths = {route.path: route.methods for route in client.app.routes if route.path.startswith("/api/capex-cycle")}

    assert "/api/capex-cycle/report" in paths
    for methods in paths.values():
        assert methods <= {"GET", "HEAD"}


def test_report_router_has_no_forbidden_imports() -> None:
    source = Path("api/features/capex_cycle/router.py").read_text()
    forbidden = (
        "api.brokers",
        "api.features.orders",
        "api.strategy",
        "submit_order",
        "place_order",
        "execute_draft",
    )

    assert not any(term in source for term in forbidden)


class FakeCapexCycleService:
    def get_scores(self, *, as_of_date=None, asset_id=None):
        return [
            CapexCycleScoreResponse(
                feature_id="feature:ai_capex_cycle",
                entity_id="ai_infrastructure",
                score=0.62,
                confidence=0.81,
                data_quality=0.74,
                as_of_date=AS_OF,
                parameter_version="ai_params_v1",
                model_version="ai_model_v1",
                reason_codes=[reason("AI_CAPEX_CYCLE_COMPUTED")],
                warnings=[],
            ),
            BioCapexBottleneckScoreResponse(
                asset_id="sample_bio_supplier",
                score=0.58,
                confidence=0.7,
                data_quality=0.8,
                component_scores={"structural_moat": 0.6},
                core_anchor_allowed=False,
                as_of_date=AS_OF,
                parameter_version="bio_params_v1",
                model_version="bio_model_v1",
                reason_codes=[reason("BIO_CAPEX_BOTTLENECK_COMPUTED")],
                warnings=[warning("BIO_REVIEW")],
            ),
        ]

    def get_scenario(self, *, as_of_date=None):
        return CapexScenarioResponse(
            scenario_id="capex_scenario_distribution",
            score=0.51,
            confidence=0.8,
            data_quality=0.75,
            scenario_distribution={"ai_buildout_continues": 0.51, "credit_stress": 0.09},
            dominant_scenario="ai_buildout_continues",
            as_of_date=AS_OF,
            parameter_version="scenario_params_v1",
            model_version="scenario_model_v1",
            reason_codes=[reason("CAPEX_SCENARIO_DISTRIBUTION_COMPUTED")],
            warnings=[],
        )

    def get_valuation(self, *, asset_id, as_of_date=None):
        return CapexValuationResponse(
            asset_id=asset_id,
            score=0.54,
            confidence=0.71,
            data_quality=0.69,
            fair_value=125.0,
            current_price=100.0,
            fair_value_ratio=1.25,
            target_per=22.0,
            as_of_date=AS_OF,
            parameter_version="valuation_params_v1",
            model_version="valuation_model_v1",
            reason_codes=[reason("CAPEX_VALUATION_COMPUTED")],
            warnings=[],
        )
