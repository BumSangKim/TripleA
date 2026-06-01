"""0001: baseline existing schema — all tables from ensure_dashboard_tables."""
from __future__ import annotations

import sqlite3

VERSION = "0001_baseline_existing_schema"

_SQL = """
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

    CREATE TABLE IF NOT EXISTS indicators (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        indicator TEXT NOT NULL,
        value     REAL,
        unit      TEXT,
        date      TEXT NOT NULL,
        source    TEXT,
        frequency TEXT,
        updated   TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(indicator, date, source)
    );

    CREATE INDEX IF NOT EXISTS idx_indicators_indicator_date
    ON indicators(indicator, date);

    CREATE TABLE IF NOT EXISTS account_policies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_type TEXT NOT NULL UNIQUE,
        role TEXT NOT NULL,
        deposit_policy TEXT,
        allowed_products TEXT,
        rebalance_priority TEXT,
        risk_note TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        updated_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS account_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL REFERENCES accounts(id),
        total_value REAL NOT NULL,
        cash_value REAL DEFAULT 0,
        domestic_stock_value REAL DEFAULT 0,
        foreign_stock_value REAL DEFAULT 0,
        bond_value REAL DEFAULT 0,
        etf_value REAL DEFAULT 0,
        pension_value REAL DEFAULT 0,
        alt_value REAL DEFAULT 0,
        snapshot_at TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS portfolio_targets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_name TEXT,
        asset_class TEXT NOT NULL UNIQUE,
        target_ratio REAL NOT NULL,
        warning_threshold REAL DEFAULT 0.03,
        danger_threshold REAL DEFAULT 0.05,
        is_active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS account_targets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_type TEXT NOT NULL,
        account_id INTEGER,
        asset_class TEXT NOT NULL,
        target_ratio REAL NOT NULL,
        warning_threshold REAL DEFAULT 0.03,
        danger_threshold REAL DEFAULT 0.05,
        is_active INTEGER DEFAULT 1,
        UNIQUE(account_type, account_id, asset_class)
    );

    CREATE TABLE IF NOT EXISTS engine_allocations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        strategy_bucket TEXT NOT NULL UNIQUE,
        target_ratio REAL NOT NULL,
        min_ratio REAL,
        max_ratio REAL,
        is_active INTEGER DEFAULT 1,
        updated_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS rebalance_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER,
        mode TEXT NOT NULL,
        account_id INTEGER,
        account_type TEXT,
        asset_class TEXT,
        current_ratio REAL,
        target_ratio REAL,
        deviation REAL,
        action TEXT,
        amount REAL,
        reason TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS order_drafts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mode TEXT NOT NULL,
        source TEXT NOT NULL,
        status TEXT NOT NULL,
        max_order_amount REAL,
        total_amount REAL DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        approved_at TEXT,
        executed_at TEXT
    );

    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        draft_id INTEGER NOT NULL REFERENCES order_drafts(id),
        account_id INTEGER,
        asset_class TEXT NOT NULL,
        side TEXT NOT NULL,
        amount REAL NOT NULL,
        status TEXT NOT NULL,
        reason TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS order_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        draft_id INTEGER REFERENCES order_drafts(id),
        mode TEXT NOT NULL,
        event TEXT NOT NULL,
        status TEXT NOT NULL,
        message TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS backtest_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        start_date TEXT,
        end_date TEXT,
        initial_capital REAL,
        strategy_mode TEXT DEFAULT 'triplea_dynamic',
        risk_profile TEXT DEFAULT 'balanced',
        universe_id TEXT DEFAULT 'default_global',
        rebalance_frequency TEXT,
        base_currency TEXT DEFAULT 'KRW',
        fee_bps REAL DEFAULT 0,
        slippage_bps REAL DEFAULT 0,
        tax_bps REAL DEFAULT 0,
        data_lookback_years INTEGER DEFAULT 5,
        status TEXT,
        total_return REAL,
        annual_return REAL,
        max_drawdown REAL,
        volatility REAL,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS backtest_points (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL REFERENCES backtest_runs(id),
        point_date TEXT NOT NULL,
        portfolio_value REAL NOT NULL,
        drawdown REAL NOT NULL,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS asset_universe (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_code TEXT NOT NULL UNIQUE,
        symbol TEXT NOT NULL,
        name TEXT,
        asset_class TEXT NOT NULL,
        market TEXT,
        currency TEXT NOT NULL DEFAULT 'KRW',
        source_type TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        updated_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS market_prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_code TEXT NOT NULL,
        price_date TEXT NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL NOT NULL,
        adj_close REAL,
        volume REAL,
        currency TEXT NOT NULL,
        source TEXT NOT NULL,
        fetched_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(asset_code, price_date)
    );

    CREATE INDEX IF NOT EXISTS idx_market_prices_asset_date
    ON market_prices(asset_code, price_date);

    CREATE TABLE IF NOT EXISTS fx_rates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        base_currency TEXT NOT NULL,
        quote_currency TEXT NOT NULL,
        rate_date TEXT NOT NULL,
        rate REAL NOT NULL,
        source TEXT NOT NULL,
        fetched_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(base_currency, quote_currency, rate_date)
    );

    CREATE INDEX IF NOT EXISTS idx_fx_rates_pair_date
    ON fx_rates(base_currency, quote_currency, rate_date);

    CREATE TABLE IF NOT EXISTS data_collection_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        collector_type TEXT NOT NULL,
        source TEXT,
        universe_id TEXT,
        start_date TEXT,
        end_date TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        records_inserted INTEGER DEFAULT 0,
        records_updated INTEGER DEFAULT 0,
        error_message TEXT,
        started_at TEXT DEFAULT (datetime('now','localtime')),
        finished_at TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_data_collection_runs_type_started
    ON data_collection_runs(collector_type, started_at);

    CREATE TABLE IF NOT EXISTS trade_series (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        period TEXT NOT NULL,
        country TEXT,
        flow TEXT NOT NULL,
        item_code TEXT NOT NULL,
        item_name TEXT,
        amount_usd REAL,
        quantity REAL,
        unit TEXT,
        yoy REAL,
        mom REAL,
        source TEXT,
        release_date TEXT,
        fetched_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(period, country, flow, item_code, source)
    );

    CREATE INDEX IF NOT EXISTS idx_trade_series_release
    ON trade_series(release_date, period);

    CREATE INDEX IF NOT EXISTS idx_trade_series_item
    ON trade_series(item_code, period);

    CREATE TABLE IF NOT EXISTS trade_item_sector_map (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_code TEXT NOT NULL,
        sector_code TEXT NOT NULL,
        item_name TEXT,
        weight REAL DEFAULT 1,
        source TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        updated_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(item_code, sector_code)
    );

    CREATE INDEX IF NOT EXISTS idx_trade_item_sector_map_sector
    ON trade_item_sector_map(sector_code, is_active);

    CREATE TABLE IF NOT EXISTS bottleneck_indicators (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        indicator_key TEXT NOT NULL,
        indicator_name TEXT,
        sector_code TEXT NOT NULL,
        value_date TEXT NOT NULL,
        release_date TEXT,
        value REAL,
        unit TEXT,
        source TEXT,
        layer TEXT,
        fetched_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(indicator_key, sector_code, value_date, source)
    );

    CREATE INDEX IF NOT EXISTS idx_bottleneck_indicators_release
    ON bottleneck_indicators(release_date, value_date);

    CREATE INDEX IF NOT EXISTS idx_bottleneck_indicators_sector
    ON bottleneck_indicators(sector_code, value_date);

    CREATE TABLE IF NOT EXISTS sector_asset_map (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sector_code TEXT NOT NULL,
        asset_code TEXT NOT NULL,
        asset_name TEXT,
        asset_type TEXT,
        currency TEXT DEFAULT 'USD',
        priority INTEGER DEFAULT 100,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        updated_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(sector_code, asset_code)
    );

    CREATE INDEX IF NOT EXISTS idx_sector_asset_map_sector
    ON sector_asset_map(sector_code, is_active, priority);

    CREATE TABLE IF NOT EXISTS backtest_positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL REFERENCES backtest_runs(id),
        point_date TEXT NOT NULL,
        asset_code TEXT NOT NULL,
        quantity REAL NOT NULL,
        price REAL NOT NULL,
        fx_rate REAL DEFAULT 1,
        market_value REAL NOT NULL,
        weight REAL NOT NULL,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE INDEX IF NOT EXISTS idx_backtest_positions_run_date
    ON backtest_positions(run_id, point_date);

    CREATE TABLE IF NOT EXISTS backtest_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL REFERENCES backtest_runs(id),
        trade_date TEXT NOT NULL,
        asset_code TEXT NOT NULL,
        side TEXT NOT NULL,
        quantity REAL NOT NULL,
        price REAL NOT NULL,
        fx_rate REAL DEFAULT 1,
        gross_amount REAL NOT NULL,
        fee REAL DEFAULT 0,
        slippage REAL DEFAULT 0,
        tax REAL DEFAULT 0,
        net_amount REAL NOT NULL,
        reason TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE INDEX IF NOT EXISTS idx_backtest_trades_run_date
    ON backtest_trades(run_id, trade_date);

    CREATE TABLE IF NOT EXISTS backtest_decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL REFERENCES backtest_runs(id),
        decision_date TEXT NOT NULL,
        strategy_mode TEXT NOT NULL,
        risk_profile TEXT,
        universe_id TEXT,
        macro_regime TEXT,
        macro_score INTEGER,
        bucket_weights_json TEXT,
        final_weights_json TEXT,
        bottleneck_scores_json TEXT,
        reasons_json TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE INDEX IF NOT EXISTS idx_backtest_decisions_run_date
    ON backtest_decisions(run_id, decision_date);

    CREATE TABLE IF NOT EXISTS backtest_sector_decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL REFERENCES backtest_runs(id),
        decision_id INTEGER REFERENCES backtest_decisions(id),
        decision_date TEXT NOT NULL,
        sector_code TEXT NOT NULL,
        total_score REAL,
        trade_score REAL,
        demand_score REAL,
        supply_score REAL,
        relative_strength_score REAL,
        regime TEXT,
        reasons_json TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE INDEX IF NOT EXISTS idx_backtest_sector_decisions_run_date
    ON backtest_sector_decisions(run_id, decision_date);

    CREATE INDEX IF NOT EXISTS idx_backtest_sector_decisions_sector
    ON backtest_sector_decisions(sector_code, decision_date);

    CREATE TABLE IF NOT EXISTS notification_channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_type TEXT NOT NULL,
        channel_name TEXT,
        config TEXT,
        is_enabled INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS notification_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_type TEXT NOT NULL,
        alert_type TEXT,
        message TEXT,
        dedup_key TEXT,
        status TEXT,
        sent_at TEXT,
        error_message TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );
"""


def apply(conn: sqlite3.Connection) -> None:
    conn.executescript(_SQL)
    conn.commit()
