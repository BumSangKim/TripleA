import os
import sqlite3

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def order_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "orders.db")
    os.environ["DB_PATH"] = db_path

    import api.db.connection as api_db
    from api.db.initialize import initialize_database
    from api.main import app

    monkeypatch.setattr(api_db, "DB_PATH", db_path)
    initialize_database()

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO accounts
        (name, type, account_type, include_in_rebalancing, initial_value)
        VALUES ('Paper ISA', 'ISA', 'ISA', 1, 100000)
        """
    )
    account_id = conn.execute("SELECT id FROM accounts LIMIT 1").fetchone()[0]
    conn.executemany(
        """
        INSERT INTO holdings
        (account_id, ticker, name, quantity, current_price, market_value, profit, asset_class)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (account_id, "005930", "삼성전자", 1, 80000, 80000, 0, "국내주식"),
            (account_id, "069500", "KODEX 200", 1, 20000, 20000, 0, "ETF"),
        ],
    )
    conn.commit()
    conn.close()

    with TestClient(app) as client:
        yield client, db_path

    del os.environ["DB_PATH"]


def test_order_draft_generates_rebalancing_candidates(order_client):
    client, _ = order_client

    res = client.post(
        "/api/orders/draft",
        json={"mode": "paper", "source": "rebalancing", "maxOrderAmount": 10000},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "paper"
    assert body["source"] == "rebalancing"
    assert body["status"] == "DRAFT"
    assert body["itemCount"] > 0
    assert all(item["amount"] <= 10000 for item in body["items"])
    assert {"BUY", "SELL"}.issubset({item["side"] for item in body["items"]})


def test_order_draft_rejects_read_only_mode(order_client):
    client, _ = order_client

    res = client.post(
        "/api/orders/draft",
        json={"mode": "mock", "source": "rebalancing"},
    )

    assert res.status_code == 403


def test_paper_order_execute_records_manual_approval_only(order_client):
    client, db_path = order_client
    draft = client.post(
        "/api/orders/draft",
        json={"mode": "paper", "source": "rebalancing", "maxOrderAmount": 10000},
    ).json()

    res = client.post(
        "/api/orders/execute",
        json={
            "mode": "paper",
            "orderDraftId": draft["draftId"],
            "confirmText": "모의 주문을 승인합니다",
        },
    )

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "APPROVED_NOT_SENT"
    assert {item["status"] for item in body["items"]} == {"APPROVED_NOT_SENT"}

    conn = sqlite3.connect(db_path)
    log = conn.execute(
        "SELECT event, status FROM order_logs WHERE draft_id=? ORDER BY id DESC LIMIT 1",
        (draft["draftId"],),
    ).fetchone()
    conn.close()
    assert log == ("PAPER_APPROVED", "APPROVED_NOT_SENT")


def test_order_drafts_history_lists_recent_drafts(order_client):
    client, _ = order_client
    created = client.post(
        "/api/orders/draft",
        json={"mode": "paper", "source": "rebalancing", "maxOrderAmount": 10000},
    ).json()

    res = client.get("/api/orders/drafts?mode=paper&limit=5")

    assert res.status_code == 200
    rows = res.json()
    assert rows[0]["draftId"] == created["draftId"]
    assert rows[0]["itemCount"] == created["itemCount"]
    assert rows[0]["items"]


def test_live_order_execute_stays_disabled(order_client):
    client, _ = order_client
    draft = client.post(
        "/api/orders/draft",
        json={"mode": "live", "source": "rebalancing", "maxOrderAmount": 10000},
    ).json()

    res = client.post(
        "/api/orders/execute",
        json={
            "mode": "live",
            "orderDraftId": draft["draftId"],
            "confirmText": "실전 주문을 확인합니다",
        },
    )

    assert res.status_code == 403
