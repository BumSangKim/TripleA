"""
api/db.py
FastAPI 전용 DB 접속 헬퍼 - 기존 economic_data.db 재사용
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = os.getenv("DB_PATH", str(PROJECT_ROOT / "data" / "economic_data.db"))


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def ensure_dashboard_tables():
    """대시보드 전용 테이블 초기화 (기존 DB에 추가)"""
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS accounts (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                type          TEXT,
                broker        TEXT,
                initial_value REAL DEFAULT 0,
                created_at    TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS holdings (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id    INTEGER REFERENCES accounts(id),
                ticker        TEXT NOT NULL,
                name          TEXT,
                quantity      REAL,
                avg_price     REAL,
                current_price REAL,
                market_value  REAL,
                profit        REAL DEFAULT 0,
                updated_at    TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS targets (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                target_type  TEXT NOT NULL,
                asset_class  TEXT NOT NULL,
                target_value REAL NOT NULL,
                warning_thr  REAL DEFAULT 3.0,
                danger_thr   REAL DEFAULT 5.0,
                created_at   TEXT DEFAULT (datetime('now','localtime')),
                updated_at   TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS dashboard_alerts (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                level      TEXT NOT NULL,
                category   TEXT,
                title      TEXT NOT NULL,
                message    TEXT,
                is_read    INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS documents (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                type       TEXT DEFAULT 'memo',
                title      TEXT NOT NULL,
                content    TEXT,
                tags       TEXT,
                url        TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            );
        """)
        _migrate_dashboard_tables(conn)
        conn.commit()
        _seed_default_targets(conn)


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, definition: str):
    if column not in _table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _migrate_dashboard_tables(conn: sqlite3.Connection):
    """기존 로컬 DB가 예전 계좌 스키마여도 최신 대시보드 쿼리가 동작하게 보강."""
    _add_column_if_missing(conn, "accounts", "initial_value", "REAL DEFAULT 0")

    holding_columns = _table_columns(conn, "holdings")
    _add_column_if_missing(conn, "holdings", "ticker", "TEXT")
    _add_column_if_missing(conn, "holdings", "current_price", "REAL")
    _add_column_if_missing(conn, "holdings", "market_value", "REAL")
    _add_column_if_missing(conn, "holdings", "profit", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "holdings", "asset_class", "TEXT")

    if "symbol" in holding_columns:
        conn.execute("UPDATE holdings SET ticker=symbol WHERE ticker IS NULL OR ticker=''")
    conn.execute("UPDATE holdings SET current_price=avg_price WHERE current_price IS NULL")
    conn.execute("""
        UPDATE holdings
        SET market_value=COALESCE(quantity, 0) * COALESCE(current_price, avg_price, 0)
        WHERE market_value IS NULL
    """)


def _seed_default_targets(conn: sqlite3.Connection):
    """기본 목표 비중 초기값 삽입 (없을 때만)"""
    row = conn.execute("SELECT COUNT(*) FROM targets").fetchone()
    if row[0] == 0:
        defaults = [
            # 자산배분 목표
            ("asset_allocation", "국내주식",   25.0,  3.0,  5.0),
            ("asset_allocation", "해외주식",   35.0,  3.0,  5.0),
            ("asset_allocation", "채권",       15.0,  2.0,  4.0),
            ("asset_allocation", "ETF",         10.0,  2.0,  4.0),
            ("asset_allocation", "현금",        15.0,  2.0,  4.0),
            # 투자·수익 목표
            ("monthly_invest",   "월 투자 목표",  10_000_000, 10.0, 20.0),
            ("return_rate",      "연 수익률 목표", 8.0,        1.5,  3.0),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO targets (target_type, asset_class, target_value, warning_thr, danger_thr) VALUES (?,?,?,?,?)",
            defaults,
        )
        conn.commit()
