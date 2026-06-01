from __future__ import annotations

import sqlite3
from datetime import date

from api.data.bottleneck_snapshot_reader import get_bottleneck_snapshot, get_sector_asset_mappings
from api.data.strategy_data_readers import SqliteBottleneckSnapshotReader, SqliteSectorAssetMappingReader


def test_bottleneck_snapshot_filters_by_lookback_and_release_date():
    conn = _conn_with_bottleneck_tables()
    conn.executemany(
        """
        INSERT INTO bottleneck_indicators
        (indicator_key, indicator_name, sector_code, value_date, release_date, value, unit, source, layer)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("OLD", "old row", "SEMICONDUCTOR", "2022-12-31", "2023-01-15", 10.0, "pt", "test", "relative_strength"),
            ("KNOWN", "known row", "SEMICONDUCTOR", "2024-02-29", "2024-03-01", 75.0, "pt", "test", "relative_strength"),
            ("FUTURE", "future row", "SEMICONDUCTOR", "2024-03-31", "2024-04-01", 90.0, "pt", "test", "relative_strength"),
            ("NORELEASE", "missing release", "SEMICONDUCTOR", "2024-02-29", None, 88.0, "pt", "test", "relative_strength"),
        ],
    )

    snapshot = get_bottleneck_snapshot(conn, date(2024, 3, 10), lookback_months=12)

    assert [item.indicator_key for item in snapshot.indicators] == ["KNOWN"]
    assert snapshot.indicators[0].value_date == date(2024, 2, 29)
    assert snapshot.indicators[0].release_date == date(2024, 3, 1)
    assert snapshot.indicators[0].value == 75.0


def test_sector_asset_mappings_return_active_assets_in_priority_order():
    conn = _conn_with_bottleneck_tables()
    conn.executemany(
        """
        INSERT INTO sector_asset_map
        (sector_code, asset_code, asset_name, asset_type, currency, priority, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("SEMICONDUCTOR", "SMH", "VanEck Semiconductor ETF", "ETF", "USD", 20, 1),
            ("SEMICONDUCTOR", "000660", "SK hynix", "EQUITY", "KRW", 10, 1),
            ("SEMICONDUCTOR", "INACTIVE", "Inactive", "ETF", "USD", 1, 0),
            ("POWER", "GRID", "Grid ETF", "ETF", None, None, 1),
        ],
    )

    mappings = get_sector_asset_mappings(conn)

    assert [item.asset_code for item in mappings["SEMICONDUCTOR"]] == ["000660", "SMH"]
    assert mappings["POWER"][0].currency == "USD"
    assert mappings["POWER"][0].priority == 100
    assert "INACTIVE" not in {item.asset_code for items in mappings.values() for item in items}


def test_bottleneck_readers_return_empty_when_tables_are_missing():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    snapshot = get_bottleneck_snapshot(conn, date(2024, 3, 10), lookback_months=12)
    mappings = get_sector_asset_mappings(conn)

    assert snapshot.indicators == []
    assert mappings == {}


def test_sqlite_bottleneck_readers_return_strategy_input_models():
    conn = _conn_with_bottleneck_tables()
    conn.execute(
        """
        INSERT INTO bottleneck_indicators
        (indicator_key, indicator_name, sector_code, value_date, release_date, value, unit, source, layer)
        VALUES ('KNOWN', 'known row', 'SEMICONDUCTOR', '2024-02-29', '2024-03-01', 75, 'pt', 'test', 'relative_strength')
        """
    )
    conn.execute(
        """
        INSERT INTO sector_asset_map
        (sector_code, asset_code, asset_name, asset_type, currency, priority, is_active)
        VALUES ('SEMICONDUCTOR', 'SMH', 'VanEck Semiconductor ETF', 'ETF', 'USD', 20, 1)
        """
    )

    snapshot = SqliteBottleneckSnapshotReader(conn).read_bottleneck_snapshot(
        date(2024, 3, 10),
        lookback_months=12,
    )
    mappings = SqliteSectorAssetMappingReader(conn).read_sector_asset_mappings()

    assert snapshot.as_of_date == date(2024, 3, 10)
    assert snapshot.indicators[0].indicator_key == "KNOWN"
    assert snapshot.indicators[0].release_date == date(2024, 3, 1)
    assert mappings["SEMICONDUCTOR"][0].asset_code == "SMH"


def _conn_with_bottleneck_tables() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
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
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE sector_asset_map (
            sector_code TEXT,
            asset_code TEXT,
            asset_name TEXT,
            asset_type TEXT,
            currency TEXT,
            priority INTEGER,
            is_active INTEGER
        )
        """
    )
    return conn
