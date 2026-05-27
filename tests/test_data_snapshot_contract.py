import sqlite3
from datetime import UTC, date, datetime
from decimal import Decimal

from api.data.models import MacroObservation, PriceBar
from api.data.repository import upsert_macro_rows, upsert_price_rows
from api.data.snapshot import build_data_snapshot


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_snapshot_excludes_prices_after_decision_date():
    conn = _conn()
    now = datetime(2026, 5, 27, tzinfo=UTC)
    rows = [
        PriceBar("360750", "KRX", date(2026, 5, 26), Decimal("100"), Decimal("100"), Decimal("100"), Decimal("100"), Decimal("1"), "mock", date(2026, 5, 26), now),
        PriceBar("360750", "KRX", date(2026, 5, 28), Decimal("101"), Decimal("101"), Decimal("101"), Decimal("101"), Decimal("1"), "mock", date(2026, 5, 28), now),
    ]
    upsert_price_rows(rows, db_session=conn)

    snapshot = build_data_snapshot(
        conn=conn,
        as_of_date=date(2026, 5, 27),
        dataset_types=["market_price_daily"],
        symbols=["360750"],
    )

    assert len(snapshot.included_datasets["market_price_daily"]) == 1
    assert snapshot.max_data_date["market_price_daily"] == "2026-05-26"


def test_snapshot_excludes_macro_released_after_decision_date():
    conn = _conn()
    now = datetime(2026, 5, 27, tzinfo=UTC)
    rows = [
        MacroObservation("CPI", date(2026, 4, 30), Decimal("3.1"), "%", "mock", date(2026, 5, 27), date(2026, 5, 20), now),
        MacroObservation("CPI", date(2026, 5, 31), Decimal("3.2"), "%", "mock", date(2026, 6, 10), date(2026, 6, 10), now),
    ]
    upsert_macro_rows(rows, db_session=conn)

    snapshot = build_data_snapshot(
        conn=conn,
        as_of_date=date(2026, 5, 27),
        dataset_types=["macro_indicator"],
        indicator_keys=["CPI"],
    )

    assert len(snapshot.included_datasets["macro_indicator"]) == 1
    assert snapshot.max_data_date["macro_indicator"] == "2026-04-30"


def test_snapshot_id_is_stable_for_same_inputs_and_warns_on_empty_dataset():
    conn = _conn()

    first = build_data_snapshot(conn=conn, as_of_date=date(2026, 5, 27), dataset_types=["market_price_daily"], symbols=["360750"])
    second = build_data_snapshot(conn=conn, as_of_date=date(2026, 5, 27), dataset_types=["market_price_daily"], symbols=["360750"])

    assert first.snapshot_id == second.snapshot_id
    assert "market_price_daily_empty" in first.warnings
