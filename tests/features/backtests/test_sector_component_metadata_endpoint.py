from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.features.backtests.router import router


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_metadata_endpoint_returns_200() -> None:
    response = client().get("/api/backtests/sector-components/ui-metadata")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_all_option_and_three_sector_options_returned() -> None:
    payload = client().get("/api/backtests/sector-components/ui-metadata").json()

    assert payload["allSectorOption"]["value"] == "ALL"
    assert payload["allSectorOption"]["sectorScope"] == {"mode": "all", "sectorId": None}
    assert [option["sectorId"] for option in payload["sectorOptions"]] == ["SEMICONDUCTOR", "POWER_GRID", "BATTERY"]
    assert [option["portfolioId"] for option in payload["sectorOptions"]] == [
        "sector_semiconductor_trade_reference_v1",
        "sector_power_grid_trade_reference_v1",
        "sector_battery_trade_reference_v1",
    ]
    assert [option["assetCount"] for option in payload["sectorOptions"]] == [18, 19, 20]
    assert payload["sectorOptions"][0]["assets"][0]["assetCode"] == "000660"
    assert payload["sectorOptions"][1]["assets"][0]["assetCode"] == "010120"


def test_metadata_includes_versions_and_warnings() -> None:
    payload = client().get("/api/backtests/sector-components/ui-metadata").json()

    assert payload["parameterVersion"] == "sector_component_backtest_v0"
    assert payload["modelVersion"] == "sector_component_backtest_model_v0"
    assert "SECTOR_COMPONENT_UI_METADATA_BUILT" in payload["reasonCodes"]
    assert any(option["warnings"] for option in payload["sectorOptions"])


def test_existing_route_paths_are_preserved() -> None:
    paths = {route.path for route in client().app.routes}

    assert "/api/backtests/run" in paths
    assert "/api/backtests/runs" in paths
    assert "/api/backtests/runs/{run_id}" in paths
    assert "/api/backtests/sector-components/ui-metadata" in paths


def test_router_has_no_repository_or_db_import() -> None:
    source = Path("api/features/backtests/router.py").read_text(encoding="utf-8")

    assert "repository" not in source
    assert "from api.db" not in source
    assert "get_conn" not in source
