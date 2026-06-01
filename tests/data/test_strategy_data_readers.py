from __future__ import annotations

import ast
import sqlite3
from datetime import date
from pathlib import Path

from api.data.strategy_data_readers import (
    SqliteBottleneckSnapshotReader,
    SqliteMacroSnapshotReader,
    SqlitePriceHistoryReader,
    SqliteSectorAssetMappingReader,
)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_sqlite_macro_snapshot_reader_returns_latest_point_in_time_value():
    conn = _conn()
    conn.executescript(
        """
        CREATE TABLE indicators (
            indicator TEXT,
            value REAL,
            unit TEXT,
            date TEXT,
            source TEXT
        );
        INSERT INTO indicators VALUES ('VIXCLS', 20.0, NULL, '2024-03-01', 'fixture');
        INSERT INTO indicators VALUES ('VIXCLS', 18.5, NULL, '2024-03-08', 'fixture');
        """
    )

    snapshot = SqliteMacroSnapshotReader(conn).read_macro_snapshot(date(2024, 3, 10))

    assert snapshot.as_of_date == date(2024, 3, 10)
    assert snapshot.get_value("vixcls") == 18.5


def test_sqlite_macro_snapshot_reader_excludes_future_rows():
    conn = _conn()
    conn.executescript(
        """
        CREATE TABLE indicators (
            indicator TEXT,
            value REAL,
            unit TEXT,
            date TEXT,
            source TEXT
        );
        INSERT INTO indicators VALUES ('VIXCLS', 18.5, NULL, '2024-03-08', 'fixture');
        INSERT INTO indicators VALUES ('VIXCLS', 40.0, NULL, '2024-03-11', 'fixture');
        """
    )

    snapshot = SqliteMacroSnapshotReader(conn).read_macro_snapshot(date(2024, 3, 10))

    assert snapshot.get_value("VIXCLS") == 18.5


def test_sqlite_bottleneck_snapshot_reader_converts_indicator_rows():
    conn = _conn()
    conn.executescript(
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
        );
        INSERT INTO bottleneck_indicators
        VALUES ('RS_SEMI', 'Relative strength', 'SEMICONDUCTOR',
                '2024-03-01', '2024-03-05', 72.0, 'score', 'fixture',
                'relative_strength');
        """
    )

    snapshot = SqliteBottleneckSnapshotReader(conn).read_bottleneck_snapshot(
        date(2024, 3, 10),
        lookback_months=12,
    )

    assert len(snapshot.indicators) == 1
    assert snapshot.indicators[0].sector_code == "SEMICONDUCTOR"
    assert snapshot.indicators[0].value == 72.0


def test_sqlite_sector_mapping_reader_returns_empty_mapping_for_empty_db():
    conn = _conn()

    assert SqliteSectorAssetMappingReader(conn).read_sector_asset_mappings() == {}


def test_sqlite_price_history_reader_returns_ordered_price_points():
    conn = _conn()
    conn.executescript(
        """
        CREATE TABLE market_prices (
            asset_code TEXT,
            price_date TEXT,
            close REAL,
            adj_close REAL
        );
        INSERT INTO market_prices VALUES ('SMH', '2024-03-08', 220.0, NULL);
        INSERT INTO market_prices VALUES ('SMH', '2024-03-11', 222.0, 221.5);
        INSERT INTO market_prices VALUES ('SPY', '2024-03-11', 500.0, NULL);
        """
    )

    points = SqlitePriceHistoryReader(conn).read_price_history(
        "SMH",
        start_date=date(2024, 3, 1),
        end_date=date(2024, 3, 31),
    )

    assert [point.price_date for point in points] == [date(2024, 3, 8), date(2024, 3, 11)]
    assert [point.price for point in points] == [220.0, 221.5]


def test_strategy_data_reader_module_does_not_import_strategy_engines():
    path = Path("api/data/strategy_data_readers.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden = {
        "api.strategy.macro_engine",
        "api.strategy.triplea_allocator",
    }

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert imports.isdisjoint(forbidden)

