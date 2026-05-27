import inspect
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from api.intraday.config import IntradayMonitoringConfig
from api.intraday.detector import detect_events_for_snapshot
from api.intraday.models import IntradayPriceSnapshot
from api.intraday.repository import ensure_intraday_tables, insert_snapshot
import api.intraday.detector as detector_module


def _conn(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(tmp_path / "intraday.db")
    conn.row_factory = sqlite3.Row
    return conn


def _snapshot(captured_at, price, *, volume="1000", quality_score=1.0, is_stale=False):
    return IntradayPriceSnapshot(
        symbol="360750",
        market="KRX",
        captured_at=captured_at,
        price=Decimal(str(price)),
        volume=Decimal(str(volume)) if volume is not None else None,
        source="mock",
        quality_score=quality_score,
        is_stale=is_stale,
    )


def _config(windows=(5,)):
    return IntradayMonitoringConfig(lookback_windows_minutes=tuple(windows))


def test_no_event_when_no_threshold_crossed(tmp_path):
    conn = _conn(tmp_path)
    now = datetime(2026, 5, 27, 9, 5, tzinfo=UTC)
    insert_snapshot(_snapshot(now - timedelta(minutes=5), "100"), conn)
    current = insert_snapshot(_snapshot(now, "101"), conn)

    result = detect_events_for_snapshot(conn, current, _config())

    assert result.events == []
    assert result.warnings == []


def test_surge_event_for_positive_price_move(tmp_path):
    conn = _conn(tmp_path)
    now = datetime(2026, 5, 27, 9, 5, tzinfo=UTC)
    insert_snapshot(_snapshot(now - timedelta(minutes=5), "100"), conn)
    current = insert_snapshot(_snapshot(now, "104"), conn)

    result = detect_events_for_snapshot(conn, current, _config())

    assert [(event.event_type, event.event_level) for event in result.events] == [("SURGE", "WARNING")]
    assert result.events[0].reason_code == "INTRADAY_SURGE_PRICE_CHANGE"


def test_drop_event_for_negative_price_move(tmp_path):
    conn = _conn(tmp_path)
    now = datetime(2026, 5, 27, 9, 5, tzinfo=UTC)
    insert_snapshot(_snapshot(now - timedelta(minutes=5), "100"), conn)
    current = insert_snapshot(_snapshot(now, "96"), conn)

    result = detect_events_for_snapshot(conn, current, _config())

    assert [(event.event_type, event.event_level) for event in result.events] == [("DROP", "WARNING")]
    assert result.events[0].reason_code == "INTRADAY_DROP_PRICE_CHANGE"


def test_watch_warning_critical_level_assignment(tmp_path):
    conn = _conn(tmp_path)
    start = datetime(2026, 5, 27, 9, 0, tzinfo=UTC)
    insert_snapshot(_snapshot(start, "100"), conn)

    levels = []
    for offset, price in enumerate(["102", "104", "107"], start=1):
        current = insert_snapshot(_snapshot(start + timedelta(minutes=offset), price), conn)
        levels.append(detect_events_for_snapshot(conn, current, _config(windows=(offset,))).events[0].event_level)

    assert levels == ["WATCH", "WARNING", "CRITICAL"]


def test_multiple_lookback_windows(tmp_path):
    conn = _conn(tmp_path)
    now = datetime(2026, 5, 27, 9, 10, tzinfo=UTC)
    insert_snapshot(_snapshot(now - timedelta(minutes=1), "103"), conn)
    insert_snapshot(_snapshot(now - timedelta(minutes=5), "100"), conn)
    current = insert_snapshot(_snapshot(now, "105"), conn)

    result = detect_events_for_snapshot(conn, current, _config(windows=(1, 5)))

    assert [event.lookback_minutes for event in result.events] == [5]


def test_volume_spike_event(tmp_path):
    conn = _conn(tmp_path)
    now = datetime(2026, 5, 27, 9, 5, tzinfo=UTC)
    insert_snapshot(_snapshot(now - timedelta(minutes=5), "100", volume="100"), conn)
    current = insert_snapshot(_snapshot(now, "101", volume="500"), conn)

    result = detect_events_for_snapshot(conn, current, _config())

    assert [(event.event_type, event.event_level) for event in result.events] == [("VOLUME_SPIKE", "WARNING")]
    assert result.events[0].reason_code == "INTRADAY_VOLUME_SPIKE"


def test_surge_and_drop_with_volume_combined_events(tmp_path):
    conn = _conn(tmp_path)
    now = datetime(2026, 5, 27, 9, 5, tzinfo=UTC)
    insert_snapshot(_snapshot(now - timedelta(minutes=5), "100", volume="100"), conn)
    surge = insert_snapshot(_snapshot(now, "104", volume="500"), conn)

    surge_events = detect_events_for_snapshot(conn, surge, _config()).events

    assert {event.event_type for event in surge_events} == {"SURGE", "VOLUME_SPIKE", "SURGE_WITH_VOLUME"}
    assert any(event.reason_code == "INTRADAY_SURGE_WITH_VOLUME" for event in surge_events)

    conn = _conn(tmp_path / "drop")
    insert_snapshot(_snapshot(now - timedelta(minutes=5), "100", volume="100"), conn)
    drop = insert_snapshot(_snapshot(now, "96", volume="500"), conn)

    drop_events = detect_events_for_snapshot(conn, drop, _config()).events

    assert {event.event_type for event in drop_events} == {"DROP", "VOLUME_SPIKE", "DROP_WITH_VOLUME"}
    assert any(event.reason_code == "INTRADAY_DROP_WITH_VOLUME" for event in drop_events)


def test_missing_lookback_data_returns_warning_without_event(tmp_path):
    conn = _conn(tmp_path)
    current = insert_snapshot(_snapshot(datetime(2026, 5, 27, 9, 5, tzinfo=UTC), "104"), conn)

    result = detect_events_for_snapshot(conn, current, _config())

    assert result.events == []
    assert result.warnings[0].reason_code == "INTRADAY_INSUFFICIENT_LOOKBACK_DATA"


def test_invalid_base_price_is_rejected_without_event(tmp_path):
    conn = _conn(tmp_path)
    now = datetime(2026, 5, 27, 9, 5, tzinfo=UTC)
    ensure_intraday_tables(conn)
    conn.execute(
        """
        INSERT INTO intraday_price_snapshot
        (symbol, market, captured_at, price, source, quality_score, is_stale)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("360750", "KRX", (now - timedelta(minutes=5)).isoformat(), "0", "mock", 1.0, 0),
    )
    conn.commit()
    current = insert_snapshot(_snapshot(now, "104"), conn)

    result = detect_events_for_snapshot(conn, current, _config())

    assert result.events == []
    assert result.warnings[0].reason_code == "INTRADAY_INVALID_BASE_PRICE"


def test_low_quality_current_snapshot_does_not_produce_normal_event(tmp_path):
    conn = _conn(tmp_path)
    now = datetime(2026, 5, 27, 9, 5, tzinfo=UTC)
    insert_snapshot(_snapshot(now - timedelta(minutes=5), "100"), conn)
    current = insert_snapshot(_snapshot(now, "110", quality_score=0.5, is_stale=True), conn)

    result = detect_events_for_snapshot(conn, current, _config())

    assert result.events == []
    assert result.warnings[0].reason_code == "INTRADAY_LOW_DATA_QUALITY"


def test_detector_does_not_import_strategy_order_or_allocation_modules():
    source = inspect.getsource(detector_module)

    blocked = ["api.strategy", "allocation", "rebalancing", "order", "execution"]
    assert all(token not in source for token in blocked)
