import json
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


def seed_market_data(db_path, start_date: str, end_date: str):
    conn = sqlite3.connect(db_path)
    prices = {
        "KOSPI": (100.0, 110.0, "KRW"),
        "SPY": (100.0, 120.0, "USD"),
        "TLT": (100.0, 90.0, "USD"),
        "QQQ": (100.0, 130.0, "USD"),
        "SMH": (100.0, 135.0, "USD"),
        "GOLD": (100.0, 105.0, "USD"),
    }
    for asset_code, (start_price, end_price, currency) in prices.items():
        conn.executemany(
            """
            INSERT OR REPLACE INTO market_prices
            (asset_code, price_date, close, currency, source)
            VALUES (?, ?, ?, ?, 'test')
            """,
            [
                (asset_code, start_date, start_price, currency),
                (asset_code, end_date, end_price, currency),
            ],
        )
    conn.executemany(
        """
        INSERT OR REPLACE INTO fx_rates
        (base_currency, quote_currency, rate_date, rate, source)
        VALUES ('USD', 'KRW', ?, 1000.0, 'test')
        """,
        [(start_date,), (end_date,)],
    )
    conn.commit()
    conn.close()


def test_backtest_run_is_saved_with_curve_points(backtest_client):
    client, db_path = backtest_client
    seed_market_data(db_path, "2020-01-01", "2020-12-31")

    res = client.post(
        "/api/backtests/run",
        json={
            "name": "Core allocation 2020",
            "startDate": "2020-01-01",
            "endDate": "2020-12-31",
            "initialCapital": 100000000,
            "rebalanceFrequency": "monthly",
            "strategyMode": "triplea_dynamic",
            "riskProfile": "balanced",
            "universeId": "default_global",
            "baseCurrency": "KRW",
            "feeBps": 5,
            "slippageBps": 5,
            "taxBps": 0,
            "dataLookbackYears": 5,
        },
    )

    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["status"] == "COMPLETED"
    assert body["runId"] > 0
    assert body["initialCapital"] == 100000000
    assert body["strategyMode"] == "triplea_dynamic"
    assert body["riskProfile"] == "balanced"
    assert body["universeId"] == "default_global"
    assert body["feeBps"] == 5
    assert body["slippageBps"] == 5
    assert body["points"][0]["date"] == "2020-01-01"
    assert body["points"][0]["value"] < 100000000.0
    assert body["points"][0]["drawdown"] < 0.0
    assert body["points"][-1]["date"] == "2020-12-31"
    assert isinstance(body["totalReturn"], float)
    assert isinstance(body["annualReturn"], float)
    assert body["maxDrawdown"] >= 0
    assert body["decisions"]
    assert body["decisions"][0]["finalWeights"]

    conn = sqlite3.connect(db_path)
    run_count = conn.execute("SELECT COUNT(*) FROM backtest_runs").fetchone()[0]
    point_count = conn.execute("SELECT COUNT(*) FROM backtest_points").fetchone()[0]
    position_count = conn.execute("SELECT COUNT(*) FROM backtest_positions").fetchone()[0]
    trade_count = conn.execute("SELECT COUNT(*) FROM backtest_trades").fetchone()[0]
    decision_rows = conn.execute(
        "SELECT final_weights_json FROM backtest_decisions WHERE run_id=? ORDER BY decision_date",
        (body["runId"],),
    ).fetchall()
    sector_decision_count = conn.execute(
        "SELECT COUNT(*) FROM backtest_sector_decisions WHERE run_id=?",
        (body["runId"],),
    ).fetchone()[0]
    conn.close()
    assert run_count == 1
    assert point_count == len(body["points"])
    assert position_count == len(body["positions"])
    assert trade_count == len(body["trades"])
    assert len(decision_rows) > 0
    final_weights = json.loads(decision_rows[0][0])
    assert "SMH" not in final_weights
    assert final_weights["CASH_KRW"] == 0.15
    assert sector_decision_count >= len(decision_rows)
    assert position_count > 0
    assert trade_count > 0
    assert body["trades"][0]["fee"] > 0
    assert body["trades"][0]["slippage"] > 0


def test_backtest_runs_are_listed_and_detail_can_be_loaded(backtest_client):
    client, db_path = backtest_client
    seed_market_data(db_path, "2021-01-01", "2021-07-01")
    created = client.post(
        "/api/backtests/run",
        json={
            "name": "Default target test",
            "startDate": "2021-01-01",
            "endDate": "2021-07-01",
            "initialCapital": 50000000,
            "rebalanceFrequency": "quarterly",
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

    decision_res = client.get(f"/api/backtests/runs/{created['runId']}/decisions")
    trade_res = client.get(f"/api/backtests/runs/{created['runId']}/trades")
    position_res = client.get(f"/api/backtests/runs/{created['runId']}/positions")
    assert decision_res.status_code == 200
    assert trade_res.status_code == 200
    assert position_res.status_code == 200
    assert decision_res.json()[0]["macroRegime"] == "neutral"
    assert trade_res.json()
    assert position_res.json()


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
        },
    )

    assert res.status_code == 400
    assert "startDate" in res.json()["detail"]


def test_backtest_rejects_missing_market_data(backtest_client, monkeypatch):
    """수집기가 아무 데이터도 가져오지 못한 경우 400 반환."""
    client, _ = backtest_client

    # 수집기가 빈 결과를 반환하도록 mock (네트워크 없는 환경 시뮬레이션)
    import api.services as svc
    monkeypatch.setattr(svc, "collect_for_asset_codes", lambda *a, **k: {})

    res = client.post(
        "/api/backtests/run",
        json={
            "name": "Missing data",
            "startDate": "2022-01-01",
            "endDate": "2022-12-31",
            "initialCapital": 1000000,
            "rebalanceFrequency": "monthly",
        },
    )

    assert res.status_code == 400
    assert "Market data coverage is insufficient" in res.json()["detail"]


def test_backtest_auto_collects_and_runs(backtest_client, monkeypatch):
    """커버리지 부족 시 수집기가 호출되고, 수집 후 백테스트가 성공적으로 완료된다."""
    client, db_path = backtest_client

    import api.services as svc

    collected: list[str] = []

    def mock_collect(conn, asset_codes, start, end):
        # 수집기 호출을 기록하고 DB에 테스트 데이터 삽입
        collected.extend(asset_codes)
        seed_market_data(db_path, start.isoformat(), end.isoformat())
        return {code: 2 for code in asset_codes}

    monkeypatch.setattr(svc, "collect_for_asset_codes", mock_collect)

    res = client.post(
        "/api/backtests/run",
        json={
            "name": "Auto-collect test",
            "startDate": "2023-01-01",
            "endDate": "2023-06-30",
            "initialCapital": 50000000,
            "rebalanceFrequency": "quarterly",
        },
    )

    assert res.status_code == 200, res.text
    assert collected, "collect_for_asset_codes should have been called"
    body = res.json()
    assert body["ok"] is True
    assert len(body["points"]) > 0


def test_backtest_rejects_manual_targets_contract(backtest_client):
    client, _ = backtest_client

    res = client.post(
        "/api/backtests/run",
        json={
            "name": "Manual targets should fail",
            "startDate": "2022-01-01",
            "endDate": "2022-12-31",
            "initialCapital": 1000000,
            "strategyMode": "triplea_dynamic",
            "riskProfile": "balanced",
            "universeId": "default_global",
            "rebalanceFrequency": "monthly",
            "targets": [{"assetClass": "FOREIGN_STOCK", "targetRatio": 1}],
        },
    )

    assert res.status_code == 422
