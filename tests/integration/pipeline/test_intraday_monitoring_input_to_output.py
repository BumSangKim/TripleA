from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from api.features.intraday.models import IntradayEvent, IntradayPriceSnapshot
from api.features.intraday.repository import insert_event, insert_snapshot, recent_events


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "intraday_input_to_output.db")
    os.environ["DB_PATH"] = db_path

    import api.db.connection as api_db
    from api.main import app

    monkeypatch.setattr(api_db, "DB_PATH", db_path)
    with TestClient(app) as test_client:
        yield test_client, db_path
    del os.environ["DB_PATH"]


def test_intraday_monitoring_raw_input_to_api_output_is_display_only(client):
    test_client, db_path = client
    conn = _conn(db_path)
    captured_at = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
    detected_at = captured_at + timedelta(minutes=5)
    first = insert_snapshot(_snapshot(captured_at, "100", quality_score=0.72, is_stale=True), conn)
    latest = insert_snapshot(_snapshot(captured_at + timedelta(minutes=1), "106", quality_score=0.95), conn)
    event = insert_event(_event(detected_at, source_snapshot_id=latest.id), conn)

    latest_response = test_client.get("/api/intraday/snapshots/latest?symbols=360750")
    symbol_response = test_client.get(
        "/api/intraday/snapshots/360750",
        params={
            "start_time": captured_at.isoformat(),
            "end_time": (captured_at + timedelta(minutes=2)).isoformat(),
        },
    )
    event_response = test_client.get("/api/intraday/events/recent?event_type=SURGE&event_level=WARNING")
    ack_response = test_client.post(f"/api/intraday/events/{event.id}/acknowledge")
    acknowledged_events = test_client.get("/api/intraday/events/recent").json()["events"]

    assert latest_response.status_code == 200
    assert symbol_response.status_code == 200
    assert event_response.status_code == 200
    assert ack_response.status_code == 200

    latest_payload = latest_response.json()["snapshots"][0]
    symbol_payloads = symbol_response.json()["snapshots"]
    event_payload = event_response.json()["events"][0]

    assert latest_payload["id"] == latest.id
    assert latest_payload["captured_at"] == latest.captured_at.isoformat()
    assert latest_payload["price"] == 106.0
    assert [item["id"] for item in symbol_payloads] == [first.id, latest.id]
    assert symbol_payloads[0]["is_stale"] is True
    assert symbol_payloads[0]["quality_score"] == 0.72
    assert event_payload["detected_at"] == detected_at.isoformat()
    assert event_payload["source_snapshot_id"] == latest.id
    assert acknowledged_events[0]["acknowledged"] is True
    assert recent_events(db_session=conn)[0].acknowledged is True

    intraday_paths = {route.path for route in test_client.app.routes if "intraday" in route.path}
    assert all("order" not in path for path in intraday_paths)
    assert all("broker" not in path for path in intraday_paths)
    assert all("score" not in path for path in intraday_paths)
    assert _payload_has_no_execution_fields(latest_payload)
    assert _payload_has_no_execution_fields(event_payload)


def _conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _snapshot(
    captured_at: datetime,
    price: str,
    *,
    quality_score: float,
    is_stale: bool = False,
) -> IntradayPriceSnapshot:
    return IntradayPriceSnapshot(
        symbol="360750",
        market="KRX",
        captured_at=captured_at,
        price=Decimal(price),
        open_price=Decimal("99"),
        high_price=Decimal("107"),
        low_price=Decimal("98"),
        volume=Decimal("1000"),
        value_traded=Decimal("106000000"),
        change_rate=Decimal("6"),
        source="fixture",
        quality_score=quality_score,
        is_stale=is_stale,
        raw_payload={"fixture": "intraday-monitoring"},
    )


def _event(detected_at: datetime, *, source_snapshot_id: int | None) -> IntradayEvent:
    return IntradayEvent(
        symbol="360750",
        market="KRX",
        event_type="SURGE",
        event_level="WARNING",
        detected_at=detected_at,
        lookback_minutes=5,
        base_price=Decimal("100"),
        current_price=Decimal("106"),
        change_rate=Decimal("6"),
        volume_ratio=Decimal("2.5"),
        reason_code="INTRADAY_SURGE_PRICE_CHANGE",
        message="display-only surge monitoring event",
        source_snapshot_id=source_snapshot_id,
    )


def _payload_has_no_execution_fields(payload: dict) -> bool:
    blocked = {"order_id", "broker", "kis", "execution", "target_weight", "score"}
    return blocked.isdisjoint(payload)
