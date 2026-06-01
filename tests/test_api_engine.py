import os
import sqlite3

import pytest
from fastapi.testclient import TestClient

from api.features.targets.schemas import TargetItem
from api.features.rebalancing.repository import RebalancingRepository


@pytest.fixture()
def engine_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "engine.db")
    os.environ["DB_PATH"] = db_path

    import api.db.connection as api_db
    from api.db.initialize import initialize_database

    monkeypatch.setattr(api_db, "DB_PATH", db_path)
    initialize_database()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    account_id = conn.execute("""
        INSERT INTO accounts (name, type, account_type, include_in_rebalancing)
        VALUES ('Engine Test', 'GENERAL', 'GENERAL', 1)
    """).lastrowid
    conn.executemany("""
        INSERT INTO holdings
        (account_id, ticker, name, quantity, current_price, market_value, profit, asset_class, strategy_bucket)
        VALUES (?, ?, ?, 1, 1, ?, 0, ?, ?)
    """, [
        (account_id, "AGG", "Aggressive", 50, "해외주식", "AGGRESSIVE_ALPHA"),
        (account_id, "DEF", "Defensive", 20, "채권", "DEFENSIVE_CORE"),
        (account_id, "CASH", "Cash", 30, "현금", "LIQUIDITY"),
    ])
    conn.commit()
    conn.close()

    yield db_path

    del os.environ["DB_PATH"]


def test_risk_budget_items_calculate_bucket_status(engine_db):
    conn = sqlite3.connect(engine_db)
    conn.row_factory = sqlite3.Row

    items = {item.strategyBucket: item for item in RebalancingRepository(conn).get_risk_budget()}

    conn.close()
    assert items["AGGRESSIVE_ALPHA"].currentRatio == 50.0
    assert items["AGGRESSIVE_ALPHA"].level == "danger"
    assert items["AGGRESSIVE_ALPHA"].action == "REDUCE"
    assert items["DEFENSIVE_CORE"].action == "INCREASE"
    assert items["LIQUIDITY"].currentRatio == 30.0


def test_risk_budget_endpoint_returns_engine_allocations(engine_db):
    from api.main import app

    with TestClient(app) as client:
        res = client.get("/api/engine/risk-budget")

    assert res.status_code == 200
    buckets = {item["strategyBucket"]: item for item in res.json()}
    assert {"AGGRESSIVE_ALPHA", "DEFENSIVE_CORE", "LIQUIDITY"}.issubset(buckets)
    assert buckets["AGGRESSIVE_ALPHA"]["level"] == "danger"


def test_rebalance_results_include_risk_budget_reason(engine_db):
    conn = sqlite3.connect(engine_db)
    conn.row_factory = sqlite3.Row
    target = TargetItem(
        asset_class="해외주식",
        target_type="asset_allocation",
        currentRatio=50,
        targetRatio=30,
        deviation=20,
        level="danger",
    )

    _, rows = RebalancingRepository(conn).record_rebalance_results("local", [target], 100000)

    conn.close()
    assert rows[0].reason.startswith("목표 초과")
    assert "위험예산 AGGRESSIVE_ALPHA danger" in rows[0].reason
