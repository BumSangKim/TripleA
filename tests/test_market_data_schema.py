import sqlite3

from api.db import ensure_dashboard_tables


def test_market_data_schema_and_seed_assets_are_created(tmp_path, monkeypatch):
    db_path = str(tmp_path / "market_data.db")
    monkeypatch.setattr("api.db.DB_PATH", db_path)

    ensure_dashboard_tables()

    conn = sqlite3.connect(db_path)
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert {
        "asset_universe",
        "market_prices",
        "fx_rates",
        "backtest_positions",
        "backtest_trades",
    }.issubset(tables)

    indexes = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
    }
    assert {
        "idx_market_prices_asset_date",
        "idx_fx_rates_pair_date",
        "idx_backtest_positions_run_date",
        "idx_backtest_trades_run_date",
    }.issubset(indexes)

    assets = {
        row[0]: row[1:]
        for row in conn.execute(
            "SELECT asset_class, asset_code, currency, source_type FROM asset_universe"
        ).fetchall()
    }
    assert assets["국내주식"] == ("KOSPI", "KRW", "yahoo")
    assert assets["해외주식"] == ("SPY", "USD", "yahoo")
    assert assets["현금"] == ("CASH_KRW", "KRW", "manual")


def test_market_price_uniqueness_uses_asset_and_date(tmp_path, monkeypatch):
    db_path = str(tmp_path / "market_data.db")
    monkeypatch.setattr("api.db.DB_PATH", db_path)
    ensure_dashboard_tables()

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO market_prices
        (asset_code, price_date, close, adj_close, currency, source)
        VALUES ('SPY', '2024-01-02', 100, 101, 'USD', 'test')
        """
    )

    try:
        conn.execute(
            """
            INSERT INTO market_prices
            (asset_code, price_date, close, adj_close, currency, source)
            VALUES ('SPY', '2024-01-02', 102, 103, 'USD', 'test')
            """
        )
        duplicated = False
    except sqlite3.IntegrityError:
        duplicated = True

    assert duplicated is True
