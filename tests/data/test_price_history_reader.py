from __future__ import annotations

import sqlite3
from datetime import date

from api.data.strategy_data_readers import SqlitePriceHistoryReader


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE market_prices (
            asset_code TEXT,
            price_date TEXT,
            close REAL,
            adj_close REAL,
            source TEXT
        );
        INSERT INTO market_prices VALUES ('SMH', '2024-02-29', 210.0, NULL, 'fixture');
        INSERT INTO market_prices VALUES ('SMH', '2024-03-08', 220.0, NULL, 'fixture');
        INSERT INTO market_prices VALUES ('SMH', '2024-03-11', 222.0, 221.5, 'fixture');
        INSERT INTO market_prices VALUES ('SMH', '2024-04-01', 230.0, NULL, 'future');
        INSERT INTO market_prices VALUES ('SPY', '2024-03-11', 500.0, NULL, 'fixture');
        """
    )
    return conn


def test_price_history_reader_returns_only_start_end_range():
    points = SqlitePriceHistoryReader(_conn()).read_price_history(
        "SMH",
        start_date=date(2024, 3, 1),
        end_date=date(2024, 3, 31),
    )

    assert [point.price_date for point in points] == [date(2024, 3, 8), date(2024, 3, 11)]
    assert [point.price for point in points] == [220.0, 221.5]


def test_price_history_reader_excludes_future_price_after_end_date():
    points = SqlitePriceHistoryReader(_conn()).read_price_history(
        "SMH",
        start_date=date(2024, 3, 1),
        end_date=date(2024, 3, 31),
    )

    assert all(point.price_date <= date(2024, 3, 31) for point in points)
    assert all(point.price != 230.0 for point in points)


def test_price_history_reader_missing_asset_returns_empty_list():
    points = SqlitePriceHistoryReader(_conn()).read_price_history(
        "MISSING",
        start_date=date(2024, 3, 1),
        end_date=date(2024, 3, 31),
    )

    assert points == []


def test_price_history_reader_preserves_source_as_of_and_date_metadata():
    points = SqlitePriceHistoryReader(_conn()).read_price_history(
        "SMH",
        start_date=date(2024, 3, 1),
        end_date=date(2024, 3, 31),
    )

    assert points[0].asset_code == "SMH"
    assert points[0].price_date == date(2024, 3, 8)
    assert points[0].source == "fixture"
    assert points[0].as_of_date == date(2024, 3, 31)

