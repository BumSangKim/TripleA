import inspect
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from api.features.intraday.alert import acknowledge_intraday_event, process_intraday_events
from api.features.intraday.config import IntradayMonitoringConfig
from api.features.intraday.models import IntradayEvent
from api.features.intraday.repository import ensure_intraday_tables, recent_events
import api.features.intraday.alert as alert_module


def _conn(tmp_path):
    conn = sqlite3.connect(tmp_path / "intraday.db")
    conn.row_factory = sqlite3.Row
    return conn


def _event(level="WARNING", detected_at=None, event_type="DROP"):
    return IntradayEvent(
        symbol="005930",
        market="KRX",
        event_type=event_type,
        event_level=level,
        detected_at=detected_at or datetime(2026, 5, 27, 10, 31, tzinfo=UTC),
        lookback_minutes=5,
        base_price=Decimal("100"),
        current_price=Decimal("95.8"),
        change_rate=Decimal("-4.2"),
        volume_ratio=Decimal("3.1"),
        reason_code="INTRADAY_DROP_PRICE_CHANGE",
        message="005930 5m -4.2% drop detected",
    )


def test_event_is_persisted_and_alert_payload_generated(tmp_path):
    conn = _conn(tmp_path)

    result = process_intraday_events(conn, [_event()], IntradayMonitoringConfig())
    events = recent_events(db_session=conn)

    assert result.persisted_events == 1
    assert result.generated_alerts == 1
    assert events[0].event_type == "DROP"
    assert result.payloads[0].dedupe_key == "005930:DROP:WARNING:5"
    assert result.payloads[0].event_id == events[0].id


def test_duplicate_alert_is_suppressed_within_window(tmp_path):
    conn = _conn(tmp_path)
    config = IntradayMonitoringConfig(duplicate_suppression_minutes=10)
    now = datetime(2026, 5, 27, 10, 31, tzinfo=UTC)

    first = process_intraday_events(conn, [_event(detected_at=now)], config)
    second = process_intraday_events(conn, [_event(detected_at=now + timedelta(minutes=5))], config)

    assert first.generated_alerts == 1
    assert second.persisted_events == 1
    assert second.generated_alerts == 0
    assert second.suppressed_alerts == 1


def test_same_event_after_suppression_window_is_allowed(tmp_path):
    conn = _conn(tmp_path)
    config = IntradayMonitoringConfig(duplicate_suppression_minutes=10)
    now = datetime(2026, 5, 27, 10, 31, tzinfo=UTC)

    process_intraday_events(conn, [_event(detected_at=now)], config)
    second = process_intraday_events(conn, [_event(detected_at=now + timedelta(minutes=11))], config)

    assert second.generated_alerts == 1
    assert second.suppressed_alerts == 0


def test_event_level_escalation_bypasses_suppression(tmp_path):
    conn = _conn(tmp_path)
    config = IntradayMonitoringConfig(duplicate_suppression_minutes=10)
    now = datetime(2026, 5, 27, 10, 31, tzinfo=UTC)

    process_intraday_events(conn, [_event(level="WATCH", detected_at=now)], config)
    escalated = process_intraday_events(conn, [_event(level="CRITICAL", detected_at=now + timedelta(minutes=1))], config)

    assert escalated.generated_alerts == 1
    assert escalated.payloads[0].dedupe_key == "005930:DROP:CRITICAL:5"


def test_acknowledgement_updates_event_state(tmp_path):
    conn = _conn(tmp_path)
    result = process_intraday_events(conn, [_event()], IntradayMonitoringConfig())

    assert acknowledge_intraday_event(conn, result.payloads[0].event_id) is True
    assert recent_events(db_session=conn)[0].acknowledged is True


def test_alert_engine_handles_repository_failures_conservatively(tmp_path):
    conn = _conn(tmp_path)
    ensure_intraday_tables(conn)
    conn.execute(
        """
        CREATE TRIGGER fail_intraday_event_insert
        BEFORE INSERT ON intraday_event
        BEGIN
            SELECT RAISE(ABORT, 'forced event failure');
        END;
        """
    )

    result = process_intraday_events(conn, [_event()], IntradayMonitoringConfig())

    assert result.persisted_events == 0
    assert result.generated_alerts == 0
    assert result.warnings[0].reason_code == "INTRADAY_ALERT_REPOSITORY_ERROR"


def test_alert_engine_does_not_call_strategy_order_modules():
    source = inspect.getsource(alert_module)

    blocked = ["api.strategy", "allocation", "rebalancing", "order", "execution", "telegram"]
    assert all(token not in source for token in blocked)
