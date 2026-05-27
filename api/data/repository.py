from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from api import db as api_db
from api.data.models import CurrentQuote, DataQualityCheck, IngestionRun, MacroObservation, PriceBar, decimal_from


def ensure_raw_data_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS raw_market_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            market TEXT NOT NULL,
            date TEXT NOT NULL,
            open TEXT,
            high TEXT,
            low TEXT,
            close TEXT NOT NULL,
            volume TEXT,
            source TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(symbol, market, date, source, as_of_date)
        );

        CREATE TABLE IF NOT EXISTS raw_current_quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            market TEXT NOT NULL,
            price TEXT NOT NULL,
            currency TEXT NOT NULL,
            quote_time TEXT,
            source TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(symbol, market, source, as_of_date)
        );

        CREATE TABLE IF NOT EXISTS raw_macro_indicators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            indicator_key TEXT NOT NULL,
            date TEXT NOT NULL,
            value TEXT NOT NULL,
            unit TEXT,
            source TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            release_date TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE(indicator_key, date, source, as_of_date)
        );

        CREATE TABLE IF NOT EXISTS data_quality_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_key TEXT NOT NULL,
            source TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            quality_score REAL NOT NULL,
            missing_ratio REAL NOT NULL,
            is_stale INTEGER NOT NULL,
            warnings_json TEXT,
            fallback_policy TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(dataset_key, source, as_of_date)
        );

        CREATE TABLE IF NOT EXISTS data_ingestion_runs (
            run_id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            row_count INTEGER NOT NULL DEFAULT 0,
            error_message TEXT
        );
        """
    )
    conn.commit()


def upsert_price_rows(rows: list[PriceBar], db_session: sqlite3.Connection | None = None) -> int:
    return _with_conn(db_session, lambda conn: _upsert_price_rows(conn, rows))


def upsert_current_quote(quote: CurrentQuote, db_session: sqlite3.Connection | None = None) -> int:
    return _with_conn(db_session, lambda conn: _upsert_current_quote(conn, quote))


def upsert_macro_rows(rows: list[MacroObservation], db_session: sqlite3.Connection | None = None) -> int:
    return _with_conn(db_session, lambda conn: _upsert_macro_rows(conn, rows))


def upsert_quality_check(check: DataQualityCheck, db_session: sqlite3.Connection | None = None) -> int:
    return _with_conn(db_session, lambda conn: _upsert_quality_check(conn, check))


def record_ingestion_run(run: IngestionRun, db_session: sqlite3.Connection | None = None) -> None:
    _with_conn(db_session, lambda conn: _record_ingestion_run(conn, run))


def read_historical_prices(
    *,
    symbol: str,
    market: str,
    start_date: str,
    end_date: str,
    db_session: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    return _with_conn(
        db_session,
        lambda conn: _read_historical_prices(conn, symbol=symbol, market=market, start_date=start_date, end_date=end_date),
    )


def read_latest_quote(
    *,
    symbol: str,
    market: str,
    db_session: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    return _with_conn(db_session, lambda conn: _read_latest_quote(conn, symbol=symbol, market=market))


def read_macro_observations(
    *,
    indicator_key: str,
    start_date: str,
    end_date: str,
    db_session: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    return _with_conn(
        db_session,
        lambda conn: _read_macro_observations(conn, indicator_key=indicator_key, start_date=start_date, end_date=end_date),
    )


def read_latest_data_quality(
    *,
    dataset_key: str,
    db_session: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    return _with_conn(db_session, lambda conn: _read_latest_data_quality(conn, dataset_key=dataset_key))


def list_latest_quality(db_session: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    return _with_conn(db_session, _list_latest_quality)


def list_latest_ingestion_runs(db_session: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    return _with_conn(db_session, _list_latest_ingestion_runs)


def count_rows(table: str, db_session: sqlite3.Connection) -> int:
    ensure_raw_data_tables(db_session)
    return int(db_session.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"])


def new_ingestion_run(source_id: str, *, status: str = "running") -> IngestionRun:
    now = datetime.now(UTC)
    return IngestionRun(
        run_id=f"{source_id}:{now.isoformat()}",
        source_id=source_id,
        status=status,
        started_at=now,
        finished_at=None,
        row_count=0,
    )


def _with_conn(db_session: sqlite3.Connection | None, fn):
    if db_session is None:
        with api_db.get_conn() as conn:
            ensure_raw_data_tables(conn)
            return fn(conn)
    ensure_raw_data_tables(db_session)
    return fn(db_session)


def _upsert_price_rows(conn: sqlite3.Connection, rows: list[PriceBar]) -> int:
    conn.executemany(
        """
        INSERT INTO raw_market_prices (symbol, market, date, open, high, low, close, volume, source, as_of_date, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, market, date, source, as_of_date) DO UPDATE SET
            open=excluded.open,
            high=excluded.high,
            low=excluded.low,
            close=excluded.close,
            volume=excluded.volume,
            updated_at=excluded.updated_at
        """,
        [
            (
                row.symbol,
                row.market,
                row.date.isoformat(),
                str(row.open),
                str(row.high),
                str(row.low),
                str(row.close),
                str(row.volume),
                row.source,
                row.as_of_date.isoformat(),
                row.updated_at.isoformat(),
            )
            for row in rows
        ],
    )
    conn.commit()
    return len(rows)


def _upsert_current_quote(conn: sqlite3.Connection, quote: CurrentQuote) -> int:
    conn.execute(
        """
        INSERT INTO raw_current_quotes (symbol, market, price, currency, quote_time, source, as_of_date, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, market, source, as_of_date) DO UPDATE SET
            price=excluded.price,
            currency=excluded.currency,
            quote_time=excluded.quote_time,
            updated_at=excluded.updated_at
        """,
        (
            quote.symbol,
            quote.market,
            str(quote.price),
            quote.currency,
            quote.quote_time.isoformat(),
            quote.source,
            quote.as_of_date.isoformat(),
            quote.updated_at.isoformat(),
        ),
    )
    conn.commit()
    return 1


def _upsert_macro_rows(conn: sqlite3.Connection, rows: list[MacroObservation]) -> int:
    conn.executemany(
        """
        INSERT INTO raw_macro_indicators (indicator_key, date, value, unit, source, as_of_date, release_date, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(indicator_key, date, source, as_of_date) DO UPDATE SET
            value=excluded.value,
            unit=excluded.unit,
            release_date=excluded.release_date,
            updated_at=excluded.updated_at
        """,
        [
            (
                row.indicator_key,
                row.date.isoformat(),
                str(row.value),
                row.unit,
                row.source,
                row.as_of_date.isoformat(),
                row.release_date.isoformat() if row.release_date else None,
                row.updated_at.isoformat(),
            )
            for row in rows
        ],
    )
    conn.commit()
    return len(rows)


def _upsert_quality_check(conn: sqlite3.Connection, check: DataQualityCheck) -> int:
    conn.execute(
        """
        INSERT INTO data_quality_checks (
            dataset_key, source, as_of_date, quality_score, missing_ratio, is_stale,
            warnings_json, fallback_policy, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(dataset_key, source, as_of_date) DO UPDATE SET
            quality_score=excluded.quality_score,
            missing_ratio=excluded.missing_ratio,
            is_stale=excluded.is_stale,
            warnings_json=excluded.warnings_json,
            fallback_policy=excluded.fallback_policy,
            updated_at=excluded.updated_at
        """,
        (
            check.dataset_key,
            check.source,
            check.as_of_date.isoformat(),
            check.quality_score,
            check.missing_ratio,
            1 if check.is_stale else 0,
            json.dumps(check.warnings, ensure_ascii=False),
            check.fallback_policy,
            check.updated_at.isoformat(),
        ),
    )
    conn.commit()
    return 1


def _record_ingestion_run(conn: sqlite3.Connection, run: IngestionRun) -> None:
    conn.execute(
        """
        INSERT INTO data_ingestion_runs (run_id, source_id, status, started_at, finished_at, row_count, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
            status=excluded.status,
            finished_at=excluded.finished_at,
            row_count=excluded.row_count,
            error_message=excluded.error_message
        """,
        (
            run.run_id,
            run.source_id,
            run.status,
            run.started_at.isoformat(),
            run.finished_at.isoformat() if run.finished_at else None,
            run.row_count,
            run.error_message,
        ),
    )
    conn.commit()


def _read_historical_prices(conn: sqlite3.Connection, *, symbol: str, market: str, start_date: str, end_date: str):
    rows = conn.execute(
        """
        SELECT * FROM raw_market_prices
        WHERE symbol=? AND market=? AND date BETWEEN ? AND ?
        ORDER BY date ASC, as_of_date ASC
        """,
        (symbol, market, start_date, end_date),
    ).fetchall()
    return [_row_dict(row) for row in rows]


def _read_latest_quote(conn: sqlite3.Connection, *, symbol: str, market: str):
    row = conn.execute(
        """
        SELECT * FROM raw_current_quotes
        WHERE symbol=? AND market=?
        ORDER BY as_of_date DESC, quote_time DESC, updated_at DESC
        LIMIT 1
        """,
        (symbol, market),
    ).fetchone()
    return _row_dict(row) if row else None


def _read_macro_observations(conn: sqlite3.Connection, *, indicator_key: str, start_date: str, end_date: str):
    rows = conn.execute(
        """
        SELECT * FROM raw_macro_indicators
        WHERE indicator_key=? AND date BETWEEN ? AND ?
        ORDER BY date ASC, as_of_date ASC
        """,
        (indicator_key, start_date, end_date),
    ).fetchall()
    return [_row_dict(row) for row in rows]


def _read_latest_data_quality(conn: sqlite3.Connection, *, dataset_key: str):
    row = conn.execute(
        """
        SELECT * FROM data_quality_checks
        WHERE dataset_key=?
        ORDER BY as_of_date DESC, updated_at DESC
        LIMIT 1
        """,
        (dataset_key,),
    ).fetchone()
    return _quality_row(row) if row else None


def _list_latest_quality(conn: sqlite3.Connection):
    rows = conn.execute(
        """
        SELECT q.*
        FROM data_quality_checks q
        JOIN (
            SELECT dataset_key, MAX(as_of_date) AS latest_as_of_date
            FROM data_quality_checks
            GROUP BY dataset_key
        ) latest
          ON q.dataset_key=latest.dataset_key AND q.as_of_date=latest.latest_as_of_date
        ORDER BY q.dataset_key
        """
    ).fetchall()
    return [_quality_row(row) for row in rows]


def _list_latest_ingestion_runs(conn: sqlite3.Connection):
    rows = conn.execute(
        """
        SELECT *
        FROM data_ingestion_runs
        ORDER BY started_at DESC
        LIMIT 100
        """
    ).fetchall()
    return [_row_dict(row) for row in rows]


def _row_dict(row) -> dict[str, Any]:
    data = dict(row)
    for key in ["open", "high", "low", "close", "volume", "price", "value"]:
        if key in data and data[key] is not None:
            data[key] = decimal_from(data[key])
    return data


def _quality_row(row) -> dict[str, Any]:
    data = _row_dict(row)
    data["is_stale"] = bool(data["is_stale"])
    data["warnings"] = json.loads(data.pop("warnings_json") or "[]")
    return data
