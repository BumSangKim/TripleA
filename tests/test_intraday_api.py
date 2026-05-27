import os
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from api.intraday.models import IntradayEvent, IntradayPriceSnapshot
from api.intraday.repository import insert_event, insert_snapshot


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "api_intraday.db")
    os.environ["DB_PATH"] = db_path

    import api.db as api_db
    from api.main import app

    monkeypatch.setattr(api_db, "DB_PATH", db_path)
    with TestClient(app) as test_client:
        yield test_client
    del os.environ["DB_PATH"]


def _conn(client):
    conn = sqlite3.connect(os.environ["DB_PATH"])
    conn.row_factory = sqlite3.Row
    return conn


def _snapshot(symbol, captured_at, price):
    return IntradayPriceSnapshot(
        symbol=symbol,
        market="KRX",
        captured_at=captured_at,
        price=Decimal(str(price)),
        volume=Decimal("1000"),
        source="mock",
    )


def _event(symbol="005930", event_type="DROP", level="WARNING", acknowledged=False):
    return IntradayEvent(
        symbol=symbol,
        market="KRX",
        event_type=event_type,
        event_level=level,
        detected_at=datetime(2026, 5, 27, 10, 31, tzinfo=UTC),
        lookback_minutes=5,
        base_price=Decimal("100"),
        current_price=Decimal("95"),
        change_rate=Decimal("-5"),
        volume_ratio=Decimal("3"),
        reason_code="INTRADAY_DROP_PRICE_CHANGE",
        message="drop detected",
        acknowledged=acknowledged,
    )


def test_intraday_router_is_registered(client):
    paths = {route.path for route in client.app.routes}

    assert "/api/intraday/snapshots/latest" in paths
    assert "/api/intraday/collect/run-once" in paths


def test_latest_snapshots_endpoint_returns_expected_data(client):
    conn = _conn(client)
    now = datetime(2026, 5, 27, 9, 1, tzinfo=UTC)
    insert_snapshot(_snapshot("360750", now, "100"), conn)
    insert_snapshot(_snapshot("360750", now + timedelta(minutes=1), "101"), conn)

    response = client.get("/api/intraday/snapshots/latest?symbols=360750")

    assert response.status_code == 200
    snapshots = response.json()["snapshots"]
    assert len(snapshots) == 1
    assert snapshots[0]["price"] == 101.0


def test_symbol_snapshots_endpoint_filters_time_range(client):
    conn = _conn(client)
    now = datetime(2026, 5, 27, 9, 1, tzinfo=UTC)
    insert_snapshot(_snapshot("360750", now, "100"), conn)
    insert_snapshot(_snapshot("360750", now + timedelta(minutes=10), "110"), conn)

    response = client.get(
        "/api/intraday/snapshots/360750",
        params={
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(minutes=5)).isoformat(),
        },
    )

    assert response.status_code == 200
    assert [item["price"] for item in response.json()["snapshots"]] == [100.0]


def test_recent_events_endpoint_filters(client):
    conn = _conn(client)
    insert_event(_event("005930", "DROP", "WARNING"), conn)
    insert_event(_event("360750", "SURGE", "WATCH"), conn)

    response = client.get("/api/intraday/events/recent?event_type=DROP&event_level=WARNING")

    assert response.status_code == 200
    events = response.json()["events"]
    assert len(events) == 1
    assert events[0]["symbol"] == "005930"


def test_acknowledge_endpoint_updates_state(client):
    conn = _conn(client)
    event = insert_event(_event(), conn)

    response = client.post(f"/api/intraday/events/{event.id}/acknowledge")
    events = client.get("/api/intraday/events/recent").json()["events"]

    assert response.status_code == 200
    assert events[0]["acknowledged"] is True


def test_run_once_endpoint_triggers_single_collection_pass(client):
    response = client.post("/api/intraday/collect/run-once?force=true")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["requested_symbols"] >= 1
    assert body["inserted_snapshots"] == body["successful_symbols"]


def test_intraday_api_does_not_expose_strategy_or_order_side_effects(client):
    paths = {route.path for route in client.app.routes if "intraday" in route.path}

    assert all("order" not in path for path in paths)
    assert all("score" not in path for path in paths)
