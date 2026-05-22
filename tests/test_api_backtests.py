import os
import sqlite3

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def backtest_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "backtests.db")
    os.environ["DB_PATH"] = db_path

    from api import db as api_db
    from api.main import app

    monkeypatch.setattr(api_db, "DB_PATH", db_path)
    api_db.ensure_dashboard_tables()

    with TestClient(app) as client:
        yield client, db_path

    del os.environ["DB_PATH"]


def test_backtest_run_is_saved_with_curve_points(backtest_client):
    client, db_path = backtest_client

    res = client.post(
        "/api/backtests/run",
        json={
            "name": "Core allocation 2020",
            "startDate": "2020-01-01",
            "endDate": "2020-12-31",
            "initialCapital": 100000000,
            "rebalanceFrequency": "monthly",
            "targets": [
                {"assetClass": "DOMESTIC_STOCK", "targetRatio": 0.25},
                {"assetClass": "FOREIGN_STOCK", "targetRatio": 0.35},
                {"assetClass": "BOND", "targetRatio": 0.20},
                {"assetClass": "CASH", "targetRatio": 0.20},
            ],
        },
    )

    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["status"] == "COMPLETED"
    assert body["runId"] > 0
    assert body["initialCapital"] == 100000000
    assert body["points"][0] == {
        "date": "2020-01-01",
        "value": 100000000.0,
        "drawdown": 0.0,
    }
    assert body["points"][-1]["date"] == "2020-12-31"
    assert isinstance(body["totalReturn"], float)
    assert isinstance(body["annualReturn"], float)
    assert body["maxDrawdown"] >= 0

    conn = sqlite3.connect(db_path)
    run_count = conn.execute("SELECT COUNT(*) FROM backtest_runs").fetchone()[0]
    point_count = conn.execute("SELECT COUNT(*) FROM backtest_points").fetchone()[0]
    conn.close()
    assert run_count == 1
    assert point_count == len(body["points"])


def test_backtest_runs_are_listed_and_detail_can_be_loaded(backtest_client):
    client, _ = backtest_client
    created = client.post(
        "/api/backtests/run",
        json={
            "name": "Default target test",
            "startDate": "2021-01-01",
            "endDate": "2021-07-01",
            "initialCapital": 50000000,
            "rebalanceFrequency": "quarterly",
            "targets": [],
        },
    ).json()

    list_res = client.get("/api/backtests/runs?limit=5")
    assert list_res.status_code == 200
    rows = list_res.json()
    assert rows[0]["runId"] == created["runId"]
    assert rows[0]["points"]

    detail_res = client.get(f"/api/backtests/runs/{created['runId']}")
    assert detail_res.status_code == 200
    assert detail_res.json()["name"] == "Default target test"


def test_backtest_rejects_invalid_request(backtest_client):
    client, _ = backtest_client

    res = client.post(
        "/api/backtests/run",
        json={
            "name": "Bad dates",
            "startDate": "2022-01-01",
            "endDate": "2021-01-01",
            "initialCapital": 1000000,
            "rebalanceFrequency": "monthly",
            "targets": [{"assetClass": "CASH", "targetRatio": 1}],
        },
    )

    assert res.status_code == 400
    assert "startDate" in res.json()["detail"]
