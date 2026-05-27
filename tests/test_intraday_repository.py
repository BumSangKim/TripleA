import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from api.intraday.models import IntradayAlert, IntradayEvent, IntradayPriceSnapshot
from api.intraday.repository import (
    IntradayRepositoryError,
    bulk_insert_snapshots,
    ensure_intraday_tables,
    find_duplicate_alert,
    insert_alert,
    insert_event,
    insert_snapshot,
    latest_snapshot,
    lookback_base_snapshot,
    mark_event_acknowledged,
    recent_events,
    snapshots_for_symbol,
)


def _conn(tmp_path):
    conn = sqlite3.connect(tmp_path / "intraday.db")
    conn.row_factory = sqlite3.Row
    return conn


def _snapshot(captured_at: datetime, price: str = "100") -> IntradayPriceSnapshot:
    return IntradayPriceSnapshot(
        symbol="360750",
        market="KRX",
        captured_at=captured_at,
        price=Decimal(price),
        open_price=Decimal("99"),
        high_price=Decimal("101"),
        low_price=Decimal("98"),
        volume=Decimal("1000"),
        value_traded=Decimal("100000"),
        change_rate=Decimal("1.0"),
        source="mock",
        quality_score=0.95,
        raw_payload={"p": price},
    )


def _event(detected_at: datetime) -> IntradayEvent:
    return IntradayEvent(
        symbol="360750",
        market="KRX",
        event_type="SURGE",
        event_level="WARNING",
        detected_at=detected_at,
        lookback_minutes=5,
        base_price=Decimal("100"),
        current_price=Decimal("105"),
        change_rate=Decimal("5"),
        volume_ratio=Decimal("2.5"),
        reason_code="PRICE_SURGE",
        message="360750 surged 5%",
        source_snapshot_id=1,
    )


def test_intraday_tables_can_be_created(tmp_path):
    conn = _conn(tmp_path)

    ensure_intraday_tables(conn)

    tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"intraday_price_snapshot", "intraday_event", "intraday_alert"}.issubset(tables)


def test_snapshot_insert_and_latest_read(tmp_path):
    conn = _conn(tmp_path)
    now = datetime(2026, 5, 27, 9, 1, tzinfo=UTC)

    saved = insert_snapshot(_snapshot(now), conn)
    latest = latest_snapshot(symbol="360750", market="KRX", db_session=conn)

    assert saved.id is not None
    assert latest is not None
    assert latest.price == Decimal("100")
    assert latest.raw_payload == {"p": "100"}


def test_duplicate_snapshot_upserts_deterministically(tmp_path):
    conn = _conn(tmp_path)
    now = datetime(2026, 5, 27, 9, 1, tzinfo=UTC)

    first = insert_snapshot(_snapshot(now, "100"), conn)
    second = insert_snapshot(_snapshot(now, "101"), conn)
    rows = conn.execute("SELECT * FROM intraday_price_snapshot").fetchall()

    assert len(rows) == 1
    assert second.id == first.id
    assert latest_snapshot(symbol="360750", market="KRX", db_session=conn).price == Decimal("101")


def test_bulk_snapshot_insert_and_time_range_query(tmp_path):
    conn = _conn(tmp_path)
    start = datetime(2026, 5, 27, 9, 0, tzinfo=UTC)
    snapshots = [_snapshot(start + timedelta(minutes=i), str(100 + i)) for i in range(3)]

    inserted = bulk_insert_snapshots(snapshots, conn)
    in_range = snapshots_for_symbol(
        symbol="360750",
        market="KRX",
        start_at=start + timedelta(minutes=1),
        end_at=start + timedelta(minutes=2),
        db_session=conn,
    )

    assert inserted == 3
    assert [item.price for item in in_range] == [Decimal("101"), Decimal("102")]


def test_lookback_base_snapshot_returns_latest_at_or_before_target(tmp_path):
    conn = _conn(tmp_path)
    start = datetime(2026, 5, 27, 9, 0, tzinfo=UTC)
    bulk_insert_snapshots([_snapshot(start, "100"), _snapshot(start + timedelta(minutes=5), "105")], conn)

    base = lookback_base_snapshot(
        symbol="360750",
        market="KRX",
        target_at=start + timedelta(minutes=4),
        db_session=conn,
    )

    assert base is not None
    assert base.price == Decimal("100")


def test_event_insert_recent_read_and_acknowledgement(tmp_path):
    conn = _conn(tmp_path)
    now = datetime(2026, 5, 27, 9, 5, tzinfo=UTC)

    saved = insert_event(_event(now), conn)
    assert saved.id is not None
    assert recent_events(db_session=conn)[0].event_type == "SURGE"

    assert mark_event_acknowledged(saved.id, conn) is True
    assert recent_events(db_session=conn)[0].acknowledged is True


def test_alert_insert_and_duplicate_lookup(tmp_path):
    conn = _conn(tmp_path)
    now = datetime(2026, 5, 27, 9, 5, tzinfo=UTC)
    event = insert_event(_event(now), conn)
    alert = IntradayAlert(
        event_id=event.id,
        symbol="360750",
        alert_level="WARNING",
        channel="internal",
        dedupe_key="360750:SURGE:WARNING:5",
        sent_at=now,
        status="SENT",
        message="360750 surge warning",
    )

    saved = insert_alert(alert, conn)
    duplicate = find_duplicate_alert(
        dedupe_key="360750:SURGE:WARNING:5",
        since=now - timedelta(minutes=10),
        db_session=conn,
    )

    assert saved.id is not None
    assert duplicate is not None
    assert duplicate.dedupe_key == "360750:SURGE:WARNING:5"


def test_invalid_snapshot_validation_rejects_non_positive_price(tmp_path):
    conn = _conn(tmp_path)

    with pytest.raises(IntradayRepositoryError, match="positive"):
        insert_snapshot(_snapshot(datetime(2026, 5, 27, 9, 1, tzinfo=UTC), "0"), conn)

    assert conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='intraday_price_snapshot'").fetchone()
    assert conn.execute("SELECT COUNT(*) AS c FROM intraday_price_snapshot").fetchone()["c"] == 0


def test_insert_failure_rolls_back_and_surfaces_error(tmp_path):
    conn = _conn(tmp_path)
    ensure_intraday_tables(conn)
    conn.execute(
        """
        CREATE TRIGGER fail_intraday_snapshot_insert
        BEFORE INSERT ON intraday_price_snapshot
        BEGIN
            SELECT RAISE(ABORT, 'forced failure');
        END;
        """
    )
    broken = _snapshot(datetime(2026, 5, 27, 9, 1, tzinfo=UTC), "100")

    with pytest.raises(IntradayRepositoryError, match="failed to insert"):
        insert_snapshot(broken, conn)

    assert conn.execute("SELECT COUNT(*) AS c FROM intraday_price_snapshot").fetchone()["c"] == 0
