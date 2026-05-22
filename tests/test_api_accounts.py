import sqlite3

from api.db import _migrate_dashboard_tables
from api.services import get_kpi_summary


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            ticker TEXT NOT NULL,
            name TEXT,
            quantity REAL,
            avg_price REAL,
            current_price REAL,
            market_value REAL,
            profit REAL DEFAULT 0
        );
    """)
    return conn


def test_kpi_summary_empty_holdings_returns_zero_values():
    conn = make_conn()

    summary = get_kpi_summary(conn)

    assert summary.totalAssets == 0
    assert summary.cash == 0
    assert summary.todayProfit == 0
    assert summary.todayProfitRate == 0


def test_kpi_summary_uses_holdings_totals():
    conn = make_conn()
    conn.executemany(
        """
        INSERT INTO holdings
        (account_id, ticker, name, quantity, avg_price, current_price, market_value, profit)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (1, "005930", "삼성전자", 10, 70000, 75000, 750000, 50000),
            (1, "000660", "SK하이닉스", 5, 120000, 110000, 550000, -50000),
        ],
    )

    summary = get_kpi_summary(conn)

    assert summary.totalAssets == 1_300_000
    assert summary.todayProfit == 0
    assert summary.todayProfitRate == 0


def test_dashboard_migration_adds_missing_account_columns():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT,
            broker TEXT
        );
        CREATE TABLE holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            symbol TEXT,
            name TEXT,
            quantity REAL,
            avg_price REAL
        );
        INSERT INTO accounts (name, type, broker) VALUES ('한국투자', '일반', 'KIS');
        INSERT INTO holdings (account_id, symbol, name, quantity, avg_price)
        VALUES (1, '005930', '삼성전자', 10, 70000);
    """)

    _migrate_dashboard_tables(conn)

    columns = {row[1] for row in conn.execute("PRAGMA table_info(holdings)")}
    assert {"ticker", "current_price", "market_value", "profit", "asset_class"}.issubset(columns)
    row = conn.execute("SELECT ticker, current_price, market_value, profit FROM holdings").fetchone()
    assert row["ticker"] == "005930"
    assert row["current_price"] == 70000
    assert row["market_value"] == 700000
    assert row["profit"] == 0
