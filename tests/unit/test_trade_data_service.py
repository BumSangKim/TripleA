import sqlite3
from datetime import date

from api.domain.trade_data import TradeSnapshot
from api.trade_data_service import SqliteTradeSnapshotReader, get_trade_snapshot


def test_get_trade_snapshot_returns_empty_when_table_missing():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    snapshot = get_trade_snapshot(conn, date(2024, 3, 10), lookback_months=12)

    assert snapshot == TradeSnapshot(as_of_date=date(2024, 3, 10), lookback_months=12, items=[])


def test_get_trade_snapshot_excludes_future_release_rows():
    conn = _conn_with_trade_series()
    conn.executemany(
        """
        INSERT INTO trade_series
        (period, country, flow, item_code, amount_usd, quantity, unit, yoy, mom, source, release_date)
        VALUES (?, 'KR', 'export', 'HS_8542', 100, NULL, NULL, ?, NULL, 'test', ?)
        """,
        [
            ("2024-01", 5.0, "2024-02-15"),
            ("2024-02", 80.0, "2024-03-15"),
        ],
    )

    snapshot = get_trade_snapshot(conn, date(2024, 3, 10), lookback_months=12)

    assert [item.period for item in snapshot.items] == ["2024-01"]
    assert snapshot.items[0].yoy == 5.0


def test_get_trade_snapshot_excludes_rows_before_lookback():
    conn = _conn_with_trade_series()
    conn.executemany(
        """
        INSERT INTO trade_series
        (period, country, flow, item_code, amount_usd, quantity, unit, yoy, mom, source, release_date)
        VALUES (?, 'KR', 'export', 'HS_8542', 100, NULL, NULL, ?, NULL, 'test', ?)
        """,
        [
            ("2022-12", 10.0, "2023-01-15"),
            ("2024-01", 20.0, "2024-02-15"),
        ],
    )

    snapshot = get_trade_snapshot(conn, date(2024, 3, 10), lookback_months=12)

    assert [item.period for item in snapshot.items] == ["2024-01"]


def test_get_trade_snapshot_converts_rows_to_domain_dataclass():
    conn = _conn_with_trade_series()
    conn.execute(
        """
        INSERT INTO trade_series
        (period, country, flow, item_code, item_name, amount_usd, quantity, unit, yoy, mom, source, release_date)
        VALUES ('2024-01', 'KR', 'export', 'HS_8542', 'Semiconductors', 123.4, 10, 'kg', 12.5, 1.2, 'test', '2024-02-15')
        """
    )

    item = get_trade_snapshot(conn, date(2024, 3, 10), lookback_months=12).items[0]

    assert item.item_code == "HS_8542"
    assert item.item_name == "Semiconductors"
    assert item.amount_usd == 123.4
    assert item.quantity == 10.0
    assert item.release_date == date(2024, 2, 15)


def test_sqlite_trade_snapshot_reader_delegates_to_get_trade_snapshot():
    conn = _conn_with_trade_series()
    conn.execute(
        """
        INSERT INTO trade_series
        (period, country, flow, item_code, amount_usd, quantity, unit, yoy, mom, source, release_date)
        VALUES ('2024-01', 'KR', 'export', 'HS_8542', 100, NULL, NULL, 5.0, NULL, 'test', '2024-02-15')
        """
    )

    snapshot = SqliteTradeSnapshotReader(conn).get_trade_snapshot(date(2024, 3, 10), lookback_months=12)

    assert isinstance(snapshot, TradeSnapshot)
    assert len(snapshot.items) == 1


def _conn_with_trade_series():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
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
        )
        """
    )
    return conn
