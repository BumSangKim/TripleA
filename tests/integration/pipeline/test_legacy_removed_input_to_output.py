from __future__ import annotations

import sqlite3
from dataclasses import fields
from datetime import date

from api.data.strategy_data_readers import (
    SqliteBottleneckSnapshotReader,
    SqliteMacroSnapshotReader,
    SqliteSectorAssetMappingReader,
)
from api.features.market_data.trade_data_service import SqliteTradeSnapshotReader
from api.strategy.triplea_allocator import TripleAAllocator


def test_legacy_removed_readers_preserve_raw_input_to_allocation_output():
    conn = _fixture_conn()
    decision_date = date(2024, 3, 10)
    _seed_known_and_future_inputs(conn)

    macro_reader = SqliteMacroSnapshotReader(conn)
    bottleneck_reader = SqliteBottleneckSnapshotReader(conn)
    sector_mapping_reader = SqliteSectorAssetMappingReader(conn)
    trade_reader = SqliteTradeSnapshotReader(conn)

    macro_snapshot = macro_reader.read_macro_snapshot(decision_date)
    bottleneck_snapshot = bottleneck_reader.read_bottleneck_snapshot(decision_date, lookback_months=12)
    sector_mappings = sector_mapping_reader.read_sector_asset_mappings()
    trade_snapshot = trade_reader.get_trade_snapshot(decision_date, lookback_months=12)

    assert macro_snapshot.get_value("VIXCLS") == 40.0
    assert all(item.data_date <= decision_date for item in macro_snapshot.indicators.values())
    assert [item.indicator_key for item in bottleneck_snapshot.indicators] == ["RS_SMH_SPY"]
    assert all(item.release_date <= decision_date for item in bottleneck_snapshot.indicators)
    assert [item.asset_code for item in sector_mappings["SEMICONDUCTOR"]] == ["SMH"]
    assert all(item.release_date <= decision_date for item in trade_snapshot.items)
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
    assert all("80.0%" not in reason for reason in decision.reasons)
    _assert_review_only_output(decision)


def test_legacy_removed_missing_raw_tables_stay_neutral_and_review_safe():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    decision_date = date(2024, 3, 10)

    decision = TripleAAllocator(
        conn,
        risk_profile="balanced",
        macro_snapshot_reader=SqliteMacroSnapshotReader(conn),
        bottleneck_snapshot_reader=SqliteBottleneckSnapshotReader(conn),
        sector_asset_mapping_reader=SqliteSectorAssetMappingReader(conn),
        trade_snapshot_reader=SqliteTradeSnapshotReader(conn),
    ).allocate(decision_date)

    assert round(sum(decision.final_weights.values()), 6) == 1.0
    assert decision.macro_regime == "neutral"
    assert decision.macro_score == 50
    assert "No macro stress signal available; neutral regime" in decision.reasons
    assert decision.bottleneck_scores
    assert all(score >= 0 for score in decision.bottleneck_scores.values())
    _assert_review_only_output(decision)


def _assert_review_only_output(decision) -> None:
    forbidden_fields = {"order", "orders", "order_candidates", "broker", "execution"}
    assert forbidden_fields.isdisjoint({field.name for field in fields(type(decision))})
    assert not hasattr(decision, "submit_order")
    assert not hasattr(decision, "execute")


def _fixture_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE indicators (
            indicator TEXT,
            value REAL,
            unit TEXT,
            date TEXT,
            source TEXT
        );

        CREATE TABLE bottleneck_indicators (
            indicator_key TEXT,
            indicator_name TEXT,
            sector_code TEXT,
            value_date TEXT,
            release_date TEXT,
            value REAL,
            unit TEXT,
            source TEXT,
            layer TEXT
        );

        CREATE TABLE sector_asset_map (
            sector_code TEXT,
            asset_code TEXT,
            asset_name TEXT,
            asset_type TEXT,
            currency TEXT,
            priority INTEGER,
            is_active INTEGER
        );

        CREATE TABLE trade_series (
            period TEXT,
            country TEXT,
            flow TEXT,
            item_code TEXT,
            item_name TEXT,
            amount_usd REAL,
            quantity REAL,
            unit TEXT,
            yoy REAL,
            mom REAL,
            source TEXT,
            release_date TEXT
        );

        CREATE TABLE market_prices (
            asset_code TEXT,
            price_date TEXT,
            close REAL,
            adj_close REAL,
            currency TEXT,
            source TEXT
        );

        CREATE TABLE fx_rates (
            base_currency TEXT,
            quote_currency TEXT,
            rate_date TEXT,
            rate REAL,
            source TEXT
        );
        """
    )
    return conn


def _seed_known_and_future_inputs(conn: sqlite3.Connection) -> None:
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
        INSERT INTO bottleneck_indicators
        (indicator_key, indicator_name, sector_code, value_date, release_date, value, unit, source, layer)
        VALUES (?, ?, 'SEMICONDUCTOR', ?, ?, ?, 'pt', 'fixture', 'relative_strength')
        """,
        [
            ("RS_SMH_SPY", "known relative strength", "2024-02-29", "2024-03-01", 90.0),
            ("RS_SMH_SPY", "future relative strength", "2024-03-14", "2024-03-15", 10.0),
        ],
    )
    conn.executemany(
        """
        INSERT INTO sector_asset_map
        (sector_code, asset_code, asset_name, asset_type, currency, priority, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("SEMICONDUCTOR", "SMH", "VanEck Semiconductor ETF", "ETF", "USD", 10, 1),
            ("SEMICONDUCTOR", "REMOVED", "Removed ETF", "ETF", "USD", 1, 0),
        ],
    )
    conn.executemany(
        """
        INSERT INTO trade_series
        (period, country, flow, item_code, item_name, amount_usd, quantity, unit, yoy, mom, source, release_date)
        VALUES (?, 'KR', 'export', 'HS_8542', 'semiconductor', 100, NULL, 'USD', ?, NULL, 'fixture', ?)
        """,
        [
            ("2024-01", 35.0, "2024-02-15"),
            ("2024-02", 80.0, "2024-03-15"),
        ],
    )
    conn.executemany(
        """
        INSERT INTO market_prices (asset_code, price_date, close, adj_close, currency, source)
        VALUES (?, ?, ?, NULL, ?, 'fixture')
        """,
        [
            ("SMH", "2024-03-08", 100.0, "USD"),
            ("SMH", "2024-03-11", 103.0, "USD"),
            ("SPY", "2024-03-08", 100.0, "USD"),
            ("SPY", "2024-03-11", 101.0, "USD"),
        ],
    )
    conn.executemany(
        """
        INSERT INTO fx_rates (base_currency, quote_currency, rate_date, rate, source)
        VALUES ('USD', 'KRW', ?, 1000.0, 'fixture')
        """,
        [("2024-03-08",), ("2024-03-11",)],
    )
    conn.commit()
