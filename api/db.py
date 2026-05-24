"""
api/db.py
FastAPI 전용 DB 접속 헬퍼 - 기존 economic_data.db 재사용
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
import os
import yaml

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
        """)
        _migrate_dashboard_tables(conn)
        conn.commit()
        _seed_default_targets(conn)
        _seed_account_policies(conn)
        _seed_engine_allocations(conn)
        _seed_asset_universe(conn)
        _seed_investment_universe(conn)
        _seed_sector_maps(conn)


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return bool(row)


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, definition: str):
    if not _table_exists(conn, table):
        return
    if column not in _table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _migrate_dashboard_tables(conn: sqlite3.Connection):
    """기존 로컬 DB가 예전 계좌 스키마여도 최신 대시보드 쿼리가 동작하게 보강."""
    _add_column_if_missing(conn, "accounts", "initial_value", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "accounts", "account_type", "TEXT DEFAULT 'GENERAL'")
    _add_column_if_missing(conn, "accounts", "connection_status", "TEXT DEFAULT 'UNLINKED'")
    _add_column_if_missing(conn, "accounts", "trade_status", "TEXT DEFAULT 'ORDER_DISABLED'")
    _add_column_if_missing(conn, "accounts", "include_in_rebalancing", "INTEGER DEFAULT 1")
    _add_column_if_missing(conn, "accounts", "data_source", "TEXT DEFAULT 'MANUAL'")
    _add_column_if_missing(conn, "accounts", "last_synced_at", "TEXT")

    holding_columns = _table_columns(conn, "holdings")
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


def _seed_account_policies(conn: sqlite3.Connection):
    policies = [
        ("GENERAL", "SATELLITE", "입출금 자유", "국내/해외 주식, ETF 등", "공격 기회 활용", "단기 유동성 관리"),
        ("ISA", "TAX_ADVANTAGED", "연간 납입 한도 고려", "국내 상장 상품 중심", "신규 납입금 활용 우선", "잦은 매매 자제"),
        ("PENSION_SAVINGS", "RETIREMENT", "장기 납입", "연금 계좌 허용 상품", "방어형 장기 운용", "위험자산 과다 노출 제한"),
        ("IRP", "RETIREMENT", "출금 제약", "IRP 허용 상품", "안전자산 우선", "안전자산 비중 유지"),
    ]
    conn.executemany("""
        INSERT INTO account_policies
        (account_type, role, deposit_policy, allowed_products, rebalance_priority, risk_note)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(account_type) DO UPDATE SET
            role=excluded.role,
            deposit_policy=excluded.deposit_policy,
            allowed_products=excluded.allowed_products,
            rebalance_priority=excluded.rebalance_priority,
            risk_note=excluded.risk_note,
            updated_at=datetime('now','localtime')
    """, policies)
    conn.commit()


def _seed_engine_allocations(conn: sqlite3.Connection):
    defaults = [
        ("DEFENSIVE_CORE", 0.65, 0.55, 0.80),
        ("AGGRESSIVE_ALPHA", 0.30, 0.10, 0.40),
        ("LIQUIDITY", 0.05, 0.03, 0.20),
    ]
    conn.executemany("""
        INSERT INTO engine_allocations (strategy_bucket, target_ratio, min_ratio, max_ratio)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(strategy_bucket) DO UPDATE SET
            target_ratio=excluded.target_ratio,
            min_ratio=excluded.min_ratio,
            max_ratio=excluded.max_ratio,
            updated_at=datetime('now','localtime')
    """, defaults)
    conn.commit()


