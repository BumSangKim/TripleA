from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from decimal import Decimal
from typing import Any

from api import db as api_db
from api.intraday.models import IntradayAlert, IntradayEvent, IntradayPriceSnapshot, ensure_aware


class IntradayRepositoryError(RuntimeError):
    pass


def ensure_intraday_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS intraday_price_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            market TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            price TEXT NOT NULL,
            open_price TEXT,
            high_price TEXT,
            low_price TEXT,
            volume TEXT,
            value_traded TEXT,
            change_rate TEXT,
            source TEXT NOT NULL,
            quality_score REAL NOT NULL,
            is_stale INTEGER NOT NULL DEFAULT 0,
            raw_payload TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(symbol, market, captured_at)
        );

        CREATE INDEX IF NOT EXISTS idx_intraday_snapshot_symbol_captured
        ON intraday_price_snapshot(symbol, captured_at);

        CREATE INDEX IF NOT EXISTS idx_intraday_snapshot_captured
        ON intraday_price_snapshot(captured_at);

        CREATE INDEX IF NOT EXISTS idx_intraday_snapshot_market_captured
        ON intraday_price_snapshot(market, captured_at);

        CREATE TABLE IF NOT EXISTS intraday_event (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            market TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_level TEXT NOT NULL,
            detected_at TEXT NOT NULL,
            lookback_minutes INTEGER NOT NULL,
            base_price TEXT,
            current_price TEXT NOT NULL,
            change_rate TEXT,
            volume_ratio TEXT,
            reason_code TEXT NOT NULL,
            message TEXT NOT NULL,
            source_snapshot_id INTEGER,
            acknowledged INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_intraday_event_symbol_detected
        ON intraday_event(symbol, detected_at);

        CREATE INDEX IF NOT EXISTS idx_intraday_event_type_detected
        ON intraday_event(event_type, detected_at);

        CREATE INDEX IF NOT EXISTS idx_intraday_event_level_detected
        ON intraday_event(event_level, detected_at);

        CREATE INDEX IF NOT EXISTS idx_intraday_event_ack_detected
        ON intraday_event(acknowledged, detected_at);

        CREATE TABLE IF NOT EXISTS intraday_alert (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL REFERENCES intraday_event(id),
            symbol TEXT NOT NULL,
            alert_level TEXT NOT NULL,
            channel TEXT NOT NULL,
            dedupe_key TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_intraday_alert_dedupe_sent
        ON intraday_alert(dedupe_key, sent_at);

        CREATE INDEX IF NOT EXISTS idx_intraday_alert_symbol_sent
        ON intraday_alert(symbol, sent_at);
        """
    )
    conn.commit()


def insert_snapshot(
    snapshot: IntradayPriceSnapshot,
    db_session: sqlite3.Connection | None = None,
) -> IntradayPriceSnapshot:
    return _with_conn(db_session, lambda conn: _insert_snapshot(conn, snapshot))


def bulk_insert_snapshots(
    snapshots: list[IntradayPriceSnapshot],
    db_session: sqlite3.Connection | None = None,
) -> int:
    return _with_conn(db_session, lambda conn: sum(1 for snapshot in snapshots if _insert_snapshot(conn, snapshot)))


def latest_snapshot(
    *,
    symbol: str,
    market: str,
    db_session: sqlite3.Connection | None = None,
) -> IntradayPriceSnapshot | None:
    return _with_conn(db_session, lambda conn: _latest_snapshot(conn, symbol=symbol, market=market))


def latest_snapshots(
    *,
    market: str | None = None,
    symbols: list[str] | None = None,
    limit: int = 100,
    db_session: sqlite3.Connection | None = None,
) -> list[IntradayPriceSnapshot]:
    return _with_conn(
        db_session,
        lambda conn: _latest_snapshots(conn, market=market, symbols=symbols, limit=limit),
    )


def snapshots_for_symbol(
    *,
    symbol: str,
    market: str,
    start_at: datetime,
    end_at: datetime,
    db_session: sqlite3.Connection | None = None,
) -> list[IntradayPriceSnapshot]:
    return _with_conn(
        db_session,
        lambda conn: _snapshots_for_symbol(conn, symbol=symbol, market=market, start_at=start_at, end_at=end_at),
    )


def lookback_base_snapshot(
    *,
    symbol: str,
    market: str,
    target_at: datetime,
    db_session: sqlite3.Connection | None = None,
) -> IntradayPriceSnapshot | None:
    return _with_conn(
        db_session,
        lambda conn: _lookback_base_snapshot(conn, symbol=symbol, market=market, target_at=target_at),
    )


def insert_event(event: IntradayEvent, db_session: sqlite3.Connection | None = None) -> IntradayEvent:
    return _with_conn(db_session, lambda conn: _insert_event(conn, event))


def recent_events(
    *,
    limit: int = 100,
    symbol: str | None = None,
    event_type: str | None = None,
    event_level: str | None = None,
    acknowledged: bool | None = None,
    db_session: sqlite3.Connection | None = None,
) -> list[IntradayEvent]:
    return _with_conn(
        db_session,
        lambda conn: _recent_events(
            conn,
            limit=limit,
            symbol=symbol,
            event_type=event_type,
            event_level=event_level,
            acknowledged=acknowledged,
        ),
    )


def find_duplicate_alert(
    *,
    dedupe_key: str,
    since: datetime,
    db_session: sqlite3.Connection | None = None,
) -> IntradayAlert | None:
    return _with_conn(db_session, lambda conn: _find_duplicate_alert(conn, dedupe_key=dedupe_key, since=since))


def insert_alert(alert: IntradayAlert, db_session: sqlite3.Connection | None = None) -> IntradayAlert:
    return _with_conn(db_session, lambda conn: _insert_alert(conn, alert))


def mark_event_acknowledged(event_id: int, db_session: sqlite3.Connection | None = None) -> bool:
    return _with_conn(db_session, lambda conn: _mark_event_acknowledged(conn, event_id))


def _with_conn(db_session: sqlite3.Connection | None, fn):
    if db_session is None:
        with api_db.get_conn() as conn:
            ensure_intraday_tables(conn)
            return fn(conn)
    ensure_intraday_tables(db_session)
    return fn(db_session)


def _insert_snapshot(conn: sqlite3.Connection, snapshot: IntradayPriceSnapshot) -> IntradayPriceSnapshot:
    _validate_snapshot(snapshot)
    captured_at = ensure_aware(snapshot.captured_at).isoformat()
    try:
        conn.execute(
            """
            INSERT INTO intraday_price_snapshot (
                symbol, market, captured_at, price, open_price, high_price, low_price,
                volume, value_traded, change_rate, source, quality_score, is_stale, raw_payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, market, captured_at) DO UPDATE SET
                price=excluded.price,
                open_price=excluded.open_price,
                high_price=excluded.high_price,
                low_price=excluded.low_price,
                volume=excluded.volume,
                value_traded=excluded.value_traded,
                change_rate=excluded.change_rate,
                source=excluded.source,
                quality_score=excluded.quality_score,
                is_stale=excluded.is_stale,
                raw_payload=excluded.raw_payload
            """,
            (
                snapshot.symbol,
                snapshot.market,
                captured_at,
                _decimal_text(snapshot.price),
                _decimal_text(snapshot.open_price),
                _decimal_text(snapshot.high_price),
                _decimal_text(snapshot.low_price),
                _decimal_text(snapshot.volume),
                _decimal_text(snapshot.value_traded),
                _decimal_text(snapshot.change_rate),
                snapshot.source,
                float(snapshot.quality_score),
                1 if snapshot.is_stale else 0,
                json.dumps(snapshot.raw_payload, ensure_ascii=False, sort_keys=True) if snapshot.raw_payload is not None else None,
            ),
        )
        conn.commit()
    except sqlite3.DatabaseError as exc:
        conn.rollback()
        raise IntradayRepositoryError("failed to insert intraday snapshot") from exc
    row = conn.execute(
        "SELECT * FROM intraday_price_snapshot WHERE symbol=? AND market=? AND captured_at=?",
        (snapshot.symbol, snapshot.market, captured_at),
    ).fetchone()
    return _snapshot_from_row(row)


def _latest_snapshot(conn: sqlite3.Connection, *, symbol: str, market: str) -> IntradayPriceSnapshot | None:
    row = conn.execute(
        """
        SELECT *
        FROM intraday_price_snapshot
        WHERE symbol=? AND market=?
        ORDER BY captured_at DESC, id DESC
        LIMIT 1
        """,
        (symbol, market),
    ).fetchone()
    return _snapshot_from_row(row) if row else None


def _latest_snapshots(
    conn: sqlite3.Connection,
    *,
    market: str | None,
    symbols: list[str] | None,
    limit: int,
) -> list[IntradayPriceSnapshot]:
    where = []
    params: list[Any] = []
    if market:
        where.append("s.market=?")
        params.append(market)
    if symbols:
        placeholders = ",".join("?" for _ in symbols)
        where.append(f"s.symbol IN ({placeholders})")
        params.extend(symbols)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    rows = conn.execute(
        f"""
        SELECT s.*
        FROM intraday_price_snapshot s
        JOIN (
            SELECT symbol, market, MAX(captured_at) AS captured_at
            FROM intraday_price_snapshot
            GROUP BY symbol, market
        ) latest
          ON s.symbol=latest.symbol
         AND s.market=latest.market
         AND s.captured_at=latest.captured_at
        {where_sql}
        ORDER BY s.captured_at DESC, s.symbol ASC
        LIMIT ?
        """,
        (*params, int(limit)),
    ).fetchall()
    return [_snapshot_from_row(row) for row in rows]


def _snapshots_for_symbol(
    conn: sqlite3.Connection,
    *,
    symbol: str,
    market: str,
    start_at: datetime,
    end_at: datetime,
) -> list[IntradayPriceSnapshot]:
    rows = conn.execute(
        """
        SELECT *
        FROM intraday_price_snapshot
        WHERE symbol=? AND market=? AND captured_at BETWEEN ? AND ?
        ORDER BY captured_at ASC, id ASC
        """,
        (symbol, market, ensure_aware(start_at).isoformat(), ensure_aware(end_at).isoformat()),
    ).fetchall()
    return [_snapshot_from_row(row) for row in rows]


def _lookback_base_snapshot(
    conn: sqlite3.Connection,
    *,
    symbol: str,
    market: str,
    target_at: datetime,
) -> IntradayPriceSnapshot | None:
    row = conn.execute(
        """
        SELECT *
        FROM intraday_price_snapshot
        WHERE symbol=? AND market=? AND captured_at<=?
        ORDER BY captured_at DESC, id DESC
        LIMIT 1
        """,
        (symbol, market, ensure_aware(target_at).isoformat()),
    ).fetchone()
    return _snapshot_from_row(row) if row else None


def _insert_event(conn: sqlite3.Connection, event: IntradayEvent) -> IntradayEvent:
    try:
        cursor = conn.execute(
            """
            INSERT INTO intraday_event (
                symbol, market, event_type, event_level, detected_at, lookback_minutes,
                base_price, current_price, change_rate, volume_ratio, reason_code,
                message, source_snapshot_id, acknowledged
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.symbol,
                event.market,
                event.event_type,
                event.event_level,
                ensure_aware(event.detected_at).isoformat(),
                int(event.lookback_minutes),
                _decimal_text(event.base_price),
                _decimal_text(event.current_price),
                _decimal_text(event.change_rate),
                _decimal_text(event.volume_ratio),
                event.reason_code,
                event.message,
                event.source_snapshot_id,
                1 if event.acknowledged else 0,
            ),
        )
        conn.commit()
    except sqlite3.DatabaseError as exc:
        conn.rollback()
        raise IntradayRepositoryError("failed to insert intraday event") from exc
    row = conn.execute("SELECT * FROM intraday_event WHERE id=?", (cursor.lastrowid,)).fetchone()
    return _event_from_row(row)


def _recent_events(
    conn: sqlite3.Connection,
    *,
    limit: int,
    symbol: str | None,
    event_type: str | None,
    event_level: str | None,
    acknowledged: bool | None,
) -> list[IntradayEvent]:
    where = []
    params: list[Any] = []
    if symbol:
        where.append("symbol=?")
        params.append(symbol)
    if event_type:
        where.append("event_type=?")
        params.append(event_type)
    if event_level:
        where.append("event_level=?")
        params.append(event_level)
    if acknowledged is not None:
        where.append("acknowledged=?")
        params.append(1 if acknowledged else 0)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    rows = conn.execute(
        f"""
        SELECT *
        FROM intraday_event
        {where_sql}
        ORDER BY detected_at DESC, id DESC
        LIMIT ?
        """,
        (*params, int(limit)),
    ).fetchall()
    return [_event_from_row(row) for row in rows]


def _find_duplicate_alert(conn: sqlite3.Connection, *, dedupe_key: str, since: datetime) -> IntradayAlert | None:
    row = conn.execute(
        """
        SELECT *
        FROM intraday_alert
        WHERE dedupe_key=? AND sent_at>=?
        ORDER BY sent_at DESC, id DESC
        LIMIT 1
        """,
        (dedupe_key, ensure_aware(since).isoformat()),
    ).fetchone()
    return _alert_from_row(row) if row else None


def _insert_alert(conn: sqlite3.Connection, alert: IntradayAlert) -> IntradayAlert:
    try:
        cursor = conn.execute(
            """
            INSERT INTO intraday_alert (
                event_id, symbol, alert_level, channel, dedupe_key, sent_at, status, message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert.event_id,
                alert.symbol,
                alert.alert_level,
                alert.channel,
                alert.dedupe_key,
                ensure_aware(alert.sent_at).isoformat(),
                alert.status,
                alert.message,
            ),
        )
        conn.commit()
    except sqlite3.DatabaseError as exc:
        conn.rollback()
        raise IntradayRepositoryError("failed to insert intraday alert") from exc
    row = conn.execute("SELECT * FROM intraday_alert WHERE id=?", (cursor.lastrowid,)).fetchone()
    return _alert_from_row(row)


def _mark_event_acknowledged(conn: sqlite3.Connection, event_id: int) -> bool:
    try:
        cursor = conn.execute(
            "UPDATE intraday_event SET acknowledged=1 WHERE id=?",
            (int(event_id),),
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.DatabaseError as exc:
        conn.rollback()
        raise IntradayRepositoryError("failed to acknowledge intraday event") from exc


def _validate_snapshot(snapshot: IntradayPriceSnapshot) -> None:
    if Decimal(str(snapshot.price)) <= 0:
        raise IntradayRepositoryError("snapshot price must be positive")
    if not snapshot.symbol.strip() or not snapshot.market.strip():
        raise IntradayRepositoryError("snapshot symbol and market are required")
    if not 0 <= float(snapshot.quality_score) <= 1:
        raise IntradayRepositoryError("snapshot quality_score must be between 0 and 1")


def _snapshot_from_row(row: sqlite3.Row | tuple[Any, ...]) -> IntradayPriceSnapshot:
    data = _row_to_dict(row, _SNAPSHOT_COLUMNS)
    raw_payload = data.get("raw_payload")
    return IntradayPriceSnapshot(
        id=int(data["id"]),
        symbol=data["symbol"],
        market=data["market"],
        captured_at=datetime.fromisoformat(data["captured_at"]),
        price=Decimal(str(data["price"])),
        open_price=_optional_decimal(data.get("open_price")),
        high_price=_optional_decimal(data.get("high_price")),
        low_price=_optional_decimal(data.get("low_price")),
        volume=_optional_decimal(data.get("volume")),
        value_traded=_optional_decimal(data.get("value_traded")),
        change_rate=_optional_decimal(data.get("change_rate")),
        source=data["source"],
        quality_score=float(data["quality_score"]),
        is_stale=bool(data["is_stale"]),
        raw_payload=json.loads(raw_payload) if raw_payload else None,
        created_at=data["created_at"],
    )


def _event_from_row(row: sqlite3.Row | tuple[Any, ...]) -> IntradayEvent:
    data = _row_to_dict(row, _EVENT_COLUMNS)
    return IntradayEvent(
        id=int(data["id"]),
        symbol=data["symbol"],
        market=data["market"],
        event_type=data["event_type"],
        event_level=data["event_level"],
        detected_at=datetime.fromisoformat(data["detected_at"]),
        lookback_minutes=int(data["lookback_minutes"]),
        base_price=_optional_decimal(data.get("base_price")),
        current_price=Decimal(str(data["current_price"])),
        change_rate=_optional_decimal(data.get("change_rate")),
        volume_ratio=_optional_decimal(data.get("volume_ratio")),
        reason_code=data["reason_code"],
        message=data["message"],
        source_snapshot_id=data.get("source_snapshot_id"),
        acknowledged=bool(data["acknowledged"]),
        created_at=data["created_at"],
    )


def _alert_from_row(row: sqlite3.Row | tuple[Any, ...]) -> IntradayAlert:
    data = _row_to_dict(row, _ALERT_COLUMNS)
    return IntradayAlert(
        id=int(data["id"]),
        event_id=int(data["event_id"]),
        symbol=data["symbol"],
        alert_level=data["alert_level"],
        channel=data["channel"],
        dedupe_key=data["dedupe_key"],
        sent_at=datetime.fromisoformat(data["sent_at"]),
        status=data["status"],
        message=data["message"],
        created_at=data["created_at"],
    )


def _row_to_dict(row: sqlite3.Row | tuple[Any, ...], columns: list[str]) -> dict[str, Any]:
    if isinstance(row, sqlite3.Row):
        return dict(row)
    return dict(zip(columns, row, strict=True))


def _decimal_text(value: Decimal | int | float | str | None) -> str | None:
    if value is None:
        return None
    return str(Decimal(str(value)))


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


_SNAPSHOT_COLUMNS = [
    "id",
    "symbol",
    "market",
    "captured_at",
    "price",
    "open_price",
    "high_price",
    "low_price",
    "volume",
    "value_traded",
    "change_rate",
    "source",
    "quality_score",
    "is_stale",
    "raw_payload",
    "created_at",
]

_EVENT_COLUMNS = [
    "id",
    "symbol",
    "market",
    "event_type",
    "event_level",
    "detected_at",
    "lookback_minutes",
    "base_price",
    "current_price",
    "change_rate",
    "volume_ratio",
    "reason_code",
    "message",
    "source_snapshot_id",
    "acknowledged",
    "created_at",
]

_ALERT_COLUMNS = [
    "id",
    "event_id",
    "symbol",
    "alert_level",
    "channel",
    "dedupe_key",
    "sent_at",
    "status",
    "message",
    "created_at",
]
