import sqlite3

from api.providers.mock import BacktestProvider, MockProvider, TestProvider as ReadOnlyTestProvider
from api.providers.modes import TradingMode, get_mode_policy


def test_mock_provider_instantiates():
    provider = MockProvider(get_mode_policy("mock"))
    assert provider.mode == TradingMode.MOCK
    assert provider.name == "MockProvider"


def test_mock_provider_sync_accounts_returns_local_noop_result():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY,
            name TEXT,
            type TEXT,
            account_type TEXT,
            broker TEXT,
            initial_value REAL,
            connection_status TEXT,
            trade_status TEXT,
            include_in_rebalancing INTEGER,
            data_source TEXT,
            last_synced_at TEXT
        );
        CREATE TABLE holdings (
            id INTEGER PRIMARY KEY,
            account_id INTEGER,
            asset_class TEXT,
            market_value REAL,
            profit REAL
        );
        INSERT INTO accounts (id, name, type, account_type, broker, initial_value)
        VALUES (1, 'Mock', 'TAXABLE', 'TAXABLE', 'MOCK', 1000);
        INSERT INTO holdings (account_id, asset_class, market_value, profit)
        VALUES (1, '현금', 250, 0), (1, 'ETF', 750, 10);
        """
    )

    result = MockProvider(get_mode_policy("mock")).sync_accounts(conn)

    assert result.ok is True
    assert result.mode == TradingMode.MOCK
    assert result.provider == "MockProvider"
    assert result.totalValue == 1000
    assert result.cashValue == 250
    assert result.syncedPositions == 0


def test_test_provider_instantiates():
    provider = ReadOnlyTestProvider(get_mode_policy("test"))
    assert provider.mode == TradingMode.TEST
    assert provider.name == "TestProvider"


def test_backtest_provider_instantiates():
    provider = BacktestProvider(get_mode_policy("backtest"))
    assert provider.mode == TradingMode.BACKTEST
    assert provider.name == "BacktestProvider"
    assert provider.capabilities.can_write_user_data is True
