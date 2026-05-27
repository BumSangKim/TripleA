import sqlite3
from datetime import date

from api.testbed.snapshot_service import create_data_snapshot, compute_data_quality, get_data_snapshot


def test_snapshot_service_create_and_retrieve_and_quality_bounds():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    snapshot = create_data_snapshot(conn, date(2026, 5, 27), ["market_prices"])
    loaded = get_data_snapshot(conn, snapshot["snapshot_id"])
    quality = compute_data_quality(conn, "asset", "SPY", date(2026, 5, 27))
    assert loaded["snapshot_id"] == snapshot["snapshot_id"]
    assert 0.0 <= quality["quality_score"] <= 1.0
    assert quality["is_stale"] is True
