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
        "data_collection_runs",
        "trade_series",
        "trade_item_sector_map",
        "bottleneck_indicators",
        "sector_asset_map",
        "backtest_positions",
        "backtest_trades",
        "backtest_decisions",
        "backtest_sector_decisions",
    }.issubset(tables)

    indexes = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
    }
    assert {
        "idx_market_prices_asset_date",
        "idx_fx_rates_pair_date",
        "idx_data_collection_runs_type_started",
        "idx_trade_series_release",
        "idx_trade_item_sector_map_sector",
        "idx_bottleneck_indicators_release",
        "idx_sector_asset_map_sector",
        "idx_backtest_positions_run_date",
        "idx_backtest_trades_run_date",
        "idx_backtest_decisions_run_date",
        "idx_backtest_sector_decisions_run_date",
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
    configured_assets = {
        row[0]: row[1:]
        for row in conn.execute(
            "SELECT asset_code, symbol, currency, source_type FROM asset_universe"
        ).fetchall()
    }
    assert configured_assets["SMH"] == ("SMH", "USD", "yahoo")
    assert configured_assets["GOLD"] == ("GLD", "USD", "yahoo")

    sector_assets = {
        tuple(row)
        for row in conn.execute(
            """
            SELECT sector_code, asset_code, currency
            FROM sector_asset_map
            WHERE is_active = 1
            """
        ).fetchall()
    }
    assert ("SEMICONDUCTOR", "SMH", "USD") in sector_assets
    assert ("POWER_GRID", "XLU", "USD") in sector_assets

    trade_items = {
        row[0]: row[1]
        for row in conn.execute(
            """
            SELECT item_code, sector_code
            FROM trade_item_sector_map
            WHERE is_active = 1
            """
        ).fetchall()
    }
    assert trade_items["HS_8542"] == "SEMICONDUCTOR"
    assert trade_items["HS_8507"] == "BATTERY"


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


def test_trade_and_bottleneck_schema_prevent_future_data_leakage(tmp_path, monkeypatch):
    db_path = str(tmp_path / "market_data.db")
    monkeypatch.setattr("api.db.DB_PATH", db_path)
    ensure_dashboard_tables()

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO trade_series
        (period, country, flow, item_code, amount_usd, yoy, source, release_date)
        VALUES ('2024-01', 'KR', 'export', 'HS_8542', 100, 12, 'test', '2024-02-15')
        """
    )
    conn.execute(
        """
        INSERT INTO trade_series
        (period, country, flow, item_code, amount_usd, yoy, source, release_date)
        VALUES ('2024-02', 'KR', 'export', 'HS_8542', 130, 30, 'test', '2024-03-15')
        """
    )
    conn.execute(
        """
        INSERT INTO bottleneck_indicators
        (indicator_key, sector_code, value_date, release_date, value, source, layer)
        VALUES ('RS_SMH_SPY', 'SEMICONDUCTOR', '2024-02-29', '2024-03-01', 71, 'test', 'relative_strength')
        """
    )
    conn.execute(
        """
        INSERT INTO bottleneck_indicators
        (indicator_key, sector_code, value_date, release_date, value, source, layer)
        VALUES ('RS_SMH_SPY', 'SEMICONDUCTOR', '2024-03-31', '2024-04-01', 90, 'test', 'relative_strength')
        """
    )

    trade_rows = conn.execute(
        """
        SELECT period FROM trade_series
        WHERE item_code = 'HS_8542' AND release_date <= '2024-03-10'
        ORDER BY release_date
        """
    ).fetchall()
    bottleneck_rows = conn.execute(
        """
        SELECT value_date FROM bottleneck_indicators
        WHERE indicator_key = 'RS_SMH_SPY' AND release_date <= '2024-03-10'
        ORDER BY release_date
        """
    ).fetchall()

    assert [row[0] for row in trade_rows] == ["2024-01"]
    assert [row[0] for row in bottleneck_rows] == ["2024-02-29"]
