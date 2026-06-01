from __future__ import annotations

import sqlite3
from dataclasses import fields
from datetime import date

from api.data.strategy_data_readers import (
    SqliteBottleneckSnapshotReader,
    SqliteMacroSnapshotReader,
    SqliteSectorAssetMappingReader,
)
from api.db.initialize import initialize_database
from api.features.market_data.trade_data_service import SqliteTradeSnapshotReader
from api.strategy.triplea_allocator import TripleAAllocator


def test_strategy_engine_decoupled_raw_input_to_allocation_output(tmp_path, monkeypatch):
    db_path = str(tmp_path / "strategy_decoupled.db")
    monkeypatch.setattr("api.db.connection.DB_PATH", db_path)
    initialize_database()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    decision_date = date(2024, 3, 10)
    _seed_raw_inputs(conn)

    macro_reader = SqliteMacroSnapshotReader(conn)
    bottleneck_reader = SqliteBottleneckSnapshotReader(conn)
    sector_mapping_reader = SqliteSectorAssetMappingReader(conn)
    trade_reader = SqliteTradeSnapshotReader(conn)

    macro_snapshot = macro_reader.read_macro_snapshot(decision_date)
    bottleneck_snapshot = bottleneck_reader.read_bottleneck_snapshot(decision_date, lookback_months=12)
    trade_snapshot = trade_reader.get_trade_snapshot(decision_date, lookback_months=12)

    assert macro_snapshot.get_value("VIXCLS") == 40.0
    assert all(item.release_date <= decision_date for item in bottleneck_snapshot.indicators)
    assert all(item.release_date <= decision_date for item in trade_snapshot.items)
    assert all(item.value != 10.0 for item in bottleneck_snapshot.indicators)
    assert all(item.yoy != 80.0 for item in trade_snapshot.items)

    decision = TripleAAllocator(
        conn,
        risk_profile="balanced",
        macro_snapshot_reader=macro_reader,
        bottleneck_snapshot_reader=bottleneck_reader,
        sector_asset_mapping_reader=sector_mapping_reader,
        trade_snapshot_reader=trade_reader,
    ).allocate(decision_date)

    assert round(sum(decision.final_weights.values()), 6) == 1.0
    assert decision.reasons
    assert decision.macro_regime == "risk_off"
    assert decision.macro_score <= 25
    assert decision.bottleneck_scores["SEMICONDUCTOR"] >= 70
    assert all("+80.0%" not in reason for reason in decision.reasons)

    forbidden_fields = {"order", "orders", "order_candidates", "broker", "execution"}
    assert forbidden_fields.isdisjoint({field.name for field in fields(type(decision))})


def _seed_raw_inputs(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS indicators (
            indicator TEXT,
            value REAL,
            unit TEXT,
            date TEXT,
            source TEXT
        )
        """
    )
    conn.executemany(
        """
        INSERT INTO indicators (indicator, value, unit, date, source)
        VALUES (?, ?, 'pt', ?, 'fixture')
        """,
        [
            ("VIXCLS", 40.0, "2024-03-01"),
            ("VIXCLS", 12.0, "2024-03-15"),
        ],
    )
    conn.executemany(
        """
        INSERT INTO trade_series
        (period, country, flow, item_code, amount_usd, yoy, source, release_date)
        VALUES (?, 'KR', 'export', 'HS_8542', 100, ?, 'fixture', ?)
        """,
        [
            ("2024-01", 35.0, "2024-02-15"),
            ("2024-02", 80.0, "2024-03-15"),
        ],
    )
    conn.executemany(
        """
        INSERT INTO bottleneck_indicators
        (indicator_key, sector_code, value_date, release_date, value, source, layer)
        VALUES (?, 'SEMICONDUCTOR', ?, ?, ?, 'fixture', 'relative_strength')
        """,
        [
            ("RS_SMH_SPY", "2024-02-29", "2024-03-01", 90.0),
            ("RS_SMH_SPY", "2024-03-14", "2024-03-15", 10.0),
        ],
    )
    conn.executemany(
        """
        INSERT OR REPLACE INTO market_prices
        (asset_code, price_date, close, currency, source)
        VALUES (?, ?, ?, ?, 'fixture')
        """,
        [
            ("KOSPI", "2024-03-08", 100.0, "KRW"),
            ("KOSPI", "2024-03-11", 101.0, "KRW"),
            ("SPY", "2024-03-08", 100.0, "USD"),
            ("SPY", "2024-03-11", 101.0, "USD"),
            ("QQQ", "2024-03-08", 100.0, "USD"),
            ("QQQ", "2024-03-11", 102.0, "USD"),
            ("SMH", "2024-03-08", 100.0, "USD"),
            ("SMH", "2024-03-11", 103.0, "USD"),
            ("TLT", "2024-03-08", 100.0, "USD"),
            ("TLT", "2024-03-11", 99.0, "USD"),
            ("GOLD", "2024-03-08", 100.0, "USD"),
            ("GOLD", "2024-03-11", 100.5, "USD"),
            ("CASH_KRW", "2024-03-08", 1.0, "KRW"),
            ("CASH_KRW", "2024-03-11", 1.0, "KRW"),
        ],
    )
    conn.executemany(
        """
        INSERT OR REPLACE INTO fx_rates
        (base_currency, quote_currency, rate_date, rate, source)
        VALUES ('USD', 'KRW', ?, 1000.0, 'fixture')
        """,
        [("2024-03-08",), ("2024-03-11",)],
    )
    conn.commit()