def _seed_asset_universe(conn: sqlite3.Connection):
    config_path = PROJECT_ROOT / "config" / "backtest_assets.yaml"
    if not config_path.exists():
        return

    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    default_assets = data.get("default_assets") or {}
    rows = []
    for item in default_assets.values():
        asset_code = (item.get("asset_code") or "").strip()
        symbol = (item.get("symbol") or "").strip()
        asset_class = (item.get("asset_class") or "").strip()
        source_type = (item.get("source_type") or "").strip()
        currency = (item.get("currency") or "KRW").strip()
        if not all([asset_code, symbol, asset_class, source_type, currency]):
            continue
        rows.append((
            asset_code,
            symbol,
            item.get("name"),
            asset_class,
            item.get("market"),
            currency,
            source_type,
            1 if item.get("is_active", True) else 0,
        ))

    if not rows:
        return

    conn.executemany("""
        INSERT INTO asset_universe
        (asset_code, symbol, name, asset_class, market, currency, source_type, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(asset_code) DO UPDATE SET
            symbol=excluded.symbol,
            name=excluded.name,
            asset_class=excluded.asset_class,
            market=excluded.market,
            currency=excluded.currency,
            source_type=excluded.source_type,
            is_active=excluded.is_active,
            updated_at=datetime('now','localtime')
    """, rows)
    conn.commit()


def _seed_investment_universe(conn: sqlite3.Connection):
    data = _load_yaml_config(PROJECT_ROOT / "config" / "investment_universe.yaml")
    universes = data.get("universes") or {}
    rows = []
    for universe in universes.values():
        for item in universe.get("assets") or []:
            asset_code = (item.get("asset_code") or "").strip()
            if not asset_code:
                continue
            source_type = (item.get("source_type") or "manual").strip()
            rows.append((
                asset_code,
                (item.get("symbol") or asset_code).strip(),
                item.get("name"),
                (item.get("asset_class") or item.get("role") or asset_code).strip(),
                item.get("market"),
                (item.get("currency") or universe.get("base_currency") or "KRW").strip(),
                source_type,
                1,
            ))

    if not rows:
        return

    conn.executemany("""
        INSERT INTO asset_universe
        (asset_code, symbol, name, asset_class, market, currency, source_type, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(asset_code) DO NOTHING
    """, rows)
    conn.commit()


def _load_yaml_config(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _seed_sector_maps(conn: sqlite3.Connection):
    taxonomy = _load_yaml_config(PROJECT_ROOT / "config" / "sector_taxonomy.yaml")
    universes = _load_yaml_config(PROJECT_ROOT / "config" / "investment_universe.yaml").get("universes") or {}
    default_assets = {
        item.get("asset_code"): item
        for item in (universes.get("default_global") or {}).get("assets", [])
        if item.get("asset_code")
    }

    trade_rows = []
    sector_asset_rows = []
    for sector_code, sector in (taxonomy.get("sectors") or {}).items():
        for item_code in sector.get("trade_items") or []:
            trade_rows.append((
                item_code,
                sector_code,
                None,
                1,
                "sector_taxonomy.yaml",
                1,
            ))

        for priority, asset_code in enumerate(sector.get("assets") or [], start=1):
            asset = default_assets.get(asset_code, {})
            sector_asset_rows.append((
                sector_code,
                asset_code,
                asset.get("name"),
                asset.get("role"),
                asset.get("currency") or "USD",
                priority,
                1,
            ))

    if trade_rows:
        conn.executemany("""
            INSERT INTO trade_item_sector_map
            (item_code, sector_code, item_name, weight, source, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(item_code, sector_code) DO UPDATE SET
                item_name=excluded.item_name,
                weight=excluded.weight,
                source=excluded.source,
                is_active=excluded.is_active,
                updated_at=datetime('now','localtime')
        """, trade_rows)

    if sector_asset_rows:
        conn.executemany("""
            INSERT INTO sector_asset_map
            (sector_code, asset_code, asset_name, asset_type, currency, priority, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sector_code, asset_code) DO UPDATE SET
                asset_name=excluded.asset_name,
                asset_type=excluded.asset_type,
                currency=excluded.currency,
                priority=excluded.priority,
                is_active=excluded.is_active,
                updated_at=datetime('now','localtime')
        """, sector_asset_rows)

    if trade_rows or sector_asset_rows:
        conn.commit()
