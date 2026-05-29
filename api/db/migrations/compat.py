"""Schema migration helpers for existing DB upgrades (ADD COLUMN style)."""
from __future__ import annotations

import sqlite3


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return bool(row)


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    if not _table_exists(conn, table):
        return
    if column not in _table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def migrate_existing_schema(conn: sqlite3.Connection) -> None:
    """Apply ADD COLUMN migrations for existing databases that predate the baseline migration."""
    _add_column_if_missing(conn, "accounts", "initial_value", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "accounts", "account_type", "TEXT DEFAULT 'GENERAL'")
    _add_column_if_missing(conn, "accounts", "connection_status", "TEXT DEFAULT 'UNLINKED'")
    _add_column_if_missing(conn, "accounts", "trade_status", "TEXT DEFAULT 'ORDER_DISABLED'")
    _add_column_if_missing(conn, "accounts", "include_in_rebalancing", "INTEGER DEFAULT 1")
    _add_column_if_missing(conn, "accounts", "data_source", "TEXT DEFAULT 'MANUAL'")
    _add_column_if_missing(conn, "accounts", "last_synced_at", "TEXT")

    holding_columns = _table_columns(conn, "holdings") if _table_exists(conn, "holdings") else set()
    _add_column_if_missing(conn, "holdings", "ticker", "TEXT")
    _add_column_if_missing(conn, "holdings", "current_price", "REAL")
    _add_column_if_missing(conn, "holdings", "market_value", "REAL")
    _add_column_if_missing(conn, "holdings", "profit", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "holdings", "asset_class", "TEXT")
    _add_column_if_missing(conn, "holdings", "price", "REAL")
    _add_column_if_missing(conn, "holdings", "value", "REAL")
    _add_column_if_missing(conn, "holdings", "strategy_bucket", "TEXT")

    if "symbol" in holding_columns:
        conn.execute("UPDATE holdings SET ticker=symbol WHERE ticker IS NULL OR ticker=''")
    conn.execute("UPDATE holdings SET current_price=avg_price WHERE current_price IS NULL")
    conn.execute("""
        UPDATE holdings
        SET market_value=COALESCE(quantity, 0) * COALESCE(current_price, avg_price, 0)
        WHERE market_value IS NULL
    """)
    conn.execute("UPDATE holdings SET price=current_price WHERE price IS NULL")
    conn.execute("UPDATE holdings SET value=market_value WHERE value IS NULL")

    _add_column_if_missing(conn, "backtest_runs", "strategy_mode", "TEXT DEFAULT 'triplea_dynamic'")
    _add_column_if_missing(conn, "backtest_runs", "risk_profile", "TEXT DEFAULT 'balanced'")
    _add_column_if_missing(conn, "backtest_runs", "universe_id", "TEXT DEFAULT 'default_global'")
    _add_column_if_missing(conn, "backtest_runs", "base_currency", "TEXT DEFAULT 'KRW'")
    _add_column_if_missing(conn, "backtest_runs", "fee_bps", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "backtest_runs", "slippage_bps", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "backtest_runs", "tax_bps", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "backtest_runs", "data_lookback_years", "INTEGER DEFAULT 5")

    conn.commit()
