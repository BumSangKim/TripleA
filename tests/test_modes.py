import sqlite3

import pytest

from api.db import ensure_dashboard_tables
from api.modes import TradingMode, get_mode_policy, normalize_mode
from api.providers import ProviderRouter
from api.services import get_target_deviations


def test_mode_policy_documents_order_boundaries():
    assert get_mode_policy("mock").order_policy == "disabled"
    assert get_mode_policy("test").external_api is False
    assert get_mode_policy("backtest").db_write_scope == "results"
    assert get_mode_policy("paper").can_execute_orders is True
    assert get_mode_policy("live").order_policy == "read_only_until_manual_approval"


def test_invalid_mode_is_rejected():
    with pytest.raises(ValueError):
        normalize_mode("production")


def test_default_mode_preserves_user_data_workflows():
    assert normalize_mode(None) == TradingMode.PAPER


def test_provider_router_selects_mode_specific_providers():
    router = ProviderRouter()

    assert router.get("mock").name == "MockProvider"
    assert router.get("test").name == "TestProvider"
    assert router.get("backtest").name == "BacktestProvider"
    assert router.get("paper").name == "PaperTradingProvider"
    assert router.get("live").name == "LiveTradingProvider"


def test_provider_router_enforces_read_only_modes():
    router = ProviderRouter()

    with pytest.raises(PermissionError):
        router.get("mock").assert_user_write_allowed()
    with pytest.raises(PermissionError):
        router.get("test").assert_user_write_allowed()

    router.get("paper").assert_user_write_allowed()


def test_dashboard_schema_tables_are_created(tmp_path, monkeypatch):
    db_path = str(tmp_path / "dashboard.db")
    monkeypatch.setattr("api.db.DB_PATH", db_path)

    ensure_dashboard_tables()

    conn = sqlite3.connect(db_path)
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert {
        "account_policies",
        "account_snapshots",
        "portfolio_targets",
        "account_targets",
        "engine_allocations",
        "rebalance_results",
        "backtest_runs",
        "notification_channels",
        "notification_logs",
    }.issubset(tables)


def test_target_deviation_uses_holdings_in_non_mock_mode():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_type TEXT NOT NULL,
            asset_class TEXT NOT NULL,
            target_value REAL NOT NULL,
            warning_thr REAL DEFAULT 3.0,
            danger_thr REAL DEFAULT 5.0
        );
        CREATE TABLE holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            ticker TEXT,
            asset_class TEXT,
            market_value REAL,
            profit REAL DEFAULT 0
        );
        INSERT INTO targets (target_type, asset_class, target_value, warning_thr, danger_thr)
        VALUES ('asset_allocation', 'ETF', 50.0, 3.0, 5.0);
        INSERT INTO holdings (account_id, ticker, asset_class, market_value)
        VALUES (1, 'SPY', 'ETF', 750000);
    """)

    result = get_target_deviations(conn, TradingMode.PAPER)

    assert result[0].currentRatio == 100.0
    assert result[0].deviation == 50.0
    assert result[0].level == "danger"
